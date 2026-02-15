"""
Simple SDK Agent for Smallest.ai

This is a basic agent template that can be deployed to the Atoms platform.
Customize the system prompt and behavior as needed.
"""

import os
from typing import AsyncIterator

from smallestai.atoms.agent.nodes import OutputAgentNode
from smallestai.atoms.agent.clients import OpenAIClient
from smallestai.atoms.agent.server import AtomsApp
from smallestai.atoms.agent.session import AgentSession


class SimpleAgent(OutputAgentNode):
    """A simple conversational agent"""
    
    def __init__(
        self,
        name: str = "SimpleAgent",
        system_prompt: str = "You are a helpful and friendly AI assistant.",
    ):
        super().__init__(name=name)
        self.system_prompt = system_prompt
        self.llm = OpenAIClient(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY"),
        )
    
    async def generate_response(self) -> AsyncIterator[str]:
        """Generate a streaming response"""
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add conversation history from context
        for msg in self.context.messages:
            messages.append({
                "role": msg.role,
                "content": msg.content
            })
        
        # Stream the response using chat() with stream=True
        async for chunk in self.llm.chat(messages, stream=True):
            if chunk.content:
                yield chunk.content


# Agent configuration
async def setup_session(session: AgentSession):
    """Configure the agent session"""
    agent = SimpleAgent(
        name="Assistant",
        system_prompt="""You are a friendly and helpful AI assistant. 
Keep your responses concise but engaging. 
If someone starts a conversation, greet them warmly and ask how you can help."""
    )
    session.add_node(agent)
    
    # Start the session after adding nodes
    await session.start()
    
    # Wait for the session to complete
    await session.wait_until_complete()


# Create the app
app = AtomsApp(setup_handler=setup_session)


if __name__ == "__main__":
    # Run locally for testing
    app.run()
