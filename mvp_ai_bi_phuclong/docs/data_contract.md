# Data Contract - MVP AI-BI Dashboard Phuc Long

## 1. Nguồn dữ liệu

| File | Mô tả | Vai trò |
|---|---|---|
| tiktok_videos_clean.csv | Dữ liệu video TikTok | Phân tích hiệu suất video ngắn |
| tiktok_comments_clean.csv | Dữ liệu bình luận TikTok | Phân tích cảm xúc và phản hồi người dùng |
| facebook_posts_clean.csv | Dữ liệu bài đăng Facebook | Phân tích hiệu suất nội dung cộng đồng |
| facebook_comments_clean.csv | Dữ liệu bình luận Facebook | Phân tích cảm xúc, rủi ro và thảo luận |

## 2. Kiến trúc dữ liệu

### Bronze

Lưu dữ liệu đầu vào gần với trạng thái gốc sau khi đã clean ở notebook.

### Silver

Chuẩn hóa các trường dữ liệu quan trọng:

- platform
- brand
- created_at
- date
- hour
- weekday
- time_slot
- text
- engagement_total
- engagement_rate
- sentiment_label
- content_pillar
- risk_keyword_flag

### Gold

Tổng hợp thành bảng phục vụ dashboard và AI Agent:

- gold_brand_overview_daily
- gold_platform_performance
- gold_content_pillar_performance
- gold_sentiment_risk_monitoring
- gold_competitor_benchmark
- gold_post_ranking
- gold_ai_action_recommendation

## 3. Nguyên tắc sử dụng dữ liệu

- Dashboard chỉ đọc dữ liệu từ tầng Gold.
- AI Agent chỉ trả lời dựa trên dữ liệu Gold hoặc summary được xuất từ Gold.
- Không phân tích lại notebook ở Chương 8.
- Không tự bịa số liệu nếu dữ liệu không có.
