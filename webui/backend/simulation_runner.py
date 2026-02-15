#!/usr/bin/env python3
"""
Async Simulation Runner for WebSocket streaming
"""

import asyncio
import base64
import io
import re
import sys
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
from core.voice import text_to_speech, is_voice_enabled, SCAMMER_VOICE, SENIOR_VOICE


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

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentence chunks for live subtitle rendering."""
        normalized = " ".join(text.split())
        if not normalized:
            return []

        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalized) if s.strip()]
        return sentences or [normalized]

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
            caller_audio, caller_speaking_duration = await loop.run_in_executor(
                None,
                self._generate_audio_payload,
                caller_message,
                SCAMMER_VOICE
            )

            await websocket.send_json({
                "type": "scammer_message",
                "data": {
                    "turn": turn_num,
                    "message": caller_message,
                    "audio_base64": caller_audio,
                    "scammer_state": self._get_scammer_state_dict(),
                }
            })

            await self._stream_live_caption(
                websocket=websocket,
                turn_num=turn_num,
                speaker="scammer",
                message=caller_message,
                speech_duration_seconds=caller_speaking_duration,
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
                    give_up_audio, give_up_duration = await loop.run_in_executor(
                        None,
                        self._generate_audio_payload,
                        give_up_msg,
                        SCAMMER_VOICE
                    )

                    await websocket.send_json({
                        "type": "scammer_gave_up",
                        "data": {
                            "turn": turn_num,
                            "message": give_up_msg,
                            "audio_base64": give_up_audio,
                            "scammer_state": self._get_scammer_state_dict(),
                        }
                    })

                    await self._stream_live_caption(
                        websocket=websocket,
                        turn_num=turn_num,
                        speaker="scammer",
                        message=give_up_msg,
                        speech_duration_seconds=give_up_duration,
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

            senior_audio, senior_speaking_duration = await loop.run_in_executor(
                None,
                self._generate_audio_payload,
                senior_message,
                SENIOR_VOICE
            )

            await websocket.send_json({
                "type": "senior_message",
                "data": {
                    "turn": turn_num,
                    "message": senior_message,
                    "audio_base64": senior_audio,
                    "senior_state": self._get_senior_state_dict(),
                }
            })

            await self._stream_live_caption(
                websocket=websocket,
                turn_num=turn_num,
                speaker="senior",
                message=senior_message,
                speech_duration_seconds=senior_speaking_duration,
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
