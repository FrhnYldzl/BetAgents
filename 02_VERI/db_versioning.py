"""
EKSEN 1 — Database Versioning System
=====================================

Her büyük data değişikliğinde otomatik snapshot + manifest.
Başka projelerde de kullanılabilir, taşınabilir.

Snapshot formatı:
    snapshots/v{major}.{minor}_{YYYYMMDD}_{tag}/
        database.db.gz       — gzipped sqlite
        manifest.json        — schema + counts + version meta
        DATA_DICTIONARY.md   — bu snapshot için doc
        readme.md            — neden alındı, ne içerir
"""
from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
SNAPSHOTS_DIR = THIS_DIR / "snapshots"
DB_PATH = THIS_DIR / "bahis_agent.db"

SNAPSHOTS_DIR.mkdir(exist_ok=True)


def get_schema_summary(conn):
    """Tüm tabloların şema + satır sayısı."""
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    schema = {}
    for (table_name,) in tables:
        if table_name.startswith("sqlite_"):
            continue
        # Columns
        cols = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        col_info = [
            {"name": c[1], "type": c[2], "notnull": bool(c[3]),
             "pk": bool(c[5]), "default": c[4]}
            for c in cols
        ]
        # Row count
        n_rows = conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        # Index info
        indices = conn.execute(
            f"SELECT name FROM sqlite_master WHERE type='index' AND tbl_name=?",
            (table_name,)
        ).fetchall()
        schema[table_name] = {
            "columns": col_info,
            "n_columns": len(col_info),
            "n_rows": n_rows,
            "indices": [i[0] for i in indices],
        }
    return schema


def get_db_hash(db_path):
    """MD5 hash of database file (integrity check)."""
    md5 = hashlib.md5()
    with open(db_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def create_snapshot(version_tag: str = None, reason: str = "manual",
                    description: str = None) -> Path:
    """
    Database snapshot al.

    Args:
        version_tag: 'v2.0' gibi. None ise auto: 'v{date}_{hash6}'
        reason: 'manual' | 'sprint_complete' | 'pre_v2_retrain' | etc
        description: snapshot için açıklama (readme'ye yazılır)
    """
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH}")

    # Version tag
    now = datetime.now()
    date_str = now.strftime("%Y%m%d_%H%M")
    db_hash = get_db_hash(DB_PATH)[:8]
    if version_tag is None:
        version_tag = f"auto_{date_str}_{db_hash[:6]}"
    snapshot_name = f"{version_tag}_{date_str}"

    snapshot_dir = SNAPSHOTS_DIR / snapshot_name
    if snapshot_dir.exists():
        print(f"[WARN] {snapshot_name} already exists, skipping")
        return snapshot_dir

    snapshot_dir.mkdir(parents=True)
    print(f"[1] Snapshot oluşturuluyor: {snapshot_name}")

    # 1) Copy database (gzipped)
    print(f"    [a] DB compress + copy...")
    db_gz = snapshot_dir / "database.db.gz"
    with open(DB_PATH, "rb") as fin, gzip.open(db_gz, "wb", compresslevel=6) as fout:
        shutil.copyfileobj(fin, fout)
    db_size_mb = db_gz.stat().st_size / 1024 / 1024
    print(f"        OK ({db_size_mb:.1f} MB compressed)")

    # 2) Manifest
    print(f"    [b] Manifest...")
    conn = sqlite3.connect(DB_PATH)
    schema = get_schema_summary(conn)
    conn.close()

    manifest = {
        "snapshot_name": snapshot_name,
        "version_tag": version_tag,
        "timestamp": now.isoformat(),
        "reason": reason,
        "description": description or "",
        "db_hash_md5": db_hash,
        "db_size_bytes": DB_PATH.stat().st_size,
        "db_size_compressed_bytes": db_gz.stat().st_size,
        "tables": schema,
        "total_tables": len(schema),
        "total_rows": sum(t["n_rows"] for t in schema.values()),
    }
    (snapshot_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"        OK ({len(schema)} tables, {manifest['total_rows']:,} rows)")

    # 3) Readme
    print(f"    [c] Readme...")
    readme = [f"# Snapshot: {snapshot_name}\n\n"]
    readme.append(f"**Tarih:** {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
    readme.append(f"**Sebep:** {reason}\n")
    if description:
        readme.append(f"**Açıklama:** {description}\n")
    readme.append(f"\n## Özet\n\n")
    readme.append(f"- Toplam tablo: {len(schema)}\n")
    readme.append(f"- Toplam satır: {manifest['total_rows']:,}\n")
    readme.append(f"- DB boyut: {db_size_mb:.1f} MB (gzip)\n")
    readme.append(f"- DB hash (MD5): `{db_hash}`\n\n")

    readme.append(f"## Tablolar\n\n")
    readme.append("| Tablo | Kolon | Satır |\n|---|---|---|\n")
    for tname in sorted(schema.keys()):
        t = schema[tname]
        readme.append(f"| {tname} | {t['n_columns']} | {t['n_rows']:,} |\n")

    readme.append(f"\n## Geri Yükleme\n\n")
    readme.append(f"```bash\n")
    readme.append(f"cd snapshots/{snapshot_name}\n")
    readme.append(f"gunzip -k database.db.gz\n")
    readme.append(f"mv database.db ../../bahis_agent.db\n")
    readme.append(f"```\n")

    (snapshot_dir / "readme.md").write_text("".join(readme), encoding="utf-8")
    print(f"        OK")

    print(f"\n[OK] Snapshot: {snapshot_dir}")
    return snapshot_dir


def list_snapshots():
    """Mevcut snapshot'ları listele."""
    print(f"\n{'Snapshot':<40s} {'Tablo':>6s} {'Satir':>10s} {'Boyut':>10s}")
    print("-" * 80)
    for snap in sorted(SNAPSHOTS_DIR.iterdir()):
        if not snap.is_dir(): continue
        manifest = snap / "manifest.json"
        if not manifest.exists(): continue
        m = json.loads(manifest.read_text(encoding="utf-8"))
        size_mb = m.get("db_size_compressed_bytes", 0) / 1024 / 1024
        print(f"{snap.name:<40s} {m['total_tables']:>6d} "
              f"{m['total_rows']:>10,} {size_mb:>8.1f}MB")


def restore_snapshot(snapshot_name: str, target_path: Path = None):
    """Bir snapshot'ı geri yükle."""
    snap_dir = SNAPSHOTS_DIR / snapshot_name
    if not snap_dir.exists():
        raise FileNotFoundError(f"Snapshot not found: {snap_dir}")

    db_gz = snap_dir / "database.db.gz"
    if not db_gz.exists():
        raise FileNotFoundError(f"DB compressed file missing")

    target = target_path or DB_PATH
    backup = target.with_suffix(".db.before_restore")
    if target.exists():
        print(f"[1] Mevcut DB yedekleniyor: {backup}")
        shutil.copy2(target, backup)

    print(f"[2] {snapshot_name} restore ediliyor -> {target}")
    with gzip.open(db_gz, "rb") as fin, open(target, "wb") as fout:
        shutil.copyfileobj(fin, fout)

    print(f"[OK] Restore tamam. Yedek: {backup}")


def auto_snapshot_if_changed(min_change_pct: float = 5.0):
    """Son snapshot'tan beri %5+ değişim varsa yeni snapshot."""
    snaps = sorted([d for d in SNAPSHOTS_DIR.iterdir() if d.is_dir()])
    if not snaps:
        # İlk snapshot
        return create_snapshot(version_tag="v0_initial",
                              reason="initial",
                              description="İlk otomatik snapshot")

    latest = snaps[-1]
    manifest_path = latest / "manifest.json"
    if not manifest_path.exists():
        return create_snapshot(version_tag="v_recovery",
                              reason="recovery",
                              description="Latest snapshot manifest eksik")

    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    latest_rows = m["total_rows"]

    conn = sqlite3.connect(DB_PATH)
    schema = get_schema_summary(conn)
    conn.close()
    current_rows = sum(t["n_rows"] for t in schema.values())

    delta_pct = abs(current_rows - latest_rows) / max(1, latest_rows) * 100
    print(f"Son snapshot: {m['snapshot_name']} ({latest_rows:,} satir)")
    print(f"Suanki DB:    {current_rows:,} satir")
    print(f"Delta: {delta_pct:.1f}% (esik {min_change_pct}%)")

    if delta_pct >= min_change_pct:
        return create_snapshot(
            reason="auto_changed",
            description=f"{delta_pct:.1f}% degisim son snapshot'tan beri"
        )
    else:
        print("[OK] Anlamli degisim yok, snapshot atlandi")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    p_create = sub.add_parser("create", help="Snapshot oluştur")
    p_create.add_argument("--tag", default=None)
    p_create.add_argument("--reason", default="manual")
    p_create.add_argument("--desc", default=None)

    p_list = sub.add_parser("list", help="Snapshot'ları listele")

    p_restore = sub.add_parser("restore", help="Snapshot restore et")
    p_restore.add_argument("snapshot_name")

    p_auto = sub.add_parser("auto", help="Anlamlı değişim varsa snapshot")
    p_auto.add_argument("--min-pct", type=float, default=5.0)

    args = parser.parse_args()

    if args.cmd == "create":
        create_snapshot(version_tag=args.tag, reason=args.reason,
                       description=args.desc)
    elif args.cmd == "list":
        list_snapshots()
    elif args.cmd == "restore":
        restore_snapshot(args.snapshot_name)
    elif args.cmd == "auto":
        auto_snapshot_if_changed(min_change_pct=args.min_pct)
    else:
        # Default: list
        list_snapshots()
