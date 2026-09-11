"""解析记录模型（JSONL 一行 = 一条记录）。

kind:
  page     只有 <pb:...> 的页码行（正文中的页码标记保留在文本内，不单独成记录）
  heading  结构标题（org ** / 明文篇题 / 左传 A/B 卷题等）
  comment  # 开头的注释块（# src: / # dating: 等，整块合并成一条）
  passage  正文单元（tls 一句一行 / SBCK 一行或行内切出片段）

layer（语义层，宁可 unknown/pending 不猜）:
  main / preface / appendix / structure / commentary_candidate / unknown

status:
  ok / pending_commentary / pending_section / pending_line
"""
from __future__ import annotations

from dataclasses import dataclass, field

LAYER_VALUES = {"main", "preface", "appendix", "backmatter", "toc",
                "structure", "commentary_candidate", "unknown"}
STATUS_VALUES = {"ok", "pending_commentary", "pending_section", "pending_line"}
KIND_VALUES = {"page", "heading", "comment", "part", "noise", "passage"}


@dataclass
class Record:
    kind: str = "passage"
    layer: str = "unknown"
    status: str = "pending_line"
    row_no: int = 0
    juan: str | None = None        # 语义卷（如左传：隱公；有把握才填）
    section: str | None = None     # 当前节/篇题（如 堯典 / 五帝本紀 / 周語上第一候选）
    subsection: str | None = None  # 左传 A/B 条目号等
    division: str | None = None    # 史记类目 紀/表/書/世家/傳
    ab: str | None = None          # 左传 A(經)/B(傳)
    text_orig: str = ""
    normalized_text: str | None = None
    char_start: int | None = None  # 在原始行内的字符偏移（SBCK 行内切分才有意义）
    char_end: int | None = None
    pb: dict | None = None          # 本单元首个 <pb:...> 结构化 {raw,book_id,edition,block,page,side}
    pb_raw: str = ""
    pb_last_raw: str = ""
    special_chars: list = field(default_factory=list)
    source_reference: dict | None = None  # {raw, src_text, prefix, section_ref, keys:[...]}
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "layer": self.layer,
            "status": self.status,
            "row_no": self.row_no,
            "juan": self.juan,
            "section": self.section,
            "subsection": self.subsection,
            "division": self.division,
            "ab": self.ab,
            "text_orig": self.text_orig,
            "normalized_text": self.normalized_text,
            "char_start": self.char_start,
            "char_end": self.char_end,
            "pb": self.pb,
            "pb_raw": self.pb_raw,
            "pb_last_raw": self.pb_last_raw,
            "special_chars": self.special_chars,
            "source_reference": self.source_reference,
            "notes": self.notes,
        }
