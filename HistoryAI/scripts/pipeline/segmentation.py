"""Step 3/4 — 分段与结构解析：一个 txt 文件 -> Record 列表。

容错要点（对应实测差异）：
- tls 系（尚書/左傳/史記）：句行 + ¶；org 标题（** / *** 形态不一）；左传 A/B 条目；
- SBCK 系（國語/戰國策）：整行连排 + 行内圆括号注候选（/ 为原刊行分隔）；
- 序/附录由文件层默认决定（structure.file_layer_defaults）；
- 一切拿不准 → pending_* / unknown，绝不猜测。
"""
from __future__ import annotations

import re
from pathlib import Path

from . import config
from .kanripo_header import FileHeader, file_no_of, split_header
from .records import Record
from .structure import (
    classify_comment_line,
    clean_title,
    file_layer_defaults,
    find_pb,
    is_org_heading,
    make_normalized,
    parse_pb,
    pending_split_parens,
    strip_pb,
    title_candidates,
    zuozhuan_classify,
)

# 各书 “** N X” 的语义角色（经实际扫描确认，规则集中于此）：
#   shiji   : X = 类目（紀/表/書/世家/傳）
#   shangshu: X = 篇题《堯典》
#   zuozhuan: X = 公名（隱公…哀公）
H2_ROLE = {"shiji": "division", "shangshu": "section", "zuozhuan": "juan"}

# 文件内分段（#+PROPERTY: FILE ...-段名. 块）段名 → 语义层。
# 段名取自 FILE 属性末段，是 kanripo 自身对内容的命名（不是我们的猜测）。
PART_LAYER_MAP = {
    "序": "preface", "叙": "preface", "敘": "preface",
    "目録": "toc", "目录": "toc",
    "後跋": "backmatter", "跋": "backmatter",
}
PART_KEYWORDS = ("序", "叙", "敘", "跋", "目", "凡例")

# SBCK 明文卷首题候选（確認度足够高的形态才给 ok；其余 pending_section）
GUOYU_SECTION_RE = re.compile(r"^(周|魯|齊|晉|鄭|楚|吳|越)語(上|中|下)?第[一二三四五六七八九十]+")
GUOYU_HEAD_RE = re.compile(r"^.{0,12}韋氏解")
ZHANGUOCE_SECTION_RE = re.compile(
    r"^[　\s]*(東周|西周|秦|齊|楚|趙|魏|韓|燕|宋|衛|中山)([(（]凡[^)）]*[)）])?\s*$"
)


def empty_line(line: str) -> bool:
    return not line.strip() and config.PARA_CHAR not in line


def only_pb_line(line: str) -> bool:
    t = strip_pb(line).replace(config.PARA_CHAR, "")
    return "<pb:" in line and not t.strip()


class FileSegmenter:
    """单个 txt 的状态机。逐行：页码继承 → 注释块合并 → 标题/条目/正文分流。"""

    def __init__(self, header: FileHeader, book_dir: str, file_no: int | None, text: str):
        self.book_dir = book_dir
        self.file_no = file_no
        self.meta = header.metadata
        self.family = ("sbck" if (header.metadata.get("BASEEDITION") or "").strip() == "SBCK"
                       else "tls" if (header.metadata.get("BASEEDITION") or "").strip() == "tls"
                       else None)
        self.lines = text.splitlines()
        self.records: list[Record] = []
        self.cur_pb_raw = ""
        self.cur_pb = None
        self._reset_context()

    # ---- 语义上下文（文件内随标题推进）----
    def _reset_context(self) -> None:
        layer, status, note = file_layer_defaults(
            self.book_dir, self.file_no, self.family, self.meta)
        self.def_layer, self.def_status, self.layer_note = layer, status, note
        self.part_layer: str | None = None   # 文件内分段（FILE 段名）的层
        self.part_label: str | None = None
        self.juan: str | None = None
        self.section: str | None = None
        self.division: str | None = None
        self.zb_year: str | None = None      # 左传：当前公年份（如 '1.1'）
        self.ab: str | None = None           # 左传：A(經)/B(傳)

    # ---- 通用记录构造 ----
    def _base(self, row_no: int, text_orig: str, kind: str, layer: str | None = None,
              status: str | None = None) -> Record:
        layer = layer if layer is not None else (self.part_layer or self.def_layer)
        status = status if status is not None else self.def_status
        rec = Record(kind=kind, layer=layer, status=status, row_no=row_no,
                     text_orig=text_orig)
        rec.juan = self.juan
        rec.section = self.section
        rec.division = self.division
        rec.ab = self.ab
        # 页码：行内 pb 优先，否则继承前文最近 pb
        pbs = find_pb(text_orig)
        if pbs:
            raw = pbs[0][0]
            if rec.pb_raw == "" or pbs[0][1] == 0:
                rec.pb_raw = raw
                rec.pb = parse_pb(raw)
            if len(pbs) > 1:
                rec.pb_last_raw = pbs[-1][0]
        if not rec.pb_raw:
            rec.pb_raw = self.cur_pb_raw
            rec.pb = parse_pb(self.cur_pb_raw) if self.cur_pb_raw else None
        # 更新“最近页码”游标（整行扫描）
        for raw, _ in pbs:
            self.cur_pb_raw = raw
            self.cur_pb = parse_pb(raw)
        rec.special_chars = config.KR_CODE_RE.findall(text_orig)
        rec.normalized_text = make_normalized(text_orig, kind, layer)
        return rec

    # ---- 主循环 ----
    def run(self) -> list[Record]:
        lines = self.lines
        n = len(lines)
        # 绝对行号 = 1 起；头部行跳过（本类从 body 开始，行号信息由调用方传入 first_body_line）
        i = self.first_line_index - 1
        while i < n:
            line = lines[i]
            row_no = i + 1
            stripped = line.strip()

            # 1) 文件内分段块（#+PROPERTY: ... FILE SB..-後跋./-目録. 等，
            #    只出现在 SBCK 系首文件中，标志序/跋/目録等部分的开始）
            if line.startswith("#+"):
                block = [line]
                j = i + 1
                while j < n and lines[j].startswith("#+"):
                    block.append(lines[j])
                    j += 1
                self._emit_part_block(row_no, block)
                i = j
                continue

            # 1b) 页码行（只有 <pb:...> 及可能跟的 ¶）
            if "<pb:" in line and only_pb_line(line):
                rec = self._base(row_no, line, "page")
                rec.layer = "structure"
                rec.status = "ok"
                self.records.append(rec)
                i += 1
                continue

            # 1c) 空白残行（内容仅为空格与 ¶，如 shiji '　　¶' 页底残行）
            if line.strip().replace(" ", "").replace("　", "") == config.PARA_CHAR:
                rec = self._base(row_no, line, "noise")
                rec.layer = "structure"
                rec.status = "ok"
                self.records.append(rec)
                i += 1
                continue

            # 2) 注释块（# 开头连续行合并；src/dating 等键原样收集）
            if line.startswith("#"):
                block = [line]
                j = i + 1
                while j < n and lines[j].startswith("#"):
                    block.append(lines[j])
                    j += 1
                self._emit_comment_block(row_no, block)
                i = j
                continue

            # 3) 空行（保留为 passage？空行不入记录，避免噪声；原文在 raw 视图仍可见）
            if empty_line(line):
                i += 1
                continue

            # 4) 正文/标题分流
            self._emit_content(line, row_no)
            i += 1
        return self.records

    # ---- 文件内分段块 ----
    def _emit_part_block(self, row_no: int, block: list[str]) -> None:
        text_orig = "\n".join(block)
        rec = self._base(row_no, text_orig, "part")
        rec.layer = "structure"
        rec.status = "ok"
        rec.normalized_text = None
        # 提取 FILE 属性中的段名（最后一段 '-' 之后、'.' 之前）
        label = None
        for ln in block:
            m = re.match(r"^#\+PROPERTY:\s*FILE\s+(.+)$", ln)
            if m:
                tail = m.group(1).strip()
                if "-" in tail:
                    label = tail.rsplit("-", 1)[1].rstrip(".").strip()
        if label and any(k in label for k in PART_KEYWORDS):
            self.part_label = label
            self.part_layer = PART_LAYER_MAP.get(label, "unknown")
            rec.notes.append(f"文件内分段开始: {label}")
            if self.part_layer == "unknown":
                rec.status = "pending_section"
        else:
            rec.notes.append("未识别段名，按普通元数据块保留")
        self.records.append(rec)

    # ---- 注释块 ----
    def _emit_comment_block(self, row_no: int, block: list[str]) -> None:
        text_orig = "\n".join(block)
        rec = self._base(row_no, text_orig, "comment")
        keys = []
        src_refs = []
        for ln in block:
            k, res = classify_comment_line(ln)
            keys.append(k)
            if res:
                src_refs.append(res)
        rec.notes.append("comment_keys:" + ",".join(sorted(set(keys))))
        if src_refs:
            first = src_refs[0]
            rec.source_reference = {
                "raw": first["raw"],
                "src_text": first["src_text"],
                "prefix": first["prefix"],
                "section_ref": first["section_ref"],
                "src_count": len(src_refs),
            }
        rec.layer = "structure"
        rec.status = "ok"
        rec.normalized_text = None
        self.records.append(rec)

    # ---- 正文行/标题行 ----
    def _emit_content(self, line: str, row_no: int) -> None:
        stripped = line.strip()
        # 4a) org 标题（tls 系为主；SBCK 异常出现也保留为结构行，不改正文）
        lvl, _code, _title = is_org_heading(line)
        if lvl:
            self._handle_org_heading(lvl, _code, line, row_no)
            return

        # 4b) 左传 A/B 体系（先于明文标题，避免 'A1.1《…》' 误入普通标题）
        if self.book_dir == "zuozhuan":
            zk, zextra = zuozhuan_classify(line)
            if zk == "heading":
                ab = zextra["ab"]
                code = zextra.get("code")
                if code is None:
                    rec = self._mk_heading(line, row_no)
                    rec.ab = ab
                    rec.notes.append(f"左传 {ab} 类卷题")
                    self._append(rec)
                    return
                # A1.1《隱公元年經》 式卷题
                title = zextra.get("title", "")
                rec = self._mk_heading(line, row_no)
                rec.ab = ab
                rec.section = clean_title(title) if title else rec.section
                self.zb_year = code
                self.ab = ab
                if title:
                    # 年份卷题下推为上下文：其下条目 sec=隱公元年經（便于核对归属）
                    self.section = rec.section
                if ab == "A":
                    rec.notes.append("春秋經卷题")
                else:
                    rec.notes.append("左傳卷题")
                self._append(rec)
                return
            if zk == "passage":
                rec = self._mk_passage(line, row_no)
                rec.ab = zextra["ab"]
                rec.subsection = zextra["code"]
                rec.section = self.section or self.juan
                self.ab = zextra["ab"]
                self._append(rec)
                return

        # 4c) 明文篇题候选（史记 1.1《五帝本紀》 / *** 2.1　《三代世表》已走 org 分支；此处兼容无星标行）
        for pat in title_candidates():
            m = pat.match(line)
            if m:
                rec = self._mk_heading(line, row_no)
                rec.section = clean_title(m.group(2)) if m.lastindex and m.lastindex >= 2 else None
                rec.notes.append("明文篇题")
                self._append(rec)
                return

        # 4d) SBCK 明文卷首题（guoyu / zhanguoce 特有形态）
        if self.family == "sbck" and self.def_layer in ("main", "preface"):
            s = stripped
            if GUOYU_HEAD_RE.search(s) or GUOYU_SECTION_RE.match(s):
                rec = self._mk_heading(line, row_no)
                rec.section = rec.section or self._sbck_section_label(s)
                rec.status = "ok"
                self._append(rec)
                return
            if self.book_dir == "zhanguoce" and ZHANGUOCE_SECTION_RE.match(s):
                rec = self._mk_heading(line, row_no)
                rec.section = self._sbck_section_label(s)
                rec.status = "pending_section"
                self._append(rec)
                return

        # 4e) SBCK 正文行内括号注候选拆分
        if (self.family == "sbck" and self.def_layer == "main"
                and ("(" in line or "（" in line)):
            self._emit_sbck_row(line, row_no)
            return

        # 4f) 普通正文行
        rec = self._mk_passage(line, row_no)
        self._append(rec)

    def _sbck_section_label(self, s: str) -> str:
        t = re.sub(r"^[　\s]+", "", s)
        t = t.split("　")[0]
        return t[:16] or None

    def _mk_heading(self, line: str, row_no: int) -> Record:
        rec = self._base(row_no, line, "heading")
        rec.layer = "structure"
        rec.status = "ok"
        return rec

    def _mk_passage(self, line: str, row_no: int) -> Record:
        rec = self._base(row_no, line, "passage")
        if rec.status != "ok":
            pass  # 文件层默认已带（如 pending_section 的 preface）
        return rec

    def _append(self, rec: Record) -> None:
        self.records.append(rec)

    # ---- org 标题按角色处理 ----
    def _handle_org_heading(self, lvl: str, code: str, line: str, row_no: int) -> None:
        rec = self._mk_heading(line, row_no)
        # 由 structure.is_org_heading 传回标题文字（去掉《》与空白）
        if lvl == "h2":
            role = H2_ROLE.get(self.book_dir, "section")
            m = re.match(r"^\*\*\s+(\d+)\s*(.*)$", line)
            text = clean_title(m.group(2)) if m else None
            if role == "division":
                self.division = text or None
            elif role == "juan":
                self.juan = text or None
                # 进入新公：重置 A/B 年份与年份篇题上下文
                self.zb_year = None
                self.ab = None
                self.section = None
            else:
                self.section = text or None
        elif lvl == "h3":
            # *** 2.1　《三代世表》：code=2.1，标题在行内后续《…》里
            m = re.match(r"^\*\*\*\s*[0-9.]+\s*(.*)$", line)
            text = clean_title(m.group(1)) if m else None
            if text:
                self.section = text or None
        rec.notes.append(f"org_{lvl}")
        self._append(rec)

    # ---- SBCK 行内括号注 ----
    def _emit_sbck_row(self, line: str, row_no: int) -> None:
        pieces = pending_split_parens(line)
        is_multi = len(pieces) > 1
        if not is_multi and pieces[0][3] == "main":
            # 无有效括号 → 普通行
            rec = self._mk_passage(line, row_no)
            rec.char_start, rec.char_end = 0, len(line)
            self._append(rec)
            return
        # 行尾的 ¶/空白归入上一片段（行重建仍连续；¶ 自身也要并回去，
        # 否则产生只含 "¶" 的孤立记录——strip() 对 ¶ 恒非空，须显式剥除）
        while len(pieces) > 1 and pieces[-1][3] == "main":
            tail_txt, _, _, _ = pieces[-1]
            residue = tail_txt.replace(config.PARA_CHAR, "").replace(" ", "").replace("　", "")
            if residue:
                break
            pieces.pop()
            pt, ps, pe, ptag = pieces[-1]
            pieces[-1] = (pt + tail_txt, ps, pe + len(tail_txt), ptag)
        # 拆成 main / paren 片段记录；行号相同、偏移不同
        # 重建校验按 (row_no, char_start) 顺序即可还原整行
        for seg_text, s, e, tag in pieces:
            rec = self._base(row_no, seg_text, "passage")
            rec.char_start, rec.char_end = s, e
            if tag == "paren":
                rec.layer = "commentary_candidate"
                rec.status = "pending_commentary"
                rec.notes.append("行内圆括号注候选（注者不猜）")
            else:
                if rec.status == "ok":
                    pass
            # 特殊字符在全行范围已有 _base 计算；空主段（行首即括号）仍保留
            if seg_text:
                self._append(rec)
        # 该行若因括号异常退回整行 main（pending_split_parens 已处理）

    # 供 run() 使用：记录正文从第几行开始（由 segment_file 传入）
    first_line_index: int = 1


def segment_file(path: Path) -> tuple[FileHeader, list[Record], str]:
    """txt 文件 -> (header, records, body)。body 供重建校验。"""
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8")
        decode_error = False
    except UnicodeDecodeError:
        text = raw.decode("utf-8", errors="replace")
        decode_error = True
    header, body = split_header(text)
    file_no = file_no_of(path.name)

    # body 行相对文件的行号 = header 行数 + 1 起
    header_line_count = len(header.raw_header.splitlines()) if header.raw_header else 0
    seg = FileSegmenter(header, path.parent.name, file_no, text)
    seg.first_line_index = header_line_count + 1  # 1-based 绝对行号
    # body 从 header 结束后立即开始：seg 需要从 header_line_count 行开始遍历
    # FileSegmenter 内部以 lines[i] 循环；此处换算成绝对行号偏移：
    seg.lines = text.splitlines()
    seg.run()
    for r in seg.records:
        if decode_error:
            r.notes.append("decode_error")
    return header, seg.records, body
