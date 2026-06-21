from pathlib import Path
import json
import os
import re

import pandas as pd
import plotly.express as px
import requests
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

CURRENT_FILE = Path(__file__).resolve()
DASHBOARD_DIR = CURRENT_FILE.parents[1]
BASE_DIR = DASHBOARD_DIR.parent
ENV_PATH = BASE_DIR / "config" / ".env"
GRAPH_DIR = BASE_DIR / "graph_rag" / "outputs"

load_dotenv(ENV_PATH)

API_BASE = os.getenv("TOKENROUTER_API_BASE", "https://api.tokenrouter.com/v1").rstrip("/")
API_KEY = os.getenv("TOKENROUTER_API_KEY", "")
MODEL = os.getenv("TOKENROUTER_MODEL", "MiniMax-M3")

st.set_page_config(
    page_title="Comment GraphRAG Pro Decision Intelligence",
    page_icon="🕸️",
    layout="wide",
)


def clean_ai_output(text: str) -> str:
    if not text:
        return ""

    cleaned = str(text)
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"```thinking.*?```", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"```think.*?```", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"^\s*(Analysis|Reasoning|Chain of thought)\s*:\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def call_ai(messages, temperature=0.2, max_tokens=4200):
    if not API_KEY:
        return "Chưa cấu hình TOKENROUTER_API_KEY trong mvp_ai_bi_phuclong/config/.env."

    url = f"{API_BASE}/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=180)
        if response.status_code >= 400:
            return f"AI API error {response.status_code}: {response.text[:1800]}"
        data = response.json()
        return clean_ai_output(data["choices"][0]["message"]["content"])
    except Exception as exc:
        return f"AI call failed: {exc}"


def render_ai_answer(answer: str, key_prefix: str):
    cleaned = clean_ai_output(answer)
    st.markdown(cleaned)
    st.download_button(
        label="Download AI insight (.md)",
        data=cleaned.encode("utf-8"),
        file_name=f"{key_prefix}.md",
        mime="text/markdown",
        use_container_width=True, # Đã sửa từ width="stretch" tránh lỗi Streamlit API
    )


@st.cache_data
def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)


def load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def safe_metric(value, default="N/A"):
    try:
        if value is None:
            return default
        if pd.isna(value):
            return default
        return value
    except Exception:
        return default


def build_graph_ai_context(
    question: str,
    topics_df: pd.DataFrame,
    nodes_df: pd.DataFrame,
    edges_df: pd.DataFrame,
    summary_text: str,
    pro_quality_df: pd.DataFrame,
    pro_metrics: dict,
    business_v3_df: pd.DataFrame,
    business_reps_v3_df: pd.DataFrame,
    clean_stats: dict,
    model_stats: dict,
) -> str:
    parts = []
    parts.append("# Comment GraphRAG Decision Intelligence Context")
    parts.append("")
    parts.append(f"User question: {question}")
    parts.append("")
    parts.append("Business objective: chuyển comment graph phức tạp thành insight quản trị marketing, CSKH và vận hành.")
    parts.append("Research focus: Phúc Long là trọng tâm; Highlands và Katinat chỉ dùng làm benchmark.")
    parts.append("Important governance rule: không dùng micro-cluster low-confidence làm kết luận chính.")
    parts.append("")

    parts.append("## Research Question Mapping")
    parts.append("- RQ1: Hiệu suất và khác biệt thảo luận theo nền tảng.")
    parts.append("- RQ2: So sánh Phúc Long với Highlands/Katinat như benchmark.")
    parts.append("- RQ3: Chủ đề/comment cluster nào ảnh hưởng đến hiệu quả nội dung.")
    parts.append("- RQ4: Sentiment/risk group nào cần theo dõi.")
    parts.append("- RQ5: Hành động đề xuất cho marketing, CSKH và vận hành.")
    parts.append("")

    if clean_stats:
        parts.append("## Clean Corpus Stats")
        parts.append(json.dumps(clean_stats, ensure_ascii=False, indent=2))
        parts.append("")

    if model_stats:
        parts.append("## Modeling Corpus Stats")
        parts.append(json.dumps(model_stats, ensure_ascii=False, indent=2))
        parts.append("")

    if pro_metrics:
        parts.append("## BERTopic Pro Model Metrics")
        parts.append(json.dumps(pro_metrics, ensure_ascii=False, indent=2))
        parts.append("")

    if not business_v3_df.empty:
        parts.append("## Business Decision v3 Topics")
        business_view = business_v3_df.sort_values(
            "business_reliability_score",
            ascending=False,
        )
        parts.append(business_view.to_markdown(index=False))
        parts.append("")
        parts.append("Business Decision Guardrails:")
        parts.append("- Business Decision v3 là tầng ra quyết định chính.")
        parts.append("- Không dùng micro-cluster làm kết luận trực tiếp.")
        parts.append("- Topic medium-confidence dùng làm tín hiệu định hướng, cần human review trước quyết định lớn.")
        parts.append("- Topic low-confidence chỉ dùng để theo dõi thêm, không dùng làm kết luận chính.")
        parts.append("- Nếu không có high-confidence topic, phải nói rõ hạn chế độ tin cậy.")
        parts.append("- Mỗi đề xuất cần nêu business_topic, confidence, owner và KPI.")
        parts.append("")

    if not business_reps_v3_df.empty:
        parts.append("## Representative Comments v3")
        rep_cols = [
            "business_topic",
            "rank",
            "brand",
            "platform",
            "sentiment_label",
            "risk_group",
            "business_match_confidence",
            "topic_probability",
            "text",
        ]
        rep_cols = [col for col in rep_cols if col in business_reps_v3_df.columns]
        parts.append(business_reps_v3_df[rep_cols].head(80).to_markdown(index=False))
        parts.append("")
    if "business_graph_nodes_v3_df" in globals() and not business_graph_nodes_v3_df.empty:
        parts.append("## Business Decision Graph v3 Nodes")
        node_cols = ["id", "label", "group", "value", "title"]
        node_cols = [col for col in node_cols if col in business_graph_nodes_v3_df.columns]
        parts.append(business_graph_nodes_v3_df[node_cols].head(100).to_markdown(index=False))
        parts.append("")

    if "business_graph_edges_v3_df" in globals() and not business_graph_edges_v3_df.empty:
        parts.append("## Business Decision Graph v3 Edges")
        edge_cols = ["source", "target", "relation", "weight", "title"]
        edge_cols = [col for col in edge_cols if col in business_graph_edges_v3_df.columns]
        parts.append(business_graph_edges_v3_df[edge_cols].head(150).to_markdown(index=False))
        parts.append("")

    if "business_graph_summary_v3_text" in globals() and business_graph_summary_v3_text:
        parts.append("## Business Decision Graph v3 Summary")
        parts.append(business_graph_summary_v3_text)
        parts.append("")

    if not pro_quality_df.empty:
        parts.append("## BERTopic Pro Micro Topic Quality")
        quality_view = pro_quality_df.sort_values(
            "topic_reliability_score",
            ascending=False,
        ).head(30)
        parts.append(quality_view.to_markdown(index=False))
        parts.append("")

    if summary_text:
        parts.append("## Legacy/Graph Summary")
        parts.append(summary_text)
        parts.append("")

    if not topics_df.empty:
        work = topics_df.copy()
        if "comment_count" in work.columns:
            work = work.sort_values("comment_count", ascending=False)
        parts.append("## Legacy Topic Preview")
        parts.append(work.head(18).to_markdown(index=False))
        parts.append("")

    if not nodes_df.empty:
        parts.append("## Node Statistics")
        parts.append(f"Total nodes: {len(nodes_df)}")
        if "group" in nodes_df.columns:
            parts.append(str(nodes_df["group"].value_counts().to_dict()))
        parts.append("")

    if not edges_df.empty:
        parts.append("## Edge Statistics")
        parts.append(f"Total edges: {len(edges_df)}")
        parts.append("")

    parts.append("## Required Management Output")
    parts.append("- Executive insight")
    parts.append("- Business topics ưu tiên")
    parts.append("- Confidence limitation")
    parts.append("- Content / CRM / Operations action")
    parts.append("- Owner and KPI")
    parts.append("- Human review requirement where needed")

    return "\n".join(parts)


# 4. CONFIG PROMPTS
GRAPH_SYSTEM_PROMPT = """
Bạn là Comment GraphRAG Marketing Insight Agent cho Phúc Long.
Vai trò: data scientist, social listening analyst và marketing strategist.

Nguyên tắc:
- Chỉ dùng Comment GraphRAG Decision Intelligence Context.
- Không bịa số liệu.
- Phúc Long là trọng tâm; Highlands và Katinat chỉ dùng làm benchmark.
- Ưu tiên Business Decision v3 thay vì micro-cluster.
- Không dùng low-confidence topic làm kết luận chính.
- Nếu không có high-confidence topic, phải nói rõ insight chỉ ở mức định hướng/human review.
- Topic medium-confidence được dùng làm tín hiệu quản trị, nhưng cần human review trước quyết định lớn.
- Mỗi đề xuất cần nêu business_topic, confidence, owner và KPI.
- Không chỉ nói tích cực/tiêu cực; phải phân tích chủ đề, sentiment/risk, Phúc Long ratio, owner và KPI.
- Liên hệ rõ với RQ1–RQ5.
- Trả lời tiếng Việt tự nhiên, rõ ràng, học thuật vừa đủ, không văn phong máy móc.
- Không hiển thị chain-of-thought hoặc thẻ <think>.

Cấu trúc bắt buộc:
1. Executive insight
2. Mapping với RQ1–RQ5
3. Business topics đáng chú ý
4. Topic cần human review / không dùng làm kết luận chính
5. Hàm ý marketing / CSKH / vận hành
6. Hành động đề xuất
7. Owner
8. KPI theo dõi
9. Hạn chế độ tin cậy
"""

# 5. STREAMLIT UI CONTENT
st.title("🕸️ Comment GraphRAG Pro Decision Intelligence")
st.caption(
    "Raw comments → Clean corpus → BERTopic Pro → Business Decision v3 → AI strategy insight."
)

# Legacy v1 paths
topic_csv = GRAPH_DIR / "comment_topics.csv"
nodes_csv = GRAPH_DIR / "comment_graph_nodes.csv"
edges_csv = GRAPH_DIR / "comment_graph_edges.csv"
summary_md = GRAPH_DIR / "comment_graph_summary.md"
graph_html = GRAPH_DIR / "comment_topic_graph.html"

# Clean/model corpus paths
clean_stats_json = GRAPH_DIR / "clean_comment_corpus_stats_pro.json"
clean_report_md = GRAPH_DIR / "clean_comment_corpus_report_pro.md"
model_stats_json = GRAPH_DIR / "model_comment_corpus_stats_pro.json"
model_report_md = GRAPH_DIR / "model_comment_corpus_report_pro.md"

# BERTopic Pro paths
pro_topics_csv = GRAPH_DIR / "comment_topics_pro.csv"
pro_quality_csv = GRAPH_DIR / "comment_topic_quality_pro.csv"
pro_representatives_csv = GRAPH_DIR / "comment_topic_representatives_pro.csv"
pro_metrics_json = GRAPH_DIR / "comment_topic_model_metrics_pro.json"
pro_summary_md = GRAPH_DIR / "comment_graph_summary_pro.md"
pro_graph_html = GRAPH_DIR / "comment_topic_graph_pro.html"

# Business Decision v3 paths
business_v3_csv = GRAPH_DIR / "comment_business_topics_decision_v3.csv"
business_reps_v3_csv = GRAPH_DIR / "comment_business_topic_representatives_v3.csv"
business_summary_v3_md = GRAPH_DIR / "comment_business_decision_summary_v3.md"
# Business Decision Graph v3 paths
business_graph_v3_html = GRAPH_DIR / "comment_business_decision_graph_v3.html"
business_graph_nodes_v3_csv = GRAPH_DIR / "comment_business_decision_nodes_v3.csv"
business_graph_edges_v3_csv = GRAPH_DIR / "comment_business_decision_edges_v3.csv"
business_graph_summary_v3_md = GRAPH_DIR / "comment_business_decision_graph_v3.md"

# Load legacy
topics_df = load_csv(topic_csv)
nodes_df = load_csv(nodes_csv)
edges_df = load_csv(edges_csv)
summary_text = load_text(summary_md)

# Load pro/v3
clean_stats = load_json(clean_stats_json)
clean_report_text = load_text(clean_report_md)
model_stats = load_json(model_stats_json)
model_report_text = load_text(model_report_md)

pro_topics_df = load_csv(pro_topics_csv)
pro_quality_df = load_csv(pro_quality_csv)
pro_representatives_df = load_csv(pro_representatives_csv)
pro_metrics = load_json(pro_metrics_json)
pro_summary_text = load_text(pro_summary_md)

business_v3_df = load_csv(business_v3_csv)
business_reps_v3_df = load_csv(business_reps_v3_csv)
business_summary_v3_text = load_text(business_summary_v3_md)
business_graph_nodes_v3_df = load_csv(business_graph_nodes_v3_csv)
business_graph_edges_v3_df = load_csv(business_graph_edges_v3_csv)
business_graph_summary_v3_text = load_text(business_graph_summary_v3_md)

if topics_df.empty and pro_topics_df.empty and business_v3_df.empty:
    st.error(
        "Chưa có dữ liệu GraphRAG. Hãy chạy pipeline: clean_comment_corpus_pro.py → "
        "prepare_modeling_corpus_pro.py → build_comment_graphrag_pro.py → "
        "aggregate_graphrag_business_v3.py"
    )
    st.stop()

# Top summary metrics
st.markdown("### Pipeline Overview")

p1, p2, p3, p4, p5 = st.columns(5)

raw_comments = int(clean_stats.get("raw_comments", 0)) if clean_stats else 0
accepted_comments = int(clean_stats.get("accepted_comments", 0)) if clean_stats else 0
modeling_rows = int(model_stats.get("modeling_rows", 0)) if model_stats else 0
clusters = int(pro_metrics.get("bertopic_topic_count_excluding_outliers", 0)) if pro_metrics else 0
business_topics = int(len(business_v3_df)) if not business_v3_df.empty else 0

p1.metric("Raw comments", f"{raw_comments:,}" if raw_comments else "N/A")
p2.metric("Accepted clean", f"{accepted_comments:,}" if accepted_comments else "N/A")
p3.metric("Modeling rows", f"{modeling_rows:,}" if modeling_rows else "N/A")
p4.metric("BERTopic clusters", f"{clusters:,}" if clusters else "N/A")
p5.metric("Business topics", f"{business_topics:,}" if business_topics else "N/A")

# Clean corpus + model quality
st.divider()
st.markdown("### Clean Corpus & Modeling Quality Panel")

if clean_stats:
    c_clean1, c_clean2, c_clean3, c_clean4 = st.columns(4)
    c_clean1.metric("Raw comments", f"{clean_stats.get('raw_comments', 0):,}")
    c_clean2.metric("Accepted comments", f"{clean_stats.get('accepted_comments', 0):,}")
    c_clean3.metric("Rejected comments", f"{clean_stats.get('rejected_comments', 0):,}")
    c_clean4.metric("Accepted ratio", f"{float(clean_stats.get('accepted_ratio', 0)) * 100:.2f}%")

    st.caption(
        "Corpus đã loại comment quá ngắn, metadata mạng xã hội, comment trùng lặp sau chuẩn hóa "
        "và comment có tỷ lệ nhiễu cao trước khi đưa vào mô hình topic."
    )
else:
    st.warning("Chưa có clean_comment_corpus_stats_pro.json.")

if model_stats:
    c_model1, c_model2, c_model3 = st.columns(3)
    c_model1.metric("Modeling rows", f"{model_stats.get('modeling_rows', 0):,}")
    c_model2.metric("Removed general/noise", f"{model_stats.get('removed_general_noise', 0):,}")
    c_model3.metric("Min quality", str(model_stats.get("min_quality", "N/A")))
else:
    st.warning("Chưa có model_comment_corpus_stats_pro.json.")

with st.expander("Clean corpus report", expanded=False):
    st.markdown(clean_report_text if clean_report_text else "No clean corpus report.")

with st.expander("Modeling corpus report", expanded=False):
    st.markdown(model_report_text if model_report_text else "No modeling corpus report.")

# BERTopic Pro metrics
st.divider()
st.markdown("### BERTopic Pro Model Metrics")

if pro_metrics:
    m1, m2, m3, m4, m5 = st.columns(5)

    outlier_ratio = pro_metrics.get("outlier_ratio", 0)
    silhouette = pro_metrics.get("silhouette_score", 0)

    m1.metric("Clean comments", f"{pro_metrics.get('raw_comments_after_cleaning', 0):,}")
    m2.metric("Clusters", f"{pro_metrics.get('bertopic_topic_count_excluding_outliers', 0):,}")
    m3.metric("Outliers", f"{pro_metrics.get('outlier_count', 0):,}")
    m4.metric("Outlier ratio", f"{float(outlier_ratio) * 100:.2f}%")
    m5.metric("Silhouette", f"{float(silhouette):.3f}")

    st.caption(
        "Đây là metric nội tại của topic modeling không giám sát. "
        "Không gọi đây là accuracy vì chưa có bộ nhãn người gán. "
        "Silhouette càng cao càng tốt; outlier ratio càng thấp càng tốt."
    )

    if not pro_quality_df.empty:
        fig_micro = px.bar(
            pro_quality_df.sort_values("topic_reliability_score", ascending=False).head(30),
            x="bertopic_label",
            y="topic_reliability_score",
            color="decision_confidence",
            title="Top BERTopic micro-cluster reliability",
        )
        st.plotly_chart(fig_micro, use_container_width=True)

        with st.expander("BERTopic Pro micro-topic quality table", expanded=False):
            st.dataframe(pro_quality_df, use_container_width=True)

    with st.expander("BERTopic Pro summary", expanded=False):
        st.markdown(pro_summary_text if pro_summary_text else "No BERTopic Pro summary.")
else:
    st.warning("Chưa có comment_topic_model_metrics_pro.json.")

# Business Decision v3
st.divider()
st.markdown("### Business Decision v3 Panel")

if not business_v3_df.empty:
    b1, b2, b3, b4 = st.columns(4)

    high_count = int((business_v3_df["decision_confidence"] == "high").sum())
    medium_count = int((business_v3_df["decision_confidence"] == "medium").sum())
    low_count = int((business_v3_df["decision_confidence"] == "low").sum())
    avg_score = float(business_v3_df["business_reliability_score"].mean())

    b1.metric("High-confidence", f"{high_count:,}")
    b2.metric("Medium-confidence", f"{medium_count:,}")
    b3.metric("Low-confidence", f"{low_count:,}")
    b4.metric("Avg business reliability", f"{avg_score:.2f}")

    if high_count == 0:
        st.warning(
            "Hiện chưa có business topic high-confidence. "
            "Các nhóm medium-confidence nên dùng làm tín hiệu định hướng và cần human review trước khi ra quyết định lớn."
        )

    st.caption(
        "Business Decision v3 là tầng quản trị chính: hệ thống không dùng micro-cluster làm kết luận trực tiếp, "
        "mà gom comment vào taxonomy nghiệp vụ như chất lượng sản phẩm, khuyến mãi, chi nhánh, nội dung, giao hàng, app/thanh toán và dịch vụ."
    )

    fig_business = px.bar(
        business_v3_df.sort_values("business_reliability_score", ascending=False),
        x="business_topic",
        y="business_reliability_score",
        color="decision_confidence",
        title="Business topic reliability score",
    )
    st.plotly_chart(fig_business, use_container_width=True)

    st.markdown("#### Business topics for management review")

    display_cols = [
        "business_topic",
        "comment_count",
        "phuc_long_ratio",
        "business_reliability_score",
        "decision_confidence",
        "management_usefulness",
        "owner",
        "kpi",
        "keywords",
    ]
    display_cols = [col for col in display_cols if col in business_v3_df.columns]

    st.dataframe(
        business_v3_df[display_cols].sort_values("business_reliability_score", ascending=False),
        use_container_width=True,
    )

    st.markdown("#### Representative comments by business topic")

    if not business_reps_v3_df.empty:
        topic_choice = st.selectbox(
            "Chọn business topic để xem comment đại diện",
            business_v3_df["business_topic"].tolist(),
        )

        reps_view = business_reps_v3_df[
            business_reps_v3_df["business_topic"].astype(str).eq(str(topic_choice))
        ].sort_values("rank")

        st.dataframe(reps_view, use_container_width=True)
    else:
        st.info("Chưa có representative comments v3.")

    if business_summary_v3_text:
        with st.expander("Business Decision v3 academic summary", expanded=False):
            st.markdown(business_summary_v3_text)
else:
    st.warning(
        "Chưa có Business Decision v3 output. "
        "Hãy chạy: python3 mvp_ai_bi_phuclong/graph_rag/aggregate_graphrag_business_v3.py"
    )

# Graph visualization
st.divider()
st.markdown("### Interactive Business Decision Graph v3")

st.caption(
    "Graph này ưu tiên hiển thị tầng Business Decision v3 để tránh hairball. "
    "Mỗi business topic được nối với confidence, owner, risk, platform và Phúc Long focus. "
    "Graph micro-topic BERTopic vẫn được giữ làm fallback nhưng không dùng làm tầng ra quyết định chính."
)

graph_to_show = (
    business_graph_v3_html
    if business_graph_v3_html.exists()
    else pro_graph_html
    if pro_graph_html.exists()
    else graph_html
)

if graph_to_show.exists():
    components.html(graph_to_show.read_text(encoding="utf-8"), height=780, scrolling=True)
else:
    st.warning("Chưa có graph HTML output.")

with st.expander("Business Decision Graph v3 node/edge data", expanded=False):
    if not business_graph_nodes_v3_df.empty:
        st.markdown("#### Nodes")
        st.dataframe(business_graph_nodes_v3_df, use_container_width=True)
    else:
        st.info("Chưa có comment_business_decision_nodes_v3.csv.")

    if not business_graph_edges_v3_df.empty:
        st.markdown("#### Edges")
        st.dataframe(business_graph_edges_v3_df, use_container_width=True)
    else:
        st.info("Chưa có comment_business_decision_edges_v3.csv.")

    if business_graph_summary_v3_text:
        st.markdown("#### Graph Summary")
        st.markdown(business_graph_summary_v3_text)

# Legacy/pro topic tables
st.divider()
st.markdown("### Topic Tables")

tab_pro, tab_legacy = st.tabs(["BERTopic Pro topics", "Legacy graph topics"])

with tab_pro:
    if not pro_topics_df.empty:
        st.dataframe(pro_topics_df, use_container_width=True)
    else:
        st.info("Chưa có comment_topics_pro.csv.")

with tab_legacy:
    if not topics_df.empty:
        st.dataframe(topics_df.sort_values("comment_count", ascending=False), use_container_width=True)
    else:
        st.info("Chưa có legacy comment_topics.csv.")

# AI Agent
st.divider()
st.markdown("### AI GraphRAG Marketing Insight Agent")

st.caption(
    "AI Agent đọc Clean Corpus, BERTopic Pro metrics, Business Decision v3, representative comments "
    "và graph context để tạo insight quản trị có confidence guardrail."
)

default_question = (
    "Dựa trên Business Decision v3, hãy phân tích các nhóm chủ đề khách hàng có ý nghĩa quản trị nhất cho Phúc Long. "
    "Nhóm nào nên ưu tiên cho content marketing, nhóm nào cần CSKH/vận hành theo dõi? "
    "Chỉ dùng topic medium trở lên làm tín hiệu chính, low chỉ nêu là cần theo dõi thêm. "
    "Trả lời kèm confidence, owner và KPI."
)

graph_question = st.text_area(
    "Hỏi AI về Comment GraphRAG Pro",
    value=default_question,
    height=130,
)

col_ai1, col_ai2 = st.columns(2)

with col_ai1:
    if st.button("Generate Business Decision Insight", use_container_width=True):
        with st.spinner("AI đang đọc Business Decision v3 và tạo insight quản trị..."):
            graph_context = build_graph_ai_context(
                question=graph_question,
                topics_df=topics_df,
                nodes_df=nodes_df,
                edges_df=edges_df,
                summary_text=summary_text,
                pro_quality_df=pro_quality_df,
                pro_metrics=pro_metrics,
                business_v3_df=business_v3_df,
                business_reps_v3_df=business_reps_v3_df,
                clean_stats=clean_stats,
                model_stats=model_stats,
            )
            answer = call_ai(
                [
                    {"role": "system", "content": GRAPH_SYSTEM_PROMPT},
                    {"role": "user", "content": graph_context + "\n\nCâu hỏi: " + graph_question},
                ],
                temperature=0.2,
                max_tokens=4200,
            )
        render_ai_answer(answer, "graphrag_business_decision_insight")

with col_ai2:
    if st.button("Ask Strategy from GraphRAG Pro", use_container_width=True):
        with st.spinner("AI đang tạo khuyến nghị chiến lược từ GraphRAG Pro..."):
            graph_context = build_graph_ai_context(
                question=graph_question,
                topics_df=topics_df,
                nodes_df=nodes_df,
                edges_df=edges_df,
                summary_text=summary_text,
                pro_quality_df=pro_quality_df,
                pro_metrics=pro_metrics,
                business_v3_df=business_v3_df,
                business_reps_v3_df=business_reps_v3_df,
                clean_stats=clean_stats,
                model_stats=model_stats,
            )
            answer = call_ai(
                [
                    {"role": "system", "content": GRAPH_SYSTEM_PROMPT},
                    {"role": "user", "content": graph_context + "\n\nYêu cầu chiến lược: " + graph_question},
                ],
                temperature=0.2,
                max_tokens=4200,
            )
        render_ai_answer(answer, "graphrag_pro_strategy_chat")