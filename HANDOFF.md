# SATeacher — HANDOFF（交接文档）

> 面向后续会话 / AI agent 的项目交接。生成于 2026-10-06，**项目状态变化后须同步更新本文件**。
> 配套文档：`docs/PLAN.md`（决策与批次交付的权威记录）、`docs/SAT-MD.md`（satmd 格式规范）。

## 1. 项目概览

SAT 自动刷题助手（本地 Web 应用）：**导入 PDF 题库 → 补录答案 → Bluebook 风格全屏练习 → 错题分析/知识点整理 → 生词本 → 多格式导出**。

- 技术栈：FastAPI + React（Vite / TypeScript / Tailwind），SQLite 单文件，PyMuPDF 转换
- **铁律**：LLM 不在主链路（导入 0 token，AI 只在用户显式点击时花钱）；界面全英文；与用户交流用中文；**有疑问必须用 question 工具问用户，不许自己猜**
- 依赖基线：`fastapi uvicorn pymupdf python-multipart httpx pytest`（+ `openpyxl` 已批准）

## 2. Git 状态（2026-10-06）

```
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
| `??` | `scripts/build_builtin.py`、`backend/app/builtin/`、`backend/app/api/builtin.py`、`backend/tests/test_builtin.py`、`frontend/src/components/BuiltinBankCard.tsx`、`HANDOFF.md` 等 | **批5 产物，已完成未提交** |

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
| 批5（未提交） | 内置题库：5A 离线构建脚本 44/44 单元（1186题+1186答案+17图）｜5B `documents.builtin_key` 迁移 + `app/api/builtin.py`（列表/单加/add-all、幂等）｜5C 导入页 `BuiltinBankCard`（折叠卡→日期分组→Add/Add all/✓In library 跳练习页） | pytest 113（+6）；E2E run4 新增全过；run/run2/run3 回归过 |

基线：**113 pytest 全过**；`npm run build` 0 错误；E2E 四套（run/run2/run3/run4）全过。

## 4. 运行与验证命令

```bash
# dev（用户日常在用 :5173 + :8000，勿杀）
scripts/dev.sh            # 或分别起 uvicorn / vite

# 后端测试（从 backend/ 跑）
cd backend && ../.venv/bin/python -m pytest -q        # 基线 113

# 前端构建（tsc + vite）
cd frontend && npm run build

# E2E（自带私有实例，不碰 dev）
cd /tmp/e2e && node run.mjs      # 导入→练习→判分→重做
cd /tmp/e2e && node run2.mjs     # 答案录入/图片/设置
cd /tmp/e2e && node run3.mjs     # 27题全流程 + 结果页三栏 + 侧边栏 + mock LLM
cd /tmp/e2e && node run4.mjs     # 内置题库：卡片/分组/单加/幂等/Add all/In library 跳转
```

**dev 库（`data/app.db`）勿动**：1 个用户文档（id=22，25年北美）+ 4 个用户验收空会话。

## 5. 批5 — 内置题库：已完成 ✅（待提交）

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
| `backend/app/satmd/parser.py` | `parse` / `set_answer`（答案注入前必须先 parse 取 `q.ext_id`/`q.no`） |
| `backend/app/api/builtin.py` | 批5B：内置题库 API（列表/单加/add-all，幂等） |
| `backend/app/builtin/` | 批5A 构建输出（44 单元 + manifest，随仓库分发） |
| `scripts/build_builtin.py` | 批5A 离线构建脚本（可幂等重建整库） |
| `backend/tests/test_builtin.py` | 批5B 测试（6 个） |
| `frontend/src/pages/ImportPage.tsx` | 导入页（批5C 题库卡挂载点 `refreshAll`） |
| `frontend/src/components/BuiltinBankCard.tsx` | 批5C 题库卡（折叠/日期分组/Add/Add all/In library） |
| `frontend/src/pages/ResultPage.tsx` | 三栏 master–detail 结果页 |
| `frontend/src/components/ReviewSidebar.tsx` | 右侧知识点整理栏（Explanation/Vocabulary/AI/Export） |
| `/tmp/e2e/` | E2E harness：`servers.mjs` + `run.mjs` / `run2.mjs` / `run3.mjs` / `run4.mjs` |
