import os
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import requests
import streamlit as st
from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "gold" / "phuclong_mvp.sqlite"
ENV_PATH = BASE_DIR / "config" / ".env"

load_dotenv(ENV_PATH)

API_BASE = os.getenv("TOKENROUTER_API_BASE", "https://api.tokenrouter.com/v1").rstrip("/")
API_KEY = os.getenv("TOKENROUTER_API_KEY", "")
MODEL = os.getenv("TOKENROUTER_MODEL", "MiniMax-M3")


import sys
ROOT_DIR = BASE_DIR.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mvp_ai_bi_phuclong.mcp_server.phuclong_data_tools import (
    generate_decision_context,
    get_platform_performance,
    get_content_pillar_performance,
    get_sentiment_risk,
    get_top_posts,
)

st.set_page_config(
    page_title="Phúc Long AI-BI Decision Cockpit",
    page_icon="🍵",
    layout="wide",
)


@st.cache_data
def load_table(table_name: str) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    try:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    finally:
        conn.close()


def clean_dim(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    for col in ["brand", "platform", "content_pillar", "risk_group", "sentiment_label", "time_slot"]:
        if col in out.columns:
            out[col] = out[col].fillna("unknown").astype(str)
            out[col] = out[col].replace({
                "None": "unknown",
                "nan": "unknown",
                "NaT": "unknown",
                "": "unknown",
            })
    return out


def filter_df(df: pd.DataFrame, brand: str, platform: str) -> pd.DataFrame:
    out = clean_dim(df)
    if "brand" in out.columns and brand != "All":
        out = out[out["brand"] == brand]
    if "platform" in out.columns and platform != "All":
        out = out[out["platform"] == platform]
    return out


def show_df(df: pd.DataFrame):
    display = df.copy()
    display = display.replace([np.inf, -np.inf], np.nan)
    display = display.fillna("N/A")
    st.dataframe(display, use_container_width=True)


def fmt_num(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value):,.0f}"
    except Exception:
        return "N/A"


def fmt_pct(value):
    try:
        if pd.isna(value):
            return "N/A"
        return f"{float(value) * 100:.2f}%"
    except Exception:
        return "N/A"


def brand_label(value: str) -> str:
    mapping = {
        "phuc_long": "Phúc Long",
        "highlands": "Highlands",
        "katinat": "Katinat",
        "unknown": "Unknown",
        "All": "All",
    }
    return mapping.get(value, value)


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
        response = requests.post(url, headers=headers, json=payload, timeout=120)
        if response.status_code >= 400:
            return f"AI API error {response.status_code}: {response.text[:1800]}"
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"AI call failed: {exc}"


def clean_ai_output(text: str) -> str:
    """Remove hidden reasoning / think tags and normalize AI output for dashboard display."""
    if not text:
        return ""

    cleaned = str(text)

    # Remove XML-style or model-style thinking blocks
    cleaned = re.sub(r"<think>.*?</think>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"<thinking>.*?</thinking>", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"```thinking.*?```", "", cleaned, flags=re.DOTALL | re.IGNORECASE)
    cleaned = re.sub(r"```think.*?```", "", cleaned, flags=re.DOTALL | re.IGNORECASE)

    # Remove leading analysis markers if model leaks them
    cleaned = re.sub(r"^\s*(Analysis|Reasoning|Chain of thought)\s*:\s*", "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def render_ai_answer(answer: str, key_prefix: str):
    cleaned = clean_ai_output(answer)

    st.markdown(cleaned)

    st.download_button(
        label="Download AI brief (.md)",
        data=cleaned.encode("utf-8"),
        file_name=f"{key_prefix}_ai_brief.md",
        mime="text/markdown",
        use_container_width=True,
    )



def safe_markdown_table(df: pd.DataFrame, max_rows=30) -> str:
    if df.empty:
        return "No data"
    try:
        compact = df.head(max_rows).replace([np.inf, -np.inf], np.nan).fillna("N/A")
        return compact.to_markdown(index=False)
    except Exception:
        return df.head(max_rows).to_csv(index=False)


def build_ai_context(benchmark, platform_perf, pillar_perf, risk_monitor, post_ranking, ai_recs, brand_filter, platform_filter):
    b = filter_df(benchmark, brand_filter, platform_filter)
    p = filter_df(platform_perf, brand_filter, platform_filter)
    c = filter_df(pillar_perf, brand_filter, platform_filter)
    r = filter_df(risk_monitor, brand_filter, platform_filter)
    posts = filter_df(post_ranking, brand_filter, platform_filter)

    if "risk_comment_count" in r.columns:
        r = r.sort_values("risk_comment_count", ascending=False)

    if "rank_score" in posts.columns:
        posts = posts.sort_values("rank_score", ascending=False)

    context = []
    context.append("DATA CONTEXT: PHUC LONG SOCIAL LISTENING AI-BI MVP")
    context.append("")
    context.append("Business goal: hỗ trợ Phúc Long ra quyết định truyền thông số dựa trên dữ liệu Facebook, TikTok, comments, sentiment, risk và benchmark Highlands/Katinat.")
    context.append("Important note: Phúc Long là thương hiệu trọng tâm. Highlands và Katinat chỉ dùng làm benchmark cạnh tranh.")
    context.append("Important note: Facebook không có trường view_count trong dataset nên total_views/engagement_rate của Facebook có thể là N/A.")
    context.append("")
    context.append("[1] Competitor Benchmark")
    context.append(safe_markdown_table(b, 20))
    context.append("")
    context.append("[2] Platform Performance")
    context.append(safe_markdown_table(p, 20))
    context.append("")
    context.append("[3] Content Pillar Performance")
    context.append(safe_markdown_table(c, 30))
    context.append("")
    context.append("[4] Sentiment & Risk Monitoring")
    context.append(safe_markdown_table(r, 30))
    context.append("")
    context.append("[5] Top Posts/Videos")
    context.append(safe_markdown_table(posts[[
        col for col in ["brand", "platform", "created_at", "time_slot", "content_pillar",
                        "view_count", "engagement_total", "comment_count", "share_count",
                        "sentiment_label", "rank_score", "text"]
        if col in posts.columns
    ]], 20))
    context.append("")
    context.append("[6] Existing Rule-based Recommendations")
    context.append(safe_markdown_table(ai_recs, 20))

    return "\n".join(context)


def build_mcp_ai_context(brand_filter: str, platform_filter: str) -> str:
    """Build context via MCP-style local tool layer."""
    brand = "All" if brand_filter == "All" else brand_filter
    platform = "All" if platform_filter == "All" else platform_filter

    try:
        ctx = generate_decision_context(brand=brand, platform=platform)
        return ctx.get("context_markdown", "")
    except Exception as exc:
        return f"MCP context generation failed: {type(exc).__name__}: {exc}"




def get_system_prompt():
    return """
Bạn là Phúc Long AI-BI Decision Copilot, đóng vai trò data scientist và marketing strategist.

Nguyên tắc bắt buộc:
- Chỉ dùng dữ liệu được cung cấp trong DATA CONTEXT.
- Không bịa số liệu.
- Nếu dữ liệu thiếu, nói rõ dữ liệu thiếu.
- Phúc Long là thương hiệu trọng tâm; Highlands và Katinat chỉ là benchmark.
- Không lặp lại phân tích notebook; tập trung vào insight, quyết định và hành động.
- Viết tiếng Việt tự nhiên, rõ ràng, học thuật vừa đủ, tránh văn phong AI máy móc. Tuyệt đối không hiển thị chain-of-thought, không hiển thị thẻ <think>, không trình bày quá trình suy luận nội bộ; chỉ trình bày kết quả phân tích cuối cùng.

Cấu trúc trả lời:
1. Insight chính
2. Bằng chứng dữ liệu
3. Diễn giải nguyên nhân
4. Hành động đề xuất
5. Mức ưu tiên
6. Bộ phận phụ trách
7. Rủi ro cần theo dõi
"""


def run_agent(agent_name: str, agent_role: str, ai_context: str, task: str) -> str:
    system = f"""
Bạn là {agent_name}.
Vai trò: {agent_role}

Quy tắc:
- Chỉ dùng DATA CONTEXT.
- Không bịa số liệu.
- Không hiển thị chain-of-thought hoặc thẻ <think>.
- Phúc Long là trọng tâm; Highlands/Katinat chỉ là benchmark.
- Trả lời ngắn gọn nhưng có bằng chứng và hành động.
"""

    user = f"""
DATA CONTEXT:
{ai_context}

TASK:
{task}

Output format:
1. Finding
2. Evidence
3. Decision implication
4. Recommended action
5. Priority
"""

    return clean_ai_output(call_ai([
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ], temperature=0.15, max_tokens=1800))


def run_multi_agent_review(ai_context: str) -> dict:
    """A2A-ready multi-agent review. Sequential in MVP, can be wrapped into A2A agents later."""

    outputs = {}

    outputs["Insight Agent"] = run_agent(
        "Insight Agent",
        "Data scientist phụ trách đọc KPI, platform performance và benchmark để phát hiện insight chính.",
        ai_context,
        "Phân tích điểm mạnh/yếu chính của Phúc Long trên Facebook và TikTok. Không đề xuất lan man, chỉ nêu 3 insight quan trọng nhất."
    )

    outputs["Risk Agent"] = run_agent(
        "Risk Agent",
        "Brand safety analyst phụ trách sentiment, risk groups và cảnh báo vận hành.",
        ai_context,
        "Phân tích các nhóm rủi ro sentiment/vận hành quan trọng nhất của Phúc Long và đề xuất phản ứng ưu tiên."
    )

    outputs["Content Strategy Agent"] = run_agent(
        "Content Strategy Agent",
        "Marketing strategist phụ trách chuyển insight thành lịch nội dung và format triển khai.",
        ai_context,
        "Đề xuất chiến lược nội dung 7 ngày cho Phúc Long trên TikTok và Facebook dựa trên dữ liệu."
    )

    synthesis_context = "\n\n".join([f"[{k}]\n{v}" for k, v in outputs.items()])

    outputs["Executive Decision Agent"] = run_agent(
        "Executive Decision Agent",
        "Decision intelligence lead phụ trách tổng hợp ý kiến các agent thành quyết định quản trị cuối cùng.",
        ai_context + "\n\nMULTI-AGENT FINDINGS:\n" + synthesis_context,
        "Tổng hợp các phát hiện của Insight Agent, Risk Agent và Content Strategy Agent thành quyết định cuối cùng cho Phúc Long trong tuần tới."
    )

    return outputs




st.title("🍵 Phúc Long AI-BI Decision Cockpit")
st.caption("Data-driven social listening → BI insight → AI Copilot → quyết định truyền thông số.")

if not DB_PATH.exists():
    st.error(f"Không tìm thấy database: {DB_PATH}")
    st.stop()

benchmark = clean_dim(load_table("gold_competitor_benchmark"))
platform_perf = clean_dim(load_table("gold_platform_performance"))
pillar_perf = clean_dim(load_table("gold_content_pillar_performance"))
risk_monitor = clean_dim(load_table("gold_sentiment_risk_monitoring"))
post_ranking = clean_dim(load_table("gold_post_ranking"))
ai_recs = clean_dim(load_table("gold_ai_action_recommendation"))

with st.sidebar:
    st.header("Bộ lọc")

    brand_options = ["All"] + sorted(benchmark["brand"].dropna().unique().tolist())
    platform_options = ["All"] + sorted(benchmark["platform"].dropna().unique().tolist())

    brand_filter = st.selectbox("Thương hiệu", brand_options, format_func=brand_label)
    platform_filter = st.selectbox("Nền tảng", platform_options)

    st.divider()
    st.subheader("AI config")
    st.write("API base:", API_BASE)
    st.write("Model:", MODEL)
    st.write("API key:", "Configured" if API_KEY else "Missing")
    st.caption("Không commit file config/.env lên Git.")

filtered_benchmark = filter_df(benchmark, brand_filter, platform_filter)
filtered_platform = filter_df(platform_perf, brand_filter, platform_filter)
filtered_risk = filter_df(risk_monitor, brand_filter, platform_filter)

total_records = filtered_benchmark["total_records"].sum() if len(filtered_benchmark) else 0
total_engagement = filtered_benchmark["total_engagement"].sum() if len(filtered_benchmark) else 0

tiktok_platform = filtered_platform[filtered_platform["platform"].eq("tiktok")]
total_tiktok_views = tiktok_platform["total_views"].sum() if len(tiktok_platform) else 0

risk_count = filtered_benchmark["risk_count"].sum() if len(filtered_benchmark) and "risk_count" in filtered_benchmark.columns else 0
positive = filtered_benchmark["positive_count"].sum() if len(filtered_benchmark) else 0
negative = filtered_benchmark["negative_count"].sum() if len(filtered_benchmark) else 0
net_sentiment = (positive - negative) / total_records if total_records else np.nan

k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Tổng records", fmt_num(total_records))
k2.metric("Tổng engagement", fmt_num(total_engagement))
k3.metric("TikTok total views", fmt_num(total_tiktok_views))
k4.metric("Risk mentions", fmt_num(risk_count))
k5.metric("Net sentiment", fmt_pct(net_sentiment))

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Executive",
    "Platform",
    "Content",
    "Risk",
    "Top Posts",
    "AI Copilot",
])

with tab1:
    st.subheader("Executive Overview")

    if filtered_benchmark.empty:
        st.info("Không có dữ liệu theo bộ lọc.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                filtered_benchmark,
                x="brand",
                y="total_engagement",
                color="platform",
                barmode="group",
                title="Tổng engagement theo thương hiệu và nền tảng",
                labels={"brand": "Thương hiệu", "total_engagement": "Tổng engagement", "platform": "Nền tảng"},
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(
                filtered_benchmark,
                x="brand",
                y="net_sentiment_score",
                color="platform",
                barmode="group",
                title="Net sentiment score theo thương hiệu và nền tảng",
                labels={"brand": "Thương hiệu", "net_sentiment_score": "Net sentiment", "platform": "Nền tảng"},
            )
            st.plotly_chart(fig, use_container_width=True)

        st.markdown("### Bảng benchmark")
        show_df(filtered_benchmark)

with tab2:
    st.subheader("Platform Deep-dive")

    if filtered_platform.empty:
        st.info("Không có dữ liệu platform performance.")
    else:
        col1, col2 = st.columns(2)

        with col1:
            fig = px.bar(
                filtered_platform,
                x="brand",
                y="median_views",
                color="platform",
                barmode="group",
                title="Median views theo thương hiệu/nền tảng",
            )
            st.plotly_chart(fig, use_container_width=True)

        with col2:
            fig = px.bar(
                filtered_platform,
                x="brand",
                y="avg_engagement_rate",
                color="platform",
                barmode="group",
                title="Average engagement rate theo thương hiệu/nền tảng",
            )
            st.plotly_chart(fig, use_container_width=True)

        fig = px.scatter(
            filtered_platform,
            x="median_views",
            y="avg_engagement_rate",
            size="post_count",
            color="brand",
            symbol="platform",
            hover_data=["total_views", "total_comments", "total_shares"],
            title="Ma trận độ phủ và tỷ lệ tương tác",
        )
        st.plotly_chart(fig, use_container_width=True)

        show_df(filtered_platform)

with tab3:
    st.subheader("Content Intelligence")

    filtered_pillar = filter_df(pillar_perf, brand_filter, platform_filter)

    if filtered_pillar.empty:
        st.info("Không có dữ liệu content intelligence.")
    else:
        fig = px.bar(
            filtered_pillar,
            x="content_pillar",
            y="total_records",
            color="brand",
            facet_col="platform",
            title="Phân bổ trụ cột nội dung theo nền tảng",
        )
        st.plotly_chart(fig, use_container_width=True)

        fig = px.scatter(
            filtered_pillar,
            x="positive_count",
            y="negative_count",
            size="total_records",
            color="content_pillar",
            hover_data=["brand", "platform", "avg_sentiment_score"],
            title="Bản đồ cảm xúc theo trụ cột nội dung",
        )
        st.plotly_chart(fig, use_container_width=True)

        show_df(
            filtered_pillar.sort_values(["brand", "platform", "total_records"], ascending=[True, True, False])
        )

with tab4:
    st.subheader("Sentiment & Risk Monitoring")

    if filtered_risk.empty:
        st.info("Không có dữ liệu risk monitoring.")
    else:
        risk_rank = (
            filtered_risk
            .groupby(["brand", "platform", "risk_group"], as_index=False)
            .agg(
                comments=("comment_count", "sum"),
                risk_comments=("risk_comment_count", "sum"),
                avg_sentiment=("avg_sentiment_score", "mean"),
            )
            .sort_values("risk_comments", ascending=False)
        )

        fig = px.bar(
            risk_rank,
            x="risk_group",
            y="risk_comments",
            color="brand",
            facet_col="platform",
            title="Risk comments theo nhóm rủi ro",
        )
        st.plotly_chart(fig, use_container_width=True)

        sentiment = (
            filtered_risk
            .groupby(["brand", "platform", "sentiment_label"], as_index=False)
            .agg(comments=("comment_count", "sum"))
        )

        fig = px.bar(
            sentiment,
            x="sentiment_label",
            y="comments",
            color="brand",
            facet_col="platform",
            title="Phân bổ sentiment trong comments",
        )
        st.plotly_chart(fig, use_container_width=True)

        show_df(risk_rank)

with tab5:
    st.subheader("Top Posts / Videos Explorer")

    posts = filter_df(post_ranking, brand_filter, platform_filter)

    keyword = st.text_input("Tìm kiếm trong nội dung bài/video", value="")
    if keyword.strip() and "text" in posts.columns:
        posts = posts[posts["text"].astype(str).str.contains(keyword.strip(), case=False, na=False)]

    cols = [
        "brand", "platform", "created_at", "time_slot", "content_pillar",
        "view_count", "engagement_total", "comment_count", "share_count",
        "sentiment_label", "rank_score", "text"
    ]
    cols = [c for c in cols if c in posts.columns]

    if posts.empty:
        st.info("Không có dữ liệu top posts/videos.")
    else:
        fig = px.scatter(
            posts.head(100),
            x="view_count",
            y="engagement_total",
            color="brand",
            size="rank_score",
            symbol="platform",
            hover_data=["content_pillar", "sentiment_label"],
            title="Top posts/videos theo views và engagement",
        )
        st.plotly_chart(fig, use_container_width=True)

        show_df(posts[cols].head(80))

with tab6:
    st.subheader("AI Copilot: Data Scientist Insight Generator")

    st.markdown(
        "AI Copilot đọc các bảng Gold đã được tổng hợp, sau đó tạo insight, bằng chứng và khuyến nghị hành động. "
        "Phúc Long là trọng tâm; Highlands và Katinat chỉ dùng làm benchmark."
    )

    ai_context = build_mcp_ai_context(brand_filter, platform_filter)

    system_prompt = get_system_prompt()

    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("Generate Executive Brief", use_container_width=True):
            user_prompt = """
Hãy tạo executive brief cho dashboard hiện tại.
Tập trung vào Phúc Long.
So sánh Highlands và Katinat chỉ như benchmark.
Đề xuất hành động truyền thông số trong 7 ngày tới dựa trên dữ liệu.
"""
            with st.spinner("AI đang phân tích dashboard..."):
                answer = call_ai([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": ai_context + "\n\n" + user_prompt},
                ])
            render_ai_answer(answer, 'phuclong')

    with col2:
        if st.button("Generate 7-day Action Plan", use_container_width=True):
            user_prompt = """
Tạo kế hoạch hành động 7 ngày cho Phúc Long.
Mỗi ngày cần có: nền tảng ưu tiên, chủ đề nội dung, mục tiêu KPI, lý do từ dữ liệu, rủi ro cần theo dõi.
"""
            with st.spinner("AI đang tạo kế hoạch 7 ngày..."):
                answer = call_ai([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": ai_context + "\n\n" + user_prompt},
                ])
            render_ai_answer(answer, 'phuclong')

    with col3:
        if st.button("Generate Risk Response Plan", use_container_width=True):
            user_prompt = """
Tạo kế hoạch phản ứng rủi ro truyền thông cho Phúc Long dựa trên sentiment và risk groups.
Cần chia theo mức ưu tiên cao/trung bình/thấp và bộ phận phụ trách.
"""
            with st.spinner("AI đang tạo risk response plan..."):
                answer = call_ai([
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": ai_context + "\n\n" + user_prompt},
                ])
            render_ai_answer(answer, 'phuclong')

    st.divider()

    question = st.text_area(
        "Hỏi AI về dữ liệu",
        value="Phúc Long nên ưu tiên hành động gì trên TikTok và Facebook trong tuần tới?",
        height=120,
    )

    if st.button("Ask AI", use_container_width=True):
        with st.spinner("AI đang trả lời..."):
            answer = call_ai([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": ai_context + "\n\nCâu hỏi: " + question},
            ])
        render_ai_answer(answer, 'phuclong')

    st.divider()
    st.markdown("### MCP Tool Inspector")
    st.caption("Khu vực này mô phỏng MCP tool call: Streamlit gọi tool layer để truy vấn sâu Gold SQLite và semantic context.")

    tool_col1, tool_col2 = st.columns([1, 2])

    with tool_col1:
        selected_tool = st.selectbox(
            "Chọn MCP-style tool",
            [
                "get_platform_performance",
                "get_content_pillar_performance",
                "get_sentiment_risk",
                "get_top_posts",
            ],
        )
        tool_top_n = st.slider("Số dòng", min_value=5, max_value=50, value=15)

    with tool_col2:
        if st.button("Run selected MCP tool", use_container_width=True):
            try:
                if selected_tool == "get_platform_performance":
                    tool_result = get_platform_performance(
                        brand=None if brand_filter == "All" else brand_filter,
                        platform=None if platform_filter == "All" else platform_filter,
                    )
                elif selected_tool == "get_content_pillar_performance":
                    tool_result = get_content_pillar_performance(
                        brand=None if brand_filter == "All" else brand_filter,
                        platform=None if platform_filter == "All" else platform_filter,
                    )
                elif selected_tool == "get_sentiment_risk":
                    tool_result = get_sentiment_risk(
                        brand=None if brand_filter == "All" else brand_filter,
                        platform=None if platform_filter == "All" else platform_filter,
                        top_n=tool_top_n,
                    )
                else:
                    tool_result = get_top_posts(
                        brand=None if brand_filter == "All" else brand_filter,
                        platform=None if platform_filter == "All" else platform_filter,
                        top_n=tool_top_n,
                    )

                st.markdown(tool_result.get("markdown", "No output"))
            except Exception as exc:
                st.error(f"MCP tool failed: {type(exc).__name__}: {exc}")

    st.divider()
    st.markdown("### A2A-ready Multi-Agent Decision Review")
    st.caption("MVP mô phỏng phối hợp nhiều agent. Phase sau có thể bọc từng agent thành A2A server/card và dùng MCP để truy cập Gold database.")

    if st.button("Run Multi-Agent Decision Review", use_container_width=True):
        with st.spinner("Đang chạy Insight Agent, Risk Agent, Content Strategy Agent và Executive Decision Agent..."):
            agent_outputs = run_multi_agent_review(ai_context)

        for agent_name, output in agent_outputs.items():
            with st.expander(agent_name, expanded=(agent_name == "Executive Decision Agent")):
                st.markdown(output)

        combined = "\n\n".join([f"# {k}\n\n{v}" for k, v in agent_outputs.items()])
        st.download_button(
            label="Download multi-agent decision review (.md)",
            data=combined.encode("utf-8"),
            file_name="phuclong_multi_agent_decision_review.md",
            mime="text/markdown",
            use_container_width=True,
        )

    st.divider()
    st.markdown("### Rule-based recommendations từ Gold table")
    show_df(ai_recs)
