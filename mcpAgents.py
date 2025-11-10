import uuid
import asyncio
from setup_env import setup_gemini_env
from google.genai import types

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService

from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters

from google.adk.apps.app import App, ResumabilityConfig
from google.adk.tools.function_tool import FunctionTool

print("✅ ADK components imported successfully.")

retry_config=types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504] # Retry on these HTTP errors
)

# MCP integration with Everything Server
mcp_image_server = McpToolset(
    connection_params=StdioConnectionParams(
        server_params=StdioServerParameters(
            command='npx',  # Run MCP server via npx
            args=["-y",  # Argument for npx to auto-confirm install
                  "@modelcontextprotocol/server-everything",
                ],
            tool_filter=['getTinyImage']
        ),
        timeout=30,
    )
)

print("✅ MCP Tool created")

# Create image agent with MCP integration
image_agent = LlmAgent(
   model=Gemini(
        model="gemini-2.5-flash-lite",
        retry_options=retry_config
   ),
   name='image_agent',
   instruction='Use the MCP Tool to generate images for user queries',
   tools = [mcp_image_server]
)

from google.adk.runners import InMemoryRunner

runner = InMemoryRunner(agent=image_agent)

import base64

async def main():
    setup_gemini_env()
    response = await runner.run_debug("Provide a sample tiny image", verbose=True)
    print("\n=== MCP Image Agent Response ===\n")
    print(response)

    # Attempt to display or save any returned images
    images_saved = 0
    try:
        from IPython.display import display, Image as IPImage
        have_ipython = True
    except Exception:
        have_ipython = False

    for event in response:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, 'function_response') and part.function_response:
                    for item in part.function_response.response.get('content', []):
                        if item.get('type') == 'image' and item.get('data'):
                            img_bytes = base64.b64decode(item['data'])
                            out_path = f"tiny_image_{images_saved}.png"
                            with open(out_path, 'wb') as f:
                                f.write(img_bytes)
                            images_saved += 1
                            print(f"Saved image to {out_path}")
                            if have_ipython:
                                display(IPImage(data=img_bytes))

if __name__ == "__main__":
    asyncio.run(main())