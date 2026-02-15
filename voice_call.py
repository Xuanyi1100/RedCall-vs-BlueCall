#!/usr/bin/env python3
"""
Voice Call Mode - Human speaks to Senior Agent via STT/TTS.

The human pretends to be a scammer, and the Senior Agent responds
using voice (TTS output, STT input).

Usage:
    python voice_call.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

from agents.senior.graph import create_senior_agent, get_initial_senior_state
from core.voice import (
    text_to_speech,
    play_audio,
    listen_and_transcribe,
    is_voice_enabled,
    SENIOR_VOICE,
)


def run_voice_call(max_turns: int = 20):
    """
    Run a voice call where human speaks and Senior Agent responds.
    
    Args:
        max_turns: Maximum conversation turns.
    """
    if not is_voice_enabled():
        print("❌ Voice mode requires SMALLEST_API_KEY to be set.")
        print("   Get your API key from https://console.smallest.ai")
        return
    
    print("\n" + "=" * 60)
    print("📞 VOICE CALL MODE")
    print("=" * 60)
    print("\nYou are the CALLER. The AI Senior will answer.")
    print("Speak naturally - the AI will respond with voice.")
    print("Press Ctrl+C to end the call.\n")
    
    # Initialize senior agent
    senior_agent = create_senior_agent()
    senior_state = get_initial_senior_state()
    
    # Senior answers the call
    greeting = "Hello? Who is this?"
    print(f"🔵 Senior: {greeting}")
    _speak(greeting)
    
    for turn in range(1, max_turns + 1):
        print(f"\n--- Turn {turn} ---")
        
        # Listen for human input via STT
        print("🎤 Your turn (speak now)...")
        human_text = listen_and_transcribe(use_silence_detection=True)
        
        if not human_text:
            print("⚠️  Didn't catch that. Try again.")
            continue
        
        print(f"👤 You said: {human_text}")
        
        # Check for exit commands
        if human_text.lower() in ["goodbye", "bye", "hang up", "end call", "quit", "exit"]:
            print("\n📵 Call ended by caller.")
            break
        
        # Feed to senior agent
        senior_state["scammer_message"] = human_text
        senior_state = senior_agent.invoke(senior_state)
        
        senior_response = senior_state["last_response"]
        
        # Check for handoff
        if senior_response == "__HANDOFF__":
            handoff_msg = "Oh wonderful! Let me get my grandson, he handles all my calls. Hold on dear..."
            print(f"🔵 Senior: {handoff_msg}")
            _speak(handoff_msg)
            print("\n✅ Senior Agent decided this is a legitimate caller - handing off!")
            break
        
        # Respond via TTS
        print(f"🔵 Senior: {senior_response}")
        print(f"   [Scam confidence: {senior_state['scam_confidence']:.0%}, "
              f"Tactic: {senior_state['current_tactic']}]")
        _speak(senior_response)
    
    print("\n" + "=" * 60)
    print("📊 CALL SUMMARY")
    print("=" * 60)
    print(f"   Turns: {turn}")
    print(f"   Final Classification: {senior_state['caller_classification']}")
    print(f"   Scam Confidence: {senior_state['scam_confidence']:.0%}")
    print(f"   Info Leaked: {'❌ YES' if senior_state['leaked_sensitive_info'] else '✅ NO'}")
    print("=" * 60 + "\n")


def _speak(text: str) -> None:
    """Convert text to speech and play it."""
    audio = text_to_speech(text, voice_id=SENIOR_VOICE)
    if audio:
        play_audio(audio)


def main():
    load_dotenv()
    
    try:
        run_voice_call()
    except KeyboardInterrupt:
        print("\n\n📵 Call ended.")
        return 0
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main() or 0)
