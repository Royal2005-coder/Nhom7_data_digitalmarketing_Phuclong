import json
from pathlib import Path
import pandas as pd

# --- 1. CẤU HÌNH ĐƯỜNG DẪN (ĐƯỢC ĐƯA LÊN ĐẦU ĐỂ TRÁNH LỖI NAMERROR) ---
BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "graph_rag" / "outputs"

ASSIGNMENTS = OUT_DIR / "comment_assignments_pro.csv"
QUALITY = OUT_DIR / "comment_topic_quality_pro.csv"
REPRESENTATIVES = OUT_DIR / "comment_topic_representatives_pro.csv"

BUSINESS_OUT = OUT_DIR / "comment_business_topics_decision_pro.csv"
BUSINESS_REP_OUT = OUT_DIR / "comment_business_topic_representatives_pro.csv"
SUMMARY_OUT = OUT_DIR / "comment_business_decision_summary_pro.md"


# --- 2. CÁC HÀM BỔ TRỢ (HELPER FUNCTIONS) ---
def confidence_label(score: float) -> str:
    if score >= 0.70:
        return "high"
    if score >= 0.52:
        return "medium"
    return "low"


def usefulness_label(confidence: str) -> str:
    """Hàm này đã được nối lại hoàn chỉnh từ đoạn code lỗi ở đầu bài"""
    if confidence == "high":
        return "usable_for_decision"
    if confidence == "medium":
        return "use_with_human_review"
    return "noisy_do_not_conclude"


def mode_or_unknown(series: pd.Series) -> str:
    if series.empty:
        return "unknown"
    mode = series.astype(str).mode()
    return str(mode.iloc[0]) if not mode.empty else "unknown"


# --- 3. HÀM XỬ LÝ CHÍNH ---
def main() -> None:
    # Kiểm tra file đầu vào
    if not ASSIGNMENTS.exists():
        raise FileNotFoundError(f"Missing {ASSIGNMENTS}")
    if not QUALITY.exists():
        raise FileNotFoundError(f"Missing {QUALITY}")

    # Đọc dữ liệu
    assignments = pd.read_csv(ASSIGNMENTS, encoding="utf-8-sig", low_memory=False)
    quality = pd.read_csv(QUALITY, encoding="utf-8-sig", low_memory=False)

    needed_quality = [
        "topic_id",
        "topic_label",
        "bertopic_label",
        "keywords",
        "topic_reliability_score",
        "decision_confidence",
        "noisy_topic_flag",
        "taxonomy_alignment_score",
        "avg_cluster_probability",
        "keyword_quality_score",
        "phuc_long_ratio",
    ]

    # Kiểm tra các cột cần thiết
    missing = [col for col in needed_quality if col not in quality.columns]
    if missing:
        raise RuntimeError(f"Missing columns in quality file: {missing}")

    # Merge dữ liệu độc lập sang dữ liệu tổng
    merged = assignments.merge(
        quality[needed_quality],
        on="topic_id",
        how="left",
        suffixes=("", "_quality"),
    )

    # Điền giá trị rỗng mặc định
    merged["topic_label"] = merged["topic_label"].fillna("unknown")
    merged["topic_reliability_score"] = merged["topic_reliability_score"].fillna(0)
    merged["topic_probability"] = merged["topic_probability"].fillna(0)
    merged["noisy_topic_flag"] = merged["noisy_topic_flag"].fillna(True)

    business_rows = []
    rep_rows = []

    # Nhóm theo topic_label (Tầng Business Decision Topic)
    for business_topic, sub in merged.groupby("topic_label"):
        if business_topic in ["unknown", "general_noise_or_social"]:
            continue

        total_comments = int(len(sub))
        if total_comments < 30:
            continue

        # Thống kê Sentiment
        positive = int((sub["sentiment_label"].astype(str) == "positive").sum())
        neutral = int((sub["sentiment_label"].astype(str) == "neutral").sum())
        negative = int((sub["sentiment_label"].astype(str) == "negative").sum())

        sentiment_total = max(1, positive + neutral + negative)
        sentiment_clarity = max(positive, neutral, negative) / sentiment_total
        negative_ratio = negative / sentiment_total

        # Thống kê Brand & Platform
        phuc_long_ratio = float((sub["brand"].astype(str) == "phuc_long").mean())
        top_brand = mode_or_unknown(sub["brand"])
        brand_purity = float((sub["brand"].astype(str) == top_brand).mean())

        top_platform = mode_or_unknown(sub["platform"])
        top_risk_group = mode_or_unknown(sub["risk_group"])

        if top_risk_group in ["none", "nan", "unknown", ""]:
            risk_clarity = 0.2
        else:
            risk_clarity = 1.0

        cluster_count = int(sub["topic_id"].nunique())
        clean_cluster_ratio = 1.0 - float(sub["noisy_topic_flag"].mean())

        avg_micro_reliability = float(sub["topic_reliability_score"].mean())
        max_micro_reliability = float(sub["topic_reliability_score"].max())
        avg_probability = float(sub["topic_probability"].mean())

        volume_score = min(1.0, total_comments / 1500)

        medium_or_high_ratio = float(
            sub["decision_confidence"].isin(["high", "medium"]).mean()
        )

        # Tính toán Business Reliability Score theo trọng số (Tổng = 1.0)
        business_reliability_score = (
            0.18 * avg_micro_reliability
            + 0.14 * max_micro_reliability
            + 0.12 * avg_probability
            + 0.12 * clean_cluster_ratio
            + 0.12 * volume_score
            + 0.10 * phuc_long_ratio
            + 0.08 * brand_purity
            + 0.08 * sentiment_clarity
            + 0.04 * risk_clarity
            + 0.02 * medium_or_high_ratio
        )

        business_reliability_score = max(0.0, min(1.0, business_reliability_score))
        decision_confidence = confidence_label(business_reliability_score)

        if clean_cluster_ratio < 0.25:
            noisy_flag = True
        else:
            noisy_flag = decision_confidence == "low"

        topic_ids = sorted([int(x) for x in sub["topic_id"].dropna().unique().tolist()])

        # Xử lý gộp Keywords (Lấy tối đa 15 từ khóa không trùng)
        keyword_text = " ".join(sub["keywords"].dropna().astype(str).head(30).tolist())
        keywords = []
        for token in keyword_text.replace("/", ",").split(","):
            token = token.strip()
            if token and token not in keywords:
                keywords.append(token)
            if len(keywords) >= 15:
                break

        # Lưu thông tin dòng dữ liệu tổng quan cho Business Topic
        business_rows.append({
            "business_topic": business_topic,
            "topic_ids": ",".join(map(str, topic_ids)),
            "micro_cluster_count": cluster_count,
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
            "avg_micro_reliability": round(avg_micro_reliability, 4),
            "max_micro_reliability": round(max_micro_reliability, 4),
            "avg_cluster_probability": round(avg_probability, 4),
            "clean_cluster_ratio": round(clean_cluster_ratio, 4),
            "medium_or_high_ratio": round(medium_or_high_ratio, 4),
            "volume_score": round(volume_score, 4),
            "sentiment_clarity_score": round(sentiment_clarity, 4),
            "risk_clarity_score": round(risk_clarity, 4),
            "business_reliability_score": round(business_reliability_score, 4),
            "decision_confidence": decision_confidence,
            "management_usefulness": usefulness_label(decision_confidence),
            "noisy_business_topic_flag": bool(noisy_flag),
            "keywords": ", ".join(keywords),
        })

        # Lấy ra 8 comment đại diện (Representative comments) chất lượng nhất
        reps = (
            sub.sort_values(["topic_probability", "topic_reliability_score"], ascending=False)
            .head(8)
        )

        for rank, (_, row) in enumerate(reps.iterrows(), start=1):
            rep_rows.append({
                "business_topic": business_topic,
                "rank": rank,
                "topic_id": int(row["topic_id"]),
                "brand": row.get("brand", "unknown"),
                "platform": row.get("platform", "unknown"),
                "sentiment_label": row.get("sentiment_label", "unknown"),
                "risk_group": row.get("risk_group", "unknown"),
                "topic_probability": round(float(row.get("topic_probability", 0)), 4),
                "topic_reliability_score": round(float(row.get("topic_reliability_score", 0)), 4),
                "text": row.get("text", ""),
            })

    # Tạo DataFrame từ list rows thu được
    business_df = pd.DataFrame(business_rows)

    if business_df.empty:
        raise RuntimeError("No business decision topics generated.")

    # Sắp xếp theo mức độ tin cậy và số lượng comment giảm dần
    business_df = business_df.sort_values(
        ["business_reliability_score", "comment_count"],
        ascending=False,
    )

    reps_df = pd.DataFrame(rep_rows)

    # Xuất dữ liệu ra file CSV
    business_df.to_csv(BUSINESS_OUT, index=False, encoding="utf-8-sig")
    reps_df.to_csv(BUSINESS_REP_OUT, index=False, encoding="utf-8-sig")

    # Thống kê số lượng theo mức độ tự tin phục vụ báo cáo summary
    high = int((business_df["decision_confidence"] == "high").sum())
    medium = int((business_df["decision_confidence"] == "medium").sum())
    low = int((business_df["decision_confidence"] == "low").sum())

    # Tạo nội dung file báo cáo Markdown
    report = [
        "# Comment GraphRAG Pro Business Decision Summary",
        "",
        f"- Business decision topics: {len(business_df):,}",
        f"- High-confidence business topics: {high:,}",
        f"- Medium-confidence business topics: {medium:,}",
        f"- Low-confidence business topics: {low:,}",
        "",
        "## Business decision topic table",
        business_df.to_markdown(index=False),
        "",
        "## Academic note",
        (
            "Bảng này không đánh giá từng micro-cluster riêng lẻ. "
            "Hệ thống gom các BERTopic micro-clusters thành business decision topics, "
            "sau đó tính business reliability score dựa trên micro-topic reliability, "
            "membership probability, clean cluster ratio, volume, Phúc Long ratio, "
            "brand purity, sentiment clarity và risk clarity. "
            "Đây là tầng phù hợp hơn để hỗ trợ ra quyết định quản trị từ social comments."
        ),
    ]

    SUMMARY_OUT.write_text("\n".join(report), encoding="utf-8")

    # In thông tin JSON kết quả ra console
    print(json.dumps({
        "status": "PASS",
        "business_topics": int(len(business_df)),
        "high_confidence": high,
        "medium_confidence": medium,
        "low_confidence": low,
        "outputs": {
            "business_topics": str(BUSINESS_OUT),
            "representatives": str(BUSINESS_REP_OUT),
            "summary": str(SUMMARY_OUT),
        },
    }, ensure_ascii=False, indent=2))


# --- 4. KHỞI CHẠY CHƯƠNG TRÌNH ---
if __name__ == "__main__":
    main()