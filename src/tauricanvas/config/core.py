from pathlib import Path

from ruamel.yaml import YAML

from tauricanvas.cargo.core import metadata, primary_package
from tauricanvas.inspection.rust import inspect
from tauricanvas.models import Config
from tauricanvas.utilities.fs import snake

y = YAML()


def load(path: Path) -> Config:
    cfg = Config.model_validate(y.load(path.read_text(encoding='utf-8')))
    p = Path(cfg.source.manifest)
    if not p.is_absolute():
        cfg.source.manifest = str((path.parent / p).resolve())
    return cfg


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8') as f:
        y.dump(data, f)


def draft(source: Path):
    md = metadata(source)
    pkg = primary_package(md, source)
    pkg_name = pkg['name']
    report = inspect(source)

    actions = []
    used_ids: set[str] = set()
    for f in report.functions:
        if not f.public:
            continue
        if f.classification in ('unsupported_signature', 'dangerous_not_enabled'):
            continue
        base_id = snake(f.name)
        aid = base_id
        n = 2
        while aid in used_ids:
            aid = f'{base_id}_{n}'
            n += 1
        used_ids.add(aid)
        actions.append({
            'id': aid,
            'enabled': f.classification == 'ready_existing_tauri_command',
            'source': {'crate': f.package, 'function': f'{f.module}::{f.name}'},
            'title': base_id.replace('_', ' ').title(),
            'safety': 'read_only',
            'confirmation': False,
            'presentation': {
                'input': 'form' if f.parameters else 'none',
                'output': 'data_grid' if 'Vec<' in f.return_type else 'details',
                'route': '/' + base_id.replace('_', '-'),
            },
        })
    return {
        'schema_version': 1,
        'project': {
            'name': pkg_name.replace('-', ' ').title(),
            'identifier': 'com.tauricanvas.' + snake(pkg_name),
            'version': '0.1.0',
            'description': 'Generated desktop interface',
        },
        'source': {'manifest': str(Path(report.manifest).resolve()), 'package': pkg_name},
        'ui': {'menus': True, 'theme_toggle': True},
        'engine': {'mode': 'copy', 'target': 'crates/app-engine'},
        'actions': actions,
    }
