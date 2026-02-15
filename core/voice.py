"""Voice module for TTS/STT using Smallest.ai Waves API."""

import os
from functools import lru_cache
from typing import Optional

from smallestai.waves import WavesClient


@lru_cache(maxsize=1)
def get_waves_client(voice_id: str = "albus") -> Optional[WavesClient]:
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
    voice_id: str = "albus",
    sample_rate: int = 24000,
) -> Optional[bytes]:
    """
    Convert text to speech audio.
    
    Args:
        text: The text to synthesize.
        voice_id: Voice to use (default: "albus").
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
SCAMMER_VOICE = "ashley"  # Female voice for scammer
SENIOR_VOICE = "albus"    # Male voice for senior


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
