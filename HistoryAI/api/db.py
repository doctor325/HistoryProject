"""API 只读查询层：每个请求开一个只读连接（数据库 = 派生物，绝不写库）。"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from scripts.pipeline import config


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    p = Path(db_path) if db_path else config.DB_PATH
    conn = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------------------------------------------ 书/文件
# 计数不做「每行一个相关子查询」（5 书 118 文件 × 多谓词 = 22 万行上重复扫多轮，
# 实测 /api/books ~0.9s）。改为：passages 单次 GROUP BY 聚合（全表一趟 <50ms），
# Python 侧按主键合并，输出字段与旧契约完全一致。

_BOOKS_BASE = """
SELECT b.book_id, b.book_dir, b.title, b.family, b.edition,
       (SELECT COUNT(*) FROM files f WHERE f.book_id = b.book_id) AS files
FROM books b ORDER BY b.book_id
"""
_BOOK_AGG = """
SELECT book_id,
       COUNT(*) AS records,
       COUNT(*) FILTER (WHERE kind = 'passage' AND layer = 'main') AS main_passages,
       COUNT(*) FILTER (WHERE status LIKE 'pending%') AS pending,
       COUNT(*) FILTER (WHERE kind = 'comment' AND source_ref_json IS NOT NULL)
         AS src_blocks,
       COUNT(*) FILTER (WHERE special_chars_json IS NOT NULL) AS kr_rows
FROM passages GROUP BY book_id
"""


def list_books(cur) -> list[dict]:
    base = {r["book_id"]: dict(r) for r in cur.execute(_BOOKS_BASE)}
    for r in cur.execute(_BOOK_AGG):
        base[r["book_id"]].update(dict(r))
    out = []
    for d in base.values():
        d.setdefault("records", 0); d.setdefault("main_passages", 0)
        d.setdefault("pending", 0); d.setdefault("src_blocks", 0)
        d.setdefault("kr_rows", 0)
        out.append(d)
    return out


def get_book(cur, book_id: str) -> dict | None:
    r = cur.execute("SELECT * FROM books WHERE book_id = ?", (book_id,)).fetchone()
    return dict(r) if r else None


_FILES_BASE = """
SELECT f.file_id, f.book_id, f.file_name, f.file_no, f.juan_prop, f.sha256,
       f.origin_path, f.meta_json
FROM files f
"""
_FILE_AGG = """
SELECT file_id,
       COUNT(*) AS records,
       COUNT(*) FILTER (WHERE kind = 'passage' AND layer = 'main') AS main,
       COUNT(*) FILTER (WHERE kind = 'passage'
                        AND layer = 'commentary_candidate') AS commentary,
       COUNT(*) FILTER (WHERE status LIKE 'pending%') AS pending,
       COUNT(*) FILTER (WHERE layer = 'preface') AS preface,
       COUNT(*) FILTER (WHERE layer IN ('backmatter', 'toc')) AS back,
       COUNT(*) FILTER (WHERE special_chars_json IS NOT NULL) AS kr_rows,
       MIN(pb_block) FILTER (WHERE pb_block IS NOT NULL) AS pb_lo,
       MAX(pb_block) FILTER (WHERE pb_block IS NOT NULL) AS pb_hi
FROM passages GROUP BY file_id
"""
_SRCREF_AGG = "SELECT file_id, COUNT(*) n FROM source_references GROUP BY file_id"
_FILES_WHERE = " WHERE f.book_id = ?"


def _merge_files(cur, base_rows: list[dict]) -> list[dict]:
    ids = [d["file_id"] for d in base_rows] or [-1]
    agg = {r["file_id"]: dict(r) for r in cur.execute(
        _FILE_AGG + " HAVING file_id IN (%s)" % ",".join("?" * len(ids)), ids)}
    refs = dict(cur.execute(
        _SRCREF_AGG + " HAVING file_id IN (%s)" % ",".join("?" * len(ids)), ids))
    out = []
    for d in base_rows:
        a = agg.get(d["file_id"], {})
        a.setdefault("records", 0); a.setdefault("main", 0)
        a.setdefault("commentary", 0); a.setdefault("pending", 0)
        a.setdefault("preface", 0); a.setdefault("back", 0)
        a.setdefault("kr_rows", 0)
        d.update(a)
        d["src_refs"] = refs.get(d["file_id"], 0)
        d["pb_range"] = f"{d['pb_lo']}-{d['pb_hi']}" if d.get("pb_lo") else None
        d.pop("pb_lo", None); d.pop("pb_hi", None)
        out.append(d)
    return out


def list_files(cur, book_id: str) -> list[dict]:
    base = [dict(r) for r in cur.execute(_FILES_BASE + _FILES_WHERE + " ORDER BY f.file_no",
                                         (book_id,))]
    return _merge_files(cur, base)


def get_file(cur, file_id: int) -> dict | None:
    r = cur.execute(_FILES_BASE + " WHERE f.file_id = ?", (file_id,)).fetchone()
    if not r:
        return None
    d = _merge_files(cur, [dict(r)])[0]
    try:
        import json
        d["meta"] = json.loads(d.pop("meta_json") or "{}")
    except ValueError:
        d["meta"] = {}
    d["kind_layer_counts"] = [dict(x) for x in cur.execute(
        "SELECT kind, layer, status, COUNT(*) n FROM passages WHERE file_id = ? "
        "GROUP BY kind, layer, status ORDER BY kind, layer", (file_id,))]
    return d


# ------------------------------------------------------------------ 记录

_FILTER_SQL = {"kind": "kind = ?", "layer": "layer = ?", "status": "status = ?",
               "section": "section = ?", "juan": "juan = ?", "q": "text_orig LIKE ?"}


def list_passages(cur, file_id: int, kind=None, layer=None, status=None,
                  q=None, offset: int = 0, limit: int = 100) -> dict:
    where, args = ["file_id = ?"], [file_id]
    for key, val in (("kind", kind), ("layer", layer), ("status", status)):
        if val:
            where.append(_FILTER_SQL[key])
            args.append(val)
    if q:
        where.append("text_orig LIKE ?")
        args.append(f"%{q}%")
    cond = " AND ".join(where)
    total = cur.execute(f"SELECT COUNT(*) FROM passages WHERE {cond}", args).fetchone()[0]
    rows = cur.execute(
        f"SELECT * FROM passages WHERE {cond} ORDER BY row_no, seq "
        f"LIMIT ? OFFSET ?", args + [limit, offset]).fetchall()
    return {"total": total, "offset": offset, "limit": limit,
            "rows": [dict(r) for r in rows]}


def get_passage(cur, passage_id: int) -> dict | None:
    r = cur.execute("SELECT * FROM passages WHERE passage_id = ?",
                    (passage_id,)).fetchone()
    return dict(r) if r else None
