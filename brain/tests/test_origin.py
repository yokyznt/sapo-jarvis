import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import InvalidStatus

from sapo.server import LOCAL_ORIGINS


async def echo(ws):
    async for m in ws:
        await ws.send(m)


async def test_browser_origin_is_rejected():
    async with serve(echo, "127.0.0.1", 0, origins=LOCAL_ORIGINS) as server:
        port = server.sockets[0].getsockname()[1]
        with pytest.raises(InvalidStatus) as e:
            async with connect(f"ws://127.0.0.1:{port}", origin="https://pagina-mala.example"):
                pass
        assert e.value.response.status_code == 403


async def test_local_client_without_origin_is_accepted():
    async with serve(echo, "127.0.0.1", 0, origins=LOCAL_ORIGINS) as server:
        port = server.sockets[0].getsockname()[1]
        async with connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send("hola")
            assert await ws.recv() == "hola"
