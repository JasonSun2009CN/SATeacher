# SATeacher

> 本地优先（local-first）的 SAT 自动刷题助手：**导入 PDF/DOCX 题库 → 补录答案 → Bluebook 风格全屏练习 → 错题复盘/知识点整理 → 生词本 → 导出 PDF/DOCX**。

![License](https://img.shields.io/badge/license-Apache--2.0-blue)
![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Vite](https://img.shields.io/badge/Vite-7-646CFF?logo=vite&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-4-38B2AC?logo=tailwindcss&logoColor=white)
![Tests](https://img.shields.io/badge/pytest-164%20passed-2E7D32)

**English**: [README.en.md](README.en.md)

---

## 目录

- [它是什么](#它是什么)
- [核心特性](#核心特性)
- [两条铁律](#两条铁律)
- [环境要求](#环境要求)
- [快速开始](#快速开始)
- [使用方法](#使用方法)
  - [1. 导入题库](#1-导入题库)
  - [2. 录入答案](#2-录入答案)
  - [3. 全屏练习](#3-全屏练习)
  - [4. 结果与复盘](#4-结果与复盘)
  - [5. 导出](#5-导出)
  - [6. 设置 LLM](#6-设置-llm)
- [可选功能](#可选功能)
- [配置与环境变量](#配置与环境变量)
- [开发与测试](#开发与测试)
- [项目结构](#项目结构)
- [常见问题排查](#常见问题排查)
- [相关文档](#相关文档)
- [License](#license)

---

## 它是什么

SATeacher 是一个**跑在你自己电脑上的 Web 应用**（FastAPI 后端 + React 前端 + SQLite 单文件）。
把 SAT 题库 PDF / Word 文档拖进来，它会在**本地、不花任何 token** 的情况下解析成结构化题目，
然后给你一个 Bluebook 风格的全屏练习界面；做完自动判分，右侧边栏可以写解析、攒生词本、（显式点击时）调用 AI 讲解，最后导出成 PDF/DOCX。

```
导入 PDF / DOCX / .md ──► 本地解析（0 token）──► 补录答案
        ──► Bluebook 全屏练习 ──► 判分 + 三栏复盘 ──► 生词本 / 解析 ──► 导出 PDF·DOCX·xlsx
```

## 核心特性

| 模块 | 能力 |
|---|---|
| **导入** | PDF（PyMuPDF 确定性转换：分栏/题号/选项/**答案键回填**/图片抽取）、DOCX（段落/表格/图片 + zip 安全校验）、`.md` / `.sat.md`、**扫描件 OCR**（macOS Vision 或系统 `tesseract`）、导入流水线（逐页报告、可取消）、上限 60 MB |
| **内置题库** | `SAT机考25年语文合集（下）` **44 个单元 / 1186 题**，离线一键 **Add** / **Add all**，0 token，幂等 |
| **资料库** | 文档列表（题数、已作答数、答案状态）、练习历史、删除（级联） |
| **答案录入** | 逐题 A–D 网格 + **批量粘贴**（`1-A 2-C` / `1. A` / `ACBDA`）+ 校验 + 预览，同步回写源文件 |
| **练习** | Bluebook 风格全屏、计时、单题视图、题号导航、标记、键盘 `A–D` / `← →`、交卷确认 |
| **结果 / 复盘** | 得分/分 section/用时统计、All · Correct · Wrong 过滤、三栏 master–detail、补键重判（regrade） |
| **侧边栏** | 手写解析（直存本地）、生词表 `Word \| Meaning \| Notes`（增删改 + 导出 .xlsx）、**AI 讲解**（显式触发）、导出入口 |
| **导出** | **PDF**（WeasyPrint，页脚页码、图片、MathJax SVG 公式）、**DOCX**（python-docx）、生词本 **.xlsx** |
| **设置** | 16 家 LLM 服务商目录、protocol（openai/anthropic）、Base URL、API Key（掩码）、模型、连通性测试 |

## 两条铁律

1. **LLM 不在主链路**：导入/解析/判分/导出全部是确定性本地计算，**0 token**；只有你在复盘页显式点了 **AI Answer**（或手动点了连通性测试）才会调用外部 API。
2. **本地优先**：所有数据都在仓库的 `data/` 目录（`app.db` + 每篇文档的 `doc.sat.md` 和图片），不上传任何云端。

## 环境要求

| 依赖 | 版本 | 用途 |
|---|---|---|
| Python | **3.11+**（实测 3.13） | 后端 |
| Node.js | **18+** | 前端构建 / dev server；（可选）导出公式渲染 |
| `pip install -r backend/requirements.txt` | — | fastapi · uvicorn · pymupdf · httpx · weasyprint · python-docx · openpyxl · cairosvg … |
| `npm install`（`frontend/`） | — | React 19 + Vite 7 + Tailwind 4 |

<details>
<summary><b>WeasyPrint（PDF 导出）需要的系统库</b></summary>

PDF 导出依赖 pango/cairo/gdk-pixbuf/harfbuzz：

```bash
# macOS
brew install pango cairo gdk-pixbuf harfbuzz

# Debian / Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 libharfbuzz0b
```

未安装时**只有 PDF 导出会失败**，其余功能不受影响。
</details>

## 快速开始

```bash
git clone https://github.com/JasonSun2009CN/SATeacher.git
cd SATeacher

./scripts/dev.sh
```

`scripts/dev.sh` 会自动：创建 `.venv` → 安装后端依赖 → `npm install` → 同时启动前后端。看到下面两行即成功：

- 后端 API：<http://localhost:8000>（健康检查 <http://localhost:8000/api/health>）
- 前端页面：<http://localhost:5173> ← **浏览器打开这个**

按 `Ctrl-C` 同时停止两端。

<details>
<summary><b>不用 dev.sh 的手动启动方式</b></summary>

```bash
# 1) 后端（终端 A）
python3 -m venv .venv
. .venv/bin/activate
pip install -r backend/requirements.txt
uvicorn app.main:app --app-dir backend --reload --port 8000

# 2) 前端（终端 B）
cd frontend
npm install
npm run dev
```

> 当前应用通过 Vite dev server 提供页面（后端只提供 `/api`）。`npm run build` 产出的 `frontend/dist/` 可用于类型检查与产物验证。
</details>

## 使用方法

> 界面为英文，下面保留按钮/页面的英文原文方便对照。

### 1. 导入题库

打开 <http://localhost:5173>（Import 页，即首页）。

1. **上传文件**：把文件拖到 *Drag a file here* 区域，或点 **choose a file**。
   支持 `PDF · DOCX · .md · .markdown · .sat.md`（≤ 60 MB；题目需带编号 `1.` `2.` …，每题四个选项）。
2. **等待流水线跑完**：`detect → convert → review` 三阶段，附**逐页 PageReport**（该页是文本/OCR/低置信/无引擎）。
   - 转换结果干净 → 自动提交入库；
   - 有疑点 → 停在复核阶段，由你点 **Commit** 落库或 **Cancel** 取消（全程 0 token）。
3. **（可选）用内置题库**：Import 页的题库卡展开后按日期分组列出 44 个单元，单个点 **Add**，或点 **Add all** 整库导入；已添加的显示 **✓ In library**，可直接跳到练习页。
4. **查看 Library**：导入完成后页面下方的 Library 列出所有文档，每条有 **Practice** / **Answers** / **Delete** 三个入口。

<details>
<summary>没有题库文件？自己写 SAT-MD</summary>

Import 页的 *SatMdTemplate* 提供 `.sat.md` 模板（可复制/下载），按模板手写题目后上传即可导入。
</details>

### 2. 录入答案

文档解析出题目但**答案键缺失/不全**时（列表里会提示），点 **Answers** 进入 `/doc/:id/answers`：

- **逐题网格**：每题点 A/B/C/D；
- **Bulk entry 批量粘贴**：输入框支持 `1-A 2-C 3-D`、`1. A`、`12B`、裸字母串 `ACBDA`，点 **Apply to grid** 一次性填充；
- 保存时自动校验（只接受 A–D），并同步回写 `doc.sat.md`；**Preview** 区可先检查再保存。

> 也可以先不录答案直接练习：交卷后会引导你来这页补录，保存后自动重判（regrade）。

### 3. 全屏练习

Library 中点 **Practice** 进入开始屏：

1. 开始屏显示 *Ready to begin* + 题目数量，点 **Begin — enter fullscreen** 进入全屏，**计时从此刻开始**（也可先点 *Enter answers first (optional)* 去补录答案）；
2. 作答方式：
   - 鼠标点选项，或按键盘 **`A` `B` `C` `D`**；
   - **`←` `→`** 切换上/下一题；
   - 底部题号面板可任意跳题；
   - **Mark for review** 标记当前题（面板中显示标记色，再次点击取消）；
3. 做完点 **Submit** → 弹确认框 → 再点 **Submit** 交卷判分。

### 4. 结果与复盘

交卷后进入 `/session/:sid/result`：

- **统计面板**：Score（得分率）、Reading & Writing、Math、Time，以及 **Wrong answers** 错题 chips（点击直接跳到该题）；
- **过滤 Tab**：`All` / `Correct` / `Wrong`；
- **三栏布局**：左侧题号索引（状态色）→ 中间单题区（`←` `→` 键盘切题、`n / total`）→ 右侧常驻 **ReviewSidebar**；
- 顶部按钮：**Practice again**（重做）/ **Back to library** / **Hide panel · Show panel**；
- 文档没有答案键时，此处会先引导补录答案再判分。

**ReviewSidebar（右侧工作区）**：

| 分区 | 用法 |
|---|---|
| **Explanation** | 给当前题手写解析，点保存直接入库（0 token） |
| **Vocabulary** | 生词表，列 `Word \| Meaning \| Notes`，可增删行/列、编辑后保存；**Export .xlsx** 导出（openpyxl，Numbers/Excel 可开） |
| **AI Answer** | 显式点击才调用 LLM（题干 + 正确选项作为上下文）；未配置 Key 或该题无答案会给出对应提示 |
| **Export** | **Export .pdf** / **Export .docx**，导出题目、答案与解析（不经过 AI） |

### 5. 导出

- **整份文档**：Result 页右侧边栏 **Export** 分区 → `Export .pdf` 或 `Export .docx`；
  - PDF：A4、页脚页码、内嵌图片、数学公式走 MathJax SVG；
  - DOCX：标题/段落/答案键/解析/生词表，公式经 cairosvg 转 PNG。
- **生词本**：Vocabulary 分区的 **Export .xlsx**。

### 6. 设置 LLM

**（可选）** 点击 Import 页右上角的 **⚙ Settings**（`/settings`）——**不配置也能完整使用**，只有 AI 讲解需要：

1. **Provider** 下拉选择服务商（内置 16 家目录，含 Base URL 与默认模型）；
2. **Base URL** 可覆盖（切 Provider 时仅在你没手改过的情况下自动填）；
3. **API Key** 只写不回显（掩码显示）；
4. **Model** 填模型名（网关类服务商会自动填默认模型）；
5. 点 **Save settings** 保存，点 **Test connection** 做连通性测试；协议（openai / anthropic）由 Provider 派生，也可显式指定。

## 可选功能

| 功能 | 说明 | 安装 |
|---|---|---|
| **扫描 PDF OCR** | 逐页检测文本密度，低密度页栅格化后识别，坐标归一回原管线 | 任选其一：系统 `tesseract`（`brew install tesseract` / `sudo apt install tesseract-ocr`，零 Python 依赖）；或 macOS 上 `pip install pyobjc-framework-Vision`（用系统 Vision）。未安装时导入页会给出提示，不会崩溃 |
| **导出数学公式** | TeX → SVG（PDF 内联 / DOCX 转 PNG） | `cd backend/app/export/mathjax && npm install`（需要 Node；缺失时公式**降级为纯文本**，导出不失败） |

导入页顶部会显示当前可用的 OCR 引擎（来自 `/api/health` 的 `ocr` 字段）。

## 配置与环境变量

| 变量 | 默认值 | 作用 |
|---|---|---|
| `SATEACHER_DATA` | `./data` | 数据根目录（`app.db`、`docs/<id>/`、`tmp/`、`exports/`、`jobs/`）。测试会用临时目录隔离 |
| `SATEACHER_API` | `http://localhost:8000` | Vite 开发代理的后端地址（后端不在本机时改这个） |

端口：后端 `8000`、前端 `5173`。

> ⚠️ `data/` 是真实数据目录（已被 `.gitignore` 忽略），清空前请先备份。

## 开发与测试

```bash
# 后端测试（基线 164 passed，用临时数据目录，不动你的数据）
cd backend && ../.venv/bin/python -m pytest -q

# 前端类型检查 + 构建（0 错误）
cd frontend && npm run build

# 本地开发（后端 :8000 + 前端 :5173）
./scripts/dev.sh
```

## 项目结构

```
SATeacher/
├── backend/
│   ├── app/
│   │   ├── main.py            FastAPI 装配（/api/health、6 个 router）
│   │   ├── api/               documents · imports · builtin · sessions · settings · ai
│   │   ├── convert/           pdf · docx · bluebook · normalize · ocr/ · llm_fallback
│   │   ├── satmd/             SAT-MD 解析（确定性状态机）
│   │   ├── export/            PDF (WeasyPrint) · docx · math_render(+mathjax 桥)
│   │   ├── repos/ · llm/      持久化 · LLM 传输层
│   │   ├── providers.py       16 家服务商目录
│   │   └── builtin/           内置题库（44 单元随仓库分发）
│   ├── tests/                 pytest（164）
│   └── requirements.txt
├── frontend/                  Vite + React 19 + TS + Tailwind 4
│   └── src/pages/             Import · AnswerKey · Practice · Result · Settings
├── scripts/dev.sh             一键起前后端
├── data/                      运行期数据（gitignore）
└── docs/                      ARCHITECTURE · PLAN · SAT-MD · RENOVATION_PLAN
```

## 常见问题排查

| 现象 | 解决 |
|---|---|
| `dev.sh` 报端口被占用 | `lsof -i :8000` / `:5173` 找到进程并结束，或换端口启动 |
| 页面一直 Loading / 提示连不上后端 | 确认后端活着：<http://localhost:8000/api/health> 应返回 `{"status":"ok",...}`；前端指向其他后端时设置 `SATEACHER_API=http://host:port` 后重启 vite |
| 导入扫描 PDF 提示需要 OCR | 安装 `tesseract`（任意平台），或 macOS 上 `pip install pyobjc-framework-Vision`，重启后端后重新导入 |
| DOCX 导入被拒绝 | 上传前做了 zip 安全校验（条目数/解压总量/压缩比/宏），异常或加密文档会被拒；请用正常导出的 `.docx` |
| PDF 导出失败 | 安装 WeasyPrint 系统库（见[环境要求](#环境要求)折叠块） |
| 导出里公式变成纯文本 | `cd backend/app/export/mathjax && npm install` 后重试（需要 Node） |
| `npm run build` 报类型错误 | `cd frontend && npm install` 后重跑；仍失败请对照 TS 报错定位 |
| 想从零开始 | 备份后删除 `data/`（或指定 `SATEACHER_DATA` 到新目录），重启后端会自动建库 |

## 相关文档

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — 系统架构、数据模型、API 面（27 条）
- [`docs/PLAN.md`](docs/PLAN.md) — 产品目标、已确认决策、批次交付记录
- [`docs/SAT-MD.md`](docs/SAT-MD.md) — SAT-MD 题目格式规范
- [`docs/RENOVATION_PLAN.md`](docs/RENOVATION_PLAN.md) — 12 章改造计划（批 7–16）
- [`ROADMAP.md`](ROADMAP.md) — 路线图与已知缺口
- [`HANDOFF.md`](HANDOFF.md) — 项目交接状态（维护者/AI agent 用）

## License

[Apache License 2.0](LICENSE)
