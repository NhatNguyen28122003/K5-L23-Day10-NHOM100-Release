# Pha 1 — Bắt lỗi luật bằng validator tự viết
_Day 10 Lab · Nhóm 03 (An Hai) · seed luyện tập 3007 · khoảng 40 phút · file: validator/validate.py_

## 1. Mục tiêu của pha

Viết `validator/validate.py` bắt **9 loại lỗi luật**, tức các lỗi máy kiểm được chỉ bằng cách đọc file, không cần nhìn ảnh. Yêu cầu đạt:

- F1 lỗi luật ≈ **1.0** trên seed luyện tập **và** ít nhất một seed khác.
- Trên **lô sạch** (`runs/clean`) báo **0** lỗi luật.
- Chỉ dùng **thư viện chuẩn** Python (+ `scripts/pngutil.py`), chỉ đọc thư mục delivery được truyền vào, không mạng.

Giao diện cố định (giảng viên sẽ gọi đúng như vậy trên đề ẩn):

```
py validator/validate.py <thư_mục_delivery> --out <errors.json> [--candidates <candidates.json>]
```

`errors.json` có dạng `{"errors": [{"type": "...", "target": "..."}]}`. Đơn vị chấm là cặp `(type, target)`; target là **tên ảnh không đuôi**, riêng `scene_leak` target là **scene_id**.

## 2. Luật chơi của validator (RULES.md)

| Được | Không được |
|---|---|
| đọc mọi file trong thư mục delivery truyền vào | đọc `_private/`, `data_source/`, annotation COCO |
| `import` thư viện chuẩn và `scripts/pngutil.py` | dùng Pillow, numpy hay gói ngoài trong validator |
| dùng AI để viết code (ghi vào `prompts.md`) | nhúng tên ảnh, id, đáp án của seed nào vào code |
| dùng `score_findings.py` để biết tốt lên hay kém đi | nộp thử từng phần để dò điểm (bị coi là gian lận) |

## 3. Kiến trúc file validate.py

File chia thành bốn phần, mỗi loại lỗi là một hàm `check_*()` riêng để mỗi thành viên giải thích được một đoạn khi vấn đáp:

1. **Ngưỡng** ở đầu file (`OOB_TOL_PX`, `DUP_SIZE_TOL_PX`, `DUP_SHIFT_MAX_PX`, `OVERLAP_TOL_PX`). Muốn đổi yêu cầu chỉ sửa ở đây.
2. **Class `Delivery`**: đọc một lần manifest, metadata, panoptic, jobs, classes; cung cấp `path()`, `boxes()`, `image_size()`.
3. **Chín hàm `check_*`**, mỗi hàm trả về danh sách target bị lỗi.
4. **`main()`**: đếm pixel mask một lần, gọi các hàm check, ghi `errors.json` và in tóm tắt.

### Các hàm tiện ích

- `sha256_file(path)`: tính sha256 trên **bytes** (mở `rb`, đọc từng khối 1 MB).
- `to_pixels(box, w, h)`: đổi box YOLO (tâm, rộng, cao chuẩn hoá) sang toạ độ góc pixel `(x1, y1, x2, y2)`.
- `jpeg_size(path)`: đọc rộng/cao từ marker SOF của JPEG khi `panoptic.json` thiếu ảnh — không cần Pillow.
- `count_mask_pixels(path)`: đọc PNG bằng `pngutil.read_rgb`, đếm số pixel của từng segment id.

## 4. Chín lỗi luật — cách bắt từng loại

### 4.1 missing_image — manifest có, file không có

```
def check_missing_image(d):
    return [img for img in d.manifest if not d.path(img, "image").is_file()]
```

Duyệt mọi ảnh trong manifest, kiểm file có tồn tại không. Ảnh đã thiếu thì bỏ qua ở bước kiểm hash (không báo trùng).

### 4.2 wrong_hash — sha256 trong manifest không phải của file

Tự **tính lại** sha256 của image, label và mask rồi so với `image_sha256`, `label_sha256`, `mask_sha256` trong manifest. Chỉ cần một file lệch là báo ảnh đó.

> **Bẫy:** chỉ kiểm "chuỗi có 64 ký tự hex" thì không bắt được gì — hash giả vẫn đúng định dạng. Và phải đọc **bytes** (`rb`): đọc dạng text trên Windows sẽ đổi `\r\n` và cho hash khác.

### 4.3 invalid_class — class_id ngoài 0–79

Đọc từng dòng label, `class_id` không nằm trong 0..79 (hoặc không có trong `classes.txt`) là lỗi. Dòng hỏng (không đủ 5 trường) bị bỏ qua chứ không làm validator chết.

### 4.4 bbox_out_of_bounds — box tràn ra ngoài ảnh

Đổi box sang pixel bằng kích thước ảnh, báo lỗi khi một cạnh tràn quá `OOB_TOL_PX = 0,5` px:

```
x1, y1, x2, y2 = to_pixels(box, w, h)
if x1 < -0.5 or y1 < -0.5 or x2 > w + 0.5 or y2 > h + 0.5: -> lỗi
```

Vì sao đổi sang pixel: YOLO làm tròn 6 chữ số, box chạm mép tự nhiên có thể ra 1.0000005; ngưỡng 0,5 px có nghĩa vật lý rõ ràng ("tràn nửa pixel"). Số đo của nhóm: box tự nhiên tràn **đúng 0,0 px**, box lỗi tràn **22–49 px**.

### 4.5 duplicate_box — một box bị chép lặp, lệch 1–2 px

Hai box là bản lặp khi: **cùng lớp**, **cùng kích thước** (chênh rộng và cao ≤ 0,5 px) và **tâm lệch ≤ 4 px**.

> **Không dùng IoU.** COCO có cặp box tự nhiên chồng nhau tới IoU khoảng 0,66 (người đứng sau người). Ngưỡng IoU thấp sẽ báo nhầm hàng loạt. Dấu hiệu chắc chắn của box chép lại là **kích thước giống hệt**.

Cách nhóm chọn ngưỡng (đo trên lô sạch + 3 seed, không đọc `_private`):

| Loại cặp box cùng lớp | Chênh kích thước | Lệch tâm |
|---|---|---|
| box lặp (lỗi) | 0,00 px | 2,24–2,83 px |
| cặp tự nhiên gần nhất (seed 6001) | 1,39 px | 2,98 px |
| cặp tự nhiên lệch tâm ít nhất trên lô sạch | 3,79 px | 2,86 px |

Bản đầu (chênh ≤ 1 px, lệch ≤ 3 px) chỉ cách cặp tự nhiên 0,02 px — quá sát. Bản chốt siết kích thước xuống 0,5 px (điều kiện phân biệt chính) và nới lệch lên 4 px để đề ẩn có lệch lớn hơn một chút vẫn bắt được.

### 4.6 scene_leak — một cảnh có ảnh ở cả train và val

Gom split theo `scene_id` trong `metadata.json`; cảnh nào có hơn một split là lỗi. **Target là scene_id**, không phải tên ảnh.

Vì sao là lỗi: 5 ảnh cùng cảnh gần như giống nhau; một ảnh ở train và ảnh khác ở val làm điểm val bị thổi phồng (rò rỉ dữ liệu).

### 4.7 guideline_mismatch — guideline của ảnh khác guideline của job

So `guideline_version` ghi ở ảnh với cột `guideline` của **job** trong `jobs.csv`. Khác nhau là lỗi.

> Vì sao so với **job** chứ không so với các ảnh khác: job là đơn vị giao việc, guideline được chốt ở đầu job. Giá trị ghi ở từng ảnh chính là thứ có thể bị sai — lấy đa số ảnh làm chuẩn sẽ sai khi lỗi rơi vào nhiều ảnh.

### 4.8 invalid_category_id — category_id không có trong categories

Lập tập `id` hợp lệ từ `panoptic.json["categories"]` (133 lớp), duyệt `segments_info` của mọi ảnh; segment có `category_id` lạ là lỗi.

### 4.9 thing_overlap — area khai nhiều hơn pixel thật

Đọc mask PNG, đếm pixel của từng segment theo id = R + G·256 + B·256², rồi so với `area` trong `segments_info`:

```
if seg["id"] != 0 and seg["area"] > counts.get(seg["id"], 0): -> lỗi
```

`area` lớn hơn số pixel thật nghĩa là một phần segment đã bị vật khác **đè** lên mask. Bỏ id 0 (nền). Trên lô sạch: 0 ca, vì COCO khai `area` đúng bằng số pixel.

## 5. Chạy và tự đo

Mở PowerShell ở thư mục gốc repo:

```
$env:PYTHONUTF8 = "1"
py validator/validate.py runs/r3007/delivery --out runs/r3007/errors.json
py scripts/score_findings.py --run runs/r3007
```

Lặp lại cho `runs/r4001`, `runs/r6001` và `runs/clean`. Mỗi lô chạy khoảng 15 giây (phần lớn là đếm pixel mask).

### Kết quả của nhóm

| Lô | Lỗi luật báo ra | F1 lỗi luật | F1 tổng |
|---|---|---|---|
| r3007 (luyện tập) | 11 | ≈ 1.0 | ≈ 0.7 |
| r4001 | 13 | ≈ 1.0 | ≈ 0.8 |
| r6001 | 11 | ≈ 1.0 | ≈ 0.8 |
| clean (không lỗi) | 0 | 1.0 | 1.0 |

Chi tiết seed 3007: bbox_out_of_bounds 1, duplicate_box 2, guideline_mismatch 2, invalid_class 1, scene_leak 1, thing_overlap 2, wrong_hash 2.

> F1 tổng còn 0,7–0,8 là **bình thường**: lỗi gán nhãn (class_swap, bbox_drift, missing_box, category_swap, instance_merge) chưa bắt — đó là việc của Pha 2.

## 6. Sau khi xong Pha 1

- Ghi số liệu thật vào `submission/REPORT.md` mục 1 (F1 theo seed, ngưỡng và cách chọn) — đã làm.
- Ghi prompt AI, chỗ AI sai, cách kiểm lại vào `submission/prompts.md` — đã làm.
- Ở Pha 2 nên ghi lỗi luật ra file riêng để gộp: `--out runs/r3007/rules.json`, rồi dùng `scripts/merge_review.py`.
- Commit với tên của người viết: `git add validator submission` rồi `git commit -m "P1: validator 9 loi luat"`.

## 7. Chuẩn bị vấn đáp

Người chấm chọn ngẫu nhiên một đoạn validator và yêu cầu **giải thích rồi sửa khi đổi yêu cầu**. Ví dụ các câu có thể gặp:

| Câu hỏi | Gợi ý trả lời |
|---|---|
| Vì sao `wrong_hash` phải tính lại sha256? | hash giả vẫn đúng định dạng 64 ký tự; chỉ tính lại trên bytes mới biết file có khớp không |
| `scene_leak` có target là gì? | `scene_id`, vì lỗi thuộc về cả cảnh chứ không riêng ảnh nào |
| Vì sao so guideline với job? | job là nguồn chuẩn; guideline ở ảnh có thể chính là chỗ sai |
| Nếu đề đổi: box lặp lệch tới 5 px? | sửa `DUP_SHIFT_MAX_PX = 6.0`; điều kiện kích thước ≤ 0,5 px vẫn giữ báo nhầm ở 0 |
| Nếu đề đổi: cho phép tràn mép 2 px? | sửa `OOB_TOL_PX = 2.0` |
| Vì sao không dùng IoU cho duplicate_box? | cặp box tự nhiên chồng nhau tới IoU ~0,66 nhưng khác kích thước |
| `thing_overlap` đếm pixel thế nào? | id = R + G·256 + B·256², đếm theo id, bỏ id 0, so với `area` |
| Validator có chạy trên đề ẩn không? | có: không phụ thuộc tên ảnh, kích thước ảnh lấy từ panoptic hoặc header JPEG, ngưỡng theo pixel |
