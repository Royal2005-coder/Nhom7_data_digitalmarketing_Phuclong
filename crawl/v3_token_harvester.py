#!/usr/bin/env python3
"""
V3 Token Harvester — FIXED for Windows
- safe_close_context() prevents crash
- Gets msToken (main goal) — video IDs from CSV, not scroll
"""
import json, time, random
from datetime import datetime
from cloakbrowser import launch_persistent_context
from v3_config import *


def harvest_tokens(brand, timeout=45):
    """Visit TikTok → extract msToken + cookies. Skip video scroll."""
    profile_path = str(PROFILE_DIR / f"tiktok_{brand}")
    url = TIKTOK_PROFILES[brand]

    print(f"\n  [{brand}] Harvesting msToken from {url}")

    tokens = {"brand": brand, "timestamp": datetime.now().isoformat(),
              "cookies": [], "ms_token": None}

    ctx = None
    try:
        ctx = launch_persistent_context(
            profile_path,
            headless=True,
            humanize=True,
            locale="vi-VN",
            timezone="Asia/Ho_Chi_Minh",
            viewport={"width": 1280, "height": 900},
        )
        page = ctx.new_page()

        # Visit profile — just need cookies, not video list
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        time.sleep(random.uniform(5, 8))

        # Extract cookies
        cookies = ctx.cookies()
        tokens["cookies"] = [
            {"name": c["name"], "value": c["value"], "domain": c["domain"]}
            for c in cookies
        ]

        # Find msToken
        for c in cookies:
            if c["name"] == "msToken":
                tokens["ms_token"] = c["value"]
                print(f"    ✓ msToken: {c['value'][:40]}...")
                break

        # Fallback: try JS extraction
        if not tokens["ms_token"]:
            try:
                ms = page.evaluate("""() => {
                    const m = document.cookie.match(/msToken=([^;]+)/);
                    return m ? m[1] : null;
                }""")
                if ms:
                    tokens["ms_token"] = ms
                    print(f"    ✓ msToken (JS): {ms[:40]}...")
            except:
                pass

        # Light scroll to make session look real (but don't wait for XHR)
        for _ in range(3):
            page.mouse.wheel(0, random.randint(500, 1000))
            time.sleep(random.uniform(1, 2))

    except Exception as e:
        print(f"    ✗ Error: {e}")
    finally:
        if ctx:
            safe_close_context(ctx)

    if not tokens["ms_token"]:
        print(f"    ⚠ No msToken found for {brand}")

    return tokens


def harvest_all():
    """Harvest tokens for all brands."""
    all_tokens = {}

    for brand in BRANDS:
        tokens = harvest_tokens(brand)
        all_tokens[brand] = tokens
        print(f"  [{brand}] msToken={'✓' if tokens['ms_token'] else '✗'}, "
              f"cookies={len(tokens['cookies'])}")
        time.sleep(random.uniform(3, 5))

    # Save
    TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(TOKEN_FILE, 'w') as f:
        json.dump(all_tokens, f, indent=2, default=str)
    print(f"\n  ✓ Tokens saved to {TOKEN_FILE}")
    return all_tokens


def load_tokens():
    """Load cached tokens. Returns None if expired (>25 min)."""
    if not TOKEN_FILE.exists():
        return None
    try:
        with open(TOKEN_FILE) as f:
            data = json.load(f)
        for brand, t in data.items():
            ts = datetime.fromisoformat(t["timestamp"])
            age_min = (datetime.now() - ts).total_seconds() / 60
            if age_min > 25:
                print(f"  ⚠ Tokens expired ({age_min:.0f} min). Re-harvest needed.")
                return None
        return data
    except:
        return None


if __name__ == "__main__":
    print("=" * 60)
    print("  V3 TOKEN HARVESTER — CloakBrowser → TikTok")
    print("=" * 60)
    harvest_all()
    print("\n  DONE!")