from smallestai.atoms.agent.server import AtomsApp
from smallestai.atoms.agent.session import AgentSession
from my_agent import MyAgent

async def on_start(session: AgentSession):
    session.add_node(MyAgent())
    await session.start()
    await session.wait_until_complete()

if __name__ == "__main__":
    app = AtomsApp(setup_handler=on_start)
    app.run()
