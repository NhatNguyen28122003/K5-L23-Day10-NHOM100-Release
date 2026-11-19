# Pha 4 — Bàn giao lô v2, không ghi đè v1
_Day 10 Lab · Nhóm 03 (An Hai) · seed luyện tập 3007 · khoảng 40 phút · công cụ: tools/build_v2.py, pack_release.py, check_handover.py_

## 1. Mục tiêu của pha

v1 bị HOLD. Nhóm làm **bản v2** để giao cho team AI — một sản phẩm **detection** (ảnh + nhãn YOLO) — mà **không sửa một byte nào của v1**.

> **Mốc CP4 (2:45):** `check_handover.py` chỉ còn FAIL ở trace/security (nếu chưa làm Pha 5–6).

Thư mục v2: `runs/r3007/handover/lab250_95697c6d4612_v2/`

| Phần | Nội dung |
|---|---|
| `images/`, `labels/` | ảnh và nhãn **giữ nguyên** của v1, trừ ảnh phải gán lại |
| `rework_queue.csv` | `image,type,annotator,reviewer,action`: ảnh tách ra để gán lại, giao đúng người theo `jobs.csv` |
| `manifest.csv` | `file,sha256` cho mọi file trong `images/` và `labels/` (dạng `images/x.jpg`) |
| `label_summary.csv` | `class,count` theo tên lớp, dòng cuối `TOTAL` |
| `truyvet.csv` | `image,scene_id,split,job_id,annotator,reviewer,guideline` — guideline theo **job**, mỗi cảnh một split |
| `README.txt` | theo `templates/README.txt`: số ảnh, số nhãn, QC v1 có mẫu số, kết luận v1 và v2, ghi chú |

## 2. Mỗi loại lỗi xử lý thế nào

| Nhóm | Loại lỗi | Xử lý |
|---|---|---|
| Sửa ngay trong v2 | `wrong_hash` | **mở ảnh kiểm trước**: còn nguyên → chỉ manifest sai, ghi hash mới; hỏng → rework |
| | `guideline_mismatch` | truyvet.csv lấy guideline theo job |
| | `scene_leak` | đưa **cả cảnh** về một split |
| Rework, rời v2 | `missing_image`, `invalid_class`, `bbox_out_of_bounds`, `duplicate_box`, `class_swap`, `bbox_drift`, `missing_box` | vào `rework_queue.csv`, giao người gán/người kiểm của job |
| Ở lại v2 | `invalid_category_id`, `thing_overlap`, `category_swap`, `instance_merge` | nhãn **detection** vẫn đúng; ghi vào Ghi chú README để báo team panoptic |

> **Không sửa tay nhãn** trong v2. Nhãn sai → rework, người gán sửa và người kiểm duyệt. Sửa tay làm mất truy vết ai sửa gì (H7 kiểm nhãn v2 phải trùng hash v1).

## 3. Bước 1 — Mở kiểm ảnh wrong_hash

Lô 3007 có 2 ảnh `wrong_hash`. Nhóm kiểm từng file:

| Ảnh | image | label | mask | Mở ảnh |
|---|---|---|---|---|
| 000000006723 | lệch | khớp | khớp | mở được 640×361, đường phố có xe — nguyên vẹn |
| 000000020247 | lệch | khớp | khớp | mở được 640×457, hai con gấu trên sỏi — nguyên vẹn |

Kết luận: chỉ manifest ghi sai → giữ trong v2, `manifest.csv` ghi hash mới.

## 4. Bước 2 — Dựng v2 bằng tools/build_v2.py

```
$env:PYTHONUTF8 = "1"
py tools/build_v2.py --run runs/r3007 --hash-ok 000000006723 000000020247
```

Công cụ làm tự động, đúng các quy tắc ở mục 2:

1. Chọn ảnh rời v2 (lỗi detection / thiếu file / wrong_hash chưa mở kiểm).
2. Chép ảnh + nhãn còn lại **nguyên byte** từ v1.
3. `rework_queue.csv`: người gán/người kiểm lấy từ `jobs.csv` theo job của ảnh, kèm việc cần làm.
4. `manifest.csv`: sha256 tính trên bytes của từng file.
5. `label_summary.csv`: đếm box theo tên lớp, dòng `TOTAL`.
6. `truyvet.csv`: guideline theo job; split theo **đa số ảnh của cảnh** (cả cảnh về một split).
7. `README.txt` theo mẫu, có `QC v1: 19/250 = 7,6%`.

Kết quả của nhóm:

| Mục | Giá trị |
|---|---|
| ảnh trong v2 | 241 |
| nhãn trong v2 | 1647 |
| ảnh rework | 9 |
| ảnh lỗi panoptic ở lại v2 | 5 |
| scene_214 | cả cảnh về `val` |

rework_queue.csv:

| image | type | người gán / kiểm |
|---|---|---|
| 000000004134 | bbox_out_of_bounds | A02 / Q01 |
| 000000005529 | duplicate_box | A05 / Q03 |
| 000000007511 | missing_box | A05 / Q03 |
| 000000007795 | missing_box | A04 / Q01 |
| 000000009483 | class_swap | A04 / Q01 |
| 000000013546 | invalid_class | A04 / Q02 |
| 000000013923 | duplicate_box | A04 / Q02 |
| 000000022589 | bbox_drift | A03 / Q01 |
| 000000023272 | class_swap | A05 / Q01 |

## 5. Bước 3 — Đóng gói, ghi lineage, kiểm tra

```
py scripts/pack_release.py runs/r3007/handover/lab250_95697c6d4612_v2
py scripts/lineage.py record --event release --release-id lab250_95697c6d4612_v2 --parent lab250_95697c6d4612
py scripts/check_handover.py --run runs/r3007
```

- `pack_release.py` tạo `.zip` tái lập (thứ tự, thời gian file cố định) và `.sha256`. **Không commit .zip**, chỉ commit `.sha256`.
- Đổi bất kỳ file nào trong v2 sau khi đóng gói → chạy lại `pack_release.py` (nếu không H15 FAIL).
- Lineage giờ có `release v2 --parent v1`.

Kết quả của nhóm sau Pha 4: **H1–H15 PASS**, chỉ H16 (trace) và H17 (security) FAIL — đúng mốc CP4. Sau Pha 5–6: **17 PASS, 0 FAIL**.

| Mã | Kiểm gì |
|---|---|
| H1 | v1 giữ nguyên (release_id tính lại khớp) |
| H2–H3 | errors.json đủ lỗi luật; review_log có confirmed cho mọi lỗi gán nhãn, ghi chú ≥ 20 ký tự, không chép giống nhau |
| H4–H7 | v2 đủ phần; ảnh lỗi detection vào rework; đúng người; nhãn không sửa tay |
| H8–H9 | manifest.csv và label_summary.csv khớp file thật |
| H10–H11 | truyvet theo jobs.csv; không cảnh nào rò train/val |
| H12–H13 | README đúng tên lô, số ảnh, số nhãn, QC v1, kết luận theo ngưỡng 2% |
| H14 | lineage có HOLD v1 và release v2 có parent |
| H15 | zip đóng gói lại khớp .sha256 |

> **PASS không có nghĩa nhãn đúng.** Bộ kiểm chỉ xác nhận định dạng và tính nhất quán. Không sửa `scripts/` để qua bộ kiểm: người chấm chạy bản gốc, sửa là 0 điểm mục 3.

## 6. Lỗi hay gặp

| Triệu chứng | Cách xử lý |
|---|---|
| H1 FAIL | đã sửa `delivery/`: tạo lại lô cùng seed, chỉ làm trong `handover/` |
| H5 FAIL với ảnh lỗi panoptic | ảnh chỉ lỗi panoptic ở lại v2, không vào rework |
| H8 FAIL | sửa file sau khi lập manifest: chạy lại build_v2 rồi pack |
| H13 FAIL | dòng `QC v1:` phải là `<số mục errors.json>/250`, kết luận đúng ngưỡng |
| H15 FAIL | chưa chạy lại `pack_release.py` sau khi đổi v2 |

## 7. Câu hỏi vấn đáp (CP4)

| Câu hỏi | Gợi ý trả lời |
|---|---|
| Lỗi nào sửa được trong v2, lỗi nào phải gán lại? | sửa: hash (ảnh nguyên), guideline theo job, split theo cảnh; gán lại: lỗi nhãn detection, thiếu file |
| Hash chứng minh gì? | file giống từng byte với lúc ghi hash, không bị đổi khi chuyển giao |
| Hash **không** chứng minh gì? | nhãn đúng; ví dụ 000000009483.txt khớp hash nhưng vẫn ghi laptop cho màn hình rời |
| Vì sao không ghi đè v1? | v1 là thứ R-021 đã học; giữ để truy vết, so sánh, quay lại; v2 là bản mới có lô cha |
| Vì sao ảnh lỗi panoptic ở lại v2? | v2 là sản phẩm detection; nhãn detection của ảnh đó vẫn đúng |
