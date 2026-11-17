"""Dataset bytes are reproducible across host and input line endings."""
import shutil
from pathlib import Path

import pytest

from lab9 import evalset

pytestmark = pytest.mark.student


def test_builds_use_lf_and_ignore_source_line_endings(tmp_path, monkeypatch):
    root = Path(__file__).resolve().parents[1]
    for relative in ("data/public_claims.jsonl", "data/eval/adversarial_v2.json", "config/fm_map.yaml"):
        dest = tmp_path / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / relative, dest)
    monkeypatch.chdir(tmp_path)
    source = tmp_path / "data/public_claims.jsonl"
    outputs = [tmp_path / evalset.ITEMS, tmp_path / evalset.ITEMS_V2]
    expected = None
    for newline in (b"\n", b"\r\n"):
        source.write_bytes(source.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", newline))
        evalset.build()
        evalset.build_v2()
        result = [path.read_bytes() for path in outputs]
        assert all(data.endswith(b"\n") and b"\r" not in data for data in result)
        assert all(evalset.load_jsonl(path) for path in outputs)
        if expected is not None:
            assert result == expected
        expected = result
