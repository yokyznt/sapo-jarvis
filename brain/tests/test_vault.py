import json
import sys

import pytest

from sapo.vault import KeyStore, protect, unprotect

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="DPAPI solo en Windows")


def test_dpapi_roundtrip_real():
    secret = "AIza-prueba-ñandú-🐸-" + "x" * 40
    blob = protect(secret)
    assert secret not in blob
    assert unprotect(blob) == secret
    assert protect(secret) != blob


def test_keystore_reads_secrets_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    path = tmp_path / "secrets.json"
    store = KeyStore(path=path)
    assert store.get() is None
    path.write_text(json.dumps({"gemini_api_key": protect("clave-uno")}), encoding="utf-8")
    assert store.get() == "clave-uno"
    path.write_text(json.dumps({"gemini_api_key": protect("clave-dos-más-larga")}), encoding="utf-8")
    assert store.get() == "clave-dos-más-larga"
    monkeypatch.setenv("GEMINI_API_KEY", "desde-env")
    assert store.get() == "desde-env"
    assert "clave" not in repr(store)


def test_keystore_bad_blob(tmp_path, monkeypatch, caplog):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    path = tmp_path / "secrets.json"
    path.write_text(json.dumps({"gemini_api_key": "bm8tZXMtZHBhcGk="}), encoding="utf-8")
    assert KeyStore(path=path).get() is None
    assert "bm8tZXMtZHBhcGk" not in caplog.text
