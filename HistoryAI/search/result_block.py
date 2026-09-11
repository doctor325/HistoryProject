# -*- coding: utf-8 -*-
"""第三阶段：Result Block —— 把「命中句」组装成「可连续阅读的史料片段」。

## 为什么需要
tls 系（尚書/左傳/史記）¶ 一句一行，一条 passage 常常就是一个 6 字句子
（`齊桓公卒。¶`）。FTS 命中是「句」，用户要读的是「一件事」。本模块只做
展示层聚合：**不改索引、不改原文、不动第一阶段 parser、不写任何库**。

## 组装规则（机会主义：有什么证据用什么）
一个 block = 命中 passage + 同一原始文件内沿 (row_no, seq) 向两侧扩展的相邻
记录，遇到下列任一**停止条件**即停：

1. 文件边界 —— 绝不跨 file_id（硬边界，永不越过）。
2. layer 变化 —— 正文与 commentary_candidate 不混（任务书 §八.4）。
3. 结构键变化（按书自适应，全部取数据库真实列）：
   - `section`    左傳(僖公十七年傳) / 尚書(篇名) / 史記表(三代世表)
   - `subsection` 左傳条目号
   - `ab`         左傳 A=經 / B=傳
   - `# src:` 段落号  史記 纪/傳 的段号（_src_paragraph 截前两级）
   **注意史記内部极不均匀**：f82(本紀) 有 1894 条 src、f95(傳) 2611 条，
   而 f94(世家) 仅 78 条、f83/f84(表) 为 0。没有证据时不猜测段落，
   改由硬上限兜底（任务书 §十：宁可短，不可臆造）。
4. 硬上限 —— 两种情形都生效：max_passages / max_chars。
   对國語 / 戰國策 / 史記世家等无结构字段的书，这是唯一的收束手段。

page/pb 换页**不**作为停止条件：一段史料本就可能跨页（任务书 §八.5），
只在结果里如实带出 pb_first / pb_last。

## 合并去重
同一文件内相邻的多个命中若落入同一个区间，只产出一个 block，match_count
汇总（任务书 §十二）。区间重叠时取并集，不丢结果。

## 不改原文
`text` 由各记录 `text_orig` 直接相接，不改写、不补标点、不做任何润色
（任务书 §十 / §二十四）。含 <pb:…>、¶ 等原样保留。
"""
from __future__ import annotations

import json
import re

# 三种展示长度。target_chars 是「尽量达到」，max_* 是「绝不超过」。
MODE_LIMITS = {
    "short":    {"target_chars": 120,  "max_passages": 12,  "max_chars": 260},
    "standard": {"target_chars": 420,  "max_passages": 40,  "max_chars": 900},
    "long":     {"target_chars": 1200, "max_passages": 120, "max_chars": 2600},
}
DEFAULT_MODE = "standard"

# 单次搜索最多组装多少个 block（防热词把全库拖进来；超出则如实标注 truncated）。
MAX_BLOCKS_PER_QUERY = 600

# 行窗口：命中行两侧至少取 FALLBACK_MARGIN 条（无结构证据时的兜底观察范围），
# 窗口总跨度不超过 WINDOW_HARD_CAP（防 src 边界远在千里时拖进半个文件）。
FALLBACK_MARGIN = 40
WINDOW_HARD_CAP = 600
WINDOW_PAD = 20          # 二次取数时在块区间外额外留的行数

# 段落号形态：'004.41.2' / '17.5.6' / '28.70.3' —— 点分数字，至少两级。
# 必须用 ^ 锚定 section_ref 开头，否则会误吃 `# dating: 6220卿有札書…` 这类
# 注解或引文里的数字（实测踩过）；只认开头一个，也不许到处抓。
_SRC_CODE_RE = re.compile(r"^([A-Za-z]*)\s*(\d+(?:\.\d+)+)")

_ROW_COLS = ("passage_id, file_id, row_no, seq, kind, layer, status, juan, section, "
             "subsection, division, ab, text_orig, source_ref_json, "
             "pb_block, pb_page, pb_side")


# ----------------------------------------------------------------- 边界证据

def _src_paragraph(source_ref_json: str | None) -> str | None:
    """从 # src: 的 section_ref 里取「段落号」前两级，作史記等书的段边界。

    数据库里的 section_ref 形态不统一，实测有：
      '004.41.2, ed. Zhōnghuáshūjú …'  → 004.41   （史記本紀，段号在最前）
      'SHIJI 28.70.3 1393/94; …'       → 28.70    （书名前缀 + 空格 + 段号）
      'ZUO 17.5.6 (643 B.C.); …'       → 17.5     （左傳，前缀 + 空格）
      '5.28.3 (…) …'                   → 5.28
    取开头「≥2 级点分数字」的第一二级。**只基于第一阶段已入库的值**，
    不重新解析原文、不猜测章节归属。开头不是号的一律视为无证据——例如
    'ZUO Xi 17.5.6'（前缀里夹了非书名词）或 '# dating: 6220…' 这类注解。
    """
    if not source_ref_json:
        return None
    try:
        ref = (json.loads(source_ref_json) or {}).get("section_ref") or ""
    except (TypeError, ValueError):
        return None
    # 只认开头的卷次号（可带 ZUO/SHIJI 类前缀）；开头不是号的一律视为无证据，
    # 例如 '# dating: 6220卿有札書…' 那种注解里的数字，绝不当段落号用。
    m = _SRC_CODE_RE.match(ref.lstrip())
    if not m:
        return None
    # 至少两级才当段号：'5' 这种孤立数字说不清是卷次还是页码，宁可不切
    # （任务书 §十：宁可短，不可臆造）。
    return ".".join(m.group(2).split(".")[:2])


def _boundary_key(section, subsection, ab) -> tuple | None:
    """结构键：键不同 = 不同段；None = 该行无段落级结构证据。"""
    if section:
        return ("sec", section, ab)
    if subsection:
        return ("sub", subsection, ab)
    if ab:
        return ("ab", ab)
    return None


def _can_take(row, marks, i, ref_i) -> bool:
    """rows[i] 能否并入以 ref_i 为参照的扩展区间（判定统一的唯一出口）。

    非 passage 行（`# src:` / `<pb:>` / 标题）在正文里透明穿过：既不进片段
    正文，也不打断扩展。但**参照行不能跟着它们走**——`# src:` 这一行本身属于
    **新**段号，若拿它当参照，下一个 passage 就在跟新段号比较，于是从 004.42
    往回读能一路读穿到文件开头（实测踩过）。参照行永远停在「最近一条真正并入
    的 passage」上。

    `key_k != key_ref` 把「有键 ↔ 无键」也判成变化（严格口径）：一侧有 section
    小节标题、另一侧无 section，就是两段史料，拼起来会读串。代价是个别片段
    短一点——按任务书 §十，宁可短，不可臆造。块之间的界限另由**锚点位置**保证：
    展开时不允许读回锚点另一侧。
    """
    if row["kind"] != "passage":
        return True
    key_ref, seg_ref, layer_ref = marks[ref_i]
    key_k, seg_k, layer_k = marks[i]
    if layer_k != layer_ref:
        return False                       # layer 边界：正文/注释不混
    # 键必须一样：**「有键 ↔ 无键」也算变化**。一侧是篇/章标题行，另一侧不属于
    # 任何篇，硬并起来就把两段史料接成一句。实测这条取严格口径与宽松口径在真实
    # 语料上产出的片段数、长度完全相同（说明宽松口径多读到的只是拼接缝上的
    # 零头），那就取不会读串的那个（任务书 §十）。
    if key_k != key_ref:
        return False
    # `# src:` 段号只在**本行没有结构字段**时才作边界证据（结构字段更可靠，
    # 且左傳/尚書的 src 行比 section 更细，用它会切碎阅读单元）。
    if key_ref is None and seg_ref is not None and seg_k is not None and seg_k != seg_ref:
        return False
    return True


# --------------------------------------------------------------- 有限行加载

class _FileCache:
    """单次搜索请求内、按文件惰性加载**有限行窗口**。

    任务书 §二十一禁止「一次加载整个文件」与「把 203,308 条拉进 Python」，
    因此只取命中附近的行：(file_id, row_no, seq) 范围查询走 idx_pas_file_row。
    窗口按需生长（第一次只取命中附近 FALLBACK_MARGIN 行；若扩展被窗口截断再
    向外扩，每次翻倍），最多长到 WINDOW_HARD_CAP。缓存随请求结束丢弃。
    """

    def __init__(self, cur):
        self._cur = cur
        self._seg_cache: dict[int, list] = {}
        self._win_cache: dict[int, tuple] = {}       # file_id -> (rows, meta)

    # ---- 段落号索引（只查源出行两列，代价与文件大小无关）----
    def segments(self, file_id: int) -> list:
        """该文件段落号管辖区间 [(lo_row, hi_row), …]；无 # src: 则返回 []。

        区间在**段号变化的那个 src 行**处收口（不是在下一条 src 行）：那个 src
        行本身已经属于新段号，旧段不能把它圈进来。这样同一个段号在文件里出现
        多次（换页处重复标号）也会被切成多段，不会跨过中间别的段号把它们并起来。

        读的是建库时算好的窄派生表 `src_paragraphs`（只两列 + 索引）。第四阶段
        实测：读 passages 里同样这批 `# src:` 行的 source_ref_json 再逐条
        json.loads + 正则，6 个大文件要 56.1ms；换成窄表 3.3ms。段号本身由
        建库侧调用**同一个** `_src_paragraph` 算好，两边不会出现两种口径。
        """
        if file_id not in self._seg_cache:
            spans: list[list] = []
            for r in self._cur.execute(
                    "SELECT row_no, paragraph_code FROM src_paragraphs "
                    "WHERE file_id = ? ORDER BY row_no", (file_id,)):
                code = r["paragraph_code"]
                if not spans or spans[-1][0] != code:
                    spans.append([code, r["row_no"]])
            self._seg_cache[file_id] = [
                (spans[i][1], spans[i + 1][1] if i + 1 < len(spans) else 10 ** 9)
                for i in range(len(spans))]
        return self._seg_cache[file_id]

    # ---- 行窗口：按需生长 ----
    def window(self, file_id: int, row_lo: int, row_hi: int):
        """取覆盖 [row_lo, row_hi] 的窗口，返回 rows（按 row_no, seq）。

        带 WINDOW_PAD 余量；单次跨度不超过 WINDOW_HARD_CAP。同文件内若已缓存
        的窗口能满足请求（有膨胀余量），直接复用，避免重复 SQL。
        """
        lo = max(1, row_lo - WINDOW_PAD)
        hi = min(row_hi + WINDOW_PAD, lo + WINDOW_HARD_CAP - 1)
        cached = self._win_cache.get(file_id)
        if cached is not None:
            rows, (clo, chi) = cached
            if clo <= lo and chi >= hi:
                return rows
        rows = self._cur.execute(
            f"SELECT {_ROW_COLS} FROM passages WHERE file_id = ? "
            f"AND row_no BETWEEN ? AND ? ORDER BY row_no, seq",
            (file_id, lo, hi)).fetchall()
        self._win_cache[file_id] = (rows, (lo, hi))
        return rows


# ----------------------------------------------------------------- 区间扩展

def _expand(rows: list, i: int, limits: dict, marks: list) -> tuple[int, int, bool, bool]:
    """从 rows[i] 向两侧扩展，返回 (lo, hi, 尾部被截断, 头部被截断)。

    marks[j] = (结构键, 段序号或None, layer)。停止：结构键变 / 段号变 /
    layer 变 / 越过硬上限。page 换页不停止（任务书 §八.5）。

    后两个布尔值区分「读到本段尽头」与「被字数/条数上限截断」——只有真被
    截断才提示可以继续展开（任务书 §十：读不到就说读到哪，不假装完整）。
    """
    max_p, max_c, target = limits["max_passages"], limits["max_chars"], limits["target_chars"]
    n = len(rows)

    def tlen(j):
        return len(rows[j]["text_orig"] or "")

    lo = hi = i
    size, count = tlen(i), 1
    ref_lo = ref_hi = i                 # 参照行：最近一条真正并入的 passage
    fwd = bwd = True
    cut_fwd = cut_bwd = False          # 该侧是被上限截断（而非读到尽头）
    while (fwd or bwd) and count < max_p and size < max_c:
        if fwd:
            if hi >= n - 1:
                fwd = False
            else:
                j = hi + 1
                if not _can_take(rows[j], marks, j, ref_hi):
                    fwd = False
                elif count + 1 > max_p or size + tlen(j) > max_c:
                    cut_fwd = True         # 还可能往下读，只是这一屏放不下
                    fwd = False
                else:
                    hi = j; count += 1; size += tlen(j)
                    if rows[j]["kind"] == "passage":
                        ref_hi = j
        if bwd and size < target and count < max_p:
            if lo <= 0:
                bwd = False
            else:
                j = lo - 1
                if not _can_take(rows[j], marks, j, ref_lo):
                    bwd = False
                elif count + 1 > max_p or size + tlen(j) > max_c:
                    cut_bwd = True
                    bwd = False
                else:
                    lo = j; count += 1; size += tlen(j)
                    if rows[j]["kind"] == "passage":
                        ref_lo = j
        if size >= target:
            break
    return lo, hi, cut_fwd, cut_bwd


def _reach_edges(rows: list, lo: int, hi: int, marks: list,
                 max_extra_chars: int = 4000) -> tuple[int, int]:
    """块区间 [lo,hi] 之外、仍属**同一段史料**的行能延伸多远（任务书 §二十）。

    用 _expand 的同一套 can_take 规则从区间两端继续走。返回可达的 (lo', hi')；
    与 (lo,hi) 相同即表示两侧都读到本段尽头了。这一步只判断边界、不取正文，
    也不做完整走查：累计额外走过 max_extra_chars 就收手——结论一样（「外面
    还有得读」），但不会为一个 2 万字的文件白走到底。
    """
    n = len(rows)
    a, b = lo, hi
    ref_a = ref_b = lo               # 区间端行的结构键就是参照口径
    extra = 0
    while b + 1 < n and extra < max_extra_chars and _can_take(rows[b + 1], marks, b + 1, ref_b):
        b += 1
        extra += len(rows[b]["text_orig"] or "")
        if rows[b]["kind"] == "passage":
            ref_b = b
    while a - 1 >= 0 and extra < max_extra_chars and _can_take(rows[a - 1], marks, a - 1, ref_a):
        a -= 1
        extra += len(rows[a]["text_orig"] or "")
        if rows[a]["kind"] == "passage":
            ref_a = a
    return a, b


def _seg_of(row_no: int, segments: list) -> int:
    """行号落在哪个段落号区间；不在任何区间内（如首条 # src: 之前的引子）返回 -1。

    不做「就近归属」：段落号只往后管辖，把区间外的行算给最近的一段会让两段
    史料的正文被拼到一起。无证据就是无证据。
    """
    for i, (lo, hi) in enumerate(segments):
        if lo <= row_no < hi:
            return i
    return -1


def _marks_for(rows: list, segments: list) -> list:
    """预计算每行的边界证据 (结构键, 段序号, layer)。"""
    segs = [_seg_of(r["row_no"], segments) if segments else -1 for r in rows]
    return [(_boundary_key(r["section"], r["subsection"], r["ab"]),
             segs[i] if segs[i] >= 0 else None, r["layer"])
            for i, r in enumerate(rows)]


# ----------------------------------------------------------------- 组装入口

def build_result_blocks(cur, hits: list, mode: str = DEFAULT_MODE) -> dict:
    """hits = [(passage_id, file_id, row_no, seq, score)] → 全部 block（未排序）。

    同一文件内反复取数走缓存；区间重叠的块合并而不是重复展示。
    """
    limits = MODE_LIMITS[mode]
    cache = _FileCache(cur)

    # 1) 逐命中扩展（按文件分组，保证窗口查询命中缓存）
    raw: list[dict] = []
    by_file: dict[int, list] = {}
    for h in hits:
        by_file.setdefault(h[1], []).append(h)

    for fid, hs in by_file.items():
        segments = cache.segments(fid)
        # 窗口要足够宽，直到结构边界或硬上限先到（否则扩展会被窗口截断，
        # 片段看起来「短」其实是取数不够）。普通记录很短，按条数给足余量。
        margin = min(WINDOW_HARD_CAP // 2,
                     FALLBACK_MARGIN + limits["max_passages"] * 2)
        lo_row = min(h[2] for h in hs)
        hi_row = max(h[2] for h in hs)
        rows = cache.window(fid, lo_row - margin, hi_row + margin)
        if not rows:
            continue
        marks = _marks_for(rows, segments)
        pos = {r["passage_id"]: i for i, r in enumerate(rows)}
        for pid, _fid, _rno, _sq, score in sorted(hs, key=lambda h: (h[2], h[3])):
            i = pos.get(pid)
            if i is None:
                continue          # 命中行不在窗口内（极端越界），本轮不组装
            a, b, cut_f, cut_b = _expand(rows, i, limits, marks)
            raw.append({"file_id": fid, "lo": a, "hi": b, "rows": rows, "marks": marks,
                        "match_count": 1, "score": score, "hit_passage_id": pid,
                        "more_before": cut_b, "more_after": cut_f})

    # 2) 区间合并（同文件、重叠或相邻 → 并集）
    merged: list[dict] = []
    for blk in raw:
        for m in merged:
            if m["file_id"] != blk["file_id"]:
                continue
            if blk["lo"] <= m["hi"] + 1 and blk["hi"] >= m["lo"] - 1:
                m["lo"] = min(m["lo"], blk["lo"])
                m["hi"] = max(m["hi"], blk["hi"])
                m["match_count"] += blk["match_count"]
                if blk["score"] < m["score"]:
                    m["score"] = blk["score"]
                    m["hit_passage_id"] = blk["hit_passage_id"]
                m["rows"] = blk["rows"] if len(blk["rows"]) > len(m["rows"]) else m["rows"]
                m["marks"] = blk["marks"] if len(blk["marks"]) > len(m["marks"]) else m["marks"]
                break
        else:
            merged.append(dict(blk))

    # 3) 成文。合并会把区间撑大，单次扩展记的截断标记不再作数——按最终区间
    #    重算「两侧还能不能继续读」，否则合并块永远显示不出可展开（实测）。
    shaped = []
    for m in merged:
        rlo, rhi = _reach_edges(m["rows"], m["lo"], m["hi"], m["marks"])
        m["more_before"] = rlo < m["lo"]
        m["more_after"] = rhi > m["hi"]
        seg = m["rows"][m["lo"]:m["hi"] + 1]
        pids = [r["passage_id"] for r in seg if r["kind"] == "passage"]
        if not pids:
            continue
        shaped.append(_shape_block(seg, pids, m, cur))
    return {"blocks": shaped, "limits": limits}


def _shape_block(seg: list, pids: list, m: dict, cur) -> dict:
    """组装对外结构。text 由 text_orig 直接相接，绝不改写、不补标点。

    只渲染 kind='passage' 的记录（真实史料正文）；`# src:`/`<pb:>`/标题等
    解析元数据行不进入片段正文——它们只在数据检查台出现（任务书 §十七）。
    页码信息另由 pb_first/pb_last 如实给出。
    """
    body = [r for r in seg if r["kind"] == "passage"]
    text = "".join(r["text_orig"] or "" for r in body)
    pbs = [r for r in body if r["pb_block"] or r["pb_page"]]
    first = body[0] if body else None

    def side(r):
        return ((r["pb_page"] or "") + (r["pb_side"] or "")) or None

    return {
        "block_id": f"{m['file_id']}:{body[0]['row_no']}:{body[0]['seq']}" if first else None,
        "hit_passage_id": m["hit_passage_id"],
        "file_id": m["file_id"],
        "row_first": body[0]["row_no"] if first else None,
        "row_last": body[-1]["row_no"] if first else None,
        "passage_ids": pids,
        "match_count": m["match_count"],
        "score": m["score"],
        "text": text,
        "juan": first["juan"] if first else None,
        "section": first["section"] if first else None,
        "subsection": first["subsection"] if first else None,
        "division": first["division"] if first else None,
        "ab": first["ab"] if first else None,
        "layer": first["layer"] if first else None,
        "pb_first": side(pbs[0]) if pbs else None,
        "pb_last": side(pbs[-1]) if pbs else None,
        "n_passages": len(pids),
        "n_chars": len(text),
        # 该侧是否还能继续读（被展示长度上限截断，而非读到本段尽头）。
        # 前端据此决定要不要给「展开更多上下文」按钮——读到尽头就不给，
        # 免得点开发现什么都没有（任务书 §十：不制造假象）。
        "more_before": m["more_before"],
        "more_after": m["more_after"],
        # 展开时的锚点：向外走要从片段首/末记录续，不能从命中点续（会重叠）。
        "first_passage_id": pids[0],
        "last_passage_id": pids[-1],
    }


# ----------------------------------------------------------------- 对外入口

def _fetch_hits(cur, q_trad: str, bid: str | None, edition: str | None) -> list:
    """取全部命中的 (passage_id, file_id, row_no, seq, score, book_id)。

    路径选择与 engine.run_search 保持一致（trigram / bigram / LIKE），但**不分页**
    —— Result Block 必须先看全命中才能正确合并与计数。LIKE 路径无 bm25，score 记 None。
    """
    from search import engine as E

    long_terms, short_terms = E.plan_query(q_trad)
    use_fts = E.fts_tokenizer(cur) == "trigram" and bool(long_terms)
    pure_two = bool(short_terms) and all(len(t) == 2 for t in short_terms)
    use_bg = not use_fts and pure_two and E.has_bigram_fts(cur)

    where, args = ["p.kind = 'passage'"], []
    if bid:
        where.append("b.book_id = ?"); args.append(bid)
    if edition:
        where.append("LOWER(b.family) = ?"); args.append(edition)

    if use_fts or use_bg:
        table = "passages_fts" if use_fts else "passages_bg"
        terms = long_terms if use_fts else short_terms
        if use_fts:                       # 同查询中的 <3 字词作 AND 附加约束
            for t in short_terms:
                c, a = E._like_cond(t)
                where.append(c); args.append(a)
        cond = " AND ".join(where)
        return cur.execute(
            f"WITH hits AS (SELECT rowid AS pid, bm25({table}) AS score FROM {table} "
            f"WHERE {table} MATCH ?) "
            f"SELECT h.pid AS passage_id, p.file_id, p.row_no, p.seq, h.score, p.book_id "
            f"FROM hits h JOIN passages p ON p.passage_id = h.pid "
            f"JOIN files f ON f.file_id = p.file_id "
            f"JOIN books b ON b.book_id = f.book_id WHERE {cond}",
            [E.fts_match_text(terms)] + args).fetchall()

    for t in long_terms + short_terms:
        c, a = E._like_cond(t)
        where.append(c); args.append(a)
    cond = " AND ".join(where)
    return cur.execute(
        f"SELECT p.passage_id, p.file_id, p.row_no, p.seq, NULL AS score, p.book_id "
        f"FROM passages p JOIN files f ON f.file_id = p.file_id "
        f"JOIN books b ON b.book_id = f.book_id WHERE {cond}", args).fetchall()


def _exec_mode(cur, q_trad: str) -> str:
    """实际检索路径（fts/bigram/like），与 engine 的文案一致。"""
    from search import engine as E
    long_terms, short_terms = E.plan_query(q_trad)
    if E.fts_tokenizer(cur) == "trigram" and long_terms:
        return "fts"
    if short_terms and all(len(t) == 2 for t in short_terms) and E.has_bigram_fts(cur):
        return "bigram"
    return "like"


def _file_meta(cur, file_ids) -> dict:
    if not file_ids:
        return {}
    ids = list(file_ids)
    rows = cur.execute(
        "SELECT f.file_id, f.file_name, f.file_no, f.origin_path, b.title, b.book_id, "
        "b.edition, b.family FROM files f JOIN books b ON b.book_id = f.book_id "
        "WHERE f.file_id IN (%s)" % ",".join("?" * len(ids)), ids).fetchall()
    return {r["file_id"]: {"book_title": r["title"], "book_id": r["book_id"],
                           "edition": r["edition"], "family": r["family"],
                           "file_name": r["file_name"], "file_no": r["file_no"],
                           "origin_path": r["origin_path"]} for r in rows}


def search_result_blocks(cur, q: str, book: str | None = None,
                         edition: str | None = None, page: int = 1,
                         page_size: int = 20, mode: str = DEFAULT_MODE,
                         text_mode: str = "orig") -> dict:
    """检索 → 组装 Result Block → 排序分页。参数非法抛 ValueError（API 转 400）。

    `total` 是**合并后的片段数**（精确），`hit_total` 是原始命中 passage 数；
    两者不等正是第三阶段要解决的问题的可观测证据（任务书 §十二）。

    `text_mode` 是第四阶段加的繁简双轨（orig/simplified/both）：只**增加**
    `text_simplified` 等字段，`text` 仍是原样的 text_orig，一字不改。
    """
    from search import dual_text
    from search import engine as E
    from search import zh

    if page < 1:
        raise ValueError("页码从 1 开始")
    page_size = min(max(page_size, 1), E.PAGE_SIZE_MAX)
    if mode not in MODE_LIMITS:
        raise ValueError(f"未知的显示长度：{mode}（可用：{'、'.join(MODE_LIMITS)}）")
    q_trad = zh.to_traditional((q or "").strip())
    if not q_trad:
        raise ValueError("请提供搜索关键词")
    bid = E.resolve_book(cur, book)
    edition = E.resolve_edition(edition)

    hit_rows = _fetch_hits(cur, q_trad, bid, edition)
    hit_total = len(hit_rows)
    # 检索词的简体形态：前端在「只看简体/繁简对照」里要用它高亮（繁体词高亮不到
    # 简体正文上）。用的是和正文同一个转换函数，两边不会出现两套简体。
    simple_terms = [dual_text.simplify(t)["text"] for t in q_trad.split() if t]
    base = {"q": q.strip(), "q_traditional": q_trad, "mode": mode,
            "text_mode": text_mode, "terms_simplified": simple_terms,
            "exec_mode": _exec_mode(cur, q_trad),
            "book": bid or "全部", "edition": edition or "全部",
            "hit_total": hit_total, "page": page, "page_size": page_size}
    if not hit_rows:
        base.update({"total": 0, "match_count_sum": 0, "truncated": False,
                     "limits": MODE_LIMITS[mode], "results": []})
        return base

    overflow = hit_total > MAX_BLOCKS_PER_QUERY
    hits = [(r["passage_id"], r["file_id"], r["row_no"], r["seq"],
             r["score"] if r["score"] is not None else 0.0)
            for r in hit_rows[:MAX_BLOCKS_PER_QUERY]]

    out = build_result_blocks(cur, hits, mode)
    meta = _file_meta(cur, {b["file_id"] for b in out["blocks"]})
    for b in out["blocks"]:
        b.update(meta.get(b["file_id"], {}))

    # 排序：命中多的在前（任务书 §十四），同数按相关度，再按书/文件/行序稳定
    blocks = sorted(out["blocks"], key=lambda b: (
        -b["match_count"], b["score"] if b["score"] is not None else 0.0,
        b.get("book_id") or "", b.get("file_no") or 0, b["row_first"]))

    lo = (page - 1) * page_size
    page_blocks = [dual_text.attach(_public_block(b), text_mode)
                   for b in blocks[lo:lo + page_size]]
    base.update({
        "total": len(blocks),                     # 片段数（合并后，精确）
        "match_count_sum": sum(b["match_count"] for b in blocks),
        "truncated": overflow,
        "limits": dict(MODE_LIMITS[mode]),
        "results": page_blocks,
    })
    return base


# 只给前端用的字段（不含内部结构：score 是 bm25 相关度、rows/marks 是组装
# 过程的中间态，且 sqlite Row 不可 JSON 序列化）。
_INTERNAL_KEYS = ("score", "rows", "marks")


def _public_block(b: dict) -> dict:
    return {k: v for k, v in b.items() if k not in _INTERNAL_KEYS}


# ------------------------------------------------------- 按需展开更多上下文

def expand_block(cur, passage_id: int, direction: str = "both", count: int = 20,
                 before_passage_id: int | None = None,
                 after_passage_id: int | None = None):
    """从片段**边界**继续向前/向后读更多**真实**邻居（任务书 §二十）。

    以「当前片段的首/末记录」为界向外取数——不是从命中点取，否则取到的行
    会与已有片段重叠。行进中遇到与 block 相同的停止条件（layer 变 / 段落号变）
    即止，并如实告知是否读到了头（reaches_* 为 True 表示这一段到此为止，
    不是因为字数上限被截断）。

    返回一行元信息：
      passage_id/direction/count 回显参数
      rows          新增的 kind='passage' 记录（passage_id/row_no/seq/text_orig）
      added         新增条数
      next_*_passage_id  下次继续展开时应传的锚点（本次最后一/首条）；无新增则为 null
      reaches_head / reaches_tail  该方向是否已到头（True=到头，不是被截断）
    """
    count = min(max(int(count), 1), 100)
    if direction not in ("before", "after", "both"):
        raise ValueError("direction 只能是 before / after / both")

    _COLS = ("passage_id, file_id, row_no, seq, kind, layer, "
             "section, subsection, ab")
    hit = cur.execute(
        f"SELECT {_COLS} FROM passages WHERE passage_id = ?", (passage_id,)).fetchone()
    if not hit:
        raise KeyError(passage_id)
    if hit["kind"] != "passage":
        # 非正文记录（`# src:` / `<pb:>` 等）本就不在史料片段正文里，无从展开
        raise ValueError("该记录不是史料正文，无法展开上下文")
    fid = hit["file_id"]

    def anchor(pid):
        if pid is None:
            return None
        r = cur.execute(
            f"SELECT {_COLS} FROM passages WHERE passage_id = ?", (pid,)).fetchone()
        if not r or r["file_id"] != fid:
            return None
        return r

    cache = _FileCache(cur)
    segs = cache.segments(fid)
    base_seg = _seg_of(hit["row_no"], segs)

    def mark_of(row):
        """候选行的边界证据，与 _marks_for 同一口径。"""
        return (_boundary_key(row["section"], row["subsection"], row["ab"]),
                _seg_of(row["row_no"], segs) if segs else None,
                row["layer"])

    def fetch(a, explicit, order, limit):
        """向一个方向走，返回 (新增行, 是否在本段内走到尽头)。

        停止条件复用 _can_take —— 与组装片段时**同一套判定**，不另写一份：
        两处规则一旦分家，就会出现「片段到 004.42 就停了，展开却读过去」这种
        前后不一致（实测踩过）。参照行同样是「最近一条真正并入的 passage」。

        参照证据取**显式传来的那一侧端点**（前端传的片段首/末记录），且在整段
        行走中**不再变化**。若改成跟着刚读到的候选行走，参照会漂到下一条记录
        的键上，规则就失去意义（实测：从末行往回读会一路吞掉上一篇）。

        另有一条硬界：**不许读到锚点的另一侧去**，即候选行必须严格在锚点之外。
        未传锚点时以记录自身为界，等于没有外层可读。
        """
        cmp_op = "<" if order == "DESC" else ">"
        rows = cur.execute(
            f"SELECT {_COLS}, text_orig FROM passages "
            f"WHERE file_id = ? AND kind = 'passage' "
            f"AND (row_no {cmp_op} ? OR (row_no = ? AND seq {cmp_op} ?)) "
            f"ORDER BY row_no {order}, seq {order} LIMIT ?",
            (fid, a["row_no"], a["row_no"], a["seq"], limit + 1)).fetchall()
        out = []
        ended = True                      # 默认到头；下面只要能多取一条就翻案
        ref_mark = mark_of(explicit) if explicit is not None else mark_of(a)
        edge = explicit if explicit is not None else a      # 不得越过它
        for r in rows:
            if len(out) >= limit:
                ended = False             # 本次是条数收的，外面还有
                break
            if order == "DESC":
                if (r["row_no"], r["seq"]) >= (edge["row_no"], edge["seq"]):
                    break                 # 锚点另一侧，不读
            elif (r["row_no"], r["seq"]) <= (edge["row_no"], edge["seq"]):
                break
            mk = mark_of(r)
            if not _can_take(r, [ref_mark, mk], 1, 0):
                break                     # 走出这段史料了：不是被截断，是到头
            out.append({"passage_id": r["passage_id"], "row_no": r["row_no"],
                        "seq": r["seq"], "text_orig": r["text_orig"]})
        if order == "DESC":
            out.reverse()
        return out, ended

    added: list = []
    reach_head = reach_tail = None
    next_before = next_after = None
    a_before = anchor(before_passage_id)
    a_after = anchor(after_passage_id)
    if direction in ("before", "both"):
        got, reach_head = fetch(a_before or hit, a_before, "DESC", count)
        added = got + added
        if got:
            next_before = got[0]["passage_id"]
    if direction in ("after", "both"):
        got, reach_tail = fetch(a_after or hit, a_after, "ASC", count)
        added = added + got
        if got:
            next_after = got[-1]["passage_id"]

    return {"passage_id": passage_id, "file_id": fid, "row_no": hit["row_no"],
            "direction": direction, "count": count, "layer": hit["layer"],
            "segment": base_seg if base_seg >= 0 else None,
            "reaches_head": reach_head, "reaches_tail": reach_tail,
            "next_before_passage_id": next_before,
            "next_after_passage_id": next_after,
            "added": len(added), "rows": added}
