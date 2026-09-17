"""Explicit, local-only Git operations for contribution art."""

import json
import os
import re
import subprocess
import tempfile
import uuid
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

LEGACY = re.compile(r'^Dummy commit on \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$')
ART = re.compile(r'^Contribution art: (\d{4}-\d{2}-\d{2}) #(\d+) \[([a-f0-9]{64})\]$')


def git(repo, *args, env=None):
    result = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, env=env)
    if result.returncode:
        raise ValueError(f'git {args[0]}: {result.stderr.strip()}')
    return result.stdout.strip()


def identity(config):
    author = config.get('author', {})
    name = os.environ.get('GITHUB_NAME', author.get('name', ''))
    email = os.environ.get('GITHUB_EMAIL', author.get('email', ''))
    if not name or not email or '@' not in email or any(c in name + email for c in '\r\n<>\x00'):
        raise ValueError('Provide a valid author name and GitHub-linked email in config or GITHUB_NAME/GITHUB_EMAIL')
    return name, email


def legacy_counts(repo, ref='HEAD'):
    counts = Counter()
    for line in git(repo, 'log', ref, '--format=%aI%x09%s').splitlines():
        stamp, subject = line.split('\t', 1)
        if LEGACY.fullmatch(subject):
            counts[stamp[:10]] += 1
    return dict(counts)


def require_clean(repo):
    if git(repo, 'status', '--porcelain'):
        raise ValueError('Repository must be clean. Commit or move your changes first.')
    git(repo, 'symbolic-ref', '--short', 'HEAD')


def paint(repo, config, plan, max_commits=200000):
    """Append missing pixels on the current branch. Never push or create future commits."""
    repo = Path(repo).resolve()
    require_clean(repo)
    if legacy_counts(repo):
        raise ValueError('Random legacy history remains. Prepare a separate replacement repository first.')
    name, email = identity(config)
    state = dict(version=1, layout_hash=plan['layout_hash'], author=dict(name=name, email=email))
    state_path = repo / '.banner' / 'state.json'
    existing = Counter()
    sequences = {}
    if state_path.is_file():
        if json.loads(state_path.read_text()) != state:
            raise ValueError('Layout or author changed. Prepare a new replacement; do not paint over existing letters.')
        for line in git(repo, 'log', '--format=%aI%x09%an%x09%ae%x09%s', '--', '.banner/pixel.json').splitlines():
            stamp, author_name, author_email, subject = line.split('\t', 3)
            match = ART.fullmatch(subject)
            if (not match or match[3] != plan['layout_hash'] or stamp[:10] != match[1]
                    or (author_name, author_email) != (name, email)):
                raise ValueError('Unexpected edits to the art history; inspect before continuing.')
            day, number = match[1], int(match[2])
            sequences.setdefault(day, []).append(number)
            existing[day] += 1
        for day, numbers in sequences.items():
            if sorted(numbers) != list(range(1, len(numbers) + 1)):
                raise ValueError(f'Incomplete or duplicate art history on {day}')
    elif (repo / '.banner').exists():
        raise ValueError('The reserved .banner directory already exists without valid state.')
    today = datetime.now(timezone.utc).date().isoformat()
    if plan['as_of'] > today:
        raise ValueError('Apply cutoff cannot be in the future. Future dates are preview-only.')
    jobs = []
    for year in plan['years']:
        target = year['commits_per_pixel']
        if target > 3600:
            raise ValueError('Intensity exceeds 3600 commits/day; inspect the activity snapshot.')
        for day in year['due_pixels']:
            for number in range(existing[day] + 1, target + 1):
                jobs.append((day, number))
    if len(jobs) > max_commits:
        raise ValueError(f'{len(jobs):,} new commits exceed the {max_commits:,} limit.')
    if not jobs:
        return 0
    jobs.sort()
    parent = git(repo, 'rev-parse', 'HEAD')
    ref = 'refs/heads/banner-build-' + uuid.uuid4().hex
    with tempfile.TemporaryFile() as stream:
        def write(text):
            stream.write(text.encode())

        def data(text):
            write(f'data {len(text.encode())}\n{text}\n')

        for index, (day, number) in enumerate(jobs):
            timestamp = int(datetime.fromisoformat(day + 'T12:00:00+00:00').timestamp()) + number - 1
            write(f'commit {ref}\nauthor {name} <{email}> {timestamp} +0000\n'
                  f'committer {name} <{email}> {timestamp} +0000\n')
            data(f'Contribution art: {day} #{number} [{plan["layout_hash"]}]\n')
            if index == 0:
                write(f'from {parent}\nM 100644 inline .banner/state.json\n')
                data(json.dumps(state, sort_keys=True) + '\n')
            write('M 100644 inline .banner/pixel.json\n')
            data(json.dumps(dict(date=day, pixel_commit=number), sort_keys=True) + '\n')
            write('\n')
        stream.seek(0)
        result = subprocess.run(['git', '-C', str(repo), 'fast-import', '--quiet'], stdin=stream,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode:
        raise ValueError(result.stderr.decode())
    # An atomic compare-and-swap is used by merge internally; don't overwrite a moved HEAD.
    if git(repo, 'rev-parse', 'HEAD') != parent:
        raise ValueError(f'HEAD changed during generation; generated history is saved at {ref}')
    git(repo, 'merge', '--ff-only', '--no-edit', ref)
    git(repo, 'update-ref', '-d', ref)
    return len(jobs)


def prepare_replacement(source, destination):
    """Copy real code updates into a NEW repository, leaving all source refs intact."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    require_clean(source)
    if destination.exists():
        raise ValueError('Destination must not exist; use a fresh path for a replacement.')
    commits = git(source, 'rev-list', '--reverse', 'HEAD').splitlines()
    retained, removed = [], []
    for oid in commits:
        subject = git(source, 'show', '-s', '--format=%s', oid)
        parents = git(source, 'show', '-s', '--format=%P', oid).split()
        if len(parents) > 1:
            raise ValueError('Automatic migration supports linear history only.')
        if LEGACY.fullmatch(subject):
            changed = git(source, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', oid).splitlines()
            if not set(changed) <= {'index.html', 'script.js', 'styles.css'}:
                raise ValueError(f'{oid}: a dummy-labelled commit touches unexpected files; inspect manually.')
            if parents:
                diff = git(source, 'diff', '--unified=0', parents[0], oid, '--', *changed)
                for line in diff.splitlines():
                    if line.startswith(('+++', '---')):
                        continue
                    if line.startswith('-') or (line.startswith('+') and line[1:].strip()
                                               and line[1:].strip() != '// Commit on ' + subject[16:]):
                        raise ValueError(f'{oid}: dummy-labelled commit contains non-generator changes.')
            removed.append(oid)
        elif ART.fullmatch(subject):
            removed.append(oid)
        else:
            retained.append(oid)
    if not retained:
        raise ValueError('No project code commits to preserve.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    backup = destination.with_name(destination.name + '-original.bundle')
    if backup.exists():
        raise ValueError(f'Backup already exists: {backup}')
    git(source, 'bundle', 'create', str(backup), '--all')
    git(source, 'bundle', 'verify', str(backup))
    destination.mkdir()
    git(destination, 'init', '-b', 'main')
    git(destination, 'fetch', '--quiet', str(source), 'HEAD')
    parent = None
    mapping = {}
    for oid in retained:
        fields = git(source, 'show', '-s', '--format=%an%x00%ae%x00%aI%x00%cn%x00%ce%x00%cI', oid).split('\x00')
        env = os.environ.copy()
        for key, value in zip(('GIT_AUTHOR_NAME', 'GIT_AUTHOR_EMAIL', 'GIT_AUTHOR_DATE',
                               'GIT_COMMITTER_NAME', 'GIT_COMMITTER_EMAIL', 'GIT_COMMITTER_DATE'), fields):
            env[key] = value
        tree = git(source, 'rev-parse', oid + '^{tree}')
        # When rebuilding an existing banner branch, remove only the generator's state.
        if git(source, 'ls-tree', oid, '--', '.banner'):
            index_file = destination / '.git' / 'banner-index'
            env['GIT_INDEX_FILE'] = str(index_file)
            git(destination, 'read-tree', tree, env=env)
            git(destination, 'update-index', '--force-remove', '.banner/state.json', '.banner/pixel.json', env=env)
            tree = git(destination, 'write-tree', env=env)
        args = ['commit-tree', tree]
        if parent:
            args += ['-p', parent]
        args += ['-m', git(source, 'show', '-s', '--format=%B', oid)]
        parent = git(destination, *args, env=env)
        mapping[oid] = parent
    git(destination, 'update-ref', 'refs/heads/main', parent)
    git(destination, 'checkout', '--quiet', 'main')
    origin = git(source, 'remote', 'get-url', 'origin')
    git(destination, 'remote', 'add', 'origin', origin)
    expected = git(source, 'rev-parse', 'refs/remotes/origin/main')
    report = dict(source=str(source), destination=str(destination), backup=str(backup),
                  removed_commits=len(removed), preserved_commits=len(retained),
                  preserved_commit_mapping=mapping, expected_remote_main=expected,
                  origin=origin, pushed=False)
    destination.with_name(destination.name + '-migration.json').write_text(json.dumps(report, indent=2) + '\n')
    return report
