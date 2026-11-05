from pathlib import Path
import subprocess

from app.core.server import *

if __name__ == "__main__":
    ui_directory = Path(__file__).resolve().parent / "app" / "ui"
    subprocess.run(["npm", "run", "build"], cwd=ui_directory, check=True)
    app.run(host="0.0.0.0", port=8000, debug=False)