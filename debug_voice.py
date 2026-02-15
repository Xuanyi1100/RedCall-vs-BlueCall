#!/usr/bin/env python3
"""Debug script to test voice components."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv()

import os

def test_microphone_devices():
    """List available audio devices."""
    print("\n=== 1. CHECKING AUDIO DEVICES ===")
    try:
        import sounddevice as sd
        print("Available audio devices:")
        print(sd.query_devices())
        print(f"\nDefault input device: {sd.default.device[0]}")
        print(f"Default output device: {sd.default.device[1]}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def test_recording_levels():
    """Test if microphone is picking up audio."""
    print("\n=== 2. TESTING MICROPHONE LEVELS ===")
    print("Speak into your microphone for 3 seconds...")
    
    try:
        import sounddevice as sd
        import numpy as np
        
        duration = 3
        sample_rate = 16000
        
        recording = sd.rec(
            int(duration * sample_rate),
            samplerate=sample_rate,
            channels=1,
            dtype='int16',
        )
        sd.wait()
        
        # Calculate levels
        max_val = np.max(np.abs(recording))
        rms = np.sqrt(np.mean(recording.astype(np.float32) ** 2))
        normalized_rms = rms / 32768.0
        
        print(f"\n📊 Audio Stats:")
        print(f"   Max amplitude: {max_val} (out of 32768)")
        print(f"   RMS level: {rms:.1f}")
        print(f"   Normalized RMS: {normalized_rms:.4f}")
        
        if max_val < 100:
            print("\n⚠️  Very low audio levels - microphone may not be working")
            print("   Try: Check system preferences > Sound > Input")
        elif max_val < 1000:
            print("\n⚠️  Low audio levels - speak louder or check mic input level")
        else:
            print("\n✅ Audio levels look good!")
        
        # Save test recording
        test_file = "debug_recording.wav"
        import wave
        import io
        
        with wave.open(test_file, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(recording.tobytes())
        
        print(f"\n💾 Saved test recording to: {test_file}")
        print(f"   Play it with: afplay {test_file}")
        
        return recording
        
    except Exception as e:
        print(f"❌ Recording error: {e}")
        return None


def test_stt(audio_bytes: bytes = None):
    """Test STT with recorded audio or a test file."""
    print("\n=== 3. TESTING STT (Pulse API) ===")
    
    api_key = os.getenv("SMALLEST_API_KEY")
    if not api_key:
        print("❌ SMALLEST_API_KEY not set in .env")
        return False
    
    print(f"✅ API key found: {api_key[:8]}...")
    
    # If no audio provided, read from debug file
    if audio_bytes is None:
        test_file = "debug_recording.wav"
        if not Path(test_file).exists():
            print(f"❌ No audio to test. Run test_recording_levels() first.")
            return False
        
        with open(test_file, "rb") as f:
            audio_bytes = f.read()
    
    print(f"📤 Sending {len(audio_bytes)} bytes to Pulse STT...")
    
    try:
        import requests
        
        response = requests.post(
            "https://waves-api.smallest.ai/api/v1/pulse/get_text",
            params={"model": "pulse", "language": "en"},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "audio/wav",
            },
            data=audio_bytes,
            timeout=30,
        )
        
        print(f"📥 Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ STT Result: {result}")
            text = result.get("transcription", result.get("text", ""))
            if text:
                print(f"\n🎯 Transcribed text: \"{text}\"")
            else:
                print("\n⚠️  Empty transcription - audio may be too quiet or unclear")
            return True
        else:
            print(f"❌ API Error: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ STT Error: {e}")
        return False


def test_silence_detection():
    """Test the silence detection threshold."""
    print("\n=== 4. TESTING SILENCE DETECTION ===")
    print("This will record until you stop speaking (1.5s of silence)...")
    print("Say something, then stop.\n")
    
    try:
        from core.voice import record_until_silence
        
        audio = record_until_silence(
            silence_threshold=0.005,  # Lowered for better detection
            silence_duration=1.5,
        )
        
        if audio:
            print(f"✅ Recorded {len(audio)} bytes")
            
            # Save it
            with open("debug_silence_detection.wav", "wb") as f:
                f.write(audio)
            print("💾 Saved to: debug_silence_detection.wav")
            
            # Try STT on it
            test_stt(audio)
        else:
            print("❌ No audio captured")
            print("\n💡 Try adjusting silence_threshold in voice.py")
            print("   Current: 0.01 (try 0.005 for quieter environments)")
            
    except Exception as e:
        print(f"❌ Error: {e}")


def main():
    print("🔧 Voice Debug Tool")
    print("=" * 50)
    
    # Test 1: Devices
    if not test_microphone_devices():
        return
    
    # Test 2: Recording levels
    recording = test_recording_levels()
    if recording is None:
        return
    
    # Test 3: STT
    test_stt()
    
    # Test 4: Silence detection
    print("\n" + "=" * 50)
    response = input("Test silence detection? (y/n): ")
    if response.lower() == 'y':
        test_silence_detection()
    
    print("\n✅ Debug complete!")


if __name__ == "__main__":
    main()
