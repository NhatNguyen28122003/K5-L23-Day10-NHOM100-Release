Release: lab250_95697c6d4612_v2
Parent: lab250_95697c6d4612
Số ảnh: 241
Số nhãn: 1647
Guideline: v1.2 (J01-J04), v1.3 (J05-J10)
QC v1: 19/250 = 7,6%
Kết luận v1: Hold — 19 ảnh/cảnh lỗi trên 250 ảnh = 7,6% > ngưỡng 2% (Day 7), không được Release; training run R-021 đã train trên v1 phải xem lại hoặc train lại
Kết luận v2: Release — tách 9 ảnh lỗi nhãn detection sang rework_queue; sửa hash, guideline theo job, split theo cảnh; 241 ảnh còn lại giữ nguyên nhãn v1 (không sửa tay)
Ghi chú: Split: scene_214 đưa cả cảnh về val. Hash: 000000006723 (đã mở kiểm: ảnh nguyên vẹn, chỉ manifest sai; ghi hash mới), 000000020247 (đã mở kiểm: ảnh nguyên vẹn, chỉ manifest sai; ghi hash mới). Guideline: 000000002157, 000000003553 ghi sai phiên bản ở metadata ảnh; truyvet.csv lấy guideline theo job (jobs.csv). Rework giao lại (người gán/người kiểm): A02/Q01: 000000004134; A03/Q01: 000000022589; A04/Q01: 000000007795, 000000009483; A04/Q02: 000000013546, 000000013923; A05/Q01: 000000023272; A05/Q03: 000000005529, 000000007511. Lỗi chỉ ở panoptic, ảnh ở lại v2 vì nhãn detection đúng, báo team panoptic: 000000013291 (instance_merge), 000000013659 (thing_overlap), 000000019742 (category_swap), 000000022192 (thing_overlap), 000000023781 (category_swap).
