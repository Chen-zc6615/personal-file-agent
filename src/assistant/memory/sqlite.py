from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from assistant.config import settings


@asynccontextmanager
async def open_sqlite_checkpointer() -> AsyncIterator[AsyncSqliteSaver]:
    """Open the SQLite checkpointer for the application lifetime."""

    database_path = settings.sqlite_path
    database_path.parent.mkdir(parents=True, exist_ok=True)

    async with AsyncSqliteSaver.from_conn_string(
        str(database_path)
    ) as checkpointer:
        yield checkpointer