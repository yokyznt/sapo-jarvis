import json
import os

import httpx
import pytest

from sapo.config import static_config
from sapo.files import read_drop
from sapo.gemini import Gemini, GeminiError
from sapo.protocol import ProtocolError, decode, relayed
from sapo.server import Hub, check_gemini, relay


@pytest.mark.parametrize(
    "raw",
    [
        {"type": ["chat"]},
        {"type": {"a": 1}},
        {"type": "event", "name": ["petted"]},
        {"type": "event", "name": "win", "what": {"x": 1}},
    ],
)
def test_decode_rejects_weird_types_without_crashing(raw):
    with pytest.raises(ProtocolError):
        decode(json.dumps(raw))


def test_decode_clamps_huge_boredom():
    assert decode(json.dumps({"type": "event", "name": "petted", "boredom": 10**400}))["boredom"] == 1.0


def test_relayed_survives_huge_numbers():
    assert relayed({"type": "mouth", "level": 10**400}) == {"type": "mouth", "level": 1.0}


async def test_relay_ignores_unhashable_type():
    assert await relay(json.dumps({"type": ["mouth"]}), None, Hub()) is False


def test_drop_refuses_unc_paths():
    assert read_drop(r"\\servidor\compartido\notas.txt").reason == "network"
    assert read_drop("//servidor/compartido/notas.txt").reason == "network"
    assert read_drop(r"\\?\UNC\servidor\compartido\notas.txt").reason == "network"


def test_drop_refuses_link_to_sensitive_file(tmp_path):
    secret_dir = tmp_path / ".ssh"
    secret_dir.mkdir()
    (secret_dir / "config").write_text("Host x\n", encoding="utf-8")
    link = tmp_path / "docs"
    try:
        import _winapi

        _winapi.CreateJunction(str(secret_dir), str(link))
    except (ImportError, OSError):
        try:
            os.symlink(secret_dir, link, target_is_directory=True)
        except OSError:
            pytest.skip("sin junctions ni symlinks")
    assert read_drop(str(link / "config")).reason == "sensitive"


async def test_check_gemini_survives_garbage_model_list():
    gemini = Gemini(lambda: "k", client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="<html>portal</html>"))))
    with pytest.raises(GeminiError):
        await gemini.models()
    await check_gemini(gemini, static_config(provider="gemini"))
