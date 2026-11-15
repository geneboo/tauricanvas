from pathlib import Path
import shutil

import pytest

pytestmark = pytest.mark.skipif(
    shutil.which('cargo') is None, reason='cargo unavailable on host'
)

FIXTURE = Path(__file__).parent / 'fixtures' / 'simple_records_engine'


def test_inspect_scopes_to_workspace():
    from tauricanvas.inspection.rust import inspect
    r = inspect(FIXTURE)
    # Every function must come from the fixture crate, not a dependency.
    assert r.functions
    assert all(f.package == 'simple-records-engine' for f in r.functions)


def test_draft_uses_real_package_name():
    from tauricanvas.config.core import draft
    cfg = draft(FIXTURE)
    assert cfg['source']['package'] == 'simple-records-engine'
    assert cfg['project']['identifier'].startswith('com.tauricanvas.')


def test_generate_end_to_end(tmp_path):
    from tauricanvas.config.core import draft, save
    from tauricanvas.generation.core import generate
    from tauricanvas.validation.core import validate

    cfg_path = tmp_path / 'tauricanvas.yaml'
    dest = tmp_path / 'gen-app'

    config = draft(FIXTURE)
    for action in config['actions']:
        action['enabled'] = True
    assert config['actions'], 'fixture must produce at least one action'
    save(cfg_path, config)

    generate(cfg_path, dest)
    assert (dest / '.tauricanvas/contract.json').is_file()
    assert validate(dest) == []

    wrapper = (dest / 'desktop/src-tauri/src/generated/mod.rs').read_text()
    # Typed adapters must call the engine crate, not stub out.
    assert 'app_engine::list_records' in wrapper
    assert 'app_engine::save_record' in wrapper

    backend = (dest / 'desktop/src-tauri/Cargo.toml').read_text()
    assert 'package="simple-records-engine"' in backend
