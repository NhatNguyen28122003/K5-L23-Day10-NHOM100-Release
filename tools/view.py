#!/usr/bin/env python3
"""Công cụ xem ảnh để review ứng viên Pha 2 — Nhóm 03 (An Hai).

Công cụ này ĐƯỢC dùng Pillow (validator thì không). Cài: py -m pip install pillow

  # vẽ mọi ứng viên trong candidates.json
  py tools/view.py runs/r3007/delivery --candidates runs/r3007/candidates.json --out runs/r3007/review_img

  # vẽ vài ảnh bất kỳ (tên không đuôi)
  py tools/view.py runs/r3007/delivery --image 000000009483 000000023272 --out runs/r3007/review_img

  # vẽ cả lô (ứng viên lên trước, rồi mọi ảnh còn lại) để lướt
  py tools/view.py runs/r3007/delivery --candidates runs/r3007/candidates.json --all --out runs/r3007/review_img

  # đề ẩn (tên ảnh dạng img_0001) — chạy y hệt
  py tools/view.py delivery --candidates submission/de_an/candidates.json --out submission/de_an/review_img

Mỗi ảnh ra một file PNG gồm hai nửa:
  TRÁI : ảnh gốc, mọi box detection (xanh dương, tên lớp detection), mọi segment thing (viền vàng, tên lớp panoptic);
         box và segment của ứng viên tô đậm (box đỏ, segment tô xanh lá).
         instance_merge: tô đỏ MỌI box cùng lớp chứa >= 20% pixel của segment (không chỉ box đầu tiên).
  PHẢI : vùng quanh ứng viên, cắt ra và phóng to (ảnh nhỏ cỡ 240x320 vẫn nhìn rõ).
Kèm index.html: mở bằng trình duyệt để lướt cả hàng đợi, có lý do và gợi ý từng ứng viên.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

BOX = (40, 120, 255)        # box detection
BOX_CAND = (230, 30, 30)    # box của ứng viên
SEG = (255, 200, 0)         # viền segment thing
SEG_CAND = (0, 200, 80)     # segment của ứng viên
CROP_MIN = 520              # cạnh nhỏ nhất của ảnh phóng to
MERGE_SHARE = 0.20          # khớp validator: box giữ >= 20% pixel segment thì tô đỏ


def font(size: int):
    for name in ("arial.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


class Lot:
    def __init__(self, root: Path):
        self.root = root
        self.manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))["items"]
        pan = json.loads((root / "panoptic.json").read_text(encoding="utf-8"))
        self.cats = {c["id"]: c for c in pan["categories"]}
        self.anns = {Path(a["file_name"]).stem: a for a in pan["annotations"]}
        self.classes = {}
        for line in (root / "classes.txt").read_text(encoding="utf-8").splitlines():
            if line.strip():
                i, n = line.split(maxsplit=1)
                self.classes[int(i)] = n.strip()

    def boxes(self, img: str, w: int, h: int):
        p = self.root / self.manifest[img]["label"]
        out = []
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) != 5:
                    continue
                c, xc, yc, bw, bh = int(float(parts[0])), *map(float, parts[1:])
                out.append((self.classes.get(c, f"?{c}"),
                            ((xc - bw / 2) * w, (yc - bh / 2) * h, (xc + bw / 2) * w, (yc + bh / 2) * h)))
        return out


def segment_mask(mask_rgb: Image.Image, sid: int) -> Image.Image:
    """Ảnh nhị phân (L) của một segment: id = R + G*256 + B*256^2."""
    r, g, b = mask_rgb.split()
    want = (sid & 255, (sid >> 8) & 255, (sid >> 16) & 255)
    parts = [ch.point(lambda v, t=t: 255 if v == t else 0) for ch, t in zip((r, g, b), want)]
    return ImageChops.multiply(ImageChops.multiply(parts[0], parts[1]), parts[2])


def outline(binary: Image.Image) -> Image.Image:
    return ImageChops.subtract(binary.filter(ImageFilter.MaxFilter(3)), binary)


def render(lot: Lot, img: str, cand: dict | None, out_dir: Path) -> Path | None:
    entry = lot.manifest.get(img)
    if not entry:
        print("không có trong manifest:", img)
        return None
    ip, mp = lot.root / entry["image"], lot.root / entry["mask"]
    if not ip.is_file():
        print("thiếu file ảnh:", img)
        return None
    base = Image.open(ip).convert("RGB")
    W, H = base.size
    canvas = base.copy()
    draw = ImageDraw.Draw(canvas, "RGBA")
    f = font(max(11, W // 45))
    focus = []  # vùng cần phóng to

    cand_bin = None  # mask nhị phân (L) của segment ứng viên, dùng để tìm các box cùng lớp

    # segment thing: viền vàng + tên lớp panoptic; segment ứng viên tô xanh lá
    if mp.is_file() and img in lot.anns:
        mask = Image.open(mp).convert("RGB")
        for s in lot.anns[img]["segments_info"]:
            cat = lot.cats.get(s["category_id"], {"name": f"?{s['category_id']}", "isthing": 1})
            if not cat.get("isthing"):
                continue
            binm = segment_mask(mask, s["id"])
            is_c = cand is not None and cand.get("segment_id") == s["id"]
            if is_c:
                cand_bin = binm
                canvas.paste(Image.new("RGB", (W, H), SEG_CAND), (0, 0), binm.point(lambda v: 110 if v else 0))
            edge = outline(binm)
            canvas.paste(Image.new("RGB", (W, H), SEG_CAND if is_c else SEG), (0, 0), edge)
            bb = binm.getbbox()
            if bb:
                tag = f"P:{cat['name']}" + (" crowd" if s.get("iscrowd") else "")
                draw.text((bb[0] + 2, bb[3] - f.size - 2), tag, fill=SEG_CAND if is_c else SEG, font=f,
                          stroke_width=2, stroke_fill=(0, 0, 0))
                if is_c:
                    focus.append(bb)

    # box detection: xanh dương + tên lớp detection; box ứng viên màu đỏ, nét dày.
    # instance_merge: tô đỏ MỌI box cùng lớp chứa >= MERGE_SHARE pixel của segment
    cbox = tuple(cand["box_px"]) if cand and cand.get("box_px") else None
    merge = bool(cand) and cand.get("type_guess") == "instance_merge" and cand_bin is not None
    seg_total = max(1, cand_bin.histogram()[255]) if merge else 1
    for name, bx in lot.boxes(img, W, H):
        is_c = cbox is not None and all(abs(a - b) < 1.0 for a, b in zip(bx, cbox))
        if merge and not is_c and name == cand.get("pan_class"):
            x1, y1, x2, y2 = (int(round(v)) for v in bx)
            part = cand_bin.crop((max(0, x1), max(0, y1), min(W, x2), min(H, y2)))
            is_c = part.histogram()[255] / seg_total >= MERGE_SHARE
        col = BOX_CAND if is_c else BOX
        draw.rectangle(bx, outline=col, width=3 if is_c else 2)
        draw.text((bx[0] + 2, bx[1] + 1), f"D:{name}", fill=col, font=f, stroke_width=2, stroke_fill=(255, 255, 255))
        if is_c:
            focus.append(bx)

    # vùng phóng to: hợp box + segment ứng viên, cộng lề 40%
    if focus:
        x1 = min(b[0] for b in focus); y1 = min(b[1] for b in focus)
        x2 = max(b[2] for b in focus); y2 = max(b[3] for b in focus)
    else:
        x1, y1, x2, y2 = 0, 0, W, H
    mx, my = max(20, (x2 - x1) * 0.4), max(20, (y2 - y1) * 0.4)
    crop_box = (int(max(0, x1 - mx)), int(max(0, y1 - my)), int(min(W, x2 + mx)), int(min(H, y2 + my)))
    crop = canvas.crop(crop_box)
    scale = max(1.0, CROP_MIN / max(1, min(crop.size)))
    crop = crop.resize((int(crop.width * scale), int(crop.height * scale)), Image.LANCZOS)

    # ghép trái (toàn ảnh) + phải (phóng to), thêm dòng tiêu đề
    left_h = max(H, crop.height)
    head = 30
    sheet = Image.new("RGB", (W + 10 + crop.width, left_h + head), (30, 30, 30))
    sheet.paste(canvas, (0, head))
    sheet.paste(crop, (W + 10, head))
    title = img
    if cand:
        title += f"  |  gợi ý: {cand.get('type_guess')}  D:{cand.get('det_class')}  P:{cand.get('pan_class')}"
    title += f"  |  {W}x{H}  phóng to x{scale:.1f}"
    ImageDraw.Draw(sheet).text((8, 6), title, fill=(255, 255, 255), font=font(16))
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{img}.png"
    sheet.save(out)
    return out


def write_index(out_dir: Path, rows: list[tuple[str, dict | None, Path]]) -> Path:
    parts = ["<!doctype html><meta charset='utf-8'><title>Review ứng viên</title>",
             "<style>body{font-family:Arial;background:#111;color:#eee;margin:16px}"
             ".c{margin:0 0 28px}img{max-width:100%;border:1px solid #444}code{color:#fc6}</style>",
             f"<h1>Hàng đợi review ({len(rows)} ảnh)</h1>",
             "<p>D: = nhãn detection (box xanh dương, ứng viên đỏ) · P: = nhãn panoptic (viền vàng, ứng viên tô xanh lá)."
             " Ghi kết luận vào review_log.csv: image,type,verdict,note — note nói THẤY GÌ và tên người xem.</p>"]
    for k, (img, cand, png) in enumerate(rows, 1):
        reason = html.escape(cand.get("reason", "")) if cand else ""
        also = "<br>".join(html.escape(a) for a in cand.get("also", [])) if cand else ""
        guess = html.escape(str(cand.get("type_guess"))) if cand else ""
        parts.append(f"<div class='c'><h3>{k}. <code>{img}</code> — gợi ý: {guess}</h3><p>{reason}</p>"
                     + (f"<p><small>khác: {also}</small></p>" if also else "")
                     + f"<img src='{png.name}' loading='lazy'></div>")
    idx = out_dir / "index.html"
    idx.write_text("\n".join(parts), encoding="utf-8")
    return idx


def main() -> int:
    ap = argparse.ArgumentParser(description="Vẽ box detection + viền segment panoptic để review")
    ap.add_argument("delivery", type=Path)
    ap.add_argument("--candidates", type=Path, help="candidates.json do validator ghi")
    ap.add_argument("--image", nargs="*", default=[], help="tên ảnh (không đuôi) muốn xem thêm")
    ap.add_argument("--all", action="store_true", help="vẽ cả lô (mọi ảnh trong manifest) để lướt")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    lot = Lot(args.delivery)
    todo: list[tuple[str, dict | None]] = []
    if args.candidates:
        for c in json.loads(args.candidates.read_text(encoding="utf-8"))["candidates"]:
            todo.append((c["image"], c))
    todo += [(i, None) for i in args.image]
    if args.all:
        seen = {i for i, _ in todo}
        todo += [(i, None) for i in sorted(lot.manifest) if i not in seen]
    if not todo:
        ap.error("cần --candidates, --image hoặc --all")

    rows = []
    for img, cand in todo:
        png = render(lot, img, cand, args.out)
        if png:
            rows.append((img, cand, png))
            print("->", png)
    print("mở để review:", write_index(args.out, rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
