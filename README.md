# RedCall vs BlueCall 🔴📞🔵

A multi-agent adversarial scam simulation system built with Python, LangGraph, and OpenAI (with DeepSeek fallback).

## Overview

This project implements two fully independent AI agents that interact through natural language only:

- **🔴 Red Team (Scammer)**: An AI simulating a phone scammer attempting to extract sensitive information using IRS/government fraud tactics
- **🔵 Blue Team (Senior Defender)**: A scam-baiting AI that pretends to be a confused elderly person while actually stalling and wasting the scammer's time

Each agent has:
- Independent memory
- Independent internal reasoning  
- Independent strategy adaptation
- Communication only through dialogue text

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                              │
│  - Maintains turn counter                                        │
│  - Passes ONLY dialogue text between agents                      │
│  - No shared state                                               │
└─────────────────────────────────────────────────────────────────┘
         │                                    │
         ▼                                    ▼
┌─────────────────────┐           ┌─────────────────────┐
│   SCAMMER AGENT     │           │   SENIOR AGENT      │
│   (Red Team)        │           │   (Blue Team)       │
├─────────────────────┤           ├─────────────────────┤
│ State:              │           │ State:              │
│ - turn              │  dialogue │ - turn              │
│ - conversation_mem  │◄─────────►│ - conversation_mem  │
│ - persuasion_stage  │   only    │ - scam_confidence   │
│ - persuasion_level  │           │ - delay_strategy    │
│ - extracted_info    │           │ - leaked_info       │
├─────────────────────┤           ├─────────────────────┤
│ Graph Flow:         │           │ Graph Flow:         │
│ analyze → escalate  │           │ analyze → strategy  │
│    → respond →      │           │    → respond →      │
│      reflect        │           │      reflect        │
└─────────────────────┘           └─────────────────────┘
```

## Setup

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key (or DeepSeek API key as fallback)
- Smallest.ai API key (optional, for voice mode)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/RedCall-vs-BlueCall.git
cd RedCall-vs-BlueCall
```

2. Install dependencies:
```bash
uv sync
```

3. Set up your API keys:
```bash
cp .env.example .env
# Edit .env and add your API keys:
# - OPENAI_API_KEY or DEEPSEEK_API_KEY (required for LLM)
# - SMALLEST_API_KEY (optional, for voice mode)
```

## Usage

### Basic Run

```bash
uv run python main.py
```

### Options

```bash
uv run python main.py --turns 10        # Run for max 10 turns
uv run python main.py --threshold 0.8   # Lower persuasion threshold
uv run python main.py --quiet           # Only show final report
```

### Voice Mode

Enable text-to-speech audio generation using [Smallest.ai](https://smallest.ai) Waves API:

```bash
# Generate audio files for each turn (saved to audio_output/)
uv run python main.py --voice

# Generate AND play audio in real-time through speakers
uv run python main.py --play

# Customize audio output directory
uv run python main.py --voice --audio-dir my_audio

# Combine with other options
uv run python main.py --play --turns 5
```

Voice mode requires `SMALLEST_API_KEY` in your `.env` file. Get your API key from [console.smallest.ai](https://console.smallest.ai).

### Example Output

```
============================================================
TURN 1
============================================================

🔴 Scammer: Hello, this is Officer Johnson from the IRS Tax Resolution Department...
   [Stage: rapport, Persuasion: 0.00]

🔵 Senior: Oh my, the IRS? What was that dear? Could you speak up a little?
   [Confidence: 0.15, Tactic: ASK_REPEAT]

============================================================
FINAL EVALUATION REPORT
============================================================

📊 BASIC METRICS
   Total Turns: 15
   End Reason: max_turns_reached
   Time Wasted: 7m 30s

🔵 DEFENDER (Senior) METRICS
   Scam Confidence: 85.00%
   Sensitive Info Leaked: ✅ NO
   Defender Score: 78/100

🔴 ATTACKER (Scammer) METRICS  
   Persuasion Level: 35.00%
   Max Stage Reached: urgency
   Scammer Score: 34/100

============================================================
WINNER: 🔵 DEFENDER
============================================================
```

## Project Structure

```
RedCall-vs-BlueCall/
├── pyproject.toml          # Project config and dependencies
├── .env.example            # Environment template
├── main.py                 # Entry point
├── orchestrator.py         # Conversation coordinator
├── evaluator.py            # Metrics and reporting
├── core/
│   ├── llm.py              # LLM abstraction (OpenAI/DeepSeek)
│   └── voice.py            # TTS using Smallest.ai Waves API
├── agents/
│   ├── scammer/            # Red Team agent
│   │   ├── state.py        # ScammerState TypedDict
│   │   ├── prompts.py      # System & node prompts
│   │   └── graph.py        # LangGraph definition
│   └── senior/             # Blue Team agent
│       ├── state.py        # SeniorState TypedDict
│       ├── prompts.py      # System & node prompts
│       └── graph.py        # LangGraph definition
└── audio_output/           # Generated audio files (when using --voice)
```

## Agent Details

### Scammer Agent (Red Team)

**Persuasion Stages:**
1. `rapport` - Building trust, friendly conversation
2. `scenario` - Presenting the problem (unpaid taxes, warrant)
3. `urgency` - Creating time pressure (police coming)
4. `extraction` - Asking for SSN, bank details
5. `final_push` - Demanding immediate payment

**Graph Nodes:**
- `analyze_node` - Assess victim compliance
- `escalate_node` - Decide stage progression
- `respond_node` - Generate scam dialogue
- `reflect_node` - Update persuasion metrics

### Senior Defender Agent (Blue Team)

**Delay Tactics (by confidence level):**
- Level 1: Ask to repeat, clarify, slow response
- Level 2: Tangents, hearing issues, "hold on"
- Level 3: Tech issues, wrong info, endless questions
- Level 4: Bathroom break, doorbell, transfer confusion
- Level 5: Loop back, fake compliance

**Graph Nodes:**
- `analyze_node` - Identify scam patterns
- `strategy_node` - Choose delay tactic
- `respond_node` - Generate stalling dialogue
- `reflect_node` - Check for info leaks

## Extending

### Voice Configuration

The voice module (`core/voice.py`) uses Smallest.ai Waves API with these defaults:
- Scammer voice: `george` (male)
- Senior voice: `emily` (female)

To change voices, edit the constants in `core/voice.py`:
```python
SCAMMER_VOICE = "george"  # Change to any Smallest.ai voice ID
SENIOR_VOICE = "emily"
```

### Custom Scam Scenarios

Edit `agents/scammer/prompts.py` to change the scam type (tech support, lottery, romance, etc.)

### Custom Defense Personas

Edit `agents/senior/prompts.py` to change the defender persona and tactics.

## License

MIT




TODO:
- STT detect emotion, to anyslysis the state of the other side
- layout and UI for the demo
- add scammer and senior inner OS to output, good for demo
- change voice
