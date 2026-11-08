"""Build and execute an installed wheel through official Pyxel packaging.

Run in a non-editable wheel installation. Output must be a new directory.
This checks a frozen runtime on the build host, not a clean OS or Steam.
"""

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import time
import zlib


def probe_environment(output: Path, saves: Path) -> dict[str, str]:
    env = os.environ.copy()
    for name in tuple(env):
        if name.startswith("PYTHON") or name in (
            "VIRTUAL_ENV",
            "LD_LIBRARY_PATH",
            "LD_LIBRARY_PATH_ORIG",
            "LD_PRELOAD",
            "LD_AUDIT",
        ):
            env.pop(name, None)
    # The executable is launched by absolute path, never via a Python launcher.
    env["PATH"] = (
        os.environ.get("SystemRoot", "C:/Windows")
        if os.name == "nt"
        else "/usr/bin:/bin"
    )
    env.update(
        LOOM_PROBE_OUTPUT=str(output),
        LOOM_PROBE_SAVES=str(saves),
        SDL_AUDIODRIVER="dummy",
    )
    return env


def validate_linux_bundle(bundle: Path) -> None:
    """Require SDL itself in the artifact, not just on the build host."""
    root = bundle.resolve()
    candidates = list(root.rglob("libSDL2-2.0.so.0"))
    if not any(
        path.is_file()
        and path.resolve().is_relative_to(root)
        and path.stat().st_size > 0
        for path in candidates
    ):
        raise RuntimeError(
            "Linux bundle is missing libSDL2-2.0.so.0; install SDL2 on the "
            "build host before app2exe (Ubuntu: libsdl2-2.0-0)"
        )


def png_pixel() -> bytes:
    def chunk(kind, data):
        return (
            struct.pack("!I", len(data))
            + kind
            + data
            + struct.pack("!I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack("!2I5B", 1, 1, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x4d"))
        + chunk(b"IEND", b"")
    )


def validate_report(report, run, executable, source):
    if (
        not report["frozen"]
        or report["runs"] != run
        or report["pixel"] != 8
        or report["rendered_pixel"] != 8
    ):
        raise RuntimeError(f"Frozen resource/save contract failed: {report}")
    if Path(report["executable"]).resolve() != executable.resolve():
        raise RuntimeError("Probe did not run the generated executable")
    expected = [
        "start.enter",
        "start.update",
        "start.exit",
        "finish.enter",
        "finish.update",
        "finish.exit",
    ]
    if report["events"] != expected:
        raise RuntimeError("Scene lifecycle contract failed")
    bundle_root = Path(report["bundle_root"]).resolve()
    if not bundle_root.is_relative_to(executable.parent.resolve()):
        raise RuntimeError("Frozen runtime root is outside the relocated bundle")
    if not Path(report["pyxel_origin"]).resolve().is_relative_to(bundle_root):
        raise RuntimeError("Pyxel was not imported from the frozen bundle")
    game_root = Path(report["game_origin"]).resolve().parent
    if game_root.is_relative_to(source) or game_root.is_relative_to(
        executable.parents[2]
    ):
        raise RuntimeError("Game leaked from the source/build tree")
    if Path(report["loom_origin"]).resolve() != game_root / "loom/__init__.py":
        raise RuntimeError("Loom was not imported beside the extracted game")
    if Path(report["asset_origin"]).resolve() != game_root / "assets/pixel.png":
        raise RuntimeError("Asset was not loaded beside the extracted game")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    import loom

    installed = Path(loom.__file__).resolve().parent
    if installed.is_relative_to(root):
        raise SystemExit(
            "Install the wheel first; editable/source imports are not accepted"
        )
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    stage = output / "loom-probe"
    stage.mkdir()
    shutil.copytree(
        installed, stage / "loom", ignore=shutil.ignore_patterns("__pycache__", "*.pyc")
    )
    shutil.copy2(root / "tests/fixtures/bundle_contract.py", stage / "main.py")
    (stage / "assets").mkdir()
    (stage / "assets/pixel.png").write_bytes(png_pixel())
    started = time.perf_counter()
    for command in (
        [sys.executable, "-m", "pyxel", "package", str(stage), str(stage / "main.py")],
        [sys.executable, "-m", "pyxel", "app2exe", str(output / "loom-probe.pyxapp")],
    ):
        subprocess.run(command, cwd=output, check=True, timeout=600)
    original = output / "dist/loom-probe"
    bundle = output / "relocated/loom-probe"
    shutil.copytree(original, bundle)
    original.rename(output / "original-bundle-not-used")
    stage.rename(output / "original-stage-not-used")
    if sys.platform.startswith("linux"):
        validate_linux_bundle(bundle)
    executable = bundle / ("loom-probe.exe" if os.name == "nt" else "loom-probe")
    cwd = output / "unrelated-working-directory"
    cwd.mkdir()
    reports = []
    for run in (1, 2):
        result_file = output / f"run-{run}.json"
        subprocess.run(
            [str(executable)],
            cwd=cwd,
            env=probe_environment(result_file, output / "saves"),
            check=True,
            timeout=30,
        )
        report = json.loads(result_file.read_text(encoding="utf-8"))
        validate_report(report, run, executable, root)
        reports.append(report)
    metrics = {
        "platform": platform.platform(),
        "versions": {
            name: importlib.metadata.version(name)
            for name in ("loom-pyxel", "pyxel", "pyinstaller")
        },
        "bundle_bytes": sum(p.stat().st_size for p in bundle.rglob("*") if p.is_file()),
        "elapsed_seconds": time.perf_counter() - started,
        "runs": reports,
        "scope": "Frozen runtime on build host; not clean OS, physical controller, or Steam verification",
    }
    (output / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
