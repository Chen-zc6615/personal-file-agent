from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Request body for a chat message."""

    message: str = Field(
        min_length=1,
        max_length=10_000,
    )
    thread_id: str | None = None


class ChatResponse(BaseModel):
    """Response returned by the assistant."""

    response: str
    thread_id: str