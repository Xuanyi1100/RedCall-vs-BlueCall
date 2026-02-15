# RedCall vs BlueCall - Web Demo

A real-time interactive web demo showing AI agents in a scam call simulation.

## Features

- 🎭 **Two-Person Call View**: Split-screen showing Scammer (Red Team) and Senior Defender (Blue Team)
- 🧠 **Inner Thoughts Display**: See what each agent is "thinking" in real-time
- 📊 **Live Metrics**: 
  - Scammer: Persuasion Phase, Trust Level, Patience
  - Senior: Classification, Scam Confidence, Current Tactic
- 🔊 **Voice Playback**: Audio plays live as the conversation progresses
- 📜 **Conversation Transcript**: Full history of the call

## Architecture

- **Backend**: FastAPI with WebSocket for real-time streaming
- **Frontend**: React + Vite + TailwindCSS

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- npm

### Installation

1. **Install Python dependencies** (from project root):
   ```bash
   pip install fastapi uvicorn websockets
   # or with uv:
   uv pip install fastapi uvicorn websockets
   ```

2. **Install frontend dependencies**:
   ```bash
   cd webui/frontend
   npm install
   ```

### Running the Demo

**Option 1: Run both servers (recommended)**
```bash
cd webui
chmod +x run_demo.sh
./run_demo.sh
```

**Option 2: Run servers separately**

Terminal 1 - Backend:
```bash
cd webui/backend
uv run python server.py
```

Terminal 2 - Frontend:
```bash
cd webui/frontend
npm run dev
```

If `npm run dev` fails due to an old system Node, run with the project-local Node runtime:
```bash
cd webui
./setup_node.sh
export PATH="$(pwd)/../.tools/node/bin:$PATH"
cd frontend
npm run dev
```

Then open http://localhost:5173 in your browser.

## Usage

1. Open http://localhost:5173
2. Configure settings:
   - **Max Turns**: How long the simulation runs
   - **Voice**: Enable/disable TTS audio
   - **Thoughts**: Show/hide agent inner thoughts
3. Click **Start Call** to begin
4. Watch the live conversation unfold!
5. Click **Reset** to start a new simulation

## Project Structure

```
webui/
├── backend/
│   ├── server.py           # FastAPI server with WebSocket
│   └── simulation_runner.py # Async simulation streaming
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Main application
│   │   ├── components/     # React components
│   │   │   ├── AgentCard.tsx
│   │   │   ├── CallHeader.tsx
│   │   │   ├── Controls.tsx
│   │   │   ├── ConversationPanel.tsx
│   │   │   └── ProgressBar.tsx
│   │   ├── hooks/
│   │   │   └── useSimulation.ts # WebSocket & state management
│   │   └── types.ts        # TypeScript types
│   └── package.json
├── run_demo.sh             # Run both servers
├── run_backend.sh          # Run backend only
├── run_frontend.sh         # Run frontend only
└── README.md
```

## API

### WebSocket: `/ws/simulation`

Send actions:
```json
{"action": "start", "config": {"max_turns": 15, "enable_voice": true}}
{"action": "stop"}
```

Receive events:
- `simulation_started` - Simulation begun
- `turn_start` - New turn starting
- `scammer_message` - Scammer spoke (includes audio)
- `senior_message` - Senior responded (includes audio)
- `scammer_gave_up` - Scammer hung up
- `simulation_end` - Simulation finished

### REST Endpoints

- `GET /api/status` - Get simulation status
- `POST /api/stop` - Stop simulation
