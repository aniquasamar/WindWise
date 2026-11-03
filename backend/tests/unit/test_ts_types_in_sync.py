"""The generated TypeScript types must match the backend schemas (run scripts/gen_ts_types.py to fix)."""
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
TYPES = ROOT / "frontend" / "src" / "api" / "types.ts"


@pytest.mark.skipif(not TYPES.exists(), reason="frontend types not generated yet")
def test_generated_types_are_up_to_date():
    spec = importlib.util.spec_from_file_location("gen_ts_types", ROOT / "scripts" / "gen_ts_types.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Compare ignoring trailing whitespace: editors differ on the final newline, and that is harmless.
    assert TYPES.read_text(encoding="utf-8").rstrip() == mod.generate().rstrip(), "run: python scripts/gen_ts_types.py"