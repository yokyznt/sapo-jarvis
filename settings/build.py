import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
BUILD = HERE / "build"
DIST = HERE / "dist"
NAME = "SapoPreferencias"


def frog(size: int = 1024) -> Image.Image:
    s = size / 256
    body = Image.new("L", (size, size), 0)
    d = ImageDraw.Draw(body)
    d.rounded_rectangle([20 * s, 70 * s, 236 * s, 226 * s], radius=74 * s, fill=255)
    d.ellipse([34 * s, 40 * s, 120 * s, 126 * s], fill=255)
    d.ellipse([136 * s, 40 * s, 222 * s, 126 * s], fill=255)
    grad = Image.linear_gradient("L").rotate(-40, expand=False).resize((size, size))
    top, bottom = (199, 238, 171), (137, 181, 110)
    color = Image.merge("RGB", [g.point(lambda v, a=a, b=b: int(a + (b - a) * v / 255)) for g, a, b in zip([grad] * 3, top, bottom)])
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).ellipse([40 * s, 214 * s, 216 * s, 240 * s], fill=(0, 0, 0, 50))
    img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(6 * s)))
    img.paste(color, (0, 0), body)
    rim = body.filter(ImageFilter.GaussianBlur(14 * s))
    edge = Image.new("RGBA", (size, size), (90, 130, 70, 0))
    edge.putalpha(Image.eval(Image.composite(Image.eval(rim, lambda v: 255 - v), Image.new("L", (size, size), 0), body), lambda v: min(150, v)))
    img.alpha_composite(edge)
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([150 * s, 76 * s, 206 * s, 122 * s], fill=(255, 255, 255, 110))
    img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(10 * s)))
    d = ImageDraw.Draw(img)
    for cx in (80, 176):
        d.rounded_rectangle([(cx - 15) * s, 70 * s, (cx + 15) * s, 116 * s], radius=15 * s, fill=(26, 20, 18, 255))
        d.ellipse([(cx - 2) * s, 76 * s, (cx + 10) * s, 88 * s], fill=(255, 255, 255, 255))
    cheeks = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    cd = ImageDraw.Draw(cheeks)
    cd.ellipse([42 * s, 124 * s, 82 * s, 146 * s], fill=(247, 163, 160, 220))
    cd.ellipse([174 * s, 124 * s, 214 * s, 146 * s], fill=(247, 163, 160, 220))
    img.alpha_composite(cheeks.filter(ImageFilter.GaussianBlur(2 * s)))
    d.arc([110 * s, 112 * s, 146 * s, 140 * s], start=20, end=160, fill=(122, 34, 54, 255), width=int(7 * s))
    return img


def make_icon(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    big = frog().resize((256, 256), Image.LANCZOS)
    big.save(path, sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)])
    big.save(path.with_suffix(".png"))


def main() -> None:
    icon = BUILD / "icon.ico"
    make_icon(icon)
    shutil.rmtree(DIST / NAME, ignore_errors=True)
    sep = ";"
    cmd = [
        sys.executable, "-m", "PyInstaller", str(HERE / "run.py"),
        "--name", NAME, "--onedir", "--windowed", "--noconfirm", "--clean",
        "--icon", str(icon),
        "--distpath", str(DIST), "--workpath", str(BUILD / "pyi"), "--specpath", str(BUILD),
        "--add-data", f"{HERE / 'sapo_prefs' / 'ui'}{sep}sapo_prefs/ui",
        "--add-data", f"{REPO / 'pc' / 'skins.json'}{sep}data/pc",
        "--add-data", f"{REPO / 'assets' / 'skins'}{sep}data/assets/skins",
        "--collect-data", "sounddevice",
        "--collect-binaries", "_sounddevice_data",
        "--exclude-module", "tkinter",
        "--exclude-module", "PIL",
        "--exclude-module", "pytest",
    ]
    subprocess.run(cmd, check=True, cwd=HERE)
    exe = DIST / NAME / f"{NAME}.exe"
    total = sum(f.stat().st_size for f in (DIST / NAME).rglob("*") if f.is_file())
    print(f"{exe}  ({total / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
