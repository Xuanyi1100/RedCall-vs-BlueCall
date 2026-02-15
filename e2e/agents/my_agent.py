import os
from smallestai.atoms.agent.nodes import OutputAgentNode
from smallestai.atoms.agent.clients.openai import OpenAIClient

class MyAgent(OutputAgentNode):
    def __init__(self):
        super().__init__(name="my-agent")
        self.llm = OpenAIClient(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY")
        )

    async def generate_response(self):
        response = await self.llm.chat(
            messages=self.context.messages,
            stream=True
        )
        async for chunk in response:
            if chunk.content:
                yield chunk.content
