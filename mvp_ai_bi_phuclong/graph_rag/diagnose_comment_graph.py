from pathlib import Path
import json
from typing import Any, Dict, List, Tuple

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "graph_rag" / "outputs"

TOPICS = OUT_DIR / "comment_topics.csv"
NODES = OUT_DIR / "comment_graph_nodes.csv"
EDGES = OUT_DIR / "comment_graph_edges.csv"

QUALITY_OUT = OUT_DIR / "comment_topic_quality_precheck.csv"
REPORT_OUT = OUT_DIR / "comment_graph_diagnostics.md"

NOISE_WORDS = {
    "nguyen", "ngọc", "trần", "lê", "hoàng", "thảo", "phương", "bảo", "hồng",
    "tao", "tui", "fl", "nam", "huyền", "xinh", "tuần1", "tháng", "lại",
    "cái", "thấy", "đâu", "xin", "bán", "mới", "ơi", "nha", "nhé", "ạ",
    "haha", "hihi", "kkk", "kkkk", "lol", "tag", "ib", "rep",
}

BUSINESS_WORDS = {
    "trà", "sữa", "matcha", "topping", "ngọt", "đắng", "giá", "voucher",
    "khuyến mãi", "app", "thanh toán", "giao hàng", "nhân viên", "phục vụ",
    "cửa hàng", "chi nhánh", "chờ", "lâu", "hết", "món", "chất lượng",
    "ly", "size", "combo", "menu", "ship", "order", "vị", "đậm", "nhạt",
    "ưu đãi", "mã", "giảm", "đơn", "đặt", "giao", "nước", "đồ uống",
}

STRATEGIC_WORDS = {
    "app", "thanh toán", "voucher", "khuyến mãi", "giá", "chất lượng",
    "nhân viên", "phục vụ", "cửa hàng", "chi nhánh", "giao hàng",
    "chờ", "lâu", "hết món", "menu", "combo", "matcha", "trà",
}


def split_keywords(text: Any) -> List[str]:
    """Tách chuỗi keywords phân tách bằng dấu phẩy thành list từ khóa chuẩn hóa."""
    if pd.isna(text):
        return []
    return [item.strip().lower() for item in str(text).split(",") if item.strip()]


def score_keywords(keywords: List[str]) -> Tuple[float, float, float]:
    """Tính keyword quality, noise ratio và strategic keyword ratio."""
    if not keywords:
        return 0.0, 1.0, 0.0

    target_keywords = keywords[:10]
    max_len = max(1, len(target_keywords))

    noise_count = sum(1 for keyword in target_keywords if keyword in NOISE_WORDS)
    business_count = sum(
        1
        for keyword in target_keywords
        if any(business_word in keyword for business_word in BUSINESS_WORDS)
    )
    strategic_count = sum(
        1
        for keyword in target_keywords
        if any(strategic_word in keyword for strategic_word in STRATEGIC_WORDS)
    )

    business_score = min(1.0, business_count / max_len)
    strategic_score = min(1.0, strategic_count / max_len)
    noise_ratio = noise_count / max_len

    keyword_quality = max(
        0.0,
        min(
            1.0,
            0.55 * business_score
            + 0.25 * strategic_score
            + 0.20 * (1.0 - noise_ratio),
        ),
    )

    return keyword_quality, noise_ratio, strategic_score


def confidence_label(score: float) -> str:
    """Đổi topic reliability score thành nhãn confidence."""
    if score >= 0.75:
        return "high"
    if score >= 0.50:
        return "medium"
    return "low"


def usefulness_label(row: pd.Series) -> str:
    """Đổi decision confidence thành mức hữu dụng quản trị."""
    confidence = row.get("decision_confidence", "low")
    if confidence == "high":
        return "usable_for_decision"
    if confidence == "medium":
        return "use_with_human_review"
    return "noisy_do_not_conclude"


def safe_markdown(df: pd.DataFrame, max_rows: int = 10) -> str:
    """Render DataFrame thành Markdown an toàn."""
    if df.empty:
        return "No data"

    safe_df = df.head(max_rows).where(pd.notna(df.head(max_rows)), "N/A")
    try:
        return safe_df.to_markdown(index=False)
    except Exception:
        return safe_df.to_csv(index=False)


def validate_input(topics: pd.DataFrame) -> None:
    """Kiểm tra đủ cột cần thiết trong comment_topics.csv."""
    required = [
        "topic_id",
        "topic_label",
        "keywords",
        "comment_count",
        "positive_count",
        "neutral_count",
        "negative_count",
        "top_brand",
        "top_platform",
        "top_risk_group",
    ]
    missing = [column for column in required if column not in topics.columns]
    if missing:
        raise RuntimeError(f"Missing required columns in comment_topics.csv: {missing}")


def compute_reliability(row: pd.Series, volume_quantile_90: float) -> Dict[str, Any]:
    """Tính toàn bộ chỉ số tin cậy cho một topic cluster."""
    keywords = split_keywords(row.get("keywords", ""))
    keyword_quality, noise_ratio, strategic_ratio = score_keywords(keywords)

    comment_count = float(row.get("comment_count", 0) or 0)
    positive_count = float(row.get("positive_count", 0) or 0)
    neutral_count = float(row.get("neutral_count", 0) or 0)
    negative_count = float(row.get("negative_count", 0) or 0)

    volume_score = min(1.0, comment_count / volume_quantile_90)

    sentiment_total = max(1.0, positive_count + neutral_count + negative_count)
    sentiment_dominance = max(positive_count, neutral_count, negative_count) / sentiment_total
    negative_ratio = negative_count / sentiment_total

    risk_group = str(row.get("top_risk_group", "none")).strip().lower()
    risk_clarity = 0.20 if risk_group in {"none", "nan", "unknown", ""} else 1.00

    top_brand = str(row.get("top_brand", "unknown")).strip().lower()
    brand_purity = 1.00 if top_brand == "phuc_long" else 0.55

    topic_reliability_score = (
        0.28 * keyword_quality
        + 0.22 * volume_score
        + 0.18 * sentiment_dominance
        + 0.14 * brand_purity
        + 0.10 * risk_clarity
        + 0.08 * strategic_ratio
    )

    decision_confidence = confidence_label(topic_reliability_score)
    noisy_flag = noise_ratio >= 0.40 or keyword_quality < 0.35 or strategic_ratio == 0.0

    return {
        "topic_id": int(row["topic_id"]),
        "topic_label": row.get("topic_label", "unknown"),
        "keywords": row.get("keywords", ""),
        "comment_count": int(comment_count),
        "positive_count": int(positive_count),
        "neutral_count": int(neutral_count),
        "negative_count": int(negative_count),
        "negative_ratio": round(negative_ratio, 4),
        "top_brand": top_brand,
        "brand_purity_proxy": round(brand_purity, 4),
        "top_platform": row.get("top_platform", "unknown"),
        "top_risk_group": risk_group,
        "keyword_quality_score": round(keyword_quality, 4),
        "noise_keyword_ratio": round(noise_ratio, 4),
        "strategic_keyword_ratio": round(strategic_ratio, 4),
        "volume_score": round(volume_score, 4),
        "sentiment_clarity_score": round(sentiment_dominance, 4),
        "risk_clarity_score": round(risk_clarity, 4),
        "topic_reliability_score": round(topic_reliability_score, 4),
        "decision_confidence": decision_confidence,
        "noisy_topic_flag": bool(noisy_flag),
    }


def main() -> None:
    if not TOPICS.exists():
        raise FileNotFoundError(f"Không tìm thấy file dữ liệu đầu vào: {TOPICS}")

    topics = pd.read_csv(TOPICS, encoding="utf-8-sig", low_memory=False)
    validate_input(topics)

    nodes = pd.read_csv(NODES, encoding="utf-8-sig", low_memory=False) if NODES.exists() else pd.DataFrame()
    edges = pd.read_csv(EDGES, encoding="utf-8-sig", low_memory=False) if EDGES.exists() else pd.DataFrame()

    total_comments = int(topics["comment_count"].fillna(0).sum())
    volume_quantile_90 = max(1.0, float(topics["comment_count"].fillna(0).quantile(0.90)))

    quality = pd.DataFrame(
        [compute_reliability(row, volume_quantile_90) for _, row in topics.iterrows()]
    )
    quality["management_usefulness"] = quality.apply(usefulness_label, axis=1)
    quality = quality.sort_values(["topic_reliability_score", "comment_count"], ascending=False)

    QUALITY_OUT.parent.mkdir(parents=True, exist_ok=True)
    quality.to_csv(QUALITY_OUT, index=False, encoding="utf-8-sig")

    high_topics = quality[quality["decision_confidence"].eq("high")]
    medium_topics = quality[quality["decision_confidence"].eq("medium")]
    low_topics = quality[quality["decision_confidence"].eq("low")]

    report = [
        "# Comment GraphRAG Diagnostics Report",
        "",
        f"- **Total topic clusters**: {len(topics):,}",
        f"- **Total comments represented**: {total_comments:,}",
        f"- **Graph nodes**: {len(nodes):,}",
        f"- **Graph edges**: {len(edges):,}",
        "",
        "## Decision confidence distribution",
        quality["decision_confidence"].value_counts().to_markdown(),
        "",
        "## Management usefulness distribution",
        quality["management_usefulness"].value_counts().to_markdown(),
        "",
        "## High-confidence topics",
        safe_markdown(high_topics, 10),
        "",
        "## Medium-confidence topics",
        safe_markdown(medium_topics, 10),
        "",
        "## Low-confidence / noisy topics",
        safe_markdown(low_topics, 10),
        "",
        "## Academic note",
        (
            "Vì topic clustering là bài toán không giám sát (Unsupervised Learning), "
            "hệ thống không dùng accuracy theo nghĩa phân loại có nhãn (Supervised Evaluation). "
            "Thay vào đó, dashboard sử dụng topic reliability score và decision confidence để đánh giá "
            "mức độ đáng tin cậy của từng cụm khi hỗ trợ ra quyết định marketing, CSKH và vận hành."
        ),
        "",
        "## Management interpretation",
        (
            "Topic có decision_confidence = high có thể dùng làm insight chính. "
            "Topic medium chỉ nên dùng làm tín hiệu tham khảo và cần human review trước khi ra quyết định lớn. "
            "Topic low hoặc noisy_topic_flag = True không nên dùng làm kết luận quản trị chính."
        ),
    ]
    REPORT_OUT.write_text("\n".join(report), encoding="utf-8")

    result = {
        "status": "PASS",
        "quality_csv": str(QUALITY_OUT),
        "report": str(REPORT_OUT),
        "topics": int(len(quality)),
        "high_confidence": int((quality["decision_confidence"] == "high").sum()),
        "medium_confidence": int((quality["decision_confidence"] == "medium").sum()),
        "low_confidence": int((quality["decision_confidence"] == "low").sum()),
        "noisy_topics": int(quality["noisy_topic_flag"].sum()),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
