from pathlib import Path
import zipfile


def test_package_skill_creates_archive(tmp_path):
    import sys

    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "scripts"))
    import package_skill

    src = tmp_path / "skill"
    (src / "scripts").mkdir(parents=True)
    (src / "references").mkdir()
    (src / "SKILL.md").write_text(
        "---\nname: pm-platform-api\nlabel: test\ndescription: d\n---\n\nbody\n",
        encoding="utf-8",
    )
    (src / "scripts" / "api_client.py").write_text("# x\n", encoding="utf-8")
    (src / "references" / "api_docs.md").write_text("# docs\n", encoding="utf-8")
    out = tmp_path / "out"
    path = package_skill.package_skill(src, out)
    assert path.exists()
    assert path.suffix == ".skill"
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        assert any(n.endswith("SKILL.md") for n in names)
        assert "scripts/api_client.py" in names
        assert "references/api_docs.md" in names
