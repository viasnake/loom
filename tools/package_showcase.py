"""Stage only the sample and runtime package, then invoke official Pyxel packaging."""

from pathlib import Path
import shutil
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
stage = root / "build" / "loom-showcase"
if stage.exists():
    raise SystemExit(
        "build/loom-showcase already exists; use a fresh checkout/build directory"
    )
stage.mkdir(parents=True)
shutil.copytree(
    root / "src" / "loom",
    stage / "loom",
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
)
shutil.copy2(root / "examples" / "showcase.py", stage / "main.py")
(root / "dist").mkdir(exist_ok=True)
subprocess.run(
    [sys.executable, "-m", "pyxel", "package", str(stage), str(stage / "main.py")],
    cwd=root / "dist",
    check=True,
)
print("Packaged showcase; app2exe must run on the target operating system.")
