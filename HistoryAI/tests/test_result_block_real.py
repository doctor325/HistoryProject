"""第三阶段 Step 8 —— Result Block 在**真实语料**上的回归。

与 test_result_block.py 的分工：那边用合成小库钉住规则，这边用真实库钉住
「跑起来是什么样」。断言全部基于**不变量**，不硬编码 passage_id（语料一重建
就变）；硬编码的只有已确认过的命中数基数（与 test_search_api.py 同源）。

覆盖三个基准词：齐桓公（trigram 路径）、管仲、黄帝（bigram 路径）。

同时验证任务书 §三.3 的零写入约束：HistoryLibrary/kanripo 下所有文件在检索
前后 mtime 与大小均不得变化。
"""
import os
import sqlite3
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.pipeline import config                             # noqa: E402
from search import result_block as RB                           # noqa: E402
from search import zh                                           # noqa: E402

HAS_DB = config.DB_PATH.is_file()

# (查询词, 原始命中数, {模式: 片段数})——已人工核对过的基数
BASELINE = {
    "齐桓公": (96, {"short": 26, "standard": 23, "long": 18}),
    "管仲": (102, {"short": 43, "standard": 31, "long": 26}),
    "黄帝": (163, {"short": 29, "standard": 23, "long": 18}),
}
MODES = ("short", "standard", "long")


def ro_conn():
    c = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


@unittest.skipUnless(HAS_DB, "需先运行 python -m scripts.pipeline.run_all")
class TestResultBlockRealData(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conn = ro_conn()
        cls.cur = cls.conn.cursor()

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def search(self, q, mode="standard", page=1, page_size=100):
        return RB.search_result_blocks(self.cur, q, None, None, page, page_size, mode)

    def all_blocks(self, q, mode="standard"):
        """翻完所有页，返回全部片段（验证分页不重复、不遗漏）。"""
        out, page = [], 1
        while True:
            d = self.search(q, mode, page, 20)
            if not d["results"]:
                break
            out += d["results"]
            if len(out) >= d["total"]:
                break
            page += 1
        return out

    # ---- 基数 ----
    def test_baseline_counts(self):
        for q, (hits, per_mode) in BASELINE.items():
            with self.subTest(q=q):
                for mode, n in per_mode.items():
                    d = self.search(q, mode)
                    self.assertEqual(d["hit_total"], hits, f"{q} 命中数")
                    self.assertEqual(d["total"], n, f"{q} {mode} 片段数")
                    self.assertLessEqual(d["total"], d["hit_total"],
                                         "片段数不可能多于原始命中数")

    # ---- 正文 ----
    def test_text_is_exact_concatenation_of_passages(self):
        """片段正文 = 它列出的那些 passage 的 text_orig 依序相接，一字不差。"""
        for q in ("齐桓公", "管仲"):
            for b in self.all_blocks(q)[:20]:
                with self.subTest(q=q, block=b["block_id"]):
                    rows = self.cur.execute(
                        "SELECT passage_id, text_orig FROM passages WHERE passage_id IN (%s)"
                        % ",".join("?" * len(b["passage_ids"])), b["passage_ids"]).fetchall()
                    by_id = {r["passage_id"]: r["text_orig"] for r in rows}
                    expect = "".join(by_id[pid] for pid in b["passage_ids"])
                    self.assertEqual(b["text"], expect)
                    self.assertEqual(b["n_chars"], len(expect))

    def test_no_parser_metadata_in_block_text(self):
        """片段正文只有史料原文：`# src:`、`# dating:` 等解析器行一律不进来。

        注意 `<pb:…>` 与它们不同——那是 tls 原文自带的页码标记，常常就长在
        正文行首（`<pb:KR2a0001_tls_100-2a>黃帝者，¶` 整条是一行 passage），
        属于第一阶段已入库的 text_orig，必须原样保留（任务书 §十）。
        """
        for q in ("齐桓公", "黄帝"):
            for b in self.all_blocks(q)[:20]:
                with self.subTest(q=q, block=b["block_id"]):
                    for marker in ("# src:", "# dating:"):
                        self.assertNotIn(marker, b["text"])
                    self.assertFalse(b["text"].lstrip().startswith("#"),
                                     "解析器注释行不得进入正文")

    def test_hits_are_actually_in_the_block(self):
        """每个片段里必须有真命中（否则就是白给的结果）。"""
        for q in ("齐桓公", "管仲", "黄帝"):
            trad = zh.to_traditional(q)
            for b in self.all_blocks(q)[:20]:
                with self.subTest(q=q, block=b["block_id"]):
                    self.assertGreaterEqual(b["match_count"], 1)
                    self.assertIn(trad, b["text"])

    # ---- 边界 ----
    def test_block_never_crosses_file(self):
        for q in ("齐桓公", "管仲"):
            for b in self.all_blocks(q):
                with self.subTest(q=q, block=b["block_id"]):
                    fids = {r["file_id"] for r in self.cur.execute(
                        "SELECT DISTINCT file_id FROM passages WHERE passage_id IN (%s)"
                        % ",".join("?" * len(b["passage_ids"])), b["passage_ids"])}
                    self.assertEqual(fids, {b["file_id"]})

    def test_block_never_crosses_layer(self):
        for q in ("齐桓公", "管仲"):
            for b in self.all_blocks(q)[:30]:
                with self.subTest(q=q, block=b["block_id"]):
                    layers = {r["layer"] for r in self.cur.execute(
                        "SELECT DISTINCT layer FROM passages WHERE passage_id IN (%s)"
                        % ",".join("?" * len(b["passage_ids"])), b["passage_ids"])}
                    self.assertEqual(layers, {b["layer"]})

    def test_passage_ids_follow_reading_order(self):
        """片段内的记录必须按 (row_no, seq) 递增——读起来才连续。"""
        for q in ("齐桓公", "管仲", "黄帝"):
            for b in self.all_blocks(q)[:20]:
                with self.subTest(q=q, block=b["block_id"]):
                    rows = self.cur.execute(
                        "SELECT passage_id, row_no, seq FROM passages WHERE passage_id IN (%s)"
                        % ",".join("?" * len(b["passage_ids"])), b["passage_ids"]).fetchall()
                    pos = {r["passage_id"]: (r["row_no"], r["seq"]) for r in rows}
                    keys = [pos[pid] for pid in b["passage_ids"]]
                    self.assertEqual(keys, sorted(keys))

    # ---- 分页 ----
    def test_pagination_has_no_gap_or_overlap(self):
        for q, (_, per_mode) in BASELINE.items():
            with self.subTest(q=q):
                blocks = self.all_blocks(q)
                self.assertEqual(len(blocks), per_mode["standard"])
                ids = [b["block_id"] for b in blocks]
                self.assertEqual(len(ids), len(set(ids)), "翻页出现重复片段")

    def test_block_ids_are_unique(self):
        for q in ("齐桓公", "管仲", "黄帝"):
            blocks = self.all_blocks(q)
            ids = [b["block_id"] for b in blocks]
            self.assertEqual(len(ids), len(set(ids)), f"{q} 有重复 block_id")

    # ---- 展开 ----
    def test_expand_more_context_if_available(self):
        """能展开的片段，展开读到的行必须真在同一段史料内、且不重叠。"""
        checked = 0
        for q in ("齐桓公", "管仲", "黄帝"):
            for mode in ("short", "standard"):
                for b in self.search(q, mode, 1, 100)["results"]:
                    if not (b["more_before"] or b["more_after"]):
                        continue
                    checked += 1
                    with self.subTest(q=q, block=b["block_id"]):
                        seen = set(b["passage_ids"])
                        before = RB.expand_block(self.cur, b["hit_passage_id"], "before", 5,
                                                 b["first_passage_id"], None)
                        after = RB.expand_block(self.cur, b["hit_passage_id"], "after", 5,
                                                None, b["last_passage_id"])
                        for row in before["rows"] + after["rows"]:
                            self.assertNotIn(row["passage_id"], seen,
                                             "展开读到了片段里已有的记录（重叠）")
                    if checked >= 8:
                        break
        self.assertGreater(checked, 0, "真实语料里应当存在可展开的片段")

    def test_expand_rows_are_contiguous_and_same_layer(self):
        checked = 0
        for q in ("齐桓公", "管仲"):
            for b in self.search(q, "standard", 1, 100)["results"]:
                if not b["more_after"]:
                    continue
                r = RB.expand_block(self.cur, b["hit_passage_id"], "after", 10,
                                    None, b["last_passage_id"])
                if not r["rows"]:
                    continue
                checked += 1
                with self.subTest(q=q, block=b["block_id"]):
                    pids = [x["passage_id"] for x in r["rows"]]
                    rows = self.cur.execute(
                        "SELECT passage_id, row_no, seq, layer FROM passages "
                        "WHERE passage_id IN (%s)" % ",".join("?" * len(pids)), pids).fetchall()
                    meta = {x["passage_id"]: x for x in rows}
                    self.assertTrue(all(meta[p]["layer"] == b["layer"] for p in pids))
                    keys = [(meta[p]["row_no"], meta[p]["seq"]) for p in pids]
                    self.assertEqual(keys, sorted(keys))
                    # 第一条必须紧接在片段末条之后
                    last = self.cur.execute(
                        "SELECT row_no, seq FROM passages WHERE passage_id = ?",
                        (b["last_passage_id"],)).fetchone()
                    self.assertGreater(keys[0], (last["row_no"], last["seq"]))
                if checked >= 5:
                    break
        self.assertGreater(checked, 0, "真实语料里应当存在可展开的片段")


@unittest.skipUnless(HAS_DB, "需先运行 python -m scripts.pipeline.run_all")
class TestLibraryUntouched(unittest.TestCase):
    """任务书 §三.3：HistoryLibrary/kanripo 零写入。检索不得改动原始史料。"""

    def _snapshot(self):
        base = config.LIBRARY_DIR
        out = {}
        if not base.is_dir():
            return out
        for p in base.rglob("*"):
            if p.is_file():
                st = p.stat()
                out[str(p)] = (st.st_size, st.st_mtime_ns)
        return out

    def test_search_does_not_write_library(self):
        if not config.LIBRARY_DIR.is_dir():
            self.skipTest("资料库目录不存在")
        before = self._snapshot()
        self.assertGreater(len(before), 0, "资料库应有文件可供比对")
        conn = ro_conn()
        try:
            for q in ("齐桓公", "管仲", "黄帝", "城濮"):
                RB.search_result_blocks(conn.cursor(), q, None, None, 1, 20, "standard")
            b = RB.search_result_blocks(conn.cursor(), "齐桓公", None, None, 1, 1,
                                        "long")["results"][0]
            RB.expand_block(conn.cursor(), b["hit_passage_id"], "both", 20)
        finally:
            conn.close()
        after = self._snapshot()
        self.assertEqual(before, after, "HistoryLibrary/kanripo 在检索过程中被改动了")


if __name__ == "__main__":
    unittest.main()
