#!/usr/bin/env python3
from __future__ import annotations
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_DIR = ROOT / 'contracts' / 'schemas'
OUT_DIR = ROOT / 'src' / 'contracts' / 'generated'

def snake_to_pascal(s: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", s)
    return ''.join(p[:1].upper() + p[1:] for p in parts if p)

def filename_to_classname(p: Path, fallback: str = 'Model') -> str:
    name = p.stem
    return snake_to_pascal(name) or fallback

def map_type(prop: Dict[str, Any]) -> str:
    t = prop.get('type')
    if isinstance(t, list):
        if 'null' in t and len(t) > 1:
            t = [x for x in t if x != 'null'][0]
        else:
            t = t[0]
    if t == 'string':
        return 'str'
    if t == 'integer':
        return 'int'
    if t == 'number':
        return 'float'
    if t == 'boolean':
        return 'bool'
    if t == 'array':
        item_t = map_type(prop.get('items', {})) if isinstance(prop.get('items'), dict) else 'Any'
        return f'List[{item_t}]'
    if t == 'object':
        ap = prop.get('additionalProperties')
        if ap is False:
            return 'Dict[str, Any]'
        if isinstance(ap, dict):
            return f'Dict[str, {map_type(ap)}]'
        return 'Dict[str, Any]'
    return 'Any'

def generate_model(schema_path: Path) -> tuple[str, str]:
    schema = json.loads(schema_path.read_text(encoding='utf-8'))
    title = schema.get('title') or filename_to_classname(schema_path)
    classname = snake_to_pascal(title)
    props = schema.get('properties', {})
    required: List[str] = list(schema.get('required', []))
    addl = schema.get('additionalProperties', True)

    imports = [
        'from __future__ import annotations',
        'from typing import Any, Dict, List, Optional',
        'from pydantic import BaseModel, Field',
    ]

    fields: List[str] = []
    for name, spec in props.items():
        py_t = map_type(spec)
        is_required = name in required
        ann = py_t if is_required else f'Optional[{py_t}]'
        default = '...' if is_required else 'None'
        descr = spec.get('description')
        field_expr = f'Field({default})' if not descr else f"Field({default}, description={json.dumps(descr)})"
        fields.append(f"    {name}: {ann} = {field_expr}")

    forbid = addl is False
    config = "    class Config:\n        extra = 'forbid'\n" if forbid else ''

    body = [
        *imports,
        '',
        f'class {classname}(BaseModel):',
        f"    " + (schema.get('description') or f'Generated from {schema_path.name}'),
        *(fields or ['    pass']),
        '',
        config,
    ]
    content = '\n'.join([line for line in body if line is not None])
    return classname, content

def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    modules: List[str] = []
    for sp in sorted(SCHEMAS_DIR.glob('*.json')):
        classname, code = generate_model(sp)
        out_path = OUT_DIR / f'{classname}.py'
        out_path.write_text(code, encoding='utf-8')
        modules.append(classname)
        print(f'generated: {out_path}')
    (OUT_DIR / '__init__.py').write_text('\n'.join(['# Auto-generated; do not edit by hand', '', *[f"from .{m} import {m}" for m in modules]]) + '\n', encoding='utf-8')
    print(f'generated {len(modules)} module(s)')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
