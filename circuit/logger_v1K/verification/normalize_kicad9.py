"""Normalize MCP-generated records to the project's KiCad 9 syntax."""
from pathlib import Path
import re

BASE = Path(__file__).resolve().parents[1]
TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|[()]|[^\s()]+')

def parse(text):
    stack, roots = [], []
    for m in TOKEN.finditer(text):
        s = m.group()
        if s == '(':
            node = {'start': m.start(), 'children': [], 'atoms': []}
            if stack:
                stack[-1]['children'].append(node)
            else:
                roots.append(node)
            stack.append(node)
        elif s == ')':
            stack.pop()['end'] = m.end()
        else:
            stack[-1]['atoms'].append(s)
    assert not stack
    return roots[0]

def normalize(path):
    text = path.read_text(encoding='utf-8')
    root = parse(text)
    edits = []
    def walk(n, parent=None):
        tag = n['atoms'][0]
        parent_tag = parent['atoms'][0] if parent else ''
        remove = tag in ('body_style', 'in_pos_files')
        if tag == 'exclude_from_sim':
            remove = parent_tag == 'text' or (parent_tag == 'symbol' and not any(c['atoms'][0] == 'lib_id' for c in parent['children']))
        if remove:
            edits.append((n['start'], n['end'], ''))
            return
        if tag == 'property':
            hidden = next((c for c in n['children'] if c['atoms'][0] == 'hide'), None)
            effects = next((c for c in n['children'] if c['atoms'][0] == 'effects'), None)
            if hidden and effects:
                edits.append((hidden['start'], hidden['end'], ''))
                edits.append((effects['end']-1, effects['end']-1, ' (hide yes)'))
        for c in n['children']:
            walk(c, n)
    walk(root)
    for start, end, value in sorted(edits, reverse=True):
        text = text[:start] + value + text[end:]
    path.write_text(text, encoding='utf-8')
    print(path.name, len(edits), 'syntax adjustments')

for name in ['logger_v1K.kicad_sch', 'logger_v1K.kicad_sym']:
    normalize(BASE / name)
