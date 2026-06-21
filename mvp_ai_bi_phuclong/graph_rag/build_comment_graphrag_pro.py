
from pathlib import Path
import json
import os
import re
from collections import Counter
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT = Path(
    os.getenv(
        "GRAPHRAG_INPUT",
        str(BASE_DIR / "graph_rag" / "outputs" / "model_comment_corpus_pro.csv"),
    )
)
OUT_DIR = BASE_DIR / "graph_rag" / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TOPICS_OUT = OUT_DIR / "comment_topics_pro.csv"
ASSIGNMENTS_OUT = OUT_DIR / "comment_assignments_pro.csv"
QUALITY_OUT = OUT_DIR / "comment_topic_quality_pro.csv"
NODES_OUT = OUT_DIR / "comment_graph_nodes_pro.csv"
EDGES_OUT = OUT_DIR / "comment_graph_edges_pro.csv"
HTML_OUT = OUT_DIR / "comment_topic_graph_pro.html"
SUMMARY_OUT = OUT_DIR / "comment_graph_summary_pro.md"
METRICS_OUT = OUT_DIR / "comment_topic_model_metrics_pro.json"
REPRESENTATIVES_OUT = OUT_DIR / "comment_topic_representatives_pro.csv"

RANDOM_STATE = int(os.getenv("GRAPHRAG_RANDOM_STATE", "42"))
MAX_COMMENTS = int(os.getenv("GRAPHRAG_MAX_COMMENTS", "22000"))
MIN_TEXT_LEN = int(os.getenv("GRAPHRAG_MIN_TEXT_LEN", "12"))
MIN_CLUSTER_SIZE = int(os.getenv("GRAPHRAG_MIN_CLUSTER_SIZE", "35"))
MODEL_NAME = os.getenv("GRAPHRAG_EMBED_MODEL", "paraphrase-multilingual-MiniLM-L12-v2")

NOISE_WORDS = {
    "nguyen", "ngọc", "trần", "lê", "hoàng", "thảo", "phương", "bảo", "hồng",
    "tao", "tui", "fl", "nam", "huyền", "xinh", "tuần1", "tháng", "lại",
    "cái", "thấy", "đâu", "xin", "bán", "mới", "ơi", "nha", "nhé", "ạ",
    "haha", "hihi", "kkk", "kkkk", "lol", "tag", "ib", "rep", "haha", "hehe",
}

BUSINESS_TAXONOMY = {
    "product_taste_quality": [
        "ngon", "dở", "ngọt", "đắng", "nhạt", "đậm", "vị", "trà", "sữa", "matcha",
        "topping", "kem", "đá", "chất lượng", "món", "nước", "uống", "trân châu",
    ],
    "price_promotion": [
        "giá", "đắt", "rẻ", "voucher", "mã", "giảm", "khuyến mãi", "ưu đãi", "sale",
        "deal", "combo", "freeship", "áp dụng", "mua", "tặng",
    ],
    "app_payment_order": [
        "app", "thanh toán", "momo", "vnpay", "bank", "online", "đặt hàng", "order",
        "lỗi app", "không thanh toán", "đơn hàng", "mã đơn", "qr", "chuyển khoản",
    ],
    "service_store_staff": [
        "nhân viên", "phục vụ", "thái độ", "quầy", "xếp hàng", "chờ lâu", "chậm", "nhanh",
        "dịch vụ", "order", "tư vấn", "bảo vệ",
    ],
    "delivery_waiting": [
        "giao hàng", "ship", "shipper", "đợi", "chờ", "lâu", "trễ", "giao", "đơn", "delay",
        "nhận hàng", "đặt giao",
    ],
    "branch_availability": [
        "chi nhánh", "cửa hàng", "quán", "mở", "đóng", "gần", "xa", "địa chỉ", "ở đâu",
        "hết món", "còn món", "khu vực", "tỉnh", "thành phố",
    ],
    "brand_love_content": [
        "thích", "yêu", "mê", "xinh", "đẹp", "trend", "viral", "clip", "video", "content",
        "hình", "ảnh", "review", "quay", "nhạc",
    ],
}

RISK_HINTS = {
    "product_taste_quality": "product_quality_risk",
    "price_promotion": "price_promotion_risk",
    "app_payment_order": "app_payment_order_risk",
    "service_store_staff": "service_store_staff_risk",
    "delivery_waiting": "delivery_waiting_risk",
    "branch_availability": "availability_store_risk",
    "brand_love_content": "brand_content_signal",
}


def normalize_text(text: Any) -> str:
    text = str(text).lower()
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"www\S+", " ", text)
    text = re.sub(r"[^0-9a-zA-ZÀ-ỹ_\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_noise_comment(text: str) -> bool:
    clean = normalize_text(text)
    if len(clean) < MIN_TEXT_LEN:
        return True
    tokens = clean.split()
    if len(tokens) <= 2:
        return True
    if clean.startswith("@"):
        return True
    if re.fullmatch(r"(ha|haha|hihi|kkk|kaka|hehe)+", clean):
        return True
    return False


def taxonomy_scores(text: str) -> Dict[str, int]:
    clean = normalize_text(text)
    scores = {}
    for topic, keywords in BUSINESS_TAXONOMY.items():
        scores[topic] = sum(1 for keyword in keywords if keyword in clean)
    return scores


def align_taxonomy(texts: List[str], topic_words: List[str]) -> Tuple[str, float, Dict[str, int]]:
    joined = " ".join(texts[:80] + topic_words)
    scores = taxonomy_scores(joined)
    best_topic = max(scores, key=scores.get)
    total_hits = sum(scores.values())
    if scores[best_topic] <= 0:
        return "general_noise_or_social", 0.0, scores
    alignment = scores[best_topic] / max(1, total_hits)
    return best_topic, float(min(1.0, alignment)), scores


def keyword_quality(topic_words: List[str], taxonomy_label: str) -> Tuple[float, float, float]:
    words = [str(w).lower().strip() for w in topic_words[:12] if str(w).strip()]
    if not words:
        return 0.0, 1.0, 0.0
    noise_count = sum(1 for w in words if w in NOISE_WORDS)
    business_vocab = set()
    for values in BUSINESS_TAXONOMY.values():
        business_vocab.update(values)
    business_count = sum(1 for w in words if any(v in w for v in business_vocab))
    strategic_count = 0
    if taxonomy_label in BUSINESS_TAXONOMY:
        strategic_count = sum(1 for w in words if any(v in w for v in BUSINESS_TAXONOMY[taxonomy_label]))
    n = max(1, len(words))
    noise_ratio = noise_count / n
    business_ratio = business_count / n
    strategic_ratio = strategic_count / n
    score = max(0.0, min(1.0, 0.45 * business_ratio + 0.35 * strategic_ratio + 0.20 * (1.0 - noise_ratio)))
    return score, noise_ratio, strategic_ratio


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.55:
        return "medium"
    return "low"


def mode_or_unknown(series: pd.Series) -> str:
    if series.empty:
        return "unknown"
    mode = series.astype(str).mode()
    return str(mode.iloc[0]) if not mode.empty else "unknown"


def compute_cluster_metrics(embeddings: np.ndarray, labels: np.ndarray) -> Dict[str, Any]:
    metrics = {
        "silhouette_score": None,
        "davies_bouldin_score": None,
        "calinski_harabasz_score": None,
        "valid_cluster_count": 0,
        "outlier_ratio": None,
    }
    try:
        from sklearn.metrics import silhouette_score, davies_bouldin_score, calinski_harabasz_score
        valid_mask = labels != -1
        valid_labels = labels[valid_mask]
        metrics["valid_cluster_count"] = int(len(set(valid_labels)))
        metrics["outlier_ratio"] = float((labels == -1).mean())
        if len(set(valid_labels)) >= 2 and valid_mask.sum() >= 50:
            sample_idx = np.where(valid_mask)[0]
            if len(sample_idx) > 5000:
                rng = np.random.default_rng(RANDOM_STATE)
                sample_idx = rng.choice(sample_idx, size=5000, replace=False)
            sample_embeddings = embeddings[sample_idx]
            sample_labels = labels[sample_idx]
            metrics["silhouette_score"] = float(silhouette_score(sample_embeddings, sample_labels, metric="cosine"))
            metrics["davies_bouldin_score"] = float(davies_bouldin_score(sample_embeddings, sample_labels))
            metrics["calinski_harabasz_score"] = float(calinski_harabasz_score(sample_embeddings, sample_labels))
    except Exception as exc:
        metrics["metric_error"] = f"{type(exc).__name__}: {exc}"
    return metrics


def load_comments() -> pd.DataFrame:
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT}")
    df = pd.read_csv(INPUT, encoding="utf-8-sig", low_memory=False)
    required = ["brand", "platform", "text", "sentiment_label", "risk_group"]
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise RuntimeError(f"Missing required columns: {missing}")
    df = df[df["brand"].isin(["phuc_long", "highlands", "katinat"])].copy()
    text_col = "text_for_model" if "text_for_model" in df.columns else "text"
    df["text_clean"] = df[text_col].fillna("").map(normalize_text)
    df["is_noise_comment"] = df["text_clean"].map(is_noise_comment)
    df = df[~df["is_noise_comment"]].copy()
    df = df[df["text_clean"].str.len() >= MIN_TEXT_LEN].copy()
    if len(df) > MAX_COMMENTS:
        df = df.sample(MAX_COMMENTS, random_state=RANDOM_STATE).copy()
    df = df.reset_index(drop=True)
    return df


def fit_topic_model(docs: List[str]):
    from sentence_transformers import SentenceTransformer
    from bertopic import BERTopic
    from hdbscan import HDBSCAN
    from umap import UMAP
    from sklearn.feature_extraction.text import CountVectorizer

    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        device = "cpu"

    embedding_model = SentenceTransformer(MODEL_NAME, device=device)
    embeddings = embedding_model.encode(
        docs,
        batch_size=96 if device == "cuda" else 32,
        show_progress_bar=True,
        normalize_embeddings=True,
    )

    umap_model = UMAP(
        n_neighbors=25,
        n_components=10,
        min_dist=0.0,
        metric="cosine",
        random_state=RANDOM_STATE,
    )
    hdbscan_model = HDBSCAN(
        min_cluster_size=MIN_CLUSTER_SIZE,
        min_samples=10,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=True,
    )
    vectorizer_model = CountVectorizer(
        ngram_range=(1, 2),
        min_df=5,
        max_df=0.85,
    )
    topic_model = BERTopic(
        embedding_model=embedding_model,
        umap_model=umap_model,
        hdbscan_model=hdbscan_model,
        vectorizer_model=vectorizer_model,
        language="multilingual",
        calculate_probabilities=True,
        verbose=True,
    )
    topics, probabilities = topic_model.fit_transform(docs, embeddings)
    return topic_model, np.asarray(topics), probabilities, np.asarray(embeddings)


def probability_for_assignments(probabilities: Any, topics: np.ndarray) -> np.ndarray:
    if probabilities is None:
        return np.where(topics == -1, 0.0, 0.65)
    probs = np.asarray(probabilities)
    if probs.ndim == 1:
        return probs.astype(float)
    if probs.ndim == 2:
        return probs.max(axis=1).astype(float)
    return np.where(topics == -1, 0.0, 0.65)


def build_outputs(df: pd.DataFrame, topic_model: Any, topics: np.ndarray, probabilities: Any, embeddings: np.ndarray) -> Dict[str, Any]:
    assignment_prob = probability_for_assignments(probabilities, topics)
    assignments = df.copy()
    assignments["topic_id"] = topics
    assignments["topic_probability"] = assignment_prob
    assignments.to_csv(ASSIGNMENTS_OUT, index=False, encoding="utf-8-sig")

    rows = []
    representative_rows = []
    unique_topics = sorted([int(t) for t in set(topics) if int(t) != -1])

    for topic_id in unique_topics:
        sub = assignments[assignments["topic_id"] == topic_id].copy()
        if sub.empty:
            continue

        topic_pairs = topic_model.get_topic(topic_id) or []
        topic_words = [word for word, _ in topic_pairs[:12]]
        rep_docs = topic_model.get_representative_docs(topic_id) or []
        taxonomy_label, taxonomy_alignment, taxonomy_score_map = align_taxonomy(rep_docs + sub["text_clean"].head(100).tolist(), topic_words)
        key_quality, noise_ratio, strategic_ratio = keyword_quality(topic_words, taxonomy_label)

        comment_count = int(len(sub))
        positive_count = int((sub["sentiment_label"].astype(str) == "positive").sum())
        neutral_count = int((sub["sentiment_label"].astype(str) == "neutral").sum())
        negative_count = int((sub["sentiment_label"].astype(str) == "negative").sum())
        sentiment_total = max(1, positive_count + neutral_count + negative_count)
        sentiment_clarity = max(positive_count, neutral_count, negative_count) / sentiment_total
        negative_ratio = negative_count / sentiment_total

        top_brand = mode_or_unknown(sub["brand"])
        top_platform = mode_or_unknown(sub["platform"])
        risk_group = mode_or_unknown(sub["risk_group"])
        if risk_group in {"none", "nan", "unknown", ""}:
            risk_group = RISK_HINTS.get(taxonomy_label, "none")
        risk_clarity = 0.20 if risk_group in {"none", "nan", "unknown", ""} else 1.00

        brand_purity = float((sub["brand"].astype(str) == top_brand).mean())
        phuc_long_ratio = float((sub["brand"].astype(str) == "phuc_long").mean())
        avg_probability = float(sub["topic_probability"].fillna(0).mean())
        representative_quality = min(1.0, len(rep_docs) / 5.0)
        volume_score = min(1.0, comment_count / 1500.0)

        topic_reliability_score = (
            0.18 * taxonomy_alignment
            + 0.15 * avg_probability
            + 0.15 * key_quality
            + 0.12 * representative_quality
            + 0.10 * brand_purity
            + 0.10 * phuc_long_ratio
            + 0.10 * sentiment_clarity
            + 0.05 * risk_clarity
            + 0.05 * volume_score
        )
        topic_reliability_score = min(1.0, max(0.0, topic_reliability_score))
        confidence = confidence_label(topic_reliability_score)
        noisy = taxonomy_label == "general_noise_or_social" or noise_ratio >= 0.40 or key_quality < 0.30

        rows.append({
            "topic_id": topic_id,
            "topic_label": taxonomy_label,
            "bertopic_label": " / ".join(topic_words[:5]),
            "keywords": ", ".join(topic_words),
            "comment_count": comment_count,
            "positive_count": positive_count,
            "neutral_count": neutral_count,
            "negative_count": negative_count,
            "negative_ratio": round(negative_ratio, 4),
            "top_brand": top_brand,
            "phuc_long_ratio": round(phuc_long_ratio, 4),
            "brand_purity_proxy": round(brand_purity, 4),
            "top_platform": top_platform,
            "top_risk_group": risk_group,
            "taxonomy_alignment_score": round(taxonomy_alignment, 4),
            "avg_cluster_probability": round(avg_probability, 4),
            "keyword_quality_score": round(key_quality, 4),
            "noise_keyword_ratio": round(noise_ratio, 4),
            "strategic_keyword_ratio": round(strategic_ratio, 4),
            "representative_comment_quality": round(representative_quality, 4),
            "volume_score": round(volume_score, 4),
            "sentiment_clarity_score": round(sentiment_clarity, 4),
            "risk_clarity_score": round(risk_clarity, 4),
            "topic_reliability_score": round(topic_reliability_score, 4),
            "decision_confidence": confidence,
            "noisy_topic_flag": bool(noisy),
            "management_usefulness": (
                "usable_for_decision" if confidence == "high" else "use_with_human_review" if confidence == "medium" else "noisy_do_not_conclude"
            ),
            "taxonomy_score_map": json.dumps(taxonomy_score_map, ensure_ascii=False),
        })

        top_rep = sub.sort_values("topic_probability", ascending=False).head(5)
        for rank, (_, rep_row) in enumerate(top_rep.iterrows(), start=1):
            representative_rows.append({
                "topic_id": topic_id,
                "rank": rank,
                "brand": rep_row.get("brand", "unknown"),
                "platform": rep_row.get("platform", "unknown"),
                "sentiment_label": rep_row.get("sentiment_label", "unknown"),
                "risk_group": rep_row.get("risk_group", "unknown"),
                "topic_probability": round(float(rep_row.get("topic_probability", 0.0)), 4),
                "text": rep_row.get("text", ""),
            })

    topics_df = pd.DataFrame(rows).sort_values(["topic_reliability_score", "comment_count"], ascending=False)
    representatives_df = pd.DataFrame(representative_rows)
    topics_df.to_csv(TOPICS_OUT, index=False, encoding="utf-8-sig")
    topics_df.to_csv(QUALITY_OUT, index=False, encoding="utf-8-sig")
    representatives_df.to_csv(REPRESENTATIVES_OUT, index=False, encoding="utf-8-sig")

    nodes, edges = [], []
    for _, row in topics_df.iterrows():
        topic_node = f"topic_{int(row.topic_id)}"
        nodes.append({
            "id": topic_node,
            "label": row.topic_label,
            "group": "business_topic",
            "value": int(row.comment_count),
            "title": f"Reliability: {row.topic_reliability_score} | Confidence: {row.decision_confidence} | Keywords: {row.keywords}",
        })
        dimensions = [
            (row.top_brand, "brand", 3),
            (row.top_platform, "platform", 2),
            (row.top_risk_group, "risk", 2),
            (row.decision_confidence, "confidence", 2),
            ("phuc_long" if row.phuc_long_ratio > 0 else "no_phuc_long_signal", "focus", 1),
        ]
        for dim, group, weight in dimensions:
            node_id = f"{group}_{dim}"
            nodes.append({"id": node_id, "label": str(dim), "group": group, "value": 10, "title": f"{group}: {dim}"})
            edges.append({"source": topic_node, "target": node_id, "weight": weight, "title": f"topic-{group}"})

    nodes_df = pd.DataFrame(nodes).drop_duplicates("id") if nodes else pd.DataFrame(columns=["id", "label", "group", "value", "title"])
    edges_df = pd.DataFrame(edges) if edges else pd.DataFrame(columns=["source", "target", "weight", "title"])
    nodes_df.to_csv(NODES_OUT, index=False, encoding="utf-8-sig")
    edges_df.to_csv(EDGES_OUT, index=False, encoding="utf-8-sig")

    try:
        from pyvis.network import Network
        net = Network(height="760px", width="100%", bgcolor="#ffffff", font_color="#222222", directed=False)
        color_map = {
            "business_topic": "#2E86AB",
            "brand": "#F18F01",
            "platform": "#6A4C93",
            "risk": "#C73E1D",
            "confidence": "#2A9D8F",
            "focus": "#5C677D",
        }
        for _, node in nodes_df.iterrows():
            net.add_node(
                node["id"],
                label=str(node["label"]),
                title=str(node.get("title", "")),
                value=float(node.get("value", 10)),
                color=color_map.get(str(node.get("group", "")), "#999999"),
            )
        for _, edge in edges_df.iterrows():
            net.add_edge(edge["source"], edge["target"], value=float(edge.get("weight", 1)), title=str(edge.get("title", "")))
        net.repulsion(node_distance=180, central_gravity=0.25, spring_length=180, spring_strength=0.04)
        net.write_html(str(HTML_OUT), notebook=False)
    except Exception as exc:
        HTML_OUT.write_text(f"<html><body><pre>PyVis render failed: {type(exc).__name__}: {exc}</pre></body></html>", encoding="utf-8")

    metrics = compute_cluster_metrics(embeddings, topics)
    metrics.update({
        "status": "PASS",
        "embedding_model": MODEL_NAME,
        "raw_comments_after_cleaning": int(len(df)),
        "bertopic_topic_count_excluding_outliers": int(len(set(topics)) - (1 if -1 in set(topics) else 0)),
        "outlier_count": int((topics == -1).sum()),
        "topic_quality_rows": int(len(topics_df)),
        "high_confidence": int((topics_df["decision_confidence"] == "high").sum()) if not topics_df.empty else 0,
        "medium_confidence": int((topics_df["decision_confidence"] == "medium").sum()) if not topics_df.empty else 0,
        "low_confidence": int((topics_df["decision_confidence"] == "low").sum()) if not topics_df.empty else 0,
    })
    METRICS_OUT.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    report = [
        "# Comment GraphRAG Pro Summary",
        "",
        f"- Embedding model: {MODEL_NAME}",
        f"- Clean comments used: {len(df):,}",
        f"- BERTopic clusters excluding outliers: {metrics['bertopic_topic_count_excluding_outliers']:,}",
        f"- Outlier count: {metrics['outlier_count']:,}",
        f"- Topic quality rows: {len(topics_df):,}",
        f"- High confidence topics: {metrics['high_confidence']:,}",
        f"- Medium confidence topics: {metrics['medium_confidence']:,}",
        f"- Low confidence topics: {metrics['low_confidence']:,}",
        "",
        "## Topic quality table",
        topics_df.to_markdown(index=False) if not topics_df.empty else "No topic quality rows",
        "",
        "## Academic note",
        (
            "Bản Pro sử dụng SentenceTransformer embeddings + BERTopic/HDBSCAN để phát hiện cụm ngữ nghĩa, "
            "sau đó căn chỉnh với taxonomy nghiệp vụ và tính topic reliability/decision confidence. "
            "Vì đây là topic modeling không giám sát, hệ thống không dùng accuracy supervised learning; "
            "thay vào đó dùng cluster metrics, membership probability, taxonomy alignment, keyword quality, "
            "brand purity, Phúc Long ratio, sentiment clarity và risk clarity."
        ),
    ]
    SUMMARY_OUT.write_text("\n".join(report), encoding="utf-8")
    return metrics


def main() -> None:
    df = load_comments()
    docs = df["text_clean"].tolist()
    topic_model, topics, probabilities, embeddings = fit_topic_model(docs)
    metrics = build_outputs(df, topic_model, topics, probabilities, embeddings)
    print(json.dumps({
        "status": "PASS",
        "clean_comments": metrics["raw_comments_after_cleaning"],
        "clusters": metrics["bertopic_topic_count_excluding_outliers"],
        "outliers": metrics["outlier_count"],
        "high_confidence": metrics["high_confidence"],
        "medium_confidence": metrics["medium_confidence"],
        "low_confidence": metrics["low_confidence"],
        "outputs": {
            "topics": str(TOPICS_OUT),
            "assignments": str(ASSIGNMENTS_OUT),
            "quality": str(QUALITY_OUT),
            "nodes": str(NODES_OUT),
            "edges": str(EDGES_OUT),
            "html": str(HTML_OUT),
            "summary": str(SUMMARY_OUT),
            "metrics": str(METRICS_OUT),
            "representatives": str(REPRESENTATIVES_OUT),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
