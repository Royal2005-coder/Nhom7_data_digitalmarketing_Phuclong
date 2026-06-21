import re
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
BRONZE_DIR = BASE_DIR / "data" / "bronze"
SILVER_DIR = BASE_DIR / "data" / "silver"
GOLD_DIR = BASE_DIR / "data" / "gold"
LOG_DIR = BASE_DIR / "artifacts" / "logs"

for d in [SILVER_DIR, GOLD_DIR, LOG_DIR]:
    d.mkdir(parents=True, exist_ok=True)


BRONZE_FILES = {
    "tiktok_videos": "tiktok_videos_clean.csv",
    "tiktok_comments": "tiktok_comments_clean.csv",
    "facebook_posts": "facebook_posts_clean.csv",
    "facebook_comments": "facebook_comments_clean.csv",
}


BRANDS = {
    "phuc_long": ["phúc long", "phuc long", "phuclong"],
    "highlands": ["highlands", "highland"],
    "katinat": ["katinat"],
}


POSITIVE_WORDS = [
    "ngon", "thơm", "thom", "đậm", "dam", "đậm vị", "dam vi", "mê", "me",
    "thích", "thich", "xịn", "xin", "ổn", "on", "tốt", "tot", "chill",
    "đẹp", "dep", "dễ thương", "de thuong", "nghiền", "nghien", "ưng", "ung",
    "tuyệt", "tuyet", "hợp", "hop", "nguyên bản", "nguyen ban"
]

NEGATIVE_WORDS = [
    "dở", "do", "tệ", "te", "đắng", "dang", "nhạt", "nhat", "lỗi", "loi",
    "chậm", "cham", "chờ lâu", "cho lau", "hết hàng", "het hang", "hết quà",
    "het qua", "mắc", "mac", "đắt", "dat", "khó chịu", "kho chiu", "thất vọng",
    "that vong", "không ngon", "khong ngon", "nhiều đá", "nhieu da"
]

RISK_KEYWORDS = {
    "app_payment_promotion": ["app", "ứng dụng", "ung dung", "mã", "ma", "voucher", "khuyến mãi", "khuyen mai", "thanh toán", "thanh toan", "lỗi", "loi"],
    "stock_gift": ["hết hàng", "het hang", "hết quà", "het qua", "sold out", "không còn", "khong con"],
    "taste_quality": ["đắng", "dang", "đậm", "dam", "nhạt", "nhat", "nhiều đá", "nhieu da", "ít trà", "it tra"],
    "service_store": ["nhân viên", "nhan vien", "thái độ", "thai do", "chờ lâu", "cho lau", "đông", "dong", "xếp hàng", "xep hang"],
}


CONTENT_PILLARS = {
    "di_san_chat_luong": [
        "trà", "tra", "đậm vị", "dam vi", "nguyên bản", "nguyen ban", "bảo lộc",
        "bao loc", "pha chế", "pha che", "thơm", "thom", "vị trà", "vi tra"
    ],
    "phong_cach_trai_nghiem": [
        "quán", "quan", "cửa hàng", "cua hang", "không gian", "khong gian",
        "chill", "góc", "goc", "hẹn", "hen", "học", "hoc", "làm việc", "lam viec"
    ],
    "trai_nghiem_so_ket_noi": [
        "app", "ứng dụng", "ung dung", "thành viên", "thanh vien", "voucher",
        "đặt hàng", "dat hang", "delivery", "online", "ưu đãi", "uu dai"
    ],
    "khuyen_mai_minigame": [
        "khuyến mãi", "khuyen mai", "giảm", "giam", "deal", "combo", "minigame",
        "giveaway", "quà", "qua", "mua", "tặng", "tang", "voucher"
    ],
}


def read_csv_safely(path: Path) -> pd.DataFrame:
    encodings = ["utf-8-sig", "utf-8", "cp1258", "cp1252", "latin1"]
    last_error = None
    for enc in encodings:
        try:
            return pd.read_csv(path, encoding=enc, low_memory=False)
        except Exception as exc:
            last_error = exc
    raise RuntimeError(f"Cannot read {path}. Last error: {last_error}")


def normalize_col_name(col: str) -> str:
    col = str(col).strip().lower()
    col = re.sub(r"[^a-z0-9_]+", "_", col)
    col = re.sub(r"_+", "_", col).strip("_")
    return col


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [normalize_col_name(c) for c in df.columns]
    return df


def first_existing_col(df: pd.DataFrame, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None


def detect_brand_from_text(value: str) -> str:
    text = str(value).lower()
    for brand, patterns in BRANDS.items():
        for p in patterns:
            if p in text:
                return brand
    return "unknown"


def normalize_brand(value, fallback_text="") -> str:
    if pd.notna(value) and str(value).strip():
        raw = str(value).strip().lower()
        detected = detect_brand_from_text(raw)
        if detected != "unknown":
            return detected
        if "phuc" in raw or "phúc" in raw:
            return "phuc_long"
        if "high" in raw:
            return "highlands"
        if "kat" in raw:
            return "katinat"
    return detect_brand_from_text(fallback_text)


def parse_datetime_series(series: pd.Series) -> pd.Series:
    if series is None:
        return pd.Series(pd.NaT)
    s = series.astype(str).str.replace("T", " ", regex=False).str.replace("Z", "", regex=False)
    return pd.to_datetime(s, errors="coerce", format="mixed")


def to_numeric_safe(series, default=0):
    if series is None:
        return pd.Series(default)
    return pd.to_numeric(series, errors="coerce").fillna(default)


def score_sentiment(text: str):
    t = str(text).lower()
    pos = sum(1 for w in POSITIVE_WORDS if w in t)
    neg = sum(1 for w in NEGATIVE_WORDS if w in t)
    score = pos - neg
    if score > 0:
        return "positive", score
    if score < 0:
        return "negative", score
    return "neutral", score


def detect_risk(text: str):
    t = str(text).lower()
    matched = []
    for group, keywords in RISK_KEYWORDS.items():
        if any(k in t for k in keywords):
            matched.append(group)
    if not matched:
        return "none"
    return "|".join(matched)


def detect_content_pillar(text: str):
    t = str(text).lower()
    scores = {}
    for pillar, keywords in CONTENT_PILLARS.items():
        scores[pillar] = sum(1 for k in keywords if k in t)
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "other"
    return best


def make_time_slot(hour):
    try:
        h = int(hour)
    except Exception:
        return "unknown"
    if 6 <= h < 11:
        return "morning_6_11"
    if 11 <= h < 14:
        return "lunch_11_14"
    if 14 <= h < 18:
        return "afternoon_14_18"
    if 18 <= h < 22:
        return "evening_18_22"
    return "night_22_6"


def standardize_posts(df: pd.DataFrame, source_name: str, platform: str) -> pd.DataFrame:
    df = normalize_columns(df)

    text_col = first_existing_col(df, [
        "text", "caption", "description", "content", "message", "post_text", "video_description", "desc"
    ])
    brand_col = first_existing_col(df, ["brand", "brand_name", "page_name", "author", "channel", "account"])
    date_col = first_existing_col(df, [
        "created_at", "create_time", "publish_time", "published_time", "time", "datetime", "date", "timestamp"
    ])

    like_col = first_existing_col(df, ["like_count", "likes_count", "likes", "like", "digg_count", "diggcount", "likecount", "reactions", "reaction_count"])
    comment_col = first_existing_col(df, ["comment_count", "comments_count", "commentcount", "comments", "comment", "comment_total", "reply_count"])
    share_col = first_existing_col(df, ["share_count", "shares_count", "sharecount", "shares", "share"])
    view_col = first_existing_col(df, ["view_count", "views_count", "viewcount", "views", "view", "play_count", "playcount", "play", "plays"])

    out = pd.DataFrame(index=df.index)
    out["source_row_id"] = range(1, len(df) + 1)
    out["source_name"] = source_name
    out["platform"] = platform
    out["record_type"] = "post"

    if text_col:
        out["text"] = df[text_col].fillna("").astype(str)
    else:
        out["text"] = ""

    if brand_col:
        out["brand"] = [
            normalize_brand(v, fallback_text=t)
            for v, t in zip(df[brand_col], out["text"])
        ]
    else:
        out["brand"] = out["text"].apply(detect_brand_from_text)

    if date_col:
        out["created_at"] = parse_datetime_series(df[date_col])
    else:
        out["created_at"] = pd.NaT

    out["date"] = out["created_at"].dt.date.astype(str)
    out["hour"] = out["created_at"].dt.hour
    out["weekday"] = out["created_at"].dt.day_name()
    out["time_slot"] = out["hour"].apply(make_time_slot)

    out["like_count"] = to_numeric_safe(df[like_col] if like_col else None)
    out["comment_count"] = to_numeric_safe(df[comment_col] if comment_col else None)
    out["share_count"] = to_numeric_safe(df[share_col] if share_col else None)
    out["view_count"] = to_numeric_safe(df[view_col] if view_col else None)

    out["engagement_total"] = out["like_count"] + out["comment_count"] + out["share_count"]
    out["engagement_rate"] = out.apply(
        lambda r: float(r["engagement_total"]) / float(r["view_count"]) if float(r["view_count"]) > 0 else None,
        axis=1,
    )
    out["comment_depth"] = out.apply(
        lambda r: float(r["comment_count"]) / float(r["engagement_total"]) if float(r["engagement_total"]) > 0 else 0,
        axis=1,
    )
    out["share_rate"] = out.apply(
        lambda r: float(r["share_count"]) / float(r["view_count"]) if float(r["view_count"]) > 0 else None,
        axis=1,
    )

    sentiments = out["text"].apply(score_sentiment)
    out["sentiment_label"] = sentiments.apply(lambda x: x[0])
    out["sentiment_score"] = sentiments.apply(lambda x: x[1])
    out["risk_group"] = out["text"].apply(detect_risk)
    out["risk_keyword_flag"] = out["risk_group"].apply(lambda x: x != "none")
    out["content_pillar"] = out["text"].apply(detect_content_pillar)

    out["caption_length"] = out["text"].str.len()
    out["is_phuc_long"] = out["brand"].eq("phuc_long")

    return out


def standardize_comments(df: pd.DataFrame, source_name: str, platform: str) -> pd.DataFrame:
    df = normalize_columns(df)

    text_col = first_existing_col(df, [
        "text", "comment_text", "comment", "content", "message", "body"
    ])
    brand_col = first_existing_col(df, ["brand", "brand_name", "page_name", "channel", "account"])
    date_col = first_existing_col(df, [
        "created_at", "create_time", "publish_time", "time", "datetime", "date", "timestamp"
    ])

    out = pd.DataFrame(index=df.index)
    out["source_row_id"] = range(1, len(df) + 1)
    out["source_name"] = source_name
    out["platform"] = platform
    out["record_type"] = "comment"

    if text_col:
        out["text"] = df[text_col].fillna("").astype(str)
    else:
        out["text"] = ""

    if brand_col:
        out["brand"] = [
            normalize_brand(v, fallback_text=t)
            for v, t in zip(df[brand_col], out["text"])
        ]
    else:
        out["brand"] = out["text"].apply(detect_brand_from_text)

    if date_col:
        out["created_at"] = parse_datetime_series(df[date_col])
    else:
        out["created_at"] = pd.NaT

    out["date"] = out["created_at"].dt.date.astype(str)
    out["hour"] = out["created_at"].dt.hour
    out["weekday"] = out["created_at"].dt.day_name()
    out["time_slot"] = out["hour"].apply(make_time_slot)

    out["like_count"] = 0
    out["comment_count"] = 1
    out["share_count"] = 0
    out["view_count"] = 0
    out["engagement_total"] = 1
    out["engagement_rate"] = None
    out["comment_depth"] = 1
    out["share_rate"] = None

    sentiments = out["text"].apply(score_sentiment)
    out["sentiment_label"] = sentiments.apply(lambda x: x[0])
    out["sentiment_score"] = sentiments.apply(lambda x: x[1])
    out["risk_group"] = out["text"].apply(detect_risk)
    out["risk_keyword_flag"] = out["risk_group"].apply(lambda x: x != "none")
    out["content_pillar"] = out["text"].apply(detect_content_pillar)

    out["caption_length"] = out["text"].str.len()
    out["is_phuc_long"] = out["brand"].eq("phuc_long")

    return out


def build_ai_recommendations(platform_perf, pillar_perf, risk_monitor, post_ranking):
    rows = []

    def add(insight, evidence, action, priority, owner):
        rows.append({
            "insight": insight,
            "evidence": evidence,
            "recommended_action": action,
            "priority": priority,
            "owner": owner,
            "created_at": datetime.now().isoformat(timespec="seconds"),
        })

    pl_tiktok = platform_perf[
        (platform_perf["brand"] == "phuc_long") &
        (platform_perf["platform"] == "tiktok")
    ]

    if not pl_tiktok.empty:
        r = pl_tiktok.iloc[0]
        add(
            "TikTok của Phúc Long cần ưu tiên mở rộng độ phủ tự nhiên.",
            f"median_views={r.get('median_views', 0)}, avg_engagement_rate={r.get('avg_engagement_rate', 0)}",
            "Tạo video 20-30 giây, hook mạnh trong 3 giây đầu, dùng hashtag ba lớp và ưu tiên khung giờ sáng 8-11h.",
            "high",
            "Content/Media",
        )

    pl_fb = platform_perf[
        (platform_perf["brand"] == "phuc_long") &
        (platform_perf["platform"] == "facebook")
    ]

    if not pl_fb.empty:
        r = pl_fb.iloc[0]
        add(
            "Facebook nên tiếp tục đóng vai trò kênh cộng đồng và kích hoạt thảo luận sâu.",
            f"total_comments={r.get('total_comments', 0)}, total_shares={r.get('total_shares', 0)}",
            "Chuẩn hóa caption 500-1000 ký tự cho ưu đãi/minigame, dùng CTA đối thoại thay vì CTA bán hàng trực tiếp.",
            "medium",
            "Content",
        )

    risky = risk_monitor[
        (risk_monitor["brand"] == "phuc_long") &
        (risk_monitor["risk_comment_count"] > 0)
    ].sort_values("risk_comment_count", ascending=False)

    if not risky.empty:
        r = risky.iloc[0]
        add(
            "Cần theo dõi nhóm rủi ro cảm xúc đang xuất hiện trong bình luận Phúc Long.",
            f"risk_group={r.get('risk_group')}, risk_comment_count={r.get('risk_comment_count')}",
            "Kích hoạt phản hồi CSKH, ghim comment hướng dẫn và chuyển vấn đề liên quan app/ưu đãi/cửa hàng cho bộ phận vận hành.",
            "high",
            "CSKH/Operations",
        )

    pl_pillars = pillar_perf[pillar_perf["brand"] == "phuc_long"].sort_values(
        ["positive_count", "total_records"], ascending=False
    )

    if not pl_pillars.empty:
        r = pl_pillars.iloc[0]
        add(
            "Có thể nhân rộng trụ cột nội dung đang tạo tín hiệu tích cực cho Phúc Long.",
            f"content_pillar={r.get('content_pillar')}, positive_count={r.get('positive_count')}",
            "Phát triển thành chuỗi nội dung định kỳ và đưa vào lịch đăng tuần tiếp theo.",
            "medium",
            "Brand/Content",
        )

    if not rows:
        add(
            "Dữ liệu chưa đủ để tạo khuyến nghị chi tiết.",
            "Không tìm thấy bảng Gold phù hợp.",
            "Kiểm tra lại pipeline và schema dữ liệu đầu vào.",
            "low",
            "Data",
        )

    return pd.DataFrame(rows)


def main():
    log = []
    log.append("# Phase 2 Pipeline Log")
    log.append(f"Run at: {datetime.now().isoformat()}")
    log.append("")

    raw = {}
    for name, filename in BRONZE_FILES.items():
        path = BRONZE_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing Bronze file: {path}")
        raw[name] = read_csv_safely(path)
        log.append(f"- Loaded {filename}: {len(raw[name]):,} rows, {len(raw[name].columns):,} columns")

    silver_posts = pd.concat([
        standardize_posts(raw["tiktok_videos"], "tiktok_videos_clean.csv", "tiktok"),
        standardize_posts(raw["facebook_posts"], "facebook_posts_clean.csv", "facebook"),
    ], ignore_index=True)

    silver_comments = pd.concat([
        standardize_comments(raw["tiktok_comments"], "tiktok_comments_clean.csv", "tiktok"),
        standardize_comments(raw["facebook_comments"], "facebook_comments_clean.csv", "facebook"),
    ], ignore_index=True)

    silver_unified = pd.concat([silver_posts, silver_comments], ignore_index=True)

    silver_posts.to_csv(SILVER_DIR / "silver_social_posts.csv", index=False, encoding="utf-8-sig")
    silver_comments.to_csv(SILVER_DIR / "silver_social_comments.csv", index=False, encoding="utf-8-sig")
    silver_unified.to_csv(SILVER_DIR / "silver_social_unified.csv", index=False, encoding="utf-8-sig")

    gold_brand_overview_daily = (
        silver_unified
        .groupby(["date", "brand", "platform"], dropna=False)
        .agg(
            total_records=("text", "count"),
            total_engagement=("engagement_total", "sum"),
            total_comments=("comment_count", "sum"),
            total_shares=("share_count", "sum"),
            total_views=("view_count", "sum"),
            positive_count=("sentiment_label", lambda s: (s == "positive").sum()),
            neutral_count=("sentiment_label", lambda s: (s == "neutral").sum()),
            negative_count=("sentiment_label", lambda s: (s == "negative").sum()),
            risk_count=("risk_keyword_flag", "sum"),
        )
        .reset_index()
    )

    gold_brand_overview_daily["net_sentiment_score"] = (
        gold_brand_overview_daily["positive_count"] - gold_brand_overview_daily["negative_count"]
    ) / gold_brand_overview_daily["total_records"].replace(0, 1)

    gold_platform_performance = (
        silver_posts
        .groupby(["brand", "platform"], dropna=False)
        .agg(
            post_count=("text", "count"),
            total_views=("view_count", "sum"),
            median_views=("view_count", "median"),
            total_engagement=("engagement_total", "sum"),
            avg_engagement_rate=("engagement_rate", "mean"),
            total_comments=("comment_count", "sum"),
            total_shares=("share_count", "sum"),
            median_caption_length=("caption_length", "median"),
        )
        .reset_index()
    )

    gold_content_pillar_performance = (
        silver_unified
        .groupby(["brand", "platform", "content_pillar"], dropna=False)
        .agg(
            total_records=("text", "count"),
            total_engagement=("engagement_total", "sum"),
            positive_count=("sentiment_label", lambda s: (s == "positive").sum()),
            negative_count=("sentiment_label", lambda s: (s == "negative").sum()),
            avg_sentiment_score=("sentiment_score", "mean"),
        )
        .reset_index()
    )

    gold_sentiment_risk_monitoring = (
        silver_comments
        .groupby(["brand", "platform", "risk_group", "sentiment_label"], dropna=False)
        .agg(
            comment_count=("text", "count"),
            risk_comment_count=("risk_keyword_flag", "sum"),
            avg_sentiment_score=("sentiment_score", "mean"),
        )
        .reset_index()
    )

    gold_competitor_benchmark = (
        silver_unified
        .groupby(["brand", "platform"], dropna=False)
        .agg(
            total_records=("text", "count"),
            total_engagement=("engagement_total", "sum"),
            total_views=("view_count", "sum"),
            positive_count=("sentiment_label", lambda s: (s == "positive").sum()),
            negative_count=("sentiment_label", lambda s: (s == "negative").sum()),
            risk_count=("risk_keyword_flag", "sum"),
        )
        .reset_index()
    )

    gold_competitor_benchmark["net_sentiment_score"] = (
        gold_competitor_benchmark["positive_count"] - gold_competitor_benchmark["negative_count"]
    ) / gold_competitor_benchmark["total_records"].replace(0, 1)

    gold_post_ranking = silver_posts.copy()
    gold_post_ranking["rank_score"] = (
        gold_post_ranking["engagement_total"].fillna(0) +
        gold_post_ranking["view_count"].fillna(0) * 0.001 +
        gold_post_ranking["sentiment_score"].fillna(0) * 5
    )
    gold_post_ranking = gold_post_ranking.sort_values("rank_score", ascending=False).head(100)

    gold_ai_action_recommendation = build_ai_recommendations(
        gold_platform_performance,
        gold_content_pillar_performance,
        gold_sentiment_risk_monitoring,
        gold_post_ranking,
    )

    gold_tables = {
        "gold_brand_overview_daily": gold_brand_overview_daily,
        "gold_platform_performance": gold_platform_performance,
        "gold_content_pillar_performance": gold_content_pillar_performance,
        "gold_sentiment_risk_monitoring": gold_sentiment_risk_monitoring,
        "gold_competitor_benchmark": gold_competitor_benchmark,
        "gold_post_ranking": gold_post_ranking,
        "gold_ai_action_recommendation": gold_ai_action_recommendation,
    }

    for name, table in gold_tables.items():
        table.to_csv(GOLD_DIR / f"{name}.csv", index=False, encoding="utf-8-sig")

    sqlite_path = GOLD_DIR / "phuclong_mvp.sqlite"
    with sqlite3.connect(sqlite_path) as conn:
        silver_posts.to_sql("silver_social_posts", conn, if_exists="replace", index=False)
        silver_comments.to_sql("silver_social_comments", conn, if_exists="replace", index=False)
        silver_unified.to_sql("silver_social_unified", conn, if_exists="replace", index=False)
        for name, table in gold_tables.items():
            table.to_sql(name, conn, if_exists="replace", index=False)

    log.append("")
    log.append("## Silver outputs")
    log.append(f"- silver_social_posts.csv: {len(silver_posts):,} rows")
    log.append(f"- silver_social_comments.csv: {len(silver_comments):,} rows")
    log.append(f"- silver_social_unified.csv: {len(silver_unified):,} rows")

    log.append("")
    log.append("## Gold outputs")
    for name, table in gold_tables.items():
        log.append(f"- {name}.csv: {len(table):,} rows")

    log.append("")
    log.append(f"SQLite database: {sqlite_path}")
    log.append("")
    log.append("## Final Status")
    log.append("PASS")

    log_text = "\n".join(log)
    log_path = LOG_DIR / "phase2_pipeline_run.md"
    log_path.write_text(log_text, encoding="utf-8")

    print(log_text)
    print(f"\nSaved log to: {log_path}")


if __name__ == "__main__":
    main()
