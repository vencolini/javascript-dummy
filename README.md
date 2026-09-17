# GitHub contribution banners

Write professional roles and technologies across each year's contribution calendar.
This is deliberate pixel art, replacing the old random dummy-commit generator.

| Year | Banner | Font |
| --- | --- | --- |
| 2026 | AI AGENTS | Compact |
| 2025 | SENIOR | Wide |
| 2024 | SOFTWARE | Wide |
| 2023 | ENGINEER | Wide |
| 2022 | AI ENGINEER | Compact |
| 2021 | TYPESCRIPT | Compact |
| 2020 | JAVASCRIPT | Compact |
| 2019 | FULL STACK | Compact |
| 2018 | NODE JS | Wide |
| 2017 | REACT | Wide |
| 2016 | NEXT JS | Wide |
| 2015 | BACKEND | Wide |
| 2014 | APIS | Wide |
| 2013 | CODE | Wide |

The years are positions on a canvas, not claims about when a technology was used.
2013's drawing starts after this account was created on July 7.

## Preview first

Requires Python 3.9+ and Git. No Python packages or tokens are needed to generate art.

```sh
python3 generate_dummy_commits.py
```

Open `preview/index.html` in a browser. The preview is a self-contained local file;
the directory also contains one SVG per year and a `plan.json` with every pixel date.
Previewing never changes Git history. No command in this project pushes to GitHub.

To preview a different cutoff:

```sh
python3 generate_dummy_commits.py preview --as-of 2026-03-01
```

Future lettering is outlined. Layouts are fixed for the entire year, so a later run
fills missing pixels without moving the earlier letters. The default 2026 design
uses 35 weeks and finishes on September 4, 2026; it is complete by September 17.

## How letters fit

Edit `banners.json` to set each year's `text`, optional `font` (`wide` or `compact`),
`align` (`left`, `center`, `right`), and optional `start_date`.

- Calendars run Sunday–Saturday, with seven rows and one column per week.
- Both the first and last calendar columns are reserved, even if an edge is a full week.
- Letters are seven pixels high, separated by one blank week; words have a three-week gap.
- Oversize messages and unsupported characters fail with an explanation; they never get cropped.
- The wide font usually uses five columns per letter. Compact uses three where readable;
  wider letters such as N, M and W keep five columns.
- Most years have 51 usable columns. Leap years and all possible weekday alignments are supported.

Text changes after applying art require a new replacement history. Adding more
commits cannot erase an old letter. Changing intensity can safely add missing commits.

## Contrast alongside real contributions

The default is 30 art commits on each letter date and zero on background dates.
With a contribution snapshot, each year's target becomes the greater of 30 (or the
configured minimum) and `3 × highest other daily contribution count + 1`.
This targets the highest contribution intensity while leaving real activity visible.

GitHub selects the final shades; it does not expose a fixed "make this dark green"
setting. Other activity is shown in a single light shade in the preview, not as a
prediction of GitHub's precise colors. Later heavy real activity can change contrast.

Optionally fetch daily totals using the GitHub CLI, already signed in with `gh auth login`:

```sh
python3 fetch_activity.py
python3 generate_dummy_commits.py preview --activity .local/activity.json
```

For a preview of replacing the **old random history**, subtract its counts:

```sh
python3 generate_dummy_commits.py preview \
  --activity .local/activity.json --subtract-legacy .
```

Snapshots stay in ignored `.local/` files. They contain aggregate daily totals, not
private repository names. Once the old history is replaced on GitHub, fetch a new
snapshot and omit `--subtract-legacy`. Apply subtracts existing art from a fresh
snapshot before recalibrating, preventing intensity from growing on every run.

## Replace the old generator's history

Simply adding letters to the old random commits would leave noisy background pixels.
`prepare` creates a separate local repository and a verified backup, without changing
any source branch or anything on GitHub:

```sh
# First commit your generator changes so the source worktree is clean.
python3 generate_dummy_commits.py prepare --destination .local/replacement
python3 generate_dummy_commits.py apply --repo .local/replacement
```

For calibrated initial intensity, use the pre-replacement activity snapshot:

```sh
python3 generate_dummy_commits.py apply --repo .local/replacement \
  --activity .local/activity.json --subtract-legacy .
```

Preparation preserves non-art code commits, their trees, author/committer identities,
dates and messages; parent links and therefore commit hashes change. It removes
commits matching the old generator's exact message pattern only after checking their
changed files and, for non-root commits, their patch contents. It also supports
rebuilding this generator's existing art. Merge histories require manual migration.

Outputs next to the destination:

- `replacement-original.bundle`: verified backup of the source repository's refs and history.
- `replacement-migration.json`: preserved commit mapping and the expected remote `main` hash.

Review the preview and replacement before publishing. Replacing the default branch
requires an explicit force push because its history changes. Use the exact previous
remote hash from the migration report to protect against overwriting new remote work:

```sh
git -C .local/replacement push \
  --force-with-lease=refs/heads/main:PREVIOUS_REMOTE_MAIN_HASH origin main:main
```

Do **not** merge the old branch back into the new one: that would restore the random
contributions. Do not push the original history to `gh-pages`, which can also count
toward the profile. The local bundle is the recovery copy. It can be opened with:

```sh
git clone .local/replacement-original.bundle ../recovered-original
```

The generator changes only this repository. Other repositories and their real commits
remain intact. Real project updates in this repository can still create background pixels.

## Continue a partially drawn year

On the clean replacement repository, run:

```sh
python3 generate_dummy_commits.py apply
git push origin main
```

Apply uses today's UTC date by default, refuses future cutoffs and uncommitted work,
and adds only missing art commits. A repeated run with unchanged settings adds zero.
Author and committer timestamps are both at noon UTC (one-second increments per pixel).
The `.banner/` files identify generated art and lock the layout for safe continuation.
The default maximum is 200,000 new commits per run; intensity above 3,600/day is rejected.
There is no automatic scheduled task; run again when more of the design's dates have elapsed.

Commits need an email linked to the GitHub account and must be reachable from the
repository's default branch. Select an individual year on the profile to see a whole
banner; the default rolling past-year view may cut across two designs. GitHub may take
up to 24 hours to update contributions after a push.

Sources: [GitHub contribution criteria](https://docs.github.com/en/account-and-profile/reference/profile-contributions-reference)
and [missing contributions](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/troubleshooting-missing-contributions).

## Verify

```sh
python3 -m unittest discover -s tests -v
```

Tests cover calendar edges, leap years, glyph orientation, actual configured phrases,
stable layouts, future clipping, contrast, idempotency, timestamps, intensity changes,
backup/migration, and refusal to discard non-generator work.
