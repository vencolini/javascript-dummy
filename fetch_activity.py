#!/usr/bin/env python3
"""Read a GitHub contribution snapshot using your existing gh login."""

import argparse
import json
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--user', default='vencolini')
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('banners.json'))
    parser.add_argument('--output', type=Path, default=Path('.local/activity.json'))
    args = parser.parse_args()
    years = sorted({item['year'] for item in json.loads(args.config.read_text())['years']})
    collections = ' '.join(
        f'y{year}: contributionsCollection(from: "{year}-01-01T00:00:00Z", to: "{year}-12-31T23:59:59Z") '
        '{ contributionCalendar { weeks { contributionDays { date contributionCount contributionLevel } } } }'
        for year in years)
    query = 'query($login:String!) { user(login:$login) { ' + collections + ' } }'
    result = subprocess.run(['gh', 'api', 'graphql', '-f', 'query=' + query, '-f', 'login=' + args.user],
                            check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    if data.get('errors') or not data.get('data', {}).get('user'):
        raise SystemExit('GitHub did not return a complete contribution snapshot')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + '\n')
    print(f'Saved daily totals to {args.output}')


if __name__ == '__main__':
    main()
