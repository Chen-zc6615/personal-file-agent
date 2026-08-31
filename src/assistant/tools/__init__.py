from langchain_core.tools import BaseTool
from assistant.tools.builtin import get_current_time


LOCAL_TOOLS: list[BaseTool] = [
    get_current_time,
]