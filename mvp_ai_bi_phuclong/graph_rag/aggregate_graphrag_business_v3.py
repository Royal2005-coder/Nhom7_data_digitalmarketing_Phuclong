from pathlib import Path
import json
import re
from collections import Counter
from typing import Any, Dict, Tuple

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "graph_rag" / "outputs"

ASSIGNMENTS = OUT_DIR / "comment_assignments_pro.csv"
QUALITY = OUT_DIR / "comment_topic_quality_pro.csv"

BUSINESS_OUT = OUT_DIR / "comment_business_topics_decision_v3.csv"
REP_OUT = OUT_DIR / "comment_business_topic_representatives_v3.csv"
SUMMARY_OUT = OUT_DIR / "comment_business_decision_summary_v3.md"

BUSINESS_TAXONOMY = {
    "product_taste_quality": {
        "keywords": [
            "ngon", "dở", "ngọt", "đắng", "nhạt", "đậm", "vị", "trà", "sữa",
            "matcha", "topping", "kem", "đá", "chất lượng", "món", "nước",
            "uống", "trân châu", "hồng trà", "trà sữa", "trà sen", "bánh",
            "sandwich", "ăn sáng", "mật ong", "bưởi",
        ],
        "owner": "Product + Content",
        "kpi": "positive taste comments, negative taste comments, repeat purchase signal",
    },
    "price_promotion": {
        "keywords": [
            "giá", "đắt", "rẻ", "voucher", "mã", "giảm", "khuyến mãi", "ưu đãi",
            "sale", "deal", "combo", "freeship", "áp dụng", "mua", "tặng",
            "mã giảm", "giảm giá",
        ],
        "owner": "Marketing + CRM",
        "kpi": "promotion engagement, voucher redemption, promo complaint ratio",
    },
    "app_payment_order": {
        "keywords": [
            "app", "thanh toán", "momo", "vnpay", "bank", "online", "đặt hàng",
            "order", "lỗi app", "không thanh toán", "đơn hàng", "mã đơn", "qr",
            "chuyển khoản",
        ],
        "owner": "Digital Product + Data",
        "kpi": "app error mentions, payment complaint ratio, order success rate",
    },
    "service_store_staff": {
        "keywords": [
            "nhân viên", "phục vụ", "thái độ", "quầy", "xếp hàng", "chậm",
            "nhanh", "dịch vụ", "order", "tư vấn", "bảo vệ",
        ],
        "owner": "Operations + Store Manager",
        "kpi": "service complaint ratio, staff mention sentiment, queue complaint",
    },
    "delivery_waiting": {
        "keywords": [
            "giao hàng", "ship", "shipper", "đợi", "chờ", "chờ lâu", "lâu",
            "trễ", "giao", "đơn", "delay", "nhận hàng", "đặt giao",
        ],
        "owner": "Operations + Delivery Partner",
        "kpi": "delivery complaint ratio, waiting mentions, delayed order mentions",
    },
    "branch_availability": {
        "keywords": [
            "chi nhánh", "cửa hàng", "quán", "mở", "đóng", "gần", "xa",
            "địa chỉ", "ở đâu", "hết món", "còn món", "khu vực", "tỉnh",
            "thành phố", "chỗ", "có chỗ",
        ],
        "owner": "Retail Expansion + Operations",
        "kpi": "branch request mentions, availability complaints, out-of-stock mentions",
    },
    "brand_love_content": {
        "keywords": [
            "thích", "yêu", "mê", "xinh", "đẹp", "trend", "viral", "clip",
            "video", "content", "hình", "ảnh", "review", "quay", "nhạc",
            "dễ thương", "dễ huông", "kịch bản", "creative", "agency",
        ],
        "owner": "Content + Social Team",
        "kpi": "positive brand mentions, share/comment rate, creative engagement",
    },
}

NEGATIVE_HINTS = {
    "dở", "đắng", "nhạt", "đắt", "lỗi", "chậm", "lâu", "trễ", "hết", "không", "tệ", "khó", "bực"
}


def normalize_text(text: Any) -> str:
    text = str(text).lower()
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"www\S+", " ", text)
    text = re.sub(r"[^0-9a-zA-ZÀ-ỹ_\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def classify_business_topic(text: str) -> Tuple[str, float, Dict[str, int]]:
    clean = normalize_text(text)
    scores: Dict[str, int] = {}
    for topic, payload in BUSINESS_TAXONOMY.items():
        score = 0
        for keyword in payload["keywords"]:
            if keyword in clean:
                score += 2 if " " in keyword else 1
        scores[topic] = score
    best_topic = max(scores, key=scores.get)
    best_score = scores[best_topic]
    total_score = sum(scores.values())
    if best_score <= 0:
        return "general_social_or_noise", 0.0, scores
    return best_topic, float(best_score / max(1, total_score)), scores


def mode_or_unknown(series: pd.Series) -> str:
    if series.empty:
        return "unknown"
    mode = series.astype(str).mode()
    return str(mode.iloc[0]) if not mode.empty else "unknown"


def confidence_label(score: float) -> str:
    if score >= 0.72:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def usefulness_label(confidence: str) -> str:
    if confidence == "high":
        return "usable_for_decision"
    if confidence == "medium":
        return "use_with_human_review"
    return "noisy_do_not_conclude"


def extract_keywords(texts, topic, top_n=16):
    vocab = BUSINESS_TAXONOMY.get(topic, {}).get("keywords", [])
    counter = Counter()
    for text in texts:
        clean = normalize_text(text)
        for keyword in vocab:
            if keyword in clean:
                counter[keyword] += 1
    return [word for word, _ in counter.most_common(top_n)]


def business_risk_hint(business_topic: str, sub: pd.DataFrame) -> str:
    mode_risk = mode_or_unknown(sub["risk_group"])
    if mode_risk not in {"none", "nan", "unknown", ""}:
        return mode_risk
    joined = " ".join(sub["text_clean"].dropna().astype(str).head(500).tolist())
    if any(word in joined for word in NEGATIVE_HINTS):
        return f"{business_topic}_risk"
    return "none"


def main() -> None:
    if not ASSIGNMENTS.exists():
        raise FileNotFoundError(f"Missing {ASSIGNMENTS}")
    if not QUALITY.exists():
        raise FileNotFoundError(f"Missing {QUALITY}")

    assignments = pd.read_csv(ASSIGNMENTS, encoding="utf-8-sig", low_memory=False)
    quality = pd.read_csv(QUALITY, encoding="utf-8-sig", low_memory=False)

    quality_cols = [
        "topic_id", "topic_reliability_score", "decision_confidence", "noisy_topic_flag",
        "avg_cluster_probability", "keyword_quality_score",
    ]
    missing = [col for col in quality_cols if col not in quality.columns]
    if missing:
        raise RuntimeError(f"Missing columns in quality: {missing}")

    merged = assignments.merge(quality[quality_cols], on="topic_id", how="left")
    merged["text_clean"] = merged.get("text_clean", merged.get("text", "")).fillna("").map(normalize_text)
    merged["topic_probability"] = merged["topic_probability"].fillna(0)
    merged["topic_reliability_score"] = merged["topic_reliability_score"].fillna(0)
    merged["noisy_topic_flag"] = merged["noisy_topic_flag"].fillna(True).astype(bool)

    classified = merged["text_clean"].map(classify_business_topic)
    merged["business_topic_v3"] = classified.map(lambda x: x[0])
    merged["business_match_confidence"] = classified.map(lambda x: x[1])

    usable = merged[merged["business_topic_v3"] != "general_social_or_noise"].copy()

    rows = []
    representatives = []

    for business_topic, sub in usable.groupby("business_topic_v3"):
        total_comments = int(len(sub))
        if total_comments < 40:
            continue

        positive = int((sub["sentiment_label"].astype(str) == "positive").sum())
        neutral = int((sub["sentiment_label"].astype(str) == "neutral").sum())
        negative = int((sub["sentiment_label"].astype(str) == "negative").sum())
        sentiment_total = max(1, positive + neutral + negative)
        sentiment_clarity = max(positive, neutral, negative) / sentiment_total
        negative_ratio = negative / sentiment_total

        phuc_long_ratio = float((sub["brand"].astype(str) == "phuc_long").mean())
        top_brand = mode_or_unknown(sub["brand"])
        brand_purity = float((sub["brand"].astype(str) == top_brand).mean())
        top_platform = mode_or_unknown(sub["platform"])
        top_risk_group = business_risk_hint(business_topic, sub)
        risk_clarity = 0.25 if top_risk_group in {"none", "nan", "unknown", ""} else 1.0

        micro_cluster_count = int(sub["topic_id"].nunique())
        avg_topic_probability = float(sub["topic_probability"].mean())
        avg_micro_reliability = float(sub["topic_reliability_score"].mean())
        max_micro_reliability = float(sub["topic_reliability_score"].max())
        clean_cluster_ratio = 1.0 - float(sub["noisy_topic_flag"].mean())
        taxonomy_match = float(sub["business_match_confidence"].mean())
        medium_or_high_ratio = float(sub["decision_confidence"].isin(["high", "medium"]).mean())
        volume_score = min(1.0, total_comments / 1500)

        business_reliability_score = (
            0.20 * taxonomy_match
            + 0.14 * volume_score
            + 0.12 * avg_topic_probability
            + 0.12 * avg_micro_reliability
            + 0.10 * max_micro_reliability
            + 0.10 * clean_cluster_ratio
            + 0.08 * phuc_long_ratio
            + 0.05 * brand_purity
            + 0.04 * sentiment_clarity
            + 0.03 * risk_clarity
            + 0.02 * medium_or_high_ratio
        )
        business_reliability_score = max(0.0, min(1.0, business_reliability_score))
        decision_confidence = confidence_label(business_reliability_score)
        keywords = extract_keywords(sub["text_clean"].tolist(), business_topic)

        rows.append({
            "business_topic": business_topic,
            "micro_cluster_count": micro_cluster_count,
            "comment_count": total_comments,
            "positive_count": positive,
            "neutral_count": neutral,
            "negative_count": negative,
            "negative_ratio": round(negative_ratio, 4),
            "top_brand": top_brand,
            "phuc_long_ratio": round(phuc_long_ratio, 4),
            "brand_purity_proxy": round(brand_purity, 4),
            "top_platform": top_platform,
            "top_risk_group": top_risk_group,
            "taxonomy_match_score": round(taxonomy_match, 4),
            "avg_topic_probability": round(avg_topic_probability, 4),
            "avg_micro_reliability": round(avg_micro_reliability, 4),
            "max_micro_reliability": round(max_micro_reliability, 4),
            "clean_cluster_ratio": round(clean_cluster_ratio, 4),
            "medium_or_high_ratio": round(medium_or_high_ratio, 4),
            "volume_score": round(volume_score, 4),
            "sentiment_clarity_score": round(sentiment_clarity, 4),
            "risk_clarity_score": round(risk_clarity, 4),
            "business_reliability_score": round(business_reliability_score, 4),
            "decision_confidence": decision_confidence,
            "management_usefulness": usefulness_label(decision_confidence),
            "owner": BUSINESS_TAXONOMY[business_topic]["owner"],
            "kpi": BUSINESS_TAXONOMY[business_topic]["kpi"],
            "keywords": ", ".join(keywords),
        })

        rep = sub.sort_values(
            ["business_match_confidence", "topic_probability", "topic_reliability_score"],
            ascending=False,
        ).head(10)
        for rank, (_, row) in enumerate(rep.iterrows(), start=1):
            representatives.append({
                "business_topic": business_topic,
                "rank": rank,
                "topic_id": int(row["topic_id"]),
                "brand": row.get("brand", "unknown"),
                "platform": row.get("platform", "unknown"),
                "sentiment_label": row.get("sentiment_label", "unknown"),
                "risk_group": row.get("risk_group", "unknown"),
                "business_match_confidence": round(float(row["business_match_confidence"]), 4),
                "topic_probability": round(float(row.get("topic_probability", 0)), 4),
                "text": row.get("text", ""),
            })

    decision = pd.DataFrame(rows)
    if decision.empty:
        raise RuntimeError("No business decision topics generated.")
    decision = decision.sort_values(["business_reliability_score", "comment_count"], ascending=False)
    reps = pd.DataFrame(representatives)

    out_decision = OUT_DIR / "comment_business_topics_decision_v3.csv"
    out_reps = OUT_DIR / "comment_business_topic_representatives_v3.csv"
    out_summary = OUT_DIR / "comment_business_decision_summary_v3.md"

    decision.to_csv(out_decision, index=False, encoding="utf-8-sig")
    reps.to_csv(out_reps, index=False, encoding="utf-8-sig")

    high = int((decision["decision_confidence"] == "high").sum())
    medium = int((decision["decision_confidence"] == "medium").sum())
    low = int((decision["decision_confidence"] == "low").sum())

    report = [
        "# Comment GraphRAG Business Decision v3",
        "",
        f"- Business topics: {len(decision):,}",
        f"- High-confidence: {high:,}",
        f"- Medium-confidence: {medium:,}",
        f"- Low-confidence: {low:,}",
        "",
        "## Business decision table",
        decision.to_markdown(index=False),
        "",
        "## Academic note",
        (
            "Business Decision v3 không dùng micro-cluster làm kết luận trực tiếp. "
            "Hệ thống gán lại từng comment vào taxonomy nghiệp vụ, sau đó tổng hợp thành business decision topics. "
            "Cách này phù hợp hơn cho ra quyết định quản trị vì giảm nhiễu từ tên người, comment ngắn và cluster rời rạc."
        ),
    ]
    out_summary.write_text("\n".join(report), encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "business_topics": int(len(decision)),
        "high_confidence": high,
        "medium_confidence": medium,
        "low_confidence": low,
        "outputs": {
            "business_topics": str(out_decision),
            "representatives": str(out_reps),
            "summary": str(out_summary),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
