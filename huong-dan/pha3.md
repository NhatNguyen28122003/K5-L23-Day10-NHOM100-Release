# Pha 3 — Quyết định phát hành và lineage
_Day 10 Lab · Nhóm 03 (An Hai) · seed luyện tập 3007 · khoảng 15 phút · công cụ: scripts/lineage.py_

## 1. Mục tiêu của pha

Có danh sách lỗi cuối (`errors.json`) rồi, nhóm phải trả lời hai câu:

1. **Lô v1 có được Release không?** Theo ngưỡng Day 7: tỉ lệ ảnh lỗi **trên 2%** thì không Release.
2. **Training run nào đã dùng lô này và bị ảnh hưởng?** Tra bằng lineage.

> **Mốc CP3 (2:05):** lineage có HOLD cho v1; lệnh `impact` ra `R-021: affected=True`.

## 2. Tính tỉ lệ lỗi v1

Tỉ lệ = số mục trong `errors.json` / 250 ảnh. Quy ước:

- Mỗi ảnh mang **nhiều nhất một lỗi**, nên số mục = số ảnh lỗi.
- Mỗi `scene_leak` tính là **một ảnh** (ảnh bị đặt sai split so với phần còn lại của cảnh), dù target là `scene_id`.
- Lỗi luật và lỗi gán nhãn **đã xác nhận** đều tính.

```
py -c "import json;e=json.load(open('runs/r3007/errors.json',encoding='utf-8'))['errors'];t={x['target'] for x in e};print(len(t),f'{len(t)/250:.1%}')"
```

| Thành phần | Số mục |
|---|---|
| lỗi luật (validator) | 11 |
| lỗi gán nhãn đã xem ảnh xác nhận | 8 |
| **tổng** | **19** |
| tỉ lệ | 19/250 = **7,6%** |
| so ngưỡng 2% | 7,6% > 2% ⇒ **HOLD** |

> Vì sao ngưỡng theo **tỉ lệ ảnh lỗi** chứ không theo số lỗi: lô to nhỏ khác nhau; 5 lỗi trong 50 ảnh (10%) nặng hơn nhiều 5 lỗi trong 1000 ảnh (0,5%). Tỉ lệ cho phép so sánh và đặt chuẩn chung.

## 3. Ghi quyết định vào lineage

Lineage là **nhật ký chỉ ghi thêm** (`runs/lineage.jsonl`), mỗi dòng một sự kiện. Lô v1 đã có `inject` và `train R-021` từ Pha 0.

```
$env:PYTHONUTF8 = "1"
py scripts/lineage.py record --event decision --release-id lab250_95697c6d4612 --decision HOLD --detail "QC v1 19/250 = 7.6% > 2%"
py scripts/lineage.py impact --release-id lab250_95697c6d4612
```

Kết quả của nhóm:

```
R-021: affected=True action=review_or_retrain
```

Lineage sau Pha 3:

| # | event | nội dung |
|---|---|---|
| 1 | inject | lô v1 seed 3007 |
| 2 | train | R-021 train trên v1 |
| 3 | decision | HOLD v1 (19/250 = 7,6%) |

> **Chỉ một máy** ghi lineage cho nhóm (máy chạy `run_lab.py` ở Pha 0). Máy thành viên khác không ghi, để không có hai nhật ký lệch nhau. Không sửa tay hay xoá dòng trong `lineage.jsonl`.

## 4. Vì sao R-021 phải xem lại hoặc train lại

- R-021 đã **học** từ nhãn v1: box sai lớp (laptop thay cho tv, bus thay cho car), box lệch, box lặp, vật bị bỏ sót.
- Sửa dataset thành v2 **không** sửa trọng số đã học — lỗi đã nằm trong model.
- Việc phải làm: đánh giá lại R-021 trên dữ liệu sạch (v2); nếu sai lệch đáng kể thì **train lại** trên v2.
- Ticket của team AI (model bỏ sót `bottle`) là ví dụ lỗi dữ liệu đã thành lỗi model.

## 5. Ghi vào REPORT.md mục 3

QC v1 a/b, kết luận, chuỗi lineage, kết quả `impact`, và lý do R-021 phải xem lại hoặc train lại — nhóm đã ghi.

## 6. Câu hỏi vấn đáp (CP3)

| Câu hỏi | Gợi ý trả lời |
|---|---|
| Đổi dataset có sửa được model đã train không? | không; model đã học từ nhãn sai, phải đánh giá lại / train lại |
| Vì sao ngưỡng theo tỉ lệ ảnh lỗi? | so sánh được giữa các lô kích thước khác nhau |
| scene_leak tính mấy ảnh? | một ảnh (ảnh lệch split so với cả cảnh) |
| Lineage dùng để làm gì? | biết lô nào sinh ra từ lô nào, run nào train trên lô nào, để khoanh vùng ảnh hưởng khi lô bị HOLD |
| Nếu tỉ lệ đúng 2%? | không vượt ngưỡng ("trên 2%" mới Hold) — nhưng vẫn nên báo cáo rõ |
