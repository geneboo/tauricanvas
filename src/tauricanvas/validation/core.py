from pathlib import Path
import json
import re

REQUIRED = [
    'Cargo.toml',
    'desktop/package.json',
    'desktop/src-tauri/Cargo.toml',
    'desktop/src-tauri/tauri.conf.json',
    'desktop/src-tauri/capabilities/default.json',
    '.tauricanvas/contract.json',
]


def validate(root: Path) -> list[str]:
    issues: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).is_file():
            issues.append(f'TC-PATH-300 missing {rel}')
    try:
        contract = json.loads((root / '.tauricanvas/contract.json').read_text(encoding='utf-8'))
        backend = (root / 'desktop/src-tauri/src/generated/mod.rs').read_text(encoding='utf-8')
        frontend = (root / 'desktop/src/generated/api.ts').read_text(encoding='utf-8')
        for action in contract['actions']:
            cmd = action['command']
            if not re.search(rf'\bfn\s+{re.escape(cmd)}\s*\(', backend):
                issues.append(f'TC-TAURI-501 missing Rust command: {cmd}')
            if not re.search(rf"""['"]{re.escape(cmd)}['"]""", frontend):
                issues.append(f'TC-TAURI-502 missing TS binding: {cmd}')
    except Exception as e:
        issues.append(f'TC-GEN-402 {e}')
    return sorted(issues)
