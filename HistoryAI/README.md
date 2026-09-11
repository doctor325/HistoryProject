# HistoryAI — 先秦典籍解析管线 + 全文检索查询台

第一阶段把 Kanripo 五部先秦典籍的原始 txt 解析为**可人工检查的结构化数据**并提供
逐条核对前端（原始史料 → Parser → 数据库）；第二阶段在其上加**先秦史料全文检索 +
中文查询台 + 上下文接口**（检索/上下文均出自数据库真实记录，不接任何 AI/向量模型）。

原则（贯穿全部代码）：

> **原始史料 > Parser > 数据库 > 检索 > AI**
> 宁可结构化程度低一点（pending / unknown / raw），也不要解析错原文。

## 目录

```
HistoryProject/
├── HistoryLibrary/kanripo/      ← 原始史料（只读！任何阶段绝不写它）
│   ├── guoyu/       國語    KR2e0001  SBCK   22 txt
│   ├── shangshu/    尚書    KR1b0001  tls    59 txt
│   ├── shiji/       史記    KR2a0001  tls    14 txt
│   ├── zhanguoce/   戰國策  KR2e0003  SBCK   11 txt
│   └── zuozhuan/    春秋左傳 KR1e0001  tls    12 txt
└── HistoryAI/
    ├── scripts/pipeline/       解析管线（本阶段实现）
    │   ├── config.py           路径/正则集中定义（不硬编码五书）
    │   ├── kanripo_header.py   文件头 org 元数据解析
    │   ├── inventory.py        只读扫描 → data/metadata/{books,files,import_runs}.json
    │   ├── records.py          记录模型（kind/layer/status/…）
    │   ├── structure.py        集中规则（pb/出处/标题/括号注/分层/归一化）
    │   ├── segmentation.py     逐文件状态机 → 记录流
    │   ├── jsonl_io.py         五书 → data/processed/parsed_*.jsonl
    │   ├── sqlite_store.py     jsonl → data/database/history.db（全量重建，幂等）
    │   ├── validate.py         对账校验（sha256/字符守恒/语法）
    │   └── run_all.py          一键编排入口
    ├── search/                 全文检索（第二阶段）
    │   ├── engine.py           FTS5 trigram / bigram / LIKE 三路调度 + 书/版别名
    │   ├── context.py          同文件真实相邻记录（上下文端点）
    │   └── zh.py               简体↔繁体（系统 LCMapStringEx，零依赖，失败恒等回退）
    ├── api/                    stdlib http.server 只读 API + 静态前端
    ├── frontend/               先秦史料查询台（纯 vanilla，零依赖，中文界面）
    ├── tests/                  unittest 144 例（一阶段 43 + 二阶段 85 + 四阶段 16）
    ├── database/schema.sql     SQLite 结构（与 sqlite_store.SCHEMA 镜像）
    └── data/                   （git 忽略）全部派生产物：metadata/processed/database/logs
```

`prompts/` 为空脚手架。`docs/` 下是三、四阶段报告与数据来源说明。

## 解析模型

每一条入库记录（`passages` 表，JSONL 一行）字段：

| 字段 | 含义 |
|---|---|
| `kind` | page(整页行)/heading(标题)/comment(# src 等注释块)/part(序跋目録分段)/noise(页底残行)/passage(正文) |
| `layer` | main 正文 / preface 序 / appendix 附录 / backmatter 跋 / toc 目录 / structure 结构 / commentary_candidate 行内注候选 |
| `status` | ok / pending_commentary / pending_section / pending_line |
| `text_orig` | **原文原样**：含 `<pb:…>`、¶、`&KR…;`，一个字符不改 |
| `normalized_text` | 仅派生的检索文本（去 pb/¶/行首空格），非原件 |
| `row_no` / `char_start/char_end` | 原文行号 / SBCK 行内括号切分的字符偏移（可拼回整行） |
| `juan/section/subsection/division/ab` | 有把握才填的语义上下文 |
| `pb_*` | 页码标记结构化（block-page-a/b 半叶） |
| `special_chars` | 该行 `&KR…;` 缺字码（只保留，不替换） |
| `source_reference` | `# src: SHU 1.1 …` 出处（原文块 + 解析的 section_ref） |

两族差异的处理（实测确认，规则集中在 structure.py/segmentation.py）：

- **tls 系**（尚書/左傳/史記）：¶ 断句一句一行；org 标题（`** N` 级）；左传 A=經 B=傳
  条目（A1.1《隱公元年經》卷题 → section 下推给其下条目，子条编号入 subsection）；
  `# src:` 出处注释块原样合并。
- **SBCK 系**（國語/戰國策）：整行连排；行内圆括号（韦昭注/高诱注形态）切为
  `commentary_candidate / pending_commentary` 片段（注者不猜）；`_000` 首文件按
  `#+PROPERTY: FILE …-序/跋/目録.` 段名分 preface/backmatter/toc；國語序文件头另有
  人工确认例外表（`file_layer_defaults`）。
- 一切拿不准 → `pending_*`/保留原文，绝不猜测。

## 运行

零第三方依赖（Python ≥3.10 stdlib）。Windows 下建议先 `set PYTHONIOENCODING=utf-8`。

```bash
# 全流程：inventory → 分段 → JSONL → SQLite → 校验（产物全部重建，~15 秒）
python -m scripts.pipeline.run_all

# 分阶段（-h 看开关）
python -m scripts.pipeline.run_all --no-validate

# 只跑校验（须先有 data/database/history.db）
python -m scripts.pipeline.validate

# 测试（144 例；含真实史料/真实库抽查，library 或库不在场时对应文件自动跳过）
# 注意：tests/ 下没有 __init__.py，`python -m unittest discover -s tests` 会报
#      "Start directory is not importable"，必须逐个文件跑并带 PYTHONPATH=.：
for f in tests/test_*.py; do PYTHONPATH=. PYTHONIOENCODING=utf-8 python "$f"; done

# 性能基准（打印逐操作 min/median，见「第二阶段性能实测」）
python tests/perf_phase2.py

# 启动中文查询台（浏览器打开 http://127.0.0.1:8600/）
python -m api.main
```

日志在 `data/logs/pipeline_*.log`；校验报告写 `data/metadata/validation.json`。
数据库是纯派生物：删掉 `data/` 后跑一次 `run_all` 即复原，library 从不被写入。

## 校验结果（2026-09-09 全量）

| 项 | 结果 |
|---|---|
| 书 / txt 文件 | 5 / 118 |
| 记录总数 | 224,822（正文 203,308 + 结构/页码等） |
| sha256 对账 / 头部元数据对账 | 118/118 一致 |
| 字符守恒（逐行拼回 == library 原件） | 118/118 通过 |
| 不合法 `<pb:>` / `&KR…;` | 0 / 0 |
| 待确认 pending | 17,347（全部为行内注候选，见下） |
| 缺字码 &KR | 70 种 / 172 处，原样保留 |

逐书（2026-09-09 run_all 产物）：

| 书 | txt | 记录 | 正文 main | 括号注候选 pending_commentary | 序 | 跋/目 | #src 出处块 |
|---|---|---|---|---|---|---|---|
| 尚書 | 59 | 7,410 | 5,686 | 0 | 0 | 0 | 802 |
| 春秋左傳 | 12 | 53,548 | 45,155 | 0 | 0 | 0 | 5,491 |
| 史記 | 14 | 122,862 | 112,620 | 0 | 0 | 0 | 5,112 |
| 國語 | 22 | 15,910 | 8,217 | 7,012 | 35 | 0 | 0 |
| 戰國策 | 11 | 25,092 | 13,259 | 10,335 | 251 | 183 | 0 |

## 已知问题与取舍（原因 / 影响 / 下一步）

1. **SBCK 行内圆括号注只标候选，不判注者**
   原刊行文中 `(…)` 既可能是注（韦昭解/高诱注）也可能是行内夹注混排、割裂正文。
   现一律切为 `commentary_candidate/pending_commentary` 片段（原文完整保留、可拼回）。
   影响：國語 7,012 / 戰國策 10,335 条待人工确认；正文 main 计数中不含它们。
   下一步：前端逐条确认（见「检查路径」），确认后才有依据升级为正注释层。
2. **空行与文件头不入 passages 表**
   原因：设计为去噪；原件永不丢失（`files.meta_json` 保留全头部；raw 视图与 library 可看原文；
   validate 的"字符守恒"正是按该规则对账并全量通过的）。
3. **tls 尾部残行 `　　¶` 归 kind=noise**（史記 47 行），正文不漏。
4. **尚書 2 个 `# src:` 块未挂到 source_references 行**（59 书中紧邻注释块且无后续正文条，
   后块覆盖前块）。影响：原出处块本身仍在 passages.comment（`source_ref_json` 可见），
   仅关联表少 2 行。下一步：loader 对连续 src 块改为各挂一行。
5. **左傳 B 系条目编号不齐**（`B1` 与 `A1.1.1` 风格不一）——两条都容错解析，
   但 `subsection` 只在有编号时填；无编号的 B 系续行留空（不猜）。
6. **`file_id` 每次全量重建从 1 起**（已重置 sqlite_sequence）；若以 ID 做了外部引用，
   重建后需重查。API 全程按当前库查询，不受影响。

## 检查路径（验收步骤）

1. 启动：`python -m api.main`，浏览器开 `http://127.0.0.1:8600/`。
2. 首页见五书统计（正文/待确认/缺字行数）。
3. 选「國語 → 文件列表 → KR2e0001_001.txt（卷一正文）」：
   - 头部元数据卡可见 TITLE/ID/BASEEDITION/WITNESS 原样；
   - 「解析记录」页：正文 main 行文本含 `<pb:…>`（绿色）、¶（灰）、行内括号注为紫字
     `commentary_candidate/pending_commentary`；行号 + char 偏移可拼回整行；
   - 用 status=「pending_commentary」过滤逐条检查注的切分是否合理（预期：像
     `(也征正也上討下之稱…)` 这类确实是注；发现正文被误切的，把行号记下来反馈）；
   - 「原文对照」页：同一文件的 library 原件逐行并排，标注该行在解析层的归属
     （文件头/空行/并入上块均有标注）——正文行两边应逐字一致。
4. 选「戰國策 → KR2e0003_000.txt」验证序(251)/後跋(170)/目録(13) 分段正确，
   没有一段正文混进序跋层。
5. 选「春秋左傳 → KR1e0001_001.txt」：juan=隱公、A1.1《隱公元年經》卷题 → 其下条目
   section=隱公元年經、A/B 分组、`# src:` 出处块出现在细看里。
6. 选「史記 → KR2a0001_201.txt（表）」验证 division=表、`*** 2.1《三代世表》` 篇题、
   页底残行标 noise。
7. 任一正文行点「细看」：normalized_text（去 pb/¶）、出处、缺字码 &KR…;（如國語
   KR2e0001_002.txt 附近）都应在。

## 设计说明（一处与任务书原稿的偏差）

任务书原拟 segmented_*.jsonl 与 parsed_*.jsonl 两层都出。实测逐行记录两者几乎重叠
（每条都带 text_orig），双份近 2 倍体积且无信息增量，因此只产 `parsed_*.jsonl` 一份
权威中间层（SQLite 由它载入），说明写在 jsonl_io.py 模块 docstring。若后续确需
segmented 全量层可随时生成，不改解析逻辑。

---

# 第二阶段：先秦史料全文检索 + 中文查询台

## 检索架构（search/engine.py）

检索语料 = `passages.kind='passage'` 行的 **normalized_text**（第一阶段的检索派生文本，
内容与原文字符守恒对账过）；`text_orig` 永不进索引、永不被改，命中后展示/上下文一律
以 `text_orig` 为准。输入查询先经 `zh.to_traditional` 转繁体（齐桓公→齊桓公），
系统简繁映射失败时恒等回退，绝不猜字。

三路调度（按 `plan_query` 分词结果）：

| 查询形态 | 路径 | 说明 |
|---|---|---|
| 任一词 ≥3 字 | FTS5 trigram（`passages_fts`，external-content） | 子串式命中，词间隐式 AND；同查询 <3 字词作 LIKE 附加约束 |
| 纯 2 字词 | FTS5 unicode61（`passages_bg`，相邻两字 token） | 与 `LIKE '%词%'` **集合等价**；点查 ~5ms 取代全扫 ~350ms |
| 含 1 字词 / 无索引表 / 无 FTS5 | LIKE 全扫补充 | 1 字词无任何索引可走（本地实测全扫 ~350ms） |

两张 FTS 表都由 `sqlite_store._fts_build` 在 `run_all` 重建末尾动态创建
（trigram ~2s / bigram ~2s，合计重建约 12s），均为纯派生物；
`stats.fts.{tokenizer,docs,bigram}` 记录实际建成的分词器与文档数。

书/版本过滤：书名接受 简/繁/别名/《》/书号（「国语」「國語」「guoyu」「KR2e0001」都可）；
别名从 books 表现场构建 + 常用写法表，识别不了返回 400 并列出可用书号。出处字段只取
数据库真实值，缺失即「暂无」；**绝不从 `KRxxxx_NNN.txt` 文件名猜章节**。

## API（全部只读；列表一律分页，默认 20，上限 100，绝不全量返回）

| 路由 | 说明 |
|---|---|
| `/api/search?q=&book=&edition=&page=&page_size=` | 全文检索；`mode: fts/bigram/like`；每项含完整出处块（书名/卷/篇/节/版本/原文件/页码/出处注）+ 原文 |
| `/api/passages/{id}/context?before=3&after=3` | 真实相邻记录：同文件 kind=passage，按 (row_no, seq) 前 3/后 3（上限 10），**非 AI 补写** |
| `/api/stats` | 统计 + FTS 状态（docs 为正文文档数口径，非全表行数） |
| `/api/books`、`/api/books/{id}/files`、`/api/files/{id}`、`/api/files/{id}/passages`、`/api/files/{id}/raw`、`/api/passages/{id}` | 第一阶段检查台全部保留 |

前端 = 无依赖 hash SPA（`frontend/` 三件套）：首页搜索 + 史料卡片；`#/search` 全文检索
（史书/版本筛选 + 每页 20/50/100）；`#/p/{id}` 阅读式史料详情（上下文前 3/后 3 可点跳转、
数据详情默认折叠）；`#/books`/`#/book/{id}`/`#/file/{id}` 数据检查台（解析记录 + 原文对照
两页签，行级数据详情）；`#/pending` 待确认注释逐条过 SBCK 原刊括号（状态保持
pending_commentary，系统不自动归属韦昭/高诱）；`#/about` 项目说明。视觉：纸张底色 +
印章红点缀、宋体正文、无第三方库。

## 第二阶段性能实测（2026-09-09，`python tests/perf_phase2.py`，本地 loopback，
热身 2 次后 5 次取 min/median）

| 操作 | min | median |
|---|---|---|
| /api/stats（首页数据） | 90ms | 92ms |
| /api/books（首页五书卡） | 153ms | 167ms |
| /api/books/KR2e0001/files（22 文件） | 18ms | 24ms |
| /api/files/*/passages（第 21 页 ×50） | 1.8ms | 2.1ms |
| /api/files/*/raw（200 行，冷/热读原件） | 2–4ms | 3–7ms |
| /api/search FTS（齐桓公 / 齊桓公 卒） | 4.1ms | 5–6ms |
| /api/search bigram（管仲） | 4.4ms | 4.9ms |
| /api/search 限定书+版（桓公@國語SBCK） | 14ms | 15ms |
| /api/search 深分页（p5 ×50） | 6.9ms | 8.8ms |
| /api/passages/{id} 详情 | 3.5ms | 4.5ms |
| /api/passages/{id}/context 上下文 | 4.7ms | 5.3ms |

全部 ≤170ms，目标 ≤300ms 达成。旧版检查台卡顿根因（每文件默认 limit=100 渲染 +
每行高亮 DOM + 每路由重复 /api/stats + 一次 22 万行统计扫描）已在重设计 + 聚合改造后消除：
`list_books/list_files` 由「每行相关子查询」改为单趟 `GROUP BY … FILTER` 聚合（0.9s→0.17s）。

## 第二阶段已知问题

1. **「崤之战」搜不到**：语料原文作「殽」（殽之戰，66 处），崤为后世通行写法——属原文
   用字而非缺陷；界面零结果提示会引导改用短词。
2. **1 字查询（如「桓」「卒」）仍走 LIKE 全扫 ~350ms**：没有能覆盖 1 字词的索引；该类
   查询多为文献学提问式（桓→桓公 430 处），可接受并已记录。
3. **data/raw/pre_qin/**：早期下载的冗余原始副本（与 HistoryLibrary 有交集但不在其目录），
   按阶段一结论**不删不盖**，仅此标注；库只认 HistoryLibrary。
4. `passages_bg`/`passages_fts` 为派生表：删除 data/ 后 run_all 全量重建即复原；
   library 与 data/raw 零写入。
5. `stats.fts.docs` 为正文文档数（203,308）口径；external-content FTS 的 count(*) 会读
   content 表返回全表行数，已改为按插入谓词从 content 侧计数（见 sqlite_store 注释）。

## 第二阶段验收路径（浏览器）

1. `python -m api.main` → http://127.0.0.1:8600/
2. 首页搜索框试示例：齐桓公（96 条）/ 管仲（102 条）/ 城濮（31 条）——简体自动转繁体；
   顶部「数据检查」「待确认注释」在导航可见。
3. 结果卡：书名/卷篇/页码/版本齐全者如实显示、缺失显示「暂无」；括号注候选有紫色
   「原刊括号内容 · 待确认」角标；点「查看原文 · 上下文」。
4. 详情页：正文宋体大字号；上下文 = 前 3 后 3 真实相邻句（点任意段跳转）；
   「数据详情（默认折叠）」展开可见 row/char 偏移/出处注/缺字码。
5. `#/pending` 选國語 → 某文件：仅列出 pending_commentary 括号片段；确认其切分是否合理。
6. `#/file/{id}?tab=raw`：原件与解析层逐行对照；`#/about` 见数据口径说明。
7. 检索限定：国语 + 四部丛刊（SBCK）→ 结果全部出自該版本；tls 版查询国语返回空。
8. 性能复测：`python tests/perf_phase2.py`。

---

# 第四阶段：自然语言提问 + 事件级史料聚合 + 繁简双轨

**只检索，不生成。** 系统回答「哪些史料在讲这件事」，不回答「这件事是什么样的」——
后者是第五阶段。扩展出的每个词都能在语料里查到实际出现，查不到的词不进结果。

## 提问链路（`level=question`）

```
用户问题 → 问题分析 → 实体识别 → 意图识别 → 古代表达扩展
        → 候选史料召回 → 相关性排序 → 完整史料片段 → 事件级聚合 → 不同史书对照
```

| 路由 | 说明 |
|---|---|
| `/api/search?q=…&level=question&text=orig\|simplified\|both` | 提问模式；返回 `question`（分析）/ `expanded`（扩展词）/ `aggregation`（事件）/ `notes`（召回说明） |

`level=question` 与 `level=passage`（二阶段）、`level=block`（三阶段）并存，互不影响。
`counts` 报的是 `{entity_pool, fallback_pool}`，事件与片段数在 `aggregation.events` /
`aggregation.n_blocks`。

**排序是可解释的**：每个片段带 `why`，逐项列出得分来源。相关度**只用于排序**，
不是对史料可信度的评判；不同史书的记载**从不合并**，只在 `aggregation.sources` 里并排。

## 第四阶段验收路径（浏览器）

1. `python -m api.main` → http://127.0.0.1:8600/ → 顶部导航点「**提问**」。
2. **第一验收题**：输入 `齐桓公什么时候死的？`
   - 分析栏应显示 意图 `death`、实体 `齊桓公`；
   - 事件 ~15 个 / 片段 ~33 个，来源横跨 **春秋左傳 · 史記 · 國語**；
   - **第一位事件的正文里应出现「冬十月乙亥，齊桓公卒」**（左傳）——这是
     「答句排到第 30 个事件里等于没有」的判据，不能只看「召回了」。
3. 依次试：`管仲是怎么死的？` / `重耳流亡了多少年？` / `商鞅变法` /
   `秦穆公和百里奚是什么关系` / `城濮之战谁赢了`。
   - `重耳流亡了多少年？` 应同时触发 `flight` + `duration`，实体显示规范名 `晉文公`
     但 `matched` 是用户原词 `重耳`；
   - `秦穆公和百里奚是什么关系` 的**前 3 个事件里应有两人同段的片段**，且说明栏
     报出的同段段数与语料实际一致（语料写「秦繆公」，是已核实别名）。
4. **否定测试**：输入 `董卓` → 事件数 0、正文为空，说明里明写「不编造」。
   （三国人物不在先秦语料里，系统必须承认找不到，而不是编。）
5. **歧义测试**：输入 `桓公` → 实体栏就写「桓公」，**不会**被补成「齊桓公」。
   语料里「桓公」指 15 家，系统如实返回全部并降档，不替用户裁决是谁。
6. **繁简双轨**：任一事件里的片段，正文默认显示 `text_orig`（繁体原文，一字不改）；
   切到「简体」时 `text_simplified` 是**另存**的派生副本。展开「数据详情」可见
   `text_mode` / `simplified_ok` / `simplified_chars`。
7. **跨书不合并**：同一事件若多书都有记载，`aggregation.sources` 按书分开列出，
   是并排呈现，不是物理拼接 —— 拼接会造出原文里不存在的连续文字。

## 第四阶段已知问题

1. **提问模式不支持按书/版本过滤**（`level=question` 只收 `q` 与 `text`），
   需要时应补 `book`/`edition`，与二阶段对齐。
2. **无人物实体的问句排序偏弱**：`城濮之战谁赢了` 识别不出人物，只靠主题词兜底，
   相关度一律 5.0，事件间次序实际由 book_id/file_id 决定，不是真正的相关性排序。
   这类**事件名**问题需要事件名词表才能改善。
3. **光杆短称**（如 `桓公`）会如实召回 15 家共 33 个事件 —— 诚实但不好用；
   更好的做法是提示用户补国名，属交互设计，本阶段未做。
4. **短称误配残余风险**：`bare_hit` 只看紧邻前一个字，正文写「是為桓公」而前文讲的
   是别国时仍可能误配；目前靠降档（weak，2 分）压低影响，未消除。
5. **SBCK 行内括注仍会出现在片段正文里**（§19B 未解决）：17,347 条保持
   `pending_commentary`，未裁注者；因为 `text_orig` 就是原文，不能删。

---

## 数据来源与再分发（发布前必读）

`HistoryLibrary/kanripo/` 是 Kanripo 项目的原始 txt（五部书，118 个文件，共约
6.5MB）。仓库里**没有**随附 README/LICENSE/版权声明，文件头只有书目元数据，
**无法确认可否再分发** —— 因此按任务书 §23：

- `HistoryProject/.gitignore` 已忽略 `HistoryLibrary/kanripo/`，本仓库**不含**原始语料；
- 需要语料请自行从 Kanripo 获取，放回 `HistoryLibrary/kanripo/<书>/`（目录名见上表）；
- `HistoryAI/data/`（数据库/日志/缓存，实测 314MB）同为派生产物，一并忽略。

细节、以及「为什么不能凭『古籍是公版』就推断整理版也是公版」，见
[`docs/data_sources.md`](docs/data_sources.md)。

## 许可

本仓库自身的内容（`HistoryAI/` 的代码、前端、测试、文档，以及本 README 与配置文件）
以 **MIT** 许可发布，全文见仓库根的 [`LICENSE`](../LICENSE)。

**MIT 不覆盖 `HistoryLibrary/kanripo/` 下的原始典籍文本** —— 那部分未随本仓库分发
（已在 `.gitignore` 中排除），授权状况未能确认，所以不在此处作任何授权声明。
换句话说：MIT 许可的是这个项目的**代码**，不是它读取的**语料**。
