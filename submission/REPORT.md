# Báo cáo nhóm 03 (An Hai)

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall), sau Pha 1 (chưa có lỗi gán nhãn):
  - 3007: 1.0 / — / 0.7 (11 lỗi luật)
  - 4001: 1.0 / — / 0.8 (13 lỗi luật)
  - 6001: 1.0 / — / 0.8 (11 lỗi luật)
  - lô sạch (seed 5, `--no-faults`): 0 lỗi luật báo ra
- Số ứng viên trên lô sạch (`--no-faults`): <<...>>; hàng đợi trên seed luyện tập: <<... ảnh>>
- Ngưỡng đã chọn và cách chọn (không dùng `_private`):
  - `bbox_out_of_bounds`: tràn > 0,5 px. Trên lô sạch và 3 seed, mọi box tự nhiên tràn đúng 0,0 px; box lỗi tràn 22–49 px.
  - `duplicate_box`: cùng lớp, chênh rộng/cao <= 0,5 px, tâm lệch <= 4 px. Đo mọi cặp box cùng lớp: box lặp chênh kích thước 0,00 px, lệch tâm 2,2–2,8 px; cặp tự nhiên gần nhất chênh rộng 1,39 px (lệch 2,98 px) nên bị loại nhờ điều kiện kích thước. Không dùng IoU.
  - `thing_overlap`: `area` khai > số pixel đếm trong mask (bỏ id 0). Lô sạch: 0 ca.
  - `wrong_hash`: tính lại sha256 trên bytes của image/label/mask, so với manifest.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
<<Trả lời bằng số của nhóm.>>

## 3. Quyết định và lineage
<<QC v1 a/b, kết luận, vì sao R-021 phải xem lại hoặc train lại.>>

## 4. Hash chứng minh gì, không chứng minh gì?
<<>>

## 5. Truy vết
<<Tiêu chí tầng a/b, vì sao lấy guideline theo job.>>

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
<<>>
