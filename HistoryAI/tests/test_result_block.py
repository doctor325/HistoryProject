"""第三阶段 Step 7 —— Result Block（史料片段）组装与 API 契约测试。

分两部分：
  TestResultBlockUnit      小库/合成数据就能验的组装规则（不依赖真实语料）
  TestResultBlockApi       HTTP 契约（真实的本地 API，只读库）

真实语料上的回归（齐桓公 / 管仲 / 黄帝）在 tests/test_result_block_real.py。

不变量（任务书 §三 / §八 / §十 / §十二 / §二十四）：
  * 片段正文 = 若干 kind='passage' 记录的 text_orig **依序相接**，一字不改
  * 绝不跨 file_id；绝不混 layer；结构键变化即止
  * 合并后 total ≤ hit_total（同段多命中只展示一次）
"""
import json
import sqlite3
import sys
import threading
import unittest
import urllib.error
import urllib.parse
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from api import main as api_main                                # noqa: E402
from scripts.pipeline import config                             # noqa: E402
from search import result_block as RB                           # noqa: E402

HAS_DB = config.DB_PATH.is_file()
QIHUANGONG = "齐桓公"


def ro_conn():
    c = sqlite3.connect(f"file:{config.DB_PATH}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


# --------------------------------------------------------------- 合成小库

SCHEMA = """
CREATE TABLE books (book_id TEXT PRIMARY KEY, title TEXT, edition TEXT, family TEXT);
CREATE TABLE files (file_id INTEGER PRIMARY KEY, book_id TEXT, file_name TEXT,
                    file_no INTEGER, origin_path TEXT);
CREATE TABLE passages (
  passage_id INTEGER PRIMARY KEY, file_id INTEGER, book_id TEXT,
  row_no INTEGER, seq INTEGER, kind TEXT, layer TEXT, status TEXT,
  juan TEXT, section TEXT, subsection TEXT, division TEXT, ab TEXT,
  text_orig TEXT, normalized_text TEXT, source_ref_json TEXT,
  pb_block TEXT, pb_page TEXT, pb_side TEXT);
CREATE TABLE passages_fts (passage_id UNINDEXED);
-- 第四阶段：段号窄派生表。真实库里由建库时算好；合成库里由 make_db 用
-- _src_paragraph（同一个函数）从 passages.source_ref_json 派生，口径一致。
CREATE TABLE src_paragraphs (file_id INTEGER, row_no INTEGER, paragraph_code TEXT);
CREATE INDEX idx_srcpara ON src_paragraphs(file_id, row_no);
"""


def _p(pid, fid, row, seq, text, kind="passage", layer="main",
       section=None, subsection=None, ab=None, juan="卷一", src=None,
       pb_page=None, pb_side=None):
    return (pid, fid, "KR1e0001", row, seq, kind, layer, "ok", juan, section,
            subsection, None, ab, text, text, src, None, pb_page, pb_side)


def make_db(rows, files=None, books=None):
    """内存库：只放组装需要的表与列（引擎不参与，命中直接给）。"""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute("INSERT INTO books VALUES ('KR1e0001','尚書','tls','tls')")
    for r in (files or [(1, "f1"), (2, "f2")]):
        conn.execute("INSERT INTO files VALUES (?,?,?,?,?)",
                     (r[0], "KR1e0001", r[1], r[0], f"kanripo/{r[1]}.txt"))
    for r in books or []:
        conn.execute("INSERT INTO books VALUES (?,?,?,?)", r)
    conn.executemany(
        "INSERT INTO passages VALUES (" + ",".join("?" * 19) + ")", rows)
    # 段号窄表：与建库侧同一条规则（_src_paragraph），只不过数据源是合成库
    for r in conn.execute("SELECT file_id, row_no, source_ref_json FROM passages"
                          " WHERE source_ref_json IS NOT NULL"):
        code = RB._src_paragraph(r["source_ref_json"])
        if code is not None:
            conn.execute("INSERT INTO src_paragraphs VALUES (?,?,?)",
                         (r["file_id"], r["row_no"], code))
    conn.commit()
    return conn


def hit(pid, fid, row, seq, score=0.0):
    return (pid, fid, row, seq, score)


class TestResultBlockUnit(unittest.TestCase):
    """组装规则：边界、合并、排序、出口结构。"""

    def blocks(self, conn, hits, mode="standard"):
        return RB.build_result_blocks(conn.cursor(), hits, mode)["blocks"]

    # ---- 结构键边界 ----
    def test_stops_at_section_change(self):
        conn = make_db([
            _p(1, 1, 1, 1, "甲甲甲甲甲", section="堯典"),
            _p(2, 1, 2, 1, "乙乙乙乙乙", section="堯典"),
            _p(3, 1, 3, 1, "丙丙丙丙丙", section="舜典"),   # section 变 → 边界
            _p(4, 1, 4, 1, "丁丁丁丁丁", section="舜典"),
        ])
        b = self.blocks(conn, [hit(1, 1, 1, 1)])[0]
        self.assertEqual(b["passage_ids"], [1, 2])         # 不含 3/4
        self.assertEqual(b["text"], "甲甲甲甲甲乙乙乙乙乙")

    def test_stops_at_layer_change(self):
        conn = make_db([
            _p(1, 1, 1, 1, "正文一", layer="main"),
            _p(2, 1, 2, 1, "正文二", layer="main"),
            _p(3, 1, 3, 1, "注文一", layer="commentary_candidate"),
            _p(4, 1, 4, 1, "注文二", layer="commentary_candidate"),
        ])
        b = self.blocks(conn, [hit(1, 1, 1, 1)])[0]
        self.assertEqual(b["passage_ids"], [1, 2])
        self.assertEqual(b["layer"], "main")

    def test_never_crosses_file(self):
        conn = make_db([
            _p(1, 1, 1, 1, "第一篇"),
            _p(9, 2, 2, 1, "第二篇"),      # 另一文件，紧邻 row_no 也不得越界
        ])
        b = self.blocks(conn, [hit(1, 1, 1, 1)])[0]
        self.assertEqual(b["passage_ids"], [1])
        self.assertEqual(b["file_id"], 1)

    def test_stops_at_subsection_and_ab(self):
        conn = make_db([
            _p(1, 1, 1, 1, "傳文一", subsection="17.1", ab="B"),
            _p(2, 1, 2, 1, "傳文二", subsection="17.1", ab="B"),
            _p(3, 1, 3, 1, "經文", subsection="17.1", ab="A"),   # 经/传不混
            _p(4, 1, 4, 1, "傳文三", subsection="17.2", ab="B"),  # 条目号变
        ])
        b = self.blocks(conn, [hit(1, 1, 1, 1)])[0]
        self.assertEqual(b["passage_ids"], [1, 2])

    # ---- 解析元数据行 ----
    def test_parser_metadata_rows_pass_through(self):
        """`# src:` / `<pb:>` 行透明穿过：不打断扩展，也不进片段正文。"""
        conn = make_db([
            _p(1, 1, 1, 1, "前句。"),
            _p(2, 1, 2, 1, "# src: SHIJI 004.41.1", kind="comment", layer="structure"),
            _p(3, 1, 3, 1, "<pb:KR2a0001_tls_100-150a>", kind="page", layer="structure"),
            _p(4, 1, 4, 1, "後句。"),
        ])
        b = self.blocks(conn, [hit(4, 1, 4, 1)])[0]
        self.assertEqual(b["passage_ids"], [1, 4])       # 元数据行不在其中
        self.assertEqual(b["text"], "前句。後句。")       # 也没被写进正文
        self.assertNotIn("# src:", b["text"])
        self.assertNotIn("<pb:", b["text"])

    def test_src_paragraph_number_is_boundary(self):
        """史記体例：无 section 时，`# src:` 段号变化即段落边界。

        `# src:` 管辖它之后、下一条 `# src:` 之前的 passage 行；段号只取前两级，
        所以 004.42.1 与 004.42.3 同段。
        """
        def src(pid, row, code):
            return _p(pid, 1, row, 1, f"# src: SHIJI {code}", kind="comment",
                      layer="structure", src=json.dumps({"section_ref": f"{code}, ed. X 1959"}))
        conn = make_db([
            _p(1, 1, 1, 1, "四〇甲"),        # 首条 # src: 之前，无段落号证据
            src(101, 2, "004.40.1"),
            _p(2, 1, 3, 1, "四一甲"),
            _p(3, 1, 4, 1, "四一乙"),
            src(102, 5, "004.42.1"),
            _p(4, 1, 6, 1, "四二甲"),
            _p(5, 1, 7, 1, "四二乙"),
        ])
        b = self.blocks(conn, [hit(5, 1, 7, 1)])[0]
        self.assertEqual(b["passage_ids"], [4, 5])      # 只管到 004.42 的自己
        self.assertEqual(b["text"], "四二甲四二乙")
        b2 = self.blocks(conn, [hit(3, 1, 4, 1)])[0]
        # 回过头读也不越进 004.42；首条 # src: 之前的那行归入它后面那一段
        self.assertEqual(b2["passage_ids"], [1, 2, 3])

    def test_src_paragraph_not_using_dating_annotation(self):
        """不许到处抓数字：只认开头那一个段号（`# dating:` 那类注解一律无证据）。"""
        self.assertIsNone(RB._src_paragraph(json.dumps({"section_ref": "dating: 6220卿有札書"})))
        self.assertIsNone(RB._src_paragraph(json.dumps({"section_ref": "no digits here"})))
        self.assertIsNone(RB._src_paragraph(json.dumps({"section_ref": "ZUO Xi 17.5.6 (643 B.C.)"})))
        self.assertIsNone(RB._src_paragraph(json.dumps({"section_ref": "5"})), "孤立数字不算段号")
        self.assertEqual(RB._src_paragraph(json.dumps({"section_ref": "004.41.2, ed. X"})), "004.41")
        self.assertEqual(RB._src_paragraph(json.dumps({"section_ref": "ZUO 17.5.6 (643 B.C.)"})), "17.5")
        self.assertEqual(RB._src_paragraph(json.dumps({"section_ref": "SHIJI 28.70.3 1393/94"})), "28.70")
        self.assertIsNone(RB._src_paragraph(None))
        self.assertIsNone(RB._src_paragraph("{不是 JSON"))

    def test_structure_field_beats_src_number(self):
        """左傳/尚書 的 section 比 `# src:` 更粗：有结构字段时不按段号切。"""
        conn = make_db([
            _p(1, 1, 1, 1, "僖公十七年一", section="僖公十七年"),
            _p(2, 1, 2, 1, "僖公十七年二", section="僖公十七年"),
            _p(3, 1, 3, 1, "# src: ZUO Xi 17.5.6", kind="comment", layer="structure",
               src=json.dumps({"section_ref": "ZUO Xi 18.1.1"})),   # 更细的段号
            _p(4, 1, 4, 1, "僖公十七年三", section="僖公十七年"),
        ])
        b = self.blocks(conn, [hit(1, 1, 1, 1)])[0]
        self.assertEqual(b["passage_ids"], [1, 2, 4])   # 段号没有把它切碎

    # ---- 合并 ----
    def test_adjacent_hits_merge_into_one_block(self):
        conn = make_db([
            _p(1, 1, 1, 1, "甲乙丙"),
            _p(2, 1, 2, 1, "丁戊己"),
            _p(3, 1, 3, 1, "庚辛壬"),
        ])
        blocks = self.blocks(conn, [hit(1, 1, 1, 1), hit(2, 1, 2, 1), hit(3, 1, 3, 1)])
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]["match_count"], 3)
        self.assertEqual(blocks[0]["n_passages"], 3)

    def test_merged_text_is_exact_concatenation(self):
        conn = make_db([
            _p(1, 1, 1, 1, "甲¶"), _p(2, 1, 2, 1, "乙¶"), _p(3, 1, 3, 1, "丙¶"),
        ])
        b = self.blocks(conn, [hit(1, 1, 1, 1), hit(3, 1, 3, 1)])[0]
        rows = conn.execute(
            "SELECT text_orig FROM passages WHERE passage_id IN (%s) ORDER BY row_no, seq"
            % ",".join("?" * len(b["passage_ids"])), b["passage_ids"]).fetchall()
        self.assertEqual(b["text"], "".join(r["text_orig"] for r in rows))

    # ---- 边界与硬上限 ----
    def test_max_chars_is_hard(self):
        conn = make_db([_p(i, 1, i, 1, "字" * 100) for i in range(1, 31)])
        b = self.blocks(conn, [hit(15, 1, 15, 1)], mode="short")[0]
        self.assertLessEqual(b["n_chars"], RB.MODE_LIMITS["short"]["max_chars"])

    def test_mode_length_monotonic(self):
        conn = make_db([_p(i, 1, i, 1, "字" * 50) for i in range(1, 61)])
        lens = [self.blocks(conn, [hit(30, 1, 30, 1)], mode=m)[0]["n_chars"]
                for m in ("short", "standard", "long")]
        self.assertLess(lens[0], lens[1])
        self.assertLess(lens[1], lens[2])

    def test_file_edges_do_not_wrap(self):
        conn = make_db([_p(1, 1, 1, 1, "首句"), _p(2, 1, 2, 1, "次句")])
        b = self.blocks(conn, [hit(1, 1, 1, 1)])[0]
        self.assertEqual(b["row_first"], 1)
        self.assertFalse(b["more_before"])             # 已到文件开头

    # ---- 出口结构 ----
    def test_block_shape(self):
        conn = make_db([
            _p(1, 1, 1, 1, "甲", pb_page="100", pb_side="a"),
            _p(2, 1, 2, 1, "乙", pb_page="101", pb_side="b"),
        ])
        b = RB._public_block(self.blocks(conn, [hit(1, 1, 1, 1)])[0])
        for k in ("block_id", "hit_passage_id", "file_id", "row_first", "row_last",
                  "passage_ids", "match_count", "text", "juan", "section", "layer",
                  "pb_first", "pb_last", "n_passages", "n_chars",
                  "more_before", "more_after", "first_passage_id", "last_passage_id"):
            self.assertIn(k, b, f"缺字段 {k}")
        self.assertEqual(b["first_passage_id"], 1)
        self.assertEqual(b["last_passage_id"], 2)
        self.assertEqual((b["pb_first"], b["pb_last"]), ("100a", "101b"))
        self.assertNotIn("rows", b)          # 内部中间态不外泄（也不可 JSON 化）
        self.assertNotIn("marks", b)
        self.assertNotIn("score", b)

    def test_reach_edges_detects_truncation(self):
        """被展示长度截断（而非读到尽头）时才提示可展开。"""
        conn = make_db([_p(i, 1, i, 1, "字" * 200) for i in range(1, 11)])
        blocks = self.blocks(conn, [hit(5, 1, 5, 1)], mode="short")
        self.assertTrue(blocks[0]["more_after"] or blocks[0]["more_before"])
        # 短到能全读下时，两侧都到头 → 不给展开按钮
        conn2 = make_db([_p(1, 1, 1, 1, "甲"), _p(2, 1, 2, 1, "乙")])
        b2 = self.blocks(conn2, [hit(1, 1, 1, 1)], mode="short")[0]
        self.assertFalse(b2["more_before"])
        self.assertFalse(b2["more_after"])


# --------------------------------------------------------------- expand

class TestExpandBlock(unittest.TestCase):
    """按需展开：从片段边界向外取，不重叠、不跨段。"""

    def setUp(self):
        self.conn = make_db([
            _p(1, 1, 1, 1, "一"), _p(2, 1, 2, 1, "二"), _p(3, 1, 3, 1, "三"),
            _p(4, 1, 4, 1, "四"), _p(5, 1, 5, 1, "五"), _p(6, 1, 6, 1, "六"),
            _p(7, 1, 7, 1, "七", section="別篇"),      # 同文件的另一篇 → 段落边界
        ])
        self.cur = self.conn.cursor()

    def test_expand_after_from_block_tail(self):
        r = RB.expand_block(self.cur, 3, "after", 2, None, 3)   # 从第 3 条往后
        self.assertEqual([x["passage_id"] for x in r["rows"]], [4, 5])
        self.assertEqual(r["added"], 2)
        self.assertFalse(r["reaches_tail"])
        self.assertEqual(r["next_after_passage_id"], 5)         # 下次的锚点

    def test_expand_stops_at_section_boundary(self):
        r = RB.expand_block(self.cur, 5, "after", 10, None, 5)
        self.assertEqual([x["passage_id"] for x in r["rows"]], [6])  # 不含第 7 条
        self.assertTrue(r["reaches_tail"])
        # 从第 7 条往回想读回上一篇，同样不许越界
        r2 = RB.expand_block(self.cur, 7, "before", 10, 7, None)
        self.assertEqual(r2["rows"], [])
        self.assertTrue(r2["reaches_head"])

    def test_expand_before_returns_reading_order(self):
        r = RB.expand_block(self.cur, 5, "before", 2, 5, None)
        self.assertEqual([x["passage_id"] for x in r["rows"]], [3, 4])
        self.assertFalse(r["reaches_head"])

    def test_expand_both(self):
        r = RB.expand_block(self.cur, 4, "both", 1)
        self.assertEqual([x["passage_id"] for x in r["rows"]], [3, 5])

    def test_expand_errors(self):
        with self.assertRaises(KeyError):
            RB.expand_block(self.cur, 999999, "after", 5)
        with self.assertRaises(ValueError):
            RB.expand_block(self.cur, 3, "sideways", 5)

    def test_expand_rejects_non_passage_record(self):
        conn = make_db([
            _p(1, 1, 1, 1, "正文"),
            _p(2, 1, 2, 1, "# src: X", kind="comment", layer="structure"),
        ])
        with self.assertRaises(ValueError):
            RB.expand_block(conn.cursor(), 2, "after", 5)

    def test_count_is_clamped(self):
        r = RB.expand_block(self.cur, 3, "after", 10 ** 6)
        self.assertLessEqual(r["count"], 100)


# --------------------------------------------------------------- HTTP 契约

@unittest.skipUnless(HAS_DB, "需先运行 python -m scripts.pipeline.run_all")
class TestResultBlockApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.srv = ThreadingHTTPServer(("127.0.0.1", 0), api_main.Handler)
        cls.port = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()

    def get(self, path):
        with urllib.request.urlopen(f"http://127.0.0.1:{self.port}{path}") as r:
            return json.load(r)

    def code(self, path):
        try:
            self.get(path)
            return 200
        except urllib.error.HTTPError as e:
            return e.code

    def search(self, **kw):
        return self.get("/api/search?" + urllib.parse.urlencode(kw))

    def test_default_is_standard_block(self):
        d = self.search(q=QIHUANGONG)
        self.assertEqual(d["mode"], "standard")
        self.assertEqual(d["total"], 23)
        self.assertEqual(d["hit_total"], 96)
        self.assertEqual(len(d["results"]), 20)

    def test_modes_change_block_granularity(self):
        short = self.search(q=QIHUANGONG, mode="short")
        long_ = self.search(q=QIHUANGONG, mode="long")
        self.assertEqual((short["total"], long_["total"]), (26, 18))
        # 命中总数与显示长度无关，必须一致
        self.assertEqual(short["hit_total"], long_["hit_total"])
        self.assertLess(short["limits"]["max_chars"], long_["limits"]["max_chars"])

    def test_bad_mode_and_book_400(self):
        self.assertEqual(self.code("/api/search?" + urllib.parse.urlencode(
            {"q": QIHUANGONG, "mode": "huge"})), 400)
        self.assertEqual(self.code("/api/search?" + urllib.parse.urlencode(
            {"q": QIHUANGONG, "book": "三字经"})), 400)

    def test_pagination_total_is_exact(self):
        p1 = self.search(q=QIHUANGONG, page_size=10, page=1)
        p2 = self.search(q=QIHUANGONG, page_size=10, page=2)
        p3 = self.search(q=QIHUANGONG, page_size=10, page=3)
        self.assertEqual(p1["total"], p2["total"])
        self.assertEqual(p1["total"], p3["total"])
        self.assertEqual(len(p1["results"]), 10)
        self.assertEqual(len(p3["results"]), 3)      # 23 段 = 10 + 10 + 3
        ids = [b["block_id"] for b in p1["results"]] + [b["block_id"] for b in p3["results"]]
        self.assertEqual(len(ids), len(set(ids)))    # 翻页不重复

    def test_block_expand_endpoint(self):
        b = self.search(q=QIHUANGONG, mode="long")["results"][0]
        if not (b["more_before"] or b["more_after"]):
            self.skipTest("该片段已读全，无需展开（不是失败）")
        d = self.get(f"/api/blocks/{b['hit_passage_id']}?direction=after&count=3"
                     f"&after_passage_id={b['last_passage_id']}")
        self.assertIn("rows", d)
        self.assertEqual(d["added"], len(d["rows"]))

    def test_block_expand_404_and_400(self):
        # 参数非法 → 400（先校验，不必查库）；记录不存在 → 404
        self.assertEqual(self.code("/api/blocks/999999999?direction=sideways"), 400)
        self.assertEqual(self.code("/api/blocks/999999999"), 404)
        d = self.search(q=QIHUANGONG, page_size=1)
        pid = d["results"][0]["hit_passage_id"]
        self.assertEqual(self.code(f"/api/blocks/{pid}?direction=sideways"), 400)


if __name__ == "__main__":
    unittest.main()
