import sys
from pathlib import Path


# Ensure project root is on sys.path so imports like `backend.app...` work when running pytest
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


