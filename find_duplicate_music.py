#!/usr/bin/env python3

import argparse
import csv
import hashlib
import html
from collections import defaultdict
from datetime import datetime
from pathlib import Path

AUDIO_EXTENSIONS = {
    ".mp3", ".flac", ".m4a", ".aac", ".ogg", ".wav", ".wma", ".opus", ".alac"
}

CHUNK_SIZE = 1024 * 1024  # 1 MB


def is_audio_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS


def file_hash(path: Path, algo: str = "sha256") -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        while chunk := f.read(CHUNK_SIZE):
            h.update(chunk)
    return h.hexdigest()


def scan_audio_files(root: Path):
    for path in root.rglob("*"):
        if is_audio_file(path):
            yield path


def format_bytes(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def build_file_record(path: Path, algo: str):
    stat = path.stat()
    return {
        "path": path,
        "size": stat.st_size,
        "mtime": stat.st_mtime,
        "mtime_iso": datetime.fromtimestamp(stat.st_mtime).isoformat(sep=" ", timespec="seconds"),
        "hash": file_hash(path, algo),
    }


def find_duplicates(root: Path, algo: str = "sha256"):
    size_map = defaultdict(list)

    print(f"Scanning audio files under: {root}")
    for path in scan_audio_files(root):
        try:
            size_map[path.stat().st_size].append(path)
        except OSError as e:
            print(f"Could not access {path}: {e}")

    candidate_groups = {size: paths for size, paths in size_map.items() if len(paths) > 1}

    hash_map = defaultdict(list)
    for size, paths in candidate_groups.items():
        print(f"Hashing {len(paths)} files with size {size} bytes...")
        for path in paths:
            try:
                record = build_file_record(path, algo)
                hash_map[(record["size"], record["hash"])].append(record)
            except OSError as e:
                print(f"Could not read {path}: {e}")

    duplicates = {key: records for key, records in hash_map.items() if len(records) > 1}
    return duplicates


def choose_keep_and_delete(records, mode):
    records_sorted = sorted(records, key=lambda r: (r["mtime"], str(r["path"])))

    if mode == "oldest":
        keep = records_sorted[0]
        delete = records_sorted[1:]
    elif mode == "newest":
        keep = records_sorted[-1]
        delete = records_sorted[:-1]
    elif mode == "first":
        keep = sorted(records, key=lambda r: str(r["path"]))[0]
        delete = [r for r in records if r != keep]
    else:
        keep = None
        delete = []

    return keep, delete


def print_summary(duplicates):
    if not duplicates:
        print("\nNo exact duplicate audio files found.")
        return

    total_groups = len(duplicates)
    extra_files = 0
    wasted_bytes = 0

    print("\nDuplicate groups found:\n")
    for i, ((size, h), records) in enumerate(duplicates.items(), start=1):
        print(f"[Group {i}]")
        print(f"Size : {size} bytes ({format_bytes(size)})")
        print(f"Hash : {h}")
        for record in sorted(records, key=lambda r: str(r["path"])):
            print(f"  - {record['path']}  [modified: {record['mtime_iso']}]")
        print()

        extra_files += len(records) - 1
        wasted_bytes += size * (len(records) - 1)

    print("Summary")
    print(f"  Duplicate groups      : {total_groups}")
    print(f"  Extra duplicate files : {extra_files}")
    print(f"  Potential space saved : {format_bytes(wasted_bytes)}")


def write_csv_report(duplicates, output_file: Path, delete_mode=None):
    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "group",
            "size_bytes",
            "size_human",
            "hash",
            "modified_time",
            "path",
            "recommended_action",
        ])

        for i, ((size, h), records) in enumerate(sorted(duplicates.items(), key=lambda x: (x[0][0], x[0][1])), start=1):
            keep, delete = choose_keep_and_delete(records, delete_mode) if delete_mode else (None, [])
            for record in sorted(records, key=lambda r: str(r["path"])):
                action = ""
                if delete_mode:
                    if keep and record["path"] == keep["path"]:
                        action = "KEEP"
                    elif any(record["path"] == d["path"] for d in delete):
                        action = f"DELETE_{delete_mode.upper()}"
                writer.writerow([
                    i,
                    size,
                    format_bytes(size),
                    h,
                    record["mtime_iso"],
                    str(record["path"]),
                    action,
                ])


def write_html_report(duplicates, output_file: Path, delete_mode=None):
    rows = []

    for i, ((size, h), records) in enumerate(sorted(duplicates.items(), key=lambda x: (x[0][0], x[0][1])), start=1):
        keep, delete = choose_keep_and_delete(records, delete_mode) if delete_mode else (None, [])
        for record in sorted(records, key=lambda r: str(r["path"])):
            action = ""
            if delete_mode:
                if keep and record["path"] == keep["path"]:
                    action = "KEEP"
                elif any(record["path"] == d["path"] for d in delete):
                    action = f"DELETE ({delete_mode})"

            rows.append(f"""
            <tr>
              <td>{i}</td>
              <td>{size}</td>
              <td>{html.escape(format_bytes(size))}</td>
              <td><code>{html.escape(h)}</code></td>
              <td>{html.escape(record["mtime_iso"])}</td>
              <td><code>{html.escape(str(record["path"]))}</code></td>
              <td><strong>{html.escape(action)}</strong></td>
            </tr>
            """)

    doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Duplicate Music Report</title>
<style>
body {{
  font-family: Arial, sans-serif;
  margin: 24px;
  background: #f7f7f7;
  color: #222;
}}
h1 {{
  margin-bottom: 8px;
}}
p {{
  margin-top: 0;
}}
table {{
  border-collapse: collapse;
  width: 100%;
  background: white;
}}
th, td {{
  border: 1px solid #ddd;
  padding: 8px;
  text-align: left;
  vertical-align: top;
}}
th {{
  background: #222;
  color: white;
  position: sticky;
  top: 0;
}}
tr:nth-child(even) {{
  background: #fafafa;
}}
code {{
  font-family: Consolas, monospace;
  font-size: 0.92em;
}}
</style>
</head>
<body>
<h1>Duplicate Music Report</h1>
<p>Generated: {html.escape(datetime.now().isoformat(sep=" ", timespec="seconds"))}</p>
<p>Delete mode recommendation: <strong>{html.escape(delete_mode or "none")}</strong></p>
<table>
  <thead>
    <tr>
      <th>Group</th>
      <th>Size (bytes)</th>
      <th>Size</th>
      <th>Hash</th>
      <th>Modified Time</th>
      <th>Path</th>
      <th>Recommended Action</th>
    </tr>
  </thead>
  <tbody>
    {''.join(rows)}
  </tbody>
</table>
</body>
</html>
"""
    output_file.write_text(doc, encoding="utf-8")


def delete_duplicates(duplicates, mode):
    total_deleted = 0
    total_freed = 0

    for (size, _), records in duplicates.items():
        keep, delete = choose_keep_and_delete(records, mode)

        print(f"\nKeeping: {keep['path']}  [modified: {keep['mtime_iso']}]")
        for record in delete:
            try:
                record["path"].unlink()
                print(f"Deleted: {record['path']}")
                total_deleted += 1
                total_freed += size
            except OSError as e:
                print(f"Failed to delete {record['path']}: {e}")

    print(f"\nDeleted files: {total_deleted}")
    print(f"Freed space  : {format_bytes(total_freed)}")


def main():
    parser = argparse.ArgumentParser(description="Find exact duplicate music files recursively.")
    parser.add_argument("root", help="Root folder to scan")
    parser.add_argument("--algo", default="sha256", help="Hash algorithm (default: sha256)")
    parser.add_argument("--csv", default="duplicate_music_report.csv", help="CSV report output path")
    parser.add_argument("--html", default="duplicate_music_report.html", help="HTML report output path")
    parser.add_argument("--yes", action="store_true", help="Confirm destructive delete actions without interactive prompt")

    delete_group = parser.add_mutually_exclusive_group()
    delete_group.add_argument("--delete-oldest", action="store_true", help="Keep oldest file, delete newer duplicates")
    delete_group.add_argument("--delete-newest", action="store_true", help="Keep newest file, delete older duplicates")
    delete_group.add_argument("--delete-all-but-first", action="store_true", help="Keep first path alphabetically, delete the rest")

    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"Invalid directory: {root}")
        return 1

    delete_mode = None
    if args.delete_oldest:
        delete_mode = "oldest"
    elif args.delete_newest:
        delete_mode = "newest"
    elif args.delete_all_but_first:
        delete_mode = "first"

    duplicates = find_duplicates(root, algo=args.algo)
    print_summary(duplicates)

    csv_path = Path(args.csv).expanduser().resolve()
    html_path = Path(args.html).expanduser().resolve()

    write_csv_report(duplicates, csv_path, delete_mode=delete_mode)
    write_html_report(duplicates, html_path, delete_mode=delete_mode)

    print(f"\nCSV report written to : {csv_path}")
    print(f"HTML report written to: {html_path}")

    if delete_mode and duplicates:
        print("\nWARNING: You are about to permanently delete files.")
        if args.yes:
            delete_duplicates(duplicates, delete_mode)
        else:
            confirm = input(f"Type YES to continue with delete mode '{delete_mode}': ")
            if confirm == "YES":
                delete_duplicates(duplicates, delete_mode)
            else:
                print("Deletion cancelled.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())