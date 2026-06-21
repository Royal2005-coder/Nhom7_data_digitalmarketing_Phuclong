# Phuc Long AI-BI Decision Intelligence Architecture

## 1. Mục tiêu

Hệ thống MVP minh họa cách chuyển dữ liệu social listening đa nền tảng thành hệ hỗ trợ ra quyết định cho Phúc Long.

Mục tiêu không phải phân tích lại notebook, mà là operationalize insight:
- Chuẩn hóa dữ liệu.
- Trực quan hóa chỉ số.
- Diễn giải bằng semantic layer.
- Kích hoạt AI Copilot.
- Mô phỏng phối hợp multi-agent A2A-ready.
- Chuẩn bị MCP/n8n automation.

## 2. Data Engineering Layer

### Bronze
Lưu dữ liệu clean gốc từ data_notebook.

### Silver
Chuẩn hóa schema:
- brand
- platform
- created_at
- time_slot
- text
- engagement_total
- sentiment_label
- risk_group
- content_pillar

### Gold
Tạo bảng phục vụ quyết định:
- gold_competitor_benchmark
- gold_platform_performance
- gold_content_pillar_performance
- gold_sentiment_risk_monitoring
- gold_post_ranking
- gold_ai_action_recommendation

## 3. Semantic Layer

Semantic layer bổ sung ý nghĩa kinh doanh cho metric:
- Facebook views có thể N/A vì dataset không có view_count.
- TikTok median_views phản ánh độ phủ điển hình.
- Engagement rate TikTok phản ánh khả năng kích hoạt trong nhóm đã tiếp cận.
- Risk groups là tín hiệu cảnh báo sớm, không phải kết luận khủng hoảng.
- Phúc Long là trọng tâm; Highlands/Katinat chỉ là benchmark.

## 4. BI Layer

Streamlit dashboard gồm:
1. Executive Overview
2. Platform Deep-dive
3. Content Intelligence
4. Sentiment & Risk Monitoring
5. Top Posts Explorer
6. AI Copilot

## 5. AI Copilot Layer

AI Copilot dùng:
- Gold tables
- Semantic layer
- AI decision skill
- User question

Output:
- Insight chính
- Bằng chứng dữ liệu
- Diễn giải nguyên nhân
- Hành động đề xuất
- Mức ưu tiên
- Bộ phận phụ trách
- Rủi ro cần theo dõi

## 6. A2A-ready Multi-Agent Layer

Các agent chuyên biệt:
- Insight Agent
- Risk Agent
- Content Strategy Agent
- Executive Decision Agent

Trong MVP, các agent chạy tuần tự trong Streamlit.
Trong production, mỗi agent có thể được đóng gói thành A2A-compatible service.

## 7. MCP-ready Tool Layer

MCP tools dự kiến:
- query_gold_table
- get_platform_performance
- get_content_pillar_performance
- get_sentiment_risk
- get_top_posts
- generate_decision_brief

MCP dùng để agent truy cập database/tool.
A2A dùng để các agent giao tiếp và phối hợp quyết định.

## 8. n8n Automation Layer

Workflow đề xuất:
1. Data Refresh Workflow
2. Risk Alert Workflow
3. Weekly Decision Brief Workflow

## 9. Production Hardening

Cần bổ sung:
- Secret management
- Auth dashboard
- PostgreSQL thay SQLite khi nhiều user
- AI request logging
- Prompt/response cache
- Data masking user-level
- Cloudflare Access
- MCP server
- A2A service deployment
