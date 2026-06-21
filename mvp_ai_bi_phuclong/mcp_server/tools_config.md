# MCP Tools Config - Phuc Long AI-BI

## get_platform_performance

Input:
- brand: optional string
- platform: optional string

Use case:
- Hỏi hiệu suất TikTok/Facebook của Phúc Long.
- So sánh median_views, engagement_rate, total_comments, total_shares.

## get_content_pillar_performance

Input:
- brand
- platform

Use case:
- Hỏi trụ cột nội dung nào nên ưu tiên.

## get_sentiment_risk

Input:
- brand
- platform
- top_n

Use case:
- Hỏi rủi ro nào cần xử lý trước.

## get_top_posts

Input:
- brand
- platform
- top_n
- keyword

Use case:
- Hỏi bài/video nào đang nổi bật và vì sao.

## generate_decision_context

Input:
- brand
- platform

Use case:
- Chatbot trả lời câu hỏi tự nhiên dựa trên semantic layer + Gold tables.
