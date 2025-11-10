import asyncio
import base64
import os
import glob
import re
import uuid

from setup_env import setup_gemini_env
from google.genai import types

from google.adk.agents import LlmAgent
from google.adk.models.google_llm import Gemini
from google.adk.apps.app import App, ResumabilityConfig
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner

from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters


# Retry configuration for robustness
retry_config = types.HttpRetryOptions(
    attempts=5,
    exp_base=7,
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],
)


# ----- Approval Logic Tool ----------------------------------------------------
COST_PER_IMAGE_USD = 0.01  # illustrative cost estimate for gating


def generate_images_request(prompt: str, num_images: int, tool_context: ToolContext) -> dict:
    """Approval-gated image generation request.

    Single image: auto-approve.
    Bulk (>1): request confirmation on first call, then resume using the decision.

    Returns a dict with status and message for the agent to act on.
    """
    if num_images <= 1:
        return {
            "status": "approved",
            "message": f"Auto-approved single image generation for prompt: '{prompt}'",
            "num_images": num_images,
        }

    # First invocation for bulk: request confirmation and return pending
    if not tool_context.tool_confirmation:
        est_cost = round(num_images * COST_PER_IMAGE_USD, 2)
        tool_context.request_confirmation(
            hint=(
                f"Bulk generation request for {num_images} images. Estimated cost: ${est_cost}. "
                f"Confirm to proceed."
            ),
            payload={"prompt": prompt, "num_images": num_images, "estimated_cost_usd": est_cost},
        )
        return {
            "status": "pending",
            "message": f"Approval required to generate {num_images} images for prompt: '{prompt}'",
            "num_images": num_images,
        }

    # Resumed call after confirmation
    if tool_context.tool_confirmation.confirmed:
        return {
            "status": "approved",
            "message": f"Approved bulk generation: {num_images} images for prompt: '{prompt}'",
            "num_images": num_images,
        }
    else:
        return {
            "status": "rejected",
            "message": f"Rejected bulk generation: {num_images} images for prompt: '{prompt}'",
            "num_images": num_images,
        }


# ----- MCP Toolset ------------------------------------------------------------
def build_mcp_image_toolset(
    provider: str = "@modelcontextprotocol/server-everything",
    tool_name: str = "getTinyImage",
    timeout: int = 30,
) -> McpToolset:
    """Constructs an MCP toolset for image generation.

    Defaults to the public "server-everything" and filters to the tiny image tool.
    """
    return McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="npx",
                args=["-y", provider],
                tool_filter=[tool_name],
            ),
            timeout=timeout,
        )
    )


# ----- Agent ------------------------------------------------------------------
mcp_image_toolset = build_mcp_image_toolset()

image_agent = LlmAgent(
    name="image_generation_agent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    instruction=(
        "You are an Image Generation Assistant. "
        "First, always call generate_images_request(prompt, num_images). "
        "If it returns status 'pending', inform the user approval is required and wait for a confirmation event. "
        "After approval, explicitly invoke the MCP image tool 'getTinyImage' exactly num_images times (one per image). "
        "For each invocation, return the image content so the system can save files. "
        "If status is 'rejected', inform the user and do not generate images. "
        "Keep responses concise and focus on tool execution when generating images."
    ),
    tools=[FunctionTool(func=generate_images_request), mcp_image_toolset],
    generate_content_config=types.GenerateContentConfig(
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=10,  # allow multiple MCP tool calls in a turn
            disable=False,
        )
    ),
)


# Wrap in a resumable app for long-running approval flows
image_app = App(
    name="image_generation_app",
    root_agent=image_agent,
    resumability_config=ResumabilityConfig(is_resumable=True),
)

session_service = InMemorySessionService()

image_runner = Runner(app=image_app, session_service=session_service)


# ----- Helpers ----------------------------------------------------------------
def check_for_approval(events):
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call and part.function_call.name == "adk_request_confirmation":
                    return {"approval_id": part.function_call.id, "invocation_id": event.invocation_id}
    return None


def print_agent_responses(events):
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.text:
                    print(f"Agent > {part.text}")


def create_approval_response(approval_info, approved: bool):
    confirmation_response = types.FunctionResponse(
        id=approval_info["approval_id"],
        name="adk_request_confirmation",
        response={"confirmed": approved},
    )
    return types.Content(role="user", parts=[types.Part(function_response=confirmation_response)])


def save_images_from_events(events, prefix: str = "generated_image_", start_index: int = 0) -> int:
    """Extracts base64 image data returned from MCP tool calls and saves PNG files.

    Returns the count of saved images.
    """
    saved = 0
    for event in events:
        if event.content and event.content.parts:
            for part in event.content.parts:
                # MCP tools typically return function_response with a 'content' list.
                fr = getattr(part, "function_response", None)
                if fr and fr.response:
                    for item in fr.response.get("content", []):
                        if item.get("type") == "image" and item.get("data"):
                            img_bytes = base64.b64decode(item["data"])  # base64
                            out_path = f"{prefix}{start_index + saved}.png"
                            with open(out_path, "wb") as f:
                                f.write(img_bytes)
                            print(f"Saved image to {out_path}")
                            saved += 1
                # Also support inline_data style image parts
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "mime_type", "").startswith("image/") and inline.data:
                    img_bytes = base64.b64decode(inline.data)
                    out_path = f"{prefix}{start_index + saved}.png"
                    with open(out_path, "wb") as f:
                        f.write(img_bytes)
                    print(f"Saved image to {out_path}")
                    saved += 1
    return saved


def get_next_image_index(prefix: str = "generated_image_") -> int:
    """Finds the next available integer index for files named like prefix{N}.png.

    Prevents overwriting previously generated images across runs.
    """
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)\.png$")
    max_idx = -1
    for path in glob.glob(f"{prefix}*.png"):
        filename = os.path.basename(path)
        m = pattern.match(filename)
        if m:
            try:
                idx = int(m.group(1))
                if idx > max_idx:
                    max_idx = idx
            except ValueError:
                continue
    return max_idx + 1


# ----- Workflow ---------------------------------------------------------------
async def run_image_workflow(prompt: str, num_images: int, auto_approve: bool = True) -> None:
    print("\n" + "=" * 60)
    print(f"User > Generate {num_images} image(s) for: '{prompt}'\n")

    session_id = f"img_{uuid.uuid4().hex[:8]}"
    await session_service.create_session(
        app_name="image_generation_app",
        user_id="test_user",
        session_id=session_id,
    )

    query_text = f"Generate {num_images} tiny image(s) with prompt: {prompt}"
    query_content = types.Content(role="user", parts=[types.Part(text=query_text)])
    events = []

    next_index = get_next_image_index(prefix="generated_image_")

    # Step 1: Initial run; gather events
    async for event in image_runner.run_async(
        user_id="test_user", session_id=session_id, new_message=query_content
    ):
        events.append(event)

    print_agent_responses(events)
    total_saved = save_images_from_events(
        events, prefix="generated_image_", start_index=next_index
    )
    next_index += total_saved

    # Step 2: Check for approval request
    approval_info = check_for_approval(events)

    # Step 3: If approval required, resume with decision
    if approval_info:
        print("⏸️  Pausing for approval...")
        print(f"🤔 Human Decision: {'APPROVE ✅' if auto_approve else 'REJECT ❌'}\n")

        resume_events = []
        async for event in image_runner.run_async(
            user_id="test_user",
            session_id=session_id,
            new_message=create_approval_response(approval_info, auto_approve),
            invocation_id=approval_info["invocation_id"],
        ):
            resume_events.append(event)

        print_agent_responses(resume_events)
        saved_after_resume = save_images_from_events(
            resume_events, prefix="generated_image_", start_index=next_index
        )
        total_saved += saved_after_resume

        if auto_approve:
            print(f"Agent > Total images saved after approval: {total_saved}")
        else:
            print("Agent > Approval rejected; no images saved.")
    else:
        print(f"Agent > Total images saved: {total_saved}")

    print("=" * 60 + "\n")


async def main():
    setup_gemini_env()
    # Demo A: Single image (auto-approve)
    await run_image_workflow(prompt="a tiny mountain scene", num_images=1)
    # Demo B: Bulk images (approve)
    await run_image_workflow(prompt="tiny sunset icon", num_images=3, auto_approve=True)
    # Demo C: Bulk images (reject)
    await run_image_workflow(prompt="tiny city skyline", num_images=2, auto_approve=False)


if __name__ == "__main__":
    asyncio.run(main())