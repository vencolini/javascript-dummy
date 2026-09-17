import json
import os
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from banner import COMPACT, FONT, layout, lettering, make_plan, write_preview
from generate_dummy_commits import main
from history import git, legacy_counts, paint, prepare_replacement

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT / 'banners.json').read_text())


class CalendarTests(unittest.TestCase):
    def test_every_weekday_alignment_and_leap_year(self):
        for year in range(2000, 2041):
            board = layout(dict(year=year, text='SOFTWARE'))
            start = date.fromisoformat(board['grid_start'])
            self.assertEqual(start.weekday(), 6)
            for key in board['pixels']:
                day = date.fromisoformat(key)
                col, row = divmod((day - start).days, 7)
                self.assertEqual(day.year, year)
                self.assertGreater(col, 0)
                self.assertLess(col, board['columns'] - 1)
                self.assertEqual(row, (day.weekday() + 1) % 7)

    def test_fifty_four_week_year_reserves_both_edges(self):
        board = layout(dict(year=2000, text='A', align='right'))
        self.assertEqual(board['columns'], 54)
        self.assertLessEqual(board['last_pixel'], '2000-12-30')

    def test_known_pixel_dates_and_orientation(self):
        board = layout(dict(year=2026, text='I', font='compact', align='left'))
        self.assertEqual(board['first_pixel'], '2026-01-04')
        self.assertIn('2026-01-10', board['pixels'])
        self.assertNotIn('2026-01-05', board['pixels'])
        self.assertIn('2026-01-12', board['pixels'])

    def test_user_words_all_fit_and_current_year_is_complete(self):
        plan = make_plan(CONFIG, date(2026, 9, 17))
        self.assertEqual([y['year'] for y in plan['years']], list(range(2026, 2012, -1)))
        current = plan['years'][0]
        self.assertEqual(current['text'], 'AI AGENTS')
        self.assertEqual(current['width'], 35)
        self.assertEqual(current['last_pixel'], '2026-09-04')
        self.assertFalse(current['pending_pixels'])
        self.assertGreaterEqual(plan['years'][-1]['first_pixel'], '2013-07-07')

    def test_glyphs_are_rectangular_and_seven_days_high(self):
        for font in (FONT, COMPACT):
            for glyph in font.values():
                rows = glyph.split('/')
                self.assertEqual(len(rows), 7)
                self.assertEqual(len({len(row) for row in rows}), 1)
                self.assertEqual(set(''.join(rows)), {'0', '1'})

    def test_validation_prevents_clipping_and_unsupported_text(self):
        for spec in (dict(year=2026, text='SOFTWARE ENGINEER'),
                     dict(year=2026, text=''), dict(year=2026, text='AI 🚀'),
                     dict(year=2026, text='AI', align='random'),
                     dict(year=2026, text='AI', font='unknown'),
                     dict(year=2026, text='AI', start_date='2025-01-01')):
            with self.assertRaises(ValueError):
                layout(spec)

    def test_plan_does_not_move_as_year_progresses(self):
        early = make_plan(CONFIG, date(2026, 3, 1))
        later = make_plan(CONFIG, date(2026, 9, 17))
        self.assertEqual(early['layout_hash'], later['layout_hash'])
        self.assertEqual(early['years'][0]['pixels'], later['years'][0]['pixels'])
        self.assertTrue(early['years'][0]['pending_pixels'])
        self.assertTrue(all(d <= '2026-03-01' for d in early['years'][0]['due_pixels']))

    def test_background_calibration_subtracts_only_legacy(self):
        plan = make_plan(CONFIG, date(2026, 9, 17),
                         {'2024-03-01': 50, '2025-01-06': 12}, {'2024-03-01': 49})
        self.assertEqual(plan['background']['2024-03-01'], 1)
        self.assertEqual(plan['years'][1]['commits_per_pixel'], 37)
        self.assertEqual(plan['years'][2]['commits_per_pixel'], 30)

    def test_preview_marks_future_and_creates_portable_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = make_plan(CONFIG, date(2026, 3, 1))
            write_preview(plan, tmp)
            self.assertIn('class="future"', (Path(tmp) / '2026.svg').read_text())
            self.assertIn('AI AGENTS', (Path(tmp) / 'index.html').read_text())
            self.assertEqual(json.loads((Path(tmp) / 'plan.json').read_text())['layout_hash'], plan['layout_hash'])


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.repo = Path(self.tmp.name) / 'source'
        self.repo.mkdir()
        git(self.repo, 'init', '-b', 'main')
        git(self.repo, 'config', 'user.name', 'Test User')
        git(self.repo, 'config', 'user.email', 'test@example.com')
        git(self.repo, 'config', 'commit.gpgsign', 'false')
        (self.repo / 'README.md').write_text('Test project\n')
        (self.repo / 'script.js').write_text("console.log('test');")
        self.commit('Initial project')
        self.config = dict(author=dict(name='Test User', email='test@example.com'),
                           commits_per_pixel=2, years=[dict(year=2024, text='I', align='left')])
        self.env = patch.dict(os.environ, {'GITHUB_NAME': 'Test User', 'GITHUB_EMAIL': 'test@example.com'})
        self.env.start()
        self.addCleanup(self.env.stop)

    def commit(self, message):
        git(self.repo, 'add', '.')
        return git(self.repo, 'commit', '-m', message)

    def test_apply_is_incremental_idempotent_and_uses_utc(self):
        first = make_plan(self.config, date(2024, 1, 10))
        self.assertGreater(paint(self.repo, self.config, first), 0)
        head = git(self.repo, 'rev-parse', 'HEAD')
        self.assertEqual(paint(self.repo, self.config, first), 0)
        self.assertEqual(head, git(self.repo, 'rev-parse', 'HEAD'))
        later = make_plan(self.config, date(2024, 2, 1))
        self.assertGreater(paint(self.repo, self.config, later), 0)
        records = git(self.repo, 'log', '--format=%aI%x09%cI%x09%s', '--', '.banner/pixel.json').splitlines()
        self.assertEqual(len(records), later['total_commits'])
        counts = {}
        for record in records:
            author_date, commit_date, subject = record.split('\t')
            self.assertEqual(author_date, commit_date)
            self.assertTrue(author_date.endswith(('+00:00', 'Z')))
            self.assertLessEqual(author_date[:10], '2024-02-01')
            counts[author_date[:10]] = counts.get(author_date[:10], 0) + 1
        self.assertEqual(set(counts), set(later['years'][0]['due_pixels']))
        self.assertEqual(set(counts.values()), {2})
        self.assertEqual(git(self.repo, 'status', '--porcelain'), '')

    def test_rejects_future_apply_dirty_tree_and_changed_layout(self):
        tomorrow = date.today() + timedelta(days=2)
        with self.assertRaisesRegex(ValueError, 'future'):
            paint(self.repo, self.config, make_plan(self.config, tomorrow))
        (self.repo / 'uncommitted.txt').write_text('keep this')
        with self.assertRaisesRegex(ValueError, 'clean'):
            paint(self.repo, self.config, make_plan(self.config, date(2024, 2, 1)))
        self.commit('Keep user file')
        paint(self.repo, self.config, make_plan(self.config, date(2024, 2, 1)))
        self.config['years'][0]['text'] = 'A'
        with self.assertRaisesRegex(ValueError, 'Layout'):
            paint(self.repo, self.config, make_plan(self.config, date(2024, 2, 1)))

    def test_apply_limit_does_not_change_head(self):
        before = git(self.repo, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'limit'):
            paint(self.repo, self.config, make_plan(self.config, date(2024, 2, 1)), max_commits=1)
        self.assertEqual(before, git(self.repo, 'rev-parse', 'HEAD'))

    def test_intensity_can_increase_without_duplicate_sequences(self):
        plan = make_plan(self.config, date(2024, 2, 1))
        paint(self.repo, self.config, plan)
        self.config['commits_per_pixel'] = 3
        brighter = make_plan(self.config, date(2024, 2, 1))
        self.assertEqual(paint(self.repo, self.config, brighter), len(brighter['years'][0]['due_pixels']))
        self.assertEqual(paint(self.repo, self.config, brighter), 0)

    def test_fresh_snapshot_preview_does_not_amplify_existing_art(self):
        plan = make_plan(self.config, date(2024, 2, 1))
        paint(self.repo, self.config, plan)
        config_path = Path(self.tmp.name) / 'config.json'
        config_path.write_text(json.dumps(self.config))
        activity_path = Path(self.tmp.name) / 'activity.json'
        activity_path.write_text(json.dumps({d: 2 for d in plan['years'][0]['due_pixels']}))
        output = Path(self.tmp.name) / 'preview'
        self.assertEqual(main(['preview', '--repo', str(self.repo), '--config', str(config_path),
                              '--activity', str(activity_path), '--output', str(output),
                              '--as-of', '2024-02-01']), 0)
        preview = json.loads((output / 'plan.json').read_text())
        self.assertEqual(preview['years'][0]['commits_per_pixel'], 2)
        self.assertEqual(preview['total_commits'], plan['total_commits'])

    def test_migration_preserves_code_and_source_with_verified_backup(self):
        (self.repo / 'script.js').write_text("console.log('test');\n// Commit on 2024-01-01T12:00:00\n")
        self.commit('Dummy commit on 2024-01-01T12:00:00')
        (self.repo / 'README.md').write_text('Improved project\n')
        self.commit('Real code update')
        git(self.repo, 'remote', 'add', 'origin', 'https://github.com/example/test.git')
        git(self.repo, 'update-ref', 'refs/remotes/origin/main', 'HEAD')
        source_head = git(self.repo, 'rev-parse', 'HEAD')
        with self.assertRaisesRegex(ValueError, 'legacy'):
            paint(self.repo, self.config, make_plan(self.config, date(2024, 2, 1)))
        destination = Path(self.tmp.name) / 'replacement'
        report = prepare_replacement(self.repo, destination)
        self.assertEqual(report['removed_commits'], 1)
        self.assertEqual(report['preserved_commits'], 2)
        self.assertEqual(git(self.repo, 'rev-parse', 'HEAD'), source_head)
        self.assertEqual(git(destination, 'rev-list', '--count', 'HEAD'), '2')
        self.assertEqual(git(destination, 'rev-parse', 'HEAD^{tree}'), git(self.repo, 'rev-parse', 'HEAD^{tree}'))
        self.assertEqual(legacy_counts(destination), {})
        self.assertTrue(Path(report['backup']).is_file())
        git(self.repo, 'bundle', 'verify', report['backup'])

    def test_migration_refuses_disguised_real_work(self):
        (self.repo / 'script.js').write_text('const realWork = true;\n')
        self.commit('Dummy commit on 2024-01-01T12:00:00')
        with self.assertRaisesRegex(ValueError, 'non-generator'):
            prepare_replacement(self.repo, Path(self.tmp.name) / 'replacement')


if __name__ == '__main__':
    unittest.main()
