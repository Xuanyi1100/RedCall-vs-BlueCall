#!/usr/bin/env python3
"""
RedCall vs BlueCall - Multi-Agent Scam Simulation

A production-style MVP implementing two fully independent LangGraph agents:
- Scammer (Red Team): Attempts to extract sensitive information
- Senior Defender (Blue Team): Scam-baiting AI that wastes scammer's time

Usage:
    python main.py [--turns N] [--threshold T] [--quiet]
    
Environment:
    GOOGLE_API_KEY: Your Google Gemini API key
"""

import argparse
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

from orchestrator import run_simulation, CallerType
from evaluator import print_report


def parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Run a scam simulation between Red Team (Scammer) and Blue Team (Senior Defender)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python main.py                    # Run with defaults (20 turns)
    python main.py --turns 10         # Run for 10 turns max
    python main.py --threshold 0.8    # Lower persuasion threshold
    python main.py --quiet            # Only show final report
        """,
    )
    
    parser.add_argument(
        "--turns",
        type=int,
        default=20,
        help="Maximum number of conversation turns (default: 20)",
    )
    
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.9,
        help="Persuasion threshold for scammer success (default: 0.9)",
    )
    
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show final report, not turn-by-turn output",
    )
    
    parser.add_argument(
        "--voice",
        action="store_true",
        help="Enable voice mode - generate TTS audio for each turn (requires SMALLEST_API_KEY)",
    )
    
    parser.add_argument(
        "--audio-dir",
        type=str,
        default="audio_output",
        help="Directory to save audio files (default: audio_output)",
    )
    
    parser.add_argument(
        "--play",
        action="store_true",
        help="Play audio in real-time during simulation (implies --voice)",
    )
    
    parser.add_argument(
        "--family",
        action="store_true",
        help="Run with a family caller instead of scammer (test false positive rate)",
    )
    
    return parser.parse_args()


def main() -> int:
    """Main entry point."""
    # Load environment variables from .env file
    load_dotenv()
    
    args = parse_args()
    
    caller_type = CallerType.FAMILY if args.family else CallerType.SCAMMER
    
    print("\n" + "="*60)
    if args.family:
        print("💚 FAMILY CALL vs 🔵 BLUE CALL")
        print("False Positive Testing Mode")
    else:
        print("🔴 RED CALL vs 🔵 BLUE CALL")
        print("Multi-Agent Scam Simulation")
    print("="*60)
    print(f"\nConfiguration:")
    print(f"  Caller Type: {caller_type.value}")
    print(f"  Max Turns: {args.turns}")
    if not args.family:
        print(f"  Persuasion Threshold: {args.threshold}")
    print(f"  Verbose: {not args.quiet}")
    print(f"  Voice Mode: {args.voice or args.play}")
    print(f"  Play Audio: {args.play}")
    if args.voice or args.play:
        print(f"  Audio Output: {args.audio_dir}")
    print("\nStarting simulation...")
    
    try:
        # Run the simulation
        result = run_simulation(
            caller_type=caller_type,
            max_turns=args.turns,
            persuasion_threshold=args.threshold,
            verbose=not args.quiet,
            voice_mode=args.voice,
            play_audio=args.play,
            audio_output_dir=args.audio_dir,
        )
        
        # Print evaluation report
        print_report(result)
        
        # Return exit code based on defender success
        if args.family:
            return 0 if result.handoff_succeeded else 1
        else:
            return 0 if not result.sensitive_info_leaked else 1
        
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nMake sure you have set either OPENAI_API_KEY or DEEPSEEK_API_KEY.")
        print("You can create a .env file with:")
        print("  OPENAI_API_KEY=your_key_here")
        print("  or")
        print("  DEEPSEEK_API_KEY=your_key_here")
        return 1
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Simulation interrupted by user.")
        return 130
        
    except Exception as e:
        print(f"\n❌ Error during simulation: {e}")
        raise


if __name__ == "__main__":
    sys.exit(main())
