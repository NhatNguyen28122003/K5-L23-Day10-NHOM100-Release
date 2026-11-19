# Pha 2 — Đối chiếu detection ↔ panoptic và xem ảnh
_Day 10 Lab · Nhóm 03 (An Hai) · seed luyện tập 3007 · khoảng 55 phút · file: validator/validate.py, tools/view.py_

## 1. Mục tiêu của pha

Pha 1 bắt **lỗi luật** (máy tự kết luận). Pha 2 bắt **lỗi gán nhãn**: nhãn đúng định dạng nhưng sai nội dung. Lô **không kèm nhãn gốc**, nên chỉ có hai cách:

1. **Đối chiếu hai nguồn** của cùng một ảnh: box detection (`labels/`) và mask panoptic (`masks/` + `panoptic.json`). Chỗ bất đồng là **ứng viên**.
2. **Mở ảnh ra xem** từng ứng viên: lỗi thật thì `confirmed`, lệch tự nhiên của COCO thì `rejected`.

| Loại lỗi | Sai ở đâu | Dấu hiệu khi đối chiếu |
|---|---|---|
| `class_swap` | box **detection** ghi lớp dễ nhầm | box và segment trùng vị trí, khác lớp; ảnh cho thấy **panoptic đúng** |
| `category_swap` | segment **panoptic** ghi lớp dễ nhầm | như trên; ảnh cho thấy **detection đúng** |
| `bbox_drift` | box detection bị dời khỏi vật | một phần pixel của segment cùng lớp rơi ra ngoài box |
| `missing_box` | detection thiếu box cho vật đáng kể | segment thing lớn, không crowd, không box nào ôm được |
| `instance_merge` | panoptic gộp hai vật thành một segment | pixel của **một** segment nằm trong **hai** box cùng lớp |

> **Mốc CP2 (1:50):** biết số ứng viên trên lô sạch; hàng đợi đủ nhỏ để xem hết; `review_log.csv` xong cho seed luyện tập; công cụ xem ảnh sẵn sàng cho đề ẩn.

## 2. Phân công của nhóm

| Người | Việc | Sản phẩm |
|---|---|---|
| Nguyễn Văn Nhất | Ghép box–segment, 5 quy tắc ứng viên, công cụ xem ảnh | `find_candidates()`, `tools/view.py` |
| Nguyễn Ngọc Đồng | Đo lô sạch, chốt ngưỡng, gộp kết quả, số liệu REPORT | `errors.json`, REPORT mục 1 |
| Trần Đức Kỳ | Xem ảnh; cải tiến công cụ xem ảnh | dòng review, `tools/view.py` |
| Đặng Thu Thuý | Chia hàng đợi, soát `review_log`, trả lời câu hỏi F1 | `review_log.csv`, REPORT mục 2 |
| **Cả 4** | **Mỗi người tự xem một phần hàng đợi** | dòng review mang tên mình |

## 3. Chuẩn bị máy (mỗi thành viên)

```
$env:PYTHONUTF8 = "1"
git pull
py -m pip install --user pillow
py scripts/inject_release.py --seed 3007 --out runs/r3007
py scripts/inject_release.py --seed 5 --no-faults --out runs/clean
```

Dùng `inject_release.py` chứ **không** dùng `run_lab.py` trên máy thành viên: lineage chính của nhóm nằm trên một máy, chạy `run_lab.py` sẽ ghi thêm lineage riêng. Cùng seed thì ra cùng lô (release `lab250_95697c6d4612`).

> Lệnh và code lấy theo **repo của nhóm**. File cẩm nang dùng cấu trúc khác (`crosscheck.py`, trường `type`); chạy lệnh của cẩm nang trên code nhóm sẽ lỗi `KeyError: 'type'` — code nhóm dùng `type_guess`.

## 4. Phần code: sinh ứng viên trong validate.py

### 4.1 Đọc mask một lần — `read_mask()`

- Đếm pixel **thật** của từng segment id (id = R + G·256 + B·256²) bằng `Counter` — dùng cho `thing_overlap` của Pha 1.
- Lấy mẫu toạ độ cứ **2 px một điểm** theo mỗi trục (1/4 số pixel): tỉ lệ vẫn chính xác mà chạy nhanh gấp khoảng 4 lần. Cả lô 250 ảnh chạy khoảng 16 giây.

### 4.2 Ghép hai nguồn

- Ghép lớp qua **tên**: `classes.txt` (0–79) ↔ `categories` (id gốc COCO).
- Bỏ segment **stuff** (trời, đường…) và **crowd**: chúng không có box tương ứng.
- Đổi box YOLO sang pixel, tính bbox của segment từ pixel thật.
- Hai số đo cho mỗi cặp box–segment: **tỉ lệ pixel segment nằm trong box** (tín hiệu chính) và IoU giữa box với bbox-pixel của segment.

> GUIDE nói rõ: IoU giữa hai bbox **không đủ** để bắt `bbox_drift` và `instance_merge`. Tín hiệu tốt là **pixel của mask**.

### 4.3 Bốn quy tắc cho năm loại lỗi (bản chốt)

Quy tắc lệch lớp dùng chung cho `class_swap` và `category_swap`; người xem ảnh quyết định loại nào.

| Ứng viên | Điều kiện |
|---|---|
| Lệch lớp (`swap`) | box và segment **khác lớp** trùng khít (IoU ≥ 0,85); box không khớp segment cùng lớp nào (IoU ≥ 0,7) và segment không khớp box cùng lớp nào |
| `instance_merge` | một segment có ≥ 20% pixel trong **mỗi** box của ≥ 2 box cùng lớp, và **không box nào ôm ≥ 90%** segment |
| `bbox_drift` | < 90% pixel segment cùng lớp nằm trong box; rộng/cao box chia segment trong 0,7–1,4 (box dời chỗ **giữ kích thước**); segment không thuộc box cùng lớp khác; vật ≥ 400 px |
| `missing_box` | segment thing không crowd chiếm ≥ 0,5% ảnh, không box cùng lớp nào chứa ≥ 50% pixel của nó |

Thêm hai luật chung:

- **Mỗi ảnh tối đa một ứng viên** (mỗi ảnh mang nhiều nhất một lỗi): giữ tín hiệu mạnh nhất, các tín hiệu yếu hơn ghi vào trường `also`.
- **Ảnh đã có lỗi luật không sinh ứng viên** (vì lý do trên).

Với ứng viên lệch lớp, validator chỉ ghi `type_guess = "swap"`: **chỉ mắt người** mới biết bên nào sai.

### 4.4 Định dạng candidates.json

```
{"candidates": [
  {"image": "000000009483", "type_guess": "swap",
   "det_class": "laptop", "pan_class": "tv",
   "box_px": [x1, y1, x2, y2], "segment_id": 1234567,
   "score": 2.97, "reason": "box 'laptop' trùng khít segment 'tv' (IoU 0.97); ..."}
]}
```

### 4.5 Lệnh chạy

```
py validator/validate.py runs/clean/delivery --out runs/clean/rules.json --candidates runs/clean/candidates.json
py validator/validate.py runs/r3007/delivery --out runs/r3007/rules.json --candidates runs/r3007/candidates.json
py -c "import json,collections;c=json.load(open('runs/r3007/candidates.json',encoding='utf-8'))['candidates'];print(len(c),collections.Counter(x['type_guess'] for x in c))"
```

Ghi lỗi luật ra **`rules.json`** (không phải `errors.json`): `errors.json` cuối được gộp ở bước 7.

## 5. Chọn ngưỡng bằng lô sạch

Lô sạch (`runs/clean`, 50 ảnh khác, không gài lỗi) cho biết **nhiễu tự nhiên**: mọi ứng viên ở đó đều là báo thừa. Nhóm chỉnh ngưỡng **chỉ dựa vào lô sạch** — không dùng `_private`, không dò điểm, không so ứng viên lặp lại giữa các seed cùng 250 ảnh (cũng là dò đáp án gián tiếp).

| Phiên bản | Lô sạch | Seed 3007 | Quan sát và cách sửa |
|---|---|---|---|
| v1 | 4 | 32 | cả 4 là bbox_drift — box ghép nhầm sang vật khác cùng lớp |
| v2 | 6 | 26 | thêm "giữ kích thước" + "segment chưa có chủ" nhưng bỏ sót điều kiện cũ; cả 6 là vật rất nhỏ |
| v3 | 2 | 15 | bỏ vật < 400 px, nới box 1 bước lấy mẫu; còn 2 ca merge mà một box ôm trọn 100% segment |
| **v4 (chốt)** | **0** | **8** | merge yêu cầu không box nào ôm ≥ 90%; drift < 90% |

Hàng đợi chốt seed 3007: **8 ảnh** — 4 lệch lớp, 2 thiếu box, 1 gộp vật, 1 box lệch.

> **Cần bao nhiêu ảnh review?** Đề **không** cho con số cố định: phải xem **hết hàng đợi**, và hàng đợi do ngưỡng của nhóm quyết định. Ước lượng khoảng 1 phút/ảnh: luyện tập 4 người × 15–25 phút ≈ 60–100 ảnh; đề ẩn ≈ 30–60 ảnh. Không xem cả 250 ảnh: không kịp, và ảnh hai nguồn khớp nhau gần như không có lỗi gán nhãn.

## 6. Xem ảnh với tools/view.py

```
py tools/view.py runs/r3007/delivery --candidates runs/r3007/candidates.json --out runs/r3007/review_img
start runs/r3007/review_img/index.html
py tools/view.py runs/r3007/delivery --image 000000009483 --out runs/r3007/review_img
```

| Ký hiệu trên ảnh | Ý nghĩa |
|---|---|
| `D:lớp`, khung xanh dương | box detection |
| khung **đỏ** | box của ứng viên |
| `P:lớp`, viền vàng | segment panoptic (thing) |
| tô **xanh lá** | segment của ứng viên |
| nửa phải | vùng quanh ứng viên, cắt và phóng to (ảnh nhỏ vẫn nhìn rõ) |

Công cụ **được** dùng Pillow; validator thì **không**. Công cụ chạy được với tên ảnh dạng `img_0001` của đề ẩn.

### Cách kết luận từng loại

| Ứng viên | `confirmed` khi | `rejected` khi |
|---|---|---|
| lệch lớp | một nguồn ghi đúng vật, nguồn kia sai: detection sai → `class_swap`; panoptic sai → `category_swap` | vật mơ hồ giữa hai lớp; box và segment là hai vật chồng nhau |
| `bbox_drift` | box lệch hẳn: hụt một mảng vật hoặc ôm nhiều nền / vật bên cạnh | vật bị che nên mask cụt; mask gồm cả đồ đang cầm |
| `missing_box` | vật rõ, đáng kể, không có box | vật bị che > 50% / ở mép ảnh trong job **guideline v1.2** (được phép bỏ `bottle`); vật thuộc crowd |
| `instance_merge` | hai vật tách biệt rõ nhưng chỉ có một segment | thật sự là một vật |

## 7. Ghi review_log.csv và gộp

Định dạng 4 cột, mã hoá **UTF-8**, sửa bằng trình soạn thảo văn bản (Excel dễ làm lệch cột hoặc đổi mã hoá):

```
image,type,verdict,note
000000009483,class_swap,confirmed,"[Kỳ] Vật bên phải là màn hình rời, có bàn phím riêng bên trái. Detection ghi nhầm laptop, panoptic tv phù hợp."
```

- `type` chỉ là một trong 5 loại gán nhãn, viết đúng chính tả (`missing_box`, không phải `missing-box`).
- `verdict` chỉ là `confirmed` hoặc `rejected` (gõ sai `comfirmed` thì dòng bị bỏ qua, không báo lỗi).
- `note` mở đầu bằng **[tên người xem]** rồi nói **thấy gì**. Ghi "có lỗi" / "OK" chỉ được một nửa điểm.
- Dùng **dấu phẩy** ngăn cột; ghi chú có dấu phẩy thì đặt trong ngoặc kép.

```
py scripts/merge_review.py --rules runs/r3007/rules.json --review runs/r3007/review_log.csv --out runs/r3007/errors.json
py scripts/score_findings.py --run runs/r3007
```

`merge_review.py` báo `FileNotFoundError` nghĩa là **chưa có** `review_log.csv` — phải xem ảnh trước rồi mới gộp.

### Kết quả của nhóm (seed 3007)

| Mục | Giá trị |
|---|---|
| hàng đợi | 8 ảnh, 8 `confirmed` |
| `errors.json` | 11 lỗi luật + 8 lỗi gán nhãn = 19 |
| F1 lỗi luật / gán nhãn / tổng | ≈ 1.0 / ≈ 0.9 / ≈ 0.9 |

> `score_findings.py` chỉ để biết validator tốt lên hay kém đi. Thêm/bớt từng ảnh rồi chấm lại để dò điểm là **gian lận** (RULES).

## 8. Lỗi hay gặp

| Triệu chứng | Cách xử lý |
|---|---|
| `KeyError: 'type'` khi đếm ứng viên | code nhóm dùng `type_guess` |
| máy bạn ra hàng trăm ứng viên | đang chạy code khác (cẩm nang / bản sửa tay): `git status`, `git pull` |
| `FileNotFoundError: review_log.csv` | chưa có kết luận review; tạo file rồi xem ảnh |
| bước gộp ra thiếu lỗi | dòng sai cột / sai chính tả `confirmed` / sai tên loại |
| lẫn `class_swap` và `category_swap` | nhìn vật thật: nguồn ghi đúng vật thì nguồn kia sai |
| lô sạch có nhiều ứng viên | bỏ stuff/crowd, dùng pixel mask, bỏ vật quá nhỏ |

## 9. Câu hỏi vấn đáp (CP2)

| Câu hỏi | Gợi ý trả lời |
|---|---|
| Lô sạch vẫn có thể có ứng viên — vì sao? | COCO lệch tự nhiên giữa hai nguồn: vật bị che, crowd, vật nhỏ, mask bị cắt phần bị đè. Bản v1 của nhóm ra 4/50 ảnh sạch |
| Báo hết ứng viên thì F1 đổi thế nào? | precision giảm vì báo thừa; F1 trừ FP nặng như FN. Ước tính v1: ~20/32 là lệch tự nhiên, precision ≈ 0,4 |
| Detection ghi `car`, panoptic ghi `truck`: bên nào sai? | mở ảnh, nhìn vật thật; script không quyết định được |
| Vì sao dùng pixel mask chứ không chỉ IoU? | box lệch vẫn có IoU cao; segment gộp có bbox to hơn cả hai box — chỉ đếm pixel trong từng box mới thấy |
| Vì sao điều kiện "giữ kích thước" cho bbox_drift? | box bị dời chỉ đổi vị trí; ghép nhầm sang vật khác thường khác kích thước |
| Vì sao bỏ vật < 400 px? | lệch 1–2 px do lấy mẫu đã kéo tỉ lệ xuống: cả 6 ca giả trên lô sạch (v2) là vật nhỏ |
