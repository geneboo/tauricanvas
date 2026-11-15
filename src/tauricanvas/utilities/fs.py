from pathlib import Path
import hashlib
import shutil
import re


def hash_file(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def copy_engine(src: Path, dst: Path) -> None:
    src = src.resolve()
    dst.mkdir(parents=True, exist_ok=True)
    for p in sorted(src.rglob('*')):
        rel = p.relative_to(src)
        if any(x in rel.parts for x in ('target', '.git', '.idea', 'node_modules')):
            continue
        if p.is_symlink() and src not in p.resolve().parents:
            continue
        if p.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
        elif p.is_file():
            (dst / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dst / rel)


def strip_workspace_section(text: str) -> str:
    """Remove the [workspace] table and its subtables from a Cargo.toml."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    skipping = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith('['):
            if stripped == '[workspace]' or stripped.startswith('[workspace.'):
                skipping = True
                continue
            skipping = False
        if not skipping:
            out.append(line)
    return ''.join(out)


def snake(s: str) -> str:
    s = re.sub(r'(?<!^)(?=[A-Z])', '_', s).replace('-', '_').replace(' ', '_')
    return re.sub('[^A-Za-z0-9_]+', '_', s).strip('_').lower()
