#!/usr/bin/env python3
"""
FastAPI Backend Server for RedCall vs BlueCall Web Demo
Real-time WebSocket streaming of simulation state
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from simulation_runner import SimulationRunner

load_dotenv()

app = FastAPI(title="RedCall vs BlueCall Demo API")

# CORS for React dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global simulation state
active_simulation: Optional[SimulationRunner] = None
active_websocket: Optional[WebSocket] = None


class SimulationConfig(BaseModel):
    max_turns: int = 15
    enable_voice: bool = True
    caller_type: str = "scammer"  # "scammer" or "family"


class SimulationStatus(BaseModel):
    running: bool
    turn: int
    completed: bool
    end_reason: Optional[str] = None


@app.get("/api/status")
async def get_status() -> SimulationStatus:
    """Get current simulation status."""
    if active_simulation:
        return SimulationStatus(
            running=active_simulation.running,
            turn=active_simulation.current_turn,
            completed=active_simulation.completed,
            end_reason=active_simulation.end_reason,
        )
    return SimulationStatus(running=False, turn=0, completed=False)


@app.post("/api/stop")
async def stop_simulation():
    """Stop the current simulation."""
    global active_simulation
    if active_simulation:
        active_simulation.stop()
        return {"status": "stopped"}
    return {"status": "no_simulation_running"}


@app.websocket("/ws/simulation")
async def websocket_simulation(websocket: WebSocket):
    """WebSocket endpoint for real-time simulation streaming."""
    global active_simulation, active_websocket
    
    await websocket.accept()
    active_websocket = websocket
    
    try:
        while True:
            # Receive control messages from client
            data = await websocket.receive_json()
            
            if data.get("action") == "start":
                config = SimulationConfig(**data.get("config", {}))
                
                # Stop any existing simulation
                if active_simulation and active_simulation.running:
                    active_simulation.stop()
                
                # Create new simulation runner
                active_simulation = SimulationRunner(
                    max_turns=config.max_turns,
                    enable_voice=config.enable_voice,
                    caller_type=config.caller_type,
                )
                
                # Run simulation with websocket streaming
                await active_simulation.run_streaming(websocket)
                
            elif data.get("action") == "stop":
                if active_simulation:
                    active_simulation.stop()
                    await websocket.send_json({
                        "type": "simulation_stopped",
                        "data": {}
                    })
                    
    except WebSocketDisconnect:
        print("WebSocket disconnected")
        if active_simulation:
            active_simulation.stop()
    except Exception as e:
        print(f"WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "data": {"message": str(e)}
            })
        except:
            pass


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
