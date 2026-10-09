# SATeacher 改造计划（Review Workspace · Import · Export）

> 状态：`实施中`（2026-10-07 起分批执行，见下方"实施进展"）
> 生成于 2026-10-06 ｜ 基线：`HEAD=abe3a0d`、pytest **121 全过**、`npm run build` 0 错误、E2E `run/run2/run3/run4` 全过
> 配套文档：`docs/PLAN.md`（决策与批次权威记录）、`docs/SAT-MD.md`（格式规范）、`docs/HANDOFF.md`（交接）
> 本文档为调研、设计与执行计划；执行记录见 §10 各批状态与 `docs/PLAN.md`。

> **实施进展（2026-10-07）**
> - **批次 A（即原批 13）已交付：PDF/DOCX 导出**。新增 `backend/app/export/`（`model.py` · `pdf.py` · `docx.py` · `math_render.py` + `mathjax/` Node 桥接）；新增端点 `GET /api/documents/{id}/export/{pdf|docx}`；前端 Export 面板按钮改为 **PDF / DOCX**。
> - **旧的三种导出格式 md/csv/json 按维护者决定删除**（不再保留）。
> - **数学公式改为已落地的 MathJax SVG 管线**（原 KaTeX spike 不再需要）：PDF 内联 SVG；DOCX 经 `cairosvg` 转 PNG 内联；Node/桥接缺失时**降级为纯文本**，导出永不崩溃。
> - 新增后端依赖：`weasyprint` · `python-docx` · `cairosvg`；可选 Node 依赖 `mathjax-full`（装在 `backend/app/export/mathjax/node_modules`，缺失时自动降级）。
> - 测试 `backend/tests/test_export.py` **7 项**（PDF/DOCX 前缀 + 回读内容 + 格式校验 + 数学桥接/容错）；后端 **124 passed**、`npm run build` 0 错误。
>
> **批次 B（DOCX 导入，2026-10-07）**
> - 新增 `backend/app/convert/docx.py`：python-docx 提取段落/表格/内嵌图片（含 `Shift+Enter` 软换行、VML 旧式图片），复用 PDF 的题号/选项/material-stem/答案键管线（0 token）；图片经 PyMuPDF 归一化为 PNG 资产。
> - 接入 `POST /api/documents`（`.docx` 分支）；导入页 `accept` 与文案更新。
> - **安全**：解析前检查 zip 条目数/解压总量/压缩比/宏部件（`vbaProject.bin`）。
> - 测试新增 `test_docx_convert.py` **12 项** + API 导入 1 项；后端 **137 passed**、`npm run build` 0 错误。
> - ⚠️ 原批 8 的其余部分（`import_jobs` 流水线、`.sat.md` 模板预览、Library 列表、拖放）**尚未实现**。
>
> **批次 C（扫描 PDF / OCR，2026-10-07）**
> - 新增 `backend/app/convert/ocr/`：`base.py`（引擎选择 + `OcrLine` 契约）、`vision.py`（macOS Vision，可选 `pyobjc-framework-Vision`）、`tesseract.py`（**子进程直接调用系统 `tesseract` 二进制**，无需 `pytesseract`，跨平台且不强制安装）。
> - `convert/pdf.py` 接入：页级**文本密度检测**（`PAGE_MIN_CHARS`，默认 25）；低密度页栅格化（2.5×）后 OCR，坐标归一化回 PDF 点，复用既有分行/分栏/分题管线；`is_chrome` 过滤页眉页脚。
> - **友好降级**：无引擎时扫描件给出可执行报错（装 Tesseract 或 macOS Vision）；有引擎但读不出文本则回落到原“no text could be extracted”提示。绝不伪造置信度——低置信仅记 warning 提示人工复核。
> - 附带修正：`normalize.option_markers` 现在接受标记后紧跟**数字/`$`/负号**（OCR 常丢空格，如 `(A)3`、`A.13`），仍拒绝 `A.very`/`D-Day`。
> - `/api/health` 增加 `ocr` 字段（可用引擎列表）；导入页据此显示 OCR 状态提示。
> - 测试新增 `test_ocr.py` **9 项**（TSV 解析、无引擎降级、文本 PDF 不触发 OCR、扫描件往返）+ API 扫描件导入/health 2 项；后端 **148 passed**、`npm run build` 0 错误。
> - **未含**（原批 11 的其余部分）：逐页状态/报告 UI、选择性 AI 视觉、`import_jobs`。这些随批 8 流水线一并落地。
>
> **批次 D（导入流水线骨架，2026-10-07）**
> - 新增 `app/imports.py`（统一导入服务：`detect → convert → commit`，**0 token**；PDF/DOCX/SAT-MD 共用一条代码路径）、`app/repos/imports.py`（`import_jobs` 表 CRUD）、`app/api/imports.py`（`POST /api/imports` · `GET` · `POST /{id}/commit` · `POST /{id}/cancel` · `DELETE` · `POST /{id}/ai-fallback` 暂返回 501）。
> - **DB 迁移**：`db.py` 新增 `migrate()`（`PRAGMA table_info` 幂等 ALTER）与 `import_jobs` 表；`documents` 增加 `import_source` / `used_ai` / `report_json`，并在 `init_db()` 中对旧库就地升级。
> - **逐页报告**：`convert/model.py` 新增 `PageReport`（`text | ocr_ok | low_confidence | ocr_unavailable | ocr_failed | empty`）；PDF 确定性管线记录每页来源/真实置信度，DOCX/SAT-MD 记单页。
> - `POST /api/documents` 改为调用同一服务（行为与状态码不变），旧的内联转换助手删除。
> - 前端：`client.ts` 新增 `ImportJob`/`ImportPageReport` 与 `createImport/getImport/commitImport/cancelImport/deleteImport`；新增 `ImportPipeline.tsx`（阶段条 + 逐页状态 + 警告 + Commit/Cancel）、`SatMdTemplate.tsx`（可复制/下载的 `.sat.md` 模板）、`LibraryList.tsx`（紧凑列表取代卡片墙）；`ImportPage.tsx` 加入**拖放投放区**并切换为流水线流程（干净转换自动提交，有疑点进复核）。
> - 测试新增 `test_imports_api.py` **13 项** + `test_migrations.py` **3 项**；后端 **164 passed**、`npm run build` 0 错误。
> - **未含**：真正的异步/分页进度（当前转换为同步执行，POST 即返回结果）、导入取消后的中间态清理策略细化、`ai-fallback` 实体（暂 501）。
>
> **批次 9（Review Workspace 外壳，2026-10-07）**
> - `ResultPage.tsx` 瘦身为「加载数据 + `<Workspace>`」；新增 `frontend/src/components/workspace/`：`Workspace.tsx`（三区编排 + 顶部栏 + 移动端抽屉）、`QuestionNav.tsx`（过滤分段 + 状态色题号网格）、`Inspector.tsx`（**Tab** 而非手风琴：Explanation · AI Tutor · Export）、`VocabularySheet.tsx`（**底部全宽、可折叠/可拖高**的词汇表，迁移原右栏内联编辑表）、`Splitter.tsx`（Pointer Events 可拖 + 方向键可达，`role="separator"`）、`usePersistentLayout.ts`（`localStorage` key `sateacher.workspace.<docId>`）、`useMediaQuery.ts`、`icons.tsx`（**无新依赖**：内联 SVG 图标）。
> - **布局持久化**：右栏宽 · 左栏宽 · 底部高 · 折叠态 · 当前 Tab；分隔条双击复位。
> - **响应式**：`≥1024` 三栏可拖；`<1024` 题号与 Inspector 收为**抽屉**（顶部「☰ Questions」/ Inspector 按钮），底部 sheet 保留。
> - **保留** `ReviewSidebar.tsx` 作为回滚路径（已不再挂载）；`#qindex` / `#qcontent` 锚点保留。
> - 验证：`npm run build` 0 错误；新增 E2E `run6.mjs`（隔离服务器，不碰用户数据）全过——三栏渲染、分隔条拖拽加宽、刷新后持久化、底部 sheet 折叠/展开、Inspector 隐藏/重开、1440/1024/375 三尺寸无横向溢出；后端 **164 passed** 不变。
> - 已知偏差：底部 sheet 目前横跨**中栏**（原计划「左+中」），后续按需调整。

> 已确认的关键技术选择（由维护者拍板）：
> 1. **PDF/DOCX 工具链 = WeasyPrint + python-docx**（WeasyPrint 需系统库：pango/cairo/gdk-pixbuf/harfbuzz）。
> 2. **OCR = macOS Vision（pyobjc-framework-Vision）为主，Tesseract 可选回退**。
> 3. **Vocabulary 表格 = react-data-grid**（先验证 React 19 兼容，不满足则回退自研）。
> 4. **AI Tutor 上下文按新需求扩展**（题干 + material + 四选项 + 正确答案 + 学生所选 + section/type），并**更新**现有 `test_ai_answer_context_is_stem_plus_correct_option`。
> 5. **交付形态 = 写入 `docs/RENOVATION_PLAN.md`**（本文件）。

---

## 1. 执行摘要

SATeacher 现在是"本地优先的 SAT 刷题工具"最小闭环的成熟态：导入（PDF/`.md`/内置题库）→ 补答案 → Bluebook 全屏练习 → 三栏结果页 → 右侧手风琴整理栏（解析 / 词汇表 / AI / 导出）。工程基线扎实（121 pytest、4 套 E2E、StrictMode 修复、内置 44 模块题库），但**四个产品面明显未达到目标形态**：

1. **导入面**：`ImportPage.tsx` 只有一个 `Choose file` 按钮，`accept=".pdf,.md,.markdown"`；无拖放、无 DOCX、无 `.sat.md` 模板预览、无处理流水线、无逐页状态/报告、无结构校验审阅界面；Library 是平铺卡片网格。后端 `documents.py` 只用扩展名判类型（无 MIME 双重检查、无 zip bomb/路径穿越防护），扫描件在 `convert/pdf.py` 直接 `ConvertError(fallback=False)` 失败——**没有任何 OCR**。
2. **复盘面**：`ReviewSidebar.tsx` 是右侧**手风琴四段**（Explanation / Vocabulary / AI / Export），词汇表是嵌在窄右栏里的 `<input>` 表格；这不是目标要求的"IDE 式固定工作台 + 底部 Vocabulary Sheet"。`ResultPage.tsx` 的三栏是正确的起点，但**没有可拖拽分隔条、没有布局持久化、没有可折叠底部表格、没有 Inspector 隐藏后的重开控制**。
3. **词汇表面**：`repos/words.py` 只存 `headers + rows_json`，**不足以**保存列 ID、列宽、排序/筛选偏好、稳定行 ID；无冻结表头、无粘贴、无键盘导航。
4. **导出/AI 面**：导出只有 md/csv/json（`documents.py` 末尾）+ 词汇表 `.xlsx`；**无 PDF/DOCX 正式导出模板**；`api/ai.py` 的上下文被锁死为"题干 + 正确选项"（material/学生作答从不发送，有测试钉死）。

本计划给出**可逐批执行**的改造路线：先做可独立验收的基础设施（设计系统、组件原语、导入流水线骨架、词汇表数据模型迁移），再做体验面（工作台、电子表格、导入页、导出模板），最后做需要新依赖与验证的重活（OCR、PDF/DOCX 生成、CB-style 改写）。**铁律不变**：LLM 不在导入主链路、导入 0 token、AI 仅在用户显式动作时消耗；界面全英文；与维护者交流用中文；每次提交前用 question 工具确认；pathspec 提交保护 `LICENSE` 与 staged `.idea/`。

预期代价：**+3 个后端依赖家族**（WeasyPrint、python-docx、pyobjc-framework-Vision）、**+2 个前端依赖**（lucide-react、react-data-grid）、**+1 套前端测试栈**（vitest + testing-library，用于组件测试）。全部为 MIT/BSD/ISC 许可，无商业授权风险。

**可分发性与跨平台（新增硬要求）**：维护者要求仓库**能被别人直接拿去用，或读完 `README` 就会用**，且**不只 macOS**。因此本计划在体验与后端之外，额外纳入：① `README.md` 重写为完整的"安装 → 运行 → 首次导入 → 模板 → 排错"指南，逐平台说明系统依赖（Python/Node、WeasyPrint 的系统库、可选 Tesseract OCR）；② 提供 `scripts/setup.sh`（macOS/Linux）与尽力而为的 `scripts/setup.ps1`（Windows）；③ 依赖缺失时的**友好降级**（无 WeasyPrint → PDF 导出禁用并给出安装指引；无 OCR → 扫描件给出替代路径），绝不让未装可选依赖的用户卡死。对应新增 **批 16**。

---

## 2. 已核实的现状与差距

> 分类记号：**[实现·体验不足]** = 功能存在但达不到目标形态；**[未实现]** = 完全没有。

### 2.1 前端

| 文件 | 当前行为（代码证据） | 差距分类 |
|---|---|---|
| `frontend/src/pages/ImportPage.tsx` | 单按钮 `<label>Choose file</label>` + 隐藏 `<input accept=".pdf,.md,.markdown">`（:104–114）；`onFile` 单文件（:45–60）；成功卡显示题数/答案状态/warnings（:118–154）；`BuiltinBankCard` 题库区（:156–162）；Library = `grid sm:grid-cols-2` 卡片墙（:170–209）。顶部用 emoji `⚙ Settings`（:88）。 | **[实现·体验不足]**：无拖放、无键盘可达的大投放区、无 `.docx`/`.sat.md` template、无 pipeline 进度、无逐页报告、Library 无层次。 |
| `frontend/src/pages/PracticePage.tsx` | 全屏开始屏（`Begin — enter fullscreen`，:187–192）→ 单题 + 题号 palette + 计时 + Submit 弹窗（:214–390）；键盘 A–D/←→（:139–157）；StrictMode startSession 双守卫（:43–69，正确）。 | **[实现·体验不足·仅小修]**：44px 触控、focus ring、`prefers-reduced-motion`、emoji `⚑`（:275）需替换，但**不得重做成 Apple 风格**。 |
| `frontend/src/pages/ResultPage.tsx` | 三栏 master–detail：`#qindex`（:297–345）/ `#qcontent`（:347–467）/ `ReviewSidebar` sticky（:470–488）；统计面板（:208–262）；三选一 tab（:277–293）；`panelOpen` 开关（:45,198–203）；右栏包装 `lg:sticky lg:top-4 lg:w-auto`（:471）。 | **[实现·体验不足]**：无分隔条拖拽、无布局持久化、无底部 Vocabulary Sheet、无 Inspector 重开、无题号 drawer。 |
| `frontend/src/components/ReviewSidebar.tsx` | 手风琴 `SectionToggle`（:17–36）；Explanation textarea + Save（:214–253）；Vocabulary 是窄栏 `<input>` 表格（:262–379）；AI 面板文案 "Context: this question + its correct answer only."（:395）；Export 只有 md/csv/json 链接（:432–443）。emoji `▾/▸/«/✕`。 | **[实现·体验不足]**：应升级为右侧固定 Study Inspector（Tab）；词汇表要移到底部全宽 sheet。 |
| `frontend/src/pages/SettingsPage.tsx` | 目录驱动 provider `<select>`（:151–163）；BaseURL/Key/Model；`Test connection`；`← Library` 是 `text-blue-700 underline` 小链接（:121）。input 类固定字符串（:115–117）。 | **[实现·体验不足]**：视觉原始、无分组卡片、无内联 focus ring 一致性。 |
| `frontend/src/pages/AnswerKeyPage.tsx` | 题目网格 A–D 按钮 + 批量粘贴 `parseBulk`（:12–25,70–90）；Preview（:235–241）。 | **[实现·体验不足]**：功能完整，视觉纳入设计系统统一即可。 |
| `frontend/src/api/client.ts` | 类型化 client；无 DOCX/OCR/PDF/DOCX 导出/normalize/import-job 端点。 | **[未实现]**：见 §7 合同。 |
| `frontend/src/index.css` | 仅 `@import "tailwindcss"` + `body { font-family: "Helvetica Neue", Arial, "Segoe UI", sans-serif }`（:1–10）。 | **[未实现]**：无设计 token。 |
| `frontend/src/App.tsx` | 5 条路由：`/`、`/doc/:id/answers`、`/doc/:id/practice`、`/session/:sid/result`、`/settings`。 | **[实现]**：路由结构可作为新 IA 的骨架。 |
| `frontend/src/components/RichText.tsx` | `react-markdown + remark-math + rehype-katex`，图片走 `api.assetUrl`。 | **[实现]**：可复用为工作台题面渲染器。 |

### 2.2 后端

| 文件 | 当前行为（代码证据） | 差距分类 |
|---|---|---|
| `backend/app/api/documents.py` | 导入仅 `lower.endswith(".pdf")` / `.md/.markdown/.sat.md`（:100–109）；`MAX_UPLOAD = 60MB`（:28）；上传暂存 `UPLOAD_TMP/<uuid>-<name>` 后 `finally unlink`（:56–65）；无 MIME 校验、无 zip bomb 防护、无 DOCX。导出 `md|csv/json`（:342–375）+ 词汇表 `.xlsx`（:226–255）。 | **[部分未实现]**。 |
| `backend/app/convert/pdf.py` | PyMuPDF 确定性 profile（含 Bluebook 双栏 `bluebook.py`）；扫描件 0 文本 → `ConvertError(fallback=False)`（:124–131,168）；非 fatal 走 `llm_fallback`（:100–110）。 | **[实现·体验不足]**：无 OCR 分支。 |
| `backend/app/convert/llm_fallback.py` | 逐 chunk 打标 + verbatim fidelity 校验 + 重试 1 次（:56–67,183–224）。 | **[实现]**：可作为"失败页/失败题块"AI 兜底的基础。 |
| `backend/app/satmd/parser.py` | 严格状态机；`Question` 无 explain 来源字段；`set_answer` 保留其余内容。 | **[实现·体验不足]**：需加解析来源/时间（见 §7）。 |
| `backend/app/repos/words.py` | `headers`（1–12 列）+ `rows_json`（≤500 行，每格 ≤2000 字符）；无列 ID/宽度/排序/筛选/行 ID。 | **[实现·体验不足]**：数据模型需向后兼容升级。 |
| `backend/app/api/ai.py` | `SYSTEM` = SAT tutor；user = `Question:\n{stem}\n\nCorrect answer: {answer}. {option}`（:56–61）——**仅题干+正确选项**。 | **[实现·体验不足·需按新需求扩展]**。 |
| `frontend/src/api/client.ts::AppSettings` / `backend/app/api/settings.py` | provider 目录（16 家，OrcaRouter 第一）、protocol 派生/覆盖、probe WYSIWYG。 | **[已实现]**：LLM 配置继续复用，API Key 永不回前端。 |
| `backend/app/db.py` | SCHEMA 含 `analyses`/`vocab`/`notes`/`llm_logs` 四张**从未被使用**的表（:79–129）；迁移只有 `init_db()` 里针对 `builtin_key` 的 ad-hoc `ALTER`（:158–165）。 | **[未实现]**：无通用迁移机制；死表需清理或明确保留。 |
| `backend/app/convert/pdf.py` / `convert/` 目录 | 无 `docx.py`、无 `ocr/`、无 `export/`。 | **[未实现]**：DOCX、OCR、PDF/DOCX 导出。 |
| `backend/tests/` | 14 个测试文件、121 用例；`conftest.py` 用 `SATEACHER_DATA=tempdir` 隔离 + session 级共享 `client`（settings 全局 KV 需每用例清理，见 `test_settings_api.py` 的 autouse `clean_settings`）。 | **[实现]**：新功能须补测试，且不得破坏现有 121。 |

### 2.3 差距总表（按改造范围 A–G 对照）

| 范围 | 状态 | 关键证据 |
|---|---|---|
| A 全新 UI 方案 | **完全未实现** | 无 token、无组件层、emoji 当图标、`index.css` 仅 10 行 |
| B IDE 式复盘工作台 | **部分**（三栏存在，无分隔条/sheet/持久化） | `ResultPage.tsx` + `ReviewSidebar.tsx` |
| C Numbers/Excel 词汇表 | **部分**（基础 input 表） | `repos/words.py`、`ReviewSidebar.tsx:262–379` |
| D 导入与 SAT-MD preview | **部分**（仅 pdf/md，无拖放/docx/template/pipeline） | `ImportPage.tsx`、`documents.py:90–130` |
| E 扫描 PDF / OCR | **完全未实现** | `convert/pdf.py:168` fatal 失败 |
| F PDF/DOCX 导出 | **完全未实现** | `documents.py:342–375` 仅 md/csv/json |
| G AI Tutor 与解析数据 | **部分**（stem+正确选项，无来源标注） | `api/ai.py:56–67`、`db.py` questions 表 |

---

## 3. 产品信息架构与用户流程

### 3.1 信息架构（IA）

```
SATeacher
├── Library（/）                        资料库主页：紧凑有层次的文档列表 + 导入入口
│   ├─ Import dropzone（大面积拖放/键盘）
│   ├─ SAT-MD template preview（零 token，可 Copy）
│   ├─ Built-in banks（44 模块）
│   └─ Documents list（Row 列表，非卡片墙）
├── Import Pipeline（模态 / 独立路由 /import/:jobId）
│   ├─ Detect → Processing（逐页状态）
│   ├─ Review（可修复错误 / 结构校验）
│   └─ Done → Enter answers / Start practice / Review SAT-MD
├── Answer key  /doc/:id/answers
├── Practice     /doc/:id/practice    ← 全屏 Bluebook（保护）
├── Result Review Workspace  /session/:sid/result
│   ├── Left: Question navigator + Question pane
│   ├── Right: Study Inspector (Tabs: Explanation · AI Tutor · Export)
│   └── Bottom: Vocabulary Sheet (collapsible/maximizable)
├── Library/doc detail?（可选，doc meta + conversion report）
└── Settings  /settings
```

### 3.2 用户流程

1. **导入流程**：拖放/选择文件 → 检测类型 → 处理流水线（逐页状态）→ 结构化结果（题数/答案状态/图片/警告/是否用 AI）→ 有疑点进审阅 → 完成后 `Enter answers` / `Start practice` / `Review imported SAT-MD`。
2. **补答案流程**（不变）：无答案 → 答案录入页（网格 + 批量粘贴）→ 保存 → 直接做/判分。
3. **练习流程**（保护）：开始屏 → 全屏做题 → 交卷 → 有键直接结果 / 无键补录后结果。
4. **复盘流程**（重构重点）：结果页加载 → 左侧题号导航（状态色）→ 中间单题（材料/题干/选项/学生作答/正确项/←→）→ 右侧 Inspector（解析 Tab / AI Tab / Export Tab）→ 底部 Vocabulary Sheet（可展开/折叠/最大化，保存状态可见）。
5. **导出流程**：Inspector → Export Tab → 选格式（**PDF / DOCX**）→ 可选"包含我已保存的解析"→ 生成下载；词汇表 → `.xlsx`。

---

## 4. 设计系统

> 目标气质：Apple 生产力软件的克制、清爽、精致、稳定。**系统字体优先、留白、清晰层级、细腻分隔线、浅灰工作台背景、低饱和蓝交互强调**。禁止：拟物、玻璃拟态、渐变堆叠、过度圆角、巨型卡片墙、装饰性 AI 味。**不用 emoji 当图标**。

### 4.1 色彩 token（Tailwind v4 `@theme` / CSS 变量）

在 `frontend/src/index.css` 用 `@theme` 定义，全部以语义命名（禁止组件里写 `slate-*`）：

```
/* 工作台与表面 */
--color-canvas:        #f5f5f7;   /* 浅灰工作台底 */
--color-surface:       #ffffff;   /* 面板 */
--color-surface-sunken:#fafafa;   /* 内嵌区（passage/代码） */
--color-overlay:       rgba(0,0,0,.40);
/* 描边与分隔 */
--color-border:        #d2d2d7;
--color-border-subtle: #e8e8ed;   /* 1px 细分隔线 */
/* 文本 */
--color-text:          #1d1d1f;
--color-text-secondary:#6e6e73;
--color-text-tertiary: #86868b;
--color-text-inverse:  #ffffff;
/* 交互强调（低饱和蓝） */
--color-accent:        #0071e3;
--color-accent-hover:  #0077ed;
--color-accent-press:  #006edb;
--color-accent-subtle: #e8f1fd;   /* 选中底 */
--color-focus-ring:    rgba(0,113,227,.35);
/* 语义 */
--color-success:       #1d8a3f;  --color-success-subtle:#e7f6ec; --color-success-border:#b7e0c4;
--color-danger:        #c72c1f;  --color-danger-subtle: #fdecea; --color-danger-border:#f3c2bd;
--color-warning:       #8a5200;  --color-warning-subtle:#fff4e0; --color-warning-border:#f0d3a0;
```

**考试页（Practice）保持中性蓝灰**：`#0f172a` 系（现 `slate`）不动，避免影响全屏体验。

对比度要求：正文 `--color-text` on `--color-surface` ≥ 4.5:1；`--color-text-secondary` 用于辅助文字，若用于正文需 ≥ 4.5:1（`#6e6e73` on `#fff` ≈ 4.6:1，达标）。

### 4.2 字体与字号层级

- 字体族：`-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", Roboto, Helvetica, Arial, sans-serif`（**去掉 "Helvetica Neue" 优先**，改系统 UI 字体）。
- 等宽（计时/题号/公式源）：`ui-monospace, "SF Mono", SFMono-Regular, Menlo, monospace`。
- 层级：

| 级别 | 字号/行高 | 字重 | 用途 |
|---|---|---|---|
| Display | 32 / 40 | 600 | 页面主标题 |
| Title | 24 / 32 | 600 | 区块标题 |
| Heading | 20 / 28 | 600 | 面板标题 |
| Subhead | 17 / 24 | 590 | 卡片/列表主行 |
| Body | 15 / 22 | 400 | 正文 |
| Small | 13 / 18 | 400 | 辅助 |
| Caption | 12 / 16 | 500 | 标签/元信息 |
| Mono | 13 / 18 | 400 | 计时/编号 |

### 4.3 间距、圆角、阴影、边框 token

- 间距基数 4px：`4 · 8 · 12 · 16 · 24 · 32 · 48 · 64`。
- 圆角：`--radius-sm:6px · --radius-md:8px · --radius-lg:12px · --radius-pill:999px`。**默认 8px**；不再满屏 `rounded-xl`。
- 阴影：`--shadow-sm:0 1px 2px rgba(0,0,0,.06)`；`--shadow-md:0 4px 12px rgba(0,0,0,.08)`；`--shadow-pop:0 10px 30px rgba(0,0,0,.12)`。面板默认无阴影，浮层才用。
- 边框：默认 `1px var(--color-border)`；面板内用 `--color-border-subtle`；focus 用 `0 0 0 3px var(--color-focus-ring)`。
- 触控目标：所有可点元素**至少 44×44 px**（图标按钮用 `min-h-11 min-w-11`）。

### 4.4 组件统一规则（`@layer components`）

| 组件 | 变体 | 规则 |
|---|---|---|
| Button | `primary` / `secondary` / `quiet` / `danger` / `icon` | 高 44px（`h-11`）；padding 0 16px；圆角 8px；transition 150ms；`:focus-visible` 显示 focus ring；disabled opacity .4 + `cursor-not-allowed`；loading 时保留宽度并显示 spinner。 |
| Input / Select / Textarea | default / error | 高 44px；边框 1px `--color-border`；focus ring；placeholder `--color-text-tertiary`；error 边框 `--color-danger-border` + 下方文案。 |
| Tabs | underline（Inspector/页签）/ segmented（过滤） | `role="tablist"`，`aria-selected`，键盘 ←→/Home/End；下划线 2px `--color-accent`；segmented 用 pill 底。 |
| Badge/Tag | neutral / success / danger / warning / accent | 12px、圆角 pill、subtle 底 + 深色文字；不用 emoji，用 16px 图标 + 文字。 |
| Empty state | — | 图标（48px，`--color-text-tertiary`）+ 一句说明 + 一个主按钮；居中、留白 ≥ 32px。 |
| Error state | inline banner / field | banner：`--color-danger-subtle` 底 + `--color-danger-border` 边 + 图标 + 文本；不靠颜色单独传意（含图标/文案）。 |
| Loading | skeleton / inline spinner / top progress | 列表用 skeleton（`--color-border-subtle` 脉冲，`prefers-reduced-motion` 时静止）；按钮内联 spinner；长任务用顶栏进度。 |
| Divider | — | 1px `--color-border-subtle`；横向 `border-t`，纵向 `border-l`。 |
| Toast | info/success/danger | 右下、`--shadow-pop`、3.5s 自动消失、可 Esc 关闭。 |
| Dialog / Popover / Drawer | — | 焦点陷阱、Esc 关闭、`aria-modal`；Drawer 用于窄屏题号导航。 |

### 4.5 图标库

- **推荐 `lucide-react`（ISC，tree-shakeable，24px stroke 一致，React 19 兼容）**。替代：`@heroicons/react`（MIT）。
- 替换映射：`⚙ Settings → Settings/SlidersHorizontal`；`⚑ Marked → Flag`；`✓/✗ → Check/X`；`– → Minus`；`« / » → PanelRightClose/PanelRightOpen`；`▾/▸ → ChevronDown/ChevronRight`；`←/→ → ArrowLeft/ArrowRight`；`✕ → X`；`↓ → Download`；`＋ → Plus`；`⚡ AI → Sparkles`。

### 4.6 响应式断点与布局降级

断点（Tailwind 默认 + 2xl）：`sm 640 · md 768 · lg 1024 · xl 1280 · 2xl 1440`。

| 宽度 | Result Workspace | Import/Library | Settings |
|---|---|---|---|
| ≥1280 | 左导航 + 中题目 + 右 Inspector + 底部 Sheet，均可拖拽 | 投放区大、模板预览并排 | 两列（表单 + 说明） |
| 1024–1279 | 同上，Inspector 默认宽 320px，底部 sheet 默认折叠 | 单列 | 单列 |
| 768–1023 | 题号导航收进 drawer；Inspector 变为**底部 Tab 面板**（Explanation/AI/Export）；Vocabulary 作为其中一个底部 tab 或独立 sheet | 单列 | 单列 |
| <640 | 单列：题干优先，底部 tab（解析/生词/AI/导出）；题号 drawer；表格横向滚动 + 冻结首列/表头 | 单列、投放区全宽 | 单列 |

**滚动归属规则（避免嵌套滚动/flex 塌陷/sticky 裁切）**：
- Workspace 根 `h-[calc(100vh-…)] overflow-hidden`，**三栏各自内部滚动**（`min-h-0 overflow-y-auto`），页面本身不滚动。
- 左题号栏：`overflow-y-auto` + `min-h-0`；不要 `sticky`（父容器已是固定高度，sticky 会被裁切）。
- 中题内容：唯一的主滚动区，`overflow-y-auto min-h-0 flex-1`。
- 右 Inspector：`overflow-y-auto min-h-0`，宽度用 state（非 `w-auto`），避免 flex 挤 0 宽（现有教训见 `ResultPage.tsx:471` 与 `HANDOFF.md §6`）。
- 底部 sheet：`shrink-0`，自身 `overflow-auto`；折叠后高度固定为工具栏 44px。
- 分隔条：`role="separator"` + `aria-orientation`，键盘 ←→/↑↓ 调整，`touch-action:none`。

### 4.7 需要系统性替换的现有 Tailwind 模式

| 现有模式 | 出现位置（证据） | 替换为 |
|---|---|---|
| `rounded-xl border bg-white p-6 shadow-sm` 卡片墙 | `ImportPage.tsx:98,172`、`ResultPage.tsx:170,205,208,262,300,347,353,464`、`SettingsPage.tsx:146` | token 面板 `.panel`（`border-subtle` + `radius-md`，去 `shadow-sm`） |
| emoji 当图标 | `ImportPage.tsx:88`、`PracticePage.tsx:275`、`ReviewSidebar.tsx:32,202,291,327`、`ResultPage.tsx:369–373` | lucide 图标组件 |
| `text-blue-700 underline` 小返回链接 | `SettingsPage.tsx:121`、`ResultPage.tsx:116,165`、`AnswerKeyPage.tsx:132`、`PracticePage.tsx:165` | `.btn-quiet` 胶囊（≥44px、hover/focus/disabled） |
| `focus:outline-none` + 仅 `focus:border-blue-500` | `SettingsPage.tsx:116`、`ReviewSidebar.tsx:229`、各处 input | 统一 `.focus-ring`（`focus-visible` 3px ring） |
| 原始 `bg-slate-*`/`text-slate-*` 混用 | 全前端 | 语义 token |
| `font-family: "Helvetica Neue"…` | `index.css:9` | 系统字体栈 |
| 无 `prefers-reduced-motion` | 全前端（`transition` 散落） | 组件默认 150–300ms + 全局 `@media (prefers-reduced-motion: reduce)` 关闭动画 |
| 小按钮 `px-2 py-1`（<44px） | `ReviewSidebar.tsx:200,288,322`、`ResultPage.tsx:386,398` | `min-h-11 min-w-11` 图标按钮 |

---

## 5. 三种尺寸下的 ASCII wireframe

### 5.1 1440px 结果工作台

```
┌───────────────────────────────────────────────────────────────────────────────────────────────┐
│  SATeacher · 2025 August North America — Harder A          [Practice again] [Library] [⚙]      │  top bar h=56
├──────────────┬──────────────────────────────────────────────────────────┬─────────────────────┤
│ QUESTION NAV │  QUESTION PANE (main scroll)                              │ STUDY INSPECTOR     │
│ (scroll)     │                                                          │ [Explanation|AI|Export]
│ 27 questions │  Q12 · Reading & Writing · p.7            [← 12/27 →]     │ ─────────────────── │
│ ┌──┬──┬──┐   │ ┌──────────────────────────────────────────────────────┐ │ Explanation         │
│ │1 │2 │3 │✓  │ │ Material / passage (RichText, images, KaTeX)         │ │ ┌─────────────────┐ │
│ ├──┼──┼──┤   │ └──────────────────────────────────────────────────────┘ │ │ textarea        │ │
│ │4 │5 │6 │✗  │ Stem (RichText)                                          │ │                 │ │
│ ├──┼──┼──┤   │ (A) ...                                                  │ │                 │ │
│ │7 │8 │9 │–  │ (B) ...  [your answer]                                   │ └─────────────────┘ │
│ └──┴──┴──┘   │ (C) ...  [correct]                                       │ [Save] source: human│
│              │ (D) ...                                                  │ updated 2m ago      │
│              │                                                          │                     │
│              │                                                          │ (scroll)            │
├──────────────┴══════════════════════ ▲ splitter (drag) ═══════════════════════════════════════┤
│ VOCABULARY SHEET   Word | Meaning | Notes | +col        [filter ____] [Sort ▾] [⤢] [▁ collapse]│
│ ┌────┬──────┬───────────────────────┬──────────┐                                              │
│ │ #  │ Word │ Meaning               │ Notes    │  (frozen header, resizable cols, paste)      │
│ ├────┼──────┼───────────────────────┼──────────┤                                              │
│ │ 1  │ elate│ make happy            │ verb     │                                              │
│ │ 2  │ ...  │ ...                   │ ...      │                                              │
│ └────┴──────┴───────────────────────┴──────────┘   Saved ✓   [Save] [Export .xlsx]            │
└───────────────────────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 1024px 窄桌面

```
┌───────────────────────────────────────────────────────────────────────────┐
│ SATeacher · Harder A                        [Practice] [Library] [⚙]      │
├───────────────────────────────┬───────────────────────────────────────────┤
│ QUESTION PANE (main scroll)   │ STUDY INSPECTOR (narrower, scroll)        │
│ Q12 · R&W            12 / 27  │ [Explanation] [AI Tutor] [Export]         │
│ ┌─ passage (scroll) ────────┐ │ ───────────────────────────────────────── │
│ └───────────────────────────┘ │ textarea                                  │
│ Stem ...                      │ [Save]  unsaved changes                   │
│ (A) ... (B) ...               │                                           │
│ (C) ... (D) ...               │                                           │
│                               │                                           │
│ [☰ Questions]  ← drawer btn   │                                           │
├═══════════════════════════════╧═══════════════════════════════════════════┤
│ VOCABULARY SHEET (collapsed toolbar)  12 words · Saved ✓   [⤢] [▲ expand] │
└───────────────────────────────────────────────────────────────────────────┘
```

### 5.3 移动端（375px）

```
┌─────────────────────────────┐
│ ‹ Library   Q12/27    [⋯]   │  top bar (sticky)
├─────────────────────────────┤
│ [Questions ▾]  [Filter ▾]   │  collapsible controls
│ ┌ passage (collapsible) ──┐ │
│ └─────────────────────────┘ │
│ Stem (RichText)             │
│ ┌ (A) ... ──────────────┐   │  full-width option rows
│ ├ (B) ... [your answer]─┤   │
│ ├ (C) ... [correct] ────┤   │
│ └ (D) ... ──────────────┘   │
│                             │  (main scroll)
├─────────────────────────────┤
│ [Explanation][AI][Export][Voc] ← bottom tab bar (sticky)
│  textarea / AI panel / ...  │  active panel, own scroll
└─────────────────────────────┘
```

关键：移动端**不伪装桌面 spreadsheet**——词汇表用横向滚动 + 冻结首列/表头，或简化为"一行一记录"编辑卡。

---

## 6. 逐页 UI 规格

### 6.1 Import / Library（`ImportPage.tsx` 重构）

**Import area**
- 大面积投放区 `.dropzone`：`role="button"` + `tabIndex=0`，键盘 Enter/Space 打开文件选择；拖拽 `dragover/drop` 高亮；`aria-describedby` 关联说明。
- 显式列出：接受 `.sat.md · .md · .markdown · .pdf · .docx`；单文件上限 60MB；**"PDF/Markdown/DOCX 转换 0 token；仅在你点击时才用 AI"**。
- 文件检测后 → 内嵌 **Pipeline**（§8 状态机）：阶段条（Detect → Convert → Validate → Commit），逐页状态列表，警告，是否用过 AI。
- 有疑点 → 大按钮 `Review issues` → 审阅界面（可修可编辑）。
- 完成 → 结果卡（题数、答案状态、图片数、warnings、`used_ai`）+ 主行动按钮：`Enter answers` / `Start practice` / `Review imported SAT-MD`。

**SAT-MD template preview**（0 token）
- 一个默认折叠的 `.panel`：`SAT-MD template` + `Copy template` 按钮。
- 内容为完整可复制示例：front matter、阅读题（含 `@material`/@stem）、数学题（`$...$`）、四个选项、`! answer:`、`! explain:`、公式、图片引用 `![figure](assets/...)`。
- 文案：**"A .sat.md that matches this template imports directly, with no API credit. This template is for use in your own tools."** 不承诺网页 AI 能任意转换。
- **必须与 `docs/SAT-MD.md` / `satmd/parser.py` 同步**：把示例纳入后端测试（`parse(TEMPLATE)` 必须成功），防止示例不可导入（见 §11）。

**Library**
- 从卡片墙改为**紧凑有层次的列表**：每行 = 标题、来源文件、题数、答案进度条、状态 tag（`Needs answers` / `Ready` / `Built-in`）、行尾操作（Practice / Answers / ··· 菜单含 Delete）。
- 顶部：搜索框 + 排序（最近/标题/题数）+ 过滤（All / Needs answers / Built-in）。
- 空状态：图标 + "Nothing imported yet" + 指向导入区。
- 题库卡 `BuiltinBankCard` 视觉纳入设计系统（保留其行为与 E2E 选择器）。

### 6.2 Practice（仅保护与小修，`PracticePage.tsx`）

- **不改**全屏结构、计时、交卷分流、键盘 A–D/←→、题号 palette、StrictMode 守卫（`startedFor`/`aliveRef`）。
- 仅：emoji `⚑` → `Flag` 图标；所有可点元素 ≥44px；统一 focus ring；`prefers-reduced-motion` 下关闭 transition；按钮/选项对比度达标。
- 保留 E2E 等待文案 `/ready to begin/i`（Tailwind uppercase 影响，见 `HANDOFF.md §6`）。

### 6.3 Result Review Workspace（重构核心，`ResultPage.tsx` + `ReviewSidebar.tsx`）

**结构**：`TopBar` + 三区 + 底部 sheet；分隔条可拖；布局（右栏宽、底部高、折叠态、当前 Tab）持久化到 `localStorage` key `sateacher.workspace.<docId>`。

**Left — Question nav**
- 题号网格（状态色：correct 绿 / wrong 红 / ungated 灰）；当前题 `aria-current`；搜索/过滤（All/Correct/Wrong）；`<1024px` 收起为 `Drawer`（`☰ Questions`）；键盘 ↑↓ 移动。

**Middle — Question pane**
- 题头：`Q{no} · {section} · {source}` + `← n/total →`。
- Material（RichText）+ Stem（RichText）+ 四选项：正确项 `[correct]`、学生项 `[your answer]`；**绝不在此暴露 AI 内部判断**。
- 无答案键 → 提示补录。
- 每题 `key` 确保切换重置。

**Right — Study Inspector（Tab，非手风琴）**
- **Explanation**：可编辑 textarea + `Save`；显示来源徽章（`human` / `ai`）+ 更新时间；未保存时警示"unsaved changes"；AI 结果可"Save as explanation"（写入 `explain` 且 `source=ai`）。
- **AI Tutor**：显式 `Explain with AI` / `Regenerate`；请求前显示将发送的上下文范围（material / 四选项 / 学生作答 / section）与"会使用已配置模型，可能消耗 token"；**不显示 token 数或价格预估**（已确认）；加载/失败/未配置三态；失败可重试；输出区可编辑并保存。
- **Export**：格式选择（**PDF / DOCX**）；"Include my saved explanations"（默认勾选，未保存草稿永不进入）；生成下载；词汇表 `.xlsx` 入口。
- Inspector 可隐藏；重开控制常驻、≥44px（`PanelRightOpen`）。

**Bottom — Vocabulary Sheet**
- 全宽、横跨左+中；可折叠/展开/最大化；折叠后保留工具栏（词数 + 保存状态 + 展开按钮）。
- 折叠与高度持久化。

**滚动归属**：见 §4.6。

### 6.4 Settings（`SettingsPage.tsx` 重设计）

- 分组卡片：`Provider`（目录下拉 + 协议说明 + note）、`Connection`（Base URL / API Key / Model / Test）、`About`（版本、数据目录）。
- 保留全部现有行为：目录驱动下拉、切 provider 的 Base URL 替换规则、网关默认模型、Key 只读掩码、probe WYSIWYG（`settings.py:114–169`）。
- 视觉：token 化、`← Library` 改胶囊按钮、focus ring、内联校验、`Test connection` 结果用 Toast/inline banner。

### 6.5 Export flow（Inspector 内 + 词汇表）

- 统一 `ExportPanel`：格式单选 + 选项 + 生成按钮 + 进度/结果；词汇表单独 `Export .xlsx`。
- 提供"此导出不消耗 token"的明示（AI 生成内容若已保存，included 标注来源）。

---

## 7. 数据模型、数据库迁移与 API 合同

### 7.1 新字段与迁移策略

**迁移机制**：新增 `backend/app/db.py::migrations()`——按 `PRAGMA user_version` 顺序执行幂等迁移（替代散落 ad-hoc `ALTER`），保留对老库的向后兼容。现有 `builtin_key` 逻辑纳入 `migration 1`。

**`questions` 增列**（解析来源/时间）：
```sql
ALTER TABLE questions ADD COLUMN explain_source TEXT;        -- human | ai | NULL
ALTER TABLE questions ADD COLUMN explain_updated_at TEXT;    -- ISO8601
```

**`documents` 增列**（导入溯源/报告）：
```sql
ALTER TABLE documents ADD COLUMN import_source TEXT;         -- pdf | satmd | docx | ocr | builtin
ALTER TABLE documents ADD COLUMN used_ai INTEGER NOT NULL DEFAULT 0;
ALTER TABLE documents ADD COLUMN report_json TEXT;           -- 逐页状态/警告/用 AI 的页
```

**新表 `import_jobs`**（长任务流水线，支撑逐页状态/取消/选择性 AI）：
```sql
CREATE TABLE IF NOT EXISTS import_jobs (
  id TEXT PRIMARY KEY,                 -- uuid
  filename TEXT NOT NULL,
  status TEXT NOT NULL,               -- detecting|converting|review|committing|done|failed|cancelled
  stage TEXT NOT NULL,
  kind TEXT,                          -- satmd|markdown|pdf_text|pdf_scan|docx
  pages_total INTEGER NOT NULL DEFAULT 0,
  pages_done  INTEGER NOT NULL DEFAULT 0,
  used_ai INTEGER NOT NULL DEFAULT 0,
  report_json TEXT,                   -- [{page,status,source,confidence,reason}]
  document_id INTEGER,
  error TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

**`word_grids` v2（向后兼容）**：保留 `headers`（名称数组）与 `rows_json`（二维值数组）为**权威表格内容**；新增偏好列：
```sql
ALTER TABLE word_grids ADD COLUMN column_ids_json   TEXT;  -- ["c1","c2",...] 稳定列 ID
ALTER TABLE word_grids ADD COLUMN column_widths_json TEXT; -- [120, 220, ...] px
ALTER TABLE word_grids ADD COLUMN row_ids_json      TEXT;  -- ["r-<uuid>", ...] 稳定行 ID
ALTER TABLE word_grids ADD COLUMN view_json         TEXT;  -- {sort:{colId,dir}, filters:[...], frozen:int, version:2}
```
读取时惰性升级：缺 `column_ids_json` 则按位置生成 `c1..cn` 并回写；`row_ids_json` 缺失则按索引生成并回写。**不破坏已有词汇数据**（现有 `GET` 返回结构保持可用，新客户端读 v2 字段，老数据读时补齐）。

**死表**：`analyses`/`vocab`/`notes`/`llm_logs` 目前无代码引用。计划**保留表结构但标注为 reserved**（不删，避免破坏既有库），或纳入未来错题本/生词复习阶段；本计划不依赖它们。

### 7.2 API 合同（请求/响应示例）

**导入流水线**
```http
POST /api/imports                       # multipart file
→ 202 {"job_id":"j_...", "status":"detecting", "kind":null}

GET /api/imports/{job_id}
→ 200 {
  "id":"j_1","status":"review","stage":"validate","kind":"pdf_scan",
  "pages_total":12,"pages_done":12,"used_ai":false,
  "pages":[{"no":1,"status":"ocr_ok","source":"vision","confidence":0.93},
           {"no":7,"status":"low_confidence","source":"vision","confidence":0.41,"reason":"dense formula"}],
  "question_count":27,"questions_detected":27,"expected":27,
  "warnings":["page 7 needs review"],
  "needs_review":true,"document_id":null
}

POST /api/imports/{job_id}/ai-fallback {"pages":[7]}     # 仅失败页 → AI 视觉
→ 200 { "used_ai":true, "pages":[{"no":7,"status":"ai_ok","source":"ai"}] }

POST /api/imports/{job_id}/commit
→ 200 {"document_id":42,"question_count":27,"answers_status":"inline"}

POST /api/imports/{job_id}/cancel
DELETE /api/imports/{job_id}
```

**保留即时导入**：`POST /api/documents`（`.sat.md`/`.md`）不变，向后兼容；内部可复用 job 管线的 commit 步骤。

**词汇表 v2**：
```jsonc
// PUT /api/documents/{id}/words
{
  "headers": ["Word","Meaning","Notes"],
  "column_ids": ["c1","c2","c3"],
  "column_widths": [140, 260, 220],
  "row_ids": ["r1","r2"],
  "rows": [["elate","make happy","verb"],["cadence","rhythm",""]],
  "view": {"sort": {"column_id":"c1","dir":"asc"}, "filters": [], "frozen": 1}
}
// GET 返回同样形状；老数据默认补全 column_ids/row_ids/widths/view
```

**AI Tutor（上下文扩展）**：
```jsonc
// POST /api/ai/answer
{ "document_id": 42, "question_id": 318 }
// → { "text": "...", "model": "gpt-4o-mini", "context": ["stem","material","options","correct","chosen","section"] }
```
- 服务端组装上下文包含：`section`、`material`、`stem`、**四个完整选项**、`correct answer`、`student's choice`（若属于某 session）。
- **仍排除**：用户手写解析（`explain`）、AI 历史输出、任何未保存草稿。
- 无答案键时**拒绝**（409），避免 AI 编造答案（保留现有行为）。

**保存 AI 解析为可编辑解析**：扩展 `ExplainPayload`：
```jsonc
// PUT /api/documents/{id}/questions/{qid}/explain
{ "content": "...", "source": "human" | "ai" }
// → { "question_id": 318, "explain": "...", "explain_source": "ai", "explain_updated_at": "..." }
```

**导出**（2026-10-07 更新：仅 PDF/DOCX；旧的 md/csv/json 已移除）：
```
GET /api/documents/{id}/export/pdf        → application/pdf
GET /api/documents/{id}/export/docx       → ...wordprocessingml.document
GET /api/documents/{id}/words/export      （.xlsx，v2 增强）
```

**CB-style normalization（显式、整卷批量，无逐题审阅）**：
```jsonc
// POST /api/documents/{id}/normalize            → 202 { "doc_id", "status": "running", ... }
//   后台逐题 LLM 改写并直接落库（temperature=0，逐题串行）
// GET  /api/documents/{id}/normalize            → 轮询 { "status": "running|done|failed",
//     "total", "done", "applied", "unchanged", "kept", "errors": ["#Q007: ..."] }
//   失败/校验不过的题保留原文；answers/source/explain 列永不触碰
// 单题端点（API 兼容，UI 不再使用）：
// POST /api/documents/{id}/questions/{qid}/normalize
// POST /api/documents/{id}/questions/{qid}/normalize/accept { "normalized": {...} }
```

---

## 8. 导入、OCR、LLM fallback、CB normalization 的状态机

### 8.1 导入状态机

```
idle
 └─ detect(file)
      ├─ .sat.md ──────────────► validate(parse) ──ok──► commit ──► done (0 token)
      ├─ .md/.markdown ────────► deterministc-normalize
      │                              ├─ parse ok ──► commit ──► done (0 token)
      │                              └─ fail ──► review ──[user]──► llm-fallback 或 manual edit
      ├─ .docx ────────────────► docx-extract (python-docx: paragraphs/tables/images/OMML) 
      │                              ├─ parse ok ──► commit ──► done (0 token)
      │                              └─ 歧义/缺结构 ──► review
      └─ .pdf ─────────────────► pdf-profile
                                     ├─ 文本层健康 ──► 现有 profile ──► commit (0 token)
                                     └─ 低文本密度页 ──► ocr-stage
```

### 8.2 OCR 状态机（仅扫描页）

```
per page:
  has_text_layer? ──yes──► deterministic profile
        │no
        ▼
  OCR adapter available? ──no──► page.status = "ocr_unavailable" ──► review
        │yes                         （提示：安装 OCR 或对该页使用 AI 视觉）
        ▼
  run OCR (macOS Vision primary; Tesseract fallback)
        ├─ confidence >= threshold (0.75) AND 结构校验通过 ──► page.status="ocr_ok"
        └─ otherwise ──► page.status ∈ {low_confidence, struct_fail}
                          └─ user choice: [Use AI on these pages] [Edit manually] [Retry OCR]
```

**绝不伪造 OCR 置信度**。真实信号仅：
1. 页是否有文本层（`page.get_text()` 字符数 / 页面积）；
2. adapter 自带的置信度（Vision `VNRecognizeTextRequest` 的 observation confidence；Tesseract 的 word conf）——**若某 adapter 不提供则不显示数字，只显示 ok/low**；
3. SAT-MD 结构校验（stem 非空、恰 A–D、section 合法、answer∈ABCD 且与选项一致）；
4. 覆盖比：检出题数 vs 由编号推断的期望题数。

### 8.3 LLM fallback 状态机（仅失败页/页块）

```
failed_pages = [ ... ]
  ├─ 无 API key ──► 显示替代路径（手工模板 / 重试 OCR / 编辑），不报错死路
  └─ 有 API key ──► 显示"将对 N 页使用 AI（模型 X），可能消耗 token" + [Run] [Cancel]
                      （只做定性提示，不显示 token 数/价格预估）
                      └─ Run ──► 逐页打标 → verbatim fidelity + 结构校验
                            ├─ 通过 ──► 合并入结果
                            └─ 失败 ──► review 编辑器（可手改）
```
**只发送失败页/页块，绝不默认整份文档**。

### 8.4 CB-style normalization 状态机（显式、可拒绝）

```
question ──[user 点击 Normalize to CB style]──► llm draft
  ├─ 校验：保留考查目标 / 事实 / 正确答案 / 单选 / A–D；材料/图片/公式/provenance 保留
  ├─ 任何"改答案"或格式不合规 ──► 拒绝草稿并报错，不写库
  └─ 合规 ──► 并排审阅 UI（Original | Normalized，差异标注）
                └─ [Accept] 写库（explain_source 不变；记录 changed 字段）
                   [Reject] 丢弃
```
**不得在学生答题页暴露正确答案或 AI 内部判断**。**触发粒度：逐题**（已确认）——`Normalize to CB style` 作用于当前题，逐题审阅、逐题接受，不做整卷批量。

---

## 9. PDF / DOCX / XLSX 导出实现方案与文档模板规范

### 9.1 技术路径

| 格式 | 方案 | 说明 |
|---|---|---|
| **PDF** | **WeasyPrint**（HTML/CSS → PDF） | 用服务端生成的 HTML 模板 + 内联 CSS（`@page` 页眉/页脚/页码、`page-break-inside: avoid`）；图片以文件路径/data URI 嵌入；字体用系统字体（CJK 走系统）。**需系统库** pango/cairo/gdk-pixbuf/harfbuzz（macOS: `brew install pango gdk-pixbuf libffi`）。 |
| **DOCX** | **python-docx** | 可继续编辑：标题/正文样式、`add_picture`、分页符、页眉页脚页码（field code）、段落 keep-with-next。 |
| **XLSX** | **openpyxl**（已有） | v2 增强：列宽、冻结首行、粗体表头、auto-filter；仅写入值，保证 Numbers 打开。 |

**数学公式（2026-10-07 已落地，原 KaTeX spike 取消）**：KaTeX 只在浏览器渲染、WeasyPrint 不执行 JS，故直接采用**已实现**的 **MathJax SVG** 管线：
1. **Node 桥接**：`backend/app/export/mathjax/render.mjs`（`mathjax-full` 的 SVG 输出，`fontCache: "local"`）把 `$...$` / `$$...$$` / `\(...\)` / `\[...\]` 渲染为**自包含 SVG**；Python 端 `backend/app/export/math_render.py` 单次 subprocess 批量调用 + 进程内缓存（按 `(tex, display)` 键）。
   - **可选依赖**：Node 或桥接 `node_modules` 缺失时，所有公式**降级为纯文本**（`$tex$`），**导出绝不崩溃**。
2. **PDF**：SVG 以 `data:image/svg+xml;base64,...` 内联进导出 HTML，WeasyPrint 直接渲染（已验证）。
3. **DOCX**：同一 SVG 经 `cairosvg` 转 PNG 后 `run.add_picture` 内联（宽度按 SVG `ex` 尺寸换算并封顶）。
   - 不再需要“服务端预渲染 KaTeX / spike 验证”——该风险已由实现消除。

**浏览器打印 PDF 不作为正式路径**（可保留为"快速打印"次要入口），正式交付走后端 WeasyPrint。

### 9.2 "SATeacher Review Pack" 模板规范

**封面**
- 主标题：文档标题（如 `2025 August North America — Harder A`）。
- 副标题：`SAT Practice Review`。
- 元信息：题目数、科目分布（R&W / Math）、生成日期。
- 可选：练习/会话信息（若从某 session 导出，显示分数、用时、日期）。
- 全英文、打印友好、克制。

**正文**
- 每题：清晰题号、section、题干、material、公式、图片。
- A–D 全部选项；正确项**明确但不过度刺眼**（加粗 + 左侧色条/勾，不用大红底）。
- 若从 session 导出：显示学生选择与 正确/错误/未作答 状态（`[your answer]` / `[correct]` / `Unanswered`）。
- 解析区：显示已保存的手写或已接受的 AI 解析，并标注来源（`Explanation · human/ai · updated`）。
- **不伪造**"每个错误选项都有单独解析"；逐选项解释作为未来增量（需新数据模型/API/UI），本文档仅记录该增量点。
- 每题 `page-break-inside: avoid`；图片/公式/长材料不被截断（`break-inside: avoid`）。
- 每页右下角低调水印 `Generated by SATeacher`。
- 页眉（文档标题）+ 页码；长文档提供**目录/索引**（**>20 题时自动生成 question index，已确认**）。
- DOCX 保持可编辑；PDF 版式稳定。
- **导出只包含已保存内容**；未保存草稿绝不进入。

### 9.3 图片、公式、Unicode、中英混排风险

- 图片：以原比例嵌入；矢量图按当前 `convert/images.py` 的 PNG 兜底。
- 公式：见 §9.1 的 Node 渲染管线；WeasyPrint 需内联 KaTeX 字体。
- Unicode/中英混排：WeasyPrint 依赖系统字体回退（PingFang/Noto）；DOCX 指定东亚字体（`w:eastAsia`）。
- 分页：CSS `break-*`（WeasyPrint 支持）；DOCX 用 `keep_with_next` + 显式分页。

---

## 10. 前后端实施批次

> 按依赖顺序；每批目标/改动文件/依赖/风险/回滚/验收。全程遵守：pathspec 提交、提交前 question 确认、不破坏 121 pytest、不动 `data/app.db`、不杀 dev 服务。

### 批 7 — 设计系统基础（可独立验收） · ✅ 完成（2026-10-08）
- **目标**：token + 组件原语 + 图标库 + AppShell，全站外观统一。
- **改动**：`frontend/src/index.css`（`@theme` token：色板/间距/圆角/阴影/字体/过渡、系统字体栈、`prefers-reduced-motion`、focus-visible、scrollbar）；新增 `frontend/src/components/ui/*`（Button/Input/Tabs/Badge/EmptyState/Banner/Toast/Icon）；`AppShell.tsx` 顶栏导航 + 移动端抽屉 + Outlet；`package.json` + `lucide-react`；全站逐步替换 emoji 与硬编码卡片样式。
- **依赖**：`lucide-react`（图标库，树摇优化）。
- **风险**：视觉回归（已有 E2E 回归保护）；E2E 选择器依赖文案。
- **回滚**：纯前端，`git revert` 单提交即可。
- **验收（已达成）**：`npm run build` 0 错；`tsc --noEmit` 0 错；后端 171 passed；E2E `run6.mjs`/`run10.mjs` 回归全过；无严重 a11y 问题。

### 批 8 — 导入流水线骨架 + DOCX 导入 + 模板预览 + Library · ✅ 已完成（批次 B + D，2026-10-07；余量 2026-10-09）
- **目标**：`import_jobs` 表 + API + 导入页重设计 + `.docx` + SAT-MD template。
- **已交付（批次 B + D）**：`convert/docx.py`（段落/表格/图片/软换行；zip 安全；复用 PDF 管线）；`app/imports.py` 统一服务；`import_jobs` 表 + `migrate()`；`api/imports.py` 状态机端点；`ImportPipeline.tsx`/`SatMdTemplate.tsx`/`LibraryList.tsx`；`ImportPage.tsx` 拖放 + 流水线 + 列表。
- **余量（2026-10-09 交付）**：
  - **真正的异步/分页进度**：`POST /api/imports` 只做校验 + 建行，立即 202 返回 `status: "converting"`（快照在起线程**之前**读取，响应体确定）；转换在 `threading.Thread`（daemon）里跑，`convert_pdf` 增可选 `progress(done, total)` 回调（bluebook 路径首尾各报一次、通用逐页循环每页一次），写回 `pages_done/pages_total`；前端 `ImportPage` 每 300ms 轮询 `GET /api/imports/{id}` 直到 `review/failed/cancelled`（上限 2000 次），`ImportPipeline` 增进度条 + 逐页计数 + 转换中 Cancel 按钮。
  - **取消可中断转换**：进度回调先读 job 行，发现 `cancelled` 就抛 `JobCancelled` 中止转换（`finally` 仍会关闭 PDF）；落库前再查一次状态，取消的 job 永不进 `review`、不残留 staged 文件。
  - **`ai-fallback` 实体**：批 11 已实现 `POST /api/imports/{id}/ai-fallback`（原 501 占位已移除）；该端点仍同步返回（LLM 只在用户显式点击时触发，uvicorn 线程池执行，不阻塞事件循环）。
  - **顺手修的 bug**：`create_import` 里 `convert_upload` 被重复调用两次（双倍耗时），已随重构消除；`staged` 上传副本在 `save_result` 复制到 `jobs/<id>/original.pdf` 后即删，不再滞留 `tmp/`。
- **依赖**：`python-docx`（批 A 已加入）。
- **风险**：DOCX 结构映射不完整（复杂文本框/嵌套表→降级为普通段落）；zip bomb/宏（**已实现防护**，见 §12）；转换线程随进程退出而中断（daemon），结果未落库的 job 重启后停在 `converting`，用户可取消/删除后重传。
- **回滚**：删除 `.docx`/`/api/imports` 分支即可；旧 `POST /api/documents` 仍为同步路径，不受影响。
- **验收（已达成）**：`test_imports_api.py` 17 项（含 3 项新增：202 异步语义、转换中取消不落库、PDF 逐页进度单调）；pytest 174；`tsc --noEmit` 0 错；`npm test` 42 过 6 跳；E2E `run.mjs`（导入→练习→判分→重考全流程）、`run6.mjs`、`run10.mjs` 全过。

### 批 9 — Review Workspace 外壳（复用现有端点） · ✅ 完成（2026-10-07）
- **目标**：三区 + 分隔条 + 布局持久化 + Inspector Tab + 底部词汇表 sheet。
- **改动**：`ResultPage.tsx` 瘦身；新增 `components/workspace/*`（`Workspace`、`QuestionNav`、`Inspector`、`VocabularySheet`、`Splitter`、`usePersistentLayout`、`useMediaQuery`、`icons`）。原 `ReviewSidebar.tsx` 保留作回滚。
- **依赖**：**无新依赖**（图标为内联 SVG，非 `lucide-react`）。
- **风险**：flex 挤 0 宽（历史 bug）；嵌套滚动 → 以 `min-h-0` + 单滚动区（中栏 `main`）化解。
- **回滚**：旧 `ReviewSidebar.tsx` 仍在仓库；路由可直接切回。
- **验收（已达成）**：`npm run build` 0 错误；E2E `run6.mjs` 1440/1024/375 三尺寸无横向溢出；分隔条拖拽 + 刷新持久化；底部 sheet 折叠/展开；Inspector 隐藏/重开；键盘 ←→；`role="separator"` 可聚焦。

### 批 10 — Vocabulary Sheet v2 · ✅ 完成（2026-10-08）
- **目标**：v1→v2 迁移 + 键盘/粘贴/冻结/排序/筛选/列宽持久化 + xlsx v2。
- **改动**：`repos/words.py` 重写为 v2（稳定列/行 ID、列宽、view 排序/筛选；v1 读取自愈升级）；`db.py`（`word_grids` 加 `columns_json`/`view_json`/`version` + `_migrate`）；`documents.py`（`WordsPayload` 兼容 v1/v2；xlsx 按列序导出 + 列宽 + 冻结表头）；`export/model.py`（v2→导出数组）；前端新增 `components/workspace/VocabGrid.tsx`，`VocabularySheet.tsx`/`ReviewSidebar.tsx` 复用之；`client.ts` 类型 v2。
- **依赖**：**无新依赖**（回退自研——`react-data-grid` 最新 `7.0.0-beta.61` 仍是 beta 且样式/凭据不自控，批 9 已有"无新依赖"先例）。
- **风险**：老数据兼容（已覆盖迁移测试）；grid a11y（`role="separator"` 列宽手柄 + 键盘 ↑↓/Enter/Tab）。
- **回滚**：v2 字段可选，读取端兼容 v1；`git revert` 单提交即可。
- **验收（已达成）**：pytest **171**（+7：`test_words_v2.py` 6 项 + 迁移 1 项）；`npm run build` 0 错；E2E `run10.mjs` 全过（增行/改格、列宽拖拽→持久化、排序 asc/desc/none、按列筛选、多格粘贴、保存→刷新→API v2 往返、xlsx 导出、三尺寸无溢出）；`run6.mjs` 回归过。

### 批 11 — 扫描 PDF / OCR + 选择性 AI 视觉 · ✅ 完成（2026-10-08）
- **目标**：页级文本密度检测 + 跨平台 OCR adapter + 逐页状态/报告 + **选择性 AI 视觉（仅失败页）**。
- **已交付（批次 C 基础版 + 本批）**：OCR adapter（Vision + Tesseract）、文本密度检测、坐标归一化、chrome 过滤、导入页逐页状态、导入流水线逐页报告、**AI fallback 端点**（`POST /api/imports/{id}/ai-fallback`，仅对 `ocr_unavailable/ocr_failed/low_confidence/empty` 页运行 LLM）、前端“Run AI fallback”按钮。
- **依赖**：**无新增 Python 依赖**——Tesseract 走系统二进制；macOS Vision 可选。
- **风险**：跨平台 adapter 差异；Tesseract 需系统二进制；AI fallback 需配置 LLM。
- **回滚**：端点可禁用；`git revert` 单提交。
- **验收（已达成）**：pytest 171（含 `test_imports_api.py` AI fallback 测试）；`npm run build` 0 错；E2E 回归过；扫描 PDF 导入 → 逐页状态显示 → 点击 AI fallback → 失败页补全题目 → commit → 结果页题数增加。

### 批 12 — CB-style normalization · ✅ 完成（2026-10-08；2026-10-09 按用户反馈改为整卷批量）
- **目标**：显式改写，答案与 provenance 不变。
- **最终交付（批 12b，用户反馈"100 多题逐题接受太麻烦"）**：**一键整卷改写直接落库，无逐题审阅**——`POST /api/documents/{id}/normalize`（202）后台线程逐题串行改写并即时应用，`GET` 同路径轮询进度；失败/校验不过的题保留原文并列出原因。
- **实现**：`llm/normalize.py` `normalize_document()`（逐题调用 LLM + `_verify_block` 重解析闸门）；`satmd/writer.py`（`ParsedDoc→text` 反序列化器，round-trip 测试锁死）；`repos/documents.py` `update_questions()`（只写 material/stem/options，**答案/出处/解析列永不触碰**）；`normalize_jobs.py`（进程内 job registry，单飞，后台 `Thread`）；前端 `NormalizeAllPanel.tsx`（进度条 + 汇总 + 失败清单），完成后 `ResultPage` 静默重取题目（不闪白屏）。批 12 原单题端点保留但 UI 不再使用；`NormalizeReview.tsx` 已删。
- **修复的批 12 遗留 bug**（当时零测试未暴露）：options 列表/字典混用、`_render_question` 吃错数据类（`BuiltQuestion`）、`repos.documents.update_questions` 不存在——三处均会导致运行时 500。
- **依赖**：无新依赖（复用现有 LLM 层，temperature=0）。
- **风险**：改写改变答案/事实（多重校验拦截：形状 + 不变量 + 重解析）；token 成本（显式点击触发，逐题计数可核对）；100+ 题耗时数分钟（进度条 + 单飞防重复点击）。
- **回滚**：端点可禁用；`git revert` 单提交；不改动原题。
- **验收（已达成）**：pytest 188（`test_normalize_api.py` 14 项 + `test_satmd_writer.py` 4 项）；`tsc --noEmit` 0 错；`npm test` 43 过；E2E 回归过。

### 批 13 — Review Pack 导出（PDF/DOCX + 数学管线） · ✅ 已完成（2026-10-07，作为"批次 A"）
- **目标**：正式 PDF/DOCX 模板 + 数学渲染 + 测试。
- **实际改动**：新增 `backend/app/export/{__init__,model,pdf,docx,math_render}.py` 与 `backend/app/export/mathjax/{package.json,render.mjs,.gitignore}`；`api/documents.py` 导出端点改为 `pdf|docx` 并删除 md/csv/json 实现与常量；`client.ts` + `ReviewSidebar.tsx` 导出按钮改为 PDF/DOCX；`requirements.txt` 增 `weasyprint`/`python-docx`/`cairosvg`。
- **依赖**：`weasyprint`、`python-docx`、`cairosvg`（+ 系统 pango/cairo/gdk-pixbuf）；可选 Node `mathjax-full`。
- **落地结果**：数学改为 **MathJax SVG** 管线（见 §9.1），**无需 spike**。真实文档 22（27 题）/ 23 渲染成功（16/11 页，含内嵌图片、页脚页码、答案键、解析）。
- **回滚**：`export/{pdf,docx}` 端点可禁用；**不再保留 md/csv/json**（维护者决定删除）。
- **验收（已达成）**：`test_export.py` 7 项——PDF/DOCX 前缀、PDF 文本回读（标题/选项/答案键/解析）、DOCX 段落回读、非法格式 400 / 缺失文档 404、数学桥接与含公式容错；后端 **124 passed**。
- **未含**（后续增量，未排期）：overview 封面/水印/目录（>20 题 question index 已确认但未实现）、从 session 导出的对错标注、逐选项解析。

### 批 14 — AI Tutor 扩展 + 解析 provenance + 收尾 · ✅ 完成（2026-10-08）
- **目标**：AI 上下文扩展（material/四选项/学生作答/section）、解析来源与时间。
- **改动**：`api/ai.py`（context 扩展：material + 全选项 + 正确答案 + 学生作答 + section；可选 session_id 获取学生作答）、`repos/sessions.py`（`get_student_answer`）、`api/ai.py` payload 增 `session_id`、`client.ts` `askAI` 增 `sessionId`、ResultPage/Workspace/Inspector 透传 `sessionId`；测试更新断言 context 包含 material/选项/section、排除手写解析。
- **依赖**：无新依赖。
- **风险**：原测试 `test_ai_answer_context_is_stem_plus_correct_option` 已更新为新语义。
- **回滚**：单提交回退。
- **验收（已达成）**：pytest 171（含 AI context 测试）；`npm run build` 0 错；E2E `run6.mjs`/`run10.mjs` 回归过。

### 批 15 — 前端组件测试栈（已批准）
- **目标**：新增 `vitest + @testing-library/react + jsdom`，覆盖 `VocabularySheet` / `Splitter` / `ImportPipeline` / `Inspector`。
- **改动**：`frontend/package.json`（devDeps + `test` 脚本）、`frontend/vitest.config.ts`、测试文件。
- **风险**：Vite 7 / React 19 配置兼容。
- **回滚**：纯新增，删除即可。
- **验收**：`npm test` 通过；不影响 `npm run build`。

### 批 16 — 可分发与跨平台接入（README / setup 脚本）
- **目标**：让别人**拿来即用，或读完 `README` 就会用**（新增硬要求）。
- **改动**：
  - `README.md`：完整的"安装 → 运行 → 首次导入 → SAT-MD 模板 → 排错"指南，逐平台（macOS / Linux / Windows）说明 Python、Node、WeasyPrint 系统库（pango/cairo/gdk-pixbuf/harfbuzz 或 Windows GTK）、可选 Tesseract。
  - `scripts/setup.sh`（macOS/Linux）+ `scripts/setup.ps1`（Windows，尽力而为）：建 venv、装依赖、提示系统库。
  - `scripts/dev.sh` 已有，补 Windows 说明；`.env.example`（`SATEACHER_DATA` / `SATEACHER_API`）。
  - 依赖缺失**友好降级**：无 WeasyPrint → PDF 导出按钮禁用 + 安装指引；无 OCR → 扫描件给替代路径。
- **依赖**：无新增（只文档/脚本）。
- **风险**：平台差异无法在单一机器全量验证 → README 标注支持度（macOS 官方验证 / Linux 尽力 / Windows 社区验证）。
- **回滚**：文档/脚本改动，独立回退。
- **验收**：干净 macOS 按 README 从零跑通；Linux 手动/CI 核对关键步骤。

---

## 11. 测试策略

### 11.1 后端单元（pytest，扩展 `backend/tests/`）
- `test_imports_api.py`：job 状态机、逐页报告、取消、commit、幂等。
- `test_docx_convert.py`：段落/表格/图片/公式抽取 → satmd；畸形/超大 zip 防护。✅ **已实现（批次 B）**
- `test_ocr.py`：合成扫描 fixture（用 PyMuPDF 把文本 PDF 栅格化为图片 PDF）→ OCR 文本；低置信分支；无 adapter 分支。
- `test_normalize_api.py`：整卷批量（应用/保留原文/答案不变/无答案跳过不花 token/409/404）、单题 accept 回归、`test_satmd_writer.py` round-trip。✅ **已实现（批 12b）**
- `test_export_pdf_docx.py`：导出字节前缀 + 回读（`pypdf`/`python-docx`/`openpyxl`）；分页与水印断言。
- `test_words_v2.py`：v1→v2 迁移往返、列宽/行 ID/view 持久化、上限校验。
- 迁移：`test_migrations.py`（老 schema → user_version 升级幂等）。
- 更新 `test_review_api.py::test_ai_answer_context_is_stem_plus_correct_option` → 新上下文契约。

### 11.2 前端组件测试（新增栈，已批准）
- `vitest + @testing-library/react + jsdom`：`VocabularySheet`（编辑/粘贴/键盘/列宽）、`Splitter`（键盘调整）、`ImportPipeline`（各状态）、`Inspector` Tab。
- 保持无状态管理库约定（普通 fetch + hooks）。

### 11.3 浏览器 E2E（扩展 `/tmp/e2e/`）
- 保留 run/run2/run3/run4（并更新受设计系统影响的文案选择器）。
- 新增：run5（导入流水线 + DOCX + 模板复制）、run6（工作台分隔条/持久化/底部 sheet/Inspector 隐藏重开）、run7（设计系统：导航/组件/token/响应式）、run10（词汇表 v2 grid + 键盘/粘贴/排序/筛选/列宽 + xlsx 往返）、run11（扫描 PDF OCR + 选择性 AI 视觉 fallback）、run12（CB normalization：生成/对比/接受/写库）、run14（AI tutor 扩展：context 扩展/学生作答/section）、run8（扫描/OCR/选择性 AI，mock）、run9（PDF/DOCX 导出下载 + 内容回读）。
- 纪律沿用 `HANDOFF.md §6`：`servers.mjs` 子进程 `unref()`；等待 Tailwind uppercase 文案用 `/ready to begin/i`；结尾 `Promise.race(browser.close, 5s)` + `process.exit(0)`。

### 11.4 OCR / 文档格式 fixture
- 用 PyMuPDF 生成**自包含** fixture：文本 PDF、扫描（图片）PDF、含图片/公式 DOCX（python-docx 生成）、SAT-MD 模板。避免外部二进制资产。

### 11.5 DOCX/PDF/XLSX 产物验证
- PDF：`pypdf` 提取文本，断言标题/题号/答案/水印；页数合理。
- DOCX：`python-docx` 读回段落/图片数量/页眉页码。
- XLSX：`openpyxl.load_workbook` 读回，`content[:2]==b"PK"`；Numbers 人工验收（打开无警告）。

### 11.6 视觉与响应式验收
- Puppeteer 截图 1440 / 1024 / 768 / 375；比对关键布局（无横向溢出、无 0 宽主栏、scroll 归属正确）。

### 11.7 无障碍验收
- `@axe-core/puppeteer` 每页扫描（无 serious/critical）；键盘 Tab 全程可达；focus ring 可见；对比度 ≥4.5:1；触控目标 ≥44px；`prefers-reduced-motion` 生效。

### 11.8 跨平台与"上手"验收（新增）
- 在**干净环境按 README 从零**安装并跑通：macOS 为官方验证目标；Linux 尽力（可进 CI）；Windows 标注为"社区验证"。
- **依赖缺失降级**：无 WeasyPrint → PDF 导出禁用且给出安装指引；无 OCR Adapter → 扫描件给出替代路径（手工模板 / AI 视觉 opt-in）；两者都不崩溃、不报错死路。
- `scripts/setup.*` 幂等（重复运行安全）。
- 首次使用的 `README` 走查：新用户仅凭 README 能完成"安装 → 导入 → 练习 → 结果 → 导出"。

---

## 12. 风险、未知点与开发前确认事项（含 2026-10-07 决定）

### 12.1 高风险
1. **WeasyPrint 系统依赖（跨平台）**：pango/cairo/gdk-pixbuf/harfbuzz。macOS 需 Homebrew、Linux 需包管理器、Windows 需 GTK。**已定**：README 逐平台文档化 + `scripts/setup.*` 协助；依赖缺失时 PDF 导出**友好禁用**而非报错死路。
2. ~~**KaTeX → PDF 渲染保真**~~ **已消除（2026-10-07）**：未采用 KaTeX，改为直接落地 **MathJax SVG** 管线（PDF 内联 SVG / DOCX 经 cairosvg 转 PNG）；Node/桥接缺失时降级纯文本。
3. **OCR 跨平台（已定）**：Adapter 必须跨平台——macOS 用 `pyobjc-framework-Vision`；Windows/Linux 用 Tesseract（`pytesseract` + 系统二进制，**不强制安装**）。缺失时给出友好提示与替代路径（手工模板 / AI 视觉 opt-in）。
4. **react-data-grid × React 19**：需先验证；不兼容则**回退自研（已接受）**（批 10 工作量上升）。
5. **DOCX 安全** ~~必须在批 8 实现~~ **导入侧已实现（2026-10-07 批次 B）**：`convert/docx.py::_check_archive` 在解析前校验 zip 条目数（≤5000）、解压总量（≤300 MB）、压缩比（>200 且 >5MB 拒绝）、并拒绝含 `vbaProject.bin` 的宏文档；只接受 `.docx` 扩展名。路径穿越不适用（不按名解压到磁盘，仅内存读图片）。
6. **异步 import job × SQLite**：并发写/锁。建议 job 状态写库加短事务；转换在内存/临时目录，commit 才落库。
7. **CB normalization 改变答案**：必须以"答案不变+结构校验+人工审阅"三重拦截；绝不能静默入库。**触发粒度逐题**。
8. **AI 上下文扩展的隐私/token 影响**：material 可能很长 → token 成本上升。操作前只做**定性**提示（"可能消耗 token"），不显示 token 数/价格预估（已确认）。
9. **跨平台"拿来即用"**：不同 OS 的系统依赖差异大，只读 README 未必够。**缓解**：README 逐平台步骤 + setup 脚本 + 依赖缺失降级 + 在 README 标注各平台支持度（macOS 官方验证 / Linux 尽力 / Windows 社区验证）。

### 12.2 必须保护（不得重置/覆盖）
- 现有 **164 pytest**（批 A 导出 7 项 + 批 B DOCX 13 项 + 批 C OCR 9 项 + 批 D 导入流水线 13 项 + 迁移 3 项 + 健康检查 1 项）、4 套 E2E、StrictMode 修复（`PracticePage` `startedFor`/`aliveRef`）、内置 44 模块题库、批 6 服务商目录。
- `data/app.db` 用户数据（1 文档 + 4 会话）——测试用 `SATEACHER_DATA` 临时目录。
- `LICENSE`（用户改动）与 staged `.idea/`——pathspec 提交保护；**每次提交前 question 确认**。

### 12.3 开发前确认事项（已于 2026-10-07 由维护者拍板）

| # | 事项 | 决定 |
|---|---|---|
| 1 | WeasyPrint 系统库安装方式 | **均可**：README 文档化 + 提供 `scripts/setup.*`；以"别人能直接拿去用 / 读完 README 会用"为验收标准。 |
| 2 | PDF 数学渲染 spike 不达标时 | **批准** MathJax SVG 内联图片回退管线。 |
| 3 | react-data-grid × React 19 不兼容时 | **接受**回退自研。 |
| 4 | OCR 跨平台 | **不只 macOS**；Adapter 跨平台，Tesseract 为可选（**不强制安装**）。 |
| 5 | 是否显示 token 粗估 | **不需要**（只做定性"可能消耗 token"提示）。 |
| 6 | 前端测试栈 | **批准** `vitest + @testing-library/react + jsdom`（批 15）。 |
| 7 | CB normalization 粒度 | **逐题**（非整卷批量）。 |
| 8 | 导出 PDF 自动目录/索引 | **是**（>20 题生成 question index）。 |
| 9 | 旧 `analyses`/`vocab`/`notes`/`llm_logs` 死表 | **保留占位**（不删，避免破坏老库），本计划不依赖。 |
| 10 | 跨平台分发与 README 上岗 | **新增硬要求**：见批 16；README 重写 + setup 脚本 + 依赖缺失降级。 |
| 11 | 旧导出格式 md/csv/json | **删除**，只保留 **PDF/DOCX**（2026-10-07 追加决定）。 |
| 12 | PDF/DOCX 数学渲染 | **直接采用 MathJax SVG**（PDF 内联 SVG / DOCX 经 cairosvg 转 PNG；缺失降级纯文本），不再走 KaTeX spike。 |
| 13 | DOCX 导入安全 | **导入侧已实现**（zip 条目/总量/压缩比/宏校验；见 §12.1-5、批次 B）。 |

> 除上表外，实施期间若出现新歧义，仍按既有铁律"**先问维护者，不自行猜测**"。

---

### 附录 A — 依赖清单新增汇总

| 包 | 用途 | 许可 | 代价/风险 | 替代 |
|---|---|---|---|---|
| `weasyprint` | PDF 导出（HTML/CSS 分页） | BSD-3 | **跨平台**系统库差异（macOS brew / Linux pkg / Windows GTK）；缺失时导出降级 | ReportLab、Playwright/Chromium |
| `python-docx` | DOCX 导入 + 导出 | MIT | 数学公式支持弱（用图片管线） | docxtpl、手动 OOXML |
| `pyobjc-framework-Vision` | macOS OCR | MIT/BSD | macOS 专属；其他平台走 Tesseract | Tesseract（跨平台） |
| `pytesseract`（**已改为不依赖**） | 跨平台 OCR 回退 | MIT | **实际实现改为直接子进程调用系统 `tesseract`**，无需 `pytesseract`；缺失给友好提示 | 系统二进制（当前方案） |
| `lucide-react`（前端） | 图标体系 | ISC | 无 | @heroicons/react |
| `react-data-grid`（前端） | 电子表格 | MIT | React 19 兼容待验证；**不兼容则回退自研（已接受）** | 自研、glide-data-grid、Handsontable(非商业) |
| `mathjax-full`（Node，**实际使用**） | TeX→SVG 数学渲染（PDF 内联 SVG / DOCX 经 cairosvg 转 PNG）；缺失时降级纯文本 | Apache-2.0 | 需 Node；桥接 `node_modules` 可选安装 | 无 |
| `cairosvg` | SVG→PNG（DOCX 内联公式图片） | LGPL-3 | 依赖系统 cairo；缺失时 DOCX 公式降级纯文本 | svglib、resvg |
| `vitest` + `@testing-library/react` + `jsdom`（前端 dev） | 组件测试 | MIT | 新增测试基建；**已批准** | Playwright component testing |
| `pypdf`（测试用） | PDF 回读校验 | BSD | 仅测试 | pdfminer.six |

### 附录 B — 结论的代码证据索引

- 导入仅扩展名判型：`backend/app/api/documents.py:97–109`
- 扫描件 fatal：`backend/app/convert/pdf.py:168–172`
- 词汇表仅 headers/rows：`backend/app/repos/words.py:23–58`
- AI 上下文最小：`backend/app/api/ai.py:56–61`；测试钉死：`backend/tests/test_review_api.py:183–212`
- 手风琴侧栏：`frontend/src/components/ReviewSidebar.tsx:17–36,206–451`
- 三栏结果页：`frontend/src/pages/ResultPage.tsx:296–488`
- 无设计 token：`frontend/src/index.css:1–10`
- 死表：`backend/app/db.py:79–129`
- migrations ad-hoc：`backend/app/db.py:155–165`
- 现导出格式：`backend/app/api/documents.py:29,342–375`

---

*（本文档为规划，不含代码变更。§12.3 事项已于 2026-10-07 确认，可按批 7→16 顺序交给后续开发 Agent 执行。）*