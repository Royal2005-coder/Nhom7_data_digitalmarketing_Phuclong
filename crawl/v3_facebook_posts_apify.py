#!/usr/bin/env python3
"""
V3 Facebook Posts — Apify Facebook Posts Scraper
Crawl 1000 posts/brand với FULL metadata chuẩn cho ML.
Dedup: post_id đã có → UPDATE metric nếu cao hơn, SKIP nếu không đổi.
"""
import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v3_config import *

try:
    from apify_client import ApifyClient
except ImportError:
    print("ERROR: pip install apify-client")
    sys.exit(1)


# Apify official actor
ACTOR_ID = "apify/facebook-posts-scraper"

FB_PAGES = {
    "phuc_long": "https://www.facebook.com/PhuclongCoffeeandTea",
    "highlands": "https://www.facebook.com/highlandscoffeevietnam",
    "katinat": "https://www.facebook.com/katinat.vn",
}


def parse_timestamp(raw):
    """Parse various timestamp formats → ISO string."""
    if not raw:
        return ""
    if isinstance(raw, (int, float)):
        try:
            return datetime.fromtimestamp(int(raw)).isoformat()
        except Exception:
            return ""
    s = str(raw).strip()
    # Already ISO
    if re.match(r"^\d{4}-\d{2}-\d{2}", s):
        return s
    # "2026-04-13T09:00:41.000Z"
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return s


def extract_hashtags(text):
    if not text:
        return ""
    tags = re.findall(r"#([\w\u00C0-\u024F\u1E00-\u1EFF]+)", str(text), re.UNICODE)
    return ",".join(tags[:50])


def detect_post_type(item):
    """Detect post type from Apify data."""
    ptype = str(item.get("type", "")).lower()
    if ptype:
        if "video" in ptype or "reel" in ptype:
            return "video"
        if "photo" in ptype or "image" in ptype:
            return "photo"
        if "link" in ptype:
            return "link"
        if "event" in ptype:
            return "event"
        return ptype

    # Fallback: check media
    media = item.get("media") or item.get("attachments") or []
    if isinstance(media, list) and media:
        first = media[0] if isinstance(media[0], dict) else {}
        if "video" in str(first).lower():
            return "video"
        if "photo" in str(first).lower() or "image" in str(first).lower():
            return "photo"

    url = str(item.get("url", "")).lower()
    if "/videos/" in url or "/reel/" in url:
        return "video"
    if "/photos/" in url:
        return "photo"

    return "text"


def crawl_apify(token, brand, max_posts=1000):
    """
    Gọi Apify Facebook Posts Scraper.
    Trả về list of dicts với FULL metadata.
    """
    client = ApifyClient(token)
    url = FB_PAGES[brand]

    print(f"\n  [{brand}] Apify crawl: {url}")
    print(f"    Actor: {ACTOR_ID}")
    print(f"    Max posts: {max_posts}")
    print(f"    Starting Apify run (may take 3-10 min)...")

    run_input = {
        "startUrls": [{"url": url}],
        "resultsLimit": max_posts,
    }

    try:
        run = client.actor(ACTOR_ID).call(run_input=run_input)
    except Exception as e:
        print(f"    ERROR running actor: {e}")
        return []

    print(f"    Run completed. Fetching results...")

    posts = []
    dataset = client.dataset(run["defaultDatasetId"])

    for item in dataset.iterate_items():
        # === POST ID ===
        pid = str(
            item.get("postId")
            or item.get("id")
            or item.get("facebookId")
            or ""
        ).strip()

        if not pid:
            # Fallback: extract from URL
            purl = item.get("url") or item.get("postUrl") or ""
            m = re.search(r"/posts/([A-Za-z0-9]+)", purl)
            if m:
                pid = m.group(1)
            else:
                m = re.search(r"story_fbid=(\d+)", purl)
                if m:
                    pid = m.group(1)
        if not pid:
            continue

        # === TEXT ===
        text = str(
            item.get("text")
            or item.get("message")
            or item.get("postText")
            or ""
        ).strip()[:2000]

        # === TIMESTAMP ===
        publish_time = parse_timestamp(
            item.get("time")
            or item.get("timestamp")
            or item.get("publishedAt")
            or item.get("date")
        )

        # === ENGAGEMENT ===
        likes = int(
            item.get("likes")
            or item.get("likesCount")
            or item.get("reactionCount")
            or item.get("reactionsCount")
            or 0
        )
        shares = int(
            item.get("shares")
            or item.get("sharesCount")
            or item.get("shareCount")
            or 0
        )
        comments = int(
            item.get("comments")
            or item.get("commentsCount")
            or item.get("commentCount")
            or 0
        )

        # === REACTIONS BREAKDOWN ===
        reactions = (
            item.get("reactionsBreakdown")
            or item.get("reactions")
            or item.get("reactionBreakdown")
        )
        reactions_json = ""
        if reactions:
            if isinstance(reactions, dict):
                reactions_json = json.dumps(reactions)
                # Nếu likes=0 nhưng có reactions → tính tổng
                if likes == 0:
                    likes = sum(int(v) for v in reactions.values() if isinstance(v, (int, float)))
            elif isinstance(reactions, str):
                reactions_json = reactions

        # === POST URL ===
        post_url = str(
            item.get("url")
            or item.get("postUrl")
            or item.get("link")
            or ""
        ).strip()

        # === POST TYPE ===
        post_type = detect_post_type(item)

        # === HASHTAGS ===
        hashtags_raw = item.get("hashtags") or []
        if isinstance(hashtags_raw, list):
            hashtags = ",".join(str(h).strip("#") for h in hashtags_raw[:50])
        else:
            hashtags = extract_hashtags(text)

        posts.append({
            "post_id": pid,
            "brand": brand,
            "post_text": text,
            "post_type": post_type,
            "publish_time": publish_time,
            "likes_count": likes,
            "shares_count": shares,
            "comments_count": comments,
            "reactions_breakdown": reactions_json,
            "hashtags": hashtags,
            "post_url": post_url,
            "crawl_source": "apify-v3",
        })

        if len(posts) % 100 == 0:
            print(f"    ... {len(posts)} posts parsed")

    print(f"    Total parsed: {len(posts)} posts")
    return posts


def upsert_posts(conn, posts):
    """
    Upsert 3 nhánh:
    - post_id chưa có → INSERT
    - post_id đã có + metric tăng hoặc field trống → UPDATE
    - post_id đã có + không đổi → SKIP
    """
    new = updated = skipped = 0

    for p in posts:
        row = conn.execute(
            """SELECT likes_count, shares_count, comments_count,
                      post_text, post_url, publish_time, reactions_breakdown
               FROM facebook_posts WHERE post_id=?""",
            (p["post_id"],),
        ).fetchone()

        if row:
            old_l = int(row[0] or 0)
            old_s = int(row[1] or 0)
            old_c = int(row[2] or 0)
            old_text = row[3] or ""
            old_url = row[4] or ""
            old_time = row[5] or ""
            old_reactions = row[6] or ""

            nl = max(old_l, p["likes_count"])
            ns = max(old_s, p["shares_count"])
            nc = max(old_c, p["comments_count"])

            fill_text = (not old_text or len(old_text) < 10) and p["post_text"]
            fill_url = (not old_url) and p["post_url"]
            fill_time = (not old_time) and p["publish_time"]
            fill_reactions = (not old_reactions) and p["reactions_breakdown"]

            changed = (
                nl != old_l or ns != old_s or nc != old_c
                or fill_text or fill_url or fill_time or fill_reactions
            )

            if changed:
                conn.execute(
                    """UPDATE facebook_posts SET
                        likes_count=?,
                        shares_count=?,
                        comments_count=?,
                        post_text=CASE WHEN post_text IS NULL OR LENGTH(post_text)<10 THEN ? ELSE post_text END,
                        post_url=CASE WHEN post_url IS NULL OR post_url='' THEN ? ELSE post_url END,
                        publish_time=CASE WHEN publish_time IS NULL OR publish_time='' THEN ? ELSE publish_time END,
                        reactions_breakdown=CASE WHEN reactions_breakdown IS NULL OR reactions_breakdown='' THEN ? ELSE reactions_breakdown END,
                        post_type=CASE WHEN post_type IS NULL OR post_type='' OR post_type='text' THEN ? ELSE post_type END,
                        hashtags=CASE WHEN hashtags IS NULL OR hashtags='' THEN ? ELSE hashtags END,
                        crawl_source=?
                    WHERE post_id=?""",
                    (nl, ns, nc,
                     p["post_text"], p["post_url"], p["publish_time"],
                     p["reactions_breakdown"], p["post_type"], p["hashtags"],
                     "apify-update", p["post_id"]),
                )
                updated += 1
            else:
                skipped += 1
        else:
            conn.execute(
                """INSERT OR IGNORE INTO facebook_posts
                    (post_id, brand, post_text, post_type, publish_time,
                     likes_count, shares_count, comments_count,
                     reactions_breakdown, hashtags, post_url, crawl_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p["post_id"], p["brand"], p["post_text"], p["post_type"],
                 p["publish_time"], p["likes_count"], p["shares_count"],
                 p["comments_count"], p["reactions_breakdown"], p["hashtags"],
                 p["post_url"], p["crawl_source"]),
            )
            new += 1

    conn.commit()
    return new, updated, skipped


def main():
    parser = argparse.ArgumentParser(description="V3 Facebook Posts — Apify Scraper")
    parser.add_argument("--token", required=True, help="Apify API token")
    parser.add_argument("--brands", nargs="+", choices=BRANDS + ["all"], default=["all"])
    parser.add_argument("--max-per-brand", type=int, default=1000)
    args = parser.parse_args()

    brands = BRANDS if "all" in args.brands else [b for b in args.brands if b in BRANDS]

    print("=" * 70)
    print("  V3 Facebook Posts — Apify Official Scraper")
    print(f"  Actor: {ACTOR_ID}")
    print(f"  Brands: {brands} | Max/brand: {args.max_per_brand}")
    print("  Full metadata: text, type, time, likes, shares, comments,")
    print("                 reactions, hashtags, url")
    print("  Dedup: INSERT new | UPDATE changed | SKIP identical")
    print("=" * 70)

    conn = get_conn()
    print_status(conn)

    gn = gu = gs = 0

    for brand in brands:
        before = conn.execute(
            "SELECT COUNT(*) FROM facebook_posts WHERE brand=?", (brand,)
        ).fetchone()[0]
        ml_before = conn.execute(
            """SELECT COUNT(*) FROM facebook_posts
               WHERE brand=? AND CAST(likes_count AS INTEGER)>0
               AND publish_time IS NOT NULL AND publish_time!=''""",
            (brand,)
        ).fetchone()[0]
        print(f"\n  [{brand}] Before: {before} total, {ml_before} ML-ready")

        posts = crawl_apify(args.token, brand, args.max_per_brand)

        if posts:
            n, u, s = upsert_posts(conn, posts)
            gn += n
            gu += u
            gs += s

            after = conn.execute(
                "SELECT COUNT(*) FROM facebook_posts WHERE brand=?", (brand,)
            ).fetchone()[0]
            ml_after = conn.execute(
                """SELECT COUNT(*) FROM facebook_posts
                   WHERE brand=? AND CAST(likes_count AS INTEGER)>0
                   AND publish_time IS NOT NULL AND publish_time!=''""",
                (brand,)
            ).fetchone()[0]

            print(f"  [{brand}] +{n} new, {u} updated, {s} skipped")
            print(f"  [{brand}] After: {after} total, {ml_after} ML-ready")
        else:
            print(f"  [{brand}] No posts returned from Apify")

        time.sleep(5)

    print_status(conn)
    print(f"\n  TOTAL: +{gn} new, {gu} updated, {gs} skipped")
    print("\n  Exporting CSVs...")
    export_csvs(conn)
    conn.close()


if __name__ == "__main__":
    main()