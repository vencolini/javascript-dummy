"""Calendar lettering and previews. Python 3.9+, standard library only."""

import hashlib
import html
import json
from datetime import date, timedelta
from pathlib import Path

# Sunday is the top row. Every glyph is seven rows high.
FONT = {
    'A': '01110/10001/10001/11111/10001/10001/10001',
    'B': '11110/10001/10001/11110/10001/10001/11110',
    'C': '01111/10000/10000/10000/10000/10000/01111',
    'D': '11110/10001/10001/10001/10001/10001/11110',
    'E': '11111/10000/10000/11110/10000/10000/11111',
    'F': '11111/10000/10000/11110/10000/10000/10000',
    'G': '01111/10000/10000/10111/10001/10001/01111',
    'H': '10001/10001/10001/11111/10001/10001/10001',
    'I': '111/010/010/010/010/010/111',
    'J': '00111/00010/00010/00010/10010/10010/01100',
    'K': '10001/10010/10100/11000/10100/10010/10001',
    'L': '10000/10000/10000/10000/10000/10000/11111',
    'M': '10001/11011/10101/10101/10001/10001/10001',
    'N': '10001/11001/11001/10101/10011/10011/10001',
    'O': '01110/10001/10001/10001/10001/10001/01110',
    'P': '11110/10001/10001/11110/10000/10000/10000',
    'Q': '01110/10001/10001/10001/10101/10010/01101',
    'R': '11110/10001/10001/11110/10100/10010/10001',
    'S': '01111/10000/10000/01110/00001/00001/11110',
    'T': '11111/00100/00100/00100/00100/00100/00100',
    'U': '10001/10001/10001/10001/10001/10001/01110',
    'V': '10001/10001/10001/10001/10001/01010/00100',
    'W': '10001/10001/10001/10101/10101/10101/01010',
    'X': '10001/10001/01010/00100/01010/10001/10001',
    'Y': '10001/10001/01010/00100/00100/00100/00100',
    'Z': '11111/00001/00010/00100/01000/10000/11111',
    '0': '01110/10001/10011/10101/11001/10001/01110',
    '1': '010/110/010/010/010/010/111',
    '2': '01110/10001/00001/00010/00100/01000/11111',
    '3': '11110/00001/00001/01110/00001/00001/11110',
    '4': '00010/00110/01010/10010/11111/00010/00010',
    '5': '11111/10000/10000/11110/00001/00001/11110',
    '6': '01110/10000/10000/11110/10001/10001/01110',
    '7': '11111/00001/00010/00100/01000/01000/01000',
    '8': '01110/10001/10001/01110/10001/10001/01110',
    '9': '01110/10001/10001/01111/00001/00001/01110',
    '-': '000/000/000/111/000/000/000',
    '+': '000/010/010/111/010/010/000',
}
COMPACT = {
    **FONT,
    'A': '010/101/101/111/101/101/101',
    'B': '110/101/101/110/101/101/110',
    'C': '011/100/100/100/100/100/011',
    'D': '110/101/101/101/101/101/110',
    'E': '111/100/100/110/100/100/111',
    'F': '111/100/100/110/100/100/100',
    'G': '011/100/100/101/101/101/011',
    'H': '101/101/101/111/101/101/101',
    'J': '001/001/001/001/101/101/010',
    'K': '101/101/101/110/101/101/101',
    'L': '100/100/100/100/100/100/111',
    'O': '010/101/101/101/101/101/010',
    'P': '110/101/101/110/100/100/100',
    'R': '110/101/101/110/101/101/101',
    'S': '011/100/100/010/001/001/110',
    'T': '111/010/010/010/010/010/010',
    'U': '101/101/101/101/101/101/111',
    'V': '101/101/101/101/101/101/010',
    'X': '101/101/101/010/101/101/101',
    'Y': '101/101/101/010/010/010/010',
    'Z': '111/001/001/010/100/100/111',
}
DAY = timedelta(days=1)


def lettering(text, font='wide'):
    if font not in ('wide', 'compact'):
        raise ValueError('font must be wide or compact')
    glyphs = FONT if font == 'wide' else COMPACT
    text = ' '.join(text.upper().split())
    if not text:
        raise ValueError('Banner text cannot be empty')
    rows = [''] * 7
    for word_index, word in enumerate(text.split()):
        if word_index:
            rows = [r + '000' for r in rows]
        for char_index, char in enumerate(word):
            if char not in glyphs:
                raise ValueError(f'Unsupported character: {char!r}; use A-Z, 0-9, +, - or spaces')
            if char_index:
                rows = [r + '0' for r in rows]
            rows = [r + g for r, g in zip(rows, glyphs[char].split('/'))]
    return text, rows


def layout(spec):
    year = spec['year']
    if type(year) is not int or not 1970 <= year <= 9998:
        raise ValueError('Year must be an integer between 1970 and 9998')
    first, last = date(year, 1, 1), date(year, 12, 31)
    grid_start = first - timedelta(days=(first.weekday() + 1) % 7)
    columns = (last - grid_start).days // 7 + 1
    # Reserve BOTH edge columns, even when an edge happens to be a full week.
    available = list(range(1, columns - 1))
    earliest = date.fromisoformat(spec.get('start_date', first.isoformat()))
    if earliest.year != year:
        raise ValueError('start_date must belong to its banner year')
    available = [col for col in available if grid_start + timedelta(weeks=col) >= earliest]
    text, rows = lettering(spec['text'], spec.get('font', 'wide'))
    width = len(rows[0])
    if width > len(available):
        raise ValueError(f'{year}: {text!r} needs {width} weeks; only {len(available)} fit. '
                         'Shorten the text or choose the compact font.')
    align = spec.get('align', 'center')
    if align not in ('left', 'center', 'right'):
        raise ValueError('align must be left, center or right')
    offset = {'left': 0, 'center': (len(available) - width) // 2,
              'right': len(available) - width}[align]
    start = available[offset]
    pixels = sorted((grid_start + timedelta(weeks=start + col, days=row)).isoformat()
                    for row in range(7) for col in range(width) if rows[row][col] == '1')
    return dict(year=year, text=text, font=spec.get('font', 'wide'), width=width,
                grid_start=grid_start.isoformat(), columns=columns, start_column=start,
                pixels=pixels, first_pixel=pixels[0], last_pixel=pixels[-1])


def load_activity(path):
    """Accept a date->count map or a saved GitHub GraphQL response."""
    if path is None:
        return {}
    data = json.loads(Path(path).read_text())
    if 'errors' in data:
        raise ValueError(f'GitHub returned errors: {data["errors"]}')
    if 'data' in data:
        data = {day['date']: day['contributionCount']
                for collection in data['data']['user'].values()
                for week in collection['contributionCalendar']['weeks']
                for day in week['contributionDays']}
    for key, count in data.items():
        date.fromisoformat(key)
        if type(count) is not int or count < 0:
            raise ValueError('Contribution counts must be non-negative integers')
    return data


def make_plan(config, as_of, activity=None, removed=None):
    activity, removed = activity or {}, removed or {}
    minimum = config.get('commits_per_pixel', 30)
    if type(minimum) is not int or not 1 <= minimum <= 1000:
        raise ValueError('commits_per_pixel must be an integer between 1 and 1000')
    years = [layout(spec) for spec in config['years']]
    if not years or len({y['year'] for y in years}) != len(years):
        raise ValueError('Configure at least one year, without duplicate years')
    background = {day: max(0, count - removed.get(day, 0)) for day, count in activity.items()}
    for year in years:
        peak = max((n for day, n in background.items() if int(day[:4]) == year['year']), default=0)
        # GitHub chooses its own levels; this is a contrast target, not a color API.
        year['commits_per_pixel'] = max(minimum, peak * 3 + 1)
        year['background_peak'] = peak
        year['due_pixels'] = [day for day in year['pixels'] if day <= as_of.isoformat()]
        year['pending_pixels'] = [day for day in year['pixels'] if day > as_of.isoformat()]
        year['commits'] = len(year['due_pixels']) * year['commits_per_pixel']
    canonical = [(y['year'], y['text'], y['pixels']) for y in sorted(years, key=lambda x: x['year'])]
    fingerprint = hashlib.sha256(json.dumps(canonical, separators=(',', ':')).encode()).hexdigest()
    return dict(version=1, as_of=as_of.isoformat(), layout_hash=fingerprint,
                years=sorted(years, key=lambda y: -y['year']), background=background,
                activity_supplied=bool(activity), total_commits=sum(y['commits'] for y in years))


def svg(year, plan):
    step, size, left, top = 16, 12, 38, 30
    width, height = left + year['columns'] * step + 10, 155
    start = date.fromisoformat(year['grid_start'])
    pixels = set(year['pixels'])
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
           f'role="img" aria-label="{year["year"]}: {html.escape(year["text"])}">',
           '<style>text{font:10px system-ui;fill:#68776c}.future{fill:#fff;stroke:#216e39;stroke-dasharray:2 2}.pixel{fill:#216e39}.activity{fill:#9be9a8}</style>']
    for row, label in ((1, 'Mon'), (3, 'Wed'), (5, 'Fri')):
        out.append(f'<text x="0" y="{top + row * step + 10}">{label}</text>')
    last_month = None
    for col in range(year['columns']):
        for row in range(7):
            day = start + timedelta(weeks=col, days=row)
            if day.year != year['year']:
                continue
            key = day.isoformat()
            if day.month != last_month:
                out.append(f'<text x="{left + col * step}" y="17">{day.strftime("%b")}</text>')
                last_month = day.month
            count = plan['background'].get(key, 0)
            future = key > plan['as_of']
            kind = ('future' if future else 'pixel') if key in pixels else ('activity' if count else 'blank')
            edge = col in (0, year['columns'] - 1)
            fill = '#f1f3f0' if edge else '#e8eee7'
            title = f'{key} · {count} other contributions'
            if key in pixels:
                title += f' · {year["commits_per_pixel"]} art commits' + (' (planned)' if future else '')
            if edge:
                title += ' · reserved edge week'
            out.append(f'<rect class="{kind}" x="{left + col * step}" y="{top + row * step}" '
                       f'width="{size}" height="{size}" rx="2" fill="{fill}"><title>{title}</title></rect>')
    return ''.join(out) + '</svg>'


def write_preview(plan, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    cards = []
    for year in plan['years']:
        graphic = svg(year, plan)
        (output / f'{year["year"]}.svg').write_text(graphic)
        status = 'Ready through cutoff' if not year['pending_pixels'] else f'{len(year["pending_pixels"])} future pixels'
        cards.append(f'<article><header><span class="year">{year["year"]}</span><h2>{html.escape(year["text"])}</h2>'
                     f'<span class="status">{status}</span></header>{graphic}<footer><span>{year["width"]} weeks · '
                     f'{len(year["pixels"])} letter pixels</span><span>{year["first_pixel"]} → {year["last_pixel"]}'
                     f'</span><span>{year["commits_per_pixel"]} commits / pixel</span></footer></article>')
    page = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Contribution banners · vencolini</title><style>
*{box-sizing:border-box}body{margin:0;background:#f6f7f2;color:#183b27;font:15px/1.55 system-ui,-apple-system,sans-serif}
main{max-width:1050px;margin:64px auto;padding:0 28px 60px}.eyebrow{letter-spacing:.16em;font-size:11px;font-weight:700;color:#548064}
h1{font-size:clamp(32px,5vw,52px);line-height:1.12;letter-spacing:-.04em;font-weight:650;margin:18px 0}
.intro{max-width:740px;color:#637369}.summary{display:flex;flex-wrap:wrap;gap:12px;margin:28px 0 36px}.summary span{background:#e7eee3;border-radius:5px;padding:8px 14px;font-size:13px}
article{background:white;border:1px solid #dde5db;border-radius:10px;padding:24px;margin:18px 0;overflow:auto}
header,footer{display:flex;align-items:center;gap:18px}header{margin-bottom:20px}.year{font:600 17px ui-monospace,monospace;color:#7b8a7e}h2{font-size:19px;letter-spacing:.06em;margin:0}.status{margin-left:auto;font-size:11px;color:#637369}
svg{display:block;width:100%;min-width:650px}footer{justify-content:space-between;font-size:11px;color:#738177;border-top:1px solid #edf0ea;padding-top:13px}
.note{font-size:13px;color:#637369;max-width:800px}.key{display:flex;align-items:center;gap:10px;flex-wrap:wrap;font-size:12px;color:#637369;margin:22px 0}.key i{width:12px;height:12px;display:inline-block;border-radius:2px;background:#216e39}.key .other{background:#9be9a8}.key .planned{background:white;border:1px dashed #216e39}
@media(max-width:640px){main{margin:28px auto;padding:0 14px 30px}article{padding:16px}header{gap:12px}.status{display:none}footer{min-width:650px}h2{font-size:16px}}
</style><main><div class="eyebrow">VENCOLINI / CONTRIBUTION CANVAS</div><h1>A few words.<br>Fourteen years of pixels.</h1>
<p class="intro">Your GitHub calendar, drawn one day at a time. Each column is a week; each row is a weekday. Both edge weeks stay clear of lettering.</p>
SUMMARY<div class="key"><i></i> Lettering <i class="other"></i> Other activity <i class="planned"></i> Future lettering</div>
<p class="note">Design preview — GitHub assigns the actual color levels. Other activity is shown in a single light shade for context. Real contributions remain; only the old generator’s random commits are subtracted in this replacement preview. Select a specific year on GitHub to see that year’s banner.</p>
CARDS<p class="note">No future-dated commits are generated. The same layout can be continued later without shifting letters or duplicating pixels. This is contribution art, not a record of work performed on these dates.</p></main></html>'''
    summary = (f'<div class="summary"><span>{len(plan["years"])} year designs</span>'
               f'<span>Cutoff: {plan["as_of"]} UTC</span><span>{plan["total_commits"]:,} planned art commits through cutoff</span></div>')
    page = page.replace('Fourteen years of pixels.', f'{len(plan["years"])} years of pixels.')
    page = page.replace('SUMMARY', summary).replace('CARDS', ''.join(cards))
    (output / 'index.html').write_text(page)
    (output / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
