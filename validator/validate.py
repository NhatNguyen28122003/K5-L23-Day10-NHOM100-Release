#!/usr/bin/env python3
"""Validator của Nhóm 03 (An Hai) — Day 10.

    python validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]

Nguyên tắc (RULES.md):
- CHỈ đọc thư mục delivery được truyền vào. Không đọc _private/, data_source/, annotation COCO, không mạng.
- Chỉ thư viện chuẩn + scripts/pngutil.py (đọc PNG).
- Không nhúng tên ảnh / đáp án của seed nào.

Pha 1 bắt 9 lỗi luật, mỗi lỗi một hàm check_*():
  File       : missing_image, wrong_hash
  Detection  : invalid_class, bbox_out_of_bounds, duplicate_box
  Metadata   : scene_leak (target = scene_id), guideline_mismatch
  Panoptic   : invalid_category_id, thing_overlap
Pha 2 (đối chiếu detection <-> panoptic) sẽ ghi ứng viên vào --candidates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import struct
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from pngutil import read_rgb  # noqa: E402  (đọc PNG bằng thư viện chuẩn)

NUM_CLASSES = 80

# ---- Ngưỡng (đo trên lô sạch runs/clean; lý do ghi trong submission/REPORT.md) ----
OOB_TOL_PX = 0.5        # box tràn quá 0,5 px ra ngoài ảnh mới tính là lỗi (bỏ qua sai số làm tròn 6 chữ số)
DUP_SIZE_TOL_PX = 0.5   # hai box "cùng kích thước": chênh rộng/cao <= 0,5 px (box chép lại chênh 0,00;
                        #   cặp tự nhiên gần nhất đo được chênh 1,39 px)
DUP_SHIFT_MAX_PX = 4.0  # và tâm lệch <= 4 px (lỗi gài lệch 1–2 px mỗi trục, tức <= 2,83 px; chừa biên cho đề ẩn)
OVERLAP_TOL_PX = 0      # area khai > số pixel đếm được + tolerance -> thing_overlap


# ============================================================ đọc lô
class Delivery:
    """Gom mọi file của lô vào một chỗ để các hàm check_* dùng chung."""

    def __init__(self, root: Path):
        self.root = root
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["items"]
        self.metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))["items"]
        self.panoptic = json.loads((root / "panoptic.json").read_text(encoding="utf-8"))
        with (root / "jobs.csv").open(encoding="utf-8", newline="") as handle:
            self.jobs = {row["job_id"]: row for row in csv.DictReader(handle)}
        self.classes = {}
        for line in (root / "classes.txt").read_text(encoding="utf-8").splitlines():
            if line.strip():
                idx, name = line.split(maxsplit=1)
                self.classes[int(idx)] = name.strip()
        # kích thước ảnh: ưu tiên panoptic.json, thiếu thì đọc header JPEG
        self.sizes = {Path(im["file_name"]).stem: (im["width"], im["height"]) for im in self.panoptic["images"]}
        self.ann_by_image = {Path(a["file_name"]).stem: a for a in self.panoptic["annotations"]}

    def path(self, image: str, kind: str) -> Path:
        """kind = image | label | mask; đường dẫn lấy từ manifest."""
        return self.root / self.manifest[image][kind]

    def image_size(self, image: str) -> tuple[int, int] | None:
        if image in self.sizes:
            return self.sizes[image]
        p = self.path(image, "image")
        return jpeg_size(p) if p.is_file() else None

    def boxes(self, image: str) -> list[tuple[int, float, float, float, float]]:
        """Box YOLO: (class_id, xc, yc, w, h) chuẩn hoá 0-1. Dòng hỏng bị bỏ qua."""
        p = self.path(image, "label")
        out = []
        if not p.is_file():
            return out
        for line in p.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) != 5:
                continue
            try:
                out.append((int(float(parts[0])), *map(float, parts[1:])))
            except ValueError:
                continue
        return out


def jpeg_size(path: Path) -> tuple[int, int] | None:
    """Đọc (width, height) từ marker SOF của JPEG, không cần Pillow."""
    data = path.read_bytes()
    i = 2
    while i + 9 < len(data):
        if data[i] != 0xFF:
            i += 1
            continue
        marker = data[i + 1]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            height, width = struct.unpack(">HH", data[i + 5 : i + 9])
            return width, height
        length = struct.unpack(">H", data[i + 2 : i + 4])[0]
        i += 2 + length
    return None


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:  # luôn đọc BYTES (rb), không đọc text
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def to_pixels(box, width: int, height: int) -> tuple[float, float, float, float]:
    """YOLO (xc, yc, w, h chuẩn hoá) -> (x1, y1, x2, y2) pixel."""
    _, xc, yc, w, h = box
    return ((xc - w / 2) * width, (yc - h / 2) * height, (xc + w / 2) * width, (yc + h / 2) * height)


# ============================================================ lỗi file
def check_missing_image(d: Delivery) -> list[str]:
    """Manifest liệt kê ảnh nhưng file ảnh không tồn tại."""
    return [img for img in d.manifest if not d.path(img, "image").is_file()]


def check_wrong_hash(d: Delivery, skip: set[str]) -> list[str]:
    """Tự tính sha256 rồi so với manifest (không chỉ kiểm định dạng 64 ký tự)."""
    bad = []
    for img, entry in d.manifest.items():
        if img in skip:
            continue
        for kind in ("image", "label", "mask"):
            p = d.path(img, kind)
            expected = entry.get(f"{kind}_sha256")
            if expected and p.is_file() and sha256_file(p) != expected.lower():
                bad.append(img)
                break
    return bad


# ============================================================ lỗi nhãn detection
def check_invalid_class(d: Delivery) -> list[str]:
    """class_id ngoài 0..79 (hoặc không có trong classes.txt)."""
    return [img for img in d.manifest if any(not (0 <= b[0] < NUM_CLASSES) or b[0] not in d.classes for b in d.boxes(img))]


def check_bbox_out_of_bounds(d: Delivery) -> list[str]:
    """Box tràn ra ngoài ảnh (đổi ra pixel để tolerance có nghĩa vật lý)."""
    bad = []
    for img in d.manifest:
        size = d.image_size(img)
        if not size:
            continue
        w, h = size
        for box in d.boxes(img):
            x1, y1, x2, y2 = to_pixels(box, w, h)
            if x1 < -OOB_TOL_PX or y1 < -OOB_TOL_PX or x2 > w + OOB_TOL_PX or y2 > h + OOB_TOL_PX:
                bad.append(img)
                break
    return bad


def check_duplicate_box(d: Delivery) -> list[str]:
    """Hai box cùng lớp, cùng kích thước (chênh <= 0,5 px), tâm lệch <= 4 px.
    Không dùng IoU: cặp box tự nhiên của COCO có thể chồng nhau tới IoU ~0,66 nhưng khác kích thước."""
    bad = []
    for img in d.manifest:
        size = d.image_size(img)
        if not size:
            continue
        w, h = size
        px = [(b[0], b[1] * w, b[2] * h, b[3] * w, b[4] * h) for b in d.boxes(img)]
        found = False
        for i in range(len(px)):
            for j in range(i + 1, len(px)):
                a, b = px[i], px[j]
                if a[0] != b[0]:
                    continue
                same_size = abs(a[3] - b[3]) <= DUP_SIZE_TOL_PX and abs(a[4] - b[4]) <= DUP_SIZE_TOL_PX
                shift = ((a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5
                if same_size and shift <= DUP_SHIFT_MAX_PX:
                    found = True
                    break
            if found:
                break
        if found:
            bad.append(img)
    return bad


# ============================================================ lỗi metadata
def check_scene_leak(d: Delivery) -> list[str]:
    """Một cảnh có ảnh ở nhiều split. Target là scene_id (không phải tên ảnh)."""
    splits = defaultdict(set)
    for item in d.metadata:
        splits[item["scene_id"]].add(item["split"])
    return sorted(scene for scene, s in splits.items() if len(s) > 1)


def check_guideline_mismatch(d: Delivery) -> list[str]:
    """Guideline ghi ở ảnh khác guideline ghi ở JOB của ảnh (jobs.csv là nguồn chuẩn)."""
    bad = []
    for item in d.metadata:
        job = d.jobs.get(item["job_id"])
        if job and item.get("guideline_version") != job["guideline"]:
            bad.append(item["image"])
    return bad


# ============================================================ lỗi panoptic
def check_invalid_category_id(d: Delivery) -> list[str]:
    """category_id của segment không có trong categories."""
    valid = {c["id"] for c in d.panoptic["categories"]}
    return [img for img, ann in d.ann_by_image.items() if any(s["category_id"] not in valid for s in ann["segments_info"])]


def count_mask_pixels(path: Path) -> dict[int, int]:
    """Đếm pixel của từng segment id trong mask (id = R + G*256 + B*256^2)."""
    _, _, pixels = read_rgb(path)
    counts: dict[int, int] = defaultdict(int)
    for i in range(0, len(pixels), 3):
        counts[pixels[i] + pixels[i + 1] * 256 + pixels[i + 2] * 65536] += 1
    return counts


def check_thing_overlap(d: Delivery, mask_counts: dict[str, dict[int, int]]) -> list[str]:
    """area khai trong segments_info LỚN HƠN số pixel thật -> segment bị vật khác đè. Bỏ id 0 (nền)."""
    bad = []
    for img, ann in d.ann_by_image.items():
        counts = mask_counts.get(img)
        if counts is None:
            continue
        for seg in ann["segments_info"]:
            if seg["id"] != 0 and seg["area"] > counts.get(seg["id"], 0) + OVERLAP_TOL_PX:
                bad.append(img)
                break
    return bad


# ============================================================ Pha 2 (sẽ viết)
def find_candidates(d: Delivery, mask_counts) -> list[dict]:
    """Đối chiếu detection <-> panoptic. Pha 2 sẽ điền."""
    return []


# ============================================================ main
def main() -> int:
    ap = argparse.ArgumentParser(description="Validator lỗi luật + ứng viên gán nhãn")
    ap.add_argument("delivery", type=Path)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--candidates", type=Path)
    args = ap.parse_args()

    d = Delivery(args.delivery)
    mask_counts = {}
    for img in d.manifest:
        p = d.path(img, "mask")
        if p.is_file():
            mask_counts[img] = count_mask_pixels(p)

    missing = check_missing_image(d)
    found: list[tuple[str, str]] = [("missing_image", t) for t in missing]
    found += [("wrong_hash", t) for t in check_wrong_hash(d, set(missing))]
    found += [("invalid_class", t) for t in check_invalid_class(d)]
    found += [("bbox_out_of_bounds", t) for t in check_bbox_out_of_bounds(d)]
    found += [("duplicate_box", t) for t in check_duplicate_box(d)]
    found += [("scene_leak", t) for t in check_scene_leak(d)]
    found += [("guideline_mismatch", t) for t in check_guideline_mismatch(d)]
    found += [("invalid_category_id", t) for t in check_invalid_category_id(d)]
    found += [("thing_overlap", t) for t in check_thing_overlap(d, mask_counts)]

    errors = [{"type": t, "target": target} for t, target in dict.fromkeys(found)]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps({"errors": errors}, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = defaultdict(int)
    for e in errors:
        summary[e["type"]] += 1
    print(f"{len(errors)} lỗi luật -> {args.out}")
    for t, n in sorted(summary.items()):
        print(f"  {t:22s} {n}")

    if args.candidates:
        cands = find_candidates(d, mask_counts)
        args.candidates.parent.mkdir(parents=True, exist_ok=True)
        args.candidates.write_text(json.dumps({"candidates": cands}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(cands)} ứng viên -> {args.candidates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
