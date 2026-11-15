from pathlib import Path
import json
import shutil
import sys

import typer
from rich.console import Console
from rich.table import Table

from tauricanvas import __version__
from tauricanvas.inspection.rust import inspect
from tauricanvas.config.core import draft, save, load
from tauricanvas.contract.core import build
from tauricanvas.generation.core import generate as gen
from tauricanvas.validation.core import validate as val
from tauricanvas.verification.core import verify as ver

app = typer.Typer(no_args_is_help=True)
c = Console()


@app.callback(invoke_without_command=True)
def main(version: bool = typer.Option(
    False, '--version', is_eager=True, help='Show version and exit.'
)):
    if version:
        c.print(__version__)
        raise typer.Exit()


@app.command()
def doctor(json_output: bool = typer.Option(False, '--json')):
    tools = {x: shutil.which(x) for x in ('cargo', 'rustfmt', 'node', 'npm')}
    ok = all(tools.values())
    if json_output:
        c.print_json(data={
            'python': sys.version.split()[0],
            'tools': tools,
            'ok': ok,
        })
    else:
        t = Table('Tool', 'Path')
        t.add_row('python', sys.executable)
        for k, v in tools.items():
            t.add_row(k, v or 'MISSING')
        c.print(t)
    if not ok:
        raise typer.Exit(10)


@app.command('inspect')
def inspect_cmd(
    source: Path = typer.Option(...),
    report: Path = typer.Option(Path('inspection.json')),
):
    r = inspect(source)
    report.write_text(r.model_dump_json(indent=2) + '\n', encoding='utf-8')
    if r.diagnostics:
        c.print(f'[yellow]{len(r.diagnostics)} diagnostic(s) \u2014 see {report}[/yellow]')
    c.print('INSPECTION_COMPLETE')


@app.command('init')
def init_cmd(
    source: Path = typer.Option(...),
    output: Path = typer.Option(Path('tauricanvas.yaml')),
):
    save(output, draft(source))
    c.print(output)


@app.command()
def generate(
    config: Path = typer.Option(...),
    output: Path = typer.Option(...),
    dry_run: bool = typer.Option(False, '--dry-run',
                                 help='Print the contract without writing files.'),
):
    if dry_run:
        cfg = load(config)
        report = inspect(Path(cfg.source.manifest))
        contract = build(cfg, report)
        c.print_json(data=contract.model_dump())
        return
    dest = gen(config, output)
    c.print(f'GENERATION_COMPLETE: {dest}')


@app.command()
def validate(project: Path = typer.Option(...)):
    issues = val(project)
    if issues:
        c.print('\n'.join(issues))
        raise typer.Exit(50)
    c.print('PASS')


@app.command()
def verify(project: Path = typer.Option(...)):
    r = ver(project)
    c.print(r['status'])
    if r['diagnostics']:
        c.print(f'[yellow]{len(r["diagnostics"])} diagnostic(s) recorded[/yellow]')
    if r['status'] != 'GENERATION_VERIFIED':
        raise typer.Exit(60)


@app.command()
def diff(project: Path = typer.Option(...)):
    from tauricanvas.utilities.fs import hash_file
    m = json.loads((project / '.tauricanvas/generated-manifest.json').read_text(encoding='utf-8'))
    changed = [
        x for x, h in m['generated_files'].items()
        if not (project / x).exists() or hash_file(project / x) != h
    ]
    c.print_json(data={'changed': changed, 'clean': not changed})
