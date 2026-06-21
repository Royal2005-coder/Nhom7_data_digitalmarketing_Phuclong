# Modeling Comment Corpus Pro Report

- Clean input rows: 13,742
- Modeling rows: 8,539
- Removed general/noise rows: 5,203
- Minimum comment quality: 0.35

## Business topic distribution
| business_topic_rule   |   count |
|:----------------------|--------:|
| product_taste_quality |    4550 |
| price_promotion       |    1638 |
| branch_availability   |     879 |
| brand_love_content    |     814 |
| delivery_waiting      |     288 |
| service_store_staff   |     207 |
| app_payment_order     |     163 |

## Brand distribution
| brand     |   count |
|:----------|--------:|
| highlands |    4210 |
| phuc_long |    2412 |
| katinat   |    1917 |

## Platform distribution
| platform   |   count |
|:-----------|--------:|
| tiktok     |    4595 |
| facebook   |    3944 |

## Academic note
Modeling corpus chỉ giữ các comment đã qua lọc nhiễu và có business_topic_rule rõ ràng. Các comment general_social_or_noise không đưa vào BERTopic để giảm khả năng mô hình học từ tên người, metadata mạng xã hội, từ lóng hoặc comment không có ý nghĩa quản trị.