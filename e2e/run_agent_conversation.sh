#!/bin/bash
#
# Run Agent-to-Agent Conversation
# 
# This script starts two local SDK agents and connects them together
# so they can have a conversation while you watch.
#
# Usage:
#   ./run_agent_conversation.sh
#
# Requirements:
#   - OPENAI_API_KEY environment variable set
#   - SMALLEST_API_KEY environment variable set (optional, for deployed agents)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Agent-to-Agent Conversation Runner                     ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Check for required environment variables
if [ -z "$OPENAI_API_KEY" ]; then
    echo -e "${RED}❌ OPENAI_API_KEY not set${NC}"
    echo "   Please set it: export OPENAI_API_KEY='your-key'"
    exit 1
fi
echo -e "${GREEN}✓ OPENAI_API_KEY is set${NC}"

# Activate virtual environment if it exists
if [ -f "../.venv/bin/activate" ]; then
    source ../.venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
fi

# Ports for the two agents
AGENT1_PORT=8081
AGENT2_PORT=8082

# Cleanup function
cleanup() {
    echo
    echo -e "${YELLOW}🛑 Shutting down agents...${NC}"
    
    # Kill agent processes
    if [ ! -z "$AGENT1_PID" ]; then
        kill $AGENT1_PID 2>/dev/null || true
    fi
    if [ ! -z "$AGENT2_PID" ]; then
        kill $AGENT2_PID 2>/dev/null || true
    fi
    
    # Kill any remaining processes on our ports
    fuser -k ${AGENT1_PORT}/tcp 2>/dev/null || true
    fuser -k ${AGENT2_PORT}/tcp 2>/dev/null || true
    
    echo -e "${GREEN}✓ Cleanup complete${NC}"
    exit 0
}

# Set trap for cleanup
trap cleanup SIGINT SIGTERM EXIT

echo
echo -e "${BLUE}Starting Agent 1 (Red) on port ${AGENT1_PORT}...${NC}"

# Create agent 1 config (Red - the caller)
cat > /tmp/agent1_red.py << 'EOF'
import os
from typing import AsyncIterator
from smallestai.atoms.agent.nodes import OutputAgentNode
from smallestai.atoms.agent.clients import OpenAIClient
from smallestai.atoms.agent.server import AtomsApp
from smallestai.atoms.agent.session import AgentSession

class RedAgent(OutputAgentNode):
    def __init__(self):
        super().__init__(name="RedAgent")
        self.system_prompt = """You are Red, a friendly sales representative calling to discuss products.
You are enthusiastic and professional. Keep responses brief (2-3 sentences).
Start conversations with a warm greeting and introduce yourself."""
        self.llm = OpenAIClient(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))
    
    async def generate_response(self) -> AsyncIterator[str]:
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self.context.messages:
            messages.append({"role": msg.role, "content": msg.content})
        async for chunk in self.llm.chat(messages, stream=True):
            if chunk.content:
                yield chunk.content

async def setup_session(session: AgentSession):
    session.add_node(RedAgent())
    await session.start()
    await session.wait_until_complete()

app = AtomsApp(setup_handler=setup_session)

if __name__ == "__main__":
    app.run(port=8081)
EOF

# Start agent 1
python /tmp/agent1_red.py &
AGENT1_PID=$!
echo -e "${GREEN}✓ Agent 1 (Red) started with PID ${AGENT1_PID}${NC}"

sleep 2

echo -e "${BLUE}Starting Agent 2 (Blue) on port ${AGENT2_PORT}...${NC}"

# Create agent 2 config (Blue - the receiver)  
cat > /tmp/agent2_blue.py << 'EOF'
import os
from typing import AsyncIterator
from smallestai.atoms.agent.nodes import OutputAgentNode
from smallestai.atoms.agent.clients import OpenAIClient
from smallestai.atoms.agent.server import AtomsApp
from smallestai.atoms.agent.session import AgentSession

class BlueAgent(OutputAgentNode):
    def __init__(self):
        super().__init__(name="BlueAgent")
        self.system_prompt = """You are Blue, a customer service representative receiving calls.
You are helpful, patient, and professional. Keep responses brief (2-3 sentences).
Listen carefully and respond appropriately to what the caller says."""
        self.llm = OpenAIClient(model="gpt-4o-mini", api_key=os.getenv("OPENAI_API_KEY"))
    
    async def generate_response(self) -> AsyncIterator[str]:
        messages = [{"role": "system", "content": self.system_prompt}]
        for msg in self.context.messages:
            messages.append({"role": msg.role, "content": msg.content})
        async for chunk in self.llm.chat(messages, stream=True):
            if chunk.content:
                yield chunk.content

async def setup_session(session: AgentSession):
    session.add_node(BlueAgent())
    await session.start()
    await session.wait_until_complete()

app = AtomsApp(setup_handler=setup_session)

if __name__ == "__main__":
    app.run(port=8082)
EOF

# Start agent 2
python /tmp/agent2_blue.py &
AGENT2_PID=$!
echo -e "${GREEN}✓ Agent 2 (Blue) started with PID ${AGENT2_PID}${NC}"

# Wait for servers to be ready
echo
echo -e "${YELLOW}⏳ Waiting for agents to be ready...${NC}"
sleep 3

# Check if agents are running
if ! kill -0 $AGENT1_PID 2>/dev/null; then
    echo -e "${RED}❌ Agent 1 failed to start${NC}"
    exit 1
fi

if ! kill -0 $AGENT2_PID 2>/dev/null; then
    echo -e "${RED}❌ Agent 2 failed to start${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Both agents are running${NC}"
echo

# Run the bridge to connect the agents
echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║     Starting Agent-to-Agent Conversation                   ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
echo

# Default message or use argument
INITIAL_MESSAGE="${1:-Hello! I'm calling to discuss some exciting new products we have available. Is this a good time to chat?}"

python agent_to_agent_websocket.py \
    --ws1 "ws://localhost:${AGENT1_PORT}/ws" \
    --ws2 "ws://localhost:${AGENT2_PORT}/ws" \
    --message "$INITIAL_MESSAGE"

# Cleanup will happen via trap
