"""
Root conftest — adds back-end/ to sys.path so tests can import from api/, core/, config/.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "back-end"))
