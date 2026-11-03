from pathlib import Path
import os
import sys

root = Path(__file__).resolve().parents[2]
python = root / ".venv/bin/python"
if python.exists() and Path(sys.prefix).resolve() != (root / ".venv").resolve():
    os.execv(str(python), [str(python), str(Path(__file__).resolve()), *sys.argv[1:]])
sys.path.insert(0, str(root))
from avoidance.bridge import main
main()
