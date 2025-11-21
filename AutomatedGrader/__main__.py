"""Entry point for running AutomatedGrader as a module.

Usage:
    python -m AutomatedGrader <input_file> [--rubric "..."] [--pause-after <stage>]
"""
import asyncio
from AutomatedGrader.orchestrator import main_cli

if __name__ == "__main__":
    asyncio.run(main_cli())

