#!/usr/bin/env python3
"""Dựng lô bàn giao v2 (sản phẩm DETECTION) từ lô v1 + errors.json — Nhóm 03 (An Hai), Pha 4.

  py tools/build_v2.py --run runs/r3007 --hash-ok 000000006723 000000020247

KHÔNG sửa gì trong delivery/ (v1). Ghi ra runs/<run>/handover/<release_id>_v2/:
  images/, labels/        ảnh + nhãn GIỮ NGUYÊN của v1, trừ ảnh phải gán lại
  rework_queue.csv        image,type,annotator,reviewer,action — giao đúng người theo jobs.csv
  manifest.csv            file,sha256 cho mọi file trong images/ và labels/
  label_summary.csv       class,count theo tên lớp, dòng cuối TOTAL
  truyvet.csv             image,scene_id,split,job_id,annotator,reviewer,guideline (guideline theo JOB; mỗi cảnh một split)
  README.txt              theo templates/README.txt

Quy tắc (GUIDE Pha 4):
  - Sửa ngay trong v2: wrong_hash (chỉ khi ảnh đã được MỞ KIỂM còn nguyên: --hash-ok), guideline_mismatch, scene_leak.
  - Lỗi nhãn detection / thiếu file -> rework_queue, rời v2.
  - Lỗi chỉ ở panoptic -> ảnh Ở LẠI v2, ghi vào Ghi chú để báo team panoptic.
Sau khi chạy: py scripts/pack_release.py <thư mục v2>
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

DET_REWORK = {"missing_image", "invalid_class", "bbox_out_of_bounds", "duplicate_box", "class_swap", "bbox_drift", "missing_box"}
PANOPTIC_ONLY = {"invalid_category_id", "thing_overlap", "category_swap", "instance_merge"}
ACTION = {
    "missing_image": "tìm lại file ảnh gốc hoặc chụp/xuất lại, rồi kiểm nhãn",
    "invalid_class": "gán lại class_id hợp lệ (0-79) cho box sai",
    "bbox_out_of_bounds": "vẽ lại box nằm trong ảnh",
    "duplicate_box": "xoá box lặp, giữ một box",
    "class_swap": "gán lại đúng lớp cho box bị nhầm lớp",
    "bbox_drift": "vẽ lại box ôm đúng vật",
    "missing_box": "thêm box cho vật bị thiếu",
    "wrong_hash": "ảnh hỏng: xuất lại file ảnh, tính lại hash",
}
THRESHOLD = 0.02


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description="Dựng lô v2 từ v1 + errors.json")
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--hash-ok", nargs="*", default=[],
                    help="ảnh wrong_hash đã MỞ KIỂM: còn nguyên, chỉ manifest sai -> giữ trong v2 với hash mới")
    args = ap.parse_args()

    d = args.run / "delivery"
    rid = json.loads((d / "release.json").read_text(encoding="utf-8"))["release_id"]
    man = json.loads((d / "manifest.json").read_text(encoding="utf-8"))["items"]
    meta = {m["image"]: m for m in json.loads((d / "metadata.json").read_text(encoding="utf-8"))["items"]}
    with (d / "jobs.csv").open(encoding="utf-8", newline="") as f:
        jobs = {r["job_id"]: r for r in csv.DictReader(f)}
    names = {}
    for line in (d / "classes.txt").read_text(encoding="utf-8").splitlines():
        if line.strip():
            i, n = line.split(maxsplit=1)
            names[int(i)] = n.strip()
    errors = json.loads((args.run / "errors.json").read_text(encoding="utf-8"))["errors"]
    by_img = {e["target"]: e["type"] for e in errors if e["target"] in man}
    leaks = [e["target"] for e in errors if e["type"] == "scene_leak"]

    # ---- ảnh nào rời v2
    rework = {img: t for img, t in by_img.items() if t in DET_REWORK}
    bad_hash = [img for img, t in by_img.items() if t == "wrong_hash"]
    for img in bad_hash:
        if img not in args.hash_ok:  # chưa mở kiểm hoặc ảnh hỏng -> gán lại / xuất lại
            rework[img] = "wrong_hash"
    keep = [img for img in man if img not in rework and (d / man[img]["image"]).is_file()]

    # ---- split mỗi cảnh: lấy split của đa số ảnh trong cảnh (cả cảnh về một split)
    scene_imgs = defaultdict(list)
    for img, m in meta.items():
        scene_imgs[m["scene_id"]].append(m["split"])
    scene_split = {}
    for sc, splits in scene_imgs.items():
        top = Counter(splits).most_common()
        scene_split[sc] = top[0][0] if len(top) == 1 or top[0][1] > top[1][1] else "train"

    # ---- dựng thư mục
    v2 = args.run / "handover" / f"{rid}_v2"
    if v2.exists():
        shutil.rmtree(v2)
    (v2 / "images").mkdir(parents=True)
    (v2 / "labels").mkdir()
    for img in keep:
        shutil.copy2(d / man[img]["image"], v2 / "images" / Path(man[img]["image"]).name)
        shutil.copy2(d / man[img]["label"], v2 / "labels" / Path(man[img]["label"]).name)

    def write_csv(name, header, rows):
        with (v2 / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)

    # rework_queue.csv — đúng người gán / người kiểm của JOB
    rq_rows = []
    for img, t in sorted(rework.items()):
        job = jobs[meta[img]["job_id"]]
        rq_rows.append([img, t, job["annotator"], job["reviewer"], ACTION.get(t, "gán lại")])
    write_csv("rework_queue.csv", ["image", "type", "annotator", "reviewer", "action"], rq_rows)

    # manifest.csv
    files = sorted(p for sub in ("images", "labels") for p in (v2 / sub).iterdir() if p.is_file())
    write_csv("manifest.csv", ["file", "sha256"], [[p.relative_to(v2).as_posix(), sha(p)] for p in files])

    # label_summary.csv
    counts = Counter()
    for p in (v2 / "labels").glob("*.txt"):
        for ln in p.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                counts[int(float(ln.split()[0]))] += 1
    summ = [[names.get(c, str(c)), n] for c, n in sorted(counts.items())]
    total = sum(counts.values())
    write_csv("label_summary.csv", ["class", "count"], summ + [["TOTAL", total]])

    # truyvet.csv — guideline theo JOB, split theo cảnh
    tv = []
    for img in keep:
        m = meta[img]
        job = jobs[m["job_id"]]
        tv.append([img, m["scene_id"], scene_split[m["scene_id"]], m["job_id"], job["annotator"], job["reviewer"], job["guideline"]])
    write_csv("truyvet.csv", ["image", "scene_id", "split", "job_id", "annotator", "reviewer", "guideline"], tv)

    # README.txt
    err_targets = {e["target"] for e in errors}
    rate = len(err_targets) / len(man)
    by_ver = defaultdict(list)
    for jid in sorted(jobs):
        by_ver[jobs[jid]["guideline"]].append(jid)
    gl = ", ".join(f"{v} ({js[0]}-{js[-1]})" for v, js in sorted(by_ver.items()))
    gm = sorted(img for img, t in by_img.items() if t == "guideline_mismatch")
    pan = sorted((img, t) for img, t in by_img.items() if t in PANOPTIC_ONLY)
    owners = defaultdict(list)
    for img, t, a, r, _ in rq_rows:
        owners[f"{a}/{r}"].append(img)
    leak_txt = "; ".join(f"{sc} đưa cả cảnh về {scene_split[sc]}" for sc in leaks) or "không có"
    hash_txt = ", ".join(f"{img} (đã mở kiểm: ảnh nguyên vẹn, chỉ manifest sai; ghi hash mới)" for img in bad_hash if img in args.hash_ok) or "không có"
    decision_v1 = "Hold" if rate > THRESHOLD else "Release"
    lines = [
        f"Release: {rid}_v2",
        f"Parent: {rid}",
        f"Số ảnh: {len(keep)}",
        f"Số nhãn: {total}",
        f"Guideline: {gl}",
        f"QC v1: {len(err_targets)}/{len(man)} = {rate * 100:.1f}%".replace(".", ","),
        f"Kết luận v1: {decision_v1} — {len(err_targets)} ảnh/cảnh lỗi trên {len(man)} ảnh = {rate * 100:.1f}%".replace(".", ",")
        + (" > ngưỡng 2% (Day 7), không được Release; training run R-021 đã train trên v1 phải xem lại hoặc train lại" if rate > THRESHOLD else " <= ngưỡng 2%"),
        f"Kết luận v2: Release — tách {len(rework)} ảnh lỗi nhãn detection sang rework_queue; sửa hash, guideline theo job, split theo cảnh; "
        f"{len(keep)} ảnh còn lại giữ nguyên nhãn v1 (không sửa tay)",
        "Ghi chú: "
        + f"Split: {leak_txt}. "
        + f"Hash: {hash_txt}. "
        + f"Guideline: {', '.join(gm) or 'không có'} ghi sai phiên bản ở metadata ảnh; truyvet.csv lấy guideline theo job (jobs.csv). "
        + "Rework giao lại (người gán/người kiểm): " + "; ".join(f"{k}: {', '.join(v)}" for k, v in sorted(owners.items())) + ". "
        + "Lỗi chỉ ở panoptic, ảnh ở lại v2 vì nhãn detection đúng, báo team panoptic: "
        + (", ".join(f"{img} ({t})" for img, t in pan) or "không có") + ".",
    ]
    (v2 / "README.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"v2: {v2}")
    print(f"  giữ {len(keep)} ảnh, {total} nhãn; rework {len(rework)}; QC v1 {len(err_targets)}/{len(man)} = {rate:.1%} -> {decision_v1}")
    print(f"  tiếp theo: py scripts/pack_release.py {v2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
