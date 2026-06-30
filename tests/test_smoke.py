from pathlib import Path


def test_project_layout() -> None:
    root = Path(__file__).resolve().parent.parent
    assert (root / "app").is_dir()
    assert (root / "importers").is_dir()
    assert (root / "models").is_dir()
    assert (root / "data").is_dir()
