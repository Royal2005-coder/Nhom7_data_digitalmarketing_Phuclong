import argparse
import random
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from v3_config import *

try:
    from cloakbrowser import launch_context, launch_persistent_context
except Exception:
    launch_context = None
    launch_persistent_context = None


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


def convert_relative_time(text):
    """
    Convert relative timestamp sang ISO format.
    '3 tuần' → '2026-05-03T00:00:00'
    'Thứ Hai, 20 tháng 4, 2026 lúc 10:06' → '2026-04-20T10:06:00'
    """
    if not text:
        return ""
    text = text.strip()

    # Đã là ISO format rồi → giữ nguyên
    if re.match(r"^\d{4}-\d{2}", text):
        return text

    now = datetime.now()

    # === PARSE RELATIVE TIME (vi-VN) ===
    # "3 tuần" → 21 ngày trước
    patterns_vi = [
        (r"(\d+)\s*giây", lambda m: now - timedelta(seconds=int(m.group(1)))),
        (r"(\d+)\s*phút", lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r"(\d+)\s*giờ", lambda m: now - timedelta(hours=int(m.group(1)))),
        (r"(\d+)\s*ngày", lambda m: now - timedelta(days=int(m.group(1)))),
        (r"(\d+)\s*tuần", lambda m: now - timedelta(weeks=int(m.group(1)))),
        (r"(\d+)\s*tháng", lambda m: now - timedelta(days=int(m.group(1)) * 30)),
        (r"(\d+)\s*năm", lambda m: now - timedelta(days=int(m.group(1)) * 365)),
    ]
    for pat, fn in patterns_vi:
        m = re.search(pat, text, re.I)
        if m:
            return fn(m).strftime("%Y-%m-%dT%H:%M:%S")

    # "hôm qua" / "hôm nay"
    if re.search(r"hôm\s*qua|yesterday", text, re.I):
        return (now - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    if re.search(r"hôm\s*nay|today|vừa\s*xong|just\s*now", text, re.I):
        return now.strftime("%Y-%m-%dT%H:%M:%S")

    # === PARSE RELATIVE TIME (en) ===
    patterns_en = [
        (r"(\d+)\s*(?:hr|hour|h\b)", lambda m: now - timedelta(hours=int(m.group(1)))),
        (r"(\d+)\s*(?:min|m\b)", lambda m: now - timedelta(minutes=int(m.group(1)))),
        (r"(\d+)\s*(?:day|d\b)", lambda m: now - timedelta(days=int(m.group(1)))),
        (r"(\d+)\s*(?:week|w\b)", lambda m: now - timedelta(weeks=int(m.group(1)))),
    ]
    for pat, fn in patterns_en:
        m = re.search(pat, text, re.I)
        if m:
            return fn(m).strftime("%Y-%m-%dT%H:%M:%S")

    # === PARSE ABSOLUTE DATE (vi-VN) ===
    # "Thứ Hai, 20 tháng 4, 2026 lúc 10:06"
    m = re.search(r"(\d{1,2})\s*tháng\s*(\d{1,2}),?\s*(\d{4})\s*(?:lúc\s*)?(\d{1,2}):(\d{2})?", text, re.I)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hour, minute = int(m.group(4)), int(m.group(5) or 0)
        try:
            return datetime(year, month, day, hour, minute).isoformat()
        except ValueError:
            pass

    # "20 tháng 4, 2026"
    m = re.search(r"(\d{1,2})\s*tháng\s*(\d{1,2}),?\s*(\d{4})", text, re.I)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            return datetime(year, month, day).isoformat()
        except ValueError:
            pass

    # === PARSE ABSOLUTE DATE (en) ===
    months_en = {"january": 1, "february": 2, "march": 3, "april": 4,
                 "may": 5, "june": 6, "july": 7, "august": 8,
                 "september": 9, "october": 10, "november": 11, "december": 12}
    m = re.search(r"(\w+)\s+(\d{1,2}),?\s*(\d{4})(?:\s+at\s+(\d{1,2}):(\d{2}))?", text, re.I)
    if m:
        month_name = m.group(1).lower()
        if month_name in months_en:
            month = months_en[month_name]
            day, year = int(m.group(2)), int(m.group(3))
            hour = int(m.group(4) or 0)
            minute = int(m.group(5) or 0)
            try:
                return datetime(year, month, day, hour, minute).isoformat()
            except ValueError:
                pass

    # Không parse được → trả về raw text
    return text


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
        profile = str(PROFILE_DIR / "facebook_fill_engagement")
        return launch_persistent_context(
            profile, headless=not headed, humanize=True, locale="vi-VN",
            timezone="Asia/Ho_Chi_Minh",
            viewport={"width": 1365, "height": 900},
        )
    raise RuntimeError("cloakbrowser unavailable")


# ══════════════════════════════════════════════════════════════════
# ENHANCED JS: Extract engagement từ POST DETAIL PAGE
# Wait longer + multiple extraction methods + scroll to load
# ══════════════════════════════════════════════════════════════════
JS_POST_DETAIL = r"""
() => {
    let likes = 0, comments = 0, shares = 0, timestamp = '';

    // Helper: parse number from text
    function pNum(s) {
        if (!s) return 0;
        s = s.trim().replace(/\./g, '').replace(/,/g, '.');
        const m = s.match(/([\d.]+)\s*([kKmMnN])?/);
        if (!m) return 0;
        let v = parseFloat(m[1]);
        const u = (m[2] || '').toLowerCase();
        if (u === 'k' || u === 'n') v *= 1000;
        if (u === 'm') v *= 1000000;
        return Math.round(v);
    }

    // === METHOD 1: aria-label (most reliable on detail page) ===
    const ariaEls = document.querySelectorAll('[aria-label]');
    for (const el of ariaEls) {
        const label = (el.getAttribute('aria-label') || '');
        const labelLow = label.toLowerCase();
        const numMatch = label.match(/([\d.,]+\s*[kKmMnN]?)/);
        if (!numMatch) continue;
        const val = pNum(numMatch[1]);
        if (val <= 0) continue;

        if (!likes && (labelLow.includes('thích') || labelLow.includes('like') ||
            labelLow.includes('reaction') || labelLow.includes('người khác') ||
            labelLow.includes('cảm xúc') || labelLow.includes('yêu thích'))) {
            likes = Math.max(likes, val);
        }
        if (!comments && (labelLow.includes('bình luận') || labelLow.includes('comment'))) {
            comments = Math.max(comments, val);
        }
        if (!shares && (labelLow.includes('chia sẻ') || labelLow.includes('share'))) {
            shares = Math.max(shares, val);
        }
    }

    // === METHOD 2: Regex từ body text ===
    const body = document.body ? (document.body.innerText || '') : '';

    if (!likes) {
        const lm = body.match(/([\d.,]+\s*[KkMmNn]?)\s*(?:lượt thích|người khác|reactions?|likes?)/i);
        if (lm) likes = pNum(lm[1]);
    }
    if (!comments) {
        const cm = body.match(/([\d.,]+\s*[KkMmNn]?)\s*(?:bình luận|comments?)/i);
        if (cm) comments = pNum(cm[1]);
    }
    if (!shares) {
        const sm = body.match(/([\d.,]+\s*[KkMmNn]?)\s*(?:lượt chia sẻ|chia sẻ|shares?)/i);
        if (sm) shares = pNum(sm[1]);
    }

    // === METHOD 3: Tìm trong toolbar reaction ===
    // Facebook post detail có toolbar: [Like icon] 1.2N  [Comment icon] 45  [Share icon] 12
    if (!likes) {
        const toolbars = document.querySelectorAll('[role="toolbar"], [data-testid]');
        for (const tb of toolbars) {
            const spans = tb.querySelectorAll('span');
            for (const sp of spans) {
                const t = (sp.innerText || '').trim();
                if (/^[\d.,]+\s*[KkMmNn]?$/.test(t)) {
                    const v = pNum(t);
                    if (v > likes) likes = v;
                    break;
                }
            }
        }
    }

    // === METHOD 4: Tìm số nằm cạnh icon reaction ===
    if (!likes) {
        const imgs = document.querySelectorAll('img[src*="emoji"], img[src*="reaction"], img[alt]');
        for (const img of imgs) {
            const next = img.nextElementSibling || img.parentElement;
            if (next) {
                const t = (next.innerText || '').trim();
                const v = pNum(t);
                if (v > 0 && v > likes) {
                    likes = v;
                    break;
                }
            }
        }
    }

    // === TIMESTAMP ===
    // Method A: aria-label chứa ngày đầy đủ
    const links = document.querySelectorAll('a[href]');
    for (const a of links) {
        const ariaLabel = a.getAttribute('aria-label') || '';
        if (/\d{4}/.test(ariaLabel) &&
            (/tháng|january|february|march|april|may|june|july|august|september|october|november|december/i.test(ariaLabel))) {
            timestamp = ariaLabel;
            break;
        }
    }

    // Method B: title attribute
    if (!timestamp) {
        const timeEls = document.querySelectorAll('abbr[data-utime], a[data-utime]');
        for (const el of timeEls) {
            const title = el.getAttribute('title') || el.getAttribute('data-tooltip') || '';
            if (title && /\d/.test(title)) {
                timestamp = title;
                break;
            }
            const utime = el.getAttribute('data-utime');
            if (utime) {
                try {
                    timestamp = new Date(parseInt(utime) * 1000).toISOString();
                    break;
                } catch(e) {}
            }
        }
    }

    // Method C: Relative time text ("3 tuần", "2 ngày")
    if (!timestamp) {
        for (const a of links) {
            const t = (a.innerText || '').trim();
            if (/^\d+\s*(giờ|phút|ngày|tuần|tháng|giây|năm|hr|min|h |d |w )/i.test(t) ||
                /^(hôm qua|yesterday|hôm nay|today|just now|vừa xong)/i.test(t)) {
                timestamp = t;
                break;
            }
        }
    }

    // Method D: Tìm timestamp trong meta/time elements
    if (!timestamp) {
        const timeEl = document.querySelector('time[datetime]');
        if (timeEl) {
            timestamp = timeEl.getAttribute('datetime') || '';
        }
    }

    return { likes, comments, shares, timestamp };
}
"""


def get_posts_missing_engagement(conn, brand, limit=500):
    """Lấy posts thiếu likes HOẶC thiếu time, có post_url."""
    return conn.execute("""
        SELECT post_id, post_url FROM facebook_posts
        WHERE brand=?
          AND post_url IS NOT NULL AND post_url != ''
          AND (
              CAST(COALESCE(likes_count, 0) AS INTEGER) = 0
              OR publish_time IS NULL OR publish_time = ''
          )
        ORDER BY RANDOM()
        LIMIT ?
    """, (brand, limit)).fetchall()


def fill_post(page, conn, post_id, post_url):
    """Mở 1 post URL, chờ render, extract engagement, update DB."""
    try:
        page.goto(post_url, wait_until="domcontentloaded", timeout=30000)

        # Chờ DOM render engagement (quan trọng!)
        time.sleep(random.uniform(4, 6))

        # Scroll nhẹ để trigger lazy-load engagement
        page.mouse.wheel(0, random.randint(300, 500))
        time.sleep(random.uniform(1, 2))

        # Click "Xem thêm" nếu có
        try:
            for txt in ["Xem thêm", "See more"]:
                loc = page.get_by_text(txt, exact=False)
                if loc.count() > 0:
                    loc.first.click(timeout=2000)
                    time.sleep(0.5)
        except Exception:
            pass

        if "login" in page.url.lower():
            return "login", 0, 0, 0, ""

        data = page.evaluate(JS_POST_DETAIL)
        likes = int(data.get("likes") or 0)
        comments = int(data.get("comments") or 0)
        shares = int(data.get("shares") or 0)
        raw_time = data.get("timestamp") or ""

        # Convert relative time → ISO
        iso_time = convert_relative_time(raw_time)

        if likes == 0 and comments == 0 and not iso_time:
            return "empty", 0, 0, 0, ""

        # Update DB: chỉ fill nếu giá trị mới > giá trị cũ
        row = conn.execute(
            "SELECT likes_count, shares_count, comments_count, publish_time FROM facebook_posts WHERE post_id=?",
            (post_id,)
        ).fetchone()

        if not row:
            return "missing", 0, 0, 0, ""

        old_l = int(row[0] or 0)
        old_s = int(row[1] or 0)
        old_c = int(row[2] or 0)
        old_time = row[3] or ""

        nl = max(old_l, likes)
        ns = max(old_s, shares)
        nc = max(old_c, comments)
        new_time = iso_time if (not old_time and iso_time) else old_time

        changed = (nl != old_l or ns != old_s or nc != old_c or (new_time != old_time))

        if changed:
            conn.execute(
                """UPDATE facebook_posts SET
                    likes_count=?, shares_count=?, comments_count=?,
                    publish_time=CASE WHEN publish_time IS NULL OR publish_time='' THEN ? ELSE publish_time END,
                    crawl_source=?
                WHERE post_id=?""",
                (nl, ns, nc, new_time, "fill-detail-page", post_id)
            )
            conn.commit()
            return "filled", nl, nc, ns, new_time

        return "skip", 0, 0, 0, ""

    except Exception as e:
        return f"err:{str(e)[:40]}", 0, 0, 0, ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--brands", nargs="+", choices=BRANDS + ["all"], default=["all"])
    parser.add_argument("--limit", type=int, default=500, help="Max posts per brand")
    parser.add_argument("--headed", action="store_true")
    args = parser.parse_args()
    brands = BRANDS if "all" in args.brands else [b for b in args.brands if b in BRANDS]

    print("=" * 70)
    print("  V3 Facebook Fill Engagement — Post Detail Page (FIXED)")
    print(f"  Brands: {brands} | Limit: {args.limit}/brand")
    print("  FIX 1: Relative time → ISO conversion")
    print("  FIX 2: Wait longer for DOM render")
    print("  FIX 3: Multiple extraction methods")
    print("=" * 70)

    conn = get_conn()
    print_status(conn)

    ctx = open_context(headed=args.headed)
    page = ctx.new_page()
    total_filled = 0
    total_empty = 0
    total_err = 0

    try:
        for brand in brands:
            posts = get_posts_missing_engagement(conn, brand, args.limit)
            print(f"\n  [{brand}] Posts missing engagement: {len(posts)}")

            if not posts:
                print(f"  [{brand}] All posts have engagement!")
                continue

            filled = 0
            empty = 0
            consecutive_login = 0

            for i, (pid, purl) in enumerate(posts):
                status, l, c, s, t = fill_post(page, conn, pid, purl)

                if status == "login":
                    consecutive_login += 1
                    if consecutive_login >= 3:
                        print(f"    Login wall. Use --headed and login once.")
                        break
                    continue

                consecutive_login = 0

                if status == "empty":
                    empty += 1
                elif status == "filled":
                    filled += 1
                elif status.startswith("err"):
                    total_err += 1

                if (i + 1) % 5 == 0 or status == "filled":
                    if status == "filled":
                        print(f"    [{i+1}/{len(posts)}] {str(pid)[:18]}: "
                              f"L={l} C={c} S={s} T={t[:20] if t else '-'}")
                    else:
                        print(f"    [{i+1}/{len(posts)}] {str(pid)[:18]}: {status}")

                time.sleep(random.uniform(2, 4))

            total_filled += filled
            total_empty += empty
            print(f"  [{brand}] Filled: {filled}, Empty: {empty}")

    finally:
        try:
            page.close()
        except:
            pass
        safe_close(ctx)

    print_status(conn)

    # Show ML-ready improvement
    print("\n  ML-READY AFTER FILL:")
    for brand in brands:
        ml = conn.execute("""
            SELECT COUNT(*) FROM facebook_posts
            WHERE brand=? AND CAST(likes_count AS INTEGER)>0
            AND publish_time IS NOT NULL AND publish_time!=''
        """, (brand,)).fetchone()[0]
        total = conn.execute("SELECT COUNT(*) FROM facebook_posts WHERE brand=?", (brand,)).fetchone()[0]
        print(f"    {brand}: {ml}/{total} ({ml/max(total,1)*100:.0f}%)")

    # Verify timestamp quality
    iso_count = conn.execute("""
        SELECT COUNT(*) FROM facebook_posts
        WHERE crawl_source='fill-detail-page'
        AND publish_time LIKE '20%'
    """).fetchone()[0]
    relative_count = conn.execute("""
        SELECT COUNT(*) FROM facebook_posts
        WHERE crawl_source='fill-detail-page'
        AND publish_time IS NOT NULL AND publish_time != ''
        AND publish_time NOT LIKE '20%'
    """).fetchone()[0]
    print(f"\n  Timestamp quality: ISO={iso_count}, still_relative={relative_count}")

    print(f"\n  TOTAL: filled={total_filled}, empty={total_empty}, errors={total_err}")
    print("\n  Exporting CSVs...")
    export_csvs(conn)
    conn.close()


if __name__ == "__main__":
    main()