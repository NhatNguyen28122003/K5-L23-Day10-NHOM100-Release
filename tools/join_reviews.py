"""Validate completed personal review files and join them into review_log.csv."""
import argparse
import csv
from pathlib import Path
import re
from tempfile import NamedTemporaryFile

FIELDS = ("image", "type", "verdict", "note")
DRAFT_FIELDS = ("image", "type_guess", "verdict", "note")
TYPES = {"class_swap", "category_swap", "bbox_drift", "missing_box", "instance_merge"}


def collect(files):
    rows, errors = [], []
    notes = {}
    for path in files:
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream, strict=True)
            try:
                if tuple(next(reader, ())) not in (FIELDS, DRAFT_FIELDS):
                    errors.append(f"{path}:1: tiêu đề cần đúng bốn cột theo mẫu")
                    continue
                for fields in reader:
                    location = f"{path}:{reader.line_num}"
                    if len(fields) != 4:
                        errors.append(f"{location}: cần đúng bốn cột, có {len(fields)}")
                        continue
                    image, kind, verdict, note = (value.strip() for value in fields)
                    issues = []
                    if not image:
                        issues.append("thiếu mã ảnh")
                    if kind not in TYPES:
                        issues.append(f"type không hợp lệ: {kind!r}")
                    if verdict not in {"confirmed", "rejected"}:
                        issues.append(f"verdict không hợp lệ: {verdict!r}")
                    reviewer = re.match(r"^\[([^\[\]]+)\]\s*(.*)$", note)
                    if not reviewer or not reviewer[1].strip() or len(reviewer[2].strip()) < 20:
                        issues.append("note cần [tên] và ít nhất 20 ký tự mô tả")
                    if note in notes:
                        issues.append(f"note trùng với {notes[note]}")
                    notes.setdefault(note, location)
                    if issues:
                        errors.append(f"{location}: " + ", ".join(issues))
                    else:
                        rows.append((image, kind, verdict, note))
            except csv.Error as error:
                errors.append(f"{path}:{reader.line_num}: CSV sai định dạng ({error})")
    return rows, errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    output = args.directory / "review_log.csv"
    files = [path for path in sorted(args.directory.glob("review_*.csv"))
             if path.is_file() and path != output]
    if not files:
        parser.error("Không có file review_<tên>.csv")
    rows, errors = collect(files)
    if errors:
        parser.exit(1, "\n".join(errors) + "\n")
    if not rows:
        parser.error("Không có dòng review đã điền")
    temp = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", newline="", dir=output.parent,
                                delete=False) as stream:
            temp = Path(stream.name)
            writer = csv.writer(stream)
            writer.writerow(FIELDS)
            writer.writerows(sorted(rows))
        temp.replace(output)
    finally:
        if temp and temp.exists():
            temp.unlink()
    print(f"{output}: {len(rows)} dòng từ {len(files)} file")


if __name__ == "__main__":
    main()
