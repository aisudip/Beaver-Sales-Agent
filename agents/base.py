# agents/base.py — Agent factory to remove class repetition
from smolagents import ToolCallingAgent


def create_agent(model, tools: list, name: str, description: str) -> ToolCallingAgent:
    """Create a ToolCallingAgent with the given model, tools, name, and description."""
    return ToolCallingAgent(
        tools=tools,
        model=model,
        name=name,
        description=description,
    )
