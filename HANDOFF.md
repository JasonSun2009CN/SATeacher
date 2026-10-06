# SATeacher — HANDOFF（交接文档）

> 面向后续会话 / AI agent 的项目交接。生成于 2026-10-06，**项目状态变化后须同步更新本文件**。
> 配套文档：`docs/PLAN.md`（决策与批次交付的权威记录）、`docs/SAT-MD.md`（satmd 格式规范）。

## 1. 项目概览

SAT 自动刷题助手（本地 Web 应用）：**导入 PDF/DOCX 题库 → 补录答案 → Bluebook 风格全屏练习 → 错题分析/知识点整理 → 生词本 → PDF/DOCX 导出**。

- 技术栈：FastAPI + React（Vite / TypeScript / Tailwind），SQLite 单文件，PyMuPDF 转换；WeasyPrint（PDF）/ python-docx（DOCX 导入+导出）；OCR＝系统 `tesseract` 子进程（可选）或 macOS Vision（可选 `pyobjc-framework-Vision`）
- **铁律**：LLM 不在主链路（导入 0 token，AI 只在用户显式点击时花钱）；界面全英文；与用户交流用中文；**有疑问必须用 question 工具问用户，不许自己猜**
- 依赖基线：`fastapi uvicorn pymupdf python-multipart httpx pytest`（+ `openpyxl` 已批准）+ `weasyprint python-docx cairosvg`（批 A 导出 + 批 B DOCX 导入，2026-10-07）；可选 Node `mathjax-full`（`backend/app/export/mathjax/`）

## 2. Git 状态（2026-10-06）

```
b1263a7 PracticePage: StrictMode double startSession fix (startedFor + aliveRef refs)
4d7426a Built-in SAT reading/writing bank (offline build, builtin API, import cards)
5e44da0 Result page: master-detail layout — question index, single-question pane, sticky workspace
f2ae30e Make vite /api proxy target configurable via SATEACHER_API env var
8d21926 feat: SATeacher — SAT practice app (import, fullscreen practice, review, exports)
8894611 Initial commit
```

工作区有意保留、**不纳入提交**：

| 状态 | 路径 | 说明 |
|---|---|---|
| ` M` | `LICENSE` | 用户自己的改动 |
| `A ` (staged) | `.idea/` | 用户暂存的 IDE 文件 |
| `??` | `backend/app/providers.py`、`backend/app/api/settings.py`、`frontend/src/pages/SettingsPage.tsx`、`backend/tests/test_settings_api.py`、`backend/tests/test_llm_base.py`、`docs/PLAN.md` 等 | **批6 产物，已完成未提交** |
| `??` / `M` | `backend/app/export/**`、`backend/tests/test_export.py`、`backend/app/api/documents.py`、`frontend/src/api/client.ts`、`frontend/src/components/ReviewSidebar.tsx`、`docs/ARCHITECTURE.md`、`ROADMAP.md`、`docs/RENOVATION_PLAN.md` | **批 A（PDF/DOCX 导出，2026-10-07）产物，未提交**；`backend/app/export/mathjax/node_modules/` **不入库**（`.gitignore`） |
| `??` / `M` | `backend/app/convert/docx.py`、`backend/tests/test_docx_convert.py`、`backend/tests/fixtures.py`、`backend/tests/conftest.py`、`backend/tests/test_api.py`、`frontend/src/pages/ImportPage.tsx`、`backend/app/api/documents.py` | **批 B（DOCX 导入，2026-10-07）产物，未提交** |
| `??` / `M` | `backend/app/convert/ocr/**`、`backend/app/convert/pdf.py`、`backend/app/convert/normalize.py`、`backend/app/main.py`、`backend/tests/test_ocr.py`、`backend/tests/test_api.py`、`backend/tests/fixtures.py`、`backend/tests/conftest.py`、`frontend/src/pages/ImportPage.tsx`、`frontend/src/api/client.ts` | **批 C（扫描 PDF / OCR，2026-10-07）产物，未提交**；无新增 Python 依赖 |
| `??` / `M` | `backend/app/imports.py`、`backend/app/api/imports.py`、`backend/app/repos/imports.py`、`backend/app/db.py`、`backend/app/repos/documents.py`、`backend/app/convert/model.py`、`backend/app/convert/docx.py`、`backend/app/main.py`、`backend/tests/test_imports_api.py`、`backend/tests/test_migrations.py`、`frontend/src/components/ImportPipeline.tsx`、`SatMdTemplate.tsx`、`LibraryList.tsx`、`frontend/src/pages/ImportPage.tsx`、`frontend/src/api/client.ts` | **批 D（导入流水线骨架，2026-10-07）产物，未提交** |

**提交约定**：`git commit -m "..." -- <paths>`（pathspec 方式，保护上表不被带进去）；**每次提交前必须用 question 工具问用户**。

## 3. 已完成的工作

| 批次 | 内容 | 验证 |
|---|---|---|
| 批1 | LLM 传输层（OpenAI/Anthropic）+ 混合转换 LLM 兜底（打标+校验+重试1次） | pytest +23 |
| 批2 | 全屏开始屏、交卷分流（graded>0→结果页 / ==0→答案页补录→regrade）、独立结果页 + 三选一 tab | pytest +3 |
| 批3 | `ReviewSidebar` IDE 折叠侧边栏（解析直存 / 词汇表 xlsx / AI 解答） | pytest +9 |
| 批4 | md/csv/json 导出端点 + 结果页统计面板（Score/分section/用时/错题chips） | pytest +4 |
| E2E 隔离 | `/tmp/e2e/` 私有实例（:8765 后端 / :5273 前端，数据每次重置），vite 代理 `SATEACHER_API` 环境变量化 | 三套 E2E 全过 |
| 结果页改版 `5e44da0` | 三栏 master–detail：左 `#qindex` 题号列表（状态色+吸顶+随tab过滤）｜中 `#qcontent` 单题（←/→按钮+键盘切题+`n/total`）｜右 `ReviewSidebar` sticky 常驻；<1024px 竖排降级 | build 0 错；E2E run/run2/run3 全过 |
| 批5 `4d7426a` | 内置题库：5A 离线构建脚本 44/44 单元（1186题+1186答案+17图）｜5B `documents.builtin_key` 迁移 + `app/api/builtin.py`（列表/单加/add-all、幂等）｜5C 导入页 `BuiltinBankCard`（折叠卡→日期分组→Add/Add all/✓In library 跳练习页） | pytest 113（+6）；E2E run4 新增全过；run/run2/run3 回归过 |
| StrictMode 修复 `b1263a7` | `PracticePage` startSession 双调修复（`startedFor` ref 同 docId 只建一次；`aliveRef` 处理真实卸载；不用 cleanup 置 cancelled——StrictMode 合成 cleanup 会丢唯一在途响应→卡 Loading） | E2E run.mjs 会话数断言（首进=1、重做=2）；run/run2/run3 全过 |
| 批6（未提交） | 服务商目录：`app/providers.py` 16 家预置（OrcaRouter 第一，BaseURL 官网核对）｜`protocol` 与 provider 解耦（settings 新增键、显式覆盖优先）｜`GET /api/settings/providers`｜probe/LLM 按 protocol 分发 + 目录默认 BaseURL｜Settings 页目录驱动下拉 + 协议提示 + 自动路由默认模型 | pytest 121（+8）；E2E run/run2/run3/run4 全过；build 0 错误 |
| **批 A（未提交，2026-10-07）** | **PDF/DOCX 导出**（替换旧 md/csv/json）：新增 `backend/app/export/{model,pdf,docx,math_render}.py` + `mathjax/` Node 桥接；端点 `GET /api/documents/{id}/export/{pdf\|docx}`；前端 Export 按钮改 PDF/DOCX。数学=MathJax SVG（PDF 内联 SVG / DOCX 经 cairosvg 转 PNG；缺失降级纯文本）。**md/csv/json 导出已删除** | `test_export.py` 7 项（前缀+回读+校验+数学）；pytest 124；build 0 错 |
| **批 B（未提交，2026-10-07）** | **DOCX 导入**（原批 8 的一部分）：新增 `backend/app/convert/docx.py`（python-docx 段落/表格/图片/软换行/VML；复用 PDF 的题号/选项/material-stem/答案键管线；**zip 安全校验**：条目数/解压总量/压缩比/宏；图片经 PyMuPDF 归一到 PNG）；`documents.py` 加 `.docx` 分支；ImportPage `accept`/文案更新。**原批 8 其余（import_jobs 流水线 / 模板预览 / Library 列表 / 拖放）未做** | `test_docx_convert.py` 12 项 + API 1 项；pytest 137；build 0 错 |
| **批 C（未提交，2026-10-07）** | **扫描 PDF / OCR**（原批 11 基础版）：新增 `backend/app/convert/ocr/{base,vision,tesseract}.py`；`convert/pdf.py` 页级文本密度检测 + 低密度页栅格化 OCR + 坐标归一化 + `is_chrome` 过滤；`normalize.option_markers` 容忍 OCR 丢空格；`/api/health` 增 `ocr`；导入页显示 OCR 状态。**零新增 Python 依赖**（Tesseract 走系统二进制子进程；macOS Vision 需可选安装 pyobjc）。**原批 11 其余（逐页报告 / 选择性 AI 视觉）未做** | `test_ocr.py` 9 项 + API 2 项；pytest 148；build 0 错 |
| **批 D（未提交，2026-10-07）** | **导入流水线骨架**（原批 8 余量）：新增 `app/imports.py`（统一 detect→convert→commit，0 token）、`repos/imports.py` + `import_jobs` 表、`api/imports.py`（create/get/commit/cancel/delete/ai-fallback(501)）；`db.py` 增 `migrate()` 与 `documents.import_source/used_ai/report_json`；`convert/model.py` 增 `PageReport` 逐页报告；`POST /api/documents` 改走同一服务；前端 `ImportPipeline.tsx`/`SatMdTemplate.tsx`/`LibraryList.tsx` + `ImportPage.tsx` 拖放与流水线 + `client.ts` 端点。**未含**：异步/分页进度、`ai-fallback` 实体 | `test_imports_api.py` 13 项 + `test_migrations.py` 3 项；pytest 164；build 0 错 |

基线：**164 pytest 全过**；`npm run build` 0 错误；E2E 四套（run/run2/run3/run4）全过。

## 4. 运行与验证命令

```bash
# dev（用户日常在用 :5173 + :8000，勿杀）
scripts/dev.sh            # 或分别起 uvicorn / vite

# 后端测试（从 backend/ 跑）
cd backend && ../.venv/bin/python -m pytest -q        # 基线 164

# 前端构建（tsc + vite）
cd frontend && npm run build

# E2E（自带私有实例，不碰 dev）
cd /tmp/e2e && node run.mjs      # 导入→练习→判分→重做
cd /tmp/e2e && node run2.mjs     # 答案录入/图片/设置
cd /tmp/e2e && node run3.mjs     # 27题全流程 + 结果页三栏 + 侧边栏 + mock LLM
cd /tmp/e2e && node run4.mjs     # 内置题库：卡片/分组/单加/幂等/Add all/In library 跳转
```

**dev 库（`data/app.db`）勿动**：1 个用户文档（id=22，25年北美）+ 4 个用户验收空会话。

## 5. 批5 — 内置题库：已完成 ✅（已提交 `4d7426a`）

**目标**：把 `SAT机考25年语文合集（下）1.4.pdf`（719 页 / 44 模块 / 1188 题 + 答案区）离线做成应用内置题库，用户在导入页一键添加（0 token）。**5A/5B/5C 均已完成并全量验证**（pytest 113、E2E run4 新增 + run/run2/run3 回归、build 0 错）。

源 PDF：`/Users/fiona/MINE/05_Studying/learning_file/out school/睿途/SAT机考25年语文合集（下）1.4.pdf`

### 产品决策（用户已通过 question 确认）

- 导入页一张**题库卡**（默认折叠）→ 展开按日期分组列 44 模块（10 组）→ 单个 **Add** + **Add all** 批量；已添加显示 **✓ In library**、可跳练习页
- 文档标题格式：**`日期 · 变体`**（如「25年8月北美 · Routing A」）
- 「25年12月亚太 · Harder A」源 PDF 缺最后 2 题（出版物缺漏，三重验证 25/25/27）→ **收录 25 题版**，构建报告 warn 标注

### 5A 离线构建（完成）

- 脚本：`scripts/build_builtin.py`；重建命令（幂等，整体重建输出目录）：
  ```bash
  .venv/bin/python scripts/build_builtin.py \
    "/Users/fiona/MINE/05_Studying/learning_file/out school/睿途/SAT机考25年语文合集（下）1.4.pdf" \
    sat2025-rw-b "SAT机考25年语文合集（下）1.4"
  ```
- 实跑结果：**44/44 单元、1186 题 / 1186 答案、17 图、exit 0（OK）**；缺题单元 warn + 按实际题号回填；全局校验 `total_q == 27*len(units) - shortfall`（扣除已知缺漏，保留对静默丢题的检测）
- 输出：`backend/app/builtin/sat2025-rw-b/{manifest.json, <unit>/doc.sat.md, <unit>/assets/}`（1.9MB，随仓库分发）
- 单元 id：`{yy}{mm:02d}-{us|apac}-{routing-a|harder-b}`（如 `2508-us-routing-a`）
- 抽查已过：`2508-us-routing-a` Q1–5 = **D,A,A,B,A**；答案以 `! answer: D` 行存于 `:::q` 块内
- 关键常量/事实：`DIVIDER_MAX_LEN=150`、PDF页码=TOC印刷页码+2、`REGION_BY_TAG={"US":"北美","International":"亚太"}`；TOC 只扫首个 divider 前页面；答案页坐标解析（题号+字母同行、标签锚定分区、NFKC）；**身份以内容页英文日期 + divider 变体行为准**（12月段 TOC 错乱仅打印 note）

### 5B 后端 builtin API（完成）

- `backend/app/api/builtin.py`：`GET /api/builtin`（manifest 发现 + 逐单元已添加状态）、`POST /{bank}/units/{unit}` 单加、`POST /{bank}/add-all` 批量；id 白名单正则防路径穿越；404/422/500 分级
- 幂等：`documents.builtin_key`（`bank_id/unit_id`）——SCHEMA 加列 + `init_db()` PRAGMA 检查老库 `ALTER TABLE` + **部分唯一索引**（`WHERE builtin_key IS NOT NULL`）；重复添加返回已有文档（`added:false`），并发竞争 `sqlite3.IntegrityError` 兜底
- 添加复用 satmd 导入路径（parse→create→write_satmd→write_assets→insert_questions，0 token）；`source_filename = "builtin:<bank>/<unit>"`
- 测试：`backend/tests/test_builtin.py` 6 个（空目录/单加/幂等/add-all/404/随附银行完整性 44 单元 1186 题）

### 5C 前端导入页题库区（完成）

- `frontend/src/components/BuiltinBankCard.tsx`：折叠卡（`button[data-bank]`、aria-expanded）→ 展开后按标题「日期」分组（连续同日期合并）→ 行内 `Add`（`button[data-add-unit]`）/ `✓ In library`（`a[title="Open in library"]` → `/doc/:id/practice`）+ 顶部 **Add all**；加载态禁用、flash/错误提示
- `ImportPage.tsx`：`banks` 状态 + `refreshAll()`（添加后并行刷新题库状态与 Library）；题库区在导入卡与 Library 之间；银行清单接口失败只 `console.warn` 不阻塞（**注意 E2E 断言 console error**）
- `client.ts`：`BuiltinBank`/`BuiltinUnit` 类型 + `listBanks` / `addBuiltinUnit` / `addBuiltinAll`
- E2E：`/tmp/e2e/run4.mjs`（折叠态断言→展开 44 单元/10 组→单加→API 幂等→Add all 44/44→In library 跳转→Library 44 文档）

## 6. 已知坑与约定

- **本会话 edit 偶发不落盘**：重要改动后必须 grep/read 复核
- **图片读取工具本会话缓存故障**：勿依赖图像目检，改用坐标/文本程序化分析
- E2E 坑：Tailwind uppercase → 等待文案用 `/ready to begin/i`；run3 结尾 `Promise.race(browser.close, 5s)` + `process.exit(0)`；`servers.mjs` 子进程必须 `unref()` 否则挂起退出
- `PracticePage` StrictMode 双调 `startSession` **已修（2026-10-06）**：`startedFor` ref 保证同 docId 只建一次会话；⚠️ 教训——不能再用 cleanup 置 `cancelled=true`（StrictMode 的合成 cleanup 会把唯一一次请求的响应丢掉导致卡 Loading），改用 `aliveRef`（真实卸载/换文档才失效）+ `startedFor` 双守卫；E2E run.mjs 增加会话数断言（首进=1、重做=2）钉死回归
- 结果页布局教训：flex 行里的侧栏包装层必须在 lg 收窄宽度（`w-full shrink-0` 不加 `lg:w-auto` 会把主栏挤成 0 宽、点击被覆盖）——已修，勿回退

## 7. 关键文件索引

| 路径 | 作用 |
|---|---|
| `backend/app/api/documents.py` | 导入路径（parse→insert→write_satmd→write_assets），builtin 添加复用 |
| `backend/app/convert/pdf.py` | `convert_pdf(path, title) → ConvertedDoc{satmd, assets, warnings, answers_status, question_count}` |
| `backend/app/convert/docx.py` | `convert_docx(path, title) → ConvertedDoc`（批 B：python-docx 段落/表格/图片 → 复用 pdf 管线；zip 安全校验） |
| `backend/app/satmd/parser.py` | `parse` / `set_answer`（答案注入前必须先 parse 取 `q.ext_id`/`q.no`） |
| `backend/app/api/builtin.py` | 批5B：内置题库 API（列表/单加/add-all，幂等） |
| `backend/app/builtin/` | 批5A 构建输出（44 单元 + manifest，随仓库分发） |
| `scripts/build_builtin.py` | 批5A 离线构建脚本（可幂等重建整库） |
| `backend/tests/test_builtin.py` | 批5B 测试（6 个） |
| `backend/tests/test_docx_convert.py` | 批 B 测试（12 个：转换/表格/图片/安全） |
| `frontend/src/pages/ImportPage.tsx` | 导入页（批5C 题库卡挂载点 `refreshAll`） |
| `frontend/src/components/BuiltinBankCard.tsx` | 批5C 题库卡（折叠/日期分组/Add/Add all/In library） |
| `backend/app/providers.py` | 批6：服务商目录（16 家预置 + protocol 常量 + 查询辅助函数） |
| `backend/app/api/settings.py` | 批6：设置 API（目录端点 `/api/settings/providers`、protocol 校验/派生、probe） |
| `backend/app/llm/base.py` | LLM 传输层（批6 起按 `protocol` 分发、目录默认 BaseURL） |
| `frontend/src/pages/SettingsPage.tsx` | 批6：设置页（目录驱动 provider 下拉、协议提示、自动路由默认模型） |
| `frontend/src/pages/ResultPage.tsx` | 三栏 master–detail 结果页 |
| `frontend/src/components/ReviewSidebar.tsx` | 右侧知识点整理栏（Explanation/Vocabulary/AI/Export） |
| `/tmp/e2e/` | E2E harness：`servers.mjs` + `run.mjs` / `run2.mjs` / `run3.mjs` / `run4.mjs` |

## 8. 批6 — 服务商目录：已完成 ✅（未提交）

**目标**：provider ≠ 协议——provider 是**提供 BaseURL 的服务商**（预置主流服务商目录），OpenAI/Anthropic 是 **protocol**（API 协议）。

- `backend/app/providers.py`：16 家预置，**OrcaRouter 列第一**，每项 `{id, name, base_url, protocol, default_model, note}`；`PROTOCOLS = (openai, anthropic)`；辅助函数 `get_provider` / `default_base_url` / `default_protocol` / `provider_ids`
- **BaseURL 官网核对（2026-10-06）**：
  - OrcaRouter `https://api.orcarouter.ai/v1`（+ `orcarouter/auto`）、OpenPaths `https://openpaths.io/v1`（+ `openpaths/auto`）、OpenRouter `https://openrouter.ai/api/v1`（+ `openrouter/auto`）
  - Groq `api.groq.com/openai/v1`、Fireworks `api.fireworks.ai/inference/v1`、NVIDIA `integrate.api.nvidia.com/v1`、Moonshot `api.moonshot.cn/v1`、DashScope 美国区 `dashscope-us.aliyuncs.com/compatible-mode/v1`
  - **⚠ MiniMax 修正**：用户给的 `api.minimax.chat` 非现官网 OpenAI 兼容端点 → 用 CN `api.minimaxi.com/v1`（国际 `api.minimax.io/v1`，note 中提示）
- 存储：`settings` 表新增 `protocol` 键（KV 无 schema 变更）；`PUT` 设 provider 时派生 protocol，**显式 `protocol` 参数优先**（provider+protocol 同传时显式值生效）；老库无 protocol → `_load()`/`_config()` 按 provider 派生
- `GET /api/settings/providers` 返回目录；`POST /api/settings/test`：显式给 provider 时 WYSIWYG 用该 provider 的协议与默认 BaseURL（避免残留配置串扰）、空 BaseURL 回落官方默认、custom 无基址友好报错
- `llm/base.py`：`complete()` 按 `cfg["protocol"]` 分发（不再看 provider 名）
- 前端 `SettingsPage.tsx`：`api.listProviders()` 目录驱动下拉（加载中占位）、切 provider 时仅在原值为空/等于上一个预设时替换 BaseURL（手改的自定义 URL 保留）、网关类自动填默认模型、协议说明与 note 提示
- 测试：pytest 113→**121**（settings +6、llm +2）；`test_settings_api.py` 加 autouse `clean_settings`（settings 为全局 KV，按测试隔离，消除 session 级共享库串扰）
- E2E：run/run2/run3/run4 四套全过（run2 覆盖设置页 UI；run3 验证 `PUT openai` 兼容）
