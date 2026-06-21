from pathlib import Path
import json

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "graph_rag" / "outputs"

CLEAN_IN = OUT_DIR / "clean_comment_corpus_pro.csv"
MODEL_OUT = OUT_DIR / "model_comment_corpus_pro.csv"
REPORT_OUT = OUT_DIR / "model_comment_corpus_report_pro.md"
STATS_OUT = OUT_DIR / "model_comment_corpus_stats_pro.json"


MIN_QUALITY = 0.35


def main() -> None:
    if not CLEAN_IN.exists():
        raise FileNotFoundError(f"Missing clean corpus: {CLEAN_IN}")

    df = pd.read_csv(CLEAN_IN, encoding="utf-8-sig", low_memory=False)

    required = [
        "brand",
        "platform",
        "text",
        "text_for_model",
        "business_topic_rule",
        "business_match_confidence",
        "comment_quality_score",
        "sentiment_label",
        "risk_group",
    ]

    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")

    before = len(df)

    model_df = df[
        (df["business_topic_rule"].astype(str) != "general_social_or_noise")
        & (df["comment_quality_score"].astype(float) >= MIN_QUALITY)
    ].copy()

    model_df = model_df.sort_values(
        ["comment_quality_score", "business_match_confidence"],
        ascending=False,
    )

    model_df.to_csv(MODEL_OUT, index=False, encoding="utf-8-sig")

    stats = {
        "status": "PASS",
        "clean_input_rows": int(before),
        "modeling_rows": int(len(model_df)),
        "removed_general_noise": int((df["business_topic_rule"].astype(str) == "general_social_or_noise").sum()),
        "min_quality": MIN_QUALITY,
        "business_topic_distribution": model_df["business_topic_rule"].value_counts().to_dict(),
        "brand_distribution": model_df["brand"].value_counts().to_dict(),
        "platform_distribution": model_df["platform"].value_counts().to_dict(),
    }

    STATS_OUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Modeling Comment Corpus Pro Report",
        "",
        f"- Clean input rows: {stats['clean_input_rows']:,}",
        f"- Modeling rows: {stats['modeling_rows']:,}",
        f"- Removed general/noise rows: {stats['removed_general_noise']:,}",
        f"- Minimum comment quality: {MIN_QUALITY}",
        "",
        "## Business topic distribution",
        model_df["business_topic_rule"].value_counts().to_markdown(),
        "",
        "## Brand distribution",
        model_df["brand"].value_counts().to_markdown(),
        "",
        "## Platform distribution",
        model_df["platform"].value_counts().to_markdown(),
        "",
        "## Academic note",
        (
            "Modeling corpus chỉ giữ các comment đã qua lọc nhiễu và có business_topic_rule rõ ràng. "
            "Các comment general_social_or_noise không đưa vào BERTopic để giảm khả năng mô hình học từ "
            "tên người, metadata mạng xã hội, từ lóng hoặc comment không có ý nghĩa quản trị."
        ),
    ]

    REPORT_OUT.write_text("\n".join(report), encoding="utf-8")

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()