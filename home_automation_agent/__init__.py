from . import agent
try:
    from ToolCallCountingPlugin import CountInvocationPlugin, ToolCallCountingPlugin
except ModuleNotFoundError:
    CountInvocationPlugin = None
    ToolCallCountingPlugin = None
from google.adk.apps.app import App

# Align app name with UI slug (underscores) to avoid runner mismatch
plugins = []
if CountInvocationPlugin is not None:
    plugins.append(CountInvocationPlugin())
if ToolCallCountingPlugin is not None:
    plugins.append(ToolCallCountingPlugin())

app = App(
    name="home_automation_agent",
    root_agent=agent.root_agent,
    plugins=plugins,
)