# Pha 5 — Truy vết ticket của team AI
_Day 10 Lab · Nhóm 03 (An Hai) · seed luyện tập 3007 · khoảng 20 phút · công cụ: tools/trace_query.py_

## 1. Mục tiêu của pha

Team AI train xong thì báo lỗi qua ticket. Nhóm dữ liệu phải trả lời: **ảnh nào cần mở lại**, chia **hai tầng**, và **báo cho ai**. Kết quả ghi vào `runs/r3007/trace.json`:

```
{"tier_a": [...tên ảnh...], "tier_b": [...tên ảnh...], "notify": [...mã người...]}
```

> **Mốc CP5 (3:05):** `trace.json` có ba khoá; `score_findings.py` in thêm phần truy vết.

## 2. Đọc đầu vào

| File | Nội dung trong lô 3007 |
|---|---|
| `incoming/ticket.md` | model hay bỏ sót `bottle` bị che hoặc ở mép ảnh; team AI thấy rõ ở **scene_197** và **scene_309** |
| `guideline/changelog.md` | **v1.3**: `bottle` bị che > 50% hoặc cắt mép **vẫn phải gán box** (v1.2 cho phép bỏ qua); không đổi lớp khác |
| `jobs.csv` | J01–J04 theo **v1.2** (cũ), J05–J10 theo v1.3 |
| `labels/` | box detection của lô v1 |
| `metadata.json` | scene_id, job_id của từng ảnh |

Suy luận: các job theo **v1.2** được phép bỏ `bottle` bị che/ở mép, nên model học được thói quen bỏ sót. Ảnh cần mở lại là ảnh thuộc job v1.2 có `bottle`.

## 3. Tiêu chí ba khoá

| Khoá | Điều kiện |
|---|---|
| `tier_a` | ảnh trong **các cảnh ticket nêu**, thuộc job theo **guideline cũ**, có **≥ 1 box detection** lớp bị đổi quy tắc |
| `tier_b` | ảnh **khác** cùng điều kiện (job guideline cũ, có box lớp đó) mà **chưa ai báo** |
| `notify` | mã **người gán + người kiểm** của các job chứa ảnh tầng a và b |

Hai điểm then chốt:

- **Guideline lấy theo job** (`jobs.csv`), không theo `guideline_version` ghi ở từng ảnh — giá trị ở ảnh có thể chính là lỗi `guideline_mismatch` (lô 3007 có 2 ảnh như vậy: 000000002157, 000000003553).
- **"Có lớp"** nghĩa là có ít nhất một **box detection** lớp đó trong `labels/` của lô (DELIVERY.md mục 3) — không dùng panoptic.

> Tầng a khác tầng b thế nào: tầng a là chỗ team AI **đã thấy** lỗi (xác nhận được ngay); tầng b là ảnh **cùng nguyên nhân** nhưng chưa ai nhìn tới — đây mới là giá trị của truy vết: tìm hết chỗ cùng gốc lỗi, không chỉ sửa chỗ được báo.

## 4. Chạy công cụ

```
$env:PYTHONUTF8 = "1"
py tools/trace_query.py runs/r3007/delivery --out runs/r3007/trace.json
py scripts/score_findings.py --run runs/r3007
```

`trace_query.py` (chỉ thư viện chuẩn) làm các bước:

1. Đọc `changelog.md`: tìm mục `## vX` đầu tiên có dòng "Lớp `tên`" → phiên bản mới (v1.3) và lớp bị đổi (`bottle`).
2. Đọc `ticket.md`: lấy mọi `scene_<số>` → scene_197, scene_309.
3. Job **cũ** = job có guideline < phiên bản mới (so theo số): J01–J04.
4. Duyệt `metadata.json`: ảnh thuộc job cũ **và** label có class_id của `bottle` → vào tầng a nếu thuộc cảnh ticket, ngược lại tầng b.
5. `notify` = người gán + người kiểm của các job chứa ảnh hai tầng, sắp xếp.

Nếu đề viết ticket/changelog theo kiểu khác, ép tham số: `--class bottle --scenes scene_197 scene_309 --new-version v1.3`.

## 5. Kết quả của nhóm

| Khoá | Ảnh / người | Chi tiết |
|---|---|---|
| tier_a | 2 | 000000002685 (scene_309, J02), 000000009590 (scene_197, J04) |
| tier_b | 4 | 000000005193, 000000006471 (J03); 000000007574, 000000008021 (J04) |
| notify | 5 | A02, A04, A05, Q01, Q03 (người gán/kiểm của J02, J03, J04) |

`score_findings.py`: **truy vết F1 ≈ 1.0** cho cả tier_a, tier_b, notify. `check_handover.py` H16 PASS.

## 6. Lỗi hay gặp

| Triệu chứng | Cách xử lý |
|---|---|
| tầng a/b thiếu ảnh | đang lấy guideline theo ảnh thay vì theo job |
| tầng a/b thừa ảnh | dùng panoptic hoặc tính cả job v1.3; chỉ dùng box detection của job cũ |
| H16 FAIL | `tier_a` và `notify` không được rỗng; mã người phải có trong `jobs.csv` |
| notify thiếu người kiểm | phải gồm **cả** annotator và reviewer |

## 7. Câu hỏi vấn đáp (CP5)

| Câu hỏi | Gợi ý trả lời |
|---|---|
| Tầng a và tầng b khác nhau thế nào? | a: trong cảnh team AI đã báo; b: cùng nguyên nhân, chưa ai báo — phải chủ động tìm |
| Vì sao lấy guideline theo job? | guideline chốt khi giao job; giá trị ở ảnh có thể là lỗi guideline_mismatch |
| Vì sao chỉ job v1.2? | v1.2 cho phép bỏ bottle bị che/ở mép; job v1.3 bắt buộc gán nên không cùng nguyên nhân |
| Báo người gán và người kiểm để làm gì? | họ cần biết quy tắc mới, kiểm lại ảnh của mình, và đây là bằng chứng truy trách nhiệm đúng người |
| Model đã train thì sao? | xem lại hoặc train lại sau khi các ảnh tầng a/b được gán bổ sung (liên hệ Pha 3) |
