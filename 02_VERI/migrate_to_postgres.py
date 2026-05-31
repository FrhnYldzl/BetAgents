"""
SQLite → PostgreSQL VERİ TAŞIMA
================================
Yerel bahis_agent.db'deki TÜM tabloları PostgreSQL'e (Railway) taşır.

İntrospection tabanlı (PRAGMA table_info) — şema otomatik üretilir:
  - Tip eşleme: INTEGER→BIGINT, REAL→DOUBLE PRECISION, TEXT→TEXT, BLOB→BYTEA
  - AUTOINCREMENT PK → BIGSERIAL (sequence kopyadan sonra setval ile sıfırlanır)
  - Tarih/saat kolonları TEXT kalır (kod ISO-string karşılaştırması yapıyor)
  - FK kısıtları atlanır (uygulama FK enforcement'a bağlı değil; sıra sorununu önler)

Kullanım:
  # Hedef PostgreSQL DATABASE_URL ortam değişkeninde olmalı:
  set DATABASE_URL=postgresql://user:pass@host:port/dbname   (Windows)
  export DATABASE_URL=postgresql://...                        (Railway shell)

  python migrate_to_postgres.py            # tam taşıma (drop+create+copy)
  python migrate_to_postgres.py --verify   # sadece satır sayısı karşılaştır
  python migrate_to_postgres.py --only matches_v2,signal_snapshots

GÜVENLİK: DATABASE_URL .env'dedir, repo'ya girmez.
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SQLITE_PATH = THIS_DIR / "bahis_agent.db"

BATCH = 1000


# ============================================================
# TİP EŞLEME (SQLite → PostgreSQL)
# ============================================================

def pg_type(sqlite_type: str) -> str:
    t = (sqlite_type or "").upper()
    if "INT" in t:
        return "BIGINT"
    if "REAL" in t or "FLOA" in t or "DOUB" in t:
        return "DOUBLE PRECISION"
    if "NUMERIC" in t or "DECIMAL" in t:
        return "DOUBLE PRECISION"
    if "BLOB" in t:
        return "BYTEA"
    # CHAR/TEXT/CLOB/VARCHAR + bilinmeyen → TEXT (tarih kolonları dahil)
    return "TEXT"


def _q(ident: str) -> str:
    """PostgreSQL identifier quote."""
    return '"' + ident.replace('"', '""') + '"'


def _default_to_pg(dflt) -> str | None:
    """SQLite kolon default'unu PG'ye çevir (çift tırnak → tek tırnak)."""
    if dflt is None:
        return None
    s = str(dflt).strip()
    if s == "":
        return None
    # SQLite bazen string default'u çift tırnakla saklar: "active" → 'active'
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        inner = s[1:-1].replace("'", "''")
        return f"'{inner}'"
    return s


# ============================================================
# SQLITE İNTROSPECTION
# ============================================================

def list_tables(sconn) -> list[str]:
    rows = sconn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def table_is_autoinc(sconn, table: str) -> bool:
    r = sconn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return bool(r and r[0] and "AUTOINCREMENT" in r[0].upper())


def columns_info(sconn, table: str) -> list[dict]:
    out = []
    for cid, name, ctype, notnull, dflt, pk in sconn.execute(
        f'PRAGMA table_info("{table}")'
    ).fetchall():
        out.append({
            "name": name, "type": ctype, "notnull": notnull,
            "default": dflt, "pk": pk,
        })
    return out


def index_defs(sconn, table: str) -> list[str]:
    """Kullanıcı indekslerini generic CREATE INDEX olarak üret."""
    defs = []
    for seq, iname, unique, origin, partial in sconn.execute(
        f'PRAGMA index_list("{table}")'
    ).fetchall():
        if origin != "c":   # sadece CREATE INDEX ile yapılanlar (pk/unique constraint değil)
            continue
        cols = [r[2] for r in sconn.execute(f'PRAGMA index_info("{iname}")').fetchall()]
        if not cols:
            continue
        uniq = "UNIQUE " if unique else ""
        col_sql = ", ".join(_q(c) for c in cols)
        defs.append(
            f'CREATE {uniq}INDEX IF NOT EXISTS {_q(iname)} ON {_q(table)} ({col_sql});'
        )
    return defs


# ============================================================
# DDL ÜRETİMİ
# ============================================================

def build_create(table: str, cols: list[dict], autoinc: bool) -> str:
    pk_cols = [c["name"] for c in sorted(cols, key=lambda c: c["pk"]) if c["pk"]]
    single_int_pk = (len(pk_cols) == 1 and autoinc)

    lines = []
    for c in cols:
        name = _q(c["name"])
        if single_int_pk and c["name"] == pk_cols[0]:
            lines.append(f"{name} BIGSERIAL")
            continue
        typ = pg_type(c["type"])
        piece = f"{name} {typ}"
        dflt = _default_to_pg(c["default"])
        if dflt is not None:
            piece += f" DEFAULT {dflt}"
        if c["notnull"] and not c["pk"]:
            piece += " NOT NULL"
        lines.append(piece)

    if pk_cols:
        pk_sql = ", ".join(_q(c) for c in pk_cols)
        lines.append(f"PRIMARY KEY ({pk_sql})")

    body = ",\n  ".join(lines)
    return f"CREATE TABLE {_q(table)} (\n  {body}\n);"


# ============================================================
# TAŞIMA
# ============================================================

def migrate(only: list[str] | None = None):
    import psycopg2
    import psycopg2.extras

    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not (url.startswith("postgres://") or url.startswith("postgresql://")):
        sys.exit("HATA: DATABASE_URL PostgreSQL'e ayarlı değil.")

    if not SQLITE_PATH.exists():
        sys.exit(f"HATA: SQLite bulunamadı: {SQLITE_PATH}")

    sconn = sqlite3.connect(str(SQLITE_PATH))
    sconn.row_factory = sqlite3.Row
    pconn = psycopg2.connect(url)
    pconn.autocommit = False
    pcur = pconn.cursor()

    tables = list_tables(sconn)
    if only:
        tables = [t for t in tables if t in only]

    print(f"=== SQLite → PostgreSQL TAŞIMA ===")
    print(f"Kaynak: {SQLITE_PATH.name}  |  Tablo: {len(tables)}")
    print()

    report = []
    for table in tables:
        cols = columns_info(sconn, table)
        autoinc = table_is_autoinc(sconn, table)
        colnames = [c["name"] for c in cols]

        # 1) Tabloyu yeniden oluştur
        pcur.execute(f'DROP TABLE IF EXISTS {_q(table)} CASCADE;')
        pcur.execute(build_create(table, cols, autoinc))

        # 2) Veriyi kopyala
        src_rows = sconn.execute(f'SELECT * FROM "{table}"').fetchall()
        n = len(src_rows)
        if n:
            col_sql = ", ".join(_q(c) for c in colnames)
            insert_sql = f'INSERT INTO {_q(table)} ({col_sql}) VALUES %s'
            data = [tuple(r[c] for c in colnames) for r in src_rows]
            for i in range(0, n, BATCH):
                psycopg2.extras.execute_values(
                    pcur, insert_sql, data[i:i + BATCH], page_size=BATCH
                )

        # 3) İndeksler
        for idx in index_defs(sconn, table):
            try:
                pcur.execute(idx)
            except Exception as e:
                print(f"  ! indeks atlandı ({table}): {e}")
                pconn.rollback()
                # devam edebilmek için tabloyu tekrar commit'le
                pconn.commit()

        # 4) AUTOINCREMENT sequence'i sıfırla
        if autoinc:
            pk = [c["name"] for c in cols if c["pk"]]
            if len(pk) == 1:
                pcur.execute(
                    f"SELECT setval(pg_get_serial_sequence(%s, %s), "
                    f"COALESCE((SELECT MAX({_q(pk[0])}) FROM {_q(table)}), 1))",
                    (table, pk[0]),
                )

        pconn.commit()
        report.append((table, n))
        print(f"  ✓ {table:32} {n:>7} satır")

    # ── DOĞRULAMA ──
    print("\n=== DOĞRULAMA (SQLite vs PostgreSQL satır sayısı) ===")
    all_ok = True
    for table, n_src in report:
        pcur.execute(f'SELECT COUNT(*) FROM {_q(table)}')
        n_dst = pcur.fetchone()[0]
        ok = (n_src == n_dst)
        all_ok &= ok
        flag = "OK" if ok else "!! UYUMSUZ"
        print(f"  {table:32} src={n_src:>7}  dst={n_dst:>7}  {flag}")

    print("\n" + ("✅ TAŞIMA BAŞARILI — tüm satır sayıları uyumlu."
                  if all_ok else "⚠️ UYUMSUZLUK VAR — yukarıyı inceleyin."))
    pcur.close(); pconn.close(); sconn.close()


def verify_only():
    import psycopg2
    url = (os.environ.get("DATABASE_URL") or "").strip()
    sconn = sqlite3.connect(str(SQLITE_PATH)); sconn.row_factory = sqlite3.Row
    pconn = psycopg2.connect(url); pcur = pconn.cursor()
    print("=== DOĞRULAMA ===")
    for t in list_tables(sconn):
        n_src = sconn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        try:
            pcur.execute(f'SELECT COUNT(*) FROM {_q(t)}')
            n_dst = pcur.fetchone()[0]
        except Exception:
            n_dst = "YOK"
            pconn.rollback()
        print(f"  {t:32} src={n_src:>7}  dst={n_dst}")
    pcur.close(); pconn.close(); sconn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="Sadece satır sayısı karşılaştır")
    ap.add_argument("--only", type=str, help="Virgülle ayrılmış tablo listesi")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if args.verify:
        verify_only()
    else:
        only = [s.strip() for s in args.only.split(",")] if args.only else None
        migrate(only)
