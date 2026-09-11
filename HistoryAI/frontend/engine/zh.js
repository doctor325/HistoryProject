/* 简体 ↔ 繁体（浏览器版）—— search/zh.py 的并行实现。
 *
 * Python 那边调 Windows 的 kernel32.LCMapStringEx 做整串转换，浏览器没有这个 API，
 * 因此改用预生成的字符表（zh_table.js）。这不是「退而求其次」：字符表对 dual_text
 * 真正会采纳的范围（长度不变）与整串转换**完全等价**，脚本 gen_zh_table.py 每次
 * 生成表时都重跑穷举断言（语料全部单字 / 二字组 / 三字组，见该文件头注释）。
 *
 * 为什么要模拟「只处理前 n 个 UTF-16 单元」这件怪事
 * ------------------------------------------------
 * search/zh.py 里是这么调的：
 *
 *     n = len(text)                                  # ← Python 的 len()：**码位**数
 *     r = LCMapStringEx(locale, flag, text, n, buf, 2*n+16, ...)
 *     return buf.value[:r]
 *
 * 而系统 API 的 cchSrc 参数数的是 **UTF-16 单元**。星形汉字（CJK 扩展 B 等）在
 * Python 里算 1 个码位、却是 2 个单元，于是「前 n 个单元」并不覆盖整个字符串，
 * 尾巴上会少掉若干个单元。这不是缺陷，是 Python 侧**既有**行为，JS 必须照样复现，
 * 否则 dual_text 的长度判据会得出相反结论：
 *
 *   - 星形字在中间：代理对完整落入前 n 个单元 → 系统原样放行（2 单元=1 码位），
 *     结果码位数比原文少 1 → 长度变了 → dual_text **整段回退原文**；
 *   - 星形字在末尾：代理对被 n 截断，只剩一个孤立高位代理 → 系统放行 1 单元
 *     （= 1 个码位）→ 长度不变 → dual_text **采纳**这个结果（那个字就成了残码位）。
 *
 * 实测：全语料 203,308 条正文里 1,176 条含星形字，其中 1,172 条回退、4 条不回退，
 * 分界正是「星形字是否落在末尾」。本文件按上面的机制实现，check_engine.py 对
 * 全部 203,308 条逐条对拍（比 sha256 摘要）。
 *
 * 另一件容易写错的事：查不到就原样返回该字（= 该字繁简同形）。表里**故意**保留了
 * 系统对扩展 B 汉字返回的残缺代理码位，照抄不修补 —— Python 侧拿到的是同样的值。
 */
"use strict";
(function (NS) {
  if (!NS.zhTable) throw new Error("zh.js 需要先加载 engine/zh_table.js");
  // 转成无原型的字典：查表时不必担心 "constructor" 之类的键名撞上 Object.prototype。
  const S2T = Object.assign(Object.create(null), NS.zhTable.s2t);
  const T2S = Object.assign(Object.create(null), NS.zhTable.t2s);

  const isHigh = (u) => u >= 0xd800 && u <= 0xdbff;
  const isLow = (u) => u >= 0xdc00 && u <= 0xdfff;

  function convertWith(table, s) {
    if (!s) return s;
    const n = [...s].length;         // Python 的 len()：码位数
    const units = s.slice(0, n);     // 系统 API 只处理前 n 个 UTF-16 单元
    let out = "";
    for (let i = 0; i < units.length; ) {
      const cu = units.charCodeAt(i);
      if (isHigh(cu) && i + 1 < units.length && isLow(units.charCodeAt(i + 1))) {
        out += units.substr(i, 2);   // 完整代理对 = 一个星形汉字：系统原样放行
        i += 2;
      } else {
        const ch = units[i];         // 孤立代理项也走这里：表里没有它 → 原样放行
        const v = table[ch];
        out += v === undefined ? ch : v;
        i += 1;
      }
    }
    return out;
  }

  NS.zh = {
    // 与 search/zh.py 同名同义；失败时 Python 恒等回退，这里查不到即原字，一致。
    toTraditional: (s) => convertWith(S2T, s),
    toSimplified: (s) => convertWith(T2S, s),
    // 供自检使用：表里有多少条
    size: () => ({ s2t: Object.keys(S2T).length, t2s: Object.keys(T2S).length }),
  };
})(window.HistoryAIEngine = window.HistoryAIEngine || {});
