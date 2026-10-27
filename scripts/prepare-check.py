#!/usr/bin/env python3
"""Read-only input gate for course/project checks; never performs the analysis."""
import argparse
import json
import os
from pathlib import Path
import sys


def read_json(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        return json.load(f)


def matches(meta, args):
    return (not args.group_id or meta.get('conversation_id') == args.group_id) and (
        not args.group_name or meta.get('peer') == args.group_name)


def inspect_archive(path, args, metadata_only=False):
    path = Path(path).expanduser()
    if path.is_dir():
        path = path / 'chat.json'
    path = path.resolve()
    metadata = path.with_name('report.json')
    data = read_json(metadata if metadata_only and metadata.is_file() else path)
    meta = data if metadata_only and metadata.is_file() else data.get('meta', {})
    if not isinstance(meta, dict) or not matches(meta, args):
        return None
    if not isinstance(meta.get('conversation_id'), str) or not meta['conversation_id'].strip():
        raise ValueError('archive group identity is missing or invalid')
    result = {'path': str(path), 'peer': meta.get('peer'),
              'group_id': meta.get('conversation_id'), 'start': meta.get('start'),
              'end': meta.get('end'), 'timezone': meta.get('timezone')}
    if metadata_only:
        return result
    messages = data.get('messages')
    if not isinstance(messages, list) or not all(isinstance(m, dict) for m in messages):
        raise ValueError('archive must contain an array of message objects')
    if not messages:
        raise ValueError('archive contains no messages')
    if not result['group_id']:
        raise ValueError('archive group identity is missing; confirm the source before analysis')
    result['message_count'] = len(messages)
    result['coverage_warnings'] = []
    if meta.get('count') not in (None, len(messages)):
        result['coverage_warnings'].append('declared count differs from messages array')
    if meta.get('unmatched_databases'):
        result['coverage_warnings'].append('some source databases were not readable')
    limitations = meta.get('limitations', [])
    if isinstance(limitations, list):
        result['coverage_warnings'].extend(x for x in limitations if isinstance(x, str))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive')
    p.add_argument('--archive-root', action='append', default=[])
    p.add_argument('--group-id')
    p.add_argument('--group-name')
    p.add_argument('--screenshot', action='append', default=[])
    p.add_argument('--image-support', choices=['available', 'unavailable', 'unknown'], default='unknown')
    p.add_argument('--ocr-text', help='local OCR JSON output or UTF-8 text; never a full chat archive')
    p.add_argument('--source-config', default=str(Path.home() / '.config/class-check/source.json'))
    p.add_argument('--no-discovery', action='store_true', help='skip standard WMR application config discovery')
    args = p.parse_args()
    result = {'status': 'blocked', 'evidence_scope': 'none', 'selected_archive': None,
              'message_count': 0, 'candidates': [], 'exporter_candidate': None,
              'can_claim_task_complete': False, 'can_claim_full_history': False,
              'can_claim_file_audit': False, 'next_action': 'provide_source', 'warnings': []}
    config = {}
    config_path = Path(args.source_config).expanduser()
    if config_path.is_file():
        try:
            config = read_json(config_path)
            if not isinstance(config, dict):
                raise ValueError('source config must be an object')
        except (OSError, ValueError) as e:
            result['warnings'].append('source config is unreadable or invalid: ' + type(e).__name__)
            config = {}
    # Only allow-listed paths are used; credentials and other fields are never emitted.
    roots = list(args.archive_root)
    configured_roots = config.get('archive_roots', [])
    if isinstance(configured_roots, list):
        roots.extend(x for x in configured_roots if isinstance(x, str))
    if not args.no_discovery:
        app_config = Path.home() / 'Library/Application Support/WeChatChatkit/settings.json'
        if app_config.is_file():
            try:
                output = read_json(app_config).get('output_dir')
                if isinstance(output, str):
                    roots.append(output)
                    result['warnings'].append('existing WMR output path discovered; no connector required to inspect archives')
            except (OSError, ValueError, AttributeError):
                result['warnings'].append('existing WMR settings could not be read')
    project = config.get('wmr_project') or os.environ.get('WMR_PROJECT')
    python = config.get('wmr_python') or os.environ.get('WMR_PYTHON')
    if isinstance(project, str) and isinstance(python, str):
        entry = Path(project).expanduser() / 'scripts/multimodal/export_full.py'
        interpreter = Path(python).expanduser()
        if entry.is_file() and interpreter.is_file():
            result['exporter_candidate'] = {'entry': str(entry.resolve()),
                                             'python': str(interpreter.absolute()),
                                             'interface_verified': False}
    if args.archive:
        try:
            selected = inspect_archive(args.archive, args)
            if selected is None:
                raise ValueError('archive identity does not match the requested group')
            result.update(status='ready_for_analysis', evidence_scope='local_archive',
                          selected_archive=selected['path'], message_count=selected['message_count'],
                          coverage=selected, next_action='read_selected_archive')
        except (OSError, ValueError, TypeError, AttributeError) as e:
            result['warnings'].append('explicit archive rejected: ' + str(e))
            result['next_action'] = 'confirm_or_repair_source'
        print(json.dumps(result, ensure_ascii=False))
        return 0
    if args.group_id or args.group_name:
        candidates = {}
        for root in dict.fromkeys(roots):
            root = Path(root).expanduser()
            # Bounded to common export layouts. No home-directory recursive search.
            paths = [root / 'chat.json']
            paths += list(root.glob('*/chat.json'))[:500]
            paths += list(root.glob('*/*/chat.json'))[:500]
            for path in paths:
                if not path.is_file():
                    continue
                # Without report metadata, avoid loading unrelated conversation bodies.
                if not path.with_name('report.json').is_file() and (
                        not args.group_name or args.group_name not in path.parent.name):
                    continue
                try:
                    item = inspect_archive(path, args, metadata_only=True)
                    if item:
                        candidates[item['path']] = item
                except (OSError, ValueError, TypeError, AttributeError):
                    result['warnings'].append('a candidate archive was unreadable; coverage may be incomplete')
        result['candidates'] = list(candidates.values())
        ids = {c['group_id'] for c in candidates.values()}
        if len(ids) > 1 or (ids and None in ids):
            result.update(status='needs_selection', next_action='confirm_group_selection')
        elif candidates:
            # Same group only; use source end timestamps, not copy/installation times.
            newest = max(candidates.values(), key=lambda c: (str(c['end'] or ''), c['path']))
            try:
                selected = inspect_archive(newest['path'], args)
                result.update(status='ready_for_analysis', evidence_scope='local_archive',
                              selected_archive=selected['path'], message_count=selected['message_count'],
                              coverage=selected, next_action='read_selected_archive')
            except (OSError, ValueError, TypeError, AttributeError) as e:
                result['warnings'].append('selected archive rejected: ' + str(e))
                result['next_action'] = 'confirm_or_repair_source'
        elif result['exporter_candidate']:
            result.update(status='needs_export', next_action='inspect_configured_exporter')
    if result['status'] != 'blocked':
        print(json.dumps(result, ensure_ascii=False))
        return 0
    readable_images = [str(Path(x).expanduser()) for x in args.screenshot if Path(x).expanduser().is_file()]
    ocr_ready = False
    if args.ocr_text:
        try:
            text = Path(args.ocr_text).expanduser().read_text(encoding='utf-8')
            if args.ocr_text.lower().endswith('.json'):
                data = json.loads(text)
                ocr_ready = any(isinstance(x.get('text'), str) and x['text'].strip()
                                for x in data.get('images', []) if isinstance(x, dict))
            else:
                ocr_ready = bool(text.strip())
        except (OSError, ValueError, AttributeError):
            result['warnings'].append('OCR text is unreadable or empty')
    if ocr_ready or (readable_images and args.image_support == 'available'):
        result.update(status='partial', evidence_scope='screenshot_ocr' if ocr_ready else 'screenshot_only',
                      next_action='summarize_visible_evidence_only')
    elif readable_images:
        result['next_action'] = 'ocr_or_request_text'
        result['warnings'].append('image input unavailable or unconfirmed; do not invent visible text')
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
