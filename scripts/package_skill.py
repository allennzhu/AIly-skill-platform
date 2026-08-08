#!/usr/bin/env python3
"""Package an Aily Skill directory into a .skill zip archive."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path


def _read_skill_name(skill_md: Path) -> str:
    text = skill_md.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        raise ValueError("SKILL.md missing YAML frontmatter")
    name_m = re.search(r"^name:\s*[\"']?([^\"'\n]+)[\"']?\s*$", m.group(1), re.M)
    if not name_m:
        raise ValueError("SKILL.md frontmatter missing name")
    return name_m.group(1).strip()


def package_skill(src_dir: Path, out_dir: Path) -> Path:
    src_dir = src_dir.resolve()
    skill_md = src_dir / "SKILL.md"
    client = src_dir / "scripts" / "api_client.py"
    if not skill_md.is_file():
        raise FileNotFoundError("SKILL.md not found")
    if not client.is_file():
        raise FileNotFoundError("scripts/api_client.py not found")
    name = _read_skill_name(skill_md)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{name}.skill"
    include_dirs = ["scripts", "references"]
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(skill_md, arcname="SKILL.md")
        for d in include_dirs:
            base = src_dir / d
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if not path.is_file():
                    continue
                if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
                    continue
                zf.write(
                    path,
                    arcname=str(path.relative_to(src_dir)).replace("\\", "/"),
                )
    return out_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("src_dir")
    parser.add_argument("out_dir")
    args = parser.parse_args(argv)
    try:
        path = package_skill(Path(args.src_dir), Path(args.out_dir))
        print(path)
        return 0
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
