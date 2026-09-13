# 第六阶段 · 搜索召回基线报告

生成时间：2026-09-13 00:16:02

由 `python tests/recall.py --report docs/phase6_recall.md` 生成，请勿手改。

## 运行环境

- 数据库：`D:\MyCode\HistoryProject\HistoryAI\data\database\history.db`
- 用例集：`tests/search_cases/`（2 个时代文件，160 条）
- 繁简转换：**可用**

繁简转换是否可用是全局开关——脚本 `search/zh.py` 依赖 Windows 的 `LCMapStringEx`，非 Windows 或调用失败会静默返回原文。

## 分类器自检

**通过。** 注入已知故障后，分类器能把「繁体原形有命中却返回 0」判为 `Search`、把「只有转换形才有命中」判为 `Normalization`、把「语料确实没有」判为 `Coverage`，并在繁简回退时如实报 `UNKNOWN`。

这一步是必需的：全绿的跑分报告本身证明不了任何事——一个永远返回 `PASS`/`Coverage` 的分类器看起来一模一样。

## 汇总

| 结果 | 条数 |
|---|---|
| 通过 | 160 |
| 注意 | 0 |
| 失败 | 0 |
| 合计 | 160 |

### 八维分布

| 维度 | 条数 | 含义 |
|---|---|---|
| `Coverage` | 16 | 语料里确实没有（检索列 instr 计数为 0） |

## 逐条结果

| id | 分组 | 查询 | 转换后 | 参数 | 语料段 | 命中段 | 结果块 | 命中形态 | 路径 | 机械审计 | 出处 | 维度 | 结论 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| person-01 | person | 齐桓公 | 齊桓公 | 默认 | 151 | 151 | 126 | text | fts | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| person-02 | person | 管仲 | 管仲 | 默认 | 189 | 189 | 141 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| person-03 | person | 楚庄王 | 楚莊王 | 默认 | 55 | 55 | 45 | text | fts | Passage:通过、Provenance:通过 | 史記 |  | PASS |
| person-04 | person | 郑庄公 | 鄭莊公 | 默认 | 19 | 19 | 17 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| person-05 | person | 秦始皇 | 秦始皇 | 默认 | 103 | 103 | 101 | both、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| person-06 | person | 晋文公 | 晉文公 | 默认 | 110 | 110 | 88 | text | fts | Passage:通过、Provenance:通过 | 史記、國語、春秋左傳 |  | PASS |
| person-07 | person | 重耳 | 重耳 | 默认 | 223 | 223 | 127 | text | bigram | Passage:通过、Provenance:通过 | 史記、春秋左傳 |  | PASS |
| person-08 | person | 秦穆公 | 秦穆公 | 默认 | 45 | 45 | 43 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| person-09 | person | 百里奚 | 百里奚 | 默认 | 26 | 26 | 23 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| person-10 | person | 伍子胥 | 伍子胥 | 默认 | 59 | 59 | 49 | both、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| person-11 | person | 孙武 | 孫武 | 默认 | 22 | 22 | 19 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| person-12 | person | 孔子 | 孔子 | 默认 | 1301 | 1301 | 1001 | both、text | bigram | Passage:通过、Provenance:通过 | 史記 |  | PASS |
| person-13 | person | 墨子 | 墨子 | 默认 | 50 | 50 | 43 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| person-14 | person | 孟子 | 孟子 | 默认 | 202 | 202 | 165 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| person-15 | person | 荀子 | 荀子 | 默认 | 16 | 16 | 15 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書、戰國策 |  | PASS |
| person-16 | person | 商鞅 | 商鞅 | 默认 | 30 | 30 | 29 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| person-17 | person | 苏秦 | 蘇秦 | 默认 | 231 | 231 | 164 | both、text | bigram | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| person-18 | person | 张仪 | 張儀 | 默认 | 355 | 355 | 228 | both、text | bigram | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| place-01 | place | 城濮 | 城濮 | 默认 | 35 | 35 | 34 | text | bigram | Passage:通过、Provenance:通过 | 史記、國語、後漢書… |  | PASS |
| place-02 | place | 長勺 | 長勺 | 默认 | 7 | 7 | 6 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、國語、春秋左傳 |  | PASS |
| place-03 | place | 邯鄲 | 邯鄲 | 默认 | 385 | 385 | 297 | text | bigram | Passage:通过、Provenance:通过 | 史記、後漢書、戰國策… |  | PASS |
| place-04 | place | 曲沃 | 曲沃 | 默认 | 146 | 146 | 96 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、春秋左傳 |  | PASS |
| place-05 | place | 葵丘 | 葵丘 | 默认 | 28 | 28 | 25 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| place-06 | place | 滎陽 | 滎陽 | 默认 | 297 | 297 | 238 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| place-07 | place | 垓下 | 垓下 | 默认 | 26 | 26 | 22 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| state-01 | state | 齊國 | 齊國 | 默认 | 131 | 131 | 123 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| state-02 | state | 晉國 | 晉國 | 默认 | 160 | 160 | 145 | text | bigram | Passage:通过、Provenance:通过 | 史記、國語、春秋左傳 |  | PASS |
| state-03 | state | 楚國 | 楚國 | 默认 | 134 | 134 | 125 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、戰國策… |  | PASS |
| state-04 | state | 秦國 | 秦國 | 默认 | 38 | 38 | 35 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| state-05 | state | 宋國 | 宋國 | 默认 | 13 | 13 | 13 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| state-06 | state | 越國 | 越國 | 默认 | 29 | 29 | 27 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| war-01 | war | 城濮之戰 | 城濮之戰 | 默认 | 1 | 1 | 1 | text | fts | Passage:通过、Provenance:通过 | 春秋左傳 |  | PASS |
| war-02 | war | 鄢陵 | 鄢陵 | 默认 | 69 | 69 | 67 | text | bigram | Passage:通过、Provenance:通过 | 史記、國語、戰國策… |  | PASS |
| war-03 | war | 長平 | 長平 | 默认 | 137 | 137 | 127 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| war-04 | war | 鉅鹿 | 鉅鹿 | 默认 | 147 | 147 | 129 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| war-05 | war | 韓原 | 韓原 | 默认 | 9 | 9 | 9 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| office-01 | office | 丞相 | 丞相 | 默认 | 1534 | 1534 | 1125 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| office-02 | office | 令尹 | 令尹 | 默认 | 216 | 216 | 170 | text | bigram | Passage:通过、Provenance:通过 | 史記、春秋左傳 |  | PASS |
| office-03 | office | 太尉 | 太尉 | 默认 | 640 | 640 | 510 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| office-04 | office | 大夫 | 大夫 | 默认 | 3531 | 3531 | 2994 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| office-05 | office | 將軍 | 將軍 | 默认 | 3975 | 3975 | 2698 | text | bigram | Passage:通过、Provenance:通过 | 史記、後漢書 |  | PASS |
| chapter-01 | chapter | 秦本紀 | 秦本紀 | 默认 | 8 | 8 | 9 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| chapter-02 | chapter | 周本紀 | 周本紀 | 默认 | 5 | 5 | 6 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| chapter-03 | chapter | 晉世家 | 晉世家 | 默认 | 3 | 3 | 4 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| chapter-04 | chapter | 十二諸侯年表 | 十二諸侯年表 | 默认 | 2 | 2 | 3 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| event-01 | event | 焚書 | 焚書 | 默认 | 11 | 11 | 9 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| event-02 | event | 三家分晉 | 三家分晉 | 默认 | 2 | 2 | 2 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| single-01 | single | 尧 | 堯 | 默认 | 712 | 712 | 573 | both、text | like | Passage:通过、Provenance:通过 | 前漢書、史記、尚書… |  | PASS |
| single-02 | single | 舜 | 舜 | 默认 | 780 | 780 | 610 | both、text | like | Passage:通过、Provenance:通过 | 史記、尚書、後漢書… |  | PASS |
| single-03 | single | 禹 | 禹 | 默认 | 1105 | 1105 | 862 | both、text | like | Passage:通过、Provenance:通过 | 前漢書、史記、尚書… |  | PASS |
| single-04 | single | 郢 | 郢 | 默认 | 278 | 278 | 213 | text | like | Passage:通过、Provenance:通过 | 史記、戰國策、春秋左傳 |  | PASS |
| single-05 | single | 絳 | 絳 | 默认 | 377 | 377 | 311 | text | like | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| multi-01 | multi | 齊桓公 管仲 | 齊桓公 管仲 | 默认 | 10 | 10 | 10 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| multi-02 | multi | 蘇秦 張儀 | 蘇秦 張儀 | 默认 | 21 | 21 | 19 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| multi-03 | multi | 秦穆公 百里奚 | 秦穆公 百里奚 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| script-01 | script | 齐桓公 | 齊桓公 | 默认 | 151 | 151 | 126 | text | fts | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| script-02 | script | 齊桓公 | 齊桓公 | 默认 | 151 | 151 | 126 | text | fts | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| script-03 | script | 苏秦 | 蘇秦 | 默认 | 231 | 231 | 164 | both、text | bigram | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| script-04 | script | 蘇秦 | 蘇秦 | 默认 | 231 | 231 | 164 | both、text | bigram | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| script-05 | script | 张仪 | 張儀 | 默认 | 355 | 355 | 228 | both、text | bigram | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| script-06 | script | 張儀 | 張儀 | 默认 | 355 | 355 | 228 | both、text | bigram | Passage:通过、Provenance:通过 | 史記、戰國策 |  | PASS |
| script-07 | script | 郑庄公 | 鄭莊公 | 默认 | 19 | 19 | 17 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| script-08 | script | 鄭莊公 | 鄭莊公 | 默认 | 19 | 19 | 17 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| script-09 | script | 晋文公 | 晉文公 | 默认 | 110 | 110 | 88 | text | fts | Passage:通过、Provenance:通过 | 史記、國語、春秋左傳 |  | PASS |
| script-10 | script | 晉文公 | 晉文公 | 默认 | 110 | 110 | 88 | text | fts | Passage:通过、Provenance:通过 | 史記、國語、春秋左傳 |  | PASS |
| section-01 | section | 秦始皇本紀 | 秦始皇本紀 | recall=section | 2 | 2 | 3 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| section-02 | section | 大禹謨 | 大禹謨 | recall=section | 1 | 1 | 2 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書、尚書 |  | PASS |
| section-03 | section | 五帝本紀 | 五帝本紀 | recall=section | 2 | 2 | 3 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| section-04 | section | 秦本紀 | 秦本紀 | recall=section | 8 | 8 | 9 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| section-05 | section | 尚書逸文 | 尚書逸文 | recall=section | 0 | 0 | 11 | section | fts | Passage:通过、Provenance:通过 | 尚書 |  | PASS |
| section-06 | section | 晉語 | 晉語 | recall=section | 8 | 8 | 16 | section、text | bigram | Passage:通过、Provenance:通过 | 前漢書、國語、戰國策 |  | PASS |
| pagination-01 | pagination | 之 | 之 | page_size=100 | 75766 | 75766 | 42166 | text | like | Pagination:通过、Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| pagination-02 | pagination | 大夫 | 大夫 | 默认 | 3531 | 3531 | 2994 | text | bigram | Pagination:通过、Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| pagination-03 | pagination | 齊 | 齊 | 默认 | 8204 | 8204 | 5131 | text | like | Pagination:通过、Passage:通过、Provenance:通过 | 史記、戰國策、春秋左傳 |  | PASS |
| pagination-04 | pagination | 將軍 | 將軍 | 默认 | 3975 | 3975 | 2698 | text | bigram | Pagination:通过、Passage:通过、Provenance:通过 | 史記、後漢書 |  | PASS |
| passage-01 | passage | 齊桓公 | 齊桓公 | mode=long | 151 | 151 | 115 | text | fts | Passage:通过、Provenance:通过 | 史記 |  | PASS |
| passage-02 | passage | 管仲 | 管仲 | mode=long、page_size=50 | 189 | 189 | 133 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、國語… |  | PASS |
| neg-02 | negative | 坑儒 | 坑儒 | 默认 | 0 | 0 | 0 | — | bigram | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| neg-03 | negative | 商鞅變法 | 商鞅變法 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| neg-04 | negative | 秦策一 | 秦策一 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| neg-05 | negative | 燕策 | 燕策 | 默认 | 0 | 0 | 0 | — | bigram | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| neg-06 | negative | 重耳 秦穆公 | 重耳 秦穆公 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-person-01 | person | 李斯 | 李斯 | 默认 | 95 | 95 | 74 | both、text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書… |  | PASS |
| qh-person-02 | person | 赵高 | 趙高 | 默认 | 89 | 89 | 61 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-person-03 | person | 项羽 | 項羽 | 默认 | 456 | 456 | 292 | text | bigram | Passage:通过、Provenance:通过 | 史記 |  | PASS |
| qh-person-04 | person | 韩信 | 韓信 | 默认 | 272 | 272 | 214 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-person-05 | person | 萧何 | 蕭何 | 默认 | 152 | 152 | 127 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-person-06 | person | 张良 | 張良 | 默认 | 111 | 111 | 92 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-person-07 | person | 司马迁 | 司馬遷 | 默认 | 54 | 54 | 55 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-person-08 | person | 班超 | 班超 | 默认 | 27 | 27 | 22 | text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-person-09 | person | 卫青 | 衛青 | 默认 | 51 | 51 | 46 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-person-10 | person | 霍去病 | 霍去病 | 默认 | 35 | 35 | 35 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-person-11 | person | 张骞 | 張騫 | 默认 | 48 | 48 | 45 | both、text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-person-12 | person | 苏武 | 蘇武 | 默认 | 36 | 36 | 32 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-person-13 | person | 王莽 | 王莽 | 默认 | 571 | 571 | 543 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-person-14 | person | 刘秀 | 劉秀 | 默认 | 9 | 9 | 8 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-person-15 | person | 吕后 | 呂后 | 默认 | 179 | 179 | 123 | text | bigram | Passage:通过、Provenance:通过 | 史記 |  | PASS |
| qh-person-16 | person | 董卓 | 董卓 | 默认 | 157 | 157 | 132 | both、text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-alias-01 | alias | 高祖 | 高祖 | 默认 | 585 | 585 | 399 | both、text | bigram | Passage:通过、Provenance:通过 | 史記 |  | PASS |
| qh-alias-02 | alias | 沛公 | 沛公 | 默认 | 431 | 431 | 218 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-alias-03 | alias | 汉武帝 | 漢武帝 | 默认 | 8 | 8 | 8 | text | fts | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-alias-04 | alias | 武帝 | 武帝 | 默认 | 877 | 877 | 808 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-alias-05 | alias | 汉文帝 | 漢文帝 | 默认 | 3 | 3 | 3 | text | fts | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-alias-06 | alias | 文帝 | 文帝 | 默认 | 515 | 515 | 426 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-alias-07 | alias | 景帝 | 景帝 | 默认 | 401 | 401 | 310 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-alias-08 | alias | 光武 | 光武 | 默认 | 705 | 705 | 590 | both、text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-alias-09 | alias | 元后 | 元后 | 默认 | 44 | 44 | 39 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、國語、尚書… |  | PASS |
| qh-alias-10 | alias | 吕太后 | 呂太后 | 默认 | 61 | 61 | 51 | both、text | fts | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-place-01 | place | 马邑 | 馬邑 | 默认 | 87 | 87 | 63 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-place-02 | place | 河西 | 河西 | 默认 | 127 | 127 | 111 | text | bigram | Passage:通过、Provenance:通过 | 史記、後漢書、戰國策… |  | PASS |
| qh-place-03 | place | 西域 | 西域 | 默认 | 310 | 310 | 249 | both、text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-war-01 | war | 白登 | 白登 | 默认 | 12 | 12 | 12 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-event-01 | event | 党锢 | 黨錮 | 默认 | 21 | 21 | 21 | text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-event-02 | event | 黄巾 | 黃巾 | 默认 | 1 | 1 | 1 | text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-event-03 | event | 推恩 | 推恩 | 默认 | 10 | 10 | 10 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-office-01 | office | 骠骑将军 | 驃騎將軍 | 默认 | 90 | 90 | 62 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-office-02 | office | 西域都护 | 西域都護 | 默认 | 7 | 7 | 7 | text | fts | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-office-03 | office | 侍中 | 侍中 | 默认 | 592 | 592 | 535 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-section-01 | section | 光武帝纪第一上 | 光武帝紀第一上 | recall=section | 0 | 0 | 1 | section | fts | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-section-02 | section | 艺文志第十 | 藝文志第十 | recall=section | 0 | 0 | 1 | section | fts | Passage:通过、Provenance:通过 | 前漢書 |  | PASS |
| qh-section-03 | section | 地理志第八上 | 地理志第八上 | recall=section | 0 | 0 | 1 | section | fts | Passage:通过、Provenance:通过 | 前漢書 |  | PASS |
| qh-section-04 | section | 班梁列传第三十七 | 班梁列傳第三十七 | recall=section | 0 | 0 | 1 | section | fts | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-section-05 | section | 高帝纪第一上 | 高帝紀第一上 | recall=section | 1 | 1 | 2 | section、text | fts | Passage:通过、Provenance:通过 | 前漢書 |  | PASS |
| qh-section-06 | section | 西周 | 西周 | book=戰國策、recall=section | 120 | 73 | 54 | both、text | bigram | Passage:通过、Provenance:通过 | 戰國策 |  | PASS |
| qh-section-07 | section | 东周 | 東周 | book=戰國策、page_size=100、recall=section | 100 | 68 | 51 | section、text | bigram | Passage:通过、Provenance:通过 | 戰國策 |  | PASS |
| qh-multi-01 | multi | 卫青 霍去病 | 衛青 霍去病 | 默认 | 4 | 4 | 4 | text | fts | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-multi-02 | multi | 王莽 光武 | 王莽 光武 | 默认 | 9 | 9 | 9 | text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-multi-03 | multi | 苏武 匈奴 | 蘇武 匈奴 | 默认 | 8 | 8 | 8 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-multi-04 | multi | 匈奴 西域 | 匈奴 西域 | 默认 | 44 | 44 | 41 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-multi-05 | multi | 萧何 韩信 | 蕭何 韓信 | 默认 | 6 | 6 | 6 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-multi-06 | multi | 高祖 项羽 | 高祖 項羽 | 默认 | 8 | 8 | 8 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-script-01 | script | 卫青 | 衛青 | 默认 | 51 | 51 | 46 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-script-02 | script | 衛青 | 衛青 | 默认 | 51 | 51 | 46 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-script-03 | script | 张骞 | 張騫 | 默认 | 48 | 48 | 45 | both、text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-script-04 | script | 張騫 | 張騫 | 默认 | 48 | 48 | 45 | both、text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-script-05 | script | 苏武 | 蘇武 | 默认 | 36 | 36 | 32 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-script-06 | script | 蘇武 | 蘇武 | 默认 | 36 | 36 | 32 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-script-07 | script | 吕后 | 呂后 | 默认 | 179 | 179 | 123 | text | bigram | Passage:通过、Provenance:通过 | 史記 |  | PASS |
| qh-script-08 | script | 呂后 | 呂后 | 默认 | 179 | 179 | 123 | text | bigram | Passage:通过、Provenance:通过 | 史記 |  | PASS |
| qh-script-09 | script | 刘秀 | 劉秀 | 默认 | 9 | 9 | 8 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-script-10 | script | 劉秀 | 劉秀 | 默认 | 9 | 9 | 8 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-script-11 | script | 党锢 | 黨錮 | 默认 | 21 | 21 | 21 | text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-script-12 | script | 黨錮 | 黨錮 | 默认 | 21 | 21 | 21 | text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-single-01 | single | 羌 | 羌 | 默认 | 944 | 944 | 680 | text | like | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-single-02 | single | 鲜卑 | 鮮卑 | 默认 | 213 | 213 | 151 | text | bigram | Passage:通过、Provenance:通过 | 後漢書 |  | PASS |
| qh-pagination-01 | pagination | 汉 | 漢 | 默认 | 8610 | 8610 | 5921 | text | like | Pagination:通过、Passage:通过、Provenance:通过 | 前漢書、史記 |  | PASS |
| qh-pagination-02 | pagination | 单于 | 單于 | 默认 | 1298 | 1298 | 803 | text | bigram | Pagination:通过、Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-pagination-03 | pagination | 大将军 | 大將軍 | 默认 | 887 | 887 | 708 | text | fts | Pagination:通过、Passage:通过、Provenance:通过 | 史記、後漢書 |  | PASS |
| qh-passage-01 | passage | 王莽 | 王莽 | mode=long | 571 | 571 | 540 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、後漢書 |  | PASS |
| qh-passage-02 | passage | 匈奴 | 匈奴 | mode=long、page_size=50 | 2007 | 2007 | 1318 | text | bigram | Passage:通过、Provenance:通过 | 前漢書、史記、後漢書 |  | PASS |
| qh-neg-01 | negative | 巨鹿 | 巨鹿 | 默认 | 0 | 0 | 0 | — | bigram | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-02 | negative | 刘邦 | 劉邦 | 默认 | 0 | 0 | 0 | — | bigram | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-03 | negative | 王政君 | 王政君 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-04 | negative | 文景之治 | 文景之治 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-05 | negative | 党锢之祸 | 黨錮之禍 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-06 | negative | 黄巾之乱 | 黃巾之亂 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-07 | negative | 推恩令 | 推恩令 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-08 | negative | 丝绸之路 | 絲綢之路 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-09 | negative | 河西之战 | 河西之戰 | 默认 | 0 | 0 | 0 | — | fts | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |
| qh-neg-10 | negative | 刘邦 项羽 | 劉邦 項羽 | 默认 | 0 | 0 | 0 | — | bigram | — | — | Coverage | PASS：预期为空，归因 Coverage 相符 |

## 0 命中清单（21 条）

每条都写明归因。`Coverage` 是语料问题（该扩语料），`Search` 才是引擎问题（该改代码）——两者绝不能混。

| id | 查询 | 语料段 | 归因 | 说明 |
|---|---|---|---|---|
| multi-03 | 秦穆公 百里奚 | 0 | Coverage | 实测共段 = 0（单独各 25 / 11）。两词分处不同段，AND 语义下必须返回空——预期为空的对照 |
| section-05 | 尚書逸文 | 0 | - | 同一个篇名在 24 个区间上重复（尚書逸文横跨 24 个文件）。实测 11 块——多个区间指向同一条首记录时只产出一块 |
| neg-02 | 坑儒 | 0 | Coverage | 实测正文 0 段（异体字 阬儒 亦为 0）；焚書 有 6 段，但坑儒确不在库 |
| neg-03 | 商鞅變法 | 0 | Coverage | 现代合成词，古籍正文不会以此四字连写；商鞅 单独有 9 段 |
| neg-04 | 秦策一 | 0 | Coverage | 本底本（SBCK 鮑彪校注本）**没有「秦策一」式编次**：戰國策 的篇题粒度为「卷第一~卷第十，每卷一个国别」，12 个国别标题是 東周/西周/秦/齊/楚/趙/魏/韓/燕/宋/衛/中山。第六点二阶段已把国别抽成 sections（正例见 qin_han 的 qh-section-06/07），所以这条负例现在考的是另一件事：**「秦策一」这个写法在本底本不存在**，正文 0 段、篇名 0 条。不是覆盖缺口，是用词与底本不符 |
| neg-05 | 燕策 | 0 | Coverage | 与 neg-04 同一原因：本底本只有国别篇题（燕），没有「燕策」式篇名。正例是 qin_han 的 qh-section-06（西周） |
| neg-06 | 重耳 秦穆公 | 0 | Coverage | 实测共段 = 0（单独各 198 / 25）。多词 AND 语义正确工作，属预期为空的对照 |
| qh-section-01 | 光武帝纪第一上 | 0 | - | 後漢書篇名，正文 0 段。简体输入经转换命中 WYG 底本的篇题行 |
| qh-section-02 | 艺文志第十 | 0 | - | 前漢書篇名，正文 0 段 |
| qh-section-03 | 地理志第八上 | 0 | - | 前漢書篇名；WYG 底本作「地理志第八上」，卷次带「上」 |
| qh-section-04 | 班梁列传第三十七 | 0 | - | 後漢書篇名（班超、梁慬合传），正文 0 段 |
| qh-neg-01 | 巨鹿 | 0 | Coverage | 正字/异体字不通用：語料作 鉅鹿 147 段（正例见 preqin war-04），「巨鹿」0 段。繁简转换不管异体字 |
| qh-neg-02 | 刘邦 | 0 | Coverage | 語料作 高祖 585 / 沛公 431（正例 qh-alias-01/02），「劉邦」0 段。检索不做别名映射 |
| qh-neg-03 | 王政君 | 0 | Coverage | 語料作 元后 44（qh-alias-09），「王政君」0 段；且 元后 还混有尚書的天子义 |
| qh-neg-04 | 文景之治 | 0 | Coverage | 现代合成词，古籍不作四字连写（文帝 515 / 景帝 401 都有） |
| qh-neg-05 | 党锢之祸 | 0 | Coverage | 现代合成词；語料作 黨錮 21（qh-event-01） |
| qh-neg-06 | 黄巾之乱 | 0 | Coverage | 語料 黃巾 仅 1 段（qh-event-02），无「之乱」连写 |
| qh-neg-07 | 推恩令 | 0 | Coverage | 語料作 推恩 10（qh-event-03），无「令」字连写 |
| qh-neg-08 | 丝绸之路 | 0 | Coverage | 现代术语，古籍不作此名（語料有 西域 310 段） |
| qh-neg-09 | 河西之战 | 0 | Coverage | 现代合成词；地名 河西 有 127 段（qh-place-02） |
| qh-neg-10 | 刘邦 项羽 | 0 | Coverage | 两个检索词都按现代写法：劉邦 0 段、項羽 456 段，AND 下必然为 0。改用語料写法（高祖 项羽）共段 8（qh-multi-06） |

## 繁简一致性

简体输入与繁体直输必须给出相同的命中数，否则说明转换环节有问题。

| 简体 | 繁体 | 简体命中 | 繁体命中 | 一致 |
|---|---|---|---|---|
| 齐桓公 | 齊桓公 | 151 | 151 | 是 |
| 苏秦 | 蘇秦 | 231 | 231 | 是 |
| 张仪 | 張儀 | 355 | 355 | 是 |
| 郑庄公 | 鄭莊公 | 19 | 19 | 是 |
| 晋文公 | 晉文公 | 110 | 110 | 是 |
| 卫青 | 衛青 | 51 | 51 | 是 |
| 张骞 | 張騫 | 48 | 48 | 是 |
| 苏武 | 蘇武 | 36 | 36 | 是 |
| 吕后 | 呂后 | 179 | 179 | 是 |
| 刘秀 | 劉秀 | 9 | 9 | 是 |
| 党锢 | 黨錮 | 21 | 21 | 是 |

## UNKNOWN 清单（0 条）

无。分类器对所有 0 命中都给出了归因。

## 基线漂移（0 条）

`search_cases/` 里的 `baseline_hits` / `baseline_blocks` 是 2026-09-12 在 7 部语料上的实测值（第六点二阶段扩容后重测）。漂移本身不是失败——语料扩充后必然变化——但每条都要能解释。

无漂移，与建立基线时完全一致。
