"""
SELECTIVE EDGE v1.0 — iddaa.com endpoint discovery probe v2.

İlk turdaki keşif:
    - https://www.iddaa.com/ → 200 OK (Next.js)
    - //sportsbook.iddaa.com ve //contentv2.iddaa.com referans var
    - Sayfa yapısı:
        /program/futbol             — futbol bülten
        /yazar-yorumlari            — yorumcular ana sayfa
        /populer-bahisler/futbol    — popüler bahisler
        /lig-analiz/puan-durumu/... — lig analizi
        /canli-skor/futbol          — canlı skor

Bu v2 probe, GERÇEK Next.js yollarını test eder ve __NEXT_DATA__ içeriğini
detaylı çözer.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from urllib import request, error

THIS_DIR = Path(__file__).resolve().parent
PROBE_CACHE = THIS_DIR / "iddaa_probe_cache"
PROBE_CACHE.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "identity",   # gzip kapat (kolay debug)
    "Referer": "https://www.iddaa.com/",
}


PROBE_TARGETS = [
    # GERÇEK Next.js sayfaları (homepage'den bulundu)
    ("program_futbol", "https://www.iddaa.com/program/futbol"),
    ("yazar_yorumlari", "https://www.iddaa.com/yazar-yorumlari"),
    ("populer_bahisler", "https://www.iddaa.com/populer-bahisler/futbol"),
    ("canli_skor", "https://www.iddaa.com/canli-skor/futbol"),
    ("kolay_kuponlar", "https://www.iddaa.com/kolay-kuponlar"),

    # Subdomain'ler (referans olarak gözüktü)
    ("contentv2_root", "https://contentv2.iddaa.com/"),
    ("sportsbook_root", "https://sportsbook.iddaa.com/"),

    # iOS app gateway tahminleri
    ("contentv2_api", "https://contentv2.iddaa.com/api/sportsbook/events"),
    ("contentv2_v1", "https://contentv2.iddaa.com/api/v1/sportsbook/events"),
    ("sportsbook_api", "https://sportsbook.iddaa.com/api/sportsbook/events"),

    # Lig analiz (puan durumu)
    ("puan_durumu", "https://www.iddaa.com/lig-analiz/puan-durumu/turkiye-super-lig"),
]


def fetch(url: str, timeout: int = 15) -> tuple[int, str, dict]:
    req = request.Request(url, headers=HEADERS)
    try:
        with request.urlopen(req, timeout=timeout) as r:
            body = r.read().decode("utf-8", errors="replace")
            return r.status, body, dict(r.headers)
    except error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        return e.code, body or f"HTTP_ERROR: {e.reason}", dict(e.headers) if e.headers else {}
    except Exception as e:
        return 0, f"EXCEPTION: {e}", {}


def extract_next_data(html: str) -> dict | None:
    marker = '__NEXT_DATA__" type="application/json">'
    start = html.find(marker)
    if start < 0:
        return None
    start += len(marker)
    end = html.find("</script>", start)
    if end < 0:
        return None
    try:
        return json.loads(html[start:end])
    except Exception:
        return None


def deep_keys(obj, prefix="", max_depth=4, depth=0):
    """Bir dict ağacında tüm anahtarları (prefix'li) listele."""
    out = []
    if depth >= max_depth:
        return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            out.append(full)
            out.extend(deep_keys(v, full, max_depth, depth + 1))
    elif isinstance(obj, list) and obj:
        out.extend(deep_keys(obj[0], prefix + "[0]", max_depth, depth + 1))
    return out


def probe_all():
    print("=" * 70)
    print("IDDAA.COM ENDPOINT PROBE v2")
    print("=" * 70)

    for name, url in PROBE_TARGETS:
        print(f"\n[{name}] {url}")
        status, body, headers = fetch(url)
        ctype = headers.get("Content-Type", "?")
        size = len(body)

        is_json = "json" in ctype.lower() or body.lstrip().startswith(("{", "["))

        print(f"  Status: {status}    Boyut: {size:>8,} byte    Type: {ctype}")

        if status == 200 and is_json:
            try:
                data = json.loads(body)
                print(f"  JSON [OK]")
                if isinstance(data, dict):
                    print(f"  Top-level: {list(data.keys())[:15]}")
                    print(f"  Deep keys (max 4):")
                    for k in deep_keys(data, max_depth=3)[:30]:
                        print(f"    - {k}")
                elif isinstance(data, list):
                    print(f"  Liste len: {len(data)}")
                    if data:
                        print(f"  Ilk elem: {json.dumps(data[0], ensure_ascii=False)[:300]}")
            except Exception as e:
                print(f"  JSON parse hata: {e}")

        elif status == 200 and "html" in ctype.lower():
            nd = extract_next_data(body)
            if nd:
                page_props = nd.get("props", {}).get("pageProps", {})
                print(f"  __NEXT_DATA__ var. pageProps keys: {list(page_props.keys())[:15]}")
                # Detayli dump (DİKKAT: buyuk olabilir)
                dump_name = name + ".nextdata.json"
                (PROBE_CACHE / dump_name).write_text(
                    json.dumps(nd, ensure_ascii=False, indent=2)[:200_000],
                    encoding="utf-8"
                )
                print(f"  __NEXT_DATA__ dump: {dump_name}")

                # build manifest'ten _next/data path bul
                build_id = nd.get("buildId")
                if build_id:
                    print(f"  buildId: {build_id}")
            else:
                # 200 ama __NEXT_DATA__ yok? muhtemelen redirect/CDN
                snippet = body[:300].replace("\n", " ")
                print(f"  __NEXT_DATA__ yok. Onsoz: {snippet}")

        safe_name = name.replace("/", "_")
        (PROBE_CACHE / f"{safe_name}.txt").write_text(
            f"URL: {url}\nSTATUS: {status}\n\n{body[:80_000]}",
            encoding="utf-8", errors="replace"
        )

        time.sleep(0.5)


if __name__ == "__main__":
    probe_all()
