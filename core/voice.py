"""Voice module for TTS/STT using Smallest.ai Waves API."""

import os
import io
import wave
import tempfile
from functools import lru_cache
from typing import Optional, Tuple

import requests
from smallestai.waves import WavesClient


# Pulse STT API endpoint
PULSE_STT_URL = "https://waves-api.smallest.ai/api/v1/pulse/get_text"


@lru_cache(maxsize=1)
def get_waves_client(voice_id: str = "emily") -> Optional[WavesClient]:
    """
    Get a configured Waves client for TTS/STT.
    
    Returns:
        WavesClient if SMALLEST_API_KEY is set, None otherwise.
    """
    api_key = os.getenv("SMALLEST_API_KEY")
    if not api_key:
        return None
    
    return WavesClient(
        api_key=api_key,
        model="lightning-v2",
        sample_rate=24000,
        voice_id=voice_id,
    )


# Max characters per API call (Smallest.ai limit is ~250 chars)
MAX_TEXT_LENGTH = 250


def _chunk_text(text: str, max_length: int = MAX_TEXT_LENGTH) -> list[str]:
    """
    Split text into chunks at sentence boundaries.
    
    Args:
        text: Text to split.
        max_length: Maximum characters per chunk.
        
    Returns:
        List of text chunks.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Split by sentences (period, exclamation, question mark)
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        # If single sentence is too long, split by commas or spaces
        if len(sentence) > max_length:
            words = sentence.split()
            for word in words:
                if len(current_chunk) + len(word) + 1 <= max_length:
                    current_chunk += (" " if current_chunk else "") + word
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = word
        elif len(current_chunk) + len(sentence) + 1 <= max_length:
            current_chunk += (" " if current_chunk else "") + sentence
        else:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = sentence
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def _combine_wav_chunks(chunks: list[bytes]) -> bytes:
    """
    Combine multiple WAV audio chunks into one.
    
    Args:
        chunks: List of WAV audio bytes.
        
    Returns:
        Combined WAV audio bytes.
    """
    if len(chunks) == 1:
        return chunks[0]
    
    import wave
    import io
    
    # Read first chunk to get parameters
    first_wav = wave.open(io.BytesIO(chunks[0]), 'rb')
    params = first_wav.getparams()
    
    # Collect all audio data
    all_frames = []
    for chunk in chunks:
        wav = wave.open(io.BytesIO(chunk), 'rb')
        all_frames.append(wav.readframes(wav.getnframes()))
        wav.close()
    
    first_wav.close()
    
    # Write combined audio
    output = io.BytesIO()
    output_wav = wave.open(output, 'wb')
    output_wav.setparams(params)
    for frames in all_frames:
        output_wav.writeframes(frames)
    output_wav.close()
    
    return output.getvalue()


def text_to_speech(
    text: str,
    voice_id: str = "emily",
    sample_rate: int = 24000,
) -> Optional[bytes]:
    """
    Convert text to speech audio.
    
    Args:
        text: The text to synthesize.
        voice_id: Voice to use (default: "emily").
        sample_rate: Audio sample rate (default: 24000).
        
    Returns:
        Audio bytes (WAV format) or None if voice is not configured.
    """
    api_key = os.getenv("SMALLEST_API_KEY")
    if not api_key:
        return None
    
    # Create client with specific voice
    client = WavesClient(
        api_key=api_key,
        model="lightning-v2",
        sample_rate=sample_rate,
        voice_id=voice_id,
    )
    
    # Split long text into chunks
    chunks = _chunk_text(text)
    
    # Synthesize each chunk
    audio_chunks = []
    for chunk in chunks:
        audio = client.synthesize(chunk)
        if audio:
            audio_chunks.append(audio)
    
    if not audio_chunks:
        return None
    
    # Combine chunks
    return _combine_wav_chunks(audio_chunks)


def is_voice_enabled() -> bool:
    """Check if voice mode is available."""
    return os.getenv("SMALLEST_API_KEY") is not None


# Voice presets for the agents
SCAMMER_VOICE = "eleanor"  # Male voice for scammer
SENIOR_VOICE = "albus"  # Female voice for senior (old-age, narrative)


def play_audio(audio_bytes: bytes) -> bool:
    """
    Play audio bytes using available system player.
    
    Args:
        audio_bytes: WAV audio data.
        
    Returns:
        True if playback succeeded, False otherwise.
    """
    import subprocess
    import tempfile
    import platform
    
    # Write to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        temp_path = f.name
    
    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["afplay", temp_path], check=True)
        elif system == "Linux":
            # Try aplay (ALSA), then paplay (PulseAudio)
            try:
                subprocess.run(["aplay", temp_path], check=True)
            except FileNotFoundError:
                subprocess.run(["paplay", temp_path], check=True)
        elif system == "Windows":
            # Use PowerShell to play audio
            subprocess.run(
                ["powershell", "-c", f"(New-Object Media.SoundPlayer '{temp_path}').PlaySync()"],
                check=True
            )
        else:
            print(f"⚠️  Unsupported platform for audio playback: {system}")
            return False
        return True
    except Exception as e:
        print(f"⚠️  Audio playback failed: {e}")
        return False
    finally:
        os.unlink(temp_path)


def play_audio_file(filepath: str) -> bool:
    """
    Play a WAV file using system player.
    
    Args:
        filepath: Path to WAV file.
        
    Returns:
        True if playback succeeded, False otherwise.
    """
    import subprocess
    import platform
    
    try:
        system = platform.system()
        if system == "Darwin":  # macOS
            subprocess.run(["afplay", filepath], check=True)
        elif system == "Linux":
            try:
                subprocess.run(["aplay", filepath], check=True)
            except FileNotFoundError:
                subprocess.run(["paplay", filepath], check=True)
        elif system == "Windows":
            subprocess.run(
                ["powershell", "-c", f"(New-Object Media.SoundPlayer '{filepath}').PlaySync()"],
                check=True
            )
        else:
            return False
        return True
    except Exception as e:
        print(f"⚠️  Audio playback failed: {e}")
        return False


# ============================================================================
# Speech-to-Text (STT) using Smallest.ai Pulse
# ============================================================================

def speech_to_text(
    audio_bytes: bytes,
    language: str = "en",
) -> Optional[str]:
    """
    Convert speech audio to text using Smallest.ai Pulse STT.
    
    Args:
        audio_bytes: Audio data in WAV format.
        language: Language code (default: "en").
        
    Returns:
        Transcribed text or None if failed.
    """
    api_key = os.getenv("SMALLEST_API_KEY")
    if not api_key:
        return None
    
    try:
        response = requests.post(
            PULSE_STT_URL,
            params={
                "model": "pulse",
                "language": language,
            },
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "audio/wav",
            },
            data=audio_bytes,
            timeout=30,
        )
        response.raise_for_status()
        result = response.json()
        # API returns 'transcription' not 'text'
        return result.get("transcription", result.get("text", "")).strip()
    except Exception as e:
        print(f"⚠️  STT failed: {e}")
        return None


def record_audio_from_mic(
    duration_seconds: float = 5.0,
    sample_rate: int = 16000,
    channels: int = 1,
) -> Optional[bytes]:
    """
    Record audio from microphone.
    
    Args:
        duration_seconds: How long to record.
        sample_rate: Audio sample rate (16000 recommended for STT).
        channels: Number of audio channels (1 = mono).
        
    Returns:
        WAV audio bytes or None if recording failed.
    """
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        print("⚠️  sounddevice not installed. Run: uv add sounddevice numpy")
        return None
    
    try:
        print(f"🎤 Recording for {duration_seconds}s... (speak now)")
        recording = sd.rec(
            int(duration_seconds * sample_rate),
            samplerate=sample_rate,
            channels=channels,
            dtype='int16',
        )
        sd.wait()  # Wait for recording to complete
        print("✅ Recording complete.")
        
        # Convert to WAV bytes
        output = io.BytesIO()
        wf = wave.open(output, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(recording.tobytes())
        wf.close()
        
        return output.getvalue()
        
    except Exception as e:
        print(f"⚠️  Recording failed: {e}")
        return None


def record_until_silence(
    silence_threshold: float = 0.005,  # Lowered for better silence detection
    silence_duration: float = 1.5,
    max_duration: float = 30.0,
    sample_rate: int = 16000,
    channels: int = 1,
) -> Optional[bytes]:
    """
    Record audio until user stops speaking (silence detected).
    
    Args:
        silence_threshold: RMS threshold (0-1) below which is considered silence.
        silence_duration: Seconds of silence before stopping.
        max_duration: Maximum recording duration.
        sample_rate: Audio sample rate.
        channels: Number of channels.
        
    Returns:
        WAV audio bytes or None if failed.
    """
    try:
        import sounddevice as sd
        import numpy as np
    except ImportError:
        print("⚠️  sounddevice not installed. Run: uv add sounddevice numpy")
        return None
    
    CHUNK_DURATION = 0.1  # 100ms chunks
    chunk_samples = int(sample_rate * CHUNK_DURATION)
    
    def get_rms(data: np.ndarray) -> float:
        """Calculate RMS (volume level) of audio chunk."""
        return np.sqrt(np.mean(data.astype(np.float32) ** 2)) / 32768.0
    
    try:
        print("🎤 Listening... (speak, then pause to finish)")
        frames = []
        silent_chunks = 0
        chunks_for_silence = int(silence_duration / CHUNK_DURATION)
        max_chunks = int(max_duration / CHUNK_DURATION)
        has_speech = False
        
        with sd.InputStream(samplerate=sample_rate, channels=channels, dtype='int16') as stream:
            for _ in range(max_chunks):
                data, _ = stream.read(chunk_samples)
                frames.append(data.copy())
                rms = get_rms(data)
                
                if rms > silence_threshold:
                    has_speech = True
                    silent_chunks = 0
                else:
                    if has_speech:
                        silent_chunks += 1
                        if silent_chunks >= chunks_for_silence:
                            break
        
        print("✅ Recording complete.")
        
        if not has_speech:
            print("⚠️  No speech detected.")
            return None
        
        # Combine frames and convert to WAV bytes
        recording = np.concatenate(frames)
        output = io.BytesIO()
        wf = wave.open(output, 'wb')
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit = 2 bytes
        wf.setframerate(sample_rate)
        wf.writeframes(recording.tobytes())
        wf.close()
        
        return output.getvalue()
        
    except Exception as e:
        print(f"⚠️  Recording failed: {e}")
        return None


def listen_and_transcribe(
    use_silence_detection: bool = True,
    duration_seconds: float = 5.0,
) -> Optional[str]:
    """
    Record from microphone and transcribe to text.
    
    Args:
        use_silence_detection: If True, record until silence. Otherwise fixed duration.
        duration_seconds: Fixed duration if not using silence detection.
        
    Returns:
        Transcribed text or None if failed.
    """
    if use_silence_detection:
        audio = record_until_silence()
    else:
        audio = record_audio_from_mic(duration_seconds)
    
    if not audio:
        return None
    
    return speech_to_text(audio)
