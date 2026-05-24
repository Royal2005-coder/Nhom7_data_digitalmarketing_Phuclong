#!/usr/bin/env python3
"""
V3 TikTok Comments — curl_cffi + msToken from CloakBrowser
Reads video_ids from SQLite (imported from CSV), NOT from scroll.
"""
import json, time, random, re, argparse
from datetime import datetime
from curl_cffi import requests as cffi_requests
from v3_config import *

IMPERSONATE_TARGETS = ["chrome", "chrome110", "chrome116", "chrome120", "safari"]

HEADERS_BASE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8",
    "Referer": "https://www.tiktok.com/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
}


def build_cookie_header(cookies_list):
    if not cookies_list:
        return ""
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies_list
                     if c.get("domain", "").endswith("tiktok.com"))


def get_videos_needing_comments(conn, brand, top_n=200):
    """Get videos from SQLite that need more comments."""
    cur = conn.execute("""
        SELECT tv.video_id, tv.video_url, tv.comments_count,
               COALESCE(tc.cnt, 0) as existing
        FROM tiktok_videos tv
        LEFT JOIN (
            SELECT video_id, COUNT(*) as cnt
            FROM tiktok_comments WHERE brand = ?
            GROUP BY video_id
        ) tc ON tv.video_id = tc.video_id
        WHERE tv.brand = ?
          AND CAST(COALESCE(tv.comments_count, 0) AS INTEGER) > 2
        ORDER BY
            CASE WHEN COALESCE(tc.cnt, 0) = 0 THEN 0 ELSE 1 END,
            (CAST(COALESCE(tv.comments_count,0) AS INTEGER) - COALESCE(tc.cnt, 0)) DESC
        LIMIT ?
    """, (brand, brand, top_n))
    return cur.fetchall()


def crawl_comments_api(video_id, brand, tokens, max_comments=200):
    """curl_cffi → TikTok comment API with harvested msToken."""
    comments = []
    seen = set()
    cursor = 0
    imp_idx = random.randint(0, len(IMPERSONATE_TARGETS) - 1)

    headers = HEADERS_BASE.copy()
    cookie_str = build_cookie_header(tokens.get("cookies", []))
    if cookie_str:
        headers["Cookie"] = cookie_str

    ms_token = tokens.get("ms_token", "")

    for page_num in range(12):
        if len(comments) >= max_comments:
            break

        imp = IMPERSONATE_TARGETS[imp_idx % len(IMPERSONATE_TARGETS)]
        imp_idx += 1

        params = {
            "aweme_id": str(video_id),
            "count": "50",
            "cursor": str(cursor),
            "aid": "1988",
            "app_language": "vi-VN",
            "app_name": "tiktok_web",
        }
        if ms_token:
            params["msToken"] = ms_token

        try:
            resp = cffi_requests.get(
                "https://www.tiktok.com/api/comment/list/",
                params=params, headers=headers,
                impersonate=imp, timeout=15,
            )

            if resp.status_code == 403:
                return comments, "blocked"
            if resp.status_code != 200:
                # Retry with different impersonation
                for alt in IMPERSONATE_TARGETS:
                    if alt == imp:
                        continue
                    try:
                        resp = cffi_requests.get(
                            "https://www.tiktok.com/api/comment/list/",
                            params=params, headers=headers,
                            impersonate=alt, timeout=15)
                        if resp.status_code == 200:
                            break
                    except:
                        continue
                if resp.status_code != 200:
                    return comments, "error"

            data = resp.json()

            if data.get("type") == "verify" or data.get("statusCode") == 10000:
                return comments, "captcha"

            cmt_list = data.get("comments", [])
            if not cmt_list:
                break

            for item in cmt_list:
                txt = item.get("text", "") or ""
                if len(txt.strip()) < 2:
                    continue

                cid = str(item.get("cid", item.get("id", "")))
                if not cid or cid in seen:
                    continue
                seen.add(cid)

                ct = None
                ts = item.get("create_time")
                if ts and isinstance(ts, (int, float)):
                    try:
                        ct = datetime.fromtimestamp(int(ts)).isoformat()
                    except:
                        pass

                user = item.get("user", {}) or {}
                usr = user.get("unique_id", user.get("nickname", "")) or ""

                comments.append((
                    cid, str(video_id), brand, txt[:2000],
                    int(item.get("digg_count", 0) or 0),
                    int(item.get("reply_comment_total", 0) or 0),
                    ct, usr[:100]
                ))

            has_more = data.get("has_more", 0)
            cursor = data.get("cursor", cursor + 50)
            if not has_more:
                break

        except Exception as e:
            if "timeout" in str(e).lower():
                return comments, "timeout"
            return comments, "error"

        time.sleep(random.uniform(0.5, 1.5))

    return comments, "ok"


def insert_comments(conn, comments):
    """Insert comments with dedup."""
    n = 0
    for c in comments:
        try:
            conn.execute("""
                INSERT OR IGNORE INTO tiktok_comments
                (comment_id, video_id, brand, comment_text,
                 like_count, reply_count, create_time, user_nickname)
                VALUES (?,?,?,?,?,?,?,?)
            """, c)
            n += 1
        except:
            pass
    conn.commit()
    return n


def main():
    parser = argparse.ArgumentParser(description="V3 TikTok Comments")
    parser.add_argument("--brands", nargs="+", choices=BRANDS + ["all"], default=["all"])
    parser.add_argument("--top-n", type=int, default=200)
    parser.add_argument("--max-cmt", type=int, default=200)
    parser.add_argument("--harvest-first", action="store_true")
    args = parser.parse_args()

    brands = BRANDS if "all" in args.brands else [b for b in args.brands if b in BRANDS]

    print("=" * 70)
    print("  V3 TikTok Comments — curl_cffi + msToken")
    print(f"  Brands: {brands} | Top-N: {args.top_n} | Max cmt: {args.max_cmt}")
    print("=" * 70)

    # Load or harvest tokens
    from v3_token_harvester import load_tokens, harvest_all
    tokens_data = load_tokens()
    if not tokens_data or args.harvest_first:
        print("\n  Harvesting fresh tokens...")
        tokens_data = harvest_all()

    conn = get_conn()
    print_status(conn)

    grand_total = 0
    api_ok = 0
    api_try = 0

    for brand in brands:
        print(f"\n{'─'*70}")
        print(f"  [{brand}] TikTok Comments")
        print(f"{'─'*70}")

        brand_tokens = tokens_data.get(brand, {})
        if not brand_tokens.get("ms_token"):
            print(f"  ⚠ No msToken for {brand}. Skipping.")
            continue

        videos = get_videos_needing_comments(conn, brand, args.top_n)
        print(f"  Videos to crawl: {len(videos)}")

        brand_new = 0
        consecutive_fail = 0

        for idx, (vid, vurl, expected, existing) in enumerate(videos):
            expected = int(expected or 0)
            existing = int(existing or 0)
            gap = expected - existing
            if gap <= 0:
                continue

            api_try += 1
            comments, status = crawl_comments_api(vid, brand, brand_tokens, args.max_cmt)

            if status in ("blocked", "captcha"):
                consecutive_fail += 1
                if consecutive_fail >= 5:
                    print(f"    ⚠ API blocked after {idx+1} videos. Stopping {brand}.")
                    break
            elif status == "ok" and comments:
                consecutive_fail = 0
                api_ok += 1

            if comments:
                n = insert_comments(conn, comments)
                brand_new += n
                grand_total += n
                print(f"    [{idx+1}/{len(videos)}] {vid[:18]}: +{n} new "
                      f"({len(comments)} got, had={existing}, ~{expected}) [{status}]")
            else:
                if consecutive_fail <= 3:
                    print(f"    [{idx+1}/{len(videos)}] {vid[:18]}: 0 [{status}]")

            time.sleep(adaptive_delay(api_ok / max(api_try, 1)))

            # Check target
            cur = conn.execute(
                "SELECT COUNT(*) FROM tiktok_comments WHERE brand = ?", (brand,))
            current = cur.fetchone()[0]
            if current >= TARGET_COMMENTS_PER_BRAND:
                print(f"    ✓ Target reached! {current:,} >= {TARGET_COMMENTS_PER_BRAND:,}")
                break

        print(f"  [{brand}] Session: +{brand_new:,}")

    print_status(conn)
    print(f"\n  SESSION: +{grand_total:,} | API: {api_ok}/{api_try}")

    # Auto-export CSVs
    print("\n  Exporting CSVs...")
    export_csvs(conn)
    conn.close()


if __name__ == "__main__":
    main()