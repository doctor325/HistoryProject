/* 繁简双轨显示（浏览器版）—— search/dual_text.py 的逐行转写。
 *
 * 三条硬约束与 Python 侧完全相同（原文见 dual_text.py 文件头）：
 *   1. text_orig 永不被覆盖，简体放在另一个字段里；
 *   2. 确定性，不调 LLM；
 *   3. **长度一变就整段回退原文** —— 宁可显示繁体，也不显示一份被悄悄改过的史料。
 *
 * 长度按**码位**数：Python 的 len() 数码位，JS 的 .length 数 UTF-16 单元。
 * CJK 扩展 B 汉字在 JS 里占 2 个单元、Python 里算 1 个码位，用 .length 判长度
 * 会得出与 Python 相反的结论。故一律 [...s].length。
 */
"use strict";
(function (NS) {
  const MODES = ["orig", "simplified", "both"];
  const DEFAULT_MODE = "orig";

  function simplify(text) {
    const src = text || "";
    if (!src) return { text: src, ok: true, changed: 0 };
    const out = NS.zh.toSimplified(src);
    if ([...out].length !== [...src].length) {
      // 长度变了 = 逐字对齐不成立，无法保证「只换了字形」→ 整段回退。
      return { text: src, ok: false, changed: 0 };
    }
    // changed 是逐字比对出来的改动字数（Python 用 zip，同样按码位）。
    const a = [...src], b = [...out];
    let changed = 0;
    for (let i = 0; i < a.length; i++) if (a[i] !== b[i]) changed++;
    return { text: out, ok: true, changed };
  }

  function attach(block, mode, srcKey) {
    mode = mode || DEFAULT_MODE;
    srcKey = srcKey || "text";
    if (MODES.indexOf(mode) < 0) {
      throw new Error("未知的繁简显示方式：" + mode + "（可用：" + MODES.join("、") + "）");
    }
    const res = simplify(block[srcKey] || "");
    const out = Object.assign({}, block);      // 就地改副本，不动 srcKey 指向的原文
    out.text_mode = mode;
    out.text_simplified = res.text;
    out.simplified_ok = res.ok;
    out.simplified_chars = res.changed;
    return out;
  }

  NS.dualText = { MODES, DEFAULT_MODE, simplify, attach };
})(window.HistoryAIEngine = window.HistoryAIEngine || {});
