# SATeacher — ROADMAP

> 本地优先的 SAT 刷题工具：**导入 PDF/题库 → 补录答案 → Bluebook 风格全屏练习 → 错题复盘/知识点整理 → 生词本 → PDF/DOCX 导出**。
> 状态快照：**2026-10-07** ｜ `HEAD=c108cfb` ｜ pytest **164 passed** ｜ E2E `run6`（Workspace）全过 ｜ `npm run build` 0 错误。
> **最近交付：批次 A（PDF/DOCX 导出）+ 批次 B（DOCX 导入）+ 批次 C（扫描 PDF / OCR）+ 批次 D（导入流水线骨架）+ 批次 9（Review Workspace 外壳）已落地** —— 见 §1「导出」「导入」「复盘」、§3 M2/M3/M5/M7。
> 相关文档：[`README.md`](README.md) · [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) · [`docs/PLAN.md`](docs/PLAN.md) · [`docs/SAT-MD.md`](docs/SAT-MD.md) · [`docs/RENOVATION_PLAN.md`](docs/RENOVATION_PLAN.md)

---

## 0. 指导原则（不变量）

1. **LLM 不在导入主链路**：导入是确定性转换，**0 token**；AI 只在用户**显式点击**时调用。
2. **本地优先**：数据全部在 `data/`（SQLite 单文件 + 文档/图片），无云依赖。
3. **正确答案不出后端**：练习接口剥离 `answer`；仅提交/复盘返回。
4. **界面全英文**；与维护者交流用中文；有疑问先问、不猜测。
5. **可分发**：别人能直接拿去用，或读完 `README` 就会用（跨平台，不只 macOS）。

---

## 1. 当前已实现（MVP，已完成）

### 导入 / 题库
- ✅ 上传 **PDF**：PyMuPDF 确定性转换（文本/分栏/分块/题号/选项/**答案键回填**/图片抽取）。
- ✅ 上传 **DOCX**：python-docx 抽取段落/表格/内嵌图片（含软换行/VML），复用 PDF 的题号/选项/material-stem/答案键管线；**zip 安全校验**（条目数/解压总量/压缩比/宏）；图片归一化为 PNG 资产。
- ✅ 上传 **`.md` / `.markdown` / `.sat.md`**：确定性解析为 SAT-MD。
- ✅ **扫描 PDF OCR**：页级文本密度检测；低密度页用 **macOS Vision（可选）或系统 `tesseract`**（跨平台、零新增 Python 依赖）栅格化识别，坐标归一化回 PDF 点后复用同一确定性管线；无引擎时给可执行提示。导入页显示 OCR 状态（`/api/health` 的 `ocr`）。
- ✅ **导入流水线**：`import_jobs` 状态机（detect → convert → review → commit/cancel）+ **逐页 `PageReport`**（文本/OCR/低置信/无引擎，含真实置信度）；`POST /api/imports` 系列端点；前端 `ImportPipeline` 阶段条 + 逐页列表、`SatMdTemplate` 模板预览/复制/下载、`LibraryList` 紧凑列表、导入页**拖放**。干净转换自动提交，有疑点进复核（仍 0 token）。
- ✅ **LLM 兜底**：仅当确定性 profile 读不出且已配 API Key 时，逐页打标（verbatim 保真校验 + 重试 1 次）。
- ✅ **内置题库**：`sat2025-rw-b`，**44 个单元**（2025 Aug–Dec，北美 + 亚太），离线、0 token、幂等导入；支持单单元 / 整库导入。
- ✅ 上限与报错：60 MB、空文件、类型不支持（415）；导入告警（图片引用等）。
- ✅ 答案来源状态：`inline` / `external` / `none`。

### 资料库
- ✅ 文档列表（题数、已作答数、是否需要补答案、创建时间）、删除（级联）、练习历史。

### 答案录入
- ✅ 逐题 A–D 网格；**批量粘贴**（`1-A 2-C` / `12B` / 裸字母串）；保存时校验 A–D；同步回写 `doc.sat.md`；预览。

### 练习（Bluebook 风格全屏）
- ✅ 开始屏（全屏）；单题视图；题号导航；计时；标记；上一题/下一题；键盘 A–D / ←→；交卷。
- ✅ 无答案文档：交卷后跳转补录答案再判分；**StrictMode 双启动已修复**。

### 结果 / 复盘（✅ IDE 式工作台已落地，2026-10-07）
- ✅ 汇总（得分、用时、Practice again、Back to library）。
- ✅ **三区固定工作台**：左「题号导航」（过滤 All/Correct/Wrong + 状态色网格，当前题 `aria-current`）、中「题目」唯一滚动区、右「Study Inspector」（**Tab**：Explanation / AI Tutor / Export）。
- ✅ 可拖拽**分隔条**（`role="separator"`、方向键可达、双击复位）+ **布局持久化**（`localStorage` `sateacher.workspace.<docId>`：左右栏宽、底部高、折叠态、当前 Tab）。
- ✅ **底部 Vocabulary Sheet**：全宽、可折叠、可拖高、可最大化（承载词汇表编辑：`Word|Meaning|Notes` 行列增删改 + 保存 + xlsx）。
- ✅ 窄屏（`<1024`）题号与 Inspector 收为**抽屉**；`<640` 单列。
- ✅ **Vocabulary Sheet v2**（2026-10-08）：稳定列/行 ID + 列宽持久化 + 冻结表头 + 排序（asc/desc/无）+ 按列筛选 + 多格粘贴 + 键盘导航；xlsx 导出带列宽/冻结行；**无新依赖**（自研 grid）。
- ✅ **手写解析**（0 token，直存 DB）；**AI 讲解**（显式；无 key 409）；**导出入口**（PDF/DOCX/xlsx）。
- ⚠️ 缺失：AI 结果 "Save as explanation" 来源徽章/时间（M7）。

### 导出（✅ PDF/DOCX 已落地，2026-10-07）
- ✅ 文档导出：**PDF**（WeasyPrint：A4、页脚页码、题号/选项/答案键/解析、内嵌图片与 MathJax SVG 公式）。
- ✅ 文档导出：**DOCX**（python-docx：标题/段落/答案键/解析/词汇表；公式经 cairosvg 转 PNG 内联）。
- ✅ 词汇表导出：**.xlsx**（openpyxl；Numbers 可打开）。
- ✅ 数学公式：**MathJax SVG** 管线；Node/桥接缺失时降级纯文本，导出不崩。
- ⚠️ 旧的 **MD / CSV / JSON 导出已按维护者决定删除**。
- ❌ 尚未含：封面/水印、**>20 题 question index**、从 session 导出的对错标注（后续增量）。

### 设置 / LLM 层
- ✅ Provider 目录（**16 家**，OrcaRouter 优先）+ protocol（openai | anthropic）派生/覆盖 + Base URL + API Key（只写、掩码）+ Model + 连通性测试。
- ✅ 统一 LLM 层：temperature 0、60s 超时、settings 驱动、有类型错误；OpenAI + Anthropic 双传输。

### 工程 / 测试
- ✅ pytest **171**（parser / convert / bluebook / **docx 12 项** / **ocr 9 项** / **导入流水线 13 项** / **迁移 3 项** / builtin / llm base/fallback / api / **export 7 项** / regrade / review / settings / **AI fallback 1 项**）。
- ✅ 浏览器 E2E `run6`（批 9 Workspace：三栏/分隔条持久化/sheet/Inspector/三尺寸）；`run10`（批 10 词汇表 v2）；`npm run build` 类型检查 + 构建。

---

## 2. 已知缺口（尚未实现）

| 领域 | 缺口 |
|---|---|
| 导入 | ~~DOCX 导入~~ **已交付（批次 B）**；~~扫描 PDF OCR 基础版~~ **已交付（批次 C）**；~~导入流水线（逐页状态/报告/取消）~~ **已交付（批次 D）**；~~`.sat.md` 模板预览~~ **已交付（批次 D）**；~~资料库列表化~~ **已交付（批次 D）**；~~选择性 AI 视觉（仅失败页）~~ **已交付（批 11，2026-10-08）** |
| 复盘 | ~~IDE 式工作台（可拖拽分隔条、布局持久化、可折叠底部 Vocabulary Sheet、Inspector 隐藏/重开、Tab 化）~~ **已交付（批次 9）** |
| 词汇表 | ~~列 ID / 列宽 / 排序筛选偏好 / 稳定行 ID、冻结表头、粘贴填充、键盘导航（数据模型 v2）~~ **已交付（批 10，2026-10-08）** |
| AI | ~~上下文扩展（material + 四选项 + 学生作答 + section）~~ **已交付（批 14，2026-10-08）**；解析来源/时间标注；~~CB-style 规范化~~ **已交付（批 12，2026-10-08）** |
| 导出 | ~~PDF / DOCX 正式导出模板~~ **基础版已交付（批 A）**；余：封面/水印/目录、session 对错标注 |
| 工程 | ~~设计系统（token/组件/图标）~~ **已交付（批 7，2026-10-08）**；前端组件测试；跨平台 + README 上手 |

---

## 3. 路线图（Milestones）

> 详细执行见 [`docs/RENOVATION_PLAN.md`](docs/RENOVATION_PLAN.md)（含每批目标/改动文件/风险/回滚/验收）。批次号沿用该计划。

| 里程碑 | 批次 | 目标 | 状态 |
|---|---|---|---|
| **M0 — Core MVP** | 1–6 | 导入(PDF/md)、答案录入、全屏练习、三栏结果、词汇表 xlsx、16 provider 目录（导出后由批 A 升级为 PDF/DOCX） | ✅ 已完成 |
| **M1 — 设计系统基础** | 7 | 设计 token（色/字/间距/圆角/阴影）、组件原语、图标库（lucide）、AppShell；全站去 emoji/去卡片墙 | ✅ **已完成（批 7，2026-10-08）** |
| **M2 — 导入 2.0** | 8 | `import_jobs` 流水线（逐页状态/取消）、**DOCX 导入**、SAT-MD 模板预览、Library 列表重设计 | 🟡 **DOCX 导入已交付（批次 B）**；其余待做 |
| **M3 — 复盘工作台** | 9 | IDE 式固定布局（可拖拽分隔条 + 持久化 + Inspector Tab + 底部 Vocabulary Sheet + 窄屏 drawer） | ✅ **已完成（批次 9，2026-10-07）** |
| **M4 — 词汇表 v2** | 10 | 数据模型迁移（列 ID/宽度/行 ID/视图偏好）+ 电子表格（编辑/粘贴/冻结/排序/筛选）+ xlsx v2 | ✅ 已完成 |
| **M5 — 扫描件 OCR** | 11 | 跨平台 OCR adapter（macOS Vision + 可选 Tesseract）+ 逐页报告 + 仅失败页 AI 兜底 | ✅ **已完成（批 11，2026-10-08）** |
| **M6 — CB-style normalization** | 12 | 显式改写→并排审阅→接受/拒绝（答案不变、material 保留、A-D 完整、温度 0、显式触发） | ✅ **已完成（批 12，2026-10-08）** |
| **M6 — CB 规范化** | 12 | 显式**逐题**改写 → 并排审阅 → 接受/拒绝（答案与出处不变） | ⬜ |
| **M7 — 导出包** | 13 | **PDF（WeasyPrint）+ DOCX（python-docx）** 正式模板 + 数学公式管线（MathJax SVG）；封面/目录为后续增量 | ✅ **已完成（批次 A）** |
| **M8 — AI 升级** | 14 | AI 上下文扩展（material/四选项/学生作答/section）+ 解析来源与时间 + Settings/Export 打磨 + a11y 回归 | ✅ **已完成（批 14，2026-10-08）** |
| **M9 — 质量栈** | 15 | 前端组件测试（vitest + testing-library + jsdom） | ⬜ |
| **M10 — 可分发** | 16 | `README` 重写（三平台安装→运行→首次导入→排错）+ `scripts/setup.*` + 依赖缺失友好降级 | ⬜ |

---

## 4. 已确认的技术决策（2026-10-07）

| 事项 | 决定 |
|---|---|
| PDF/DOCX 工具链 | **WeasyPrint + python-docx**（WeasyPrint 需系统库 pango/cairo/gdk-pixbuf/harfbuzz） |
| DOCX 导入 | 复用 PDF 的题号/选项/material-stem/答案键管线（0 token）；解析前做 **zip 安全校验**（条目数/解压总量/压缩比/宏）；仅内存读图片，不落盘解压 |
| 数学公式（PDF/DOCX） | **已实现 MathJax SVG 管线**（PDF 内联 SVG；DOCX 经 cairosvg 转 PNG；缺失降级纯文本）；原 KaTeX spike 取消 |
| OCR | **已实现（批次 C）**：**不只 macOS**——macOS 用 Vision（`pyobjc-framework-Vision`，可选），其他平台用系统 Tesseract（**子进程直调，零 Python 依赖、不强制安装**）；缺失时给可执行提示，绝不崩溃 |
| 电子表格 | **react-data-grid**（MIT）；若与 React 19 不兼容则**回退自研**（已接受） |
| AI 上下文 | **扩展**为题干 + material + 四选项 + 正确答案 + 学生所选 + section/type，并更新旧测试 |
| token 提示 | 仅**定性**提示"可能消耗 token"，**不显示** token 数/价格 |
| CB 规范化粒度 | **逐题** |
| PDF 目录 | **>20 题自动生成** question index |
| 死表 `analyses/vocab/notes/llm_logs` | **保留占位**，不删 |
| 前端测试栈 | **批准** vitest + testing-library + jsdom |
| 跨平台/README | **硬要求**：别人能直接拿去用，或读完 README 会用 |

---

## 5. 验收与命令

```bash
# 后端测试（临时数据目录，不动 dev 数据）
cd backend && ../.venv/bin/python -m pytest -q          # 基线 164 passed

# 前端类型检查 + 构建
cd frontend && npm run build                            # 0 错误

# 端到端
cd /tmp/e2e && node run.mjs                             # run2/run3/run4 同理

# 本地开发
./scripts/dev.sh                                        # 后端 :8000 + 前端 :5173
```

每次提交前：pathspec 保护 `LICENSE` 与 staged `.idea/`；用 question 工具向维护者确认。

---

## 6. 明确的"暂不做"

- 云同步 / 账号体系 / 多人协作（本地优先，单用户）。
- 错题本 SRS 复习（`vocab` 表预留，未排期）。
- 整卷批量 CB 改写（只做逐题）。
- 学生答题页暴露答案或 AI 内部判断（永不）。