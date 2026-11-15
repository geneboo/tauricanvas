from tauricanvas.models import ActionContract, Contract


def outer(s: str):
    s = s.strip()
    if '<' in s and s.endswith('>'):
        return (s[:s.index('<')], s[s.index('<') + 1:-1])
    return (s, None)


def _split_top(b: str, sep: str = ',') -> list[str]:
    parts: list[str] = []
    depth = 0
    last = 0
    for i, c in enumerate(b):
        if c == '<':
            depth += 1
        elif c == '>':
            depth -= 1
        elif c == sep and depth == 0:
            parts.append(b[last:i])
            last = i + 1
    parts.append(b[last:])
    return parts


def _strip_ref(s: str) -> str:
    s = s.strip()
    while s.startswith('&'):
        s = s[1:].strip()
        if s.startswith("'"):
            bits = s.split(None, 1)
            s = bits[1].strip() if len(bits) > 1 else ''
    return s.removeprefix('mut ').strip()


def map_type(s: str):
    s = _strip_ref(s)
    a, b = outer(s)
    if a == 'Result' and b:
        return map_type(_split_top(b)[0])
    if a == 'Option' and b:
        t = map_type(b)
        t['optional'] = True
        return t
    if a == 'Vec' and b:
        return {'kind': 'list', 'item': map_type(b), 'optional': False}
    if a in ('HashMap', 'BTreeMap') and b:
        parts = _split_top(b)
        return {
            'kind': 'map',
            'key': map_type(parts[0]),
            'item': map_type(parts[1]),
            'optional': False,
        }
    if a == 'Cow' and b:
        parts = _split_top(b)
        return map_type(parts[1])
    kind = {
        'String': 'string', 'str': 'string', 'bool': 'boolean',
        'u8': 'integer', 'u16': 'integer', 'u32': 'integer',
        'u64': 'integer', 'u128': 'integer', 'usize': 'integer',
        'i8': 'integer', 'i16': 'integer', 'i32': 'integer',
        'i64': 'integer', 'i128': 'integer', 'isize': 'integer',
        'f32': 'number', 'f64': 'number',
        '()': 'unit', 'PathBuf': 'path',
    }.get(s, 'object')
    return {'kind': kind, 'name': None if kind != 'object' else s, 'optional': False}


def build(cfg, report):
    acts = []
    for a in cfg.actions:
        if not a.enabled:
            continue
        ms = [f for f in report.functions
              if f.package == a.source.crate and f'{f.module}::{f.name}' == a.source.function]
        if len(ms) != 1:
            raise ValueError(f'TC-ACTION-201 {a.id} resolves to {len(ms)} functions')
        f = ms[0]
        if f.classification in ('unsupported_signature', 'dangerous_not_enabled'):
            raise ValueError(f'TC-ACTION-202 unsafe action {a.id}')
        head, inner = outer(f.return_type.strip())
        returns_result = head == 'Result' and inner is not None
        acts.append(ActionContract(
            id=a.id, title=a.title, command=a.id, source=f.identity,
            safety=a.safety,
            parameters=[{'name': p.name, 'type': map_type(p.type_syntax)} for p in f.parameters],
            output=map_type(f.return_type),
            route=a.presentation.route,
            async_=f.async_,
            returns_result=returns_result,
        ))
    return Contract(name=cfg.project.name, identifier=cfg.project.identifier, actions=acts)
