"""Conversation orchestrator for the multi-agent scam simulation."""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from agents.scammer.graph import create_scammer_agent, get_initial_scammer_state
from agents.scammer.state import ScammerState
from agents.senior.graph import create_senior_agent, get_initial_senior_state
from agents.senior.state import SeniorState
from core.voice import text_to_speech, is_voice_enabled, play_audio_file, SCAMMER_VOICE, SENIOR_VOICE


@dataclass
class TurnRecord:
    """Record of a single conversation turn."""
    turn_number: int
    scammer_message: str
    senior_message: str
    scam_confidence: float
    persuasion_level: float
    persuasion_stage: str
    delay_tactic: str
    # Voice audio paths (if voice mode enabled)
    scammer_audio_path: Optional[str] = None
    senior_audio_path: Optional[str] = None


@dataclass
class ConversationResult:
    """Final result of the conversation simulation."""
    turns: List[TurnRecord]
    total_turns: int
    final_scam_confidence: float
    final_persuasion_level: float
    sensitive_info_leaked: bool
    persuasion_succeeded: bool
    end_reason: str
    # Placeholder for voice API integration
    time_wasted_seconds: float = 0.0


@dataclass 
class Orchestrator:
    """
    Orchestrates the conversation between Scammer and Senior agents.
    
    This class maintains the global turn counter and passes only dialogue
    text between the two independent agents. No internal state is shared.
    """
    max_turns: int = 20
    persuasion_threshold: float = 0.9
    voice_mode: bool = False  # Enable TTS audio generation
    play_audio: bool = False  # Play audio in real-time
    audio_output_dir: str = "audio_output"  # Directory for audio files
    
    # Internal state (not shared with agents)
    _scammer_agent: Optional[object] = field(default=None, init=False)
    _senior_agent: Optional[object] = field(default=None, init=False)
    _scammer_state: Optional[ScammerState] = field(default=None, init=False)
    _senior_state: Optional[SeniorState] = field(default=None, init=False)
    _turns: List[TurnRecord] = field(default_factory=list, init=False)
    _voice_enabled: bool = field(default=False, init=False)
    
    def __post_init__(self):
        """Initialize the agents."""
        self._scammer_agent = create_scammer_agent()
        self._senior_agent = create_senior_agent()
        self._scammer_state = get_initial_scammer_state()
        self._senior_state = get_initial_senior_state()
        self._turns = []
        
        # Check if voice mode can be enabled
        if self.voice_mode:
            if is_voice_enabled():
                self._voice_enabled = True
                # Create audio output directory
                Path(self.audio_output_dir).mkdir(parents=True, exist_ok=True)
            else:
                print("⚠️  Voice mode requested but SMALLEST_API_KEY not set. Running in text-only mode.")
                self._voice_enabled = False
    
    def run(self, verbose: bool = True) -> ConversationResult:
        """
        Run the conversation simulation.
        
        Args:
            verbose: If True, print each turn as it happens.
            
        Returns:
            ConversationResult with full transcript and metrics.
        """
        end_reason = "max_turns_reached"
        
        for turn_num in range(1, self.max_turns + 1):
            if verbose:
                print(f"\n{'='*60}")
                print(f"TURN {turn_num}")
                print('='*60)
            
            # Step 1: Scammer generates message
            # Input: last senior message (or empty for cold open)
            self._scammer_state["victim_message"] = self._senior_state["last_response"]
            
            # Run scammer's full graph
            self._scammer_state = self._scammer_agent.invoke(self._scammer_state)
            scammer_message = self._scammer_state["last_response"]
            
            # Generate scammer audio if voice mode enabled
            scammer_audio_path = None
            if self._voice_enabled:
                scammer_audio_path = self._generate_audio(
                    scammer_message, SCAMMER_VOICE, turn_num, "scammer"
                )
            
            if verbose:
                print(f"\n🔴 Scammer: {scammer_message}")
                print(f"   [Scam Phase: {self._scammer_state['persuasion_stage']}, "
                      f"Victim Trust: {self._scammer_state['persuasion_level']:.0%}]")
                if scammer_audio_path:
                    print(f"   🔊 Audio: {scammer_audio_path}")
            
            # Play scammer audio if enabled
            if self.play_audio and scammer_audio_path:
                play_audio_file(scammer_audio_path)
            
            # Check if scammer succeeded
            if self._scammer_state["persuasion_level"] >= self.persuasion_threshold:
                end_reason = "persuasion_succeeded"
                self._record_turn(turn_num, scammer_message, "(scam succeeded)")
                if verbose:
                    print("\n⚠️  Scammer reached persuasion threshold!")
                break
            
            if self._scammer_state["extracted_sensitive"]:
                end_reason = "sensitive_info_extracted"
                self._record_turn(turn_num, scammer_message, "(info extracted)")
                if verbose:
                    print("\n⚠️  Scammer extracted sensitive information!")
                break
            
            # Step 2: Senior responds
            # Input: scammer's message
            self._senior_state["scammer_message"] = scammer_message
            
            # Run senior's full graph
            self._senior_state = self._senior_agent.invoke(self._senior_state)
            senior_message = self._senior_state["last_response"]
            
            # Generate senior audio if voice mode enabled
            senior_audio_path = None
            if self._voice_enabled:
                senior_audio_path = self._generate_audio(
                    senior_message, SENIOR_VOICE, turn_num, "senior"
                )
            
            if verbose:
                print(f"\n🔵 Senior: {senior_message}")
                print(f"   [Scam Detected: {self._senior_state['scam_confidence']:.0%}, "
                      f"Delay Move: {self._senior_state['current_tactic']}]")
                if senior_audio_path:
                    print(f"   🔊 Audio: {senior_audio_path}")
            
            # Play senior audio if enabled
            if self.play_audio and senior_audio_path:
                play_audio_file(senior_audio_path)
            
            # Check if senior leaked info
            if self._senior_state["leaked_sensitive_info"]:
                end_reason = "sensitive_info_leaked"
                self._record_turn(turn_num, scammer_message, senior_message)
                if verbose:
                    print("\n⚠️  Senior leaked sensitive information!")
                break
            
            # Record the turn
            self._record_turn(
                turn_num, scammer_message, senior_message,
                scammer_audio_path, senior_audio_path
            )
        
        if self._voice_enabled and verbose:
            print(f"\n🔊 Audio files saved to: {self.audio_output_dir}/")
        
        # Build final result
        return ConversationResult(
            turns=self._turns,
            total_turns=len(self._turns),
            final_scam_confidence=self._senior_state["scam_confidence"],
            final_persuasion_level=self._scammer_state["persuasion_level"],
            sensitive_info_leaked=self._senior_state["leaked_sensitive_info"],
            persuasion_succeeded=self._scammer_state["persuasion_level"] >= self.persuasion_threshold,
            end_reason=end_reason,
            # Placeholder: estimate ~30 seconds per turn for voice
            time_wasted_seconds=len(self._turns) * 30.0,
        )
    
    def _generate_audio(
        self,
        text: str,
        voice_id: str,
        turn_num: int,
        agent: str,
    ) -> Optional[str]:
        """Generate TTS audio for a message."""
        try:
            audio_bytes = text_to_speech(text, voice_id=voice_id)
            if audio_bytes:
                filename = f"turn_{turn_num:02d}_{agent}.wav"
                filepath = Path(self.audio_output_dir) / filename
                with open(filepath, "wb") as f:
                    f.write(audio_bytes)
                return str(filepath)
        except Exception as e:
            print(f"⚠️  Failed to generate audio: {e}")
        return None
    
    def _record_turn(
        self,
        turn_num: int,
        scammer_message: str,
        senior_message: str,
        scammer_audio_path: Optional[str] = None,
        senior_audio_path: Optional[str] = None,
    ) -> None:
        """Record a turn in the conversation history."""
        self._turns.append(TurnRecord(
            turn_number=turn_num,
            scammer_message=scammer_message,
            senior_message=senior_message,
            scam_confidence=self._senior_state["scam_confidence"],
            persuasion_level=self._scammer_state["persuasion_level"],
            persuasion_stage=self._scammer_state["persuasion_stage"],
            delay_tactic=self._senior_state["current_tactic"],
            scammer_audio_path=scammer_audio_path,
            senior_audio_path=senior_audio_path,
        ))


def run_simulation(
    max_turns: int = 20,
    persuasion_threshold: float = 0.9,
    verbose: bool = True,
    voice_mode: bool = False,
    play_audio: bool = False,
    audio_output_dir: str = "audio_output",
) -> ConversationResult:
    """
    Convenience function to run a simulation.
    
    Args:
        max_turns: Maximum number of conversation turns.
        persuasion_threshold: Persuasion level that ends the simulation.
        verbose: If True, print each turn.
        voice_mode: If True, generate TTS audio for each message.
        play_audio: If True, play audio in real-time (implies voice_mode).
        audio_output_dir: Directory to save audio files.
        
    Returns:
        ConversationResult with full transcript and metrics.
    """
    # play_audio implies voice_mode
    if play_audio:
        voice_mode = True
    
    orchestrator = Orchestrator(
        max_turns=max_turns,
        persuasion_threshold=persuasion_threshold,
        voice_mode=voice_mode,
        play_audio=play_audio,
        audio_output_dir=audio_output_dir,
    )
    return orchestrator.run(verbose=verbose)
