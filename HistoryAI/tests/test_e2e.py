"""Step 10 — 端到端：JSONL→SQLite(临时库)、validate 全量对账、API 只读抽查。

前提：data/processed/parsed_*.jsonl 与 data/database/history.db 已由 run_all 生成
（缺则跳过本文件；重建命令见 README）。
"""
import json
import sqlite3
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from scripts.pipeline import config
from scripts.pipeline.validate import run_validation

HAS_OUTPUTS = config.DB_PATH.is_file() and len(list(config.PROCESSED_DIR.glob("parsed_*.jsonl"))) == 5


@unittest.skipUnless(HAS_OUTPUTS, "先运行 python -m scripts.pipeline.run_all 生成产物")
class TestDbLoader(unittest.TestCase):
    def test_rebuild_into_throwaway_db(self):
        from scripts.pipeline.sqlite_store import rebuild
        with tempfile.TemporaryDirectory() as td:
            stats = rebuild(Path(td) / "t.db")
            self.assertEqual(stats["books"], 5)
            self.assertEqual(stats["files"], 118)
            self.assertGreater(stats["records"], 220_000)
            self.assertGreater(stats["passages"], 200_000)
            conn = sqlite3.connect(Path(td) / "t.db")
            # 与正式库同 schema、同重建逻辑
            self.assertEqual(
                conn.execute("SELECT COUNT(*) FROM kr_chars").fetchone()[0], stats["kr_codes"])
            conn.close()

    def test_db_counts_match_metadata(self):
        import sqlite3
        conn = sqlite3.connect(str(config.DB_PATH))
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM books").fetchone()[0], 5)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM files").fetchone()[0], 118)
        # 正式库导出的 import_runs 记录应与库内记录数一致
        run = conn.execute("SELECT n_records, status FROM import_runs "
                           "ORDER BY ran_at DESC LIMIT 1").fetchone()
        self.assertEqual(run[1], "ok")
        self.assertEqual(run[0], conn.execute("SELECT COUNT(*) FROM passages").fetchone()[0])
        conn.close()


@unittest.skipUnless(HAS_OUTPUTS, "需先运行管线")
class TestValidate(unittest.TestCase):
    def test_full_validation_passes(self):
        v = run_validation(quiet=True)
        self.assertEqual(v["files"], 118)
        self.assertEqual(v["files_ok"], 118, "有文件未通过字符守恒对账")
        self.assertEqual(v["sha256_ok"], 118)
        self.assertEqual(v["body_ok"], 118)
        self.assertEqual(v["meta_ok"], 118)
        self.assertEqual(v["pb_bad"], 0)
        self.assertEqual(v["kr_bad"], 0)


@unittest.skipUnless(HAS_OUTPUTS, "需先运行管线")
class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from api import main as api_main
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), api_main.Handler)
        cls.port = cls.srv.server_address[1]
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, path):
        import urllib.request
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return json.load(r)

    def test_books(self):
        books = self.get("/api/books")
        self.assertEqual(len(books), 5)
        self.assertIn("KR2a0001", {b["book_id"] for b in books})

    def test_files_and_passages(self):
        files = self.get("/api/books/KR2e0001/files")     # 國語
        self.assertEqual(len(files), 22)
        fid = files[1]["file_id"]                          # 國語卷一（正文）
        d = self.get(f"/api/files/{fid}/passages?limit=5")
        self.assertGreater(d["total"], 1000)
        pc = self.get(f"/api/files/{fid}/passages?status=pending_commentary&limit=1")
        self.assertGreater(pc["total"], 0)                 # 韦昭注候选
        r = pc["rows"][0]
        self.assertEqual(r["layer"], "commentary_candidate")
        self.assertIn("(", r["text_orig"])

    def test_raw_compare(self):
        # 原文行与解析覆盖标注：guoyu_000 首行应是文件头
        d = self.get("/api/files/1/raw?start=1&end=3")
        self.assertIn("文件头", d["lines"][0]["annotation"])

    def test_q_search(self):
        import urllib.parse
        q = urllib.parse.quote("五帝本紀")
        files = self.get("/api/books/KR2a0001/files")
        d = self.get(f"/api/files/{files[0]['file_id']}/passages?q={q}&limit=2")
        self.assertGreater(d["total"], 0)


if __name__ == "__main__":
    unittest.main()
