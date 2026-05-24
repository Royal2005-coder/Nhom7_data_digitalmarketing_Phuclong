import json, subprocess, sys, re, argparse, time, hashlib
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from v3_config import *

FB_PAGES = {
    "phuc_long": "https://www.facebook.com/PhuclongCoffeeandTea",
    "highlands": "https://www.facebook.com/highlandscoffeevietnam",
    "katinat":   "https://www.facebook.com/katinat.vn",
}

def load_cookies_file():
    """Convert fb_state.json to Netscape cookies.txt for yt-dlp."""
    if not STATE_FILE.exists():
        print("  ERROR: No FB cookies"); return None
    with open(STATE_FILE) as f: data = json.load(f)
    
    cookie_file = Path("crawl/.cookies/fb_cookies.txt")
    with open(cookie_file, "w") as f:
        f.write("# Netscape HTTP Cookie File\n")
        for c in data.get("cookies", []):
            domain = c.get("domain", ".facebook.com")
            flag = "TRUE" if domain.startswith(".") else "FALSE"
            path = c.get("path", "/")
            secure = "TRUE" if c.get("secure") else "FALSE"
            expires = str(int(c.get("expires", 0)))
            name = c.get("name", "")
            value = c.get("value", "")
            f.write(f"{domain}\t{flag}\t{path}\t{secure}\t{expires}\t{name}\t{value}\n")
    
    print(f"  Cookies file: {cookie_file}")
    return str(cookie_file)

def crawl_fb_posts_ytdlp(brand, cookie_file, max_posts=400):
    """Use yt-dlp to extract FB page posts metadata."""
    url = FB_PAGES[brand]
    print(f"\n  [{brand}] Extracting posts from {url}")
    print(f"    Using yt-dlp (may take 5-10 min per brand)...")

    cmd = [
        sys.executable, "-m", "yt_dlp",
        "--dump-json", "--no-download",
        "--playlist-end", str(max_posts),
        "--no-warnings", "--quiet",
        "--cookies", cookie_file,
        "--extractor-args", "facebook:webpage_url_basename=posts",
        url
    ]

    posts = []
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                text=True, encoding="utf-8", errors="replace")
        
        for line in proc.stdout:
            line = line.strip()
            if not line: continue
            try:
                d = json.loads(line)
                pid = d.get("id", "")
                if not pid: continue
                
                # Clean post ID
                pid = str(pid).split("_")[-1] if "_" in str(pid) else str(pid)
                
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

                desc = d.get("description") or d.get("title") or ""
                
                # Detect post type
                post_type = "text"
                if d.get("duration"): post_type = "video"
                elif d.get("thumbnails"): post_type = "photo"
                
                webpage_url = d.get("webpage_url") or d.get("url") or ""
                
                posts.append({
                    "post_id": str(pid),
                    "brand": brand,
                    "post_text": desc[:2000],
                    "post_type": post_type,
                    "publish_time": ts_str,
                    "likes_count": int(d.get("like_count") or 0),
                    "shares_count": int(d.get("repost_count") or 0),
                    "comments_count": int(d.get("comment_count") or 0),
                    "reactions_breakdown": "",
                    "hashtags": ",".join(re.findall(r"#([\w\u00C0-\u024F\u1E00-\u1EFF]+)", desc, re.UNICODE)[:30]),
                    "post_url": webpage_url,
                    "crawl_source": "yt-dlp-fb-v3"
                })
                
                if len(posts) % 20 == 0:
                    print(f"    ... {len(posts)} posts extracted")
                    
            except json.JSONDecodeError:
                continue
        
        proc.wait(timeout=120)
        stderr = proc.stderr.read()
        if proc.returncode != 0 and not posts:
            print(f"    yt-dlp stderr: {stderr[:200]}")
            
    except Exception as e:
        print(f"    Error: {e}")

    print(f"    Total: {len(posts)} posts from {brand}")
    return posts

def upsert_posts(conn, posts):
    """Smart upsert: INSERT new, UPDATE if engagement changed, SKIP identical."""
    new, updated, skipped = 0, 0, 0
    for p in posts:
        existing = conn.execute(
            "SELECT likes_count, shares_count, comments_count FROM facebook_posts WHERE post_id=?",
            (p["post_id"],)).fetchone()
        
        if existing:
            old_l, old_s, old_c = existing
            new_l, new_s, new_c = p["likes_count"], p["shares_count"], p["comments_count"]
            if (new_l != old_l or new_s != old_s or new_c != old_c) and (new_l + new_s + new_c) > 0:
                conn.execute("""UPDATE facebook_posts SET
                    likes_count=?, shares_count=?, comments_count=?,
                    publish_time=CASE WHEN publish_time IS NULL OR publish_time='' THEN ? ELSE publish_time END,
                    crawl_source=? WHERE post_id=?""",
                    (max(new_l, old_l), max(new_s, old_s), max(new_c, old_c),
                     p["publish_time"], "yt-dlp-update", p["post_id"]))
                updated += 1
            else:
                skipped += 1
        else:
            conn.execute("""INSERT OR IGNORE INTO facebook_posts
                (post_id,brand,post_text,post_type,publish_time,likes_count,
                 shares_count,comments_count,reactions_breakdown,hashtags,post_url,crawl_source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (p["post_id"],p["brand"],p["post_text"],p["post_type"],p["publish_time"],
                 p["likes_count"],p["shares_count"],p["comments_count"],
                 p["reactions_breakdown"],p["hashtags"],p["post_url"],p["crawl_source"]))
            new += 1
    conn.commit()
    return new, updated, skipped

def main():
    pa = argparse.ArgumentParser()
    pa.add_argument("--brands", nargs="+", choices=BRANDS+["all"], default=["all"])
    pa.add_argument("--max-per-brand", type=int, default=400)
    a = pa.parse_args()
    brands = BRANDS if "all" in a.brands else [b for b in a.brands if b in BRANDS]

    print("="*70)
    print("  V3 Facebook Posts — yt-dlp Extraction")
    print(f"  Brands: {brands} | Max/brand: {a.max_per_brand}")
    print("  Upsert: INSERT new | UPDATE changed | SKIP identical")
    print("="*70)

    cookie_file = load_cookies_file()
    if not cookie_file: return

    conn = get_conn()
    print_status(conn)
    tn, tu, ts = 0, 0, 0

    for brand in brands:
        before = conn.execute("SELECT COUNT(*) FROM facebook_posts WHERE brand=?", (brand,)).fetchone()[0]
        print(f"  [{brand}] Existing: {before} posts")
        
        posts = crawl_fb_posts_ytdlp(brand, cookie_file, a.max_per_brand)
        if posts:
            n, u, s = upsert_posts(conn, posts)
            tn += n; tu += u; ts += s
            print(f"  [{brand}] +{n} new, {u} updated, {s} skipped")
        time.sleep(3)

    print_status(conn)
    print(f"\n  TOTAL: +{tn} new, {tu} updated, {ts} skipped")
    print("\n  Exporting..."); export_csvs(conn); conn.close()

if __name__=="__main__": main()