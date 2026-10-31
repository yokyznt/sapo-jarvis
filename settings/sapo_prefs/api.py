import os
import subprocess
import threading

from . import __version__, autostart, gemini, phone, secrets, store, system

ALLOWED_URLS = ("https://aistudio.google.com/", "https://github.com/yokyznt/sapo-jarvis", "https://ai.google.dev/")


class Api:
    def __init__(self, run_key: str = autostart.RUN_KEY, run_name: str = autostart.NAME):
        self._run_key = run_key
        self._run_name = run_name
        self._lock = threading.Lock()

    def state(self) -> dict:
        cfg = store.effective()
        return {
            "config": cfg,
            "skins": system.skins(),
            "monitors": system.monitors(),
            "devices": system.audio_devices(),
            "voices": {"local": system.LOCAL_VOICES, "gemini": system.GEMINI_VOICES},
            "has_key": secrets.has_key(),
            "env_key": bool(os.environ.get("GEMINI_API_KEY")),
            "startup": self._startup(cfg),
            "phone": phone.state(),
            "about": {"version": __version__, "home": str(store.home()), "config": str(store.config_path())},
        }

    def _startup(self, cfg: dict | None = None) -> dict:
        cfg = cfg or store.effective()
        reg = autostart.get(self._run_key, self._run_name)
        command = cfg["startup"]["command"] or reg or autostart.default_command()
        return {"enabled": reg is not None, "command": command, "available": autostart.command_ok(command), "found": autostart.find_sapo_exe() is not None}

    def set(self, section: str, key: str, value) -> dict:
        try:
            with self._lock:
                return {"ok": True, "value": store.update(section, key, value)}
        except (KeyError, ValueError) as e:
            return {"ok": False, "error": str(e).strip("'")}
        except OSError:
            return {"ok": False, "error": "No pude guardar el archivo de configuración."}

    def pin(self):
        return store.effective()["pc"]["pin"]

    def unpin(self) -> dict:
        try:
            with self._lock:
                store.remove("pc", "pin")
            return {"ok": True}
        except OSError:
            return {"ok": False, "error": "No pude guardar el archivo de configuración."}

    def save_key(self, key: str) -> dict:
        try:
            secrets.save_key(key or "")
        except ValueError:
            return {"ok": False, "error": "Eso no parece una key. Cópiala completa desde AI Studio."}
        except OSError:
            return {"ok": False, "error": "Windows no pudo cifrar o guardar la key."}
        return {"ok": True, "has_key": True}

    def delete_key(self) -> dict:
        try:
            secrets.delete_key()
        except OSError:
            return {"ok": False, "error": "No pude borrar la key."}
        return {"ok": True, "has_key": False}

    def test_key(self) -> dict:
        key = secrets.load_key() or os.environ.get("GEMINI_API_KEY")
        if not key:
            return {"ok": False, "message": "Primero pega una key."}
        ok, message = gemini.test_key(key)
        return {"ok": ok, "message": message.replace(key, "•••")}

    def set_autostart(self, enabled: bool, command: str) -> dict:
        try:
            command = store.validate("startup", "command", command)
        except ValueError as e:
            return {"ok": False, "error": str(e), "startup": self._startup()}
        try:
            with self._lock:
                store.update("startup", "command", command)
                if enabled:
                    if not autostart.command_ok(command):
                        store.update("startup", "autostart", False)
                        autostart.remove(self._run_key, self._run_name)
                        return {"ok": False, "error": "No encuentro ese programa. Revisa la ruta.", "startup": self._startup()}
                    autostart.set(command, self._run_key, self._run_name)
                else:
                    autostart.remove(self._run_key, self._run_name)
                store.update("startup", "autostart", bool(enabled))
        except OSError:
            return {"ok": False, "error": "Windows no me dejó cambiar el inicio automático.", "startup": self._startup()}
        return {"ok": True, "startup": self._startup()}

    def phone_state(self) -> dict:
        return phone.state()

    def phone_pair(self) -> dict:
        try:
            with self._lock:
                code = phone.new_code()
        except OSError:
            return {"ok": False, "error": "Windows no pudo cifrar o guardar el código."}
        return {"ok": True, **code, "ips": phone.local_ips(), "port": phone.PORT}

    def phone_cancel(self) -> dict:
        try:
            with self._lock:
                phone.cancel_code()
        except OSError:
            return {"ok": False, "error": "No pude cancelar el código."}
        return {"ok": True}

    def phone_revoke(self, tid: str) -> dict:
        try:
            with self._lock:
                found = phone.revoke(tid)
        except OSError:
            return {"ok": False, "error": "No pude revocar ese celular."}
        if not found:
            return {"ok": False, "error": "Ese celular ya no estaba vinculado.", "phone": phone.state()}
        return {"ok": True, "phone": phone.state()}

    def devices(self) -> dict:
        return system.audio_devices()

    def open_url(self, url: str) -> bool:
        if isinstance(url, str) and url.startswith(ALLOWED_URLS):
            os.startfile(url)
            return True
        return False

    def open_folder(self) -> bool:
        home = store.home()
        home.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["explorer", str(home)])
        return True
