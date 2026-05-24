import json, subprocess, sys, argparse, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from v3_config import *

def crawl_videos_ytdlp(brand, max_videos=250):
    """yt-dlp --dump-json to extract ALL video metadata from TikTok profile."""
    url = TIKTOK_PROFILES[brand]
    print(f"\n  [{brand}] Extracting videos from {url}")
    print(f"    Using yt-dlp (may take 2-5 min per brand)...")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json", "--no-download",
        "--playlist-end", str(max_videos),
        "--no-warnings", "--quiet",
        "--extractor-args", "tiktok:api_hostname=api22-normal-c-useast2a.tiktokv.com",
        url
    ]

    videos = []
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                vid = d.get("id", "")
                if not vid:
                    continue

                ts_str = ""
                ts = d.get("timestamp")
                if ts:
                    try: ts_str = datetime.fromtimestamp(int(ts)).isoformat()
                    except: pass
                if not ts_str:
                    ud = d.get("upload_date", "")
                    if ud and len(ud) == 8:
                        try: ts_str = datetime.strptime(ud, "%Y%m%d").isoformat()
                        except: pass

                tags = d.get("tags") or []
                desc = d.get("description") or d.get("title") or ""

                videos.append({
                    "video_id": str(vid),
                    "brand": brand,
                    "author_name": d.get("uploader") or d.get("channel") or "",
                    "views_count": int(d.get("view_count") or 0),
                    "likes_count": int(d.get("like_count") or 0),
                    "comments_count": int(d.get("comment_count") or 0),
                    "shares_count": int(d.get("repost_count") or 0),
                    "collect_count": int(d.get("collect_count") or 0),
                    "duration_seconds": int(d.get("duration") or 0),
                    "publish_time": ts_str,
                    "video_desc": desc[:2000],
                    "music_used": d.get("track") or d.get("artist") or "",
                    "hashtags": ",".join(tags[:50]),
                    "video_url": d.get("webpage_url") or f"https://www.tiktok.com/@{d.get('uploader','')}/video/{vid}",
                    "crawl_source": "yt-dlp-v3"
                })

                if len(videos) % 20 == 0:
                    print(f"    ... {len(videos)} videos extracted")

            except json.JSONDecodeError:
                continue

        proc.wait(timeout=60)
    except Exception as e:
        print(f"    Error: {e}")

    print(f"    Total: {len(videos)} videos from {brand}")
    return videos

def insert_videos(conn, videos):
    """Insert new + update existing videos."""
    new, updated = 0, 0
    for v in videos:
        exists = conn.execute("SELECT video_id FROM tiktok_videos WHERE video_id=?",
                              (v["video_id"],)).fetchone()
        if exists:
            conn.execute("""UPDATE tiktok_videos SET
                views_count=?, likes_count=?, comments_count=?, shares_count=?,
                collect_count=?, crawl_source=?
                WHERE video_id=?""",
                (v["views_count"], v["likes_count"], v["comments_count"],
                 v["shares_count"], v["collect_count"], "yt-dlp-update", v["video_id"]))
            updated += 1
        else:
            conn.execute("""INSERT OR IGNORE INTO tiktok_videos
                (video_id,brand,author_name,views_count,likes_count,comments_count,
                 shares_count,collect_count,duration_seconds,publish_time,video_desc,
                 music_used,hashtags,video_url,crawl_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (v["video_id"],v["brand"],v["author_name"],v["views_count"],
                 v["likes_count"],v["comments_count"],v["shares_count"],
                 v["collect_count"],v["duration_seconds"],v["publish_time"],
                 v["video_desc"],v["music_used"],v["hashtags"],v["video_url"],
                 v["crawl_source"]))
            new += 1
    conn.commit()
    return new, updated

def main():
    pa = argparse.ArgumentParser()
    pa.add_argument("--brands", nargs="+", choices=BRANDS+["all"], default=["all"])
    pa.add_argument("--max-per-brand", type=int, default=250)
    a = pa.parse_args()
    brands = BRANDS if "all" in a.brands else [b for b in a.brands if b in BRANDS]

    print("="*70)
    print("  V3 TikTok Videos — yt-dlp Metadata Extraction")
    print(f"  Brands: {brands} | Max/brand: {a.max_per_brand}")
    print("="*70)

    conn = get_conn()
    print_status(conn)
    total_new, total_upd = 0, 0

    for brand in brands:
        videos = crawl_videos_ytdlp(brand, a.max_per_brand)
        if videos:
            n, u = insert_videos(conn, videos)
            total_new += n
            total_upd += u
            print(f"  [{brand}] +{n} new, {u} updated (total extracted: {len(videos)})")
        time.sleep(3)

    print_status(conn)
    print(f"\n  TOTAL: +{total_new} new videos, {total_upd} updated")
    print("\n  Exporting CSVs...")
    export_csvs(conn)
    conn.close()

if __name__=="__main__": main()