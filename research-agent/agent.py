from google.adk.agents import LlmAgent 
from google.adk.models.google_llm import Gemini 
from google.adk.tools.agent_tool import AgentTool 
from google.adk.tools.google_search_tool import google_search 

from google.genai import types 
from typing import List 

retry_config = types.HttpRetryOptions( 
    attempts=5,  # Maximum retry attempts 
    exp_base=7,  # Delay multiplier 
    initial_delay=1, 
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors 
) 

# ---- Count number of papers in a list of strings ---- 
def count_papers(papers: List[str]): 
    """ 
    This function counts the number of papers in a list of strings. 
    Args: 
      papers: A list of strings, where each string is a research paper. 
    Returns: 
      The number of papers in the list. 
    """ 
    return len(papers) 


# Google Search agent 
google_search_agent = LlmAgent( 
    name="google_search_agent", 
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config), 
    description="Searches for information using Google search", 
    instruction="""Use the google_search tool to find information on the given topic. Return the raw search results. 
    If the user asks for a list of papers, then give them the list of research papers you found and not the summary.""", 
    tools=[google_search] 
) 


# Root agent 
root_agent = LlmAgent( 
    name="research_paper_finder_agent", 
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config), 
    instruction="""Your task is to find research papers and count them. 

    You MUST ALWAYS follow these steps: 
    1) Find research papers on the user provided topic using the 'google_search_agent'. 
    2) Then, pass the papers to 'count_papers' tool to count the number of papers returned. 
    3) Return both the list of research papers and the total number of papers. 
    """, 
    tools=[AgentTool(agent=google_search_agent), count_papers] 
)
print("✅ Agent created")

from google.adk.runners import InMemoryRunner
from google.adk.plugins.logging_plugin import LoggingPlugin
import os, sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ToolCallCountingPlugin import ToolCallCountingPlugin
from google.genai import types

import asyncio

async def main():
    runner = InMemoryRunner(
        agent=root_agent,
        plugins=[LoggingPlugin(), ToolCallCountingPlugin()],
    )

    print("✅ Runner configured")
    print("🚀 Running agent with LoggingPlugin...")
    print("📊 Watch the comprehensive logging output below:\n")

    # Debug helper is async; await to run and print events.
    await runner.run_debug("Find latest quantum computing papers", verbose=True)


if __name__ == "__main__":
    asyncio.run(main())