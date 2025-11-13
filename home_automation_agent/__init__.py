from . import agent
from google.adk.apps.app import App
from ToolCallCountingPlugin import ToolCallCountingPlugin

# Expose an App so the ADK web loader discovers it
app = App(
    name="home-automation-agent",
    root_agent=agent.root_agent,
    plugins=[ToolCallCountingPlugin()],
)