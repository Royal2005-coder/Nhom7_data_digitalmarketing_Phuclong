import json
from pathlib import Path
import pandas as pd
from pyvis.network import Network

# Khởi tạo đường dẫn thư mục gốc và thư mục output
BASE_DIR = Path(__file__).resolve().parents[1]
OUT_DIR = BASE_DIR / "graph_rag" / "outputs"

BUSINESS_CSV = OUT_DIR / "comment_business_topics_decision_v3.csv"
NODES_OUT = OUT_DIR / "comment_business_decision_nodes_v3.csv"
EDGES_OUT = OUT_DIR / "comment_business_decision_edges_v3.csv"
HTML_OUT = OUT_DIR / "comment_business_decision_graph_v3.html"
SUMMARY_OUT = OUT_DIR / "comment_business_decision_graph_v3.md"

COLOR_MAP = {
    "business_topic": "#2563EB",
    "confidence_high": "#16A34A",
    "confidence_medium": "#F59E0B",
    "confidence_low": "#DC2626",
    "owner": "#7C3AED",
    "risk": "#EF4444",
    "brand_focus": "#0EA5E9",
    "platform": "#64748B",
}

X_POS = {
    "business_topic": -500,
    "confidence": -120,
    "owner": 240,
    "risk": 520,
    "platform": 640,  # Thêm trục X riêng cho platform để tránh đè lên risk
    "brand_focus": 760,
}


def node_color(group: str, label: str = "") -> str:
    if group == "confidence":
        return COLOR_MAP.get(f"confidence_{label}", "#F59E0B")
    return COLOR_MAP.get(group, "#94A3B8")


def safe_id(text: str) -> str:
    return (
        str(text)
        .lower()
        .replace(" ", "_")
        .replace("/", "_")
        .replace("+", "plus")
        .replace("&", "and")
    )


def main() -> None:
    if not BUSINESS_CSV.exists():
        raise FileNotFoundError(f"Missing {BUSINESS_CSV}")

    df = pd.read_csv(BUSINESS_CSV, encoding="utf-8-sig", low_memory=False)

    required = [
        "business_topic",
        "comment_count",
        "phuc_long_ratio",
        "business_reliability_score",
        "decision_confidence",
        "owner",
        "top_risk_group",
        "top_platform",
        "keywords",
    ]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise RuntimeError(f"Missing columns: {missing}")

    nodes = []
    edges = []

    # Cố định vị trí theo hàng để graph không thành hairball
    df = df.sort_values("business_reliability_score", ascending=False).reset_index(drop=True)

    for idx, row in df.iterrows():
        y = idx * 150

        topic = str(row["business_topic"])
        confidence = str(row["decision_confidence"])
        owner = str(row["owner"])
        risk = str(row["top_risk_group"])
        platform = str(row["top_platform"])

        phuc_long_ratio = float(row.get("phuc_long_ratio", 0))
        reliability = float(row.get("business_reliability_score", 0))
        comment_count = int(row.get("comment_count", 0))
        keywords = str(row.get("keywords", ""))

        topic_id = f"topic::{safe_id(topic)}"
        confidence_id = f"confidence::{confidence}"
        owner_id = f"owner::{safe_id(owner)}"
        risk_id = f"risk::{safe_id(risk)}"
        platform_id = f"platform::{safe_id(platform)}"
        brand_focus_id = f"brand_focus::phuc_long_ratio"

        topic_title = (
            f"<b>{topic}</b><br>"
            f"Comments: {comment_count:,}<br>"
            f"Reliability: {reliability:.3f}<br>"
            f"Confidence: {confidence}<br>"
            f"Phuc Long ratio: {phuc_long_ratio:.2%}<br>"
            f"Owner: {owner}<br>"
            f"Risk: {risk}<br>"
            f"Keywords: {keywords}"
        )

        nodes.append({
            "id": topic_id,
            "label": topic,
            "group": "business_topic",
            "value": max(15, min(60, comment_count / 80)),
            "title": topic_title,
            "x": X_POS["business_topic"],
            "y": y,
        })

        dim_nodes = [
            (confidence_id, confidence, "confidence", X_POS["confidence"], y),
            (owner_id, owner, "owner", X_POS["owner"], y),
            (risk_id, risk, "risk", X_POS["risk"], y),
            (platform_id, platform, "platform", X_POS["platform"], y + 55), # Sửa X_POS sang platform
            (brand_focus_id, "Phúc Long focus", "brand_focus", X_POS["brand_focus"], y),
        ]

        for node_id, label, group, x, yy in dim_nodes:
            nodes.append({
                "id": node_id,
                "label": label,
                "group": group,
                "value": 20,
                "title": f"{group}: {label}",
                "x": x,
                "y": yy,
            })

        edges.extend([
            {
                "source": topic_id,
                "target": confidence_id,
                "weight": max(1, reliability * 5),
                "relation": "has_confidence",
                "title": f"Reliability={reliability:.3f}",
            },
            {
                "source": topic_id,
                "target": owner_id,
                "weight": 2,
                "relation": "owned_by",
                "title": f"Owner={owner}",
            },
            {
                "source": topic_id,
                "target": risk_id,
                "weight": 2,
                "relation": "risk_signal",
                "title": f"Risk={risk}",
            },
            {
                "source": topic_id,
                "target": platform_id,
                "weight": 1,
                "relation": "dominant_platform",
                "title": f"Platform={platform}",
            },
            {
                "source": topic_id,
                "target": brand_focus_id,
                "weight": max(1, phuc_long_ratio * 5),
                "relation": "phuc_long_ratio",
                "title": f"Phuc Long ratio={phuc_long_ratio:.2%}",
            },
        ])

    nodes_df = pd.DataFrame(nodes).drop_duplicates("id")
    edges_df = pd.DataFrame(edges)

    nodes_df.to_csv(NODES_OUT, index=False, encoding="utf-8-sig")
    edges_df.to_csv(EDGES_OUT, index=False, encoding="utf-8-sig")

    net = Network(
        height="780px",
        width="100%",
        bgcolor="#ffffff",
        font_color="#111827",
        directed=True,
    )

    for _, node in nodes_df.iterrows():
        group = str(node["group"])
        label = str(node["label"])

        net.add_node(
            node["id"],
            label=label,
            title=str(node["title"]),
            value=float(node["value"]),
            color=node_color(group, label),
            x=float(node["x"]),
            y=float(node["y"]),
            physics=False,
        )

    for _, edge in edges_df.iterrows():
        relation = str(edge["relation"])
        color = "#94A3B8"

        if relation == "has_confidence":
            color = "#F59E0B"
        elif relation == "owned_by":
            color = "#7C3AED"
        elif relation == "risk_signal":
            color = "#EF4444"
        elif relation == "phuc_long_ratio":
            color = "#0EA5E9"

        net.add_edge(
            edge["source"],
            edge["target"],
            value=float(edge["weight"]),
            title=str(edge["title"]),
            label=str(edge["relation"]),
            color=color,
            smooth=False,
        )

    net.set_options(
        """
        {
          "physics": {
            "enabled": false
          },
          "interaction": {
            "hover": true,
            "navigationButtons": true,
            "keyboard": true
          },
          "edges": {
            "arrows": {
              "to": {
                "enabled": true,
                "scaleFactor": 0.7
              }
            },
            "font": {
              "size": 9,
              "align": "middle"
            },
            "smooth": false
          },
          "nodes": {
            "font": {
              "size": 16,
              "face": "arial"
            },
            "shape": "dot",
            "scaling": {
              "min": 12,
              "max": 50
            }
          }
        }
        """
    )

    net.write_html(str(HTML_OUT), notebook=False)

    summary = [
        "# Business Decision Graph v3",
        "",
        "Graph này được thiết kế để tránh hairball.",
        "",
        "## Node groups",
        "- Blue: business topic",
        "- Green/Orange/Red: confidence",
        "- Purple: owner",
        "- Red: risk",
        "- Cyan: Phúc Long focus",
        "- Gray: platform",
        "",
        "## Design rule",
        "Graph không vẽ toàn bộ micro-cluster. Graph chỉ vẽ quan hệ quản trị quan trọng: topic → confidence, owner, risk, platform, Phúc Long focus.",
        "",
        "## Business topics",
        df.to_markdown(index=False),
    ]

    SUMMARY_OUT.write_text("\n".join(summary), encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "nodes": int(len(nodes_df)),
        "edges": int(len(edges_df)),
        "html": str(HTML_OUT),
        "nodes_csv": str(NODES_OUT),
        "edges_csv": str(EDGES_OUT),
        "summary": str(SUMMARY_OUT),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()