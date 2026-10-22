import json
import subprocess
from pathlib import Path

def git(*args):
    return subprocess.check_output(['git', *args], text=True).strip()

local = git('rev-parse', 'HEAD')
remote = git('rev-parse', 'origin/master')
expected = {
    'circuit/SensorHub/.gitignore',
    'circuit/SensorHub/SensorHub.kicad_pcb',
    'circuit/SensorHub/SensorHub.kicad_pro',
    'circuit/SensorHub/SensorHub.kicad_sch',
    'circuit/SensorHub/SensorHub.kicad_sym',
    'circuit/SensorHub/sym-lib-table',
}
assert set(git('diff-tree', '--no-commit-id', '--name-only', '-r', local).splitlines()) == expected
assert not git('diff', '--cached', '--name-only')
tree = git('merge-tree', '--write-tree', local, remote)
assert '\n' not in tree
assert set(git('diff', '--name-only', remote, tree).splitlines()) == expected
git('diff', '--check', remote, tree)
merged = git('commit-tree', tree, '-p', local, '-p', remote, '-m',
             'Merge current remote master with scoped SensorHub KiCad wiring update')
branch = 'codex/sensorhub-sync-20261021'
git('branch', branch, merged)
print(json.dumps({'local_commit': local, 'previous_remote': remote, 'publish_commit': merged, 'files': sorted(expected)}, indent=2), flush=True)
subprocess.run(['git', 'push', 'origin', f'{branch}:master'], check=True)
published = git('ls-remote', 'origin', 'refs/heads/master').split()[0]
assert published == merged, (published, merged)
assert git('rev-parse', 'HEAD') == local
assert not git('diff', '--cached', '--name-only')
Path('outputs/sensorhub_schematic_20261020/publication.json').write_text(
    json.dumps({'published_commit': published, 'local_commit': local, 'files': sorted(expected)}, indent=2) + '\n')
print('VERIFIED published master:', published, flush=True)
