# Phuc Long Semantic Layer

## Vai trò hệ thống

Hệ thống AI-BI Dashboard không phân tích lại notebook mà operationalize insight từ dữ liệu social listening thành quyết định truyền thông số cho Phúc Long.

## Trọng tâm thương hiệu

Phúc Long là thương hiệu trọng tâm. Highlands và Katinat chỉ là benchmark cạnh tranh.

## Diễn giải nền tảng

### Facebook
Facebook là kênh cộng đồng, chăm sóc khách hàng, minh bạch thông tin và kích hoạt tương tác sâu. Dataset Facebook hiện không có view_count, vì vậy không dùng Facebook views hoặc engagement_rate theo views để kết luận.

### TikTok
TikTok là kênh khám phá và mở rộng độ phủ. Các chỉ số quan trọng gồm median_views, total_views, avg_engagement_rate, share_rate và comment_count.

## Diễn giải chỉ số

### total_records
Tổng số bản ghi trong bảng Gold.

### total_engagement
Tổng tương tác đã chuẩn hóa từ likes, comments, shares hoặc reactions tương đương.

### total_views
Chỉ diễn giải chắc chắn với TikTok. Facebook có thể bằng 0/N/A do thiếu trường view_count.

### median_views
Trung vị lượt xem, dùng để đánh giá độ phủ điển hình. Quan trọng hơn average views khi có video viral làm lệch trung bình.

### avg_engagement_rate
Tỷ lệ tương tác trung bình. Với TikTok, công thức dựa trên engagement_total / view_count.

### net_sentiment_score
Tín hiệu sức khỏe cảm xúc thương hiệu. Giá trị dương càng cao cho thấy tỷ lệ tích cực vượt tiêu cực càng lớn.

### risk_count
Số bản ghi chứa tín hiệu rủi ro. Đây là cảnh báo sớm, không phải kết luận khủng hoảng.

## Luật ra quyết định

### TikTok engagement cao nhưng median_views thấp
Diễn giải: nội dung phù hợp với nhóm đã tiếp cận nhưng chưa được phân phối rộng.
Hành động: tối ưu hook 3 giây đầu, video 20-30 giây, hashtag ba lớp, tăng khả năng share.

### Facebook engagement/comment/share cao
Diễn giải: kênh cộng đồng mạnh, nên dùng để giải thích thông tin, minigame, ưu đãi, CSKH.
Hành động: caption 500-1000 ký tự, CTA đối thoại, ghim comment hướng dẫn.

### Rủi ro app_payment_promotion tăng
Diễn giải: vấn đề nằm ở app, voucher, thanh toán hoặc điều kiện ưu đãi.
Hành động: ghim hướng dẫn, CSKH phản hồi nhanh, chuyển IT/Ops xử lý.

### Rủi ro taste_quality tăng
Diễn giải: đặc tính cốt trà đậm có thể bị hiểu sai thành lỗi sản phẩm.
Hành động: triển khai chuỗi Sành trà Phúc Long, hướng dẫn tùy chỉnh đường/đá.

## Content Pillars

- di_san_chat_luong: trà, cốt trà, Bảo Lộc, đậm vị, nguyên bản.
- phong_cach_trai_nghiem: không gian, cửa hàng, học tập, làm việc, chill.
- trai_nghiem_so_ket_noi: app, thành viên, voucher, delivery.
- khuyen_mai_minigame: combo, giveaway, quà tặng, ưu đãi.
- other: nhóm chưa đủ tín hiệu phân loại.
