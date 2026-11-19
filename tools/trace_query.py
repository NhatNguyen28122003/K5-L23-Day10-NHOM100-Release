#!/usr/bin/env python3
"""Truy vết ticket của team AI — Nhóm 03 (An Hai), Pha 5. Chỉ thư viện chuẩn.

  py tools/trace_query.py runs/r3007/delivery --out runs/r3007/trace.json
  py tools/trace_query.py delivery --out submission/de_an/trace.json          # đề ẩn

Đọc incoming/ticket.md (cảnh team AI nêu) và guideline/changelog.md (lớp bị đổi quy tắc ở phiên bản mới):
  tier_a : ảnh trong các cảnh ticket nêu, thuộc job theo guideline CŨ, có >= 1 box detection lớp bị đổi quy tắc
  tier_b : ảnh khác cùng điều kiện (job guideline cũ, có box lớp đó) mà chưa ai báo
  notify : mã người gán + người kiểm của các job chứa ảnh tầng a và b
Guideline lấy theo JOB (jobs.csv), KHÔNG theo guideline_version ghi ở ảnh (có thể chính là lỗi guideline_mismatch).
"Có lớp" = có box detection lớp đó trong labels/ của lô (docs/DELIVERY.md mục 3).
Có thể ép tham số bằng --class / --scenes / --new-version nếu đề viết ticket theo kiểu khác.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path


def vkey(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v))


def parse_changelog(text: str) -> tuple[str | None, str | None]:
    """Trả (phiên bản mới, tên lớp bị đổi quy tắc): mục '## vX' đầu tiên nhắc 'Lớp `tên`'."""
    sections = re.split(r"^##\s+", text, flags=re.M)[1:]
    for sec in sections:
        head, _, body = sec.partition("\n")
        m = re.search(r"[Ll]ớp\s+`([^`]+)`", body)
        ver = re.search(r"v\d+(?:\.\d+)*", head)
        if m and ver:
            return ver.group(0), m.group(1)
    return None, None


def main() -> int:
    ap = argparse.ArgumentParser(description="Truy vết ticket: tier_a, tier_b, notify")
    ap.add_argument("delivery", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--class", dest="cls", help="ép tên lớp bị đổi quy tắc")
    ap.add_argument("--scenes", nargs="*", help="ép danh sách cảnh ticket nêu")
    ap.add_argument("--new-version", help="ép phiên bản guideline mới")
    args = ap.parse_args()
    d = args.delivery

    ticket = (d / "incoming" / "ticket.md").read_text(encoding="utf-8")
    new_ver, cls = parse_changelog((d / "guideline" / "changelog.md").read_text(encoding="utf-8"))
    cls = args.cls or cls
    new_ver = args.new_version or new_ver
    scenes = set(args.scenes or re.findall(r"scene_\d+", ticket))
    if not (cls and new_ver and scenes):
        raise SystemExit(f"không đọc được ticket/changelog (lớp={cls}, bản mới={new_ver}, cảnh={sorted(scenes)}): dùng --class/--new-version/--scenes")

    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}
    old_jobs = {j for j, r in jobs.items() if vkey(r["guideline"]) < vkey(new_ver)}  # guideline CŨ theo job

    cls_ids = set()
    for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            i, n = line.split(maxsplit=1)
            if n.strip() == cls:
                cls_ids.add(int(i))
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]

    def has_class(img: str) -> bool:
        p = d / man[img]["label"] if img in man else None
        if not p or not p.is_file():
            return False
        for ln in p.read_text(encoding="utf-8").splitlines():
            parts = ln.split()
            try:
                if parts and int(float(parts[0])) in cls_ids:
                    return True
            except ValueError:
                continue
        return False

    tier_a, tier_b = [], []
    for m in meta:
        img = m["image"]
        if m["job_id"] not in old_jobs or not has_class(img):
            continue
        (tier_a if m["scene_id"] in scenes else tier_b).append(img)
    touched = {m["job_id"] for m in meta if m["image"] in set(tier_a) | set(tier_b)}
    notify = sorted({jobs[j]["annotator"] for j in touched} | {jobs[j]["reviewer"] for j in touched})

    out = {"tier_a": sorted(tier_a), "tier_b": sorted(tier_b), "notify": notify}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"lớp đổi quy tắc: {cls} (từ {new_ver}); job guideline cũ: {sorted(old_jobs)}; cảnh ticket: {sorted(scenes)}")
    print(f"tier_a {len(tier_a)} ảnh, tier_b {len(tier_b)} ảnh, notify {notify} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
