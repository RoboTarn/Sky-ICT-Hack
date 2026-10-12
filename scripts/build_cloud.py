"""Promote Vite assets to the Vercel CDN; FastAPI serves SPA entry paths."""
from pathlib import Path
from shutil import copytree

root = Path(__file__).resolve().parent.parent
copytree(root / 'dist' / 'assets', root / 'public' / 'assets', dirs_exist_ok=True)
