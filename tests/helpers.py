import subprocess
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "xime-index-submit"


def run_cli(args, cwd=None):
    return subprocess.run(args, cwd=cwd, text=True, capture_output=True)
