import base64
import json
import time

import pytest

from sapo_prefs import app, phone, secrets, store
from sapo_prefs.api import Api


@pytest.fixture(autouse=True)
def sapo_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SAPO_HOME", str(tmp_path))
    return tmp_path


def read_secrets(home):
    return json.loads((home / "secrets.json").read_text("utf-8"))


def opened(blob):
    return json.loads(secrets.unprotect(base64.b64decode(blob)).decode("utf-8"))


def seal(data):
    return base64.b64encode(secrets.protect(json.dumps(data).encode("utf-8"))).decode("ascii")


def test_new_code_is_encrypted_and_keeps_other_secrets(sapo_home):
    (sapo_home / "secrets.json").write_text(json.dumps({"gemini_api_key": "x"}), "utf-8")
    now = time.time()
    r = phone.new_code(now)
    code = r["code"]
    assert len(code) == 6 and code.isdigit() and r["expires_in"] == 300
    raw = (sapo_home / "secrets.json").read_text("utf-8")
    data = read_secrets(sapo_home)
    assert data["gemini_api_key"] == "x"
    assert f'"{code}"' not in raw
    assert opened(data["phone_pair"]) == {"code": code, "expires": now + 300, "tries": 0}
    assert phone.pending(now + 10) == 290
    assert phone.pending(now + 301) == 0


def test_codes_vary():
    assert len({phone.new_code()["code"] for _ in range(8)}) > 1


def test_pending_zero_after_too_many_tries(sapo_home):
    (sapo_home / "secrets.json").write_text(json.dumps({"phone_pair": seal({"code": "123456", "expires": time.time() + 200, "tries": 5})}), "utf-8")
    assert phone.pending() == 0
    (sapo_home / "secrets.json").write_text(json.dumps({"phone_pair": "basura"}), "utf-8")
    assert phone.pending() == 0


def test_cancel_code(sapo_home):
    phone.new_code()
    phone.cancel_code()
    assert "phone_pair" not in read_secrets(sapo_home)
    assert phone.pending() == 0
    phone.cancel_code()


def test_devices_and_revoke(sapo_home):
    tokens = [
        {"id": "aa11", "device": "Nothing A059", "date": "2026-10-31T12:00:00", "token": "blob1"},
        {"id": "bb22", "device": "", "date": "2026-10-30T09:00:00", "token": "blob2"},
        "basura",
    ]
    (sapo_home / "secrets.json").write_text(json.dumps({"gemini_api_key": "k", "phone_tokens": tokens}), "utf-8")
    assert phone.devices() == [
        {"id": "aa11", "device": "Nothing A059", "date": "2026-10-31T12:00:00"},
        {"id": "bb22", "device": "Celular", "date": "2026-10-30T09:00:00"},
    ]
    assert all("token" not in d for d in phone.devices())
    r = Api().phone_revoke("aa11")
    assert r["ok"] and [d["id"] for d in r["phone"]["devices"]] == ["bb22"]
    data = read_secrets(sapo_home)
    assert data["gemini_api_key"] == "k" and len(data["phone_tokens"]) == 2
    again = Api().phone_revoke("aa11")
    assert again["ok"] is False and again["error"]


def test_api_pair_and_state(sapo_home):
    api = Api()
    r = api.phone_pair()
    assert r["ok"] and len(r["code"]) == 6 and r["port"] == 8766 and isinstance(r["ips"], list)
    st = api.phone_state()
    assert 0 < st["pending"] <= 300 and st["devices"] == [] and st["port"] == 8766 and st["name"]
    assert api.phone_cancel() == {"ok": True}
    assert api.phone_state()["pending"] == 0


def test_local_ips_are_private():
    import ipaddress

    for ip in phone.local_ips():
        addr = ipaddress.ip_address(ip)
        assert addr.is_private and not addr.is_loopback


def test_phone_section_and_como_yo(sapo_home):
    assert store.effective()["phone"] == {"enabled": False}
    assert store.update("phone", "enabled", True) is True
    assert store.update("brain", "personality", "como_yo") == "como_yo"
    data = json.loads((sapo_home / "config.json").read_text("utf-8"))
    assert data == {"phone": {"enabled": True}, "brain": {"personality": "como_yo"}}
    assert store.effective()["phone"]["enabled"] is True
    with pytest.raises(ValueError):
        store.update("phone", "enabled", "si")
    assert Api().set("phone", "port", 1)["ok"] is False


def test_ui_has_phone_tab():
    html = app.page()
    for needle in ('data-tab="celular"', 'id="tab-celular"', 'data-bind="phone.enabled"', 'id="pair-new"', 'id="devices"', 'data-v="como_yo"', "firewall", "phone_pair", "phone_revoke"):
        assert needle in html
