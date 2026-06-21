# Phuc Long MCP Server-ready Tool Layer

## Mục tiêu

Lớp MCP-style tools giúp AI chatbot truy vấn sâu dữ liệu Gold SQLite và semantic layer, thay vì chỉ dựa trên prompt tĩnh.

## Database

mvp_ai_bi_phuclong/data/gold/phuclong_mvp.sqlite

## Tools

### list_gold_tables
Liệt kê các bảng trong SQLite database.

### get_table_schema
Trả schema của một bảng.

### query_gold_table
Truy vấn bảng Gold theo brand/platform.

### get_platform_performance
Trả hiệu suất nền tảng theo brand/platform.

### get_competitor_benchmark
Trả benchmark Phúc Long, Highlands, Katinat.

### get_content_pillar_performance
Trả hiệu suất theo trụ cột nội dung.

### get_sentiment_risk
Trả nhóm sentiment/risk theo brand/platform.

### get_top_posts
Trả top posts/videos theo rank_score.

### get_ai_recommendations
Trả rule-based recommendations từ Gold table.

### get_semantic_context
Trả semantic_layer, ai_decision_skill và decision_playbook.

### generate_decision_context
Tổng hợp semantic context + Gold tables thành context cho AI Copilot.

## Vai trò trong kiến trúc

- MCP dùng cho agent-to-tool/data access.
- A2A dùng cho agent-to-agent collaboration.
- Streamlit hiện gọi trực tiếp local MCP-style tools.
- Phase sau có thể bọc tool layer này thành MCP server thật cho LibreChat/n8n.
