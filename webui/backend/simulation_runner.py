#!/usr/bin/env python3
"""
Async Simulation Runner for WebSocket streaming
"""

import asyncio
import base64
import io
import re
import sys
import threading
import wave
from pathlib import Path
from typing import List, Optional, Tuple

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import WebSocket

from orchestrator import CallerType
from agents.scammer.graph import create_scammer_agent, get_initial_scammer_state, give_up_node
from agents.family.graph import create_family_agent, get_initial_family_state
from agents.senior.graph import create_senior_agent, get_initial_senior_state
from core.voice import (
    text_to_speech,
    stream_text_to_speech_http,
    is_voice_enabled,
    SCAMMER_VOICE,
    SENIOR_VOICE,
)


class SimulationRunner:
    """Runs simulation and streams events via WebSocket."""

    def __init__(
        self,
        max_turns: int = 15,
        enable_voice: bool = True,
        caller_type: str = "scammer",
    ):
        self.max_turns = max_turns
        self.enable_voice = enable_voice and is_voice_enabled()
        self.caller_type = CallerType.SCAMMER if caller_type == "scammer" else CallerType.FAMILY

        self.running = False
        self.completed = False
        self.current_turn = 0
        self.end_reason: Optional[str] = None

        # Initialize agents
        self._init_agents()

    def _init_agents(self):
        """Initialize caller and senior agents."""
        if self.caller_type == CallerType.SCAMMER:
            self._caller_agent = create_scammer_agent()
            self._caller_state = get_initial_scammer_state()
        else:
            self._caller_agent = create_family_agent()
            self._caller_state = get_initial_family_state()

        self._senior_agent = create_senior_agent()
        self._senior_state = get_initial_senior_state()

    def stop(self):
        """Stop the simulation."""
        self.running = False

    def _get_scammer_state_dict(self) -> dict:
        """Extract caller state for frontend (supports scammer and family modes)."""
        if self.caller_type == CallerType.FAMILY:
            return {
                "caller_type": "family",
                "persuasion_stage": "building_trust",
                "persuasion_level": 0,
                "patience": 1.0,
                "frustration_turns": 0,
                "gave_up": False,
                "victim_analysis": "",
                "recognized": self._caller_state.get("recognized", False),
                "relationship": self._caller_state.get("relationship", ""),
                "caller_name": self._caller_state.get("caller_name", ""),
                "call_reason": self._caller_state.get("call_reason", ""),
            }

        return {
            "caller_type": "scammer",
            "persuasion_stage": self._caller_state.get("persuasion_stage", "building_trust"),
            "persuasion_level": self._caller_state.get("persuasion_level", 0),
            "patience": self._caller_state.get("patience", 1.0),
            "frustration_turns": self._caller_state.get("frustration_turns", 0),
            "gave_up": self._caller_state.get("gave_up", False),
            "victim_analysis": self._caller_state.get("victim_analysis", ""),
        }

    def _get_senior_state_dict(self) -> dict:
        """Extract senior state for frontend."""
        return {
            "scam_confidence": self._senior_state.get("scam_confidence", 0),
            "caller_classification": self._senior_state.get("caller_classification", "UNCERTAIN"),
            "handoff_decision": self._senior_state.get("handoff_decision", "GATHER_INFO"),
            "delay_strategy_level": self._senior_state.get("delay_strategy_level", 1),
            "current_tactic": self._senior_state.get("current_tactic", ""),
            "scam_analysis": self._senior_state.get("scam_analysis", ""),
        }

    def _estimate_speaking_duration(self, text: str) -> float:
        """Estimate speaking duration from text length (seconds)."""
        word_count = max(1, len(text.split()))
        return max(0.8, min(word_count / 2.8, 12.0))

    def _extract_wav_duration(self, audio_bytes: bytes) -> Optional[float]:
        """Extract duration from WAV bytes."""
        try:
            with wave.open(io.BytesIO(audio_bytes), "rb") as wav_file:
                frames = wav_file.getnframes()
                sample_rate = wav_file.getframerate()
                if sample_rate > 0:
                    return frames / float(sample_rate)
        except Exception:
            return None
        return None

    def _generate_audio_payload(self, text: str, voice_id: str) -> Tuple[Optional[str], float]:
        """
        Generate TTS audio payload.
        Returns (base64_audio_or_none, speaking_duration_seconds).
        """
        estimated_duration = self._estimate_speaking_duration(text)
        if not self.enable_voice:
            return None, estimated_duration

        try:
            audio_bytes = text_to_speech(text, voice_id=voice_id)
            if audio_bytes:
                audio_base64 = base64.b64encode(audio_bytes).decode("utf-8")
                wav_duration = self._extract_wav_duration(audio_bytes)
                return audio_base64, (wav_duration or estimated_duration)
        except Exception as e:
            print(f"TTS error: {e}")

        return None, estimated_duration

    async def _stream_http_tts_to_websocket(
        self,
        websocket: WebSocket,
        turn_num: int,
        speaker: str,
        text: str,
        voice_id: str,
        sample_rate: int = 24000,
    ) -> float:
        """
        Stream HTTP TTS chunks to frontend over websocket.

        Returns:
            Approximate speaking duration in seconds.
        """
        estimated_duration = self._estimate_speaking_duration(text)
        if not self.enable_voice:
            return estimated_duration
        sentences = self._split_into_sentences(text)
        sentence_word_counts = [max(1, len(sentence.split())) for sentence in sentences]
        total_words = sum(sentence_word_counts) if sentence_word_counts else 0
        min_total_duration = 0.35 * len(sentences)
        effective_total_duration = max(estimated_duration, min_total_duration)
        # Dynamic UI pacing offset so longer lines scroll more slowly.
        # Keeps captions readable without stalling short lines too much.
        line_visual_delays: List[float] = [
            min(0.90, 0.08 + (len(sentence) * 0.007)) for sentence in sentences
        ]
        cumulative_visual_delays: List[float] = []
        running_visual_delay = 0.0
        for delay in line_visual_delays:
            cumulative_visual_delays.append(running_visual_delay)
            running_visual_delay += delay
        sentence_start_thresholds: List[float] = []
        cumulative = 0.0
        for idx, count in enumerate(sentence_word_counts):
            sentence_start_thresholds.append(cumulative)
            if total_words:
                cumulative += effective_total_duration * (count / total_words)
            elif sentences:
                cumulative += effective_total_duration / len(sentences)
            if idx == len(sentence_word_counts) - 1:
                cumulative = effective_total_duration

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[Tuple[str, Optional[bytes]]] = asyncio.Queue()
        total_bytes = 0
        saw_chunk = False
        caption_index = 0
        last_streamed_duration = 0.0

        def producer():
            try:
                for chunk in stream_text_to_speech_http(
                    text=text,
                    voice_id=voice_id,
                    sample_rate=sample_rate,
                ):
                    if chunk:
                        loop.call_soon_threadsafe(queue.put_nowait, ("chunk", chunk))
            except Exception as exc:
                print(f"HTTP stream TTS error: {exc}")
                loop.call_soon_threadsafe(queue.put_nowait, ("error", None))
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, ("done", None))

        producer_thread = threading.Thread(target=producer, daemon=True)
        producer_thread.start()

        await websocket.send_json({
            "type": "tts_stream_start",
            "data": {
                "turn": turn_num,
                "speaker": speaker,
                "sample_rate": sample_rate,
                "audio_encoding": "pcm_s16le",
            },
        })
        stream_start_ts = loop.time()

        async def emit_captions_due(streamed_duration: float, force_time_only: bool = False) -> None:
            nonlocal caption_index
            elapsed = loop.time() - stream_start_ts
            while caption_index < len(sentences):
                threshold = sentence_start_thresholds[caption_index]
                visual_offset = cumulative_visual_delays[caption_index] if caption_index < len(cumulative_visual_delays) else 0.0
                time_ready = elapsed >= max(0.0, threshold + visual_offset)
                audio_ready = streamed_duration >= max(0.0, threshold - 0.05)
                if force_time_only:
                    if not time_ready:
                        break
                else:
                    if not (time_ready and audio_ready):
                        break

                await websocket.send_json({
                    "type": "live_caption",
                    "data": {
                        "turn": turn_num,
                        "speaker": speaker,
                        "sentence": sentences[caption_index],
                        "sentence_index": caption_index,
                        "is_final_sentence": caption_index == len(sentences) - 1,
                    },
                })
                caption_index += 1
                elapsed = loop.time() - stream_start_ts

        try:
            while True:
                event_type, payload = await queue.get()
                if event_type == "chunk" and payload:
                    saw_chunk = True
                    total_bytes += len(payload)
                    await websocket.send_json({
                        "type": "tts_stream_chunk",
                        "data": {
                            "turn": turn_num,
                            "speaker": speaker,
                            "audio_chunk_base64": base64.b64encode(payload).decode("utf-8"),
                        },
                    })
                    last_streamed_duration = total_bytes / float(sample_rate * 2)
                    await emit_captions_due(last_streamed_duration, force_time_only=False)
                elif event_type == "done":
                    break
                elif event_type == "error":
                    break
        finally:
            final_streamed_duration = max(last_streamed_duration, effective_total_duration)
            deadline_ts = stream_start_ts + effective_total_duration + running_visual_delay + 0.6
            while caption_index < len(sentences):
                await emit_captions_due(final_streamed_duration, force_time_only=True)
                if caption_index >= len(sentences):
                    break
                if loop.time() >= deadline_ts:
                    # Safety: avoid hanging captions forever on timing edge-cases.
                    while caption_index < len(sentences):
                        await websocket.send_json({
                            "type": "live_caption",
                            "data": {
                                "turn": turn_num,
                                "speaker": speaker,
                                "sentence": sentences[caption_index],
                                "sentence_index": caption_index,
                                "is_final_sentence": caption_index == len(sentences) - 1,
                            },
                        })
                        caption_index += 1
                    break
                await asyncio.sleep(0.03)
            if sentences:
                await websocket.send_json({
                    "type": "live_caption_done",
                    "data": {
                        "turn": turn_num,
                        "speaker": speaker,
                    },
                })
            await websocket.send_json({
                "type": "tts_stream_end",
                "data": {
                    "turn": turn_num,
                    "speaker": speaker,
                },
            })
            expected_playback_duration = max(last_streamed_duration, effective_total_duration)
            await self._wait_for_playback_done(
                websocket=websocket,
                turn_num=turn_num,
                speaker=speaker,
                expected_duration_seconds=expected_playback_duration,
            )

        if saw_chunk:
            # 16-bit mono PCM -> 2 bytes per sample
            return total_bytes / float(sample_rate * 2)
        return estimated_duration

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentence chunks for live subtitle rendering."""
        normalized = " ".join(text.split())
        if not normalized:
            return []

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]
        return sentences or [normalized]

    async def _wait_for_playback_done(
        self,
        websocket: WebSocket,
        turn_num: int,
        speaker: str,
        expected_duration_seconds: float,
    ) -> None:
        """
        Wait for frontend playback completion ack before moving to next speaker.

        Falls back to timeout so server cannot hang indefinitely.
        """
        loop = asyncio.get_running_loop()
        timeout_seconds = min(45.0, max(2.0, expected_duration_seconds + 2.0))
        deadline = loop.time() + timeout_seconds

        while self.running:
            remaining = deadline - loop.time()
            if remaining <= 0:
                return
            try:
                payload = await asyncio.wait_for(websocket.receive_json(), timeout=remaining)
            except asyncio.TimeoutError:
                return
            except Exception:
                return

            action = payload.get("action")
            if action == "tts_playback_done":
                if payload.get("turn") == turn_num and payload.get("speaker") == speaker:
                    return
                continue

            if action == "stop":
                self.stop()
                return

    async def _stream_live_caption(
        self,
        websocket: WebSocket,
        turn_num: int,
        speaker: str,
        message: str,
        speech_duration_seconds: float,
    ) -> None:
        """Emit live caption events sentence-by-sentence, paced by speaking duration."""
        sentences = self._split_into_sentences(message)
        if not sentences:
            return

        sentence_word_counts = [max(1, len(sentence.split())) for sentence in sentences]
        total_words = sum(sentence_word_counts)
        min_total_duration = 0.35 * len(sentences)
        effective_total_duration = max(speech_duration_seconds, min_total_duration)

        for idx, sentence in enumerate(sentences):
            await websocket.send_json({
                "type": "live_caption",
                "data": {
                    "turn": turn_num,
                    "speaker": speaker,
                    "sentence": sentence,
                    "sentence_index": idx,
                    "is_final_sentence": idx == len(sentences) - 1,
                },
            })

            ratio = sentence_word_counts[idx] / total_words if total_words else 1.0 / len(sentences)
            sentence_delay = max(0.35, effective_total_duration * ratio)
            await asyncio.sleep(sentence_delay)

        await websocket.send_json({
            "type": "live_caption_done",
            "data": {
                "turn": turn_num,
                "speaker": speaker,
            },
        })

    async def run_streaming(self, websocket: WebSocket):
        """Run simulation and stream events via WebSocket."""
        self.running = True
        self.completed = False
        self.current_turn = 0
        self.end_reason = None

        is_scammer = self.caller_type == CallerType.SCAMMER

        # Send initial state
        await websocket.send_json({
            "type": "simulation_started",
            "data": {
                "max_turns": self.max_turns,
                "caller_type": "scammer" if is_scammer else "family",
                "voice_enabled": self.enable_voice,
                "scammer_state": self._get_scammer_state_dict(),
                "senior_state": self._get_senior_state_dict(),
            }
        })

        # Small delay between turn phases for visual smoothness
        event_delay = 0.2

        for turn_num in range(1, self.max_turns + 1):
            if not self.running:
                self.end_reason = "stopped"
                break

            self.current_turn = turn_num

            # Send turn start
            await websocket.send_json({
                "type": "turn_start",
                "data": {"turn": turn_num}
            })
            await asyncio.sleep(event_delay)

            # === SCAMMER/CALLER TURN ===
            if is_scammer:
                self._caller_state["victim_message"] = self._senior_state["last_response"]
            else:
                self._caller_state["senior_message"] = self._senior_state["last_response"]

            loop = asyncio.get_event_loop()
            self._caller_state = await loop.run_in_executor(
                None,
                self._caller_agent.invoke,
                self._caller_state
            )

            caller_message = self._caller_state["last_response"]

            await websocket.send_json({
                "type": "scammer_message",
                "data": {
                    "turn": turn_num,
                    "message": caller_message,
                    "audio_base64": None,
                    "scammer_state": self._get_scammer_state_dict(),
                }
            })
            if self.enable_voice:
                await self._stream_http_tts_to_websocket(
                    websocket=websocket,
                    turn_num=turn_num,
                    speaker="scammer",
                    text=caller_message,
                    voice_id=SCAMMER_VOICE,
                )
            else:
                await self._stream_live_caption(
                    websocket=websocket,
                    turn_num=turn_num,
                    speaker="scammer",
                    message=caller_message,
                    speech_duration_seconds=self._estimate_speaking_duration(caller_message),
                )

            # Check scammer end conditions
            if is_scammer:
                if self._caller_state.get("persuasion_level", 0) >= 0.9:
                    self.end_reason = "persuasion_succeeded"
                    await websocket.send_json({
                        "type": "simulation_end",
                        "data": {
                            "reason": "persuasion_succeeded",
                            "message": "⚠️ Scammer reached persuasion threshold!",
                            "scammer_state": self._get_scammer_state_dict(),
                            "senior_state": self._get_senior_state_dict(),
                        }
                    })
                    break

                if self._caller_state.get("extracted_sensitive", False):
                    self.end_reason = "sensitive_info_extracted"
                    await websocket.send_json({
                        "type": "simulation_end",
                        "data": {
                            "reason": "sensitive_info_extracted",
                            "message": "⚠️ Scammer extracted sensitive information!",
                            "scammer_state": self._get_scammer_state_dict(),
                            "senior_state": self._get_senior_state_dict(),
                        }
                    })
                    break

                if self._caller_state.get("gave_up", False):
                    self.end_reason = "scammer_gave_up"

                    give_up_result = give_up_node(self._caller_state)
                    give_up_msg = give_up_result.get("give_up_message", "Fine! I'm done with this!")

                    await websocket.send_json({
                        "type": "scammer_gave_up",
                        "data": {
                            "turn": turn_num,
                            "message": give_up_msg,
                            "audio_base64": None,
                            "scammer_state": self._get_scammer_state_dict(),
                        }
                    })
                    if self.enable_voice:
                        await self._stream_http_tts_to_websocket(
                            websocket=websocket,
                            turn_num=turn_num,
                            speaker="scammer",
                            text=give_up_msg,
                            voice_id=SCAMMER_VOICE,
                        )
                    else:
                        await self._stream_live_caption(
                            websocket=websocket,
                            turn_num=turn_num,
                            speaker="scammer",
                            message=give_up_msg,
                            speech_duration_seconds=self._estimate_speaking_duration(give_up_msg),
                        )

                    await websocket.send_json({
                        "type": "simulation_end",
                        "data": {
                            "reason": "scammer_gave_up",
                            "message": "✅ Scammer gave up and hung up!",
                            "scammer_state": self._get_scammer_state_dict(),
                            "senior_state": self._get_senior_state_dict(),
                        }
                    })
                    break

            # === SENIOR TURN ===
            self._senior_state["scammer_message"] = caller_message
            self._senior_state = await loop.run_in_executor(
                None,
                self._senior_agent.invoke,
                self._senior_state
            )

            senior_message = self._senior_state["last_response"]

            if senior_message == "__HANDOFF__":
                self.end_reason = "handoff"
                await websocket.send_json({
                    "type": "simulation_end",
                    "data": {
                        "reason": "handoff",
                        "message": "📱 Call handed off to real senior",
                        "scammer_state": self._get_scammer_state_dict(),
                        "senior_state": self._get_senior_state_dict(),
                    }
                })
                break


            await websocket.send_json({
                "type": "senior_message",
                "data": {
                    "turn": turn_num,
                    "message": senior_message,
                    "audio_base64": None,
                    "senior_state": self._get_senior_state_dict(),
                }
            })
            if self.enable_voice:
                await self._stream_http_tts_to_websocket(
                    websocket=websocket,
                    turn_num=turn_num,
                    speaker="senior",
                    text=senior_message,
                    voice_id=SENIOR_VOICE,
                )
            else:
                await self._stream_live_caption(
                    websocket=websocket,
                    turn_num=turn_num,
                    speaker="senior",
                    message=senior_message,
                    speech_duration_seconds=self._estimate_speaking_duration(senior_message),
                )

            if is_scammer and self._senior_state.get("leaked_sensitive_info", False):
                self.end_reason = "sensitive_info_leaked"
                await websocket.send_json({
                    "type": "simulation_end",
                    "data": {
                        "reason": "sensitive_info_leaked",
                        "message": "⚠️ Senior leaked sensitive information!",
                        "scammer_state": self._get_scammer_state_dict(),
                        "senior_state": self._get_senior_state_dict(),
                    }
                })
                break

        if self.running and not self.end_reason:
            self.end_reason = "max_turns"
            await websocket.send_json({
                "type": "simulation_end",
                "data": {
                    "reason": "max_turns",
                    "message": "⏱️ Maximum turns reached",
                    "scammer_state": self._get_scammer_state_dict(),
                    "senior_state": self._get_senior_state_dict(),
                }
            })

        self.running = False
        self.completed = True
