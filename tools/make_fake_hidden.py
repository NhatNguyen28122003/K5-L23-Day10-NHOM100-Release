#!/usr/bin/env python3
"""Giả lập đề ẩn từ một lô có sẵn — Nhóm 03 (An Hai), Pha 6.

  py tools/make_fake_hidden.py runs/clean/delivery runs/fake_hidden/delivery

Đề ẩn khác lô luyện tập ở ba điểm: tên ảnh mã hoá (img_0001...), ảnh bị lật, ảnh bị nén lại.
Script biến một lô đã biết kết quả (ví dụ lô sạch: 0 lỗi luật, 0 ứng viên) thành lô có ba đặc điểm đó,
để thử cả pipeline (validator, view.py, trace_query.py) trước khi nhận đề thật.

Việc làm:
  1. Đổi tên ảnh sang <prefix>NNNN ở mọi nơi: images/, labels/, masks/, manifest.json
     (khoá + đường dẫn), metadata.json, panoptic.json (images.file_name, annotations.file_name).
  2. Lật ngang ảnh JPEG (nén lại, --quality) và mask PNG (không mất mát, id segment giữ nguyên).
  3. Label YOLO: x_center -> 1 - x_center. Bbox trong segments_info: x -> W - (x + w).
  4. Tính lại sha256 cho image/label/mask trong manifest.json.
Các file còn lại (classes.txt, jobs.csv, guideline/, incoming/, release.json) được chép nguyên.
File thiếu trong lô nguồn thì bị bỏ qua (manifest vẫn giữ dòng đó). Chỉ dùng Pillow + thư viện chuẩn.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image, ImageOps


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flip_label(text: str) -> str:
    out = []
    for line in text.splitlines():
        parts = line.split()
        if len(parts) != 5:
            out.append(line)  # dòng hỏng giữ nguyên, validator vẫn phải xử lý được
            continue
        parts[1] = f"{1.0 - float(parts[1]):.6f}"
        out.append(" ".join(parts))
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Giả lập đề ẩn: đổi tên, lật, nén lại, tính lại hash")
    ap.add_argument("src", type=Path, help="thư mục delivery nguồn (ví dụ runs/clean/delivery)")
    ap.add_argument("dst", type=Path, help="thư mục delivery đích (ví dụ runs/fake_hidden/delivery)")
    ap.add_argument("--prefix", default="img_")
    ap.add_argument("--quality", type=int, default=85, help="chất lượng JPEG khi nén lại")
    args = ap.parse_args()

    src, dst = args.src, args.dst
    if dst.exists():
        shutil.rmtree(dst)
    for sub in ("images", "labels", "masks"):
        (dst / sub).mkdir(parents=True)
    for name in ("classes.txt", "jobs.csv", "release.json"):
        if (src / name).is_file():
            shutil.copy2(src / name, dst / name)
    for sub in ("guideline", "incoming"):
        if (src / sub).is_dir():
            shutil.copytree(src / sub, dst / sub)

    man = json.loads((src / "manifest.json").read_text(encoding="utf-8"))
    meta = json.loads((src / "metadata.json").read_text(encoding="utf-8"))
    pan = json.loads((src / "panoptic.json").read_text(encoding="utf-8"))

    old_names = list(man["items"])
    new_name = {old: f"{args.prefix}{i:04d}" for i, old in enumerate(old_names, 1)}
    width = {Path(im["file_name"]).stem: im["width"] for im in pan["images"]}

    # --- manifest + file ảnh / label / mask
    new_items = {}
    for old, entry in man["items"].items():
        new = new_name[old]
        item = {"image": f"images/{new}.jpg", "label": f"labels/{new}.txt", "mask": f"masks/{new}.png"}
        # file thiếu (lô có missing_image): bỏ qua, giữ nguyên dòng manifest để lỗi vẫn còn
        if (src / entry["image"]).is_file():
            with Image.open(src / entry["image"]) as im:
                ImageOps.mirror(im.convert("RGB")).save(dst / item["image"], "JPEG", quality=args.quality)
        if (src / entry["label"]).is_file():
            text = (src / entry["label"]).read_text(encoding="utf-8")
            (dst / item["label"]).write_text(flip_label(text), encoding="utf-8")
        if (src / entry["mask"]).is_file():
            with Image.open(src / entry["mask"]) as mk:
                ImageOps.mirror(mk.convert("RGB")).save(dst / item["mask"], "PNG")
        for kind in ("image", "label", "mask"):
            if (dst / item[kind]).is_file():
                item[f"{kind}_sha256"] = sha256(dst / item[kind])
        new_items[new] = item
    man["items"] = new_items
    (dst / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- metadata
    for row in meta["items"]:
        row["image"] = new_name[row["image"]]
    meta["items"].sort(key=lambda r: r["image"])
    (dst / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")

    # --- panoptic: tên file + bbox lật ngang
    for im in pan["images"]:
        im["file_name"] = new_name[Path(im["file_name"]).stem] + Path(im["file_name"]).suffix
    for ann in pan["annotations"]:
        old = Path(ann["file_name"]).stem
        w = width[old]
        ann["file_name"] = new_name[old] + Path(ann["file_name"]).suffix
        for seg in ann["segments_info"]:
            x, y, bw, bh = seg["bbox"]
            seg["bbox"] = [w - (x + bw), y, bw, bh]
    (dst / "panoptic.json").write_text(json.dumps(pan, ensure_ascii=False), encoding="utf-8")

    print(f"{len(old_names)} ảnh -> {dst} (tên {args.prefix}0001..., lật ngang, JPEG q={args.quality})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
