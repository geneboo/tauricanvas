from pathlib import Path
import json

from tauricanvas.verification.process import run


def manifest(source: Path) -> Path:
    p = source.expanduser().resolve()
    p = p if p.name == 'Cargo.toml' else p / 'Cargo.toml'
    if not p.is_file():
        raise FileNotFoundError(f'TC-CARGO-001 Cargo manifest not found: {p}')
    return p


def metadata(source: Path) -> dict:
    m = manifest(source)
    r = run(['cargo', 'metadata', '--format-version', '1', '--manifest-path', str(m)], m.parent)
    if r.code:
        raise RuntimeError('TC-CARGO-002 cargo metadata failed\n' + r.err)
    return json.loads(r.out)


def primary_package(md: dict, source: Path) -> dict:
    """Return the package whose manifest matches `source`."""
    target = str(manifest(source).resolve())
    for p in md['packages']:
        if str(Path(p.get('manifest_path', '')).resolve()) == target:
            return p
    member_ids = set(md.get('workspace_members') or [])
    if member_ids:
        for p in md['packages']:
            if p['id'] in member_ids:
                return p
    raise RuntimeError(f'TC-CARGO-003 no primary package for {target}')
