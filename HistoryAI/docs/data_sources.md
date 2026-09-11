# 数据来源与再分发

本文回答两件事：**库里的原文从哪来**，以及**什么能公开、什么不能**。

## 一、原始语料

`HistoryLibrary/kanripo/` 下是 Kanripo（漢籍リポジトリ / Kanseki Repository）项目的
纯文本，五部先秦典籍，共 118 个 txt：

| 目录 | 书名 | Kanripo ID | 底本 | 文件数 | 体积 |
|------|------|-----------|------|-------:|-----:|
| `guoyu/` | 國語 | KR2e0001 | SBCK（四部叢刊） | 22 | 529K |
| `shangshu/` | 尚書 | KR1b0001 | tls | 59 | 321K |
| `shiji/` | 史記 | KR2a0001 | tls | 14 | 3.1M |
| `zhanguoce/` | 戰國策 | KR2e0003 | SBCK | 11 | 942K |
| `zuozhuan/` | 春秋左傳 | KR1e0001 | tls | 12 | 1.7M |

上表的 ID/底本取自每个文件自己的头部元数据（`#+PROPERTY: ID` / `BASEEDITION` /
`WITNESS`），不是外部查来的 —— 换句话说，**这些字段是语料自己说的**。

文件形态：`#+` 开头的 org 模式头部 + 正文。正文里 `¶` 是 Kanripo 的句读分隔符，
`<pb:…>` 是原书页码锚点。tls 家族与 SBCK 家族的差别见 `phase2_report.md`。

## 二、能不能再分发：**不能确认，所以没有打包**

对整个 `HistoryLibrary/` 做过一次检索：**没有任何 README、LICENSE、COPYING 或版权
声明文件**；文件头里也只有 ID/底本/见证本这类书目元数据，没有授权条款。

任务书 §23 对此有明确处置：

> 不要默认把 `HistoryLibrary/kanripo/` 整个上传到 Public Repository；先检查
> README/license/copyright/source attribution；**如果无法确认：不要上传原始
> corpus**，而是 `.gitignore` 它并在 README 说明。

所以本仓库采取的做法是：

1. `HistoryProject/.gitignore` 里忽略 `HistoryLibrary/kanripo/`；
2. 想跑这个项目的读者，**自行**从 Kanripo 获取对应五部书的 txt，放回
   `HistoryLibrary/kanripo/<书>/` 原位置（目录名与上表一致）；
3. 管线只读这些文件，不做任何写入，路径由 `scripts/pipeline/config.py` 统一解析。

**没有做的事**（不做为妙）：没有替语料补一份许可证、没有凭「古籍本身是公版」就
推断扫描整理版也是公版、没有把语料换个地方偷偷带上。整理/标点/校勘是有劳动的，
公版的是古人写的字，不是这一版的整理成果 —— 这两件事不能混为一谈。

## 三、派生产物

`HistoryAI/data/` 全部是**派生产物**：`metadata/`（扫描清单）、`processed/`
（解析后的 JSONL）、`database/history.db`（SQLite，含 FTS5 索引）、`logs/`。
它们都能由「原始语料 + `scripts/pipeline`」一键重建（约 15 秒），实测 314MB，
因此同样 `.gitignore`（§23 也点名了 `data/`、`*.db`、缓存、临时文件）。

重建方式见 README 的「运行」一节：`python scripts/pipeline/run_all.py`。

## 四、派生数据里会不会夹带原文

会，而且是有意为之 —— `passages.text_orig` 就是原文本身的一行行切片，检索结果
直接展示它。这是本项目的目的（让用户读到真实史料），不是疏漏。

需要留意的是：**只要发布了 `history.db`，就等于发布了语料**。所以数据库和语料
一样按「不能确认授权 → 不外传」处理。真要公开演示，得换成自有版权的文本，
或者只发布代码 + 让使用者自建库。

## 五、代码与文档

`HistoryAI/` 下的代码、前端、测试、文档是本项目自己的产物。
发布前的安全审计（§22）已核对：源码与文档里不含 API key、token、密码、cookie、
私密 URL、本机绝对路径、个人信息。

审计中改名/改写过的地方只有一处：`docs/phase2_report.md` 结尾提到过一个本机
绝对路径，已改为相对描述。
