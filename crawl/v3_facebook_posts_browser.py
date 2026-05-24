import argparse
import random
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v3_config import *

try:
    from cloakbrowser import launch_context, launch_persistent_context
except Exception:
    launch_context = None
    launch_persistent_context = None

FB_PAGE_URLS = {
    "phuc_long": "https://www.facebook.com/phuclongcoffeeandtea",
    "highlands": "https://www.facebook.com/highlandscoffeevietnam",
    "katinat": "https://www.facebook.com/katinat.vn",
}

POST_PATTERNS = [
    r"/posts/([A-Za-z0-9]+)",
    r"story_fbid=(\d+)",
    r"/permalink/(\d+)",
    r"/reel/(\d+)",
    r"/videos/(\d+)",
    r"/photos/[^/]+/(\d+)",
    r"/photo/\?fbid=(\d+)",
]


def extract_post_id(url):
    if not url:
        return None
    for pat in POST_PATTERNS:
        m = re.search(pat, url)
        if m:
            return str(m.group(1))
    return None


def clean_text(text):
    if not text:
        return ""
    text = re.sub(r"\s+", " ", str(text)).strip()
    ui = ["Thích", "Bình luận", "Chia sẻ", "Like", "Comment", "Share",
          "Viết bình luận", "Write a comment", "Xem thêm", "See more",
          "Tất cả cảm xúc", "All reactions", "Gửi", "Send"]
    for x in ui:
        text = text.replace(x, " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:2000]


def parse_num(text):
    if not text:
        return 0
    t = str(text).strip().replace(",", ".")
    m = re.search(r"([\d]+(?:[.,]\d+)?)\s*([KkMmNn]|nghìn|triệu|Tr)?", t)
    if not m:
        return 0
    n = float(m.group(1).replace(",", "."))
    unit = (m.group(2) or "").lower()
    if unit in ["k", "n", "nghìn"]:
        n *= 1000
    elif unit in ["m", "triệu", "tr"]:
        n *= 1000000
    return int(n)


def extract_hashtags(text):
    if not text:
        return ""
    tags = re.findall(r"#([\w\u00C0-\u024F\u1E00-\u1EFF]+)", text, re.UNICODE)
    return ",".join(tags[:30])


def safe_close(ctx):
    try:
        ctx.close()
    except Exception:
        pass


def open_context(headed=False):
    storage = str(STATE_FILE) if STATE_FILE.exists() else None
    if launch_context:
        try:
            return launch_context(
                headless=not headed, humanize=True, locale="vi-VN",
                timezone="Asia/Ho_Chi_Minh",
                viewport={"width": 1365, "height": 900},
                storage_state=storage,
            )
        except Exception as e:
            print(f"  launch_context failed: {e}")
    if launch_persistent_context:
        profile = str(PROFILE_DIR / "facebook_posts_browser")
        return launch_persistent_context(
            profile, headless=not headed, humanize=True, locale="vi-VN",
            timezone="Asia/Ho_Chi_Minh",
            viewport={"width": 1365, "height": 900},
        )
    raise RuntimeError("cloakbrowser launch unavailable")


# ═══════════════════════════════════════════════════════════════
# ENHANCED JS: Lấy engagement + timestamp RIÊNG BIỆT từ DOM
# ═══════════════════════════════════════════════════════════════
JS_EXTRACT = """
() => {
    const out = [];
    // Tìm tất cả article (mỗi article = 1 post trên Facebook)
    const articles = document.querySelectorAll('[role="article"]');
    
    for (const art of articles) {
        // === 1. TÌM POST URL ===
        let postHref = '';
        const allLinks = art.querySelectorAll('a[href]');
        for (const a of allLinks) {
            const h = (a.href || '').toLowerCase();
            if (h.includes('/posts/') || h.includes('story_fbid=') ||
                h.includes('/permalink/') || h.includes('/reel/') ||
                h.includes('/videos/') || h.includes('/photos/') ||
                h.includes('/photo/?fbid=')) {
                postHref = a.href;
                break;
            }
        }
        if (!postHref) continue;

        // === 2. LẤY POST TEXT (phần nội dung chính) ===
        let postText = '';
        // Facebook đặt nội dung post trong div[data-ad-preview="message"]
        // hoặc div có dir="auto" chứa text dài
        const msgDiv = art.querySelector('[data-ad-preview="message"]');
        if (msgDiv) {
            postText = msgDiv.innerText || '';
        }
        if (!postText || postText.length < 10) {
            // Fallback: tìm div có dir="auto" chứa text dài nhất
            const autoDivs = art.querySelectorAll('div[dir="auto"]');
            let longest = '';
            for (const d of autoDivs) {
                const t = d.innerText || '';
                if (t.length > longest.length && t.length < 3000) {
                    longest = t;
                }
            }
            if (longest.length > postText.length) postText = longest;
        }
        if (!postText || postText.length < 5) {
            postText = art.innerText ? art.innerText.substring(0, 2000) : '';
        }

        // === 3. LẤY TIMESTAMP ===
        // Facebook render timestamp trong <a> có aria-label chứa ngày/giờ
        // hoặc trong <abbr> hoặc <span> gần top của article
        let timestamp = '';
        
        // Method 1: aria-label trên link timestamp
        for (const a of allLinks) {
            const ariaLabel = a.getAttribute('aria-label') || '';
            // Aria-label chứa ngày dạng "Thứ Hai, 20 tháng 4, 2026 lúc 10:06"
            // hoặc "Monday, April 20, 2026 at 10:06 AM"
            if (/\d{4}/.test(ariaLabel) && 
                (/tháng|thang|january|february|march|april|may|june|july|august|september|october|november|december/i.test(ariaLabel))) {
                timestamp = ariaLabel;
                break;
            }
        }
        
        // Method 2: Tìm trong các span/abbr
        if (!timestamp) {
            const timeEls = art.querySelectorAll('a[href*="__cft__"], abbr[data-utime]');
            for (const el of timeEls) {
                const ariaLabel = el.getAttribute('aria-label') || '';
                if (ariaLabel && /\d/.test(ariaLabel)) {
                    timestamp = ariaLabel;
                    break;
                }
                const title = el.getAttribute('title') || '';
                if (title && /\d/.test(title)) {
                    timestamp = title;
                    break;
                }
            }
        }
        
        // Method 3: Tìm text dạng "X giờ", "X ngày", "Hôm qua"
        if (!timestamp) {
            for (const a of allLinks) {
                const t = (a.innerText || '').trim();
                if (/^\d+\s*(giờ|phút|ngày|tuần|tháng|giây|hr|min|h |d |w )/i.test(t) ||
                    /^(hôm qua|yesterday|hôm nay|today|just now|vừa xong)/i.test(t)) {
                    timestamp = t;
                    break;
                }
            }
        }

        // === 4. LẤY ENGAGEMENT (likes, comments, shares) ===
        let likes = 0, comments = 0, shares = 0;
        
        // Facebook render engagement trong toolbar ở cuối post
        // Cấu trúc: [icon] "1,2N" ... "45 bình luận" ... "12 lượt chia sẻ"
        const artText = art.innerText || '';
        
        // Method 1: Parse từ aria-label trên nút reaction
        // Facebook có nút với aria-label="1.234 lượt thích" hoặc "1,2K reactions"
        const allEls = art.querySelectorAll('[aria-label]');
        for (const el of allEls) {
            const label = (el.getAttribute('aria-label') || '').toLowerCase();
            
            // Likes/Reactions
            if (!likes && (label.includes('lượt thích') || label.includes('reaction') || 
                label.includes('like') || label.includes('người khác') ||
                label.includes('cảm xúc') || label.includes('thả tim'))) {
                const m = label.match(/([\d.,]+\s*[kKmMnN]?)/);
                if (m) {
                    let n = m[1].replace(/\./g, '').replace(/,/g, '.');
                    const numMatch = n.match(/([\d.]+)\s*([kKmMnN])?/);
                    if (numMatch) {
                        let val = parseFloat(numMatch[1]);
                        const unit = (numMatch[2] || '').toLowerCase();
                        if (unit === 'k' || unit === 'n') val *= 1000;
                        if (unit === 'm') val *= 1000000;
                        likes = Math.max(likes, Math.round(val));
                    }
                }
            }
            
            // Comments
            if (!comments && (label.includes('bình luận') || label.includes('comment'))) {
                const m = label.match(/([\d.,]+\s*[kKmMnN]?)/);
                if (m) {
                    let n = m[1].replace(/\./g, '').replace(/,/g, '.');
                    const numMatch = n.match(/([\d.]+)\s*([kKmMnN])?/);
                    if (numMatch) {
                        let val = parseFloat(numMatch[1]);
                        const unit = (numMatch[2] || '').toLowerCase();
                        if (unit === 'k' || unit === 'n') val *= 1000;
                        comments = Math.max(comments, Math.round(val));
                    }
                }
            }
            
            // Shares
            if (!shares && (label.includes('chia sẻ') || label.includes('share'))) {
                const m = label.match(/([\d.,]+\s*[kKmMnN]?)/);
                if (m) {
                    let n = m[1].replace(/\./g, '').replace(/,/g, '.');
                    const numMatch = n.match(/([\d.]+)\s*([kKmMnN])?/);
                    if (numMatch) {
                        let val = parseFloat(numMatch[1]);
                        const unit = (numMatch[2] || '').toLowerCase();
                        if (unit === 'k' || unit === 'n') val *= 1000;
                        shares = Math.max(shares, Math.round(val));
                    }
                }
            }
        }
        
        // Method 2: Parse từ innerText dạng "45 bình luận  12 lượt chia sẻ"
        if (!likes || !comments || !shares) {
            // Likes: "X lượt thích" hoặc "X người khác"
            if (!likes) {
                const lm = artText.match(/([\d.,]+\s*[KkMmNn]?)\s*(?:lượt thích|người khác|reactions?|likes?)/i);
                if (lm) {
                    let val = lm[1].replace(/\./g, '').replace(/,/g, '.');
                    const nm = val.match(/([\d.]+)\s*([kKmMnN])?/);
                    if (nm) {
                        let v = parseFloat(nm[1]);
                        const u = (nm[2] || '').toLowerCase();
                        if (u === 'k' || u === 'n') v *= 1000;
                        if (u === 'm') v *= 1000000;
                        likes = Math.round(v);
                    }
                }
            }
            // Comments: "X bình luận"
            if (!comments) {
                const cm = artText.match(/([\d.,]+\s*[KkMmNn]?)\s*(?:bình luận|comments?)/i);
                if (cm) {
                    let val = cm[1].replace(/\./g, '').replace(/,/g, '.');
                    const nm = val.match(/([\d.]+)\s*([kKmMnN])?/);
                    if (nm) {
                        let v = parseFloat(nm[1]);
                        const u = (nm[2] || '').toLowerCase();
                        if (u === 'k' || u === 'n') v *= 1000;
                        comments = Math.round(v);
                    }
                }
            }
            // Shares: "X lượt chia sẻ"
            if (!shares) {
                const sm = artText.match(/([\d.,]+\s*[KkMmNn]?)\s*(?:lượt chia sẻ|chia sẻ|shares?)/i);
                if (sm) {
                    let val = sm[1].replace(/\./g, '').replace(/,/g, '.');
                    const nm = val.match(/([\d.]+)\s*([kKmMnN])?/);
                    if (nm) {
                        let v = parseFloat(nm[1]);
                        const u = (nm[2] || '').toLowerCase();
                        if (u === 'k' || u === 'n') v *= 1000;
                        shares = Math.round(v);
                    }
                }
            }
        }

        // === 5. DETECT POST TYPE ===
        const hLow = postHref.toLowerCase();
        let postType = 'text';
        if (hLow.includes('/reel/') || hLow.includes('/videos/')) postType = 'video';
        else if (hLow.includes('/photos/') || hLow.includes('/photo/')) postType = 'photo';
        else if (art.querySelector('video')) postType = 'video';
        else if (art.querySelector('img[src*="scontent"]')) postType = 'photo';

        out.push({
            href: postHref,
            text: postText.substring(0, 2000),
            timestamp: timestamp,
            likes: likes,
            comments: comments,
            shares: shares,
            postType: postType
        });
    }
    return out;
}
"""


def extract_visible_posts(page, brand):
    items = page.evaluate(JS_EXTRACT)
    posts = []
    seen = set()
    for item in items:
        href = item.get("href") or ""
        pid = extract_post_id(href)
        if not pid or pid in seen:
            continue
        seen.add(pid)
        raw_text = item.get("text") or ""
        text = clean_text(raw_text)
        if len(text) < 10:
            continue

        posts.append({
            "post_id": pid,
            "brand": brand,
            "post_text": text,
            "post_type": item.get("postType") or "text",
            "publish_time": item.get("timestamp") or "",
            "likes_count": int(item.get("likes") or 0),
            "shares_count": int(item.get("shares") or 0),
            "comments_count": int(item.get("comments") or 0),
            "reactions_breakdown": "",
            "hashtags": extract_hashtags(text),
            "post_url": href,
            "crawl_source": "browser-dom-v3",
        })
    return posts


def upsert_posts(conn, posts):
    new = updated = skipped = 0
    for p in posts:
        row = conn.execute(
            "SELECT likes_count, shares_count, comments_count, post_text, post_url, publish_time "
            "FROM facebook_posts WHERE post_id=?",
            (p["post_id"],),
        ).fetchone()
        if row:
            old_l = int(row[0] or 0)
            old_s = int(row[1] or 0)
            old_c = int(row[2] or 0)
            old_text = row[3] or ""
            old_url = row[4] or ""
            old_time = row[5] or ""
            nl = max(old_l, int(p["likes_count"] or 0))
            ns = max(old_s, int(p["shares_count"] or 0))
            nc = max(old_c, int(p["comments_count"] or 0))
            fill_text = (not old_text) and p["post_text"]
            fill_url = (not old_url) and p["post_url"]
            fill_time = (not old_time) and p["publish_time"]
            changed = (nl != old_l or ns != old_s or nc != old_c
                       or fill_text or fill_url or fill_time)
            if changed:
                conn.execute(
                    "UPDATE facebook_posts SET likes_count=?, shares_count=?, comments_count=?, "
                    "post_text=CASE WHEN post_text IS NULL OR post_text='' THEN ? ELSE post_text END, "
                    "post_url=CASE WHEN post_url IS NULL OR post_url='' THEN ? ELSE post_url END, "
                    "publish_time=CASE WHEN publish_time IS NULL OR publish_time='' THEN ? ELSE publish_time END, "
                    "crawl_source=? WHERE post_id=?",
                    (nl, ns, nc, p["post_text"], p["post_url"],
                     p["publish_time"], "browser-dom-update", p["post_id"]),
                )
                updated += 1
            else:
                skipped += 1
        else:
            conn.execute(
                "INSERT OR IGNORE INTO facebook_posts "
                "(post_id,brand,post_text,post_type,publish_time,likes_count,"
                "shares_count,comments_count,reactions_breakdown,hashtags,post_url,crawl_source) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (p["post_id"], p["brand"], p["post_text"], p["post_type"], p["publish_time"],
                 p["likes_count"], p["shares_count"], p["comments_count"],
                 p["reactions_breakdown"], p["hashtags"], p["post_url"], p["crawl_source"]),
            )
            new += 1
    conn.commit()
    return new, updated, skipped


def crawl_brand(conn, ctx, brand, max_per_brand=9999, scrolls=120):
    url = FB_PAGE_URLS[brand]
    before = conn.execute("SELECT COUNT(*) FROM facebook_posts WHERE brand=?", (brand,)).fetchone()[0]
    print(f"\n  [{brand}] Browser crawl: {url}")
    print(f"  [{brand}] Existing posts: {before}")

    page = ctx.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=45000)
    time.sleep(random.uniform(5, 8))

    if "login" in page.url.lower():
        print("    Login detected. Use --headed and log in once.")
        try: page.close()
        except: pass
        return 0, 0, 0

    total_new = total_upd = total_skip = 0
    no_growth = 0
    last_total = before

    for i in range(scrolls):
        posts = extract_visible_posts(page, brand)
        n, u, s = upsert_posts(conn, posts)
        total_new += n
        total_upd += u
        total_skip += s
        current = conn.execute("SELECT COUNT(*) FROM facebook_posts WHERE brand=?", (brand,)).fetchone()[0]

        # Count posts with engagement data
        has_engagement = conn.execute(
            "SELECT COUNT(*) FROM facebook_posts WHERE brand=? AND "
            "(CAST(likes_count AS INTEGER)>0 OR CAST(comments_count AS INTEGER)>0)",
            (brand,)).fetchone()[0]

        if current <= last_total and u == 0:
            no_growth += 1
        else:
            last_total = current
            no_growth = 0
        if i % 5 == 0 or n or u:
            print(f"    Scroll {i+1}/{scrolls}: batch={len(posts)} +{n} new, {u} upd, {s} skip | "
                  f"total={current} (has_engagement={has_engagement})")
        if total_new >= max_per_brand:
            print(f"    Cap reached: +{total_new}")
            break
        if no_growth >= 12:
            print("    No growth after repeated scrolls; stopping.")
            break
        try:
            for txt in ["Xem thêm", "See more"]:
                loc = page.get_by_text(txt, exact=False)
                cnt = min(loc.count(), 3)
                for k in range(cnt):
                    try: loc.nth(k).click(timeout=1000)
                    except: pass
        except: pass
        page.mouse.wheel(0, random.randint(1400, 2300))
        time.sleep(random.uniform(1.7, 3.2))

    try: page.close()
    except: pass
    print(f"  [{brand}] Result: +{total_new} new, {total_upd} updated, {total_skip} skipped")
    return total_new, total_upd, total_skip


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brands", nargs="+", choices=BRANDS + ["all"], default=["all"])
    parser.add_argument("--max-per-brand", type=int, default=9999)
    parser.add_argument("--scrolls", type=int, default=120)
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    brands = BRANDS if "all" in args.brands else [b for b in args.brands if b in BRANDS]

    print("=" * 70)
    print("  V3 Facebook Posts Browser DOM Crawler (ENHANCED METADATA)")
    print(f"  Brands: {brands} | max/brand={args.max_per_brand} | scrolls={args.scrolls}")
    print("  Extracts: text + likes + comments + shares + timestamp")
    print("  Logic: INSERT new | UPDATE changed | SKIP identical")
    print("=" * 70)

    conn = get_conn()
    print_status(conn)
    ctx = open_context(headed=args.headed)
    gn = gu = gs = 0
    try:
        for brand in brands:
            n, u, s = crawl_brand(conn, ctx, brand, args.max_per_brand, args.scrolls)
            gn += n
            gu += u
            gs += s
            time.sleep(random.uniform(3, 6))
    finally:
        safe_close(ctx)
    print_status(conn)
    print(f"\n  TOTAL: +{gn} new, {gu} updated, {gs} skipped")
    print("\n  Exporting CSVs...")
    export_csvs(conn)
    conn.close()


if __name__ == "__main__":
    main()