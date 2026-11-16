"""Put the repository root on sys.path so tests can import the pipeline module.

Without this, `pytest tests/test_rag_gate.py` cannot `import rag_pipeline`,
because pytest only adds the test file's own directory to sys.path.
"""

import sys
from pathlib import Path

ROOT = str(Path(__file__).parent.resolve())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
