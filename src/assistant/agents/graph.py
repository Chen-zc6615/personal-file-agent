from langchain_core.messages import SystemMessage
from langgraph.graph import MessagesState, START, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.base import BaseCheckpointSaver

from assistant.config import settings
from assistant.tools.mcp import load_mcp_tools
from assistant.llm import create_llm
from assistant.tools import LOCAL_TOOLS


SYSTEM_PROMPT = """
You are a helpful personal assistant.
Use tools when they are needed to answer accurately.

For file organization:
1. Always create and show an organization plan first.
2. Never move, rename, overwrite, or delete files during planning.
3. Only apply a file organization or rename plan, or create an archive,
   after the user explicitly confirms the displayed plan in a later message.
4. Never assume that silence or an ambiguous response is confirmation.
5. Never reorganize a software project directory.
""".strip()


async def create_agent_graph(
        checkpointer: BaseCheckpointSaver | None = None,
    ):
    """Create the LangGraph agent workflow."""

    mcp_tools = await load_mcp_tools(settings.mcp_servers)

    tools = [
        *LOCAL_TOOLS,
        *mcp_tools,
    ]

    llm = create_llm()
    llm_with_tools = llm.bind_tools(tools)

    async def call_model(state: MessagesState):
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            *state['messages'],
        ]

        response = await llm_with_tools.ainvoke(messages)

        return {
            "messages": [response]
        }

    builder = StateGraph(MessagesState)

    builder.add_node("model", call_model)
    builder.add_node("tools", ToolNode(tools))

    builder.add_edge(START, "model")
    builder.add_conditional_edges("model", tools_condition)
    builder.add_edge("tools", "model")

    return builder.compile(
        checkpointer=checkpointer,
    )
