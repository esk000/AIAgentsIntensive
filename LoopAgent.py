import asyncio
from setup_env import setup_gemini_env
from google.adk.agents import Agent, SequentialAgent, LoopAgent
from google.adk.runners import InMemoryRunner
from google.adk.tools import FunctionTool

# This agent runs ONCE at the beginning to create the first draft.
initial_writer_agent = Agent(
    name="InitialWriterAgent",
    model="gemini-2.5-flash-lite",
    instruction="""Based on the user's prompt, write the first draft of a short story (around 100-150 words).
    Output only the story text, with no introduction or explanation.""",
    output_key="current_story", # Stores the first draft in the state.
)

print("✅ initial_writer_agent created.")

# This agent's only job is to provide feedback or the approval signal. It has no tools.
critic_agent = Agent(
    name="CriticAgent",
    model="gemini-2.5-flash-lite",
    instruction="""You are a constructive story critic. Review the story provided below.
    Story: {current_story}
    
    Evaluate the story's plot, characters, and pacing.
    - If the story is well-written and complete, you MUST respond with the exact phrase: "APPROVED"
    - Otherwise, provide 2-3 specific, actionable suggestions for improvement.""",
    output_key="critique", # Stores the feedback in the state.
)

print("✅ critic_agent created.")

# This is the function that the RefinerAgent will call to exit the loop.
def exit_loop(critique: str):
    """Decide whether to approve based on the critic's comments.

    Approval rules:
    - If the critique includes the word 'APPROVED' (case-insensitive), approve.
    - If there are no clear suggestions present, approve.
    - Otherwise, continue refinement.

    Heuristics for suggestions: look for common markers such as '-', '•', 'suggestion',
    'improve', 'could', 'should', 'would benefit'.
    """
    text = (critique or "").lower()
    approved_signal = "approved" in text

    markers = ["-", "•", "suggestion", "improve", "could", "should", "would benefit"]
    suggestion_count = sum(text.count(m) for m in markers)

    if approved_signal or suggestion_count == 0:
        return {"status": "approved", "message": "Story approved. Exiting refinement loop."}
    return {"status": "continue", "message": "Critique indicates refinements are needed."}

print("✅ exit_loop function created.")

# This agent refines the story based on critique OR calls the exit_loop function.
refiner_agent = Agent(
    name="RefinerAgent",
    model="gemini-2.5-flash-lite",
    instruction="""You are a story refiner. You have a story draft and critique.
    
    Story Draft: {current_story}
    Critique: {critique}
    
    Your task is to analyze the critique.
    - First, call `exit_loop(critique={critique})` to decide whether to stop.
    - If the tool returns status "approved", do not change the story and stop.
    - Otherwise, rewrite the story draft to fully incorporate the feedback from the critique.""",
    
    output_key="current_story", # It overwrites the story with the new, refined version.
    tools=[FunctionTool(exit_loop)], # The tool is now correctly initialized with the function reference.
)

print("✅ refiner_agent created.")

# The LoopAgent contains the agents that will run repeatedly: Critic -> Refiner.
story_refinement_loop = LoopAgent(
    name="StoryRefinementLoop",
    sub_agents=[critic_agent, refiner_agent],
    max_iterations=2, # Prevents infinite loops
)

# The root agent is a SequentialAgent that defines the overall workflow: Initial Write -> Refinement Loop.
root_agent = SequentialAgent(
    name="StoryPipeline",
    sub_agents=[initial_writer_agent, story_refinement_loop],
)

print("✅ Loop and Sequential Agents created.")

runner = InMemoryRunner(agent=root_agent)

async def main():
    setup_gemini_env()
    response = await runner.run_debug(
        "Write a short story about a lighthouse keeper who discovers a mysterious, glowing map"
    )
    print("\n=== Refined Story ===\n")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
