from pathlib import Path

from tauricanvas.models import Diagnostic, Function, Inspection, Parameter, RustType
from tauricanvas.cargo.core import metadata, manifest


def _text(node, data: bytes) -> str:
    return data[node.start_byte:node.end_byte].decode()


def _preceding_attrs(node, data: bytes) -> list[str]:
    """Collect attribute_item siblings immediately preceding `node`.

    Walk `prev_sibling` and stop at the first non-attribute, non-comment
    sibling. This prevents leaking an attribute from a previous item onto
    the current one (the previous implementation did).
    """
    attrs: list[str] = []
    sib = node.prev_sibling
    while sib is not None:
        if sib.type == 'attribute_item':
            attrs.append(_text(sib, data))
        elif sib.type in ('line_comment', 'block_comment'):
            pass  # comments between attribute and item are ignored
        else:
            break
        sib = sib.prev_sibling
    attrs.reverse()
    return attrs


def _is_public(node, data: bytes) -> bool:
    for child in node.children:
        if child.type == 'visibility_modifier':
            return _text(child, data).startswith('pub')
    return False


def _module_of(path: Path, package: str, root: Path) -> str:
    rel = path.relative_to(root).with_suffix('')
    parts = list(rel.parts)
    if len(parts) == 1 and parts[0] in ('lib', 'main'):
        return package.replace('-', '_')
    if parts and parts[-1] == 'mod':
        parts = parts[:-1]
    return '::'.join(parts)


def classify(f: Function) -> Function:
    dangerous = any(f.name.startswith(x) for x in (
        'delete_all', 'drop_', 'erase_', 'format_', 'execute_shell',
        'run_command', 'shutdown',
    ))
    bad = (
        f.unsafe
        or f.generic
        or any(
            '&' in p.type_syntax
            or '*' in p.type_syntax
            or 'dyn ' in p.type_syntax
            or 'Fn' in p.type_syntax        # C1: was p.parameters
            for p in f.parameters
        )
        or '&' in f.return_type
    )
    if not f.public:
        f.classification = 'internal_not_candidate'
        f.reasons = ['not public']
    elif dangerous:
        f.classification = 'dangerous_not_enabled'
        f.reasons = ['security-sensitive name']
    elif bad:
        f.classification = 'unsupported_signature'
        f.reasons = ['explicit adapter required']
    elif any('tauri::command' in a for a in f.attributes):
        f.classification = 'ready_existing_tauri_command'
        f.reasons = ['existing Tauri command']
    else:
        f.classification = 'review_required'
        f.reasons = ['explicit selection required']
    return f


def parse(path: Path, package: str, root: Path):
    import tree_sitter_rust
    from tree_sitter import Language, Parser

    parser = Parser(Language(tree_sitter_rust.language()))
    data = path.read_bytes()
    tree = parser.parse(data)
    fs: list[Function] = []
    ts: list[RustType] = []
    ds: list[Diagnostic] = []
    module = _module_of(path, package, root)

    def walk(node):
        if node.type == 'ERROR':
            ds.append(Diagnostic(
                code='TC-RUST-002', severity='warning', stage='inspection',
                message='parse error', file=str(path), line=node.start_point[0] + 1,
            ))
        if node.type == 'function_item':
            name_node = node.child_by_field_name('name')
            params_node = node.child_by_field_name('parameters')
            ret_node = node.child_by_field_name('return_type')
            name = _text(name_node, data) if name_node else '<anon>'
            ps: list[Parameter] = []
            if params_node:
                for child in params_node.named_children:
                    if child.type == 'parameter':
                        pat = child.child_by_field_name('pattern')
                        typ = child.child_by_field_name('type')
                        typet = _text(typ, data) if typ else ''
                        ps.append(Parameter(
                            name=_text(pat, data) if pat else '_',
                            type_syntax=typet,
                            borrowed='&' in typet,
                        ))
                    elif child.type == 'self_parameter':
                        raw = _text(child, data)
                        ps.append(Parameter(name='self', type_syntax=raw, borrowed='&' in raw))
            pre = _text(node, data).split('fn ', 1)[0].split()
            f = Function(
                identity=f'{package}::{module}::{name}',
                package=package, module=module, name=name,
                file=str(path), line=node.start_point[0] + 1,
                public=_is_public(node, data),
                async_='async' in pre,
                unsafe='unsafe' in pre,
                generic=node.child_by_field_name('type_parameters') is not None,
                parameters=ps,
                return_type=_text(ret_node, data).removeprefix('->').strip() if ret_node else '()',
                attributes=_preceding_attrs(node, data),
            )
            fs.append(classify(f))
        elif node.type in ('struct_item', 'enum_item', 'type_item', 'union_item'):
            name_node = node.child_by_field_name('name')
            if name_node is not None:
                name = _text(name_node, data)
                fields = []
                body = node.child_by_field_name('body')
                if body:
                    for child in body.named_children:
                        if child.type == 'field_declaration':
                            f_name = child.child_by_field_name('name')
                            f_type = child.child_by_field_name('type')
                            if f_name and f_type:
                                fields.append(Parameter(
                                    name=_text(f_name, data),
                                    type_syntax=_text(f_type, data)
                                ))
                ts.append(RustType(
                    identity=f'{package}::{module}::{name}',
                    package=package,
                    name=name, kind=node.type.replace('_item', ''),
                    file=str(path), line=node.start_point[0] + 1,
                    public=_is_public(node, data),
                    fields=fields,
                ))
        for child in node.named_children:
            walk(child)

    walk(tree.root_node)
    return fs, ts, ds


def inspect(source: Path) -> Inspection:
    md = metadata(source)
    manifest_path = str(manifest(source))
    member_ids = set(md.get('workspace_members') or [])
    if member_ids:
        pkgs = [p for p in md['packages'] if p['id'] in member_ids]
    else:
        ws_root = Path(md['workspace_root']).resolve()
        pkgs = []
        for p in md['packages']:
            mp = Path(p.get('manifest_path', '')).resolve()
            try:
                mp.relative_to(ws_root)
                pkgs.append(p)
            except ValueError:
                pass
    if not pkgs:
        raise RuntimeError('TC-RUST-003 no workspace member packages found')

    fs: list[Function] = []
    ts: list[RustType] = []
    ds: list[Diagnostic] = []
    for pkg in sorted(pkgs, key=lambda x: x['name']):
        for target in pkg['targets']:
            root = Path(target['src_path']).parent
            for path in sorted(root.rglob('*.rs')):
                if 'target' in path.parts or 'node_modules' in path.parts:
                    continue
                a, b, c = parse(path, pkg['name'], root)
                fs += a
                ts += b
                ds += c
    return Inspection(
        manifest=manifest_path,
        workspace_root=md['workspace_root'],
        packages=sorted(pkgs, key=lambda x: x['name']),
        functions=sorted(fs, key=lambda x: x.identity),
        types=sorted(ts, key=lambda x: x.identity),
        diagnostics=ds,
    )
