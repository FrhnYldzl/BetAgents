"""
iddaa.com Match Detail API Probe
Fetches JS chunks, finds API base URL, then calls all discovered endpoints
for event 2975498.
"""
import urllib.request
import sys
import re
import json

sys.stdout.reconfigure(encoding="utf-8")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "tr-TR,tr;q=0.9",
    "Referer": "https://www.iddaa.com/",
}

EVENT_ID = "2975498"


def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace"), r.headers


# ── Step 1: Get app JS to find API base URL ──────────────────
print("=" * 60)
print("STEP 1: App JS'den API base URL bul")
print("=" * 60)

app_chunks = [
    "pages/_app-a3135a23cf32e106.js",
    "9577-aea0b5183f26eedb.js",
    "4379-c3a4c04bcea657a7.js",
    "7410-19b1979f59666a66.js",
    "8073-d52c6a2b9335a3d3.js",
]

api_base = None
for chunk in app_chunks:
    url = f"https://s.iddaa.com/_next/static/chunks/{chunk}"
    try:
        js, _ = fetch(url, timeout=12)
        # Look for API base patterns
        matches = re.findall(
            r'(?:apiUrl|baseUrl|API_URL|BASE_URL|apiBase|serviceUrl)'
            r'\s*[:=]\s*["\']([^"\']{10,80})["\']', js
        )
        for m in matches:
            print(f"  Found in {chunk}: {m}")
            if "iddaa" in m.lower():
                api_base = m
        # Also find any iddaa API domain
        iddaa_apis = re.findall(r'"(https?://[a-z][a-z0-9.-]*iddaa[a-z0-9.-]*\.(?:com|net|org)[^"]{0,60})"', js)
        for a in list(dict.fromkeys(iddaa_apis)):
            print(f"  API ref in {chunk}: {a}")
            if not api_base and "api" in a.lower():
                api_base = a.rstrip("/")
    except Exception as e:
        print(f"  SKIP {chunk}: {e}")

print()

# ── Step 2: Try all known iddaa API patterns ─────────────────
print("=" * 60)
print("STEP 2: Bilinen API pattern'lari dene")
print("=" * 60)

# Try fetching the data API that Next.js SSG uses
next_api_urls = [
    f"https://www.iddaa.com/_next/data/qxAnPN2FXhDcZeiAOrJRH/program/futbol/mac-detay/2/{EVENT_ID}/maclar.json",
    f"https://www.iddaa.com/_next/data/qxAnPN2FXhDcZeiAOrJRH/program/futbol/mac-detay/2/{EVENT_ID}/istatistikler.json",
    f"https://www.iddaa.com/_next/data/qxAnPN2FXhDcZeiAOrJRH/program/futbol/mac-detay/2/{EVENT_ID}/kadrolar.json",
    f"https://www.iddaa.com/_next/data/qxAnPN2FXhDcZeiAOrJRH/program/futbol/mac-detay/2/{EVENT_ID}/h2h.json",
]

working_apis = {}
for url in next_api_urls:
    try:
        data, hdrs = fetch(url, timeout=12)
        print(f"  OK [{len(data)}] {url.split('/')[-1]}")
        try:
            j = json.loads(data)
            # Print structure
            def show_keys(d, prefix="", depth=0):
                if depth > 3:
                    return
                if isinstance(d, dict):
                    for k, v in list(d.items())[:15]:
                        t = type(v).__name__
                        if isinstance(v, (dict, list)):
                            cnt = len(v)
                            print(f"    {'  '*depth}{prefix}{k}: {t}({cnt})")
                            show_keys(v, "", depth+1)
                        else:
                            val_str = str(v)[:60] if v is not None else "null"
                            print(f"    {'  '*depth}{prefix}{k}: {val_str}")
                elif isinstance(d, list) and len(d) > 0:
                    print(f"    {'  '*depth}[list of {len(d)}, first item keys: {list(d[0].keys()) if isinstance(d[0], dict) else type(d[0]).__name__}]")
            show_keys(j)
            working_apis[url] = j
        except json.JSONDecodeError:
            print(f"    (HTML response, not JSON)")
            print(f"    First 200: {data[:200]}")
    except Exception as e:
        print(f"  FAIL {url.split('/')[-1]}: {type(e).__name__}: {str(e)[:60]}")

print()

# ── Step 3: indir.iddaa.com API ──────────────────────────────
print("=" * 60)
print("STEP 3: indir.iddaa.com API endpoints")
print("=" * 60)

indir_endpoints = [
    f"https://indir.iddaa.com/macdetay/event/{EVENT_ID}",
    f"https://indir.iddaa.com/macdetay/{EVENT_ID}",
    f"https://indir.iddaa.com/gunluk/event/{EVENT_ID}",
    f"https://indir.iddaa.com/karsilastirma/{EVENT_ID}",
    f"https://indir.iddaa.com/istatistik/{EVENT_ID}",
    f"https://indir.iddaa.com/kadro/{EVENT_ID}",
    "https://indir.iddaa.com/",
    "https://indir.iddaa.com/gunluk",
]

for url in indir_endpoints:
    try:
        data, hdrs = fetch(url, timeout=8)
        ct = hdrs.get("content-type", "")
        print(f"  OK [{len(data)}] {ct[:30]} → {url}")
        if "json" in ct:
            try:
                j = json.loads(data)
                print(f"    Keys: {list(j.keys()) if isinstance(j, dict) else f'list({len(j)})'}")
            except: pass
        elif len(data) < 500:
            print(f"    Body: {data[:200]}")
    except Exception as e:
        print(f"  FAIL {url}: {type(e).__name__}: {str(e)[:60]}")

print()

# ── Step 4: Scrape match detail page for section tabs ────────
print("=" * 60)
print("STEP 4: Sayfa HTML'den tab/section yapısı")
print("=" * 60)

try:
    html, _ = fetch(
        "https://www.iddaa.com/program/futbol/mac-detay/2/2975498/maclar",
        timeout=15
    )
    # Tab links
    tabs = re.findall(r'href="(/program/futbol/mac-detay/[^"]+)"', html)
    print("  Tabs bulunan:")
    for t in list(dict.fromkeys(tabs)):
        print(f"    {t}")
    # Data attributes
    data_attrs = re.findall(r'data-[a-z-]+="([^"]{3,60})"', html)
    unique_da = list(dict.fromkeys(data_attrs))[:20]
    print(f"\n  data-* attributes ({len(unique_da)} benzersiz):")
    for da in unique_da:
        print(f"    {da}")
except Exception as e:
    print(f"  HATA: {e}")

print()
print("=" * 60)
print("PROBE TAMAMLANDI")
print("=" * 60)
