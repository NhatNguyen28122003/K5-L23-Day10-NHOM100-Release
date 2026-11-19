# Pha 6 — Bảo mật và đề ẩn
_Day 10 Lab · Nhóm 03 (An Hai) · seed luyện tập 3007 · 10 phút bảo mật + 40 phút đề ẩn · file: runs/r3007/security.md_

## 1. Mục tiêu của pha

1. **Bảo mật (10 phút):** viết `runs/r3007/security.md` theo `templates/security.md`, ba mục, **gắn với lô vừa bàn giao** — không chép slide.
2. **Đề ẩn (40 phút):** chạy validator, công cụ xem ảnh và truy vết của nhóm trên một lô mới rồi nộp.

> **Mốc CP6a (3:15):** `security.md` đủ ba mục; `check_handover.py` không còn FAIL. **CP6b (3:55):** đã nộp `de_an/`, chạy `export_submission.py`, commit, push.

## 2. security.md — ba mục bắt buộc

`check_handover.py` (H17) kiểm: ≥ 3 mục `## ...` mỗi mục có nội dung (≥ 80 ký tự), không còn `<<...>>`; mục có chữ **"khuôn mặt"** phải kết luận **Hold** và nêu **tên ít nhất một ảnh** có người trong lô.

### Mục 1 — Ca USB: hết giờ, muốn chép lô về nhà

- **Không** chép ra USB, **không** gửi email cá nhân, **không** nhờ người ngoài làm hộ.
- Lý do gắn với lô: `lab250_95697c6d4612` có ảnh người thật (000000001296, 000000019924) và mã người gán/kiểm (A02–A05, Q01–Q03) — dữ liệu khách hàng, chỉ xử lý trên hạ tầng công ty.
- USB dễ mất; email cá nhân ngoài kiểm soát truy cập; người làm hộ không có cam kết bảo mật.
- Cách đúng: lưu tiến độ trên hệ thống công ty, báo trưởng nhóm xin thêm thời gian, hoặc xin quyền VPN / máy ảo của công ty.

### Mục 2 — Năm việc: được hay không

| Việc | Kết luận | Vì sao |
|---|---|---|
| mở job được giao trên máy công ty | **được** | đúng người, đúng quyền, đúng hạ tầng (vd A04 mở J04 để gán lại ảnh rework) |
| chụp màn hình gửi người quen | không | ảnh chụp vẫn là dữ liệu (mặt người, nhãn), ra ngoài không thu hồi được |
| chép lô ra USB | không | như mục 1 |
| dán nhãn/ảnh thật lên chatbot | không | dịch vụ ngoài có thể lưu, dùng để huấn luyện; nằm ngoài hợp đồng (COCO công khai nên lab được dán, có ghi prompts.md) |
| đưa tài khoản CVAT cho đồng nghiệp | không | mỗi nhãn phải truy được đúng người; truyvet.csv và rework_queue giao theo mã người |

### Mục 3 — Ca khuôn mặt: thấy mặt người rõ, guideline yêu cầu làm mờ

- Ảnh có mặt người rõ trong lô của nhóm: **000000001296** (cô gái cầm điện thoại, mặt nhìn thẳng), **000000019924** (người đội mũ rộng vành, cận mặt), 000000004395, 000000016598.
- Kết luận: **Hold** lô + **báo người phụ trách** dự án/bảo mật, kèm danh sách ảnh.
- Không tự làm mờ / tự xoá vì:
  1. làm mờ là **sửa dữ liệu** — lô đã giao phải giữ nguyên, sửa thì thành bản mới có lineage và người duyệt;
  2. cách làm mờ (vùng, mức, có ảnh hưởng nhãn person không) phải theo quy trình chung cho cả lô và các job khác;
  3. xoá ảnh làm mất bằng chứng, lệch manifest và số liệu QC.

Cách nhóm tìm ảnh ví dụ: lọc các ảnh có segment `person` chiếm diện tích lớn nhất trong `panoptic.json`, rồi **mở xem** để chọn ảnh thấy rõ mặt.

### Kiểm tra

```
$env:PYTHONUTF8 = "1"
py scripts/check_handover.py --run runs/r3007
```

Kết quả của nhóm: **17 PASS, 0 FAIL**.

## 3. Đề ẩn (40 phút) — quy trình

Đề ẩn dùng **250 ảnh khác**, tên ảnh đã mã hoá (`img_0001`…), ảnh đã qua xử lý (lật, nén lại), mức lỗi có thể khác lô luyện tập. Validator dựa vào nhãn gốc hay tham số của `inject_release.py` sẽ không đứng vững.

### Chuẩn bị TRƯỚC khi nhận đề

- Mọi máy: `git pull`, `$env:PYTHONUTF8 = "1"`, đã cài Pillow.
- Validator, `tools/view.py`, `tools/trace_query.py` chạy được (đã thử trên lô luyện tập).
- Phân vai: một người chạy lệnh và chia hàng đợi, cả nhóm xem ảnh, một người gộp và commit.

### Các bước khi nhận đề

1. Vào tab **Releases** của repo đề, tải `de_an.zip` (hoặc nhận qua LMS), giải nén vào **thư mục gốc repo nhóm** → được `delivery/`.
2. Chạy validator:

```
py validator/validate.py delivery --out submission/de_an/rules.json --candidates submission/de_an/candidates.json
```

3. Vẽ ảnh ứng viên và chia cho cả nhóm:

```
py tools/view.py delivery --candidates submission/de_an/candidates.json --out submission/de_an/review_img
start submission/de_an/review_img/index.html
```

4. Mỗi người xem phần của mình, ghi `submission/de_an/review_log.csv` (`image,type,verdict,note`, ghi tên người xem, nói rõ thấy gì).
5. Gộp:

```
py scripts/merge_review.py --rules submission/de_an/rules.json --review submission/de_an/review_log.csv --out submission/de_an/errors.json
```

6. Truy vết:

```
py tools/trace_query.py delivery --out submission/de_an/trace.json
```

7. Commit và push. **Không commit** thư mục `delivery/` của đề (đã có trong `.gitignore`) và **không commit** `review_img/` nếu repo giới hạn dung lượng.

Sản phẩm bắt buộc trong `submission/de_an/`: `errors.json`, `candidates.json`, `review_log.csv`, `trace.json`.

### Phân bổ 40 phút (gợi ý)

| Phút | Việc |
|---|---|
| 0–5 | tải, giải nén, chạy validator, vẽ ảnh |
| 5–25 | cả nhóm xem ảnh, ghi review_log |
| 25–30 | gộp errors.json, chạy trace_query |
| 30–35 | soát định dạng review_log, đối chiếu ticket nếu trace có điểm lạ |
| 35–40 | commit, push, kiểm tra trên GitHub |

## 4. Nộp bài (sau đề ẩn)

```
py scripts/export_submission.py --run runs/r3007
py scripts/check_handover.py --run runs/r3007
```

- `export_submission.py` chép bài seed luyện tập sang `submission/r3007/` (errors, candidates, review_log, trace, security, handover v2 + .sha256) và `lineage.jsonl`.
- Đổi tiêu đề `README.md` thành `# Day 10 Lab — Nhóm 03`.
- Nộp link repo lên LMS. Mỗi người ≥ 2 commit có nội dung.

## 5. Câu hỏi vấn đáp (CP6)

| Câu hỏi | Gợi ý trả lời |
|---|---|
| Thấy mặt người rõ: vì sao Hold + báo người phụ trách, không tự làm mờ? | làm mờ là sửa dữ liệu đã giao, phải theo quy trình chung, có bản mới và lineage; tự xoá làm mất bằng chứng |
| Vì sao không đưa tài khoản CVAT cho đồng nghiệp? | mất truy vết ai gán/kiểm nhãn nào; rework giao theo mã người |
| Lab cho dán ảnh COCO lên AI, sao dự án thật thì không? | COCO công khai; dữ liệu dự án thuộc khách hàng, gửi ra dịch vụ ngoài là vi phạm |
| Đề ẩn khác lô luyện tập ở đâu? | ảnh khác, tên mã hoá, ảnh lật/nén lại, mức lỗi khác: validator phải dựa vào đối chiếu, không dựa vào tham số gài lỗi |
