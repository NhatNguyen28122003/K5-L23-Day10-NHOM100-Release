# Báo cáo nhóm 03 (An Hai)

## 1. Số liệu luyện tập
- F1 theo seed (rule / cross_check / overall):
  - 3007 (seed luyện tập, sau Pha 2 — 11 lỗi luật + 8 lỗi gán nhãn đã xem ảnh xác nhận): **1.0 / 0.9 / 0.9**
  - Chỉ lỗi luật (sau Pha 1, trước khi xem ảnh):
  - 3007: 1.0 / — / 0.7 (11 lỗi luật)
  - 4001: 1.0 / — / 0.8 (13 lỗi luật)
  - 6001: 1.0 / — / 0.8 (11 lỗi luật)
  - lô sạch (seed 5, `--no-faults`): 0 lỗi luật báo ra
- Số ứng viên trên lô sạch (`--no-faults`, 50 ảnh) và hàng đợi seed 3007 (250 ảnh) qua từng phiên bản đối chiếu:

| Phiên bản | Lô sạch | Seed 3007 | Ghi chú |
|---|---|---|---|
| v1: ghép theo pixel, drift chỉ xét tỉ lệ pixel trong box | 4 (cả 4 bbox_drift) | 32 | ~8% ảnh sạch có ứng viên -> ~20 báo thừa / 250 ảnh |
| v2: thêm "box dời giữ kích thước", "segment chưa có chủ" | 6 | 26 | cả 6 ca sạch là vật rất nhỏ (6–37 px) |
| v3: bỏ vật < 400 px, nới box 1 bước lấy mẫu | 2 (instance_merge) | 15 | 2 ca: một box ôm trọn 100% segment |
| **v4 (chốt): merge yêu cầu không box nào ôm >= 90% segment; drift < 90%** | **0** | **8** | 4 lệch lớp, 2 thiếu box, 1 gộp, 1 box lệch |

- Hàng đợi chốt: **8 ảnh**, 4 người xem hết trong vài phút; cả 8 được xác nhận là lỗi (`review_log.csv`).
- Ngưỡng đối chiếu (chỉ dùng lô sạch, không dùng `_private`, không so ứng viên giữa các seed):
  - Lệch lớp: box và bbox-pixel segment khác lớp IoU >= 0,85 và box không khớp segment cùng lớp nào (IoU >= 0,7).
  - `instance_merge`: một segment có >= 20% pixel trong mỗi box của >= 2 box cùng lớp, và không box nào ôm >= 90% segment.
  - `bbox_drift`: < 90% pixel segment cùng lớp nằm trong box, rộng/cao box / segment trong 0,7–1,4 (box dời chỗ giữ kích thước), segment không thuộc box cùng lớp khác, vật >= 400 px.
  - `missing_box`: segment thing không crowd >= 0,5% ảnh, không box cùng lớp nào chứa >= 50% pixel của nó.
  - Pixel mask lấy mẫu 1/4 (bước 2 px); bỏ segment stuff và crowd; ảnh đã có lỗi luật không sinh ứng viên (mỗi ảnh tối đa một lỗi).
- Ngưỡng đã chọn và cách chọn (không dùng `_private`):
  - `bbox_out_of_bounds`: tràn > 0,5 px. Trên lô sạch và 3 seed, mọi box tự nhiên tràn đúng 0,0 px; box lỗi tràn 22–49 px.
  - `duplicate_box`: cùng lớp, chênh rộng/cao <= 0,5 px, tâm lệch <= 4 px. Đo mọi cặp box cùng lớp: box lặp chênh kích thước 0,00 px, lệch tâm 2,2–2,8 px; cặp tự nhiên gần nhất chênh rộng 1,39 px (lệch 2,98 px) nên bị loại nhờ điều kiện kích thước. Không dùng IoU.
  - `thing_overlap`: `area` khai > số pixel đếm trong mask (bỏ id 0). Lô sạch: 0 ca.
  - `wrong_hash`: tính lại sha256 trên bytes của image/label/mask, so với manifest.

## 2. Vì sao báo hết ứng viên làm F1 giảm?
F1 là trung bình điều hoà của precision và recall, nên một báo thừa (FP) bị trừ nặng như một bỏ sót (FN).
Ứng viên chỉ là chỗ hai nguồn nhãn bất đồng; COCO vốn lệch tự nhiên giữa detection và panoptic (vật bị che, crowd, vật nhỏ, mask đã cắt phần bị đè).
Số của nhóm: với cách ghép v1, lô sạch 50 ảnh — **không có lỗi nào** — vẫn ra 4 ứng viên, tức khoảng 8% ảnh. Trên 250 ảnh luyện tập, v1 ra 32 ứng viên;
bản chốt chỉ giữ 8 ứng viên và cả 8 được xác nhận khi xem ảnh. Theo tỉ lệ nhiễu đo trên lô sạch (~8% ảnh), khoảng 20 trong 32 ứng viên v1
là lệch tự nhiên. Nộp cả 32 mà không xem ảnh thì precision chỉ còn khoảng 12/32 ≈ 0,4 (ước tính), F1 lỗi gán nhãn tụt mạnh;
còn với hàng đợi chốt, precision cao nhưng F1 cross_check ≈ 0,9 cho thấy vẫn bỏ sót một phần lỗi — đây là đánh đổi precision/recall khi chọn ngưỡng.
Ngoài ra ứng viên lệch lớp cần mắt người mới biết là `class_swap` hay `category_swap`: đoán sai loại cũng là một FP cộng một FN.

## 3. Quyết định và lineage
- **QC v1: 19/250 = 7,6%** (11 lỗi luật + 8 lỗi gán nhãn đã xem ảnh xác nhận; mỗi ảnh tối đa một lỗi, `scene_leak` của `scene_214` tính là một ảnh). Ngưỡng Day 7 là 2% (tối đa 5/250 ảnh lỗi), 7,6% vượt gần gấp 4 lần.
- **Kết luận v1: HOLD.** Đã ghi vào lineage:
  `lineage.py record --event decision --release-id lab250_95697c6d4612 --decision HOLD --detail "QC v1 19/250 = 7.6% > 2%"`.
- `lineage.py impact --release-id lab250_95697c6d4612` trả về **`R-021: affected=True action=review_or_retrain`**.
- Vì sao R-021 phải xem lại hoặc train lại: R-021 đã train trên đúng release v1. Model là hàm của dữ liệu lúc train; sửa hay thay dataset sau đó **không** làm trọng số đã học thay đổi. Những nhãn sai (lệch lớp, box lệch, box lặp, thiếu box) đã đi vào gradient, còn `scene_leak` làm ảnh cùng cảnh nằm ở cả train và val nên số đánh giá của R-021 có thể bị thổi phồng. Vì vậy phải: (1) xem lại metric R-021 trên tập val đã bỏ rò rỉ / v2; (2) nếu kém hoặc không chắc thì train lại trên v2. Lineage cho biết **run nào** bị ảnh hưởng thay vì phải đoán.
- Vì sao ngưỡng theo **tỉ lệ ảnh lỗi** chứ không theo số lỗi: số lỗi tuyệt đối phụ thuộc cỡ lô (5 lỗi trên 250 ảnh khác 5 lỗi trên 50 000 ảnh); tỉ lệ ảnh lỗi so được giữa các lô và gắn với rủi ro thực tế là "bao nhiêu phần dữ liệu train bị bẩn". Đếm theo ảnh (không theo box) để một ảnh nhiều box sai không bị tính nhiều lần.

## 4. Hash chứng minh gì, không chứng minh gì?
- **Chứng minh:** file nhận được giống từng byte với file đã ghi hash (toàn vẹn, không bị sửa/đổi khi chuyển giao). `manifest.csv` của v2 có sha256 cho 482 file; `.sha256` của zip v2 cho biết gói bàn giao không bị thay đổi; `release_id` v1 tính từ hash manifest + metadata nên v1 bị sửa là phát hiện ngay (H1).
- **Không chứng minh:** nhãn **đúng**. Hash của `000000009483.txt` khớp hoàn toàn nhưng nhãn vẫn ghi laptop cho một màn hình rời. Hash cũng không chứng minh ảnh không hỏng nội dung nếu hash được ghi sau khi hỏng, không chứng minh ai làm, hay dữ liệu đúng split/guideline.
- Trong lô: 2 ảnh `wrong_hash` (000000006723, 000000020247) — nhóm **mở ảnh kiểm** thấy ảnh nguyên vẹn (đường phố, hai con gấu), chỉ manifest ghi sai, nên giữ trong v2 với hash mới. Nếu ảnh hỏng thì phải đưa vào rework.
- Không ghi đè v1: v1 là bằng chứng của thứ R-021 đã học; ghi đè làm mất khả năng truy vết và so sánh. v2 là bản mới có lô cha.

- **Kết luận v2: Release trong phạm vi detection.** Bản dựng từ dữ liệu nhóm đã đẩy lên giữ 241 ảnh với 1.647 nhãn YOLO, chuyển 9 ảnh vào rework theo job và xử lý các vấn đề hash, guideline và split. Checker đạt 17 PASS, 0 FAIL. F1 cross-check khoảng 0,9 đo khả năng tìm lỗi của quy trình review trên v1. Điểm này cho thấy có thể còn lỗi chưa phát hiện, nên team AI cần chạy QC trên lô nhận và đánh giá lại R-021 trên tập val đã bỏ rò rỉ.
- Năm ảnh chỉ có lỗi panoptic được giữ trong gói detection. README v2 ghi rõ việc cần xử lý cho từng ảnh: tách segment ở `000000013291`, kiểm vùng chồng và đồng bộ mask/area ở `000000013659` và `000000022192`, sửa lớp segment ở `000000019742` và `000000023781`. Các mask cần được team panoptic kiểm lại trước một lượt bàn giao riêng.

## 5. Truy vết
- Ticket: model bỏ sót `bottle` bị che hoặc ở mép, team AI nêu `scene_197`, `scene_309`. Changelog: v1.3 bắt buộc gán box cho `bottle` bị che > 50% hoặc ở mép; v1.2 cho phép bỏ qua.
- Tiêu chí (`tools/trace_query.py`): job theo guideline **cũ** = v1.2 theo `jobs.csv` (J01–J04); "có lớp" = có ít nhất một box detection `bottle` trong `labels/` của lô.
  - `tier_a` (2 ảnh): trong scene_197/scene_309, job v1.2, có box bottle: 000000002685 (scene_309, J02), 000000009590 (scene_197, J04).
  - `tier_b` (4 ảnh): cùng điều kiện nhưng ở cảnh khác, chưa ai báo: 000000005193, 000000006471 (J03), 000000007574, 000000008021 (J04).
  - `notify`: người gán + người kiểm của J02, J03, J04: A02, A04, A05, Q01, Q03.
- Vì sao lấy guideline theo **job**: guideline được chốt khi giao job; giá trị `guideline_version` ghi ở từng ảnh có thể chính là lỗi `guideline_mismatch` (lô có 2 ảnh như vậy: 000000002157, 000000003553). Lấy theo ảnh thì tầng truy vết lệch theo đúng chỗ dữ liệu sai.
- Tự đo: F1 truy vết ≈ 1.0 cho cả tier_a, tier_b, notify.

## 6. Bug hoặc điểm chưa rõ trong lab (nếu có)
- **Windows: `run_lab.py` chết vì `UnicodeEncodeError` dù gọi `py -X utf8`.** `run_lab.py` gọi `inject_release.py` bằng `subprocess` với `sys.executable` nhưng không truyền cờ `-X utf8`; console Windows mặc định cp1252 nên dòng in tiếng Việt cuối `inject_release.py` làm tiến trình con lỗi, `run_lab.py` dừng **trước** khi ghi lineage (delivery đã tạo xong). Cách nhóm xử lý: đặt `$env:PYTHONUTF8 = "1"` (được tiến trình con kế thừa) rồi chạy lại; vì lineage chưa có dòng nào nên chạy lại an toàn. Gợi ý sửa: truyền `-X utf8` hoặc `env PYTHONUTF8=1` trong `run_lab.py`. Nhóm không sửa `scripts/`.
- **H15 khi đổi hệ điều hành.** Cùng thư mục v2 trong Git, `pack_release.py` tạo SHA-256 khác nhau trên Windows và Linux do thứ tự file và trường `create_system` trong ZIP khác nhau. Lô `r3007` được tạo và đóng gói trên Windows. Nên dùng Windows khi tái lập lô và kiểm gói này bằng script gốc.
