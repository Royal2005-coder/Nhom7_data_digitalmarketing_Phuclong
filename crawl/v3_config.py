#!/usr/bin/env python3
"""
V3 Config — SQLite backend (ZERO CONFIG, no Docker needed)
Auto-imports existing CSVs on first run.
"""
import sqlite3, time, random, re, os, csv
from datetime import datetime
from pathlib import Path

# ─── PATHS ─────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
PROJECT_DIR = BASE_DIR.parent
DB_PATH = PROJECT_DIR / "data" / "social_listening.db"
CSV_DIR = PROJECT_DIR / "data" / "raw"
CLEAN_DIR = PROJECT_DIR / "data" / "clean"
PROFILE_DIR = BASE_DIR / ".profiles"
COOKIE_DIR = BASE_DIR / ".cookies"
TOKEN_FILE = BASE_DIR / ".tokens" / "tiktok_tokens.json"
STATE_FILE = COOKIE_DIR / "fb_state.json"

for d in [PROFILE_DIR, COOKIE_DIR, BASE_DIR / ".tokens",
          PROJECT_DIR / "data", CSV_DIR, CLEAN_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ─── BRANDS ────────────────────────────────────────────────
BRANDS = ["phuc_long", "highlands", "katinat"]

TIKTOK_PROFILES = {
    "phuc_long":  "https://www.tiktok.com/@phuclongofficial",
    "highlands":  "https://www.tiktok.com/@highlandscoffeevietnam",
    "katinat":    "https://www.tiktok.com/@katinatvn",
}

FACEBOOK_PAGES = {
    "phuc_long":  "https://www.facebook.com/PhuclongCoffeeandTea",
    "highlands":  "https://www.facebook.com/highlandscoffeevietnam",
    "katinat":    "https://www.facebook.com/katinat.vn",
}

# ─── TARGETS ───────────────────────────────────────────────
TARGET_VIDEOS_PER_BRAND = 500
TARGET_COMMENTS_PER_BRAND = 12000
TARGET_POSTS_PER_BRAND = 500

# ─── SQLite SCHEMA ─────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS tiktok_videos (
    video_id TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    author_name TEXT,
    views_count INTEGER DEFAULT 0,
    likes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    shares_count INTEGER DEFAULT 0,
    collect_count INTEGER DEFAULT 0,
    duration_seconds INTEGER DEFAULT 0,
    publish_time TEXT,
    video_desc TEXT,
    music_used TEXT,
    hashtags TEXT,
    video_url TEXT,
    crawl_source TEXT DEFAULT 'csv_import'
);

CREATE TABLE IF NOT EXISTS tiktok_comments (
    comment_id TEXT PRIMARY KEY,
    video_id TEXT,
    brand TEXT NOT NULL,
    comment_text TEXT,
    like_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    create_time TEXT,
    user_nickname TEXT
);

CREATE TABLE IF NOT EXISTS facebook_posts (
    post_id TEXT PRIMARY KEY,
    brand TEXT NOT NULL,
    post_text TEXT,
    post_type TEXT,
    publish_time TEXT,
    likes_count INTEGER DEFAULT 0,
    shares_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    reactions_breakdown TEXT,
    hashtags TEXT,
    post_url TEXT,
    crawl_source TEXT DEFAULT 'csv_import'
);

CREATE TABLE IF NOT EXISTS facebook_comments (
    comment_id TEXT PRIMARY KEY,
    post_id TEXT,
    brand TEXT NOT NULL,
    comment_text TEXT,
    like_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    create_time TEXT,
    user_name TEXT
);

CREATE INDEX IF NOT EXISTS idx_tt_cmt_brand ON tiktok_comments(brand);
CREATE INDEX IF NOT EXISTS idx_tt_cmt_video ON tiktok_comments(video_id);
CREATE INDEX IF NOT EXISTS idx_fb_cmt_brand ON facebook_comments(brand);
CREATE INDEX IF NOT EXISTS idx_fb_cmt_post ON facebook_comments(post_id);
CREATE INDEX IF NOT EXISTS idx_tt_vid_brand ON tiktok_videos(brand);
CREATE INDEX IF NOT EXISTS idx_fb_post_brand ON facebook_posts(brand);
"""


def get_conn():
    """Get SQLite connection (auto-creates DB + imports CSVs on first run)."""
    first_run = not DB_PATH.exists()
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(SCHEMA)

    if first_run:
        print("  ⚡ First run — importing existing CSVs into SQLite...")
        _import_csvs(conn)

    return conn


def _import_csvs(conn):
    """Import existing CSV files into SQLite."""
    mappings = [
        ("tiktok_videos.csv", "tiktok_videos",
         ["video_id", "brand", "author_name", "views_count", "likes_count",
          "comments_count", "shares_count", "collect_count", "duration_seconds",
          "publish_time", "video_desc", "music_used", "hashtags", "video_url", "crawl_source"]),
        ("tiktok_comments.csv", "tiktok_comments",
         ["comment_id", "video_id", "brand", "comment_text", "like_count",
          "reply_count", "create_time", "user_nickname"]),
        ("facebook_posts.csv", "facebook_posts",
         ["post_id", "brand", "post_text", "post_type", "publish_time",
          "likes_count", "shares_count", "comments_count", "reactions_breakdown",
          "hashtags", "post_url", "crawl_source"]),
        ("facebook_comments.csv", "facebook_comments",
         ["comment_id", "post_id", "brand", "comment_text", "like_count",
          "reply_count", "create_time", "user_name"]),
    ]

    for csv_name, table, expected_cols in mappings:
        # Try raw first, then clean
        csv_path = CSV_DIR / csv_name
        if not csv_path.exists():
            csv_path = CLEAN_DIR / csv_name
        if not csv_path.exists():
            print(f"    ⚠ {csv_name} not found, skipping")
            continue

        try:
            # Auto-detect encoding
            for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252"]:
                try:
                    with open(csv_path, "r", encoding=enc) as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
            else:
                print(f"    ✗ {csv_name}: encoding error")
                continue

            if not rows:
                print(f"    ⚠ {csv_name}: empty")
                continue

            # Map CSV columns to DB columns
            csv_cols = list(rows[0].keys())
            # Find matching columns
            col_map = {}
            for ec in expected_cols:
                for cc in csv_cols:
                    if cc.lower().strip() == ec.lower().strip():
                        col_map[ec] = cc
                        break

            if not col_map:
                print(f"    ✗ {csv_name}: no matching columns")
                continue

            db_cols = list(col_map.keys())
            placeholders = ",".join(["?"] * len(db_cols))
            cols_str = ",".join(db_cols)

            n = 0
            for row in rows:
                vals = []
                for dc in db_cols:
                    v = row.get(col_map[dc], "")
                    if v == "" or v is None:
                        vals.append(None)
                    else:
                        vals.append(str(v).strip())
                try:
                    conn.execute(
                        f"INSERT OR IGNORE INTO {table} ({cols_str}) VALUES ({placeholders})",
                        vals)
                    n += 1
                except:
                    pass

            conn.commit()
            print(f"    ✓ {csv_name}: {n} rows imported into {table}")

        except Exception as e:
            print(f"    ✗ {csv_name}: {e}")


def get_status(conn):
    """Return dict of {(platform, brand): count}."""
    status = {}
    for table, platform in [
        ("tiktok_videos", "tt_vid"),
        ("tiktok_comments", "tt_cmt"),
        ("facebook_posts", "fb_post"),
        ("facebook_comments", "fb_cmt"),
    ]:
        try:
            cur = conn.execute(f"SELECT brand, COUNT(*) FROM {table} GROUP BY brand")
            for brand, cnt in cur.fetchall():
                status[(platform, brand)] = cnt
        except:
            pass
    return status


def print_status(conn):
    """Pretty-print current data status vs targets."""
    status = get_status(conn)
    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    print(f"\n{'='*70}")
    print(f"  DATA STATUS — {now}")
    print(f"{'='*70}")
    print(f"  {'Brand':12} | {'TT Vid':>8} | {'TT Cmt':>8} | {'FB Post':>8} | {'FB Cmt':>8} | {'Total Cmt':>9}")
    print(f"  {'-'*12}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*9}")
    total_all = 0
    for brand in BRANDS:
        tv = status.get(("tt_vid", brand), 0)
        tc = status.get(("tt_cmt", brand), 0)
        fp = status.get(("fb_post", brand), 0)
        fc = status.get(("fb_cmt", brand), 0)
        total_cmt = tc + fc
        total_all += tv + tc + fp + fc
        print(f"  {brand:12} | {tv:>8,} | {tc:>8,} | {fp:>8,} | {fc:>8,} | {total_cmt:>9,}")
    print(f"  {'-'*12}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*8}-+-{'-'*9}")
    print(f"  {'TARGET':12} | {TARGET_VIDEOS_PER_BRAND:>8,} | {TARGET_COMMENTS_PER_BRAND:>8,} | "
          f"{TARGET_POSTS_PER_BRAND:>8,} | {TARGET_COMMENTS_PER_BRAND:>8,} |")
    print(f"  {'TOTAL':12} | {total_all:>8,} records")
    print(f"{'='*70}\n")
    return status


def export_csvs(conn):
    """Export all tables back to CSV."""
    tables = {
        "tiktok_videos": CSV_DIR / "tiktok_videos.csv",
        "tiktok_comments": CSV_DIR / "tiktok_comments.csv",
        "facebook_posts": CSV_DIR / "facebook_posts.csv",
        "facebook_comments": CSV_DIR / "facebook_comments.csv",
    }
    for table, path in tables.items():
        cur = conn.execute(f"SELECT * FROM {table}")
        cols = [d[0] for d in cur.description]
        rows = cur.fetchall()
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(cols)
            writer.writerows(rows)
        print(f"  ✓ {path.name}: {len(rows)} rows")


def adaptive_delay(success_rate, base_min=1.5, base_max=4.0):
    if success_rate < 0.3:
        return random.uniform(base_max * 2, base_max * 4)
    elif success_rate < 0.6:
        return random.uniform(base_max, base_max * 2)
    return random.uniform(base_min, base_max)


def extract_hashtags(text):
    if not text:
        return ""
    tags = re.findall(r'#([\w\u00C0-\u024F\u1E00-\u1EFF]+)', text, re.UNICODE)
    return ",".join(tags[:50])


def safe_close_context(ctx):
    """Close CloakBrowser context safely (Windows bug workaround)."""
    try:
        ctx.close()
    except Exception:
        pass  # Known CloakBrowser 0.3.30 Windows close bug — harmless


# ─── QUICK TEST ────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 70)
    print("  V3 Config — SQLite Backend")
    print(f"  DB: {DB_PATH}")
    print("=" * 70)
    conn = get_conn()
    print_status(conn)
    conn.close()