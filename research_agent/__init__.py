from . import agent
from google.adk.apps.app import App
from ToolCallCountingPlugin import CountInvocationPlugin, ToolCallCountingPlugin

# Expose an App so the loader picks it up and registers the plugin.
app = App(
    name="research-agent",
    root_agent=agent.root_agent,
    plugins=[CountInvocationPlugin(), ToolCallCountingPlugin()],
)