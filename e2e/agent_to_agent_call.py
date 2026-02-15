#!/usr/bin/env python3
"""
Agent-to-Agent Voice Call via Smallest.ai WebSocket API

This script connects two existing Smallest.ai agents together via WebSocket,
allowing them to have a voice conversation while you can listen to the audio.

Requirements:
    pip install websockets

Environment Variables:
    SMALLEST_API_KEY - Your Smallest.ai API key
    
Usage:
    python agent_to_agent_call.py --agent1 <agent_id_1> --agent2 <agent_id_2>
    
    # Save audio to file (for WSL/headless):
    python agent_to_agent_call.py --agent1 <id1> --agent2 <id2> --save-audio
"""

import asyncio
import base64
import json
import os
import argparse
import struct
import subprocess
import threading
import wave
import io
from typing import Optional
from queue import Queue
import sys
from datetime import datetime

try:
    import websockets
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)


# Audio configuration
SAMPLE_RATE = 24000  # Common for voice AI APIs
CHANNELS = 1
SAMPLE_WIDTH = 2  # 16-bit audio
CHUNK_SIZE = 1024

# Smallest.ai WebSocket endpoint (adjust if different)
SMALLEST_WS_BASE_URL = os.getenv("SMALLEST_WS_URL", "wss://atoms-api.smallest.ai/v1/realtime")


def is_wsl() -> bool:
    """Check if running in WSL"""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except:
        return False


class AudioPlayer:
    """
    Handles audio playback with multiple backends:
    - WSL: Streams to PowerShell via named pipe or saves to file
    - Linux: Uses aplay/paplay
    - Fallback: Saves to WAV file
    """
    
    def __init__(self, sample_rate: int = SAMPLE_RATE, save_to_file: bool = False):
        self.sample_rate = sample_rate
        self.save_to_file = save_to_file
        self.audio_queue: Queue = Queue()
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.audio_buffer: list[bytes] = []
        self.output_file: Optional[str] = None
        self.player_process: Optional[subprocess.Popen] = None
        self.lock = threading.Lock()
        self._is_wsl = is_wsl()
    
    def start(self):
        """Start the audio playback/recording"""
        self.running = True
        self.audio_buffer = []
        
        if self.save_to_file:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_file = f"conversation_{timestamp}.wav"
            print(f"🎙️  Recording audio to: {self.output_file}")
        else:
            # Try to start streaming playback
            if self._is_wsl:
                print("🔊 WSL detected - streaming audio via PowerShell")
                self._start_wsl_player()
            else:
                print("🔊 Starting audio playback")
                self._start_linux_player()
        
        self.thread = threading.Thread(target=self._playback_loop, daemon=True)
        self.thread.start()
    
    def _start_wsl_player(self):
        """Start PowerShell-based audio player for WSL"""
        try:
            # Use ffplay from Windows if available (install ffmpeg on Windows)
            # This streams raw PCM audio
            self.player_process = subprocess.Popen(
                [
                    "powershell.exe", "-Command",
                    f"ffplay -f s16le -ar {self.sample_rate} -ac {CHANNELS} -nodisp -autoexit -i pipe:0"
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print("   Using ffplay for audio (install ffmpeg on Windows if not working)")
        except Exception as e:
            print(f"⚠️  Could not start ffplay: {e}")
            print("   Falling back to saving audio file")
            self.save_to_file = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_file = f"conversation_{timestamp}.wav"
    
    def _start_linux_player(self):
        """Start Linux audio player"""
        try:
            # Try aplay for raw PCM streaming
            self.player_process = subprocess.Popen(
                ["aplay", "-f", "S16_LE", "-r", str(self.sample_rate), "-c", str(CHANNELS), "-q"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except FileNotFoundError:
            print("⚠️  aplay not found, saving to file instead")
            self.save_to_file = True
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.output_file = f"conversation_{timestamp}.wav"
    
    def _playback_loop(self):
        """Process audio from the queue"""
        while self.running:
            try:
                audio_data = self.audio_queue.get(timeout=0.1)
                if audio_data:
                    with self.lock:
                        self.audio_buffer.append(audio_data)
                    
                    # Stream to player if available
                    if self.player_process and self.player_process.stdin:
                        try:
                            self.player_process.stdin.write(audio_data)
                            self.player_process.stdin.flush()
                        except (BrokenPipeError, OSError):
                            pass
            except:
                continue
    
    def play(self, audio_bytes: bytes):
        """Add audio bytes to the playback queue"""
        self.audio_queue.put(audio_bytes)
    
    def stop(self):
        """Stop playback and save audio if needed"""
        self.running = False
        
        if self.thread:
            self.thread.join(timeout=1.0)
        
        # Close player process
        if self.player_process:
            try:
                if self.player_process.stdin:
                    self.player_process.stdin.close()
                self.player_process.wait(timeout=2.0)
            except:
                self.player_process.kill()
        
        # Save to file
        if self.audio_buffer:
            if self.save_to_file and self.output_file:
                self._save_wav()
            elif not self.player_process:
                # Fallback: save if no player was running
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.output_file = f"conversation_{timestamp}.wav"
                self._save_wav()
        
        print("🔇 Audio stopped")
    
    def _save_wav(self):
        """Save buffered audio to WAV file"""
        if not self.output_file or not self.audio_buffer:
            return
        
        with self.lock:
            with wave.open(self.output_file, 'wb') as wav_file:
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(SAMPLE_WIDTH)
                wav_file.setframerate(self.sample_rate)
                wav_file.writeframes(b''.join(self.audio_buffer))
        
        print(f"💾 Audio saved to: {self.output_file}")
        if self._is_wsl:
            # Convert to Windows path
            win_path = self.output_file
            print(f"   Play in Windows: explorer.exe {win_path}")


class AgentConnection:
    """Manages WebSocket connection to a Smallest.ai agent"""
    
    def __init__(self, agent_id: str, name: str, api_key: str):
        self.agent_id = agent_id
        self.name = name
        self.api_key = api_key
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.connected = False
        self.partner: Optional['AgentConnection'] = None
        self.audio_player: Optional[AudioPlayer] = None
    
    async def connect(self):
        """Establish WebSocket connection to the agent"""
        # Build WebSocket URL with agent ID
        ws_url = f"{SMALLEST_WS_BASE_URL}?agent_id={self.agent_id}"
        
        headers = [
            ("Authorization", f"Bearer {self.api_key}"),
            ("Content-Type", "application/json")
        ]
        
        try:
            print(f"🔗 Connecting to {self.name} ({self.agent_id})...")
            self.ws = await websockets.connect(
                ws_url,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=10
            )
            self.connected = True
            print(f"✅ {self.name} connected successfully")
            
            # Send session initialization
            await self._initialize_session()
            
        except Exception as e:
            print(f"❌ Failed to connect {self.name}: {e}")
            raise
    
    async def _initialize_session(self):
        """Initialize the session with the agent"""
        init_message = {
            "type": "session.update",
            "session": {
                "type": "realtime",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "sample_rate": SAMPLE_RATE
            }
        }
        await self.send(init_message)
    
    async def send(self, message: dict):
        """Send a JSON message to the agent"""
        if self.ws and self.connected:
            await self.ws.send(json.dumps(message))
    
    async def send_audio(self, audio_base64: str):
        """Send audio data to the agent"""
        message = {
            "type": "input_audio_buffer.append",
            "audio": audio_base64
        }
        await self.send(message)
    
    async def commit_audio(self):
        """Signal end of audio input"""
        await self.send({"type": "input_audio_buffer.commit"})
    
    async def trigger_response(self):
        """Trigger the agent to generate a response"""
        await self.send({"type": "response.create"})
    
    async def listen(self):
        """Listen for messages from the agent and handle them"""
        if not self.ws:
            return
        
        try:
            async for message in self.ws:
                await self._handle_message(message)
        except websockets.exceptions.ConnectionClosed:
            print(f"🔌 {self.name} connection closed")
            self.connected = False
    
    async def _handle_message(self, raw_message: str):
        """Process incoming messages from the agent"""
        try:
            message = json.loads(raw_message)
            msg_type = message.get("type", "")
            
            # Handle different message types
            if msg_type == "session.created":
                print(f"📝 {self.name} session created")
            
            elif msg_type == "session.updated":
                print(f"🔄 {self.name} session updated")
            
            elif msg_type == "response.audio.delta":
                # Agent is speaking - forward audio to partner and play locally
                audio_data = message.get("delta", "")
                if audio_data:
                    # Decode and play locally
                    audio_bytes = base64.b64decode(audio_data)
                    if self.audio_player:
                        self.audio_player.play(audio_bytes)
                    
                    # Forward to partner agent
                    if self.partner and self.partner.connected:
                        await self.partner.send_audio(audio_data)
            
            elif msg_type == "response.audio.done":
                # Agent finished speaking - trigger partner to respond
                print(f"🎤 {self.name} finished speaking")
                if self.partner and self.partner.connected:
                    await self.partner.commit_audio()
                    await self.partner.trigger_response()
            
            elif msg_type == "response.text.delta":
                # Text transcript of what agent is saying
                text = message.get("delta", "")
                if text:
                    print(f"💬 {self.name}: {text}", end="", flush=True)
            
            elif msg_type == "response.text.done":
                print()  # Newline after text
            
            elif msg_type == "error":
                error = message.get("error", {})
                print(f"❌ {self.name} error: {error.get('message', 'Unknown error')}")
            
            elif msg_type in ["response.created", "response.done", "rate_limits.updated"]:
                pass  # Ignore routine messages
            
            else:
                # Log unknown message types for debugging
                if os.getenv("DEBUG"):
                    print(f"🔍 {self.name} received: {msg_type}")
        
        except json.JSONDecodeError:
            print(f"⚠️ {self.name}: Invalid JSON message")
    
    async def disconnect(self):
        """Close the WebSocket connection"""
        if self.ws:
            self.connected = False
            await self.ws.close()
            print(f"🔌 {self.name} disconnected")


class AgentToAgentCall:
    """Orchestrates a call between two agents"""
    
    def __init__(self, agent1_id: str, agent2_id: str, api_key: str, save_audio: bool = False):
        self.agent1 = AgentConnection(agent1_id, "Agent 1 (Red)", api_key)
        self.agent2 = AgentConnection(agent2_id, "Agent 2 (Blue)", api_key)
        self.audio_player = AudioPlayer(save_to_file=save_audio)
        
        # Link agents as partners
        self.agent1.partner = self.agent2
        self.agent2.partner = self.agent1
        
        # Share audio player
        self.agent1.audio_player = self.audio_player
        self.agent2.audio_player = self.audio_player
    
    async def start(self, initial_message: str = "Hello! Let's have a conversation."):
        """Start the agent-to-agent call"""
        print("\n" + "="*60)
        print("🎯 Starting Agent-to-Agent Voice Call")
        print("="*60 + "\n")
        
        # Start audio player
        self.audio_player.start()
        
        try:
            # Connect both agents
            await asyncio.gather(
                self.agent1.connect(),
                self.agent2.connect()
            )
            
            # Give sessions time to initialize
            await asyncio.sleep(1)
            
            # Start both listeners
            listen_tasks = [
                asyncio.create_task(self.agent1.listen()),
                asyncio.create_task(self.agent2.listen())
            ]
            
            # Kick off the conversation by sending initial message to Agent 1
            print(f"\n💬 Initiating conversation: \"{initial_message}\"\n")
            
            # Send initial text prompt to Agent 1
            await self.agent1.send({
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "user",
                    "content": [{
                        "type": "input_text",
                        "text": initial_message
                    }]
                }
            })
            await self.agent1.trigger_response()
            
            # Wait for the conversation
            print("Press Ctrl+C to end the call...\n")
            await asyncio.gather(*listen_tasks)
            
        except asyncio.CancelledError:
            print("\n⏹️ Call ended by user")
        except Exception as e:
            print(f"\n❌ Error during call: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the call and clean up"""
        print("\n🛑 Stopping call...")
        self.audio_player.stop()
        await asyncio.gather(
            self.agent1.disconnect(),
            self.agent2.disconnect()
        )
        print("✅ Call ended\n")


async def main():
    parser = argparse.ArgumentParser(
        description="Connect two Smallest.ai agents for a voice conversation"
    )
    parser.add_argument(
        "--agent1", "-a1",
        required=True,
        help="Agent ID for the first agent (e.g., Red Call agent)"
    )
    parser.add_argument(
        "--agent2", "-a2",
        required=True,
        help="Agent ID for the second agent (e.g., Blue Call agent)"
    )
    parser.add_argument(
        "--message", "-m",
        default="Hello! I'm calling to have a conversation with you. How are you today?",
        help="Initial message to start the conversation"
    )
    parser.add_argument(
        "--api-key", "-k",
        default=os.getenv("SMALLEST_API_KEY"),
        help="Smallest.ai API key (or set SMALLEST_API_KEY env var)"
    )
    parser.add_argument(
        "--save-audio", "-s",
        action="store_true",
        help="Save audio to WAV file instead of playing live (useful for WSL/headless)"
    )
    
    args = parser.parse_args()
    
    if not args.api_key:
        print("❌ Error: SMALLEST_API_KEY environment variable not set")
        print("   Set it with: export SMALLEST_API_KEY='your-api-key'")
        sys.exit(1)
    
    call = AgentToAgentCall(args.agent1, args.agent2, args.api_key, save_audio=args.save_audio)
    
    try:
        await call.start(args.message)
    except KeyboardInterrupt:
        await call.stop()


if __name__ == "__main__":
    asyncio.run(main())
