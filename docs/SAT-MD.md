# SAT-MD 格式规范 v1

SATeacher 的**中间交换格式**。所有导入的文档（PDF/DOCX/MD）先转成 SAT-MD，
再由确定性解析器转成 JSON 入库。**这条链路不消耗 LLM token。**

状态：`v1 draft`（实现前需确认 §7 未决项）

---

## 1. 文件约定

| 项 | 规则 |
|---|---|
| 扩展名 | `.sat.md` |
| 编码 | UTF-8，LF 换行 |
| 图片 | 存放在与 `.sat.md` 同级的 `assets/` 目录，MD 中用相对路径引用 |
| 一文档一文件 | 一份导入的源文档 = 一个 `.sat.md` + 一个 `assets/` |

## 2. Front matter（必需）

```yaml
---
satmd: 1                      # 格式版本号，必需
title: "2024 International School Final"
source: "final-2024.pdf"      # 原始文件名，溯源用
lang: en                      # 题目语言：en | zh | mixed
imported_at: "2026-10-05T12:00:00Z"
answers: none                 # inline | external | none（见 §5）
---
```

- `satmd` 版本不符 → 解析器直接拒绝并报错，不做降级猜测。
- front matter 之外、题目块之外的自由文本一律忽略（转换器用它放备注，用 `<!-- -->` 注释）。

## 3. 题目块 `:::q`

每题独立成块（**不存在跨题共享的 passage 块**；题干自带的阅读材料放在 `@material` 区）。

### 3.1 语法（按行的状态机）

```
:::q {#Q001 sec=rw}      ← 块开始：id + 属性
@material                  ← 可选：本题自带材料（阅读段落/图表说明）
……材料正文……
@stem                      ← 可选但强烈建议：题干起点
……题干正文……
- A. 选项一                 ← 固定 4 个选项，A–D，大写字母 + 点
- B. 选项二
- C. 选项三
- D. 选项四
! answer: B                ← 可选元数据，见 §3.3
! explain: 因为第二段……      ← 可选
:::                        ← 块结束
```

- **无任何标记**：块内全部内容都是题干。
- **只有 `@stem`**：`@stem` 之前的内容自动作为材料（`@material` 的简写形式）。
- **`@material` 与 `@stem` 同时出现**：分别界定材料与题干；只有 `@material` 而没有 `@stem` 是错误。
- 选项行必须恰好 4 个，顺序 `A B C D`；解析器遇到数量不对 → **报错，不猜测**。
- 块内禁止出现裸 `:::` 行（除非作为块结束）。

### 3.2 头部属性

| 属性 | 必需 | 取值 | 说明 |
|---|---|---|---|
| `id` | ✅ | `Q` + 数字/字符串，文档内唯一 | 例 `#Q001` |
| `sec` | ✅ | `rw` \| `math` | 语文（阅读与写作）/ 数学 |
| `no` | ⬜ | 整数 | 原卷题号，与 id 分开存 |
| `type` | ⬜ | 自由串 | 如 `vocab` `craft` `algebra` |
| `difficulty` | ⬜ | `e` \| `m` \| `h` | easy / medium / hard |

### 3.3 元数据行 `! key: value`

| key | 说明 |
|---|---|
| `answer` | `A`–`D`。导入时没有就**不写这一行**，由后续答案录入页补 |
| `explain` | 解析/正确理由。可缺省，按需用 LLM 或手写补 |
| `source` | 溯源，如 `p.12` |

- 未知 key **原样保留并透传**（向前兼容），但不参与判分逻辑。

## 4. 数学与图片

- 行内公式 `$x^2$`，独立公式 `$$\frac{a}{b}$$`，前端用 KaTeX 渲染（**不经过 LLM**）。
- 图片：`![图表说明](assets/q003-fig1.png)`，路径相对于 `.sat.md`。
  转换器负责从 PDF 抠图并写入 `assets/`；图片在题干、材料、选项里都可能出现。

## 5. 答案的三种状态（`answers` 字段）

| 值 | 含义 | 后续动作 |
|---|---|---|
| `inline` | 源文档含答案/解析，转换时已填入 `! answer:` | 可直接判分 |
| `external` | 源文档末尾有独立答案表（如 `Answer Key` / `答案`） | 转换器按题号回填 |
| `none` | 源文档无答案 | 导入后进入**答案录入页**：显示题数，逐题或批量粘贴录入 |

`none` → 录入完成 → 落库时写入 questions 表，`.sat.md` 文件同步回写 `! answer:` 并把 `answers` 改为 `external`。

## 6. 示例

### 6.1 阅读题（自带材料，暂无答案）

```markdown
:::q {#Q001 sec=rw no=1 type=vocab difficulty=m}
@material
Despite the committee's reservations, the new policy was adopted
without amendment. Critics called the decision premature; supporters
insisted the data supported action.

@stem
The author's attitude toward the committee is best described as

- A. undisguised contempt
- B. cautious approval
- C. outright indifference
- D. blunt hostility
:::
```

### 6.2 数学题（含公式与图片，有答案）

```markdown
:::q {#Q002 sec=math no=12 difficulty=e}
! answer: B
! explain: 两边同减 5 再同除 3
If $3x + 5 = 20$, what is the value of $x$?

![number line](assets/q002-fig1.png)

- A. 3
- B. 5
- C. 8
- D. 15
:::
```

> 注：`sec=rath` 为笔误示例，正确值为 `sec=math`。

## 7. 设计决议（已确认）

1. 材料内标题不做独立字段，由转换器写成材料首行（如 `**Title — Source**`）。
2. 材料与题干的图片共用 `assets/`，用 `alt` 文本区分归属，不单独建字段。
3. **保序**：题目按块出现顺序存储（`order_idx`），`no` 只记录原卷题号。
4. 选项硬编码为 **恰好 4 个 A–D**，超出或不足一律报错。

## 8. 解析器实现约定

- 单一入口：`parse(text) -> {meta, questions[]}`，纯函数，**不调用 LLM、不做模糊推断**。
- 任何结构错误抛出带行号的 `SatMdError`，导入界面直接展示错误位置。
- 单元测试覆盖：正常块 / 缺选项 / 选项数不对 / 版本不符 / 公式与图片 / `@material` 组合 / 未知 `!` key。
