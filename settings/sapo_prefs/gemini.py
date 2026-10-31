import json
import urllib.error
import urllib.request

URL = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000"


def test_key(key: str, timeout: float = 12) -> tuple[bool, str]:
    req = urllib.request.Request(URL, headers={"x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403):
            return False, "Google dice que la key no es válida o no tiene permiso."
        if e.code == 429:
            return False, "La key funciona pero llegó al límite gratis; espera un rato."
        return False, f"Google respondió con un error ({e.code})."
    except (urllib.error.URLError, TimeoutError, OSError):
        return False, "No pude conectar con Google. Revisa tu internet."
    except ValueError:
        return False, "Respuesta rara de Google."
    models = [m.get("name", "") for m in data.get("models", []) if isinstance(m, dict)]
    flash = any("flash" in m for m in models)
    return True, f"¡Funciona! {len(models)} modelos disponibles" + ("." if flash else ", pero no veo Gemini Flash.")
