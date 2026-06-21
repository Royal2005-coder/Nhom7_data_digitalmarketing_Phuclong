# MVP AI-BI Dashboard for Phuc Long

## Mục tiêu

MVP này minh họa quy trình chuyển hóa dữ liệu social listening đa nền tảng của Phúc Long thành hệ thống hỗ trợ ra quyết định truyền thông số.

Luồng triển khai:

1. Nạp dữ liệu clean từ data_notebook.
2. Chuẩn hóa dữ liệu theo kiến trúc Bronze - Silver - Gold.
3. Xây dựng các bảng Gold phục vụ BI Dashboard.
4. Trực quan hóa insight bằng Metabase hoặc Streamlit.
5. Tích hợp AI Agent để hỏi đáp dữ liệu và đề xuất hành động.
6. Tự động hóa cập nhật và cảnh báo bằng n8n.

## Phạm vi MVP

MVP sử dụng 4 file dữ liệu clean:

- tiktok_videos_clean.csv
- tiktok_comments_clean.csv
- facebook_posts_clean.csv
- facebook_comments_clean.csv

## Không thuộc phạm vi MVP

- Không crawl dữ liệu mới.
- Không train lại mô hình sentiment.
- Không phân tích lại toàn bộ notebook.
- Không xây production system.

## Cấu trúc thư mục

mvp_ai_bi_phuclong/
- data/
  - bronze/
  - silver/
  - gold/
- pipeline/
- dashboard/
- ai_agent/
- n8n/
- docs/
- artifacts/

## Ý nghĩa học thuật

MVP này là phần triển khai thực hành cho Chương 8, chứng minh cách dữ liệu social listening có thể được chuyển hóa thành dashboard, AI insight và đề xuất hành động cho Phúc Long.
