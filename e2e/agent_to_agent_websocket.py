#!/usr/bin/env python3
"""
Agent-to-Agent WebSocket Bridge for Smallest.ai SDK Agents

This script connects to two deployed Smallest.ai SDK agents via their WebSocket URLs
and bridges their conversation, allowing them to talk to each other while you listen.

Requirements:
    pip install websockets

Usage:
    python agent_to_agent_websocket.py --ws1 <websocket_url_1> --ws2 <websocket_url_2>
    
    # Or with agent IDs (fetches websocket URLs from live builds):
    python agent_to_agent_websocket.py --agent1 <agent_id_1> --agent2 <agent_id_2>
"""

import asyncio
import json
import os
import argparse
import wave
import threading
import subprocess
from typing import Optional, AsyncIterator
from queue import Queue
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import sys

try:
    from websockets.asyncio.client import connect as websocket_connect
except ImportError:
    print("Please install websockets: pip install websockets")
    sys.exit(1)


# Audio configuration
SAMPLE_RATE = 24000
CHANNELS = 1
SAMPLE_WIDTH = 2


class EventType(str, Enum):
    """SDK Event types"""
    SYSTEM_INIT = "system.init"
    SYSTEM_LLM_REQUEST = "system.llm.request"
    SYSTEM_USER_JOINED = "system.user.joined"
    AGENT_READY = "agent.ready"
    AGENT_ERROR = "agent.error"
    AGENT_LLM_RESPONSE_START = "agent.llm.response.start"
    AGENT_LLM_RESPONSE_CHUNK = "agent.llm.response.chunk"
    AGENT_LLM_RESPONSE_END = "agent.llm.response.end"
    AGENT_TRANSCRIPT_UPDATE = "agent.transcript.update"
    AGENT_SPEAK = "agent.speak"
    AGENT_END_CALL = "agent.end_call"


@dataclass
class SDKEvent:
    """Simple SDK event structure"""
    type: str
    data: dict
    
    def to_json(self) -> str:
        return json.dumps({"type": self.type, **self.data})
    
    @classmethod
    def from_json(cls, data: str) -> "SDKEvent":
        parsed = json.loads(data)
        event_type = parsed.pop("type", "unknown")
        return cls(type=event_type, data=parsed)


def is_wsl() -> bool:
    """Check if running in WSL"""
    try:
        with open('/proc/version', 'r') as f:
            return 'microsoft' in f.read().lower()
    except:
        return False


class AudioRecorder:
    """Records conversation audio to WAV file"""
    
    def __init__(self, output_dir: str = "."):
        self.output_dir = output_dir
        self.audio_buffer: list[bytes] = []
        self.output_file: Optional[str] = None
        self.lock = threading.Lock()
    
    def start(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.output_file = os.path.join(self.output_dir, f"conversation_{timestamp}.wav")
        self.audio_buffer = []
        print(f"🎙️  Recording audio to: {self.output_file}")
    
    def add_audio(self, audio_bytes: bytes):
        with self.lock:
            self.audio_buffer.append(audio_bytes)
    
    def save(self):
        if not self.output_file or not self.audio_buffer:
            return
        
        with self.lock:
            with wave.open(self.output_file, 'wb') as wav_file:
                wav_file.setnchannels(CHANNELS)
                wav_file.setsampwidth(SAMPLE_WIDTH)
                wav_file.setframerate(SAMPLE_RATE)
                wav_file.writeframes(b''.join(self.audio_buffer))
        
        print(f"💾 Audio saved to: {self.output_file}")
        if is_wsl():
            print(f"   Play in Windows: explorer.exe {self.output_file}")


class AgentWebSocketClient:
    """WebSocket client for a Smallest.ai SDK agent"""
    
    def __init__(self, ws_url: str, name: str):
        self.ws_url = ws_url
        self.name = name
        self.ws = None
        self.connected = False
        self.partner: Optional["AgentWebSocketClient"] = None
        self.audio_recorder: Optional[AudioRecorder] = None
        self._response_queue: asyncio.Queue = asyncio.Queue()
    
    async def connect(self):
        """Connect to the agent's WebSocket"""
        try:
            print(f"🔗 Connecting to {self.name}...")
            self.ws = await websocket_connect(self.ws_url)
            
            # Send init event
            init_event = SDKEvent(
                type=EventType.SYSTEM_INIT.value,
                data={
                    "version": "1.0.0",
                    "session_context": {
                        "initial_variables": {},
                        "conversation_type": "webcall"
                    }
                }
            )
            await self.ws.send(init_event.to_json())
            
            # Wait for ready event
            response = await asyncio.wait_for(self.ws.recv(), timeout=10.0)
            event = SDKEvent.from_json(response)
            
            if event.type == EventType.AGENT_READY.value:
                self.connected = True
                print(f"✅ {self.name} connected and ready")
            elif event.type == EventType.AGENT_ERROR.value:
                print(f"❌ {self.name} error: {event.data.get('message', 'Unknown')}")
                return False
            else:
                print(f"⚠️  {self.name} unexpected response: {event.type}")
            
            return self.connected
            
        except asyncio.TimeoutError:
            print(f"❌ {self.name} connection timeout")
            return False
        except Exception as e:
            print(f"❌ {self.name} connection failed: {e}")
            return False
    
    async def send_event(self, event: SDKEvent):
        """Send an event to the agent"""
        if self.ws and self.connected:
            await self.ws.send(event.to_json())
    
    async def send_user_message(self, text: str):
        """Send a user message to the agent"""
        # Update transcript with user message
        await self.send_event(SDKEvent(
            type=EventType.AGENT_TRANSCRIPT_UPDATE.value,
            data={"role": "user", "content": text}
        ))
        # Request LLM response
        await self.send_event(SDKEvent(
            type=EventType.SYSTEM_LLM_REQUEST.value,
            data={}
        ))
    
    async def listen(self) -> AsyncIterator[SDKEvent]:
        """Listen for events from the agent"""
        if not self.ws:
            return
        
        try:
            async for message in self.ws:
                event = SDKEvent.from_json(message)
                yield event
        except Exception as e:
            print(f"🔌 {self.name} disconnected: {e}")
            self.connected = False
    
    async def disconnect(self):
        """Close the WebSocket connection"""
        if self.ws:
            self.connected = False
            await self.ws.close()
            print(f"🔌 {self.name} disconnected")


class AgentToAgentBridge:
    """Bridges two agents together for a conversation"""
    
    def __init__(self, ws_url1: str, ws_url2: str):
        self.agent1 = AgentWebSocketClient(ws_url1, "Agent 1 (Red)")
        self.agent2 = AgentWebSocketClient(ws_url2, "Agent 2 (Blue)")
        self.audio_recorder = AudioRecorder()
        
        # Link agents
        self.agent1.partner = self.agent2
        self.agent2.partner = self.agent1
        self.agent1.audio_recorder = self.audio_recorder
        self.agent2.audio_recorder = self.audio_recorder
        
        self._running = False
        self._current_speaker: Optional[AgentWebSocketClient] = None
        self._response_buffer = ""
    
    async def _handle_agent_events(self, agent: AgentWebSocketClient):
        """Handle events from one agent"""
        async for event in agent.listen():
            if not self._running:
                break
            
            if event.type == EventType.AGENT_LLM_RESPONSE_START.value:
                self._current_speaker = agent
                self._response_buffer = ""
                print(f"\n💬 {agent.name}: ", end="", flush=True)
            
            elif event.type == EventType.AGENT_LLM_RESPONSE_CHUNK.value:
                chunk = event.data.get("text", "")
                self._response_buffer += chunk
                print(chunk, end="", flush=True)
            
            elif event.type == EventType.AGENT_LLM_RESPONSE_END.value:
                print()  # Newline
                # Forward the response to the partner agent
                if agent.partner and agent.partner.connected and self._response_buffer:
                    print(f"   → Forwarding to {agent.partner.name}")
                    await agent.partner.send_user_message(self._response_buffer)
                self._current_speaker = None
                self._response_buffer = ""
            
            elif event.type == EventType.AGENT_SPEAK.value:
                # Direct speak event
                text = event.data.get("text", "")
                if text:
                    print(f"\n🗣️  {agent.name}: {text}")
                    if agent.partner and agent.partner.connected:
                        await agent.partner.send_user_message(text)
            
            elif event.type == EventType.AGENT_TRANSCRIPT_UPDATE.value:
                role = event.data.get("role", "")
                content = event.data.get("content", "")
                if role == "assistant" and content:
                    # Log assistant responses
                    pass
            
            elif event.type == EventType.AGENT_ERROR.value:
                print(f"\n❌ {agent.name} error: {event.data.get('message', 'Unknown')}")
            
            elif event.type == EventType.AGENT_END_CALL.value:
                print(f"\n📞 {agent.name} ended the call")
                self._running = False
                break
    
    async def start(self, initial_message: str):
        """Start the agent-to-agent conversation"""
        print("\n" + "=" * 60)
        print("🎯 Starting Agent-to-Agent Conversation")
        print("=" * 60 + "\n")
        
        self.audio_recorder.start()
        self._running = True
        
        try:
            # Connect both agents
            results = await asyncio.gather(
                self.agent1.connect(),
                self.agent2.connect(),
                return_exceptions=True
            )
            
            if not all(r is True for r in results):
                print("❌ Failed to connect both agents")
                return
            
            # Notify agents that user joined
            await self.agent1.send_event(SDKEvent(
                type=EventType.SYSTEM_USER_JOINED.value,
                data={}
            ))
            await self.agent2.send_event(SDKEvent(
                type=EventType.SYSTEM_USER_JOINED.value,
                data={}
            ))
            
            await asyncio.sleep(0.5)
            
            # Start listening to both agents
            listen_tasks = [
                asyncio.create_task(self._handle_agent_events(self.agent1)),
                asyncio.create_task(self._handle_agent_events(self.agent2))
            ]
            
            # Kick off the conversation
            print(f"\n💬 Starting conversation: \"{initial_message}\"\n")
            await self.agent1.send_user_message(initial_message)
            
            print("Press Ctrl+C to end the conversation...\n")
            
            # Wait for tasks
            await asyncio.gather(*listen_tasks, return_exceptions=True)
            
        except asyncio.CancelledError:
            print("\n⏹️  Conversation ended by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the conversation"""
        print("\n🛑 Stopping conversation...")
        self._running = False
        self.audio_recorder.save()
        await asyncio.gather(
            self.agent1.disconnect(),
            self.agent2.disconnect(),
            return_exceptions=True
        )
        print("✅ Conversation ended\n")


async def get_agent_websocket_url(agent_id: str, api_key: str) -> Optional[str]:
    """Get the WebSocket URL for a deployed agent"""
    try:
        import httpx
        
        async with httpx.AsyncClient() as client:
            # Get the live build for the agent
            response = await client.get(
                f"https://atoms-api.smallest.ai/api/v1/sdk/agents/{agent_id}/builds",
                headers={"Authorization": f"Bearer {api_key}"},
                params={"limit": 50, "offset": 0}
            )
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") and data.get("data", {}).get("builds"):
                # Find the live build
                for build in data["data"]["builds"]:
                    if build.get("isLive") and build.get("websocketUrl"):
                        return build["websocketUrl"]
                
                # No live build, check for any successful build
                for build in data["data"]["builds"]:
                    if build.get("status") == "SUCCEEDED" and build.get("websocketUrl"):
                        print(f"⚠️  No live build for {agent_id}, using latest successful build")
                        return build["websocketUrl"]
            
            print(f"❌ No deployed build found for agent {agent_id}")
            return None
            
    except Exception as e:
        print(f"❌ Failed to get WebSocket URL for {agent_id}: {e}")
        return None


async def main():
    parser = argparse.ArgumentParser(
        description="Connect two Smallest.ai SDK agents for a conversation"
    )
    
    # WebSocket URLs (direct)
    parser.add_argument(
        "--ws1",
        help="WebSocket URL for the first agent"
    )
    parser.add_argument(
        "--ws2", 
        help="WebSocket URL for the second agent"
    )
    
    # Or agent IDs (will fetch WebSocket URLs)
    parser.add_argument(
        "--agent1", "-a1",
        help="Agent ID for the first agent (will fetch WebSocket URL from live build)"
    )
    parser.add_argument(
        "--agent2", "-a2",
        help="Agent ID for the second agent (will fetch WebSocket URL from live build)"
    )
    
    parser.add_argument(
        "--message", "-m",
        default="Hello! I'm calling to have a conversation with you. How are you today?",
        help="Initial message to start the conversation"
    )
    parser.add_argument(
        "--api-key", "-k",
        default=os.getenv("SMALLEST_API_KEY"),
        help="Smallest.ai API key (required if using --agent1/--agent2)"
    )
    
    args = parser.parse_args()
    
    ws_url1 = args.ws1
    ws_url2 = args.ws2
    
    # If agent IDs provided, fetch WebSocket URLs
    if args.agent1 and args.agent2:
        if not args.api_key:
            print("❌ API key required when using agent IDs")
            print("   Set SMALLEST_API_KEY or use --api-key")
            sys.exit(1)
        
        print("🔍 Fetching WebSocket URLs from deployed builds...")
        ws_url1, ws_url2 = await asyncio.gather(
            get_agent_websocket_url(args.agent1, args.api_key),
            get_agent_websocket_url(args.agent2, args.api_key)
        )
    
    if not ws_url1 or not ws_url2:
        print("❌ Both WebSocket URLs are required")
        print("   Use --ws1 and --ws2, or --agent1 and --agent2")
        sys.exit(1)
    
    print(f"📡 Agent 1 WebSocket: {ws_url1}")
    print(f"📡 Agent 2 WebSocket: {ws_url2}")
    
    bridge = AgentToAgentBridge(ws_url1, ws_url2)
    
    try:
        await bridge.start(args.message)
    except KeyboardInterrupt:
        await bridge.stop()


if __name__ == "__main__":
    asyncio.run(main())
