# Bảo mật khi làm việc

> Gắn với lô nhóm 03 vừa bàn giao: v1 `lab250_95697c6d4612` (250 ảnh, HOLD) và v2 `lab250_95697c6d4612_v2` (241 ảnh, 9 ảnh rework giao A02–A05 / Q01–Q03).

## 1. Ca USB: hết giờ, muốn chép lô về nhà làm tiếp
Không chép lô ra USB, không gửi qua email cá nhân, không nhờ người ngoài dự án làm hộ. Lô `lab250_95697c6d4612` chứa 250 ảnh có người thật (ví dụ 000000001296, 000000019924) cùng nhãn và thông tin người gán/người kiểm (A02–A05, Q01–Q03): đây là dữ liệu của khách hàng, chỉ được xử lý trên hạ tầng công ty. USB dễ mất, email cá nhân nằm ngoài kiểm soát truy cập và nhật ký, người làm hộ không ký cam kết bảo mật và không có quyền với dữ liệu. Cách đúng: dừng ở mốc hiện tại, lưu tiến độ (review_log, rework_queue) trên máy/kho của công ty, báo trưởng nhóm nếu cần thêm thời gian; nếu bắt buộc làm từ xa thì xin quyền VPN/máy ảo của công ty, không tự mang dữ liệu ra.

## 2. Năm việc: được hay không
- **Mở job được giao trên máy công ty — ĐƯỢC.** Đúng người, đúng quyền, đúng hạ tầng; ví dụ A04 mở J04 để gán lại 000000007795 và 000000009483 trong rework_queue.
- **Chụp màn hình gửi người quen — KHÔNG.** Ảnh chụp màn hình vẫn là dữ liệu (mặt người, nhãn, mã job), ra khỏi hệ thống là mất kiểm soát, không thu hồi được.
- **Chép lô ra USB — KHÔNG.** Như ca 1: dễ thất lạc, không có nhật ký truy cập, vi phạm thoả thuận xử lý dữ liệu.
- **Dán nhãn/ảnh thật lên chatbot công cộng — KHÔNG.** Dữ liệu gửi lên dịch vụ ngoài có thể bị lưu, dùng để huấn luyện, nằm ngoài hợp đồng. (Trong lab, ảnh COCO là dữ liệu công khai nên được dán và nhóm ghi lại trong prompts.md; với dữ liệu dự án thật thì không.)
- **Đưa tài khoản CVAT cho đồng nghiệp — KHÔNG.** Mỗi nhãn phải truy được đúng người: truyvet.csv và rework_queue.csv giao việc theo mã người gán/người kiểm; dùng chung tài khoản làm sai truy vết và trách nhiệm. Đồng nghiệp cần việc thì xin quyền riêng.

## 3. Ca khuôn mặt: thấy mặt người rõ trong lô, guideline yêu cầu làm mờ
Lô của nhóm có nhiều ảnh thấy rõ mặt người, ví dụ **000000001296** (cô gái cầm điện thoại chụp ảnh, mặt nhìn thẳng), **000000019924** (người phụ nữ đội mũ rộng vành, cận mặt), 000000004395 và 000000016598. Kết luận: **Hold** lô (không bàn giao, không Release) và **báo người phụ trách** dự án/bảo mật dữ liệu, kèm danh sách tên ảnh và vị trí. Không tự làm mờ hay tự xoá ảnh vì: (1) làm mờ là sửa dữ liệu — lô đã giao phải giữ nguyên, sửa là bản mới có lineage, có người duyệt; (2) cách làm mờ (vùng, mức độ, có ảnh hưởng nhãn person không) phải theo quy trình chung cho cả lô và các job khác, không do một người quyết; (3) xoá ảnh làm mất bằng chứng và lệch manifest, số liệu QC. Người phụ trách quyết định làm mờ có kiểm soát rồi phát hành bản mới, ghi vào lineage.
