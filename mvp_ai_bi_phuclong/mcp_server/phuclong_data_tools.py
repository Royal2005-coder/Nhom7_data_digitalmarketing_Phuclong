import json
import sqlite3
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "gold" / "phuclong_mvp.sqlite"
SEMANTIC_PATH = BASE_DIR / "docs" / "semantic_layer.md"
SKILL_PATH = BASE_DIR / "ai_agent" / "phuclong_ai_decision_skill.md"
PLAYBOOK_PATH = BASE_DIR / "docs" / "decision_playbook.md"


ALLOWED_TABLES = {
    "gold_competitor_benchmark",
    "gold_platform_performance",
    "gold_content_pillar_performance",
    "gold_sentiment_risk_monitoring",
    "gold_post_ranking",
    "gold_ai_action_recommendation",
    "gold_brand_overview_daily",
    "silver_social_posts",
    "silver_social_comments",
    "silver_social_unified",
}


def read_text_safe(path: Path) -> str:
    try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    except Exception:
        return ""
    return ""


def connect():
    return sqlite3.connect(DB_PATH)


def table_exists(table_name: str) -> bool:
    with connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchall()
    return len(rows) > 0


def sanitize_table(table_name: str) -> str:
    if table_name not in ALLOWED_TABLES:
        raise ValueError(f"Table not allowed: {table_name}")
    if not table_exists(table_name):
        raise ValueError(f"Table does not exist: {table_name}")
    return table_name


def df_to_records(df: pd.DataFrame, max_rows: int = 50):
    if df.empty:
        return []
    safe = df.head(max_rows).where(pd.notna(df), None)
    return safe.to_dict(orient="records")


def df_to_markdown(df: pd.DataFrame, max_rows: int = 30) -> str:
    if df.empty:
        return "No data"
    safe = df.head(max_rows).where(pd.notna(df), "N/A")
    try:
        return safe.to_markdown(index=False)
    except Exception:
        return safe.to_csv(index=False)


def list_gold_tables():
    with connect() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()

    tables = [r[0] for r in rows]
    return {
        "database": str(DB_PATH),
        "tables": tables,
        "allowed_tables": sorted(list(ALLOWED_TABLES)),
    }


def get_table_schema(table_name: str):
    table = sanitize_table(table_name)
    with connect() as conn:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()

    schema = [
        {
            "column_id": r[0],
            "name": r[1],
            "type": r[2],
            "notnull": r[3],
            "default": r[4],
            "pk": r[5],
        }
        for r in rows
    ]

    return {
        "table": table,
        "schema": schema,
    }


def query_gold_table(table_name: str, brand: str = None, platform: str = None, limit: int = 50):
    table = sanitize_table(table_name)
    limit = int(max(1, min(limit, 200)))

    query = f"SELECT * FROM {table}"
    params = []
    where = []

    if brand and brand != "All":
        where.append("brand = ?")
        params.append(brand)

    if platform and platform != "All":
        where.append("platform = ?")
        params.append(platform)

    if where:
        query += " WHERE " + " AND ".join(where)

    query += f" LIMIT {limit}"

    with connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    return {
        "table": table,
        "row_count": len(df),
        "markdown": df_to_markdown(df, limit),
        "records": df_to_records(df, limit),
    }


def get_platform_performance(brand: str = None, platform: str = None):
    return query_gold_table(
        "gold_platform_performance",
        brand=brand,
        platform=platform,
        limit=100,
    )


def get_competitor_benchmark(brand: str = None, platform: str = None):
    return query_gold_table(
        "gold_competitor_benchmark",
        brand=brand,
        platform=platform,
        limit=100,
    )


def get_content_pillar_performance(brand: str = None, platform: str = None):
    return query_gold_table(
        "gold_content_pillar_performance",
        brand=brand,
        platform=platform,
        limit=150,
    )


def get_sentiment_risk(brand: str = None, platform: str = None, top_n: int = 50):
    table = "gold_sentiment_risk_monitoring"
    top_n = int(max(1, min(top_n, 150)))

    query = f"SELECT * FROM {table}"
    params = []
    where = []

    if brand and brand != "All":
        where.append("brand = ?")
        params.append(brand)

    if platform and platform != "All":
        where.append("platform = ?")
        params.append(platform)

    if where:
        query += " WHERE " + " AND ".join(where)

    query += " ORDER BY risk_comment_count DESC, comment_count DESC"
    query += f" LIMIT {top_n}"

    with connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    return {
        "table": table,
        "row_count": len(df),
        "markdown": df_to_markdown(df, top_n),
        "records": df_to_records(df, top_n),
    }


def get_top_posts(brand: str = None, platform: str = None, top_n: int = 30, keyword: str = None):
    table = "gold_post_ranking"
    top_n = int(max(1, min(top_n, 100)))

    query = f"SELECT * FROM {table}"
    params = []
    where = []

    if brand and brand != "All":
        where.append("brand = ?")
        params.append(brand)

    if platform and platform != "All":
        where.append("platform = ?")
        params.append(platform)

    if keyword:
        where.append("LOWER(text) LIKE ?")
        params.append(f"%{keyword.lower()}%")

    if where:
        query += " WHERE " + " AND ".join(where)

    query += " ORDER BY rank_score DESC"
    query += f" LIMIT {top_n}"

    with connect() as conn:
        df = pd.read_sql_query(query, conn, params=params)

    keep_cols = [
        c for c in [
            "brand", "platform", "created_at", "time_slot", "content_pillar",
            "view_count", "engagement_total", "comment_count", "share_count",
            "sentiment_label", "rank_score", "text"
        ]
        if c in df.columns
    ]

    df = df[keep_cols]

    return {
        "table": table,
        "row_count": len(df),
        "markdown": df_to_markdown(df, top_n),
        "records": df_to_records(df, top_n),
    }


def get_ai_recommendations():
    return query_gold_table(
        "gold_ai_action_recommendation",
        limit=50,
    )


def get_semantic_context():
    semantic = read_text_safe(SEMANTIC_PATH)
    skill = read_text_safe(SKILL_PATH)
    playbook = read_text_safe(PLAYBOOK_PATH)

    return {
        "semantic_layer": semantic,
        "ai_decision_skill": skill,
        "decision_playbook": playbook,
    }


def generate_decision_context(brand: str = "phuc_long", platform: str = "All"):
    benchmark = get_competitor_benchmark(brand=None if brand == "All" else brand, platform=None if platform == "All" else platform)
    platform_perf = get_platform_performance(brand=None if brand == "All" else brand, platform=None if platform == "All" else platform)
    content = get_content_pillar_performance(brand=None if brand == "All" else brand, platform=None if platform == "All" else platform)
    risk = get_sentiment_risk(brand=None if brand == "All" else brand, platform=None if platform == "All" else platform, top_n=50)
    posts = get_top_posts(brand=None if brand == "All" else brand, platform=None if platform == "All" else platform, top_n=25)
    recs = get_ai_recommendations()
    semantic = get_semantic_context()

    text = []
    text.append("# MCP Decision Context")
    text.append("")
    text.append("## Semantic Layer")
    text.append(semantic.get("semantic_layer", ""))
    text.append("")
    text.append("## AI Decision Skill")
    text.append(semantic.get("ai_decision_skill", ""))
    text.append("")
    text.append("## Decision Playbook")
    text.append(semantic.get("decision_playbook", ""))
    text.append("")
    text.append("## Competitor Benchmark")
    text.append(benchmark["markdown"])
    text.append("")
    text.append("## Platform Performance")
    text.append(platform_perf["markdown"])
    text.append("")
    text.append("## Content Pillar Performance")
    text.append(content["markdown"])
    text.append("")
    text.append("## Sentiment Risk")
    text.append(risk["markdown"])
    text.append("")
    text.append("## Top Posts")
    text.append(posts["markdown"])
    text.append("")
    text.append("## AI Recommendations")
    text.append(recs["markdown"])

    return {
        "brand": brand,
        "platform": platform,
        "context_markdown": "\n".join(text),
    }


TOOLS = {
    "list_gold_tables": list_gold_tables,
    "get_table_schema": get_table_schema,
    "query_gold_table": query_gold_table,
    "get_platform_performance": get_platform_performance,
    "get_competitor_benchmark": get_competitor_benchmark,
    "get_content_pillar_performance": get_content_pillar_performance,
    "get_sentiment_risk": get_sentiment_risk,
    "get_top_posts": get_top_posts,
    "get_ai_recommendations": get_ai_recommendations,
    "get_semantic_context": get_semantic_context,
    "generate_decision_context": generate_decision_context,
}


def call_tool(tool_name: str, **kwargs):
    if tool_name not in TOOLS:
        raise ValueError(f"Unknown tool: {tool_name}")
    return TOOLS[tool_name](**kwargs)


if __name__ == "__main__":
    # Simple smoke test
    print(json.dumps(list_gold_tables(), ensure_ascii=False, indent=2))
