from contextlib import asynccontextmanager
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from assistant import api


class FakeAgentGraph:
    """A fake Agent used to avoid calling a real LLM."""

    async def ainvoke(self, input_data, config):
        user_message = input_data["messages"][0]["content"]

        return {
            "messages": [
                AIMessage(content=f"收到：{user_message}")
            ]
        }


@asynccontextmanager
async def fake_checkpointer():
    yield object()


async def fake_create_agent_graph(checkpointer):
    return FakeAgentGraph()


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(
        api,
        "open_sqlite_checkpointer",
        fake_checkpointer,
    )
    monkeypatch.setattr(
        api,
        "create_agent_graph",
        fake_create_agent_graph,
    )

    with TestClient(api.app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_chat_generates_thread_id(client):
    response = client.post(
        "/chat",
        json={
            "message": "你好",
            "thread_id": None,
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["response"] == "收到：你好"
    UUID(data["thread_id"])


def test_chat_reuses_thread_id(client):
    response = client.post(
        "/chat",
        json={
            "message": "继续聊天",
            "thread_id": "test-thread",
        },
    )

    assert response.status_code == 200
    assert response.json()["thread_id"] == "test-thread"


def test_chat_rejects_empty_message(client):
    response = client.post(
        "/chat",
        json={
            "message": "",
        },
    )

    assert response.status_code == 422