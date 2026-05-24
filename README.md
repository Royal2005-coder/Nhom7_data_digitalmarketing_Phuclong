# Nhom7 - Phan tich hieu qua noi dung so Phuc Long Coffee & Tea

## Du an: Ung dung Hoc may danh gia hieu qua noi dung so cua Phuc Long Coffee & Tea trong boi canh canh tranh nganh va de xuat giai phap toi uu

### Dataset Overview

| Dataset | Phuc Long | Highlands | Katinat | Tong |
|---|---|---|---|---|
| TikTok Videos | 240 | 250 | 250 | **740** |
| TikTok Comments | 2,052 | 5,471 | 2,636 | **10,159** |
| Facebook Posts | 1,141 | 1,601 | 1,587 | **4,329** |
| Facebook Comments | 3,931 | 5,045 | 4,014 | **12,990** |
| **TONG** | **7,364** | **12,367** | **8,487** | **28,218** |

### Data Quality: OVERALL A+

| Tieu chi | Score |
|---|---|
| TikTok Videos (739/740 ML-ready) | A+ |
| Facebook Posts (3,444/4,329 ML-ready) | A+ |
| Comments PhoBERT (22,910 usable) | A+ |
| Data Integrity (0 loi) | A+ |

---

## Quick Start - Google Colab

```python
import pandas as pd

BASE = "https://raw.githubusercontent.com/Royal2005-coder/Nhom7_data_digitalmarketing_Phuclong/main/data_notebook/"

tt_videos   = pd.read_csv(BASE + "tiktok_videos_clean.csv")
tt_comments = pd.read_csv(BASE + "tiktok_comments_clean.csv")
fb_posts    = pd.read_csv(BASE + "facebook_posts_clean.csv")
fb_comments = pd.read_csv(BASE + "facebook_comments_clean.csv")

print(f"TikTok Videos:   {len(tt_videos)} rows")
print(f"TikTok Comments: {len(tt_comments)} rows")
print(f"Facebook Posts:  {len(fb_posts)} rows")
print(f"Facebook Comments: {len(fb_comments)} rows")
```

---

## Cau truc Workspace

```
project/
|-- crawl/                          # Core crawl scripts (10 files)
|   |-- v3_config.py                # Cau hinh chung: BRANDS, DB, export
|   |-- v3_tiktok_videos.py         # Crawl TikTok videos (yt-dlp)
|   |-- v3_tiktok_comments.py       # Crawl TikTok comments (curl_cffi + msToken)
|   |-- v3_facebook_posts.py        # Crawl FB posts (DOM extraction)
|   |-- v3_facebook_posts_apify.py  # Crawl FB posts (Apify GraphQL)
|   |-- v3_facebook_posts_browser.py# Crawl FB posts (CloakBrowser)
|   |-- v3_facebook_comments.py     # Crawl FB comments (mbasic parse)
|   |-- v3_facebook_fill_engagement.py # Fill engagement tu detail page
|   |-- v3_orchestrator.py          # Dieu phoi toan bo pipeline
|   |-- v3_token_harvester.py       # Thu hoach msToken/cookies
|
|-- data_notebook/                  # 4 CSV clean cho Colab/Notebook
|   |-- tiktok_videos_clean.csv     # 740 rows
|   |-- tiktok_comments_clean.csv   # 10,159 rows
|   |-- facebook_posts_clean.csv    # 4,329 rows
|   |-- facebook_comments_clean.csv # 12,990 rows
|
|-- data/                           # Raw data + SQLite DB
|   |-- social_listening.db         # Co so du lieu chinh
|   |-- raw/                        # 4 CSV raw exported
|
|-- temp_restore/                   # Apify legacy structure (tham khao)
|-- README.md
```

---

## Ky thuat Crawl

| Ky thuat | Du lieu | Cong cu | So luong |
|---|---|---|---|
| yt-dlp subprocess | TikTok Videos | yt-dlp + JSON extract | 740 |
| curl_cffi + msToken | TikTok Comments | TLS fingerprint chrome120 | 10,159 |
| Apify GraphQL | Facebook Posts | apify/facebook-posts-scraper | 2,686 |
| CloakBrowser DOM | Facebook Posts | Playwright + stealth | 1,260 |
| curl_cffi + mbasic | Facebook Comments | mbasic.facebook.com parse | 12,990 |

---

## Tech Stack

- **Python 3.12** - Ngon ngu chinh
- **SQLite** - Co so du lieu
- **yt-dlp** - Crawl TikTok metadata
- **curl_cffi** - HTTP client voi TLS fingerprint
- **Apify** - Facebook Posts scraper
- **Playwright** - Browser automation
- **BeautifulSoup** - HTML parsing
- **pandas** - Data processing
- **PhoBERT** - Vietnamese sentiment analysis (notebook)
- **scikit-learn / LightGBM** - ML models (notebook)

---

## San sang cho phan tich

1. PhoBERT Sentiment Analysis - 22,910 comments tieng Viet
2. Random Forest / LightGBM Engagement Prediction
3. SHAP Feature Importance
4. Topic Modeling (LDA/BERTopic)
5. Graph Network Analysis
6. Temporal Analysis (4 nam data: 2022-2026)

---

## Team - Nhom 7

| Vai tro | Thanh vien |
|---|---|
| Data Engineer | Nhom 7 |
| ML Engineer | Nhom 7 |
| Analyst | Nhom 7 |

**Truong Dai hoc Kinh te - Luat (UEL)**

---

*Dataset crawled: 25/05/2026 | Validated: A+ | Records: 28,218*
