"""Documentation configuration; imports the local source without starting Pyxel."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

project = "Loom"
extensions = ["sphinx.ext.autodoc"]
html_theme = "shibuya"
html_theme_options = {
    "github_url": "https://github.com/viasnake/loom",
}
html_show_sourcelink = False
html_show_sphinx = False
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
autodoc_member_order = "bysource"
autodoc_typehints = "description"
