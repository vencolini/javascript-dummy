#!/usr/bin/env python3
"""Turn contribution calendars into banners. Default action is a read-only preview."""

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

from banner import load_activity, make_plan, write_preview
from history import legacy_counts, paint, prepare_replacement


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=('preview', 'apply', 'prepare'), default='preview')
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('banners.json'))
    parser.add_argument('--as-of', type=date.fromisoformat, default=datetime.now(timezone.utc).date())
    parser.add_argument('--activity', type=Path, help='JSON snapshot of daily GitHub counts')
    parser.add_argument('--subtract-legacy', type=Path, help='Old repository whose dummy counts should be subtracted from the snapshot')
    parser.add_argument('--output', type=Path, default=Path('preview'), help='Preview output directory')
    parser.add_argument('--repo', type=Path, default=Path('.'), help='Local repository to apply to / prepare from')
    parser.add_argument('--destination', type=Path, help='New local repository for prepare (must not exist)')
    parser.add_argument('--max-commits', type=int, default=200000)
    args = parser.parse_args(argv)
    try:
        if args.action == 'prepare':
            if args.destination is None:
                raise ValueError('prepare requires --destination pointing to a new directory')
            report = prepare_replacement(args.repo, args.destination)
            print(json.dumps(report, indent=2))
            return 0
        config = json.loads(args.config.read_text())
        activity = load_activity(args.activity)
        removed = legacy_counts(args.subtract_legacy) if args.subtract_legacy else {}
        plan = make_plan(config, args.as_of, activity, removed)
        if args.action == 'apply':
            # Subtract existing art from a fresh activity snapshot before recalibrating,
            # otherwise each run would inflate its own intensity.
            if activity:
                from history import ART, git
                for line in git(args.repo, 'log', '--format=%s').splitlines():
                    match = ART.fullmatch(line)
                    if match:
                        removed[match[1]] = removed.get(match[1], 0) + 1
                plan = make_plan(config, args.as_of, activity, removed)
            added = paint(args.repo, config, plan, args.max_commits)
            print(f'Added {added:,} contribution-art commits locally. Nothing was pushed.')
        else:
            write_preview(plan, args.output)
            print(f'Preview: {(args.output / "index.html").resolve()}')
        for year in plan['years']:
            print(f'{year["year"]}  {year["text"]:12}  {year["width"]:2} weeks  '
                  f'{year["first_pixel"]} → {year["last_pixel"]}  '
                  f'{len(year["pending_pixels"]):3} future pixels  '
                  f'{year["commits_per_pixel"]} commits/pixel')
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(f'Error: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
