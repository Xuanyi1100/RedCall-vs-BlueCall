"""Conversation orchestrator for the multi-agent scam simulation."""

import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Union

from agents.scammer.graph import create_scammer_agent, get_initial_scammer_state, give_up_node
from agents.scammer.state import ScammerState
from agents.family.graph import create_family_agent, get_initial_family_state
from agents.family.state import FamilyState
from agents.senior.graph import create_senior_agent, get_initial_senior_state
from agents.senior.state import SeniorState
from core.voice import text_to_speech, is_voice_enabled, play_audio_file, SCAMMER_VOICE, SENIOR_VOICE


class CallerType(Enum):
    """Type of caller for the simulation."""
    SCAMMER = "scammer"
    FAMILY = "family"


@dataclass
class TurnRecord:
    """Record of a single conversation turn."""
    turn_number: int
    caller_message: str
    senior_message: str
    scam_confidence: float
    caller_classification: str
    # Scammer-specific (None for family calls)
    persuasion_level: Optional[float] = None
    persuasion_stage: Optional[str] = None
    patience: Optional[float] = None
    # Family-specific (None for scammer calls)
    recognized: Optional[bool] = None
    # Common
    delay_tactic: str = ""
    # Voice audio paths (if voice mode enabled)
    caller_audio_path: Optional[str] = None
    senior_audio_path: Optional[str] = None


@dataclass
class ConversationResult:
    """Final result of the conversation simulation."""
    turns: List[TurnRecord]
    total_turns: int
    caller_type: CallerType
    final_scam_confidence: float
    final_caller_classification: str
    end_reason: str
    # Scammer-specific metrics
    final_persuasion_level: Optional[float] = None
    final_patience: Optional[float] = None
    sensitive_info_leaked: bool = False
    persuasion_succeeded: bool = False
    scammer_gave_up: bool = False
    # Family-specific metrics
    family_recognized: bool = False
    handoff_succeeded: bool = False
    # Common
    time_wasted_seconds: float = 0.0


@dataclass 
class Orchestrator:
    """
    Orchestrates the conversation between a Caller (Scammer or Family) and Senior agents.
    
    This class maintains the global turn counter and passes only dialogue
    text between the two independent agents. No internal state is shared.
    """
    caller_type: CallerType = CallerType.SCAMMER
    max_turns: int = 20
    persuasion_threshold: float = 0.9
    voice_mode: bool = False  # Enable TTS audio generation
    play_audio: bool = False  # Play audio in real-time
    audio_output_dir: str = "audio_output"  # Directory for audio files
    family_scenario: Optional[dict] = None  # Custom family scenario
    
    # Internal state (not shared with agents)
    _caller_agent: Optional[object] = field(default=None, init=False)
    _senior_agent: Optional[object] = field(default=None, init=False)
    _caller_state: Optional[Union[ScammerState, FamilyState]] = field(default=None, init=False)
    _senior_state: Optional[SeniorState] = field(default=None, init=False)
    _turns: List[TurnRecord] = field(default_factory=list, init=False)
    _voice_enabled: bool = field(default=False, init=False)
    
    def __post_init__(self):
        """Initialize the agents based on caller type."""
        if self.caller_type == CallerType.SCAMMER:
            self._caller_agent = create_scammer_agent()
            self._caller_state = get_initial_scammer_state()
        else:
            self._caller_agent = create_family_agent()
            self._caller_state = get_initial_family_state(self.family_scenario)
        
        self._senior_agent = create_senior_agent()
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
        is_scammer = self.caller_type == CallerType.SCAMMER
        
        for turn_num in range(1, self.max_turns + 1):
            if verbose:
                print(f"\n{'='*60}")
                print(f"TURN {turn_num}")
                print('='*60)
            
            # Step 1: Caller generates message
            if is_scammer:
                self._caller_state["victim_message"] = self._senior_state["last_response"]
            else:
                self._caller_state["senior_message"] = self._senior_state["last_response"]
            
            # Run caller's graph
            self._caller_state = self._caller_agent.invoke(self._caller_state)
            caller_message = self._caller_state["last_response"]
            
            # Generate caller audio if voice mode enabled
            caller_audio_path = None
            if self._voice_enabled:
                caller_audio_path = self._generate_audio(
                    caller_message, SCAMMER_VOICE, turn_num, "caller"
                )
            
            if verbose:
                if is_scammer:
                    print(f"\n🔴 Scammer: {caller_message}")
                    print(f"   [Phase: {self._caller_state['persuasion_stage']}, "
                          f"Trust: {self._caller_state['persuasion_level']:.0%}, "
                          f"Patience: {self._caller_state['patience']:.0%}]")
                else:
                    print(f"\n💚 Family ({self._caller_state['caller_name']}): {caller_message}")
                    print(f"   [Recognized: {self._caller_state['recognized']}]")
                if caller_audio_path:
                    print(f"   🔊 Audio: {caller_audio_path}")
            
            # Play caller audio if enabled
            if self.play_audio and caller_audio_path:
                play_audio_file(caller_audio_path)
            
            # Check scammer-specific end conditions
            if is_scammer:
                if self._caller_state["persuasion_level"] >= self.persuasion_threshold:
                    end_reason = "persuasion_succeeded"
                    self._record_turn(turn_num, caller_message, "(scam succeeded)")
                    if verbose:
                        print("\n⚠️  Scammer reached persuasion threshold!")
                    break
                
                if self._caller_state["extracted_sensitive"]:
                    end_reason = "sensitive_info_extracted"
                    self._record_turn(turn_num, caller_message, "(info extracted)")
                    if verbose:
                        print("\n⚠️  Scammer extracted sensitive information!")
                    break
                
                if self._caller_state["gave_up"]:
                    end_reason = "scammer_gave_up"
                    # Generate frustrated hang-up message
                    give_up_result = give_up_node(self._caller_state)
                    give_up_msg = give_up_result.get("give_up_message", "Fine! I'm done with this!")
                    self._caller_state["give_up_message"] = give_up_msg
                    
                    if verbose:
                        print(f"\n🔴 Scammer: {give_up_msg}")
                        print("   [📵 HUNG UP - Lost patience]")
                        print("\n✅ Scammer gave up and hung up!")
                    
                    self._record_turn(turn_num, give_up_msg, "(scammer hung up)")
                    break
            
            # Step 2: Senior responds
            self._senior_state["scammer_message"] = caller_message
            
            # Run senior's graph
            self._senior_state = self._senior_agent.invoke(self._senior_state)
            senior_message = self._senior_state["last_response"]
            
            # Check for handoff signal
            if senior_message == "__HANDOFF__":
                end_reason = "handoff_to_senior"
                self._record_turn(turn_num, caller_message, "(call handed off to real senior)")
                if verbose:
                    if is_scammer:
                        print("\n⚠️  Senior agent decided to hand off call (false negative!)")
                    else:
                        print("\n✅ Call successfully handed off to real senior!")
                break
            
            # Generate senior audio if voice mode enabled
            senior_audio_path = None
            if self._voice_enabled:
                senior_audio_path = self._generate_audio(
                    senior_message, SENIOR_VOICE, turn_num, "senior"
                )
            
            if verbose:
                print(f"\n🔵 Senior: {senior_message}")
                print(f"   [Classification: {self._senior_state['caller_classification']}, "
                      f"Confidence: {self._senior_state['scam_confidence']:.0%}, "
                      f"Tactic: {self._senior_state['current_tactic']}]")
                if senior_audio_path:
                    print(f"   🔊 Audio: {senior_audio_path}")
            
            # Play senior audio if enabled
            if self.play_audio and senior_audio_path:
                play_audio_file(senior_audio_path)
            
            # Check if senior leaked info (only matters for scammer calls)
            if is_scammer and self._senior_state["leaked_sensitive_info"]:
                end_reason = "sensitive_info_leaked"
                self._record_turn(turn_num, caller_message, senior_message)
                if verbose:
                    print("\n⚠️  Senior leaked sensitive information!")
                break
            
            # Record the turn
            self._record_turn(
                turn_num, caller_message, senior_message,
                caller_audio_path, senior_audio_path
            )
        
        if self._voice_enabled and verbose:
            print(f"\n🔊 Audio files saved to: {self.audio_output_dir}/")
        
        # Build final result
        return self._build_result(end_reason)
    
    def _build_result(self, end_reason: str) -> ConversationResult:
        """Build the final ConversationResult based on caller type."""
        is_scammer = self.caller_type == CallerType.SCAMMER
        
        result = ConversationResult(
            turns=self._turns,
            total_turns=len(self._turns),
            caller_type=self.caller_type,
            final_scam_confidence=self._senior_state["scam_confidence"],
            final_caller_classification=self._senior_state["caller_classification"],
            end_reason=end_reason,
            time_wasted_seconds=len(self._turns) * 30.0,
        )
        
        if is_scammer:
            result.final_persuasion_level = self._caller_state["persuasion_level"]
            result.final_patience = self._caller_state["patience"]
            result.sensitive_info_leaked = self._senior_state["leaked_sensitive_info"]
            result.persuasion_succeeded = self._caller_state["persuasion_level"] >= self.persuasion_threshold
            result.scammer_gave_up = self._caller_state["gave_up"]
        else:
            result.family_recognized = self._caller_state["recognized"]
            result.handoff_succeeded = end_reason == "handoff_to_senior"
        
        return result
    
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
        caller_message: str,
        senior_message: str,
        caller_audio_path: Optional[str] = None,
        senior_audio_path: Optional[str] = None,
    ) -> None:
        """Record a turn in the conversation history."""
        is_scammer = self.caller_type == CallerType.SCAMMER
        
        record = TurnRecord(
            turn_number=turn_num,
            caller_message=caller_message,
            senior_message=senior_message,
            scam_confidence=self._senior_state["scam_confidence"],
            caller_classification=self._senior_state["caller_classification"],
            delay_tactic=self._senior_state["current_tactic"],
            caller_audio_path=caller_audio_path,
            senior_audio_path=senior_audio_path,
        )
        
        if is_scammer:
            record.persuasion_level = self._caller_state["persuasion_level"]
            record.persuasion_stage = self._caller_state["persuasion_stage"]
            record.patience = self._caller_state["patience"]
        else:
            record.recognized = self._caller_state["recognized"]
        
        self._turns.append(record)


def run_simulation(
    caller_type: CallerType = CallerType.SCAMMER,
    max_turns: int = 20,
    persuasion_threshold: float = 0.9,
    verbose: bool = True,
    voice_mode: bool = False,
    play_audio: bool = False,
    audio_output_dir: str = "audio_output",
    family_scenario: Optional[dict] = None,
) -> ConversationResult:
    """
    Convenience function to run a simulation.
    
    Args:
        caller_type: Type of caller (SCAMMER or FAMILY).
        max_turns: Maximum number of conversation turns.
        persuasion_threshold: Persuasion level that ends the simulation.
        verbose: If True, print each turn.
        voice_mode: If True, generate TTS audio for each message.
        play_audio: If True, play audio in real-time (implies voice_mode).
        audio_output_dir: Directory to save audio files.
        family_scenario: Custom scenario for family calls.
        
    Returns:
        ConversationResult with full transcript and metrics.
    """
    # play_audio implies voice_mode
    if play_audio:
        voice_mode = True
    
    orchestrator = Orchestrator(
        caller_type=caller_type,
        max_turns=max_turns,
        persuasion_threshold=persuasion_threshold,
        voice_mode=voice_mode,
        play_audio=play_audio,
        audio_output_dir=audio_output_dir,
        family_scenario=family_scenario,
    )
    return orchestrator.run(verbose=verbose)
