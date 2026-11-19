# Dùng AI

| # | Ai dùng | Công cụ | Prompt (tóm tắt) | AI sai ở đâu | Nhóm kiểm lại thế nào |
|---|---|---|---|---|---|
| 1 | Nguyễn Văn Nhất | Claude Code | "Bắt đầu viết validator cho Pha 1 (hướng dẫn chi tiết tiếng Việt)": viết `validator/validate.py` 9 lỗi luật theo DELIVERY.md, chỉ thư viện chuẩn | Bản đầu đặt ngưỡng `duplicate_box` chênh kích thước <= 1 px / lệch <= 3 px: sát một cặp box tự nhiên (chênh 1,39 px, lệch 2,98 px ở seed 6001) | Đo mọi cặp box cùng lớp trên lô sạch + 3 seed, siết còn <= 0,5 px / nới lệch <= 4 px; chạy `score_findings.py` (rule F1 ≈ 1.0 trên 3007, 4001, 6001) và lô sạch (0 lỗi) |
