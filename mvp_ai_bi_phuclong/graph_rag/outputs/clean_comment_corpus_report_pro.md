# Clean Comment Corpus Pro Report

- Raw comments: 23,032
- Accepted comments: 13,742
- Rejected comments: 9,290
- Accepted ratio: 59.66%
- Duplicate rejected: 1,129

## Business topic distribution
| business_topic_rule     |   count |
|:------------------------|--------:|
| general_social_or_noise |    5203 |
| product_taste_quality   |    4550 |
| price_promotion         |    1638 |
| branch_availability     |     879 |
| brand_love_content      |     814 |
| delivery_waiting        |     288 |
| service_store_staff     |     207 |
| app_payment_order       |     163 |

## Reject reason distribution
| reject_reason                                                                                 |   count |
|:----------------------------------------------------------------------------------------------|--------:|
| too_short_char|too_short_token|low_comment_quality_score                                      |    2883 |
| too_short_char|too_short_token                                                                |    1403 |
| social_meta_noise                                                                             |    1395 |
| low_comment_quality_score                                                                     |    1045 |
| too_short_char|too_short_token|high_token_noise_ratio|low_comment_quality_score               |     782 |
| too_short_token                                                                               |     466 |
| too_short_token|low_comment_quality_score                                                     |     280 |
|                                                                                               |     255 |
| too_short_char                                                                                |     214 |
| too_short_char|too_short_token|social_meta_noise                                              |     154 |
| noise_pattern                                                                                 |     114 |
| too_short_token|high_token_noise_ratio|low_comment_quality_score                              |      99 |
| too_short_char|low_comment_quality_score                                                      |      71 |
| high_token_noise_ratio|low_comment_quality_score                                              |      55 |
| too_short_char|too_short_token|noise_pattern|high_token_noise_ratio|low_comment_quality_score |      16 |
| noise_pattern|low_comment_quality_score                                                       |      13 |
| high_token_noise_ratio                                                                        |       9 |
| too_short_char|too_short_token|high_token_noise_ratio                                         |       8 |
| social_meta_noise|noise_pattern                                                               |       5 |
| too_short_char|too_short_token|noise_pattern|low_comment_quality_score                        |       5 |
| too_short_token|high_token_noise_ratio                                                        |       4 |
| noise_pattern|high_token_noise_ratio|low_comment_quality_score                                |       4 |
| too_short_char|too_short_token|noise_pattern                                                  |       3 |
| too_short_char|noise_pattern|low_comment_quality_score                                        |       2 |
| too_short_char|high_token_noise_ratio|low_comment_quality_score                               |       1 |
| noise_pattern|high_token_noise_ratio                                                          |       1 |
| too_short_char|noise_pattern                                                                  |       1 |
| too_short_char|too_short_token|social_meta_noise|low_comment_quality_score                    |       1 |
| too_short_char|noise_pattern|high_token_noise_ratio|low_comment_quality_score                 |       1 |

## Academic note
Bước này làm sạch comment trước khi đưa vào topic model. Các comment quá ngắn, comment metadata mạng xã hội, comment chứa tỷ lệ từ nhiễu cao, comment trùng lặp sau chuẩn hóa và comment không đạt comment_quality_score tối thiểu được loại khỏi corpus modeling. Cách này giúp giảm nguy cơ mô hình học topic từ tên người, từ lóng hoặc tín hiệu tương tác không có ý nghĩa quản trị.