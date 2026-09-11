/* Result Block —— 把「命中句」组装成「可连续阅读的史料片段」（浏览器版）。
 * search/result_block.py 的忠实移植。
 *
 * ## 为什么需要
 * tls 系（尚書/左傳/史記）¶ 一句一行，一条 passage 常常就是一个 6 字句子
 * （`齊桓公卒。¶`）。命中是「句」，用户要读的是「一件事」。本模块只做展示层
 * 聚合：**不改索引、不改原文、不写任何东西**。
 *
 * ## 组装规则（机会主义：有什么证据用什么）
 * 一个 block = 命中记录 + 同一原始文件内沿 (row_no, seq) 向两侧扩展的相邻记录，
 * 遇到下列任一**停止条件**即停：
 *
 * 1. 文件边界 —— 绝不跨 file_id（硬边界，永不越过）。
 * 2. layer 变化 —— 正文与 commentary_candidate 不混（任务书 §八.4）。
 * 3. 结构键变化（按书自适应，全部取数据库真实列）：
 *    - `section`    左傳(僖公十七年傳) / 尚書(篇名) / 史記表(三代世表)
 *    - `subsection` 左傳条目号
 *    - `ab`         左傳 A=經 / B=傳
 *    - `# src:` 段落号  史記 纪/傳 的段号（srcParagraph 截前两级）
 *    **注意史記内部极不均匀**：f82(本紀) 有 1894 条 src、f95(傳) 2611 条，
 *    而 f94(世家) 仅 78 条、f83/f84(表) 为 0。没有证据时不猜测段落，
 *    改由硬上限兜底（任务书 §十：宁可短，不可臆造）。
 * 4. 硬上限 —— 两种情形都生效：max_passages / max_chars。
 *    对國語 / 戰國策 / 史記世家等无结构字段的书，这是唯一的收束手段。
 *
 * page/pb 换页**不**作为停止条件：一段史料本就可能跨页（任务书 §八.5），
 * 只在结果里如实带出 pb_first / pb_last。
 *
 * ## 合并去重
 * 同一文件内相邻的多个命中若落入同一个区间，只产出一个 block，match_count
 * 汇总（任务书 §十二）。区间重叠时取并集，不丢结果。
 *
 * ## 不改原文
 * `text` 由各记录 `text_orig` 直接相接，不改写、不补标点、不做任何润色
 * （任务书 §十 / §二十四）。含 <pb:…>、¶ 等原样保留。
 *
 * ## 与原模块的唯一差别：数据来源
 * Python 从 SQLite 现取行窗口；这里从内存语料取。**窗口语义照抄**——
 * 同样有 FALLBACK_MARGIN 余量、同样受 WINDOW_HARD_CAP 截断、同样复用
 * 已覆盖请求的缓存窗口。若图省事直接返回全文件，扩展就会读到 Python 读不到
 * 的行，片段长度和 more_before/more_after 都会跟着变。
 */
"use strict";
(function (NS) {
  // 三种展示长度。target_chars 是「尽量达到」，max_* 是「绝不超过」。
  const MODE_LIMITS = {
    short:    { target_chars: 120,  max_passages: 12,  max_chars: 260 },
    standard: { target_chars: 420,  max_passages: 40,  max_chars: 900 },
    long:     { target_chars: 1200, max_passages: 120, max_chars: 2600 },
  };
  const DEFAULT_MODE = "standard";

  // 单次搜索最多组装多少个 block（防热词把全库拖进来；超出则如实标注 truncated）。
  const MAX_BLOCKS_PER_QUERY = 600;

  // 行窗口：命中行两侧至少取 FALLBACK_MARGIN 条（无结构证据时的兜底观察范围），
  // 窗口总跨度不超过 WINDOW_HARD_CAP（防 src 边界远在千里时拖进半个文件）。
  const FALLBACK_MARGIN = 40;
  const WINDOW_HARD_CAP = 600;
  const WINDOW_PAD = 20;          // 二次取数时在块区间外额外留的行数

  // 段落号形态：'004.41.2' / '17.5.6' / '28.70.3' —— 点分数字，至少两级。
  // 必须用 ^ 锚定 section_ref 开头，否则会误吃 `# dating: 6220卿有札書…` 这类
  // 注解或引文里的数字（实测踩过）；只认开头一个，也不许到处抓。
  const SRC_CODE_RE = /^([A-Za-z]*)\s*(\d+(?:\.\d+)+)/;

  // 组装时要读的列（对应 Python 的 _ROW_COLS；这里直接用打包语料的列名）。
  const ROW_COLS = ["passage_id", "file_id", "row_no", "seq", "kind", "layer",
                    "status", "juan", "section", "subsection", "division", "ab",
                    "text_orig", "pb_block", "pb_page", "pb_side"];

  function cplen(s) { return [...s].length; }

  // Python 的 str.split()（不带参数）按 Python 的空白集合切，见上面 terms_simplified。
  const PY_WS_SPLIT_RE = new RegExp("[" + NS.PY_WS + "]+");

  // ----------------------------------------------------------------- 边界证据

  /** 从 `# src:` 的 section_ref 里取「段落号」前两级，作史記等书的段边界。
   *
   *  数据库里的 section_ref 形态不统一，实测有：
   *    '004.41.2, ed. Zhōnghuáshūjú …'  → 004.41   （史記本紀，段号在最前）
   *    'SHIJI 28.70.3 1393/94; …'       → 28.70    （书名前缀 + 空格 + 段号）
   *    'ZUO 17.5.6 (643 B.C.); …'       → 17.5     （左傳，前缀 + 空格）
   *    '5.28.3 (…) …'                   → 5.28
   *  取开头「≥2 级点分数字」的第一二级。**只基于第一阶段已入库的值**，
   *  不重新解析原文、不猜测章节归属。开头不是号的一律视为无证据——例如
   *  'ZUO Xi 17.5.6'（前缀里夹了非书名词）或 '# dating: 6220…' 这类注解。 */
  function srcParagraph(sourceRefJson) {
    if (!sourceRefJson) return null;
    let ref = "";
    try {
      ref = ((JSON.parse(sourceRefJson) || {}).section_ref) || "";
    } catch (e) {
      return null;
    }
    const m = SRC_CODE_RE.exec(ref.replace(/^\s+/, ""));
    if (!m) return null;
    // 至少两级才当段号：'5' 这种孤立数字说不清是卷次还是页码，宁可不切
    // （任务书 §十：宁可短，不可臆造）。
    return m[2].split(".").slice(0, 2).join(".");
  }

  /** 结构键：键不同 = 不同段；null = 该行无段落级结构证据。 */
  function boundaryKey(section, subsection, ab) {
    if (section) return ["sec", section, ab];
    if (subsection) return ["sub", subsection, ab];
    if (ab) return ["ab", ab];
    return null;
  }

  /** rows[i] 能否并入以 refI 为参照的扩展区间（判定统一的唯一出口）。
   *
   *  非 passage 行（`# src:` / `<pb:>` / 标题）在正文里透明穿过：既不进片段
   *  正文，也不打断扩展。但**参照行不能跟着它们走**——`# src:` 这一行本身属于
   *  **新**段号，若拿它当参照，下一个 passage 就在跟新段号比较，于是从 004.42
   *  往回读能一路读穿到文件开头（实测踩过）。参照行永远停在「最近一条真正并入
   *  的 passage」上。
   *
   *  `keyK != keyRef` 把「有键 ↔ 无键」也判成变化（严格口径）：一侧有 section
   *  小节标题、另一侧无 section，就是两段史料，拼起来会读串。代价是个别片段
   *  短一点——按任务书 §十，宁可短，不可臆造。块之间的界限另由**锚点位置**保证：
   *  展开时不允许读回锚点另一侧。 */
  function canTake(row, marks, i, refI) {
    if (row.kind !== "passage") return true;
    const [keyRef, segRef, layerRef] = marks[refI];
    const [keyK, segK, layerK] = marks[i];
    if (layerK !== layerRef) return false;         // layer 边界：正文/注释不混
    // 键必须一样：**「有键 ↔ 无键」也算变化**。一侧是篇/章标题行，另一侧不属于
    // 任何篇，硬并起来就把两段史料接成一句。实测这条取严格口径与宽松口径在真实
    // 语料上产出的片段数、长度完全相同（说明宽松口径多读到的只是拼接缝上的
    // 零头），那就取不会读串的那个（任务书 §十）。
    const same = keyK === keyRef ||
      (keyK !== null && keyRef !== null && keyK.length === keyRef.length &&
       keyK.every((v, j) => v === keyRef[j]));
    if (!same) return false;
    // `# src:` 段号只在**本行没有结构字段**时才作边界证据（结构字段更可靠，
    // 且左傳/尚書的 src 行比 section 更细，用它会切碎阅读单元）。
    if (keyRef === null && segRef !== null && segK !== null && segK !== segRef) {
      return false;
    }
    return true;
  }

  /** 行号落在哪个段落号区间；不在任何区间内（如首条 `# src:` 之前的引子）返回 -1。
   *
   *  不做「就近归属」：段落号只往后管辖，把区间外的行算给最近的一段会让两段
   *  史料的正文被拼到一起。无证据就是无证据。 */
  function segOf(rowNo, segments) {
    for (let i = 0; i < segments.length; i++) {
      if (segments[i][0] <= rowNo && rowNo < segments[i][1]) return i;
    }
    return -1;
  }

  /** 预计算每行的边界证据 (结构键, 段序号, layer)。 */
  function marksFor(rows, segments) {
    return rows.map((r) => {
      const s = segments.length ? segOf(r.row_no, segments) : -1;
      return [boundaryKey(r.section, r.subsection, r.ab),
              s >= 0 ? s : null, r.layer];
    });
  }

  // --------------------------------------------------------------- 有限行加载

  /** 单次请求内、按文件惰性加载**有限行窗口**（Python 的 _FileCache）。
   *
   *  任务书 §二十一禁止「一次加载整个文件」——这里照抄窗口语义：只取命中附近
   *  的行，窗口按需生长，最多长到 WINDOW_HARD_CAP。缓存随请求结束丢弃。 */
  class FileCache {
    constructor(corpus) {
      this.corpus = corpus;
      this._cols = ROW_COLS.map((c) => corpus.col[c]);
      this._segCache = new Map();
      this._winCache = new Map();       // file_id -> {rows, lo, hi}
    }

    /** 按 passage_id 物化一条记录；不存在返回 null（对应 Python 的 fetchone()）。 */
    recOfPassage(pid) {
      const i = this.corpus.indexOfPassage(pid);
      return i < 0 ? null : this.rec(i);
    }

    /** 把一行打包数据物化成对象，字段名与 Python 的 sqlite Row 键一致。 */
    rec(i) {
      const r = this.corpus.rows[i];
      const o = {};
      for (let k = 0; k < ROW_COLS.length; k++) {
        const name = ROW_COLS[k];
        const v = r[this._cols[k]];
        const d = this.corpus.dicts[name];
        o[name] = d ? (v >= 0 ? d[v] : null) : v;
      }
      return o;
    }

    // ---- 段落号索引（只看 `# src:` 行两列，代价与文件大小无关）----
    /** 该文件段落号管辖区间 [[lo_row, hi_row), …]；无 `# src:` 则返回 []。
     *
     *  区间在**段号变化的那个 src 行**处收口（不是在下一条 src 行）：那个 src
     *  行本身已经属于新段号，旧段不能把它圈进来。这样同一个段号在文件里出现
     *  多次（换页处重复标号）也会被切成多段，不会跨过中间别的段号把它们并起来。
     *
     *  建库时算好的是窄派生表 `src_paragraphs`；这里没有那张表，就地对 `# src:`
     *  行重算 —— 用的是**同一个** srcParagraph（建库侧也是调它），两边不会出现
     *  两种口径。 */
    segments(fileId) {
      if (this._segCache.has(fileId)) return this._segCache.get(fileId);
      const spans = [];
      const sp = this.corpus.spanOfFile(fileId);
      if (sp) {
        const cKind = this.corpus.col.kind, cRow = this.corpus.col.row_no;
        const cRef = this.corpus.col.source_ref_json;
        const kinds = this.corpus.dicts.kind;
        const rows = this.corpus.rows;
        for (let i = sp[0]; i < sp[1]; i++) {
          const r = rows[i];
          if (kinds[r[cKind]] !== "comment") continue;   // 段号只挂在 `# src:` 行上
          const refJson = r[cRef];
          if (!refJson) continue;
          const code = srcParagraph(refJson);
          if (code === null) continue;
          if (!spans.length || spans[spans.length - 1][0] !== code) {
            spans.push([code, r[cRow]]);
          }
        }
      }
      const out = spans.map((s, i) => [
        s[1], i + 1 < spans.length ? spans[i + 1][1] : 1e9]);
      this._segCache.set(fileId, out);
      return out;
    }

    // ---- 行窗口：按需生长 ----
    /** 取覆盖 [rowLo, rowHi] 的窗口，返回 rows（按 row_no, seq）。
     *
     *  带 WINDOW_PAD 余量；单次跨度不超过 WINDOW_HARD_CAP。同文件内若已缓存
     *  的窗口能满足请求（有膨胀余量），直接复用。 */
    window(fileId, rowLo, rowHi) {
      const lo = Math.max(1, rowLo - WINDOW_PAD);
      const hi = Math.min(rowHi + WINDOW_PAD, lo + WINDOW_HARD_CAP - 1);
      const cached = this._winCache.get(fileId);
      if (cached && cached.lo <= lo && cached.hi >= hi) return cached.rows;

      const rows = [];
      const sp = this.corpus.spanOfFile(fileId);
      if (sp) {
        const rowsRaw = this.corpus.rows, cRow = this.corpus.col.row_no;
        // 文件内按 (row_no, seq) 有序，所以 row_no 落在 [lo, hi] 的行必是一段连续区间
        let i = this.corpus.lowerBoundInFile(fileId, lo);
        for (; i >= 0 && i < sp[1]; i++) {
          if (rowsRaw[i][cRow] > hi) break;
          rows.push(this.rec(i));
        }
      }
      this._winCache.set(fileId, { rows, lo, hi });
      return rows;
    }
  }

  // ----------------------------------------------------------------- 区间扩展

  /** 从 rows[i] 向两侧扩展，返回 [lo, hi, 尾部被截断, 头部被截断]。
   *
   *  marks[j] = (结构键, 段序号或 null, layer)。停止：结构键变 / 段号变 /
   *  layer 变 / 越过硬上限。page 换页不停止（任务书 §八.5）。
   *
   *  后两个布尔值区分「读到本段尽头」与「被字数/条数上限截断」——只有真被
   *  截断才提示可以继续展开（任务书 §十：读不到就说读到哪，不假装完整）。 */
  function expand(rows, i, limits, marks) {
    const maxP = limits.max_passages, maxC = limits.max_chars;
    const target = limits.target_chars;
    const n = rows.length;
    const tlen = (j) => (rows[j].text_orig || "").length;

    let lo = i, hi = i;
    let size = tlen(i), count = 1;
    let refLo = i, refHi = i;           // 参照行：最近一条真正并入的 passage
    let fwd = true, bwd = true;
    let cutFwd = false, cutBwd = false; // 该侧是被上限截断（而非读到尽头）
    while ((fwd || bwd) && count < maxP && size < maxC) {
      if (fwd) {
        if (hi >= n - 1) {
          fwd = false;
        } else {
          const j = hi + 1;
          if (!canTake(rows[j], marks, j, refHi)) {
            fwd = false;
          } else if (count + 1 > maxP || size + tlen(j) > maxC) {
            cutFwd = true;              // 还可能往下读，只是这一屏放不下
            fwd = false;
          } else {
            hi = j; count += 1; size += tlen(j);
            if (rows[j].kind === "passage") refHi = j;
          }
        }
      }
      if (bwd && size < target && count < maxP) {
        if (lo <= 0) {
          bwd = false;
        } else {
          const j = lo - 1;
          if (!canTake(rows[j], marks, j, refLo)) {
            bwd = false;
          } else if (count + 1 > maxP || size + tlen(j) > maxC) {
            cutBwd = true;
            bwd = false;
          } else {
            lo = j; count += 1; size += tlen(j);
            if (rows[j].kind === "passage") refLo = j;
          }
        }
      }
      if (size >= target) break;
    }
    return [lo, hi, cutFwd, cutBwd];
  }

  /** 块区间 [lo,hi] 之外、仍属**同一段史料**的行能延伸多远（任务书 §二十）。
   *
   *  用 expand 的同一套 canTake 规则从区间两端继续走。返回可达的 [lo', hi']；
   *  与 [lo,hi] 相同即表示两侧都读到本段尽头了。这一步只判断边界、不取正文，
   *  也不做完整走查：累计额外走过 maxExtraChars 就收手——结论一样（「外面还有
   *  得读」），但不会为一个 2 万字的文件白走到底。 */
  function reachEdges(rows, lo, hi, marks, maxExtraChars = 4000) {
    const n = rows.length;
    let a = lo, b = hi;
    let refA = lo, refB = lo;           // 区间端行的结构键就是参照口径
    let extra = 0;
    while (b + 1 < n && extra < maxExtraChars &&
           canTake(rows[b + 1], marks, b + 1, refB)) {
      b += 1;
      extra += (rows[b].text_orig || "").length;
      if (rows[b].kind === "passage") refB = b;
    }
    while (a - 1 >= 0 && extra < maxExtraChars &&
           canTake(rows[a - 1], marks, a - 1, refA)) {
      a -= 1;
      extra += (rows[a].text_orig || "").length;
      if (rows[a].kind === "passage") refA = a;
    }
    return [a, b];
  }

  // ----------------------------------------------------------------- 组装入口

  /** hits = [[passage_id, file_id, row_no, seq, score], …] → 全部 block（未排序）。
   *
   *  同一文件内反复取数走缓存；区间重叠的块合并而不是重复展示。 */
  function buildResultBlocks(corpus, hits, mode = DEFAULT_MODE) {
    const limits = MODE_LIMITS[mode];
    const cache = new FileCache(corpus);

    // 1) 逐命中扩展（按文件分组，保证窗口查询命中缓存）
    const raw = [];
    const byFile = new Map();
    for (const h of hits) {
      if (!byFile.has(h[1])) byFile.set(h[1], []);
      byFile.get(h[1]).push(h);
    }

    for (const [fid, hs] of byFile) {
      const segments = cache.segments(fid);
      // 窗口要足够宽，直到结构边界或硬上限先到（否则扩展会被窗口截断，
      // 片段看起来「短」其实是取数不够）。普通记录很短，按条数给足余量。
      const margin = Math.min(Math.floor(WINDOW_HARD_CAP / 2),
                              FALLBACK_MARGIN + limits.max_passages * 2);
      const loRow = Math.min(...hs.map((h) => h[2]));
      const hiRow = Math.max(...hs.map((h) => h[2]));
      const rows = cache.window(fid, loRow - margin, hiRow + margin);
      if (!rows.length) continue;
      const marks = marksFor(rows, segments);
      const pos = new Map(rows.map((r, i) => [r.passage_id, i]));
      const sorted = hs.slice().sort((x, y) =>
        (x[2] - y[2]) || (x[3] - y[3]));
      for (const h of sorted) {
        const pid = h[0];
        const i = pos.get(pid);
        if (i === undefined) continue;  // 命中行不在窗口内（极端越界），本轮不组装
        const [a, b, cutF, cutB] = expand(rows, i, limits, marks);
        raw.push({ file_id: fid, lo: a, hi: b, rows, marks,
                   match_count: 1, score: h[4], hit_passage_id: pid,
                   more_before: cutB, more_after: cutF });
      }
    }

    // 2) 区间合并（同文件、重叠或相邻 → 并集）
    const merged = [];
    for (const blk of raw) {
      let hit = false;
      for (const m of merged) {
        if (m.file_id !== blk.file_id) continue;
        if (blk.lo <= m.hi + 1 && blk.hi >= m.lo - 1) {
          m.lo = Math.min(m.lo, blk.lo);
          m.hi = Math.max(m.hi, blk.hi);
          m.match_count += blk.match_count;
          if (blk.score < m.score) {
            m.score = blk.score;
            m.hit_passage_id = blk.hit_passage_id;
          }
          m.rows = blk.rows.length > m.rows.length ? blk.rows : m.rows;
          m.marks = blk.marks.length > m.marks.length ? blk.marks : m.marks;
          hit = true;
          break;
        }
      }
      if (!hit) merged.push(Object.assign({}, blk));
    }

    // 3) 成文。合并会把区间撑大，单次扩展记的截断标记不再作数——按最终区间
    //    重算「两侧还能不能继续读」，否则合并块永远显示不出可展开（实测）。
    const shaped = [];
    for (const m of merged) {
      const [rlo, rhi] = reachEdges(m.rows, m.lo, m.hi, m.marks);
      m.more_before = rlo < m.lo;
      m.more_after = rhi > m.hi;
      const seg = m.rows.slice(m.lo, m.hi + 1);
      const pids = seg.filter((r) => r.kind === "passage")
        .map((r) => r.passage_id);
      if (!pids.length) continue;
      shaped.push(shapeBlock(seg, pids, m));
    }
    return { blocks: shaped, limits };
  }

  /** 组装对外结构。text 由 text_orig 直接相接，绝不改写、不补标点。
   *
   *  只渲染 kind='passage' 的记录（真实史料正文）；`# src:`/`<pb:>`/标题等
   *  解析元数据行不进入片段正文——它们只在数据检查台出现（任务书 §十七）。
   *  页码信息另由 pb_first/pb_last 如实给出。 */
  function shapeBlock(seg, pids, m) {
    const body = seg.filter((r) => r.kind === "passage");
    const text = body.map((r) => r.text_orig || "").join("");
    const pbs = body.filter((r) => r.pb_block || r.pb_page);
    const first = body.length ? body[0] : null;

    const side = (r) => ((r.pb_page || "") + (r.pb_side || "")) || null;

    return {
      block_id: first ? `${m.file_id}:${body[0].row_no}:${body[0].seq}` : null,
      hit_passage_id: m.hit_passage_id,
      file_id: m.file_id,
      row_first: first ? body[0].row_no : null,
      row_last: first ? body[body.length - 1].row_no : null,
      passage_ids: pids,
      match_count: m.match_count,
      score: m.score,
      text: text,
      juan: first ? first.juan : null,
      section: first ? first.section : null,
      subsection: first ? first.subsection : null,
      division: first ? first.division : null,
      ab: first ? first.ab : null,
      layer: first ? first.layer : null,
      pb_first: pbs.length ? side(pbs[0]) : null,
      pb_last: pbs.length ? side(pbs[pbs.length - 1]) : null,
      n_passages: pids.length,
      n_chars: cplen(text),
      // 该侧是否还能继续读（被展示长度上限截断，而非读到本段尽头）。
      // 前端据此决定要不要给「展开更多上下文」按钮——读到尽头就不给，
      // 免得点开发现什么都没有（任务书 §十：不制造假象）。
      more_before: m.more_before,
      more_after: m.more_after,
      // 展开时的锚点：向外走要从片段首/末记录续，不能从命中点续（会重叠）。
      first_passage_id: pids[0],
      last_passage_id: pids[pids.length - 1],
    };
  }

  // ----------------------------------------------------------------- 对外入口

  /** 取全部命中的 [passage_id, file_id, row_no, seq, score]。
   *
   *  路径选择与 engine.runSearch 保持一致（trigram / bigram / LIKE），但**不分页**
   *  —— Result Block 必须先看全命中才能正确合并与计数。LIKE 路径无 bm25，score 记 null。 */
  function fetchHits(corpus, qTrad, bid, edition) {
    const E = NS.engine;
    const [longTerms, shortTerms] = E.planQuery(qTrad);
    const st = corpus.bm25 || {};
    const useFts = !!st.trigram && longTerms.length > 0;
    const pureTwo = shortTerms.length > 0 && shortTerms.every((t) => cplen(t) === 2);
    const useBg = !useFts && pureTwo && !!st.bigram;
    const filter = { bookId: bid, family: edition };

    const rowsOf = (idxs, scores) => idxs.map((i, k) => {
      const r = corpus.rows[i];
      const c = corpus.col;
      return [r[c.passage_id], corpus.cell(i, "file_id"),
              r[c.row_no], r[c.seq], scores === null ? null : scores[k]];
    });

    let hits, scoreNeg = null;
    if (useFts) {
      // 长词走 FTS，同查询的 <3 字词作 AND 附加约束参与命中（不计分）
      hits = corpus.likeScan(longTerms.concat(shortTerms), filter).hits;
      const folded = longTerms.map(NS.asciiFold);
      const df = folded.map((t) => E.docFreq(corpus, t));
      // 取负：SQLite 的 bm25() 返回负分（越小越相关），engine.bm25 算的是**正**
      // 分值，两侧的调用点都要翻一次号（engine.js 的 runSearch 也是 `-s`）。
      // 这里的分数直接进 block 的 score 字段，也是排序的次级键 —— 不翻号，
      // 强相关片段会被排到最后（实测：'齊桓公' 首位变成 戰國策 的一条）。
      scoreNeg = hits.map((i) => {
        const text = corpus.mtext[i];
        const dl = E.dlTrigram(text);
        let s = 0;
        for (let k = 0; k < folded.length; k++) {
          s += E.bm25(st.trigram, df[k], dl, E.countOcc(text, folded[k]));
        }
        return -s;
      });
    } else if (useBg) {
      const toks = shortTerms.map(E.phraseToken);
      const kept = toks.filter((t) => t !== null);
      if (!kept.length) {
        hits = [];
      } else if (kept.every((t) => cplen(t) === 2)) {
        hits = corpus.likeScan(kept, filter).hits;
      } else {
        hits = E.scanBgTokens(corpus, kept, filter);
      }
      scoreNeg = hits.map((i) => {
        const text = corpus.mtext[i];
        const own = E.bgTokens(text);
        const dl = own.length;
        let s = 0;
        for (let k = 0; k < kept.length; k++) {
          let f = 0;
          for (let j = 0; j < own.length; j++) if (own[j] === kept[k]) f++;
          s += E.bm25(st.bigram, E.bigramDf(corpus, kept[k]), dl, f);
        }
        return -s;   // 同上：SQLite 的负分约定
      });
    } else {
      hits = corpus.likeScan(longTerms.concat(shortTerms), filter).hits;
    }

    // 命中顺序按 passage_id 升序 —— 对齐 Python `_fetch_hits` 的**隐式**顺序：
    // 三条路径的 SQL 都没有 ORDER BY，实测靠 SQLite 全表扫 passages 给出 rowid
    // 序（= passage_id 升序，'齊'/'之'/'大夫'/'諸侯'/'諸侯之' 等逐一验过）。
    //
    // 为什么必须显式排：JS 的 likeScan 走的是**打包序**（按 book_id/file_no/
    // row_no 分组，窗口取数要求同文件的行连续），与 passage_id 序不同 ——
    // 而这个顺序是**可观测**的，`hit_rows[:600]`（MAX_BLOCKS_PER_QUERY）截的
    // 就是它。不排的话，命中超过 600 的查询两边会组装出完全不同的片段集
    // （实测 '齊' 6079 命中：match_count_sum 291 vs 162）。
    const pid = corpus.col.passage_id;
    const order = hits.map((_, k) => k)
      .sort((a, b) => corpus.rows[hits[a]][pid] - corpus.rows[hits[b]][pid]);
    return rowsOf(order.map((k) => hits[k]), scoreNeg === null ? null : order.map((k) => scoreNeg[k]));
  }

  /** 实际检索路径（fts/bigram/like），与 engine 的文案一致。 */
  function execMode(corpus, qTrad) {
    const E = NS.engine;
    const [longTerms, shortTerms] = E.planQuery(qTrad);
    const st = corpus.bm25 || {};
    if (st.trigram && longTerms.length) return "fts";
    if (shortTerms.length && shortTerms.every((t) => cplen(t) === 2) && st.bigram) {
      return "bigram";
    }
    return "like";
  }

  function fileMeta(corpus, fileIds) {
    const out = {};
    for (const fid of fileIds) {
      const f = corpus.fileById.get(fid);
      if (!f) continue;
      const b = corpus.bookById.get(f.book_id);
      out[fid] = {
        book_title: b ? b.title : null,
        book_id: f.book_id,
        edition: b ? b.edition : null,
        family: b ? b.family : null,
        file_name: f.file_name,
        file_no: f.file_no,
        origin_path: f.origin_path,
      };
    }
    return out;
  }

  /** 检索 → 组装 Result Block → 排序分页。参数非法抛 Error（API 转 400）。
   *
   *  `total` 是**合并后的片段数**（精确），`hit_total` 是原始命中 passage 数；
   *  两者不等正是第三阶段要解决的问题的可观测证据（任务书 §十二）。
   *
   *  `text_mode` 是繁简双轨（orig/simplified/both）：只**增加** `text_simplified`
   *  等字段，`text` 仍是原样的 text_orig，一字不改。 */
  function searchResultBlocks(corpus, q, opts) {
    opts = opts || {};
    const E = NS.engine;
    let page = opts.page === undefined ? 1 : opts.page;
    let pageSize = opts.pageSize === undefined ? 20 : opts.pageSize;
    const mode = opts.mode === undefined ? DEFAULT_MODE : opts.mode;
    const textMode = opts.textMode === undefined ? "orig" : opts.textMode;

    if (page < 1) throw new Error("页码从 1 开始");
    pageSize = Math.min(Math.max(pageSize, 1), E.PAGE_SIZE_MAX);
    if (!Object.prototype.hasOwnProperty.call(MODE_LIMITS, mode)) {
      throw new Error(`未知的显示长度：${mode}（可用：${Object.keys(MODE_LIMITS).join("、")}）`);
    }
    const qTrad = NS.zh.toTraditional(NS.pyStrip(q || ""));
    if (!qTrad) throw new Error("请提供搜索关键词");
    const bid = E.resolveBook(corpus, opts.book);
    const edition = E.resolveEdition(opts.edition);

    const hitRows = fetchHits(corpus, qTrad, bid, edition);
    const hitTotal = hitRows.length;
    // 检索词的简体形态：前端在「只看简体/繁简对照」里要用它高亮（繁体词高亮不到
    // 简体正文上）。用的是和正文同一个转换函数，两边不会出现两套简体。
    // 切词用 Python 的空白集合（PY_WS），不能用 /\s+/：两边差 U+001C-1F/U+0085
    // 与 U+FEFF，差一个字符就会多切/少切出一个词项，terms_simplified 跟着错。
    const simpleTerms = qTrad.split(PY_WS_SPLIT_RE).filter((t) => t)
      .map((t) => NS.dualText.simplify(t).text);
    const base = {
      q: NS.pyStrip(q || ""), q_traditional: qTrad, mode: mode,
      text_mode: textMode, terms_simplified: simpleTerms,
      exec_mode: execMode(corpus, qTrad),
      book: bid || "全部", edition: edition || "全部",
      hit_total: hitTotal, page: page, page_size: pageSize,
    };
    if (!hitRows.length) {
      Object.assign(base, {
        total: 0, match_count_sum: 0, truncated: false,
        limits: MODE_LIMITS[mode], results: [],
      });
      return base;
    }

    const overflow = hitTotal > MAX_BLOCKS_PER_QUERY;
    const hits = hitRows.slice(0, MAX_BLOCKS_PER_QUERY)
      .map((r) => [r[0], r[1], r[2], r[3], r[4] === null ? 0.0 : r[4]]);

    const out = buildResultBlocks(corpus, hits, mode);
    const meta = fileMeta(corpus, new Set(out.blocks.map((b) => b.file_id)));
    for (const b of out.blocks) Object.assign(b, meta[b.file_id] || {});

    // 排序：命中多的在前（任务书 §十四），同数按相关度，再按书/文件/行序稳定
    const blocks = out.blocks.slice().sort((x, y) =>
      (y.match_count - x.match_count) ||
      ((x.score === null ? 0.0 : x.score) - (y.score === null ? 0.0 : y.score)) ||
      cmpStr(x.book_id || "", y.book_id || "") ||
      ((x.file_no || 0) - (y.file_no || 0)) ||
      (x.row_first - y.row_first));

    const lo = (page - 1) * pageSize;
    const pageBlocks = blocks.slice(lo, lo + pageSize)
      .map((b) => NS.dualText.attach(publicBlock(b), textMode));
    Object.assign(base, {
      total: blocks.length,                   // 片段数（合并后，精确）
      match_count_sum: blocks.reduce((s, b) => s + b.match_count, 0),
      truncated: overflow,
      limits: Object.assign({}, MODE_LIMITS[mode]),
      results: pageBlocks,
    });
    return base;
  }

  function cmpStr(a, b) { return a < b ? -1 : a > b ? 1 : 0; }

  // 只给前端用的字段（不含内部结构：score 是 bm25 相关度、rows/marks 是组装
  // 过程的中间态）。
  const INTERNAL_KEYS = ["score", "rows", "marks"];

  function publicBlock(b) {
    const out = {};
    for (const k of Object.keys(b)) {
      if (INTERNAL_KEYS.indexOf(k) < 0) out[k] = b[k];
    }
    return out;
  }

  // ------------------------------------------------------- 按需展开更多上下文

  /** 从片段**边界**继续向前/向后读更多**真实**邻居（任务书 §二十）。
   *
   *  以「当前片段的首/末记录」为界向外取数——不是从命中点取，否则取到的行
   *  会与已有片段重叠。行进中遇到与 block 相同的停止条件（layer 变 / 段落号变）
   *  即止，并如实告知是否读到了头（reaches_* 为 true 表示这一段到此为止，
   *  不是因为字数上限被截断）。 */
  function expandBlock(corpus, passageId, opts) {
    opts = opts || {};
    let count = opts.count === undefined ? 20 : opts.count;
    const direction = opts.direction === undefined ? "both" : opts.direction;
    const beforePid = opts.beforePassageId === undefined ? null : opts.beforePassageId;
    const afterPid = opts.afterPassageId === undefined ? null : opts.afterPassageId;

    count = Math.min(Math.max(Math.trunc(count), 1), 100);
    if (["before", "after", "both"].indexOf(direction) < 0) {
      throw new Error("direction 只能是 before / after / both");
    }

    const cache = new FileCache(corpus);
    const hit = cache.recOfPassage(passageId);
    if (!hit) throw new Error("KEY:" + passageId);
    if (hit.kind !== "passage") {
      // 非正文记录（`# src:` / `<pb:>` 等）本就不在史料片段正文里，无从展开
      throw new Error("该记录不是史料正文，无法展开上下文");
    }
    const fid = hit.file_id;

    const anchor = (pid) => {
      if (pid === null || pid === undefined) return null;
      const r = cache.recOfPassage(pid);
      if (!r || r.file_id !== fid) return null;
      return r;
    };

    const segs = cache.segments(fid);
    const baseSeg = segOf(hit.row_no, segs);

    const markOf = (row) => [
      boundaryKey(row.section, row.subsection, row.ab),
      segs.length ? segOf(row.row_no, segs) : null,
      row.layer];

    /** 向一个方向走，返回 [新增行, 是否在本段内走到尽头]。
     *
     *  停止条件复用 canTake —— 与组装片段时**同一套判定**，不另写一份：
     *  两处规则一旦分家，就会出现「片段到 004.42 就停了，展开却读过去」这种
     *  前后不一致（实测踩过）。参照行同样是「最近一条真正并入的 passage」。
     *
     *  参照证据取**显式传来的那一侧端点**（前端传的片段首/末记录），且在整段
     *  行走中**不再变化**。若改成跟着刚读到的候选行走，参照会漂到下一条记录
     *  的键上，规则就失去意义（实测：从末行往回读会一路吞掉上一篇）。
     *
     *  另有一条硬界：**不许读到锚点的另一侧去**，即候选行必须严格在锚点之外。
     *  未传锚点时以记录自身为界，等于没有外层可读。 */
    const fetch = (a, explicit, order, limit) => {
      const cmpOp = order === "DESC" ? "<" : ">";
      // Python 侧是 SQL 的 (row_no <> a) OR (row_no = a AND seq <> a.seq)，
      // 这里在文件的行区间上顺序扫描，取严格在锚点之外的前 limit+1 条正文行。
      const sp = corpus.spanOfFile(fid);
      const cand = [];
      if (sp) {
        const cRow = corpus.col.row_no, cKind = corpus.col.kind, cSeq = corpus.col.seq;
        const kinds = corpus.dicts.kind, rowsRaw = corpus.rows;
        const cmpSeq = order === "DESC" ? (x, y) => x < y : (x, y) => x > y;
        const cmpRow = order === "DESC" ? (x, y) => x < y : (x, y) => x > y;
        const walked = [];
        for (let i = sp[0]; i < sp[1]; i++) {
          const r = rowsRaw[i];
          if (kinds[r[cKind]] !== "passage") continue;
          if (cmpRow(r[cRow], a.row_no) ||
              (r[cRow] === a.row_no && cmpSeq(r[cSeq], a.seq))) {
            walked.push(i);
          }
        }
        // SQL 的 ORDER BY row_no/seq 就等价于按 (row_no, seq) 升序/降序取
        walked.sort((x, y) => {
          const dx = rowsRaw[x][cRow] - rowsRaw[y][cRow];
          if (dx) return order === "DESC" ? -dx : dx;
          const ds = rowsRaw[x][cSeq] - rowsRaw[y][cSeq];
          return order === "DESC" ? -ds : ds;
        });
        for (const i of walked.slice(0, limit + 1)) cand.push(cache.rec(i));
      }

      const out = [];
      let ended = true;                 // 默认到头；下面只要能多取一条就翻案
      const refMark = explicit !== null && explicit !== undefined
        ? markOf(explicit) : markOf(a);
      const edge = explicit !== null && explicit !== undefined ? explicit : a;
      for (const r of cand) {
        if (out.length >= limit) {
          ended = false;                // 本次是条数收的，外面还有
          break;
        }
        if (order === "DESC") {
          if (r.row_no > edge.row_no ||
              (r.row_no === edge.row_no && r.seq >= edge.seq)) {
            break;                      // 锚点另一侧，不读
          }
        } else if (r.row_no < edge.row_no ||
                   (r.row_no === edge.row_no && r.seq <= edge.seq)) {
          break;
        }
        const mk = markOf(r);
        if (!canTake(r, [refMark, mk], 1, 0)) {
          break;                        // 走出这段史料了：不是被截断，是到头
        }
        out.push({ passage_id: r.passage_id, row_no: r.row_no,
                   seq: r.seq, text_orig: r.text_orig });
      }
      if (order === "DESC") out.reverse();
      return [out, ended];
    };

    let added = [];
    let reachHead = null, reachTail = null;
    let nextBefore = null, nextAfter = null;
    const aBefore = anchor(beforePid), aAfter = anchor(afterPid);
    if (direction === "before" || direction === "both") {
      const [got, rh] = fetch(aBefore || hit, aBefore, "DESC", count);
      reachHead = rh;
      added = got.concat(added);
      if (got.length) nextBefore = got[0].passage_id;
    }
    if (direction === "after" || direction === "both") {
      const [got, rt] = fetch(aAfter || hit, aAfter, "ASC", count);
      reachTail = rt;
      added = added.concat(got);
      if (got.length) nextAfter = got[got.length - 1].passage_id;
    }

    return {
      passage_id: passageId, file_id: fid, row_no: hit.row_no,
      direction: direction, count: count, layer: hit.layer,
      segment: baseSeg >= 0 ? baseSeg : null,
      reaches_head: reachHead, reaches_tail: reachTail,
      next_before_passage_id: nextBefore,
      next_after_passage_id: nextAfter,
      added: added.length, rows: added,
    };
  }

  NS.resultBlock = {
    MODE_LIMITS, DEFAULT_MODE, MAX_BLOCKS_PER_QUERY,
    FALLBACK_MARGIN, WINDOW_HARD_CAP, WINDOW_PAD, ROW_COLS,
    srcParagraph, boundaryKey, canTake, segOf, marksFor,
    FileCache, expand, reachEdges, buildResultBlocks, shapeBlock,
    fetchHits, execMode, fileMeta, searchResultBlocks, expandBlock,
    publicBlock,
  };
})(window.HistoryAIEngine = window.HistoryAIEngine || {});
