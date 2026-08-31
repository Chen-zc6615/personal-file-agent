from langchain_litellm import ChatLiteLLM
from assistant.config import settings

def create_llm() -> ChatLiteLLM:
    """Create the chat model used by the agent."""
    return ChatLiteLLM(
        model=settings.model_name,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
    )