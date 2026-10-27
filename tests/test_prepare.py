"""Offline behavior checks: evidence readiness is not task completion."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/prepare-check.py'


class PrepareTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.image = self.root / 'screenshot.png'
        self.image.write_bytes(b'synthetic image placeholder')

    def tearDown(self):
        self.temp.cleanup()

    def run_gate(self, *args, discovery=False):
        command = [sys.executable, str(SCRIPT), '--source-config', str(self.root / 'missing.json')]
        if not discovery:
            command.append('--no-discovery')
        p = subprocess.run(command + list(args), capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stderr, '')
        return json.loads(p.stdout)

    def archive(self, folder, name='Project A', group='a@chatroom', end='2026-10-27 12:00:00'):
        folder.mkdir(parents=True)
        data = {'meta': {'peer': name, 'conversation_id': group, 'start': '2026-09-27 01:52:00',
                         'end': end, 'timezone': 'Asia/Shanghai', 'count': 1,
                         'scope': '本机现存记录', 'unmatched_databases': []},
                'messages': [{'message_key': 'fixture:1', 'type': 'text', 'text': 'fixture only'}]}
        (folder / 'chat.json').write_text(json.dumps(data))
        (folder / 'report.json').write_text(json.dumps(data['meta']))
        return folder / 'chat.json'

    def test_no_vision_no_text_is_blocked(self):
        d = self.run_gate('--screenshot', str(self.image), '--image-support', 'unavailable')
        self.assertEqual(d['status'], 'blocked')
        self.assertEqual(d['evidence_scope'], 'none')
        self.assertFalse(d['can_claim_task_complete'])

    def test_unknown_vision_does_not_become_readable(self):
        d = self.run_gate('--screenshot', str(self.image))
        self.assertEqual(d['status'], 'blocked')
        self.assertEqual(d['next_action'], 'ocr_or_request_text')

    def test_readable_screenshot_is_only_partial(self):
        d = self.run_gate('--screenshot', str(self.image), '--image-support', 'available')
        self.assertEqual(d['status'], 'partial')
        self.assertEqual(d['evidence_scope'], 'screenshot_only')
        self.assertFalse(d['can_claim_file_audit'])

    def test_ocr_text_has_explicit_screenshot_scope(self):
        ocr = self.root / 'ocr.json'
        ocr.write_text(json.dumps({'images': [{'path': str(self.image), 'text': 'recognized fixture'}]}))
        d = self.run_gate('--screenshot', str(self.image), '--ocr-text', str(ocr))
        self.assertEqual(d['evidence_scope'], 'screenshot_ocr')
        self.assertEqual(d['status'], 'partial')

    def test_archive_takes_precedence_over_screenshot(self):
        archive = self.archive(self.root / 'archive')
        d = self.run_gate('--archive', str(archive), '--screenshot', str(self.image))
        self.assertEqual(d['status'], 'ready_for_analysis')
        self.assertEqual(d['evidence_scope'], 'local_archive')
        self.assertEqual(d['message_count'], 1)
        self.assertFalse(d['can_claim_task_complete'])
        self.assertFalse(d['can_claim_full_history'])

    def test_wrong_group_cannot_be_used(self):
        archive = self.archive(self.root / 'archive')
        d = self.run_gate('--archive', str(archive), '--group-id', 'other@chatroom')
        self.assertEqual(d['status'], 'blocked')

    def test_same_name_different_ids_needs_selection(self):
        archives = self.root / 'archives'
        self.archive(archives / 'first', group='a@chatroom')
        self.archive(archives / 'second', group='b@chatroom')
        d = self.run_gate('--archive-root', str(archives), '--group-name', 'Project A')
        self.assertEqual(d['status'], 'needs_selection')
        self.assertEqual(len(d['candidates']), 2)

    def test_latest_archive_for_exact_group(self):
        archives = self.root / 'archives'
        self.archive(archives / 'old', end='2026-09-27 12:00:00')
        latest = self.archive(archives / 'new')
        d = self.run_gate('--archive-root', str(archives), '--group-id', 'a@chatroom')
        self.assertEqual(d['selected_archive'], str(latest.resolve()))

    def test_configured_exporter_not_mistaken_for_missing_connector(self):
        project = self.root / 'wmr'
        entry = project / 'scripts/multimodal/export_full.py'
        entry.parent.mkdir(parents=True)
        entry.write_text('raise SystemExit(99)\n')
        config = self.root / 'source.json'
        config.write_text(json.dumps({'wmr_project': str(project), 'wmr_python': sys.executable,
                                      'token': 'SECRET-MUST-NOT-LEAK'}))
        d = self.run_gate('--source-config', str(config), '--group-name', 'Project A',
                          '--screenshot', str(self.image), '--image-support', 'available')
        self.assertEqual(d['status'], 'needs_export')
        self.assertEqual(d['next_action'], 'inspect_configured_exporter')
        self.assertNotIn('SECRET-MUST-NOT-LEAK', json.dumps(d))

    def test_no_query_does_not_scan_unrelated_archives(self):
        archives = self.root / 'archives'
        self.archive(archives / 'unrelated')
        d = self.run_gate('--archive-root', str(archives))
        self.assertEqual(d['candidates'], [])
        self.assertEqual(d['status'], 'blocked')

    def test_virtual_environment_interpreter_path_is_preserved(self):
        project = self.root / 'wmr'
        entry = project / 'scripts/multimodal/export_full.py'
        entry.parent.mkdir(parents=True)
        entry.write_text('raise SystemExit(99)\n')
        interpreter = self.root / 'venv/bin/python'
        interpreter.parent.mkdir(parents=True)
        interpreter.symlink_to(sys.executable)
        config = self.root / 'source.json'
        config.write_text(json.dumps({'wmr_project': str(project), 'wmr_python': str(interpreter)}))
        d = self.run_gate('--source-config', str(config), '--group-name', 'Project A')
        self.assertEqual(d['exporter_candidate']['python'], str(interpreter.absolute()))

    def test_malformed_group_identity_is_blocked(self):
        archive = self.archive(self.root / 'archive')
        data = json.loads(archive.read_text())
        data['meta']['conversation_id'] = {'unexpected': 'object'}
        archive.write_text(json.dumps(data))
        d = self.run_gate('--archive', str(archive))
        self.assertEqual(d['status'], 'blocked')

    def test_no_input_writes(self):
        archive = self.archive(self.root / 'archive')
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.root.rglob('*') if p.is_file()}
        self.run_gate('--archive', str(archive))
        after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_fresh_course_routes_to_external_wce_installation(self):
        d = self.run_gate('--group-name', 'Example course')
        self.assertEqual(d['status'], 'needs_install')
        self.assertEqual(d['next_action'], 'check_environment_and_install_external_wce')
        self.assertIn('docs/INSTALL.md', d['installation_guide'])
        self.assertFalse(d['can_claim_task_complete'])

    def test_installed_wce_without_config_routes_to_setup(self):
        app = self.root / 'WeChatChatkit.app'
        app.mkdir()
        d = self.run_gate('--group-name', 'Example course', '--wce-app', str(app))
        self.assertEqual(d['status'], 'needs_setup')
        self.assertEqual(d['next_action'], 'guide_wce_first_run_permissions_and_local_key_import')

    def test_configured_wce_app_routes_to_export(self):
        app = self.root / 'WeChatChatkit.app'
        app.mkdir()
        settings = self.root / 'settings.json'
        settings.write_text(json.dumps({'db_storage': '/synthetic/account/db_storage',
                                         'output_dir': str(self.root/'archives')}))
        d = self.run_gate('--group-name', 'Example course', '--wce-app', str(app),
                          '--wce-settings', str(settings))
        self.assertEqual(d['status'], 'needs_export')
        self.assertEqual(d['next_action'], 'export_selected_group_with_wce')

    def test_screenshot_default_identifies_group_then_continues_wce_workflow(self):
        d = self.run_gate('--screenshot', str(self.image), '--image-support', 'available')
        self.assertEqual(d['next_action'], 'identify_group_then_bootstrap_wce')

    def test_explicit_screenshot_only_does_not_install_wce(self):
        d = self.run_gate('--group-name', 'Example course', '--screenshot-only',
                          '--screenshot', str(self.image), '--image-support', 'available')
        self.assertEqual(d['status'], 'partial')
        self.assertEqual(d['next_action'], 'summarize_visible_evidence_only')


if __name__ == '__main__':
    unittest.main()
