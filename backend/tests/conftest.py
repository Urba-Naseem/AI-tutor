import sys
from pathlib import Path

# Force the backend directory into Python's module search path
backend_path = Path(__file__).resolve().parent.parent
if str(backend_path) not in sys.path:
    sys.path.insert(0, str(backend_path))