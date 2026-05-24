import json, time, random, re, argparse, hashlib, sys
from datetime import datetime
from pathlib import Path
from curl_cffi import requests as cffi_requests
from bs4 import BeautifulSoup
sys.path.insert(0, str(Path(__file__).parent))
from v3_config import *

IMPERSONATE = ["chrome", "chrome110", "chrome116", "chrome120"]

def load_fb_cookies():
    if not STATE_FILE.exists():
        print("  ERROR: No FB cookies"); return None
    with open(STATE_FILE) as f: data = json.load(f)
    cs = "; ".join(f"{c['name']}={c['value']}" for c in data.get("cookies",[]) if c.get("domain","").endswith("facebook.com"))
    print(f"  Loaded {len(data.get('cookies',[]))} FB cookies")
    return cs

def to_mbasic(url):
    if not url: return None
    url = str(url).split("?")[0]
    for old in ["www.facebook.com","m.facebook.com","web.facebook.com"]:
        url = url.replace(old, "mbasic.facebook.com")
    return url

def get_posts(conn, brand, top_n=100):
    sql = """
        SELECT fp.post_id, fp.post_url, fp.comments_count, COALESCE(fc.cnt,0)
        FROM facebook_posts fp
        LEFT JOIN (SELECT post_id, COUNT(*) cnt FROM facebook_comments WHERE brand=? GROUP BY post_id) fc
        ON fp.post_id=fc.post_id
        WHERE fp.brand=? AND fp.post_url IS NOT NULL AND fp.post_url!=''
          AND CAST(COALESCE(fp.comments_count,0) AS INTEGER)>2
        ORDER BY CASE WHEN COALESCE(fc.cnt,0)=0 THEN 0 ELSE 1 END,
                 (CAST(COALESCE(fp.comments_count,0) AS INTEGER)-COALESCE(fc.cnt,0)) DESC
        LIMIT ?"""
    return conn.execute(sql, (brand, brand, top_n)).fetchall()

def crawl_mbasic(post_url, post_id, brand, cookie_str, max_cmt=300):
    comments, seen = [], set()
    url = to_mbasic(post_url)
    if not url: return comments
    hdrs = {"Accept":"text/html", "Accept-Language":"vi-VN,vi;q=0.9",
            "Cookie":cookie_str, "Referer":"https://mbasic.facebook.com/"}
    for page in range(15):
        if len(comments)>=max_cmt: break
        try:
            r = cffi_requests.get(url, headers=hdrs,
                impersonate=random.choice(IMPERSONATE), timeout=20, allow_redirects=True)
            if r.status_code==302 or "login" in r.url.lower():
                print("      Login redirect"); break
            if r.status_code!=200: break
            soup = BeautifulSoup(r.text, "html.parser")
            divs = soup.find_all("div", {"id": re.compile(r"^[0-9]+$")})
            if not divs: divs = soup.find_all("div", attrs={"data-sigil":"comment"})
            pn = 0
            for d in divs:
                body = d.find("div", attrs={"data-sigil":"comment-body"})
                if body: txt = body.get_text(strip=True)
                else:
                    parts = [s.get_text(strip=True) for s in d.find_all("span") if len(s.get_text(strip=True))>1]
                    txt = " ".join(parts[:3])
                if not txt or len(txt)<2: continue
                th = hashlib.md5(txt.encode()).hexdigest()[:16]
                if th in seen: continue
                seen.add(th)
                au = ""
                at = d.find("h3") or d.find("a")
                if at: au = at.get_text(strip=True)[:100]
                cid = d.get("id","")
                if not cid or not cid.isdigit():
                    cid = hashlib.md5(f"{post_id}_{txt[:60]}_{au}".encode()).hexdigest()[:20]
                comments.append((cid, post_id, brand, txt[:2000], 0, 0, None, au))
                pn += 1
                if len(comments)>=max_cmt: break
            if pn==0 and page==0:
                blocks = []
                for tag in soup.find_all(["div","span"]):
                    t = tag.get_text(strip=True)
                    if 5<len(t)<500 and not any(s in t.lower() for s in
                        ["like","reply","comment","share","facebook","log in","thich","binh luan","chia se"]):
                        th = hashlib.md5(t.encode()).hexdigest()[:16]
                        if th not in seen: seen.add(th); blocks.append(t)
                for t in blocks[3:]:
                    cid = hashlib.md5(f"{post_id}_{t[:60]}".encode()).hexdigest()[:20]
                    comments.append((cid, post_id, brand, t[:2000], 0, 0, None, ""))
                    if len(comments)>=max_cmt: break
            nxt = None
            for a in soup.find_all("a", href=True):
                lt = a.get_text(strip=True).lower()
                if any(k in lt for k in ["xem them","view more","previous","truoc","more comment"]):
                    h = a["href"]
                    nxt = ("https://mbasic.facebook.com"+h) if h.startswith("/") else (h if h.startswith("http") else None)
                    break
            if nxt and nxt!=url: url=nxt; time.sleep(random.uniform(1.5,3))
            else: break
        except Exception as e:
            if "timeout" in str(e).lower(): break
            print(f"      Error: {e}"); break
    return comments

def main():
    pa = argparse.ArgumentParser()
    pa.add_argument("--brands", nargs="+", choices=BRANDS+["all"], default=["all"])
    pa.add_argument("--top-n", type=int, default=80)
    pa.add_argument("--max-cmt", type=int, default=300)
    a = pa.parse_args()
    brands = BRANDS if "all" in a.brands else [b for b in a.brands if b in BRANDS]
    print("="*70)
    print("  V3 Facebook Comments - curl_cffi + mbasic.facebook.com")
    print(f"  Brands: {brands} | Top-N: {a.top_n} | FAST mode")
    print("="*70)
    cs = load_fb_cookies()
    if not cs: return
    conn = get_conn(); print_status(conn); ga = 0
    for brand in brands:
        print(f"\n{'~'*70}\n  [{brand}] Facebook Comments\n{'~'*70}")
        posts = get_posts(conn, brand, a.top_n)
        print(f"  Posts: {len(posts)}")
        if not posts: continue
        before = conn.execute("SELECT COUNT(*) FROM facebook_comments WHERE brand=?",(brand,)).fetchone()[0]
        zs = 0
        for i,(pid,purl,rep,ex) in enumerate(posts):
            rep,ex = int(rep or 0), int(ex or 0)
            cmts = crawl_mbasic(purl, pid, brand, cs, a.max_cmt)
            if cmts:
                for c in cmts:
                    try: conn.execute("INSERT OR IGNORE INTO facebook_comments (comment_id,post_id,brand,comment_text,like_count,reply_count,create_time,user_name) VALUES (?,?,?,?,?,?,?,?)", c)
                    except: pass
                conn.commit()
                af = conn.execute("SELECT COUNT(*) FROM facebook_comments WHERE brand=? AND post_id=?",(brand,pid)).fetchone()[0]
                an = af - ex; zs = 0
                print(f"    [{i+1}/{len(posts)}] {str(pid)[:18]}: +{an} new (parsed={len(cmts)}, had={ex}, ~{rep})")
            else:
                zs += 1
                if zs<=5: print(f"    [{i+1}/{len(posts)}] {str(pid)[:18]}: 0 (~{rep})")
                if zs>=10: print("    Stopping - too many zeros"); break
            time.sleep(random.uniform(2,4) if zs<3 else random.uniform(5,8))
        after = conn.execute("SELECT COUNT(*) FROM facebook_comments WHERE brand=?",(brand,)).fetchone()[0]
        act = after-before; ga += act
        print(f"  [{brand}] Actual new: +{act} (total: {after})")
    print_status(conn)
    print(f"\n  SESSION ACTUAL NEW: +{ga}")
    print("\n  Exporting..."); export_csvs(conn); conn.close()

if __name__=="__main__": main()