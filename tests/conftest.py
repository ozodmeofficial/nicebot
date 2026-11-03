import os
import socket

import pytest

PG_URL = os.environ.get("NB_PG_URL", "postgres://postgres@localhost:5432/nbtest")
MY_URL = os.environ.get("NB_MY_URL", "mysql://nb:nb@localhost:3306/nbtest")


def _up(port: int) -> bool:
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


BACKENDS = ["sqlite", "mongo"]
if _up(5432):
    BACKENDS.append("postgres")
if _up(3306):
    BACKENDS.append("mysql")


async def make_db(kind: str):
    from nicebot.orm import Database

    if kind == "sqlite":
        return await Database("sqlite:///:memory:").connect(migrate=False)
    if kind == "mongo":
        from mongomock_motor import AsyncMongoMockClient

        return await Database("mongodb://localhost/nbtest", client=AsyncMongoMockClient(tz_aware=True)).connect(migrate=False)
    if kind == "postgres":
        db = await Database(PG_URL).connect(migrate=False)
        for r in await db.fetch("SELECT tablename FROM pg_tables WHERE schemaname = current_schema()"):
            await db.execute(f'DROP TABLE IF EXISTS "{r["tablename"]}" CASCADE')
        return db
    if kind == "mysql":
        db = await Database(MY_URL).connect(migrate=False)
        await db.execute("SET FOREIGN_KEY_CHECKS = 0")
        for r in await db.fetch("SELECT table_name AS t FROM information_schema.tables WHERE table_schema = DATABASE()"):
            await db.execute(f"DROP TABLE IF EXISTS `{r['t']}`")
        await db.execute("SET FOREIGN_KEY_CHECKS = 1")
        return db
    raise ValueError(kind)


@pytest.fixture(params=BACKENDS)
async def db(request):
    database = await make_db(request.param)
    yield database
    await database.close()
