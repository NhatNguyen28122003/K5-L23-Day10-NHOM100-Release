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
from collections import Counter, defaultdict
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


class MaskInfo:
    """Kết quả đọc một mask panoptic.
    counts : số pixel THẬT của từng segment id (dùng cho thing_overlap).
    points : toạ độ (x, y) lấy mẫu mỗi SAMPLE_STEP pixel theo hai trục (dùng cho đối chiếu Pha 2)."""

    def __init__(self, width: int, height: int, counts: dict[int, int], points: dict[int, list[tuple[int, int]]]):
        self.width, self.height, self.counts, self.points = width, height, counts, points


SAMPLE_STEP = 2  # lấy 1/4 số pixel: tỉ lệ vẫn chính xác, chạy nhanh gấp ~4 lần


def read_mask(path: Path) -> MaskInfo:
    """Đọc mask (id = R + G*256 + B*256^2): đếm pixel từng id và lấy mẫu toạ độ."""
    width, height, pixels = read_rgb(path)
    rgb = Counter(zip(pixels[0::3], pixels[1::3], pixels[2::3]))  # đếm ở tốc độ C
    counts = {r + g * 256 + b * 65536: n for (r, g, b), n in rgb.items()}
    points: dict[int, list[tuple[int, int]]] = defaultdict(list)
    stride = width * 3
    for y in range(0, height, SAMPLE_STEP):
        row = pixels[y * stride : (y + 1) * stride]
        step = 3 * SAMPLE_STEP
        for k, (r, g, b) in enumerate(zip(row[0::step], row[1::step], row[2::step])):
            sid = r + g * 256 + b * 65536
            if sid:
                points[sid].append((k * SAMPLE_STEP, y))
    return MaskInfo(width, height, counts, points)


def count_mask_pixels(path: Path) -> dict[int, int]:
    """Đếm pixel của từng segment id trong mask (id = R + G*256 + B*256^2)."""
    return read_mask(path).counts


def check_thing_overlap(d: Delivery, mask_counts: dict[str, dict[int, int]]) -> list[str]:
    """area khai trong segments_info LỚN HƠN số pixel thật -> segment bị vật khác đè. Bỏ id 0 (nền)."""
    bad = []
    for img, ann in d.ann_by_image.items():
        info = mask_counts.get(img)
        if info is None:
            continue
        counts = info.counts
        for seg in ann["segments_info"]:
            if seg["id"] != 0 and seg["area"] > counts.get(seg["id"], 0) + OVERLAP_TOL_PX:
                bad.append(img)
                break
    return bad


# ============================================================ Pha 2: đối chiếu detection <-> panoptic
# Ứng viên KHÔNG phải lỗi: người trong nhóm phải mở ảnh rồi mới ghi confirmed/rejected.
# Tín hiệu chính là PIXEL của mask, không phải IoU giữa hai bbox (GUIDE Pha 2).
SWAP_IOU = 0.85          # box và segment khác lớp trùng khít (IoU box vs bbox-pixel của segment) -> nghi đổi lớp
OWN_MATCH_IOU = 0.70     # box "đã có segment của mình" nếu khớp một segment cùng lớp tới mức này
DRIFT_INSIDE_MAX = 0.90  # segment cùng lớp chỉ còn < 90% pixel nằm trong box -> nghi box lệch
DRIFT_INSIDE_MIN = 0.0   #   box có thể dời xa hẳn khỏi vật; điều kiện kích thước + "segment chưa có chủ" giữ độ chính xác
DRIFT_SIZE = (0.7, 1.4)  #   box dời chỗ giữ nguyên kích thước: rộng/cao box chia bbox segment trong khoảng này
DRIFT_MIN_PX = 400       #   bỏ vật < ~20x20 px: lệch 1-2 px do lấy mẫu đã kéo tỉ lệ xuống (6/6 ca trên lô sạch là vật nhỏ)
MISSING_MIN_FRAC = 0.005 # segment thing chiếm >= 0,5% ảnh mà không box cùng lớp nào ôm được -> nghi thiếu box
MISSING_COVER = 0.50     #   "ôm được" = box chứa >= 50% pixel của segment
MERGE_SHARE = 0.20       # một segment có >= 20% pixel nằm trong MỖI box của >= 2 box cùng lớp -> nghi gộp


def _iou(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / union if union > 0 else 0.0


def _inside(points, box) -> float:
    """Tỉ lệ pixel (đã lấy mẫu) của segment nằm trong box."""
    if not points:
        return 0.0
    x1, y1, x2, y2 = box[0] - SAMPLE_STEP, box[1] - SAMPLE_STEP, box[2] + SAMPLE_STEP, box[3] + SAMPLE_STEP
    return sum(1 for x, y in points if x1 <= x <= x2 and y1 <= y <= y2) / len(points)


def find_candidates(d: Delivery, masks: dict[str, MaskInfo], skip: set[str] = frozenset()) -> list[dict]:
    """Ghép box detection với segment panoptic (qua TÊN lớp) và sinh ứng viên 5 loại.
    Mỗi ảnh giữ nhiều nhất MỘT ứng viên (mỗi ảnh mang nhiều nhất một lỗi), ưu tiên tín hiệu mạnh nhất.
    skip: ảnh đã có lỗi luật -> không sinh ứng viên (một ảnh chỉ mang một lỗi)."""
    cat_name = {c["id"]: c["name"] for c in d.panoptic["categories"]}
    is_thing = {c["id"]: c.get("isthing", 0) == 1 for c in d.panoptic["categories"]}
    out = []
    for img, ann in d.ann_by_image.items():
        info = masks.get(img)
        if info is None or img not in d.manifest or img in skip:
            continue
        W, H = info.width, info.height
        boxes = []
        for b in d.boxes(img):
            if b[0] in d.classes:
                x1, y1, x2, y2 = to_pixels(b, W, H)
                boxes.append({"name": d.classes[b[0]], "box": (x1, y1, x2, y2)})
        segs = []
        for s in ann["segments_info"]:
            if not is_thing.get(s["category_id"]) or s.get("iscrowd"):
                continue  # bỏ stuff (trời, đường...) và crowd: không có box tương ứng
            pts = info.points.get(s["id"], [])
            if not pts:
                continue
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            segs.append({"id": s["id"], "name": cat_name.get(s["category_id"], "?"), "pts": pts,
                         "n": info.counts.get(s["id"], 0),
                         "bbox": (min(xs), min(ys), max(xs) + SAMPLE_STEP, max(ys) + SAMPLE_STEP)})
        if not segs and not boxes:
            continue

        inside = {(i, j): _inside(s["pts"], b["box"]) for i, b in enumerate(boxes) for j, s in enumerate(segs)}
        iou = {(i, j): _iou(b["box"], s["bbox"]) for i, b in enumerate(boxes) for j, s in enumerate(segs)}
        found = []  # (độ mạnh, ứng viên)

        def cand(kind, score, reason, box=None, seg=None):
            found.append((score, {"image": img, "type_guess": kind,
                                  "det_class": box["name"] if box else None,
                                  "pan_class": seg["name"] if seg else None,
                                  "box_px": [round(v, 1) for v in box["box"]] if box else None,
                                  "segment_id": seg["id"] if seg else None,
                                  "score": round(score, 3), "reason": reason}))

        # box i "có segment của mình" nếu khớp một segment CÙNG lớp đủ tốt
        def box_has_own(i):
            return any(iou[i, j] >= OWN_MATCH_IOU for j, s in enumerate(segs) if s["name"] == boxes[i]["name"])

        def seg_has_own(j):
            return any(iou[i, j] >= OWN_MATCH_IOU for i, b in enumerate(boxes) if b["name"] == segs[j]["name"])

        swapped_segs = set()
        # 1) Lệch lớp: box và segment trùng khít nhưng khác tên lớp -> class_swap HOẶC category_swap (xem ảnh mới biết)
        for i, b in enumerate(boxes):
            for j, s in enumerate(segs):
                if s["name"] != b["name"] and iou[i, j] >= SWAP_IOU and not box_has_own(i) and not seg_has_own(j):
                    swapped_segs.add(j)
                    cand("swap", 2.0 + iou[i, j], f"box '{b['name']}' trùng khít segment '{s['name']}' (IoU {iou[i, j]:.2f}); "
                         "ảnh cho thấy detection sai -> class_swap, panoptic sai -> category_swap", b, s)

        # 2) instance_merge: một segment trải trên >= 2 box cùng lớp, mỗi box giữ >= MERGE_SHARE pixel của nó
        merged_segs = set()
        for j, s in enumerate(segs):
            holders = [i for i, b in enumerate(boxes) if b["name"] == s["name"] and inside[i, j] >= MERGE_SHARE
                       and not any(iou[i, k] >= OWN_MATCH_IOU for k, t in enumerate(segs) if k != j and t["name"] == s["name"])]
            # hai vật bị gộp: KHÔNG box riêng nào ôm trọn cả segment (box nào chứa >= 90% thì segment là của box đó)
            if len(holders) >= 2 and all(inside[i, j] < 0.9 for i in holders):
                merged_segs.add(j)
                shares = ", ".join(f"{inside[i, j]:.0%}" for i in holders)
                cand("instance_merge", 1.5 + min(inside[i, j] for i in holders),
                     f"segment '{s['name']}' trải trên {len(holders)} box cùng lớp (phần pixel trong từng box: {shares})",
                     boxes[holders[0]], s)

        # 3) bbox_drift: box và segment cùng lớp khớp nhất, nhưng một phần đáng kể pixel segment rơi ra ngoài box.
        #    Box bị dời giữ nguyên KÍCH THƯỚC -> kích thước box ~ bbox segment; và segment không thuộc box cùng lớp nào khác.
        for i, b in enumerate(boxes):
            same = [(inside[i, j], j) for j, s in enumerate(segs) if s["name"] == b["name"] and j not in merged_segs]
            if not same:
                continue
            frac, j = max(same)
            claimed = any(inside[k, j] >= 0.9 for k, o in enumerate(boxes) if k != i and o["name"] == b["name"])
            bw, bh = b["box"][2] - b["box"][0], b["box"][3] - b["box"][1]
            sw, sh = segs[j]["bbox"][2] - segs[j]["bbox"][0], segs[j]["bbox"][3] - segs[j]["bbox"][1]
            same_size = sw > 0 and sh > 0 and DRIFT_SIZE[0] <= bw / sw <= DRIFT_SIZE[1] and DRIFT_SIZE[0] <= bh / sh <= DRIFT_SIZE[1]
            big_enough = segs[j]["n"] >= DRIFT_MIN_PX
            if DRIFT_INSIDE_MIN <= frac < DRIFT_INSIDE_MAX and same_size and not claimed and big_enough:
                cand("bbox_drift", 1.0 + (1 - frac), f"chỉ {frac:.0%} pixel segment '{segs[j]['name']}' nằm trong box "
                     f"(IoU box/segment {iou[i, j]:.2f})", b, segs[j])

        # 4) missing_box: segment thing đủ lớn, không crowd, không box cùng lớp nào ôm được
        for j, s in enumerate(segs):
            if j in swapped_segs or j in merged_segs or s["n"] < MISSING_MIN_FRAC * W * H:
                continue
            if not any(inside[i, j] >= MISSING_COVER for i, b in enumerate(boxes) if b["name"] == s["name"]):
                cand("missing_box", 0.5 + min(s["n"] / (W * H), 0.5),
                     f"segment '{s['name']}' {s['n']} px ({s['n'] / (W * H):.1%} ảnh) không có box cùng lớp", None, s)

        if found:
            found.sort(key=lambda t: -t[0])
            best = found[0][1]
            if len(found) > 1:
                best["also"] = [f"{c['type_guess']} ({c['reason']})" for _, c in found[1:4]]
            out.append(best)
    return out


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
            mask_counts[img] = read_mask(p)

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
        cands = find_candidates(d, mask_counts, {e["target"] for e in errors})
        args.candidates.parent.mkdir(parents=True, exist_ok=True)
        args.candidates.write_text(json.dumps({"candidates": cands}, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{len(cands)} ứng viên -> {args.candidates}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
