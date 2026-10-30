import json
import winreg

import pytest

from sapo_prefs import autostart, gemini, secrets, store
from sapo_prefs.api import Api

TEST_KEY = r"Software\SapoTest"


@pytest.fixture(autouse=True)
def sapo_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SAPO_HOME", str(tmp_path))
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    return tmp_path


@pytest.fixture
def run_key():
    yield TEST_KEY
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, TEST_KEY)
    except FileNotFoundError:
        pass


def write_config(home, data):
    (home / "config.json").write_text(json.dumps(data), "utf-8")


def read_config(home):
    return json.loads((home / "config.json").read_text("utf-8"))


def test_home_uses_env(sapo_home):
    assert store.config_path() == sapo_home / "config.json"


def test_update_preserves_unknown_keys_and_sections(sapo_home):
    write_config(sapo_home, {
        "pc": {"skin": "menta", "pin": {"x": 960, "y": -250}, "futuro": 1},
        "brain": {"gemini_model": "gemini-flash-latest", "ollama_model": "qwen3.5:4b"},
        "otra": {"a": [1, 2]},
    })
    store.update("pc", "energy", "Zen")
    store.update("brain", "personality", "tierno")
    store.update("voice", "pitch", 3)
    data = read_config(sapo_home)
    assert data["pc"] == {"skin": "menta", "pin": {"x": 960, "y": -250}, "futuro": 1, "energy": "Zen"}
    assert data["brain"] == {"gemini_model": "gemini-flash-latest", "ollama_model": "qwen3.5:4b", "personality": "tierno"}
    assert data["otra"] == {"a": [1, 2]}
    assert data["voice"]["pitch"] == 3.0
    assert not (sapo_home / "config.json.tmp").exists()


def test_creates_file_when_missing(sapo_home):
    store.update("pc", "size", 2)
    assert read_config(sapo_home) == {"pc": {"size": 2}}


def test_corrupt_config_gives_defaults_and_is_rewritten(sapo_home):
    (sapo_home / "config.json").write_text("{no es json", "utf-8")
    eff = store.effective()
    assert eff == {k: {kk: (list(vv) if isinstance(vv, list) else vv) for kk, vv in v.items()} for k, v in store.DEFAULTS.items()}
    store.update("pc", "skin", "rosa")
    assert read_config(sapo_home) == {"pc": {"skin": "rosa"}}


def test_effective_replaces_invalid_values(sapo_home):
    write_config(sapo_home, {"pc": {"size": 7, "energy": "Loco", "volume": 3, "monitor": "1", "pin": {"x": "a"}}, "brain": {"comment_minutes": 5}, "voice": "mal"})
    eff = store.effective()
    assert eff["pc"]["size"] == 0
    assert eff["pc"]["energy"] == "Normal"
    assert eff["pc"]["volume"] == 0.6
    assert eff["pc"]["monitor"] == 1
    assert eff["pc"]["pin"] is None
    assert eff["brain"]["comment_minutes"] == 5
    assert eff["voice"]["wake"] == "oye sapo"


@pytest.mark.parametrize("section,key,value", [
    ("pc", "size", 3),
    ("pc", "size", True),
    ("pc", "size", "1"),
    ("pc", "energy", "zen"),
    ("pc", "volume", 1.5),
    ("pc", "volume", "nan"),
    ("pc", "skin", "../evil"),
    ("pc", "monitor", -1),
    ("pc", "sounds", 1),
    ("brain", "provider", "openai"),
    ("brain", "comment_minutes", 0),
    ("brain", "comment_minutes", 2.5),
    ("brain", "blacklist", "keepass"),
    ("voice", "wake", "   "),
    ("voice", "speed", 5),
    ("voice", "mic", "a\nb"),
    ("startup", "autostart", "si"),
])
def test_rejects_invalid(sapo_home, section, key, value):
    with pytest.raises(ValueError):
        store.update(section, key, value)
    assert not (sapo_home / "config.json").exists()


def test_rejects_unknown_key():
    with pytest.raises(KeyError):
        store.update("pc", "pin", {"x": 1, "y": 2})


def test_blacklist_normalized():
    assert store.update("brain", "blacklist", [" KeePass ", "keepass", "", "Banco"]) == ["keepass", "banco"]


def test_remove_pin_keeps_rest(sapo_home):
    write_config(sapo_home, {"pc": {"skin": "noche", "pin": {"x": 1, "y": 2}}, "brain": {"vision": False}})
    Api().unpin()
    assert read_config(sapo_home) == {"pc": {"skin": "noche"}, "brain": {"vision": False}}


def test_api_set_reports_errors(sapo_home):
    api = Api()
    assert api.set("pc", "energy", "Travieso") == {"ok": True, "value": "Travieso"}
    bad = api.set("pc", "energy", "Turbo")
    assert bad["ok"] is False and bad["error"]
    assert api.set("nada", "x", 1)["ok"] is False


def test_dpapi_round_trip():
    raw = "AIzaSy-prueba-ñ-🐸".encode("utf-8")
    blob = secrets.protect(raw)
    assert blob != raw and raw not in blob
    assert secrets.unprotect(blob) == raw


def test_secret_file_is_encrypted_and_preserved(sapo_home):
    (sapo_home / "secrets.json").write_text(json.dumps({"otro": "x"}), "utf-8")
    secrets.save_key("  AIzaFAKEkey1234567890  ")
    text = (sapo_home / "secrets.json").read_text("utf-8")
    assert "AIzaFAKEkey1234567890" not in text
    assert json.loads(text)["otro"] == "x"
    assert secrets.load_key() == "AIzaFAKEkey1234567890"
    assert "gemini_api_key" not in (sapo_home / "config.json").read_text("utf-8") if (sapo_home / "config.json").exists() else True
    secrets.delete_key()
    assert secrets.load_key() is None
    assert json.loads((sapo_home / "secrets.json").read_text("utf-8")) == {"otro": "x"}


def test_secret_rejects_garbage(sapo_home):
    with pytest.raises(ValueError):
        secrets.save_key("con espacios dentro")
    (sapo_home / "secrets.json").write_text(json.dumps({"gemini_api_key": "bm8gZXMgZHBhcGk="}), "utf-8")
    assert secrets.load_key() is None


def test_test_key_never_leaks(monkeypatch):
    monkeypatch.setattr(gemini, "test_key", lambda key: (False, f"error con {key}"))
    secrets.save_key("AIzaSECRETO")
    r = Api().test_key()
    assert r["ok"] is False and "AIzaSECRETO" not in r["message"]


def test_registry_run_value(run_key):
    assert autostart.get(run_key) is None
    autostart.set('"C:\\Sapo\\Sapo.exe" --quieto', run_key)
    assert autostart.get(run_key) == '"C:\\Sapo\\Sapo.exe" --quieto'
    autostart.remove(run_key)
    assert autostart.get(run_key) is None
    autostart.remove(run_key)


def test_api_autostart(sapo_home, run_key, tmp_path):
    exe = tmp_path / "Sapo.exe"
    exe.write_bytes(b"MZ")
    api = Api(run_key=run_key)
    bad = api.set_autostart(True, '"C:\\no\\existe\\Sapo.exe"')
    assert bad["ok"] is False and autostart.get(run_key) is None
    ok = api.set_autostart(True, f'"{exe}" --tray')
    assert ok["ok"] and ok["startup"]["enabled"] and autostart.get(run_key) == f'"{exe}" --tray'
    assert read_config(sapo_home)["startup"] == {"command": f'"{exe}" --tray', "autostart": True}
    off = api.set_autostart(False, f'"{exe}" --tray')
    assert off["ok"] and not off["startup"]["enabled"] and autostart.get(run_key) is None
    assert read_config(sapo_home)["startup"]["autostart"] is False


def test_command_parsing(tmp_path):
    exe = tmp_path / "con espacio" / "Sapo.exe"
    exe.parent.mkdir()
    exe.write_bytes(b"MZ")
    assert autostart.command_ok(f'"{exe}" --x')
    assert not autostart.command_ok("")
    assert not autostart.command_ok(str(exe))
