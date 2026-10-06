# SATeacher 开发计划

状态：`draft · 待确认` ｜ 配套文档：[SAT-MD 格式规范](./SAT-MD.md)

## 1. 产品目标

SAT 自动刷题助手：**导入题目文档 → 生成题数并补录答案 → Bluebook 风格做题 → 错题分析 → 生词本 / 笔记 → 多格式导出**。

## 2. 已确认的决策

| 维度 | 决策 |
|---|---|
| 形态 | 本地 Web 应用（浏览器访问本机服务） |
| 技术栈 | FastAPI（Python）+ React（Vite, TS, Tailwind） |
| 文档定位 | **文档本身就是题库**（含题干 + 四选项），不是阅读材料 |
| 题型 | 全部四选一；分 `rw`（语文）与 `math`（数学） |
| 答案 | 导入时可能没有 → 导入后进「答案录入页」按题号补；源文档已含答案则直接用 |
| passage | 每题独立，阅读材料随题走（`@material`） |
| 图片 | 必须支持（从 PDF 抠图 + 前端渲染） |
| PDF 转换 | 纯代码优先（PyMuPDF），**LLM 只做识别失败页的兜底** |
| 错题分析 | **用户自己写**；LLM 仅作侧边栏，按需讲解 |
| 存储 | SQLite 单文件 |
| 节奏 | 先打通端到端最小闭环，再堆功能 |
| 界面语言 | 全英文 |
| MVP 导入格式 | PDF + 手写 `.sat.md`（DOCX 放 Phase 4） |
| 图表抠图 | 位图直接提取；矢量图按包围盒截图兜底 |
| 推进方式 | Phase 0→1 连续做完，验收后再进 Phase 2 |
| PDF 转换（2026-10-06） | 新增 **Bluebook 双栏 profile**（`convert/bluebook.py`）：徽章数字 + 行带 y 对齐配对左栏 passage 与右栏题干，选项续行拼接，页眉/页脚/圆圈选项伪图过滤；纯坐标确定性，0 token。真实 17 页导出 PDF → 27/27 题转换成功 |
| LLM 配置（2026-10-06） | 设置页存 SQLite `settings` 表：Provider（OpenAI/Anthropic，OpenAI 可自定义 Base URL）+ API Key + Model；Key 只写不回传（GET 掩码）；「Test connection」走供应商 `/models` 列表接口，0 token |
| **混合转换（批1，2026-10-06）** | 确定性 profile 优先（0 token 秒回）；非 fatal 的 `ConvertError(fallback=True)` 触发 **LLM 兜底**；fatal（打不开/加密/0 页/0 文本）`fallback=False` 不兜底。LLM 只**打标**（material/question/option/answer/ignore），组装由代码完成；输出必过确定性校验（原文 verbatim fidelity、NFKC+弯引号+空白+casefold 后 substring、每题恰 A–D），不过则带反馈纠错**重试 1 次**。兜底成功导入卡显示 warning「AI-assisted import…」；未配置 API 时报错「no LLM API configured; add an API key and a model in Settings」 |
| **LLM 层（批1）** | `app/llm/base.py`：`complete(system, messages)` / `configured()` / typed `LLMError`；temperature 0、timeout 60s；OpenAI + Anthropic 双传输；401/403/404/429/400/5xx/网络错误统一映射为可读消息 |
| **练习流程（批2）** | 全屏开始屏（`Begin — enter fullscreen`，requestFullscreen 必须用户手势，失败 catch 后继续）→ 做题 → 交卷。源无答案（graded==0）→ 跳 `/doc/:id/answers?session=:sid` 补录 → 「Save & view results」判分；源有答案直接出结果。结果页独立路由 `/session/:sid/result`：汇总卡（分数/用时/Practice again/Back to library）+ **三选一 tab**（All 标 ✓✗– / Correct only / Wrong only）+ 题卡点选。后端新增 `POST /api/sessions/{id}/regrade`（按存储的 chosen 重判分；未提交 409） |
| **IDE 折叠栏（批3）** | 结果页右侧 `ReviewSidebar`（手风琴三区 + Export）：**Explanation**——解析手写直存 DB（`PUT …/questions/{qid}/explain`，0 token，空串清除）；**Vocabulary**——Numbers/Excel 式自由表格（默认 `Word｜Meaning｜Notes`，行列增删改，`GET/PUT …/words`，openpyxl 导出 `.xlsx`）；**AI Answer**——context = **题目题干 + 正确选项**（不含材料/用户作答/手写解析），`POST /api/ai/answer`，未配 key 409、LLMError 502 |
| **导出 + 统计（批4）** | `GET /api/documents/{id}/export/{md\|csv\|json}`（题干+选项+答案+解析，0 token，CSV 标准引号转义）；结果页**纯统计面板**：Score（含 blank 数）、分 section 正确率（rw/math）、用时、错题 chips（点击跳题）。新依赖 **openpyxl（已批准）** |

## 3. Token 成本原则

**LLM 不在主链路上。**

```
PDF/DOCX/MD ──纯代码──> raw.md ──纯代码规范化──> .sat.md ──确定性 parser──> JSON ──> SQLite
                                        ↑
                          仅当某页识别失败（开关控制）→ LLM 兜底
                          仅当用户点「讲解这题」→ LLM 侧边栏
```

导入一份题库 **0 token**；讲解按次计费。

**混合转换细则（批1）**：确定性 profile（SAT/Bluebook/normalize）先跑；抛 `ConvertError(fallback=True)`（非 fatal：如无法识别版式）才进 LLM 兜底；fatal 错误（文件打不开、密码、0 页、0 文本）`fallback=False` 直接报错。兜底时 LLM 仅对每页文本打标（material/question/option/answer/ignore），题目组装、选项配对、A–D 校验全部由代码完成，结果必过 verbatim fidelity 校验，失败带反馈重试 1 次。AI 只在**用户显式动作**时花钱：兜底导入、AI 解答按钮。

## 4. 架构

```
SATeacher/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI 入口、CORS、路由挂载
│   │   ├── db.py              # sqlite 连接 + schema 迁移
│   │   ├── repos/             # documents / questions / sessions / vocab / notes / settings
│   │   ├── convert/           # PDF|DOCX|MD → SAT-MD
│   │   │   ├── pdf.py         #   PyMuPDF 文本与图片抽取
│   │   │   ├── normalize.py   #   断行合并、选项/题号识别、答案区回填、sec 判定
│   │   │   ├── images.py      #   抠图 → assets/
│   │   │   └── llm_fallback.py#   识别失败页兜底（可开关）
│   │   ├── satmd/parser.py    # SAT-MD → JSON，确定性状态机，不调 LLM
│   │   ├── llm/
│   │   │   ├── base.py        # 统一接口：complete(system, messages)
│   │   │   ├── openai.py      # OpenAI（含 base_url 可指向任何兼容端点）
│   │   │   └── anthropic.py   # Anthropic
│   │   └── api/               # routers
│   ├── tests/                 # fixture：pdf / sat.md / parser 用例
│   └── requirements.txt
├── frontend/
│   └── src/
│       ├── pages/             # Import · AnswerKey · Practice · Result · Wrong · Vocab · Notes · Settings
│       ├── components/        # 题面、A–D 选项、答题卡、计时器、LLM 侧边栏
│       └── api/               # fetch 封装
├── docs/                      # PLAN.md · SAT-MD.md
├── data/                      # gitignore：app.db · *.sat.md · assets/ · exports/
├── scripts/dev.sh             # 一键起前后端
└── .gitignore
```

**依赖取舍**：`sqlite3` 标准库 + 手写 schema（不引 ORM）；HTTP 用 FastAPI 自带；前端不引状态管理库，TanStack Query 级别的复杂度也不需要，用普通 `fetch` + hooks。

## 5. 数据模型（SQLite）

```sql
documents(id, title, source_filename, satmd_path, answers_status,   -- inline|external|none|pending
          question_count, created_at)
questions(id, document_id, ext_id, no, sec, type, difficulty,
          material, stem, options_json,        -- ["A. ...", ...] 恰好4项
          answer, explain, source_ref,         -- answer 可空
          images_json, order_idx)
sessions(id, document_id, started_at, finished_at, mode)            -- 一次练习
session_items(session_id, question_id, no, chosen, is_correct, answered_at)
analyses(id, question_id, session_id, content, created_at, updated_at) -- 用户手写错题分析
vocab(id, word, context, document_id, question_id, meaning,
          ease, interval, due_at, created_at)                        -- 轻量间隔重复
notes(id, document_id, question_id, content, created_at, updated_at) -- question_id 可空=文档笔记
settings(key, value)                                                 -- LLM provider/base_url/model/api_key
llm_logs(id, purpose, provider, model, tokens_in, tokens_out, created_at)
```

## 6. API 草案

```
POST   /api/documents              multipart 上传 → {id, question_count, answers_status}
GET    /api/documents              列表
GET    /api/documents/{id}/questions
PUT    /api/documents/{id}/answers 批量写入答案（答案录入页）
POST   /api/sessions               {document_id, range?} 开始练习
POST   /api/sessions/{id}/submit   判分 → 成绩 + 错题列表
GET/POST/PUT /api/analyses         错题分析（用户手写）
CRUD    /api/vocab                 生词本
CRUD    /api/notes                 笔记
POST   /api/llm/chat               侧边栏讲解（注入题目 + 用户作答 + 正确答案）
GET/PUT /api/settings              LLM 配置（key 只写，GET 返回掩码）
POST   /api/settings/test          测连（GET 供应商 /models，0 token）
POST   /api/export?format=md|csv|json   导出（PDF 走前端打印样式）
```

**实际落地（2026-10-06 批 1–4，与草案的差异以此为准）**：

```
POST   /api/sessions/{id}/regrade            按存储的 chosen 重判分（未提交 409）
PUT    /api/documents/{id}/questions/{qid}/explain   解析手写直存（空串清除）
GET    /api/documents/{id}/words             自由表格（默认 Word|Meaning|Notes）
PUT    /api/documents/{id}/words             校验行列上限后入库
GET    /api/documents/{id}/words/export      openpyxl 生成 .xlsx
GET    /api/documents/{id}/export/{fmt}      md | csv | json（题干+选项+答案+解析）
POST   /api/ai/answer                        AI 解答（context = 题干 + 正确选项）
POST   /api/llm/chat（草案，未实现）          AI 解答走 /api/ai/answer；analyses/vocab/notes CRUD 暂未启用
```

## 7. Bluebook 风格做题页（验收基准）

- 顶部条：`Section 1 · Question N / M` + 计时器
- 主区：`@material` 引用块在上，题干在下，四个选项为**圆角描边按钮 + 左侧字母圆圈**，选中态高亮
- 底部：`Previous` / `Next`、题号答题卡（网格，标记题加旗标）、`Submit`
- 数学题 KaTeX 渲染公式；图片按原始比例展示
- 交卷 → 确认弹窗 → 结果页（分数、逐题对错、错题跳转）

## 8. 分阶段计划

### Phase 0 — 脚手架（半天）
仓库结构、`requirements.txt`、Vite+React+Tailwind、SQLite schema、`/api/health`、`scripts/dev.sh`、`.gitignore`（`data/`、`.idea/`）。
**验收**：两条命令起前后端，页面显示后端健康状态。
**状态**：✅ 完成（2026-10-05）——`dev.sh` 一键起前后端，健康检查与页面均正常。

### Phase 1 — 端到端最小闭环 ⭐ MVP
1. `satmd/parser.py` + 单测（fixture `.sat.md` 覆盖 §8 全部用例）
2. `convert/`：PyMuPDF 文本抽取 → 断行合并 → 选项/题号识别 → 图片抠取 → 生成 `.sat.md` + `assets/`；识别答案区则回填
3. 导入 API + 导入页（上传 → 显示题数 + 答案识别状态）
4. 答案录入页：题号网格逐题输入 **+ 批量粘贴**（`1-A 2-C …`）+ 「稍后再说」
5. 做题页（§7）+ 提交判分 + 结果页
**验收**：一份真实 PDF 从上传到出分全流程可用，**全程 0 token**。
**状态**：✅ 代码完成（2026-10-05）——后端 51 测试全过；`npm run build`（tsc）0 错误；浏览器 E2E 全过（UI 上传 PDF → 键盘答题 → 标记 → 提交弹窗 → 4/5 判分 → 重做），控制台 0 报错；截图核对 5 个页面均符合设计。**待办**：用用户真实 PDF 校准转换器后正式验收。

### Phase 2 — 错题本 + LLM 侧边栏
错题列表/筛选、用户手写分析编辑器；`llm/` provider 层（OpenAI + Anthropic，配置页填 base_url/key/model）；右侧边栏讲解（快捷 prompt：「讲解这题」「为什么 B 不对」）。
**验收**：做错题能写分析、能唤起讲解，两个 provider 都能切换。

### Phase 3 — 生词本 + 笔记
题目文本划词 → 存生词（带原句上下文、关联回题）；生词列表、轻量间隔复习、CSV 导出；题目级 + 文档级 Markdown 笔记。
**验收**：做题时划词入库，隔天复习列表出现到期词。

### Phase 4 — 导出与导入兜底
导出 MD / CSV / JSON、浏览器打印 PDF；导入失败页的 LLM 兜底（按页开关）；可选扩展 DOCX / 手写 MD 导入。
**验收**：任意格式导出可用；一份排版混乱的 PDF 靠兜底成功导入。

### Phase 5 — 打磨
模块划分（Section/Module）、自适应式分段、统计图表、复习计划强化、打包说明（用户本地 `uv/pip` 启动）。

### 批次交付记录（2026-10-06，均未 commit）

| 批 | 内容 | 验证 |
|---|---|---|
| 批1 | `app/llm/` 传输层 + `convert/llm_fallback.py` 混合转换 + `ConvertError` fallback 标记 | pytest +23 |
| 批2 | 全屏开始屏、交卷后补录（`?session=`）、regrade 端点、独立结果页 + 三选一 | pytest +3；E2E run1/run2/run3 |
| 批3 | `ReviewSidebar`（解析直存 / 词汇表 xlsx / AI 解答 context=题干+正确选项）、`word_grids` 表、openpyxl | pytest +9；E2E-3 |
| 批4 | md/csv/json 导出、结果页纯统计面板（分 section、错题 chips 跳题、用时） | pytest +4；E2E-3 |

当前基线：**107 pytest 全过**；`npm run build` 0 错误；E2E `run.mjs` / `run2.mjs` / `run3.mjs` 全过。
E2E 位于 `/tmp/e2e/`（puppeteer-core + 本机 Chrome，不进仓库）；run3 内置本地 mock LLM 服务（:8123）验证 AI 解答全链路。

## 9. 已确认（原未决项）

1. 界面语言：**全英文**（含菜单、设置、错题本）。
2. MVP 导入格式：**PDF + `.sat.md`**。
3. 图表：**位图提取 + 矢量图截图**，不追求 SVG 还原。
4. 推进：**Phase 0→1 连续做完再验收**，通过后进 Phase 2。
