from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request

from assistant.agents.graph import create_agent_graph
from assistant.config import settings
from assistant.memory.sqlite import open_sqlite_checkpointer
from assistant.schemas import ChatRequest, ChatResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with open_sqlite_checkpointer() as checkpointer:
        app.state.agent_graph = await create_agent_graph(
            checkpointer=checkpointer,
        )
        yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
) -> ChatResponse:
    thread_id = payload.thread_id or str(uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    result = await request.app.state.agent_graph.ainvoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": payload.message,
                }
            ]
        },
        config=config,
    )

    final_message = result["messages"][-1]
    content = final_message.content

    if not isinstance(content, str):
        content = str(content)

    return ChatResponse(
        response=content,
        thread_id=thread_id,
    )