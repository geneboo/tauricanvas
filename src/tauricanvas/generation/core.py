from pathlib import Path
import json
import os
import re
import shutil
import tempfile

from tauricanvas.cargo.core import manifest, metadata, primary_package
from tauricanvas.config.core import load
from tauricanvas.contract.core import build
from tauricanvas.inspection.rust import inspect
from tauricanvas.models import ActionContract, Function, Inspection
from tauricanvas.utilities.fs import copy_engine, hash_file, strip_workspace_section
from tauricanvas.validation.core import validate

BUILTIN_TYPES = {
    'String', 'str', 'bool', 'char', 'Self', 'self',
    'u8', 'u16', 'u32', 'u64', 'u128', 'usize',
    'i8', 'i16', 'i32', 'i64', 'i128', 'isize',
    'f32', 'f64',
    'Vec', 'Option', 'Result', 'HashMap', 'BTreeMap', 'HashSet', 'BTreeSet',
    'Box', 'Rc', 'Arc', 'Cell', 'RefCell', 'Mutex', 'RwLock', 'Cow',
    'PathBuf', 'Path', 'Duration', 'SystemTime',
    'IpAddr', 'Ipv4Addr', 'Ipv6Addr', 'SocketAddr',
}


def _write(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s if s.endswith('\n') else s + '\n', encoding='utf-8')


def _camel(s: str) -> str:
    parts = s.split('_')
    return parts[0] + ''.join(p[:1].upper() + p[1:] for p in parts[1:])


def _rust_path_for_type(type_name: str, report: Inspection) -> str | None:
    matches = [t for t in report.types if t.name == type_name]
    if len(matches) != 1:
        return None
    t = matches[0]
    parts = t.identity.split('::')
    if len(parts) < 2:
        return None
    module_parts = parts[1:-1]
    pkg_underscored = t.package.replace('-', '_')
    if not module_parts or module_parts == [pkg_underscored]:
        return f'app_engine::{type_name}'
    return 'app_engine::' + '::'.join(parts[1:])


def _resolve_type_syntax(syntax: str, report: Inspection) -> str | None:
    unresolved: list[str] = []

    def repl(m):
        name = m.group(0)
        if name in BUILTIN_TYPES:
            return name
        path = _rust_path_for_type(name, report)
        if path is None:
            unresolved.append(name)
            return name
        return path

    resolved = re.sub(r'\b[A-Z][A-Za-z0-9_]*\b', repl, syntax)
    return None if unresolved else resolved


def _find_function(action: ActionContract, report: Inspection) -> Function | None:
    for f in report.functions:
        if f.identity == action.source:
            return f
    suffix = action.source.split('::', 1)[-1]
    for f in report.functions:
        if f'{f.module}::{f.name}' == suffix:
            return f
    return None


def _gen_stub(action: ActionContract) -> str:
    return (
        '#[tauri::command]\n'
        f'pub async fn {action.command}() -> Result<serde_json::Value, String> {{\n'
        f'    Err("Adapter required: {action.source}".into())\n'
        '}}\n'
    )


def _gen_typed(action: ActionContract, fn: Function, report: Inspection) -> str | None:
    resolved_params: list[tuple[str, str]] = []
    for p in fn.parameters:
        if p.name in ('self', '_'):
            return None
        resolved = _resolve_type_syntax(p.type_syntax, report)
        if resolved is None:
            return None
        resolved_params.append((p.name, resolved))

    pkg_underscored = fn.package.replace('-', '_')
    fn_path = (f'app_engine::{fn.name}' if fn.module == pkg_underscored
               else f'app_engine::{fn.module}::{fn.name}')

    sig_params = ', '.join(f'{name}: serde_json::Value' for name, _ in resolved_params)
    lines = ['#[tauri::command]']
    lines.append(
        f'pub async fn {action.command}({sig_params}) -> Result<serde_json::Value, String> {{'
    )
    for name, resolved in resolved_params:
        lines.append(
            f'    let {name}: {resolved} = serde_json::from_value({name})'
            '.map_err(|e| e.to_string())?;'
        )
    call_args = ', '.join(name for name, _ in resolved_params)
    call = f'{fn_path}({call_args})'
    if fn.async_:
        call += '.await'
    if action.returns_result:
        lines.append(f'    let result = {call}.map_err(|e| format!("{{:?}}", e))?;')
    else:
        lines.append(f'    let result = {call};')
    lines.append('    serde_json::to_value(result).map_err(|e| e.to_string())')
    lines.append('}')
    return '\n'.join(lines) + '\n'


def _gen_wrapper(action: ActionContract, report: Inspection) -> str:
    fn = _find_function(action, report)
    if fn is None:
        return _gen_stub(action)
    typed = _gen_typed(action, fn, report)
    return typed if typed is not None else _gen_stub(action)


def _gen_ts(action: ActionContract, fn: Function | None) -> str:
    name = action.id
    if fn is None or not fn.parameters:
        return (
            f'export async function {name}(): Promise<unknown> {{\n'
            f"  return invoke<unknown>('{action.command}');\n"
            '}\n'
        )
    usable = [p for p in fn.parameters if p.name not in ('self', '_')]
    args = ', '.join(f'{p.name}: unknown' for p in usable)
    invoke_args = ', '.join(f'{_camel(p.name)}: {p.name}' for p in usable)
    return (
        f'export async function {name}({args}): Promise<unknown> {{\n'
        f"  return invoke<unknown>('{action.command}', {{ {invoke_args} }});\n"
        '}\n'
    )


def generate(config_path: Path, dest: Path) -> Path:
    cfg = load(config_path)
    src_manifest = manifest(Path(cfg.source.manifest))
    md = metadata(Path(cfg.source.manifest))
    primary = primary_package(md, Path(cfg.source.manifest))
    report = inspect(Path(cfg.source.manifest))
    contract = build(cfg, report)

    dest = dest.resolve()
    if dest.exists():
        raise FileExistsError(f'TC-GEN-001 output already exists: {dest}')
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.' + dest.name + '.stage-', dir=dest.parent))

    try:
        (stage / '.tauricanvas').mkdir()
        (stage / 'reports').mkdir()
        _write(stage / '.tauricanvas/contract.json',
               contract.model_dump_json(indent=2) + '\n')
        _write(stage / 'reports/inspection.json',
               report.model_dump_json(indent=2) + '\n')

        # Engine copy (with [workspace] stripped) \u2014 fixes C12
        engine_dst = stage / cfg.engine.target
        copy_engine(src_manifest.parent, engine_dst)
        copied_cargo = engine_dst / 'Cargo.toml'
        if copied_cargo.is_file():
            _write(copied_cargo, strip_workspace_section(copied_cargo.read_text(encoding='utf-8')))

        _write(stage / 'Cargo.toml',
               '[workspace]\n'
               'resolver="2"\n'
               f'members=["crates/xtask","desktop/src-tauri","{cfg.engine.target}"]\n')
        _write(stage / '.cargo/config.toml',
               '[alias]\n'
               'app-doctor="run -p xtask -- doctor"\n'
               'app-check="run -p xtask -- check"\n'
               'app-build="run -p xtask -- build"\n')

        # Backend Cargo.toml \u2014 fixes C2 (use real package name)
        pkg_name = primary['name']
        dep_crate = Path(cfg.engine.target).name.replace('-', '_')
        _write(stage / 'desktop/src-tauri/Cargo.toml',
               '[package]\n'
               'name="tauricanvas-desktop"\n'
               'version="0.1.0"\n'
               'edition="2021"\n'
               '[lib]\n'
               'name="tauricanvas_desktop"\n'
               'crate-type=["lib","cdylib","staticlib"]\n'
               '[build-dependencies]\n'
               'tauri-build="2"\n'
               '[dependencies]\n'
               'tauri="2"\n'
               'serde_json="1"\n'
               f'{dep_crate}={{package="{pkg_name}",path="../../{cfg.engine.target}"}}\n')
        _write(stage / 'desktop/src-tauri/build.rs',
               'fn main() { tauri_build::build(); }\n')

        # Generated Rust commands \u2014 fixes C11 (typed adapters)
        wraps = [_gen_wrapper(a, report) for a in contract.actions]
        names = [f'generated::{a.command}' for a in contract.actions]
        _write(stage / 'desktop/src-tauri/src/generated/mod.rs',
               '\n'.join(wraps) if wraps else '// No actions enabled.\n')
        handler = ', '.join(names)
        lib_rs = ['pub mod generated;']
        if cfg.ui.menus:
            lib_rs.append('use tauri::menu::{MenuBuilder, SubmenuBuilder, MenuItemBuilder, PredefinedMenuItem};')
            lib_rs.append('use tauri::Manager;')
        lib_rs.append('pub fn run() {')
        lib_rs.append('    tauri::Builder::default()')
        if cfg.ui.menus:
            lib_rs.append('        .setup(|app| {')
            lib_rs.append('            let file_menu = SubmenuBuilder::new(app, "File")')
            lib_rs.append('                .item(&PredefinedMenuItem::quit(app, Some("Quit"))?)')
            lib_rs.append('                .build()?;')
            lib_rs.append('            let edit_menu = SubmenuBuilder::new(app, "Edit")')
            lib_rs.append('                .items(&[')
            lib_rs.append('                    &PredefinedMenuItem::undo(app, None)?,')
            lib_rs.append('                    &PredefinedMenuItem::redo(app, None)?,')
            lib_rs.append('                    &PredefinedMenuItem::separator(app)?,')
            lib_rs.append('                    &PredefinedMenuItem::cut(app, None)?,')
            lib_rs.append('                    &PredefinedMenuItem::copy(app, None)?,')
            lib_rs.append('                    &PredefinedMenuItem::paste(app, None)?,')
            lib_rs.append('                ])')
            lib_rs.append('                .build()?;')
            lib_rs.append('            let mut view_menu = SubmenuBuilder::new(app, "View");')
            if cfg.ui.theme_toggle:
                lib_rs.append('            let theme_toggle = MenuItemBuilder::with_id("toggle_theme", "Toggle Light/Dark").build(app)?;')
                lib_rs.append('            view_menu = view_menu.item(&theme_toggle);')
            lib_rs.append('            let view_menu = view_menu.build()?;')
            lib_rs.append('            let help_menu = SubmenuBuilder::new(app, "Help")')
            lib_rs.append('                .item(&MenuItemBuilder::with_id("about", "About").build(app)?)')
            lib_rs.append('                .build()?;')
            lib_rs.append('            let menu = MenuBuilder::new(app)')
            lib_rs.append('                .item(&file_menu)')
            lib_rs.append('                .item(&edit_menu)')
            lib_rs.append('                .item(&view_menu)')
            lib_rs.append('                .item(&help_menu)')
            lib_rs.append('                .build()?;')
            lib_rs.append('            app.set_menu(menu)?;')
            lib_rs.append('            app.on_menu_event(|app, event| {')
            if cfg.ui.theme_toggle:
                lib_rs.append('                if event.id().as_ref() == "toggle_theme" {')
                lib_rs.append('                    if let Some(window) = app.get_webview_window("main") {')
                lib_rs.append('                        let current = window.theme().unwrap_or(tauri::Theme::Light);')
                lib_rs.append('                        let next = match current {')
                lib_rs.append('                            tauri::Theme::Dark => tauri::Theme::Light,')
                lib_rs.append('                            _ => tauri::Theme::Dark,')
                lib_rs.append('                        };')
                lib_rs.append('                        let _ = window.set_theme(Some(next));')
                lib_rs.append('                    }')
                lib_rs.append('                }')
            lib_rs.append('            });')
            lib_rs.append('            Ok(())')
            lib_rs.append('        })')
        lib_rs.append(f'        .invoke_handler(tauri::generate_handler![{handler}])')
        lib_rs.append('        .run(tauri::generate_context!())')
        lib_rs.append('        .expect("Tauri error");')
        lib_rs.append('}')
        _write(stage / 'desktop/src-tauri/src/lib.rs', '\n'.join(lib_rs) + '\n')
        _write(stage / 'desktop/src-tauri/src/main.rs',
               'fn main() { tauricanvas_desktop::run(); }\n')

        _write(stage / 'desktop/src-tauri/capabilities/default.json',
               json.dumps({'identifier': 'default', 'windows': ['main'],
                           'permissions': ['core:default']}, indent=2) + '\n')

        # --- Copy the default icon ---
        # Resolve the path to the assets directory within the installed package
        asset_icon = Path(__file__).parent.parent / 'assets' / 'icons' / 'icon.ico'
        target_icon = stage / 'desktop/src-tauri/icons/icon.ico'
        
        if asset_icon.is_file():
            target_icon.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(asset_icon, target_icon)
        else:
            # Fail gracefully if someone deleted the asset
            print(f"WARNING: Default icon not found at {asset_icon}")
        # ------------------------------

        # Tauri config \u2014 fixes C10 (sensible CSP)
        _write(stage / 'desktop/src-tauri/tauri.conf.json', json.dumps({
            '$schema': 'https://schema.tauri.app/config/2',
            'productName': cfg.project.name,
            'version': cfg.project.version,
            'identifier': cfg.project.identifier,
            'build': {
                'beforeDevCommand': 'npm run dev',
                'beforeBuildCommand': 'npm run build',
                'devUrl': 'http://localhost:1420',
                'frontendDist': '../dist',
            },
            'app': {
                'windows': [{'label': 'main', 'title': cfg.project.name,
                             'width': 1280, 'height': 820}],
                'security': {
                    'csp': "default-src 'self'; "
                           "connect-src ipc: http://ipc.localhost; "
                           "img-src 'self' asset: http://asset.localhost data:; "
                           "style-src 'self' 'unsafe-inline'",
                },
            },
            'bundle': {'active': True},
        }, indent=2) + '\n')

        # Frontend package.json \u2014 fixes C15 (@tauri-apps/cli)
        _write(stage / 'desktop/package.json', json.dumps({
            'name': 'tauricanvas-frontend',
            'private': True,
            'version': '0.1.0',
            'type': 'module',
            'scripts': {
                'dev': 'vite',
                'build': 'tsc && vite build',
                'typecheck': 'tsc --noEmit',
                'tauri': 'tauri',
            },
            'dependencies': {'@tauri-apps/api': '^2.0.0'},
            'devDependencies': {
                'typescript': '^5.6.0',
                'vite': '^6.0.0',
                '@tauri-apps/cli': '^2.0.0',
            },
        }, indent=2) + '\n')
        _write(stage / 'desktop/tsconfig.json', json.dumps({
            'compilerOptions': {
                'target': 'ES2022', 'module': 'ESNext',
                'moduleResolution': 'Bundler',
                'strict': True, 'noEmit': True,
                'lib': ['ES2022', 'DOM'],
            },
            'include': ['src'],
        }, indent=2) + '\n')
        _write(stage / 'desktop/index.html',
               '<!doctype html>\n'
               '<html><body>'
               '<div id="app"></div>'
               '<script type="module" src="/src/main.ts"></script>'
               '</body></html>\n')

        # TS API surface
        api_lines = ["import { invoke } from '@tauri-apps/api/core';", '']
        for action in contract.actions:
            api_lines.append(_gen_ts(action, _find_function(action, report)).rstrip('\n'))
            api_lines.append('')
        _write(stage / 'desktop/src/generated/api.ts',
               '\n'.join(api_lines).rstrip() + '\n')

        # Dynamic UI Generation based on YAML Actions
        ui_html = [f'<h1>{cfg.project.name}</h1>']
        js_lines = [
            "import './style.css';",
            "import * as api from './generated/api';",
            "const app = document.querySelector<HTMLDivElement>('#app')!;"
        ]
        event_listeners = []
        
        for a in contract.actions:
            ui_html.append(f'<div class="card"><h2>{a.title}</h2>')
            
            for p in a.parameters:
                p_name = p['name']
                p_type = p['type'].get('kind')
                if p_type == 'object':
                    struct_name = p['type'].get('name')
                    struct_def = next((t for t in report.types if t.name == struct_name), None)
                    if struct_def and struct_def.fields:
                        ui_html.append(f'<details><summary>Advanced: Paste JSON for {p_name}</summary><textarea id="in_json_{a.id}_{p_name}" style="min-height:100px"></textarea></details>')
                        ui_html.append(f'<div style="border-left: 3px solid #7867ff; padding-left: 1rem; margin-bottom: 1rem;">')
                        ui_html.append(f'<b>{p_name} Fields:</b>')
                        for f in struct_def.fields:
                            f_type = f.type_syntax
                            input_type = "number" if ('f64' in f_type or 'f32' in f_type or 'int' in f_type) else "text"
                            ui_html.append(f'<input id="in_field_{a.id}_{p_name}_{f.name}" type="{input_type}" placeholder="{f.name}" />')
                        ui_html.append('</div>')
                    else:
                        ui_html.append(f'<textarea id="in_{a.id}_{p_name}" placeholder="{p_name} (JSON)"></textarea>')
                elif p_type == 'list':
                    ui_html.append(f'<textarea id="in_{a.id}_{p_name}" placeholder="{p_name} (JSON Array)"></textarea>')
                elif p_type == 'integer' or p_type == 'number':
                    ui_html.append(f'<input id="in_{a.id}_{p_name}" type="number" step="any" placeholder="{p_name}" />')
                else:
                    ui_html.append(f'<input id="in_{a.id}_{p_name}" type="text" placeholder="{p_name}" />')
            
            ui_html.append(f'<button id="btn_{a.id}">Run {a.title}</button>')
            ui_html.append(f'<div id="out_{a.id}" class="output-box"></div></div>')
            
            event_listeners.append(f'document.getElementById("btn_{a.id}")!.onclick = async () => {{')
            event_listeners.append(f'  try {{')
            
            args = []
            for p in a.parameters:
                p_name = p['name']
                p_type = p['type'].get('kind')
                
                if p_type == 'object':
                    struct_name = p['type'].get('name')
                    struct_def = next((t for t in report.types if t.name == struct_name), None)
                    if struct_def and struct_def.fields:
                        event_listeners.append(f'    const jsonStr = (document.getElementById("in_json_{a.id}_{p_name}") as HTMLTextAreaElement).value.trim();')
                        event_listeners.append(f'    let val = null;')
                        event_listeners.append(f'    if (jsonStr) {{')
                        event_listeners.append(f'      val = JSON.parse(jsonStr);')
                        event_listeners.append(f'    }} else {{')
                        event_listeners.append(f'      val = {{')
                        for f in struct_def.fields:
                            val_expr = f'(document.getElementById("in_field_{a.id}_{p_name}_{f.name}") as HTMLInputElement).value'
                            if ('f64' in f.type_syntax or 'f32' in f.type_syntax):
                                val_expr = f'parseFloat({val_expr})'
                            elif ('int' in f.type_syntax):
                                val_expr = f'parseInt({val_expr}, 10)'
                            event_listeners.append(f'        {f.name}: {val_expr},')
                        event_listeners.append(f'      }};')
                        event_listeners.append(f'    }}')
                        args.append('val')
                    else:
                        val_expr = f'(document.getElementById("in_{a.id}_{p_name}") as HTMLTextAreaElement).value'
                        args.append(f'JSON.parse({val_expr})')
                elif p_type == 'list':
                    val_expr = f'(document.getElementById("in_{a.id}_{p_name}") as HTMLTextAreaElement).value'
                    args.append(f'JSON.parse({val_expr})')
                elif p_type == 'integer':
                    val_expr = f'(document.getElementById("in_{a.id}_{p_name}") as HTMLInputElement).value'
                    args.append(f'parseInt({val_expr}, 10)')
                elif p_type == 'number':
                    val_expr = f'(document.getElementById("in_{a.id}_{p_name}") as HTMLInputElement).value'
                    args.append(f'parseFloat({val_expr})')
                else:
                    val_expr = f'(document.getElementById("in_{a.id}_{p_name}") as HTMLInputElement).value'
                    args.append(val_expr)
            
            args_str = ', '.join(args)
            event_listeners.append(f'    const result = await api.{a.id}({args_str});')
            event_listeners.append(f'    const outEl = document.getElementById("out_{a.id}")!;')
            event_listeners.append(f'    if (Array.isArray(result)) {{')
            event_listeners.append(f'      let table = "<table><thead><tr>";')
            event_listeners.append(f'      if (result.length > 0) {{')
            event_listeners.append(f'        Object.keys(result[0]).forEach(k => table += `<th>${{k}}</th>`);')
            event_listeners.append(f'        table += "</tr></thead><tbody>";')
            event_listeners.append(f'        result.forEach(row => {{')
            event_listeners.append(f'          table += "<tr>";')
            event_listeners.append(f'          Object.values(row).forEach(v => table += `<td>${{v}}</td>`);')
            event_listeners.append(f'          table += "</tr>";')
            event_listeners.append(f'        }});')
            event_listeners.append(f'        table += "</tbody></table>";')
            event_listeners.append(f'        outEl.innerHTML = table;')
            event_listeners.append(f'      }} else {{')
            event_listeners.append(f'        outEl.textContent = "No data returned.";')
            event_listeners.append(f'      }}')
            event_listeners.append(f'    }} else {{')
            event_listeners.append(f'      outEl.textContent = typeof result === "object" ? JSON.stringify(result, null, 2) : result;')
            event_listeners.append(f'    }}')
            event_listeners.append(f'  }} catch (e) {{')
            event_listeners.append(f'    document.getElementById("out_{a.id}")!.textContent = "Error: " + e;')
            event_listeners.append(f'  }}')
            event_listeners.append(f'}};')

        js_lines.append(f'app.innerHTML = `{"".join(ui_html)}`;')
        js_lines.extend(event_listeners)
        _write(stage / 'desktop/src/main.ts', '\n'.join(js_lines))
        default_css = '''
:root{font-family:system-ui;color-scheme:light dark;background:#1e1e1e;color:#eee}
body{margin:0;padding:2rem;max-width:1000px;margin:0 auto}
h1{color:#7867ff;text-align:center}
.card{background:#2d2d2d;border:1px solid #444;border-radius:8px;padding:1.5rem;margin-bottom:1.5rem;box-shadow:0 4px 6px rgba(0,0,0,0.3)}
.card h2{margin-top:0;color:#a491ff;font-size:1.2rem}
input, textarea{display:block;width:100%;box-sizing:border-box;margin-bottom:1rem;padding:0.75rem;background:#1a1a1a;border:1px solid #555;color:#fff;border-radius:4px;font-family:monospace}
textarea{min-height:80px}
button{background:#7867ff;color:white;border:none;padding:0.75rem 1.5rem;border-radius:4px;cursor:pointer;font-weight:bold}
button:hover{background:#6354cc}
pre, .output-box{background:#111;padding:1rem;border-radius:4px;overflow-x:auto;margin-top:1rem;border-left:4px solid #7867ff;font-family:monospace}
table{width:100%;border-collapse:collapse;margin-top:1rem}
th, td{padding:0.75rem;text-align:left;border-bottom:1px solid #444}
th{background:#333;color:#a491ff}
details{margin-bottom:1rem;background:#222;padding:0.5rem;border-radius:4px}
summary{cursor:pointer;color:#ccc;font-size:0.9rem}
'''
        _write(stage / 'desktop/src/style.css', default_css)
        _write(stage / 'desktop/vite.config.ts',
               "import { defineConfig } from 'vite';\n"
               'export default defineConfig({ '
               'server: { port: 1420, strictPort: true } });\n')
        _write(stage / 'desktop/src/custom/.gitkeep', '')

        # xtask \u2014 fixes C16 (real subcommands)
        _write(stage / 'crates/xtask/Cargo.toml',
               '[package]\nname="xtask"\nversion="0.1.0"\nedition="2021"\n')
        _write(stage / 'crates/xtask/src/main.rs', """use std::process::{exit, Command};

fn main() {
    let cmd = std::env::args().nth(1).unwrap_or_else(|| "help".to_string());
    match cmd.as_str() {
        "doctor" => {
            for tool in ["cargo", "node", "npm"] {
                match Command::new(tool).arg("--version").output() {
                    Ok(o) => println!("{}: {}", tool,
                        String::from_utf8_lossy(&o.stdout).trim()),
                    Err(_) => eprintln!("{}: MISSING", tool),
                }
            }
        }
        "check" => {
            let ok = Command::new("cargo").args(["check", "--workspace"])
                .status().map(|s| s.success()).unwrap_or(false);
            if !ok { exit(1); }
        }
        "build" => {
            let ok = Command::new("cargo")
                .args(["build", "--release", "--workspace"])
                .status().map(|s| s.success()).unwrap_or(false);
            if !ok { exit(1); }
        }
        _ => println!("xtask subcommands: doctor, check, build"),
    }
}
""")

        # Docs
        _write(stage / 'README.md',
               f'# {cfg.project.name}\n\n'
               'Generated by TauriCanvas. Edit `desktop/src/custom/` only; '
               'everything else is regenerated.\n\n'
               '## Commands\n\n'
               '```\n'
               'cargo app-doctor                    # check toolchain\n'
               'cargo app-check                     # cargo check workspace\n'
               'cargo app-build                     # release build\n'
               'npm --prefix desktop install        # install JS deps\n'
               'npm --prefix desktop run tauri dev  # launch the app\n'
               '```\n')
        _write(stage / 'AI_GUIDE.md',
               '# AI Guide\n\n'
               '- Do not edit `crates/app-engine/` (copied from source) '
               'or `desktop/src/generated/` (regenerated).\n'
               '- Add custom logic under `desktop/src/custom/` and register it '
               'from `desktop/src/main.ts`.\n'
               '- Regenerate with `tauricanvas generate` after changing `tauricanvas.yaml`.\n')

        # Manifest of generated files
        files = {
            p.relative_to(stage).as_posix(): hash_file(p)
            for p in stage.rglob('*')
            if p.is_file() and '.tauricanvas' not in p.parts
        }
        _write(stage / '.tauricanvas/generated-manifest.json',
               json.dumps({'generator_version': '0.1.0', 'generated_files': files},
                          indent=2) + '\n')

        issues = validate(stage)
        if issues:
            raise RuntimeError('TC-GEN-002 generated project failed validation:\n'
                               + '\n'.join(issues))

        os.replace(stage, dest)
        return dest
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
