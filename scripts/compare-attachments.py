#!/usr/bin/env python3
"""Compare exported WeChat file messages with a local course directory."""

import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
import sys
import xml.etree.ElementTree as ET


class InputError(Exception):
    pass


class IdentityError(Exception):
    pass


def md5_hasher():
    try:
        return hashlib.md5(usedforsecurity=False)
    except TypeError:  # Python versions before the usedforsecurity keyword.
        return hashlib.md5()


def hash_file(path):
    md5, sha256, size = md5_hasher(), hashlib.sha256(), 0
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as stream:
        while True:
            block = stream.read(1024 * 1024)
            if not block:
                break
            size += len(block)
            md5.update(block)
            sha256.update(block)
    return md5.hexdigest(), size, sha256.hexdigest()


def values_below(node, name):
    return [child.text.strip() for child in node.iter()
            if child is not node and child.tag.rsplit("}", 1)[-1].lower() == name
            and child.text and child.text.strip()]


def xml_identity(raw):
    """Return XML md5, size, title; sender prefixes before XML are discarded."""
    if not isinstance(raw, str) or not raw.strip():
        return None, None, None
    match = re.search(r"<\?xml\b|<msg(?:\s|>)", raw, re.I)
    if not match:
        if "<" in raw:
            raise IdentityError("raw_content is not parseable message XML")
        return None, None, None
    xml = raw[match.start():]
    if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml, re.I):
        raise IdentityError("message XML declarations are not accepted")
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise IdentityError("message XML is malformed") from exc
    appmsgs = [node for node in root.iter()
               if node.tag.rsplit("}", 1)[-1].lower() == "appmsg"]
    md5s, sizes, titles = [], [], []
    for appmsg in appmsgs:
        md5s.extend(values_below(appmsg, "md5"))
        for node in appmsg.iter():
            tag = node.tag.rsplit("}", 1)[-1].lower()
            if tag == "totallen" and node.text and node.text.strip():
                sizes.append(node.text.strip())
            elif tag == "title" and node.text and node.text.strip():
                titles.append(node.text.strip())
    return unique(md5s, "XML MD5"), unique(sizes, "XML size"), titles[0] if titles else None


def unique(values, label):
    if not values:
        return None
    normalized = {value.lower() for value in values}
    if len(normalized) != 1:
        raise IdentityError("conflicting " + label + " values in message XML")
    return next(iter(normalized))


def parse_md5(value, label):
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", value.strip()):
        raise IdentityError("invalid " + label)
    return value.strip().lower()


def parse_size(value, label):
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]+", str(value).strip()):
        raise IdentityError("invalid " + label)
    return int(value)


def attachment_identity(message):
    media = message.get("media") if isinstance(message.get("media"), dict) else {}
    xml_md5, xml_size, xml_title = xml_identity(message.get("raw_content"))
    xml_md5 = parse_md5(xml_md5, "XML MD5")
    xml_size = parse_size(xml_size, "XML size")
    media_md5 = parse_md5(media.get("md5"), "media.md5")
    media_size = parse_size(media.get("bytes"), "media.bytes")
    if xml_md5 and media_md5 and xml_md5 != media_md5:
        raise IdentityError("XML MD5 conflicts with media.md5")
    if xml_size is not None and media_size is not None and xml_size != media_size:
        raise IdentityError("XML size conflicts with media.bytes")
    md5 = xml_md5 or media_md5
    size = xml_size if xml_size is not None else media_size
    if md5 is None or size is None:
        raise IdentityError("message MD5 and size are required")
    return md5, size, media, xml_title


def safe_source_path(root, src):
    if not isinstance(src, str) or not src.strip():
        raise FileNotFoundError("media.src is missing")
    src = src.strip()
    if (os.path.isabs(src) or PureWindowsPath(src).is_absolute()
            or "\\" in src or "\x00" in src):
        raise InputError("media.src must be a relative path")
    candidate = root / src
    try:
        resolved = candidate.resolve(strict=True)
    except FileNotFoundError:
        raise
    except (OSError, RuntimeError) as exc:
        raise InputError("media.src cannot be safely resolved") from exc
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise InputError("media.src resolves outside the archive") from exc
    return resolved


def scan_course_dir(root):
    by_name, by_sha, warnings = {}, {}, []
    complete = True

    def walk_error(exc):
        nonlocal complete
        path = os.path.abspath(exc.filename or root)
        if path == str(root):
            raise InputError("course directory is not readable") from exc
        complete = False
        try:
            rel = Path(path).relative_to(root).as_posix()
        except ValueError:
            rel = "<subdirectory>"
        warnings.append({"path": rel, "error": exc.strerror or type(exc).__name__})

    for current, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if not os.path.islink(os.path.join(current, d)))
        for name in sorted(names):
            path = Path(current) / name
            try:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    continue
            except OSError as exc:
                complete = False
                warnings.append({"path": path.relative_to(root).as_posix(),
                                 "error": exc.strerror or type(exc).__name__})
                continue
            rel = path.relative_to(root).as_posix()
            by_name.setdefault(name, []).append(rel)
            try:
                _, _, digest = hash_file(path)
            except OSError as exc:
                complete = False
                warnings.append({"path": rel, "error": exc.strerror or type(exc).__name__})
                continue
            by_sha.setdefault(digest, []).append(rel)
    return by_name, by_sha, complete, warnings


def archive_paths(value):
    supplied = Path(value).expanduser()
    try:
        supplied = supplied.resolve(strict=True)
    except OSError as exc:
        raise InputError("archive path does not exist or cannot be read") from exc
    if supplied.is_dir():
        root, chat_json = supplied, supplied / "chat.json"
    else:
        chat_json = supplied
        root = supplied.parent
    if not chat_json.is_file():
        raise InputError("archive must be chat.json or its parent directory containing chat.json")
    try:
        with chat_json.open("r", encoding="utf-8-sig") as stream:
            data = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise InputError("cannot read a valid UTF-8 chat.json") from exc
    if not isinstance(data, dict) or not isinstance(data.get("messages"), list):
        raise InputError("chat.json must contain a messages array")
    return root.resolve(), chat_json.resolve(), data


def filename_of(media, xml_title):
    value = media.get("filename")
    if not isinstance(value, str) or not value.strip():
        value = xml_title
    if not isinstance(value, str) or not value.strip():
        return None
    # Treat both separators as path delimiters; only the attachment's name is needed.
    return re.split(r"[/\\]", value.strip())[-1] or None


def compare_one(message, root, by_name, by_sha, scan_complete):
    media = message.get("media") if isinstance(message.get("media"), dict) else {}
    try:
        _, _, xml_title = (None, None, None)
        # Resolve first so a genuinely missing local source is reported as unavailable.
        source = safe_source_path(root, media.get("src"))
    except FileNotFoundError as exc:
        source_status, source_reason, digest = "unavailable", str(exc), None
        media, xml_title = media, None
    except InputError as exc:
        source_status, source_reason, digest = "unverified", str(exc), None
        xml_title = None
    else:
        try:
            expected_md5, expected_size, media, xml_title = attachment_identity(message)
            info = source.stat()
            if not stat.S_ISREG(info.st_mode):
                raise IdentityError("media.src is not a regular file")
            actual_md5, actual_size, actual_sha = hash_file(source)
            if actual_md5 != expected_md5 or actual_size != expected_size:
                raise IdentityError("source MD5 or size does not match message metadata")
            source_status, source_reason, digest = "verified", None, actual_sha
        except IdentityError as exc:
            source_status, source_reason, digest = "unverified", str(exc), None
        except OSError:
            source_status, source_reason, digest = "unverified", "source file cannot be read", None
    filename = filename_of(media, xml_title)
    name_candidates = sorted(by_name.get(filename, [])) if filename else []
    matches = sorted(by_sha.get(digest, [])) if digest else []
    if source_status != "verified":
        directory_status, reason = "unverifiable", source_reason
    elif matches:
        directory_status, reason = "matched", None
    elif not scan_complete:
        directory_status, reason = "unverifiable", "course directory scan incomplete"
    elif name_candidates:
        directory_status, reason = "name_conflict", "same-name files have different content"
    else:
        directory_status, reason = "absent", "no same-name or content match"
    return {
        "message_key": message.get("message_key"),
        "time": message.get("time"),
        "sender": message.get("sender"),
        "filename": filename,
        "source_status": source_status,
        "directory_status": directory_status,
        "sha256": digest,
        "matches": matches,
        "name_candidates": name_candidates,
        "reason": reason,
    }


def safe_meta(meta):
    if not isinstance(meta, dict):
        return {}
    result = {}
    fields = ("peer", "conversation_id", "count", "start", "end", "timezone",
              "source_rows", "duplicates_removed", "ready", "scope",
              "limitations", "unmatched_databases", "counts")
    for key in fields:
        value = meta.get(key)
        if isinstance(value, (str, int, float)) and not isinstance(value, bool):
            result[key] = value
        elif isinstance(value, bool) or (isinstance(value, list)
                and all(isinstance(item, str) for item in value)):
            result[key] = value
        elif key == "counts" and isinstance(value, dict) and all(
                isinstance(item, (int, float)) and not isinstance(item, bool)
                for item in value.values()):
            result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", required=True, help="chat.json or its parent directory")
    parser.add_argument("--course-dir", required=True, help="local course directory to compare")
    args = parser.parse_args()
    try:
        root, chat_json, data = archive_paths(args.archive)
        course_dir = Path(args.course_dir).expanduser().resolve(strict=True)
        if not course_dir.is_dir():
            raise InputError("course-dir must be a readable directory")
        by_name, by_sha, scan_complete, warnings = scan_course_dir(course_dir)
        file_messages = [m for m in data["messages"]
                         if isinstance(m, dict) and m.get("type") == "file"]
        files = [compare_one(m, root, by_name, by_sha, scan_complete) for m in file_messages]
        summary = {status: sum(row["directory_status"] == status for row in files)
                   for status in ("matched", "absent", "name_conflict", "unverifiable")}
        summary = {"total": len(files), **summary}
        result = {
            "schema_version": 1,
            "archive": str(root),
            "course_dir": str(course_dir),
            "coverage": {"meta": safe_meta(data.get("meta")),
                         "messages": len(data["messages"]), "file_messages": len(files)},
            "summary": summary,
            "files": files,
            "warnings": warnings,
        }
        sys.stdout.write(json.dumps(result, ensure_ascii=True, separators=(",", ":")) + "\n")
    except (InputError, OSError) as exc:
        print("error: " + str(exc), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
