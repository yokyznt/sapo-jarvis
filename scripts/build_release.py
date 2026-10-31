import argparse
import os
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PC = REPO / "pc"
BUILD = REPO / "build"
APP = BUILD / "Sapo"
DIST = REPO / "dist"
INSTALLER = REPO / "installer"
PREFS = REPO / "settings" / "dist" / "SapoPreferencias"
ICON_SVG = REPO / "assets" / "skins" / "clasico.svg"
SIZES = (16, 24, 32, 48, 64, 128, 256)
LIMIT = 1.5e9


def version() -> str:
    text = (PC / "export_presets.cfg").read_text(encoding="utf-8")
    m = re.search(r'application/product_version="(\d+)\.(\d+)\.(\d+)', text)
    return ".".join(m.groups()) if m else "0.0.0"


def find_godot() -> Path:
    env = os.environ.get("GODOT")
    if env:
        return Path(env)
    root = Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Packages"
    hits = sorted(root.glob("GodotEngine.GodotEngine.Mono_*/Godot_v4*_mono_win64/Godot_v4*_mono_win64_console.exe"))
    if not hits:
        sys.exit("No encontré Godot 4 mono (winget install GodotEngine.GodotEngine.Mono) ni la variable GODOT")
    return hits[-1]


def find_iscc() -> Path:
    for base in (os.environ.get("LOCALAPPDATA", ""), os.environ.get("ProgramFiles(x86)", ""), os.environ.get("ProgramFiles", "")):
        for p in (Path(base) / "Programs" / "Inno Setup 6" / "ISCC.exe", Path(base) / "Inno Setup 6" / "ISCC.exe"):
            if p.is_file():
                return p
    found = shutil.which("ISCC")
    if not found:
        sys.exit("No encontré ISCC.exe (winget install JRSoftware.InnoSetup)")
    return Path(found)


def run(cmd: list, **kw) -> None:
    print(">", " ".join(str(c) for c in cmd), flush=True)
    subprocess.run([str(c) for c in cmd], check=True, **kw)


def size_of(path: Path) -> int:
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else path.stat().st_size


def write_ico(pngs: list[tuple[int, bytes]], out: Path) -> None:
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, data in pngs:
        dim = 0 if size >= 256 else size
        entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32, len(data), offset + len(blobs))
        blobs += data
    out.write_bytes(head + entries + blobs)


def icons(godot: Path) -> None:
    work = BUILD / "icon"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    run([godot, "--headless", "--script", REPO / "scripts" / "svg_png.gd", "--", ICON_SVG, work, *SIZES], cwd=work)
    pngs = [(s, (work / f"icon_{s}.png").read_bytes()) for s in SIZES]
    write_ico(pngs, PC / "icon.ico")
    shutil.copyfile(work / "icon_256.png", PC / "icon.png")
    print(f"icono: {PC / 'icon.ico'} ({(PC / 'icon.ico').stat().st_size} B)")


def export_godot(godot: Path) -> None:
    APP.mkdir(parents=True, exist_ok=True)
    (APP / "Sapo.exe").unlink(missing_ok=True)
    shutil.rmtree(APP / "data_Sapo_windows_x86_64", ignore_errors=True)
    run([godot, "--headless", "--path", PC, "--import"])
    run([godot, "--headless", "--path", PC, "--export-release", "Windows Desktop", APP / "Sapo.exe"])
    if not (APP / "Sapo.exe").is_file() or not (APP / "data_Sapo_windows_x86_64" / "Sapo.dll").is_file():
        sys.exit("La exportación de Godot falló (falta Sapo.exe o Sapo.dll); revisa: dotnet build pc/Sapo.csproj")
    print(f"Sapo.exe: {size_of(APP / 'Sapo.exe') / 1e6:.1f} MB")


def build_core() -> None:
    work, out = BUILD / "pyi-work", BUILD / "pyi-dist"
    shutil.rmtree(out, ignore_errors=True)
    run(["uv", "run", "--project", REPO / "brain", "--frozen", "--with", "pyinstaller", "pyinstaller", INSTALLER / "core.spec", "--noconfirm", "--clean", "--distpath", out, "--workpath", work], cwd=INSTALLER)
    dest = APP / "core"
    shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(out / "core", dest)
    print(f"core: {size_of(dest) / 1e6:.1f} MB")


def copy_prefs() -> None:
    exe = PREFS / "SapoPreferencias.exe"
    if not exe.is_file():
        run(["uv", "run", "--project", REPO / "settings", "--frozen", "--with", "pyinstaller", "python", REPO / "settings" / "build.py"])
    shutil.copy2(exe, APP / exe.name)
    shutil.copytree(PREFS / "_internal", APP / "_internal", dirs_exist_ok=True)
    print(f"Preferencias: {size_of(PREFS) / 1e6:.1f} MB")


def compile_setup(ver: str) -> Path:
    DIST.mkdir(exist_ok=True)
    run([find_iscc(), f"/DAppVersion={ver}", f"/DSourceDir={APP}", f"/DOutDir={DIST}", INSTALLER / "sapo.iss"])
    setup = DIST / f"Sapo-Setup-{ver}.exe"
    print(f"instalador: {setup} ({setup.stat().st_size / 1e6:.1f} MB)")
    return setup


def main() -> None:
    steps = ["icon", "godot", "core", "prefs", "setup"]
    parser = argparse.ArgumentParser(description="Construye Sapo.exe, el cerebro empaquetado y el instalador")
    parser.add_argument("--solo", nargs="*", choices=steps, help="pasos a correr (por defecto todos)")
    args = parser.parse_args()
    todo = args.solo or steps
    ver = version()
    godot = find_godot()
    if "icon" in todo:
        icons(godot)
    if "godot" in todo:
        export_godot(godot)
    if "core" in todo:
        build_core()
    if "prefs" in todo:
        copy_prefs()
    total = size_of(APP) if APP.is_dir() else 0
    print(f"build/Sapo: {total / 1e6:.1f} MB")
    if total > LIMIT:
        print("aviso: build/Sapo pasa de 1.5 GB")
    if "setup" in todo:
        compile_setup(ver)


if __name__ == "__main__":
    main()
