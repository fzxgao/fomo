import sys
from pathlib import Path

# Ensure package root is importable when running tests directly
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fomo.io.mrcio import list_mrcs

def test_list_mrcs_case_insensitive(tmp_path):
    # Create files with mixed-case extensions
    files = [
        tmp_path / "A.MRC",
        tmp_path / "b.mrcs",
        tmp_path / "C.REC",
    ]
    for f in files:
        f.write_bytes(b"test")
    result = set(list_mrcs(str(tmp_path)))
    expected = {str(f) for f in files}
    assert result == expected
