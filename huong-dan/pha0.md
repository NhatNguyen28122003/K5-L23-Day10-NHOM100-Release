# Pha 0 — Chuẩn bị
_Day 10 Lab · Bàn giao dataset & Truy vết · Nhóm 03 (An Hai) · seed luyện tập 3007 · khoảng 15 phút_

## 1. Mục tiêu của pha

Pha 0 dựng sẵn mọi thứ để các pha sau chỉ còn việc viết code và xem ảnh. Hết pha này, nhóm phải có:

- Dữ liệu gốc đã tải về máy (`data_source/`, khoảng 1 GB).
- Lô luyện tập `runs/r3007/delivery/` gồm 250 ảnh có lỗi gài sẵn theo seed.
- Nhật ký lineage `runs/lineage.jsonl` có training run `R-021` gắn với lô v1.
- Thêm vài lô phụ để thử validator: một seed khác và một **lô sạch** (không gài lỗi).
- `submission/TEAM.md` ghi rõ ai làm phần nào, và một commit mở đầu.

| Mốc | Tự kiểm tra (CP0, phút 0:15) |
|---|---|
| Dữ liệu | `data_source/` đã có, script tải báo `ready` |
| Lô luyện tập | thư mục `runs/r3007/delivery` tồn tại, có 250 ảnh |
| Chia việc | `TEAM.md` có đủ thành viên, MSHV, tài khoản GitHub, phần chính |

## 2. Chuẩn bị máy (Windows)

Lab chỉ cần **Python 3.10 trở lên**, không cần GPU, không cần `pip install` cho bài làm. Kiểm tra phiên bản:

```
py --version
```

Trên máy nhóm: Python 3.13.14, đạt yêu cầu.

> **Bắt buộc trên Windows:** trước khi chạy bất kỳ script nào, đặt biến môi trường UTF-8 trong cửa sổ PowerShell đang dùng. Cờ `-X utf8` KHÔNG truyền sang tiến trình con, nên `run_lab.py` vẫn chết ở dòng in tiếng Việt nếu chỉ dùng cờ.
> Mỗi lần mở PowerShell mới, gõ: `$env:PYTHONUTF8 = "1"`

Quy ước gõ lệnh: luôn chạy **từ thư mục gốc repo**; trên Windows gọi `py` thay cho `python3`; không nối lệnh bằng `&&`, chạy từng lệnh một.

## 3. Các bước thực hiện

### Bước 1 — Tải dữ liệu (một lần, khoảng 1 GB)

```
py scripts/download_public.py
```

Script tải về `data_source/`:

- `annotations_trainval2017.zip` (khoảng 250 MB) và `panoptic_annotations_trainval2017.zip`: annotation COCO gốc, dùng để **sinh** lô.
- 250 ảnh COCO val2017 cho bộ luyện tập, cộng 50 ảnh pool `calib` cho lô sạch.

Dấu hiệu xong: các dòng `ready coco250...` và `ready coco_panoptic250...`. Tải bị đứt thì cứ chạy lại: file đã có sẽ báo `cached`, không tải lại.

> **Không bao giờ** cho validator đọc `data_source/`. Đó là nhãn gốc; dùng nó là gian lận (RULES.md).

### Bước 2 — Chọn seed và tạo lô luyện tập

Quy ước của GUIDE: seed = số nhóm × 1000 + 7. Nhóm 03 nên **seed = 3007**.

```
py scripts/run_lab.py --seeds 3007
```

Lệnh này làm ba việc:

1. Gọi `inject_release.py` sinh `runs/r3007/delivery/` (lô v1 có lỗi gài) và `runs/r3007/_private/` (đáp án, nhóm KHÔNG được đọc).
2. Ghi sự kiện `inject` vào `runs/lineage.jsonl`.
3. Lần chạy đầu tiên: ghi sự kiện `train` — training run **R-021** đã train trên lô v1 này. Pha 3 sẽ dùng nó để hỏi "run nào bị ảnh hưởng".

Kết quả của nhóm:

| Thông tin | Giá trị |
|---|---|
| seed | 3007 |
| release_id v1 | `lab250_95697c6d4612` |
| lineage | 2 dòng: `inject` và `train R-021` |

> **Chỉ chạy `run_lab.py` MỘT lần.** Chạy lại sẽ gắn thêm dòng vào lineage. Nếu lỡ làm hỏng `delivery/` (ví dụ sửa tay), mới tạo lại bằng `run_lab.py` cùng seed.
> Nếu lần đầu chết vì lỗi `UnicodeEncodeError` (chưa đặt PYTHONUTF8): kiểm tra `runs/lineage.jsonl` — nếu chưa có dòng nào thì chạy lại an toàn.

### Bước 3 — Tạo lô phụ để thử validator

Validator phải đúng trên **mọi seed**, không chỉ seed của nhóm. Tạo thêm lô bằng `inject_release.py` (không đụng lineage):

```
py scripts/inject_release.py --seed 4001 --out runs/r4001
py scripts/inject_release.py --seed 6001 --out runs/r6001
py scripts/inject_release.py --seed 5 --no-faults --out runs/clean
```

- `runs/r4001`, `runs/r6001`: lô có lỗi với seed khác, để kiểm validator không "học thuộc" seed 3007.
- `runs/clean`: **50 ảnh khác** (pool calib), **không gài lỗi**. Dùng để đo báo nhầm: validator luật phải báo 0 lỗi ở đây; ở Pha 2 nó cho biết số ứng viên "lệch tự nhiên" của COCO.

### Bước 4 — Đọc định dạng lô

Đọc `docs/DELIVERY.md`, rồi mở thử `runs/r3007/delivery/`:

| File / thư mục | Nội dung | Ghi chú |
|---|---|---|
| `images/*.jpg` | 250 ảnh COCO | có thể thiếu file (lỗi `missing_image`) |
| `labels/*.txt` | nhãn YOLO: `class_id xc yc w h` chuẩn hoá 0–1 | lớp 0–79 |
| `masks/*.png` | mask panoptic, id segment = R + G·256 + B·256² | đọc bằng `scripts/pngutil.py` |
| `panoptic.json` | `categories` (133 lớp), `images` (kích thước), `annotations` (`segments_info`: id, category_id, area, bbox, iscrowd) | category_id là id COCO gốc |
| `classes.txt` | 80 dòng `class_id tên` | ghép với panoptic qua **tên** lớp |
| `manifest.json` | mỗi ảnh: đường dẫn image/label/mask + sha256 từng file | nguồn của `wrong_hash` |
| `metadata.json` | mỗi ảnh: scene_id, split, job_id, guideline_version | 5 ảnh/cảnh |
| `jobs.csv` | job_id, annotator, reviewer, guideline | 10 job × 25 ảnh; J01–J04 v1.2, J05–J10 v1.3 |
| `guideline/changelog.md` | v1.3 đổi quy tắc lớp `bottle` | dùng ở Pha 5 |
| `incoming/ticket.md` | team AI báo thiếu box `bottle` ở scene_197, scene_309 | dùng ở Pha 5 |
| `release.json` | release_id của v1 | dùng ở Pha 3–4 |

> **Không sửa bất cứ thứ gì trong `delivery/`.** release_id được tính từ sha256 của manifest và metadata; sửa một byte là `check_handover.py` báo H1 FAIL ở Pha 4.

### Bước 5 — Chia việc và điền TEAM.md

Phân công của nhóm (bản trong `submission/TEAM.md`):

| Thành viên | GitHub | Phần chính |
|---|---|---|
| Nguyễn Văn Nhất | NhatNguyen28122003 | validator luật / đối chiếu |
| Nguyễn Ngọc Đồng | IsMeNotee | đối chiếu / review |
| Trần Đức Kỳ | STSGx5 | truy vết / bảo mật |
| Đặng Thu Thuý | thuythu0312 | bảo mật / bàn giao |

Ai cũng phải **xem ảnh** ở Pha 2, và phải giải thích được phần mình làm khi vấn đáp.

### Bước 6 — Commit

```
git add -A
git commit -m "P0: chia viec, chon seed 3007"
git push
```

`runs/` và `data_source/` đã nằm trong `.gitignore` nên không bị commit. Bài làm sẽ được chép sang `submission/` bằng `scripts/export_submission.py` lúc nộp.

> Rubric yêu cầu **mỗi người ít nhất 2 commit có nội dung, mang tên và email của mình**. Mỗi bạn tự commit phần việc của mình bằng tài khoản riêng (kiểm tra `git config user.name` và `git config user.email` trên máy mình).

## 4. Lỗi hay gặp ở Pha 0

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `UnicodeEncodeError: 'charmap' codec` | console Windows dùng cp1252 | `$env:PYTHONUTF8 = "1"` rồi chạy lại |
| `Chưa có dữ liệu. Chạy: ...download_public.py` | chưa tải xong | chạy lại script tải, đợi dòng `ready` |
| lineage có 2 dòng `train` | chạy `run_lab.py` hai lần | xoá `runs/` và chạy lại một lần duy nhất |
| bạn khác pull về bị lệch lịch sử | đã force push | `git fetch` rồi `git reset --hard origin/main` (mất thay đổi chưa commit) |

## 5. Câu hỏi tự kiểm tra

- Vì sao validator không được đọc `_private/` và `data_source/`? (Ngoài đời người kiểm không có nhãn gốc; nếu có thì đã không cần QC.)
- Vì sao cần lô sạch? (Để đo báo nhầm: lỗi luật phải 0, còn ứng viên đối chiếu là "nhiễu tự nhiên" của COCO.)
- Vì sao chỉ chạy `run_lab.py` một lần? (Lineage là nhật ký; ghi trùng `train R-021` làm sai câu trả lời "run nào bị ảnh hưởng".)
