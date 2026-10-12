#!/usr/bin/env python3
"""Validate the public workflow and sign it with Apple's Shortcuts CLI on macOS."""
import argparse
import json
import plistlib
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument('--check', action='store_true', help='Validate without signing')
args = parser.parse_args()
source = ROOT / 'src/保质期管家.plist'
p = plistlib.loads(source.read_bytes())
actions = p['WFWorkflowActions']
uuids = [a['WFWorkflowActionParameters']['UUID'] for a in actions]
assert len(uuids) == len(set(uuids)), 'Duplicate UUID'
known = set(uuids)

def inspect(value):
    if isinstance(value, dict):
        if 'OutputUUID' in value:
            assert value['OutputUUID'] in known, 'Unresolved output reference'
        assert 'WFCalendarDescriptor' not in value, 'Personal calendar descriptor'
        for child in value.values(): inspect(child)
    elif isinstance(value, list):
        for child in value: inspect(child)

inspect(p)
stack = []
for action in actions:
    kind = action['WFWorkflowActionIdentifier']
    q = action['WFWorkflowActionParameters']
    if kind.endswith(('conditional', 'choosefrommenu')):
        mode = q['WFControlFlowMode']
        group = q['GroupingIdentifier']
        if mode == 0: stack.append((kind, group))
        else:
            assert stack and stack[-1] == (kind, group), 'Unbalanced control flow'
            if mode == 2: stack.pop()
        if kind.endswith('conditional') and mode == 0:
            assert q['WFCondition'] in (100, 2), 'Unexpected condition'
            if q['WFCondition'] == 2: assert q.get('WFNumberValue') == '0'
assert not stack, 'Unclosed control flow'
raw = source.read_text()
assert '/Users/' not in raw and 'x-apple-reminderkit://' not in raw, 'Personal path or list ID'
print(f'Validated {len(actions)} actions and all output references.')
if not args.check:
    (ROOT / 'src/workflow.json').write_text(json.dumps(p, ensure_ascii=False, indent=2) + '\n')
    target = ROOT / 'downloads/保质期管家.shortcut'
    target.parent.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        unsigned = Path(tmp) / 'public-unsigned.shortcut'
        unsigned.write_bytes(source.read_bytes())
        subprocess.run(['shortcuts', 'sign', '--mode', 'anyone', '--input', str(unsigned), '--output', str(target)], check=True)
    print(f'Signed: {target}')
