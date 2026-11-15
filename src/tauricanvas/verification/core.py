from pathlib import Path
import json

from .process import run


def verify(project: Path) -> dict:
    gates: list[dict] = []
    for args, cwd in [
        (['cargo', 'check', '--workspace', '--all-targets'], project),
        (['cargo', 'test', '--workspace', '--no-run'], project),
    ]:
        r = run(args, cwd)
        gates.append({
            'command': args, 'cwd': str(cwd), 'exit_code': r.code,
            'status': 'PASS' if r.code == 0 else 'FAIL',
            'stderr': r.err[-4000:],
        })

    if (project / 'desktop/node_modules').exists():
        for cmd in ('typecheck', 'build'):
            r = run(['npm', 'run', cmd], project / 'desktop')
            gates.append({
                'command': ['npm', 'run', cmd],
                'cwd': str(project / 'desktop'),
                'exit_code': r.code,
                'status': 'PASS' if r.code == 0 else 'FAIL',
                'stderr': r.err[-4000:],
            })
    else:
        gates.append({
            'command': ['npm', 'install'],
            'cwd': str(project / 'desktop'),
            'exit_code': None,
            'status': 'SKIP',
            'stderr': 'node_modules not present \u2014 run `npm --prefix desktop install` first',
        })

    diagnostics: list[dict] = []
    inspection_path = project / 'reports/inspection.json'
    if inspection_path.is_file():
        try:
            diagnostics = json.loads(inspection_path.read_text(encoding='utf-8')).get('diagnostics', [])
        except Exception:
            pass

    all_pass = all(g['status'] in ('PASS', 'SKIP') for g in gates)
    status = 'GENERATION_VERIFIED' if all_pass else 'GENERATION_COMPLETE_UNVERIFIED'
    report = {'status': status, 'gates': gates, 'diagnostics': diagnostics}
    out = project / 'reports/verification.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return report
