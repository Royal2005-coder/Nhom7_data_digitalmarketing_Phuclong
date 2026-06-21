from pathlib import Path
import json
import re

import pandas as pd
import networkx as nx
from pyvis.network import Network
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import MiniBatchKMeans


BASE_DIR = Path(__file__).resolve().parents[1]
INPUT = BASE_DIR / "data" / "silver" / "silver_social_comments.csv"
OUT_DIR = BASE_DIR / "graph_rag" / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

STOPWORDS = {
    "và", "là", "của", "có", "cho", "mình", "bạn", "này", "đó", "thì", "mà",
    "với", "trong", "trên", "được", "không", "ko", "k", "rồi", "nha", "nhé",
    "ạ", "ơi", "cũng", "rất", "quá", "lắm", "đi", "về", "ở", "ra", "vào",
    "nên", "như", "để", "các", "một", "những", "em", "anh", "chị"
}


def normalize_text(text):
    text = str(text).lower()
    text = re.sub(r"http\S+", " ", text)
    text = re.sub(r"[^0-9a-zA-ZÀ-ỹ_\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def safe_mode(series, default="unknown"):
    mode = series.dropna().mode()
    if len(mode) == 0:
        return default
    return str(mode.iloc[0])


def main():
    if not INPUT.exists():
        raise FileNotFoundError(f"Missing input file: {INPUT}")

    df = pd.read_csv(INPUT, encoding="utf-8-sig", low_memory=False)

    required_cols = ["brand", "platform", "text", "sentiment_label", "risk_group"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise RuntimeError(f"Missing columns in silver_social_comments.csv: {missing}")

    df = df[df["brand"].isin(["phuc_long", "highlands", "katinat"])].copy()
    df["text_clean"] = df["text"].fillna("").map(normalize_text)
    df = df[df["text_clean"].str.len() >= 8].copy()

    if len(df) > 12000:
        df = df.sample(12000, random_state=42)

    vectorizer = TfidfVectorizer(
        max_features=1800,
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.8,
        stop_words=list(STOPWORDS),
    )

    x_matrix = vectorizer.fit_transform(df["text_clean"])

    n_clusters = min(18, max(6, len(df) // 600))

    model = MiniBatchKMeans(
        n_clusters=n_clusters,
        random_state=42,
        batch_size=1024,
        n_init="auto",
    )

    df["topic_id"] = model.fit_predict(x_matrix)

    terms = vectorizer.get_feature_names_out()
    centers = model.cluster_centers_

    topic_rows = []

    for topic_id in range(n_clusters):
        sub = df[df["topic_id"] == topic_id]
        top_idx = centers[topic_id].argsort()[-10:][::-1]
        keywords = [terms[i] for i in top_idx]
        topic_label = " / ".join(keywords[:4])

        topic_rows.append({
            "topic_id": int(topic_id),
            "topic_label": topic_label,
            "keywords": ", ".join(keywords),
            "comment_count": int(len(sub)),
            "positive_count": int((sub["sentiment_label"] == "positive").sum()),
            "neutral_count": int((sub["sentiment_label"] == "neutral").sum()),
            "negative_count": int((sub["sentiment_label"] == "negative").sum()),
            "top_brand": safe_mode(sub["brand"], "unknown"),
            "top_platform": safe_mode(sub["platform"], "unknown"),
            "top_risk_group": safe_mode(sub["risk_group"], "none"),
        })

    topics = pd.DataFrame(topic_rows)

    graph = nx.Graph()

    def add_node(node_id, label, group, value=5, title=""):
        graph.add_node(
            node_id,
            label=str(label),
            group=str(group),
            value=int(value),
            title=str(title),
        )

    for _, row in topics.iterrows():
        topic_node = f"topic_{row.topic_id}"

        add_node(
            topic_node,
            f"T{row.topic_id}: {row.topic_label}",
            "topic",
            value=max(8, int(row.comment_count)),
            title=(
                f"Topic {row.topic_id}<br>"
                f"Comments: {row.comment_count}<br>"
                f"Positive: {row.positive_count}<br>"
                f"Neutral: {row.neutral_count}<br>"
                f"Negative: {row.negative_count}<br>"
                f"Risk: {row.top_risk_group}"
            ),
        )

        for keyword in str(row.keywords).split(", ")[:6]:
            keyword_node = f"keyword_{keyword}"
            add_node(keyword_node, keyword, "keyword", value=4, title=f"Keyword: {keyword}")
            graph.add_edge(topic_node, keyword_node, weight=2, title="topic-keyword")

        for value, group_name in [
            (row.top_brand, "brand"),
            (row.top_platform, "platform"),
            (row.top_risk_group, "risk"),
        ]:
            dim_node = f"{group_name}_{value}"
            add_node(dim_node, value, group_name, value=10, title=f"{group_name}: {value}")
            graph.add_edge(topic_node, dim_node, weight=3, title=f"topic-{group_name}")

        for sentiment in ["positive", "neutral", "negative"]:
            count = int(row[f"{sentiment}_count"])
            if count > 0:
                sentiment_node = f"sentiment_{sentiment}"
                add_node(sentiment_node, sentiment, "sentiment", value=12, title=f"Sentiment: {sentiment}")
                graph.add_edge(topic_node, sentiment_node, weight=max(1, count), title=f"{count} comments")

    nodes = [{"id": node, **attrs} for node, attrs in graph.nodes(data=True)]
    edges = [{"source": source, "target": target, **attrs} for source, target, attrs in graph.edges(data=True)]

    topics.to_csv(OUT_DIR / "comment_topics.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(nodes).to_csv(OUT_DIR / "comment_graph_nodes.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(edges).to_csv(OUT_DIR / "comment_graph_edges.csv", index=False, encoding="utf-8-sig")
    nx.write_graphml(graph, OUT_DIR / "comment_topic_graph.graphml")

    net = Network(height="720px", width="100%", bgcolor="#ffffff", font_color="#222222")
    net.from_nx(graph)
    net.repulsion(
        node_distance=180,
        central_gravity=0.18,
        spring_length=120,
        spring_strength=0.05,
        damping=0.9,
    )
    net.show_buttons(filter_=["physics"])
    net.save_graph(str(OUT_DIR / "comment_topic_graph.html"))

    summary = []
    summary.append("# Comment Sentiment Topic GraphRAG Summary")
    summary.append("")
    summary.append(f"- Input comments sampled: {len(df):,}")
    summary.append(f"- Topic clusters: {n_clusters}")
    summary.append(f"- Graph nodes: {graph.number_of_nodes()}")
    summary.append(f"- Graph edges: {graph.number_of_edges()}")
    summary.append("")
    summary.append("## Top Topics")
    summary.append(topics.sort_values("comment_count", ascending=False).head(10).to_markdown(index=False))

    (OUT_DIR / "comment_graph_summary.md").write_text("\n".join(summary), encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "comments": int(len(df)),
        "topics": int(n_clusters),
        "nodes": int(graph.number_of_nodes()),
        "edges": int(graph.number_of_edges()),
        "output_dir": str(OUT_DIR),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
import networkx as nx
