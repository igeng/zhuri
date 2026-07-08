<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue?style=flat-square" alt="version">
  <img src="https://img.shields.io/badge/python-3.10+-green?style=flat-square" alt="python">
  <img src="https://img.shields.io/badge/license-MIT-orange?style=flat-square" alt="license">
  <img src="https://img.shields.io/badge/tests-184%20passed-brightgreen?style=flat-square" alt="tests">
  <img src="https://img.shields.io/badge/framework-free-red?style=flat-square" alt="zero framework">
</p>

<h1 align="center">zhuri (逐日)</h1>

<p align="center">
  <em>夸父逐日，日夜不息。</em><br>
  <em>零框架依赖的多智能体长周期自主研究编排器。</em>
</p>

<p align="center">
  <strong>启动它，离开，回来时论文已经写好了。</strong>
</p>

---

## zhuri 是什么？

`zhuri` 是一个**零框架依赖的多智能体编排器**，实现了 **Deli_AutoResearch** 协议：
一个终端优先的驱动器（风格类似 Claude Code / OpenCode），用于运行**长周期、零交互**
的自主研究/编码任务。

> *"它不交付可执行代码，而是交付经过实战检验的约定。"*
> — Deli_AutoResearch SKILL.md

### 解决了什么问题？

| 问题 | zhuri 的解法 |
|------|------------|
| 认知循环（反复尝试相同方向） | 方向多样性 + 强制结构转向 |
| 假活（看起来在跑，实际停了） | 3 层心跳看门狗（L0/L1/L2） |
| 运行时脆弱（崩溃=进度丢失） | 文件持久化，无 resume |
| LLM 编造引用 | ArXiv + Semantic Scholar 真实搜索 |
| 无限烧 API 额度 | 无法改善时自动停止 |

### 设计立场

- **不用任何智能体框架**——不用 crewai/langgraph/langchain/autogen/llama-index
- **文件系统通信**——Agent 是独立的操作系统进程
- **零交互**——一旦确认，绝不再问（B1 原则）

详细规格：[`SPEC.md`](./SPEC.md)
使用教程：[`TUTORIAL_zh.md`](./TUTORIAL_zh.md)
English: [`README.md`](./README.md) · [`TUTORIAL.md`](./TUTORIAL.md)

---

## 快速开始

### 1. 安装

```bash
git clone git@github.com:igeng/zhuri.git
cd zhuri
pip install -e .                # 可编辑模式（推荐）
pip install -e '.[dev]'         # 含 pytest + coverage
```

### 2. 配置

```bash
mkdir -p ~/.config/zhuri
cp examples/config.toml ~/.config/zhuri/config.toml
```

编辑配置文件。**始终使用 `${ENV_VAR}` ——永远不要硬编码密钥。**

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-v4-flash", "deepseek-v4-pro"]

[agents.work]
provider = "deepseek"
model    = "deepseek-v4-pro"
```

在 shell profile 中设置环境变量（`~/.bashrc`）：

```bash
export DEEPSEEK_API_KEY="sk-your-key"
export MOONSHOT_API_KEY="sk-your-key"
```

### 3. 验证

```bash
zhuri config check              # 语法 + provider 校验
zhuri doctor                    # 在线探测 API Key
```

### 4. 运行

```bash
zhuri "你的研究问题" --yes                     # 前台运行，实时监控
zhuri "你的研究问题" --yes --synthesize         # 跑完自动综合
zhuri "你的研究问题" --yes --detach --synthesize  # 后台无人值守
zhuri                                            # 交互式 REPL
```

---

## 启动方式

| 方式 | 命令 | 场景 |
|------|------|------|
|  快速 | `zhuri "问题" --direct --yes` | 单次 LLM 调用，立刻出结果 |
|  前台 | `zhuri "任务" --yes` | 实时监控，默认最多 30 轮 |
|  后台 | `zhuri "任务" --yes --detach` | 跑几小时/天，用 `zhuri status` 查看 |
|  自动综合 | `zhuri "任务" --yes --detach --synthesize` | 后台 + 自动出文档 |
|  REPL | `zhuri` | 交互式会话，多任务管理 |

**产物在哪里？** `.zhuri/tasks/<task-id>/state/deliverable.md`

---

## 架构

```
┌── 编排器（监控 → 检测停滞 → 注入方向）─────┐
│  · 方向多样性 — 绝不重复相同的结构轴        │
│  · 自动转向 (stale≥2) → 升级 (≥4) → 自停 (≥8) │
│  · 评审→弱点→子技能 反馈闭环                │
└────┬─────────────┬─────────────┬────────────┘
  [任务 A]      [任务 B]      [任务 C]   ← 独立子进程

┌── 心跳看门狗（3 层）──┐
│ L0  常驻守护（无会话）  │
│ L1  定时巡逻（重启/推动） │
│ L2  业务循环自检        │
└───────────────────────┘

┌── 工作代理（每轮迭代）──────┐
│ 1. 预搜索 ArXiv + Semantic Scholar │
│ 2. LLM 轮次（≤15 / ≤30 分钟）      │
│ 3. 追加 findings 到 state/         │
│ 4. 退出 — 进程不可复用             │
└────────────────────────────────┘
```

---

## 核心功能

###  学术论文搜索

每轮工作迭代前自动搜索 **ArXiv** + **Semantic Scholar**
获取真实论文（两个 API 均免费、无需认证）。引用基于真实出版物，
而非模型训练数据。用 `--no-search` 禁用。

###  子技能任务包

内置论文写作包，含 5 个子技能，每个编码了专家工作流：

| 子技能 | 方向键 | 流水线 |
|--------|--------|--------|
|  文献调研 | `subskill:literature` | Recall → LQS 评分 → A/B/C/D 分级 → 会场升级 |
|  论文结构 | `subskill:structure` | 章节架构 + 段落模式 + MECE 分类 |
|  实验设计 | `subskill:experiment` | 设计 → 执行(API/GPU) → 迭代(≤5) → 报告 |
|  学术图表 | `subskill:figures` | Booktabs 表格 + 矢量图 + 质量清单 |
|  同行评审 | `subskill:review` | 5 个 persona → 中位数评分 → 弱点路由 |

###  实时监控与自动停止

终端实时输出执行进度。编排器在任务无法改进时自动停止：

| 阈值 | 值 | 动作 |
|------|-----|------|
| 转向 | stale ≥ 2 | 强制切换结构轴 |
| 升级 | stale ≥ 4 | 标记需人工关注 |
| 自动停止 | stale ≥ 8 | 停 — 无法继续推进 |

###  REPL 交互（支持多行粘贴）

```
❯ 写一篇关于大模型后训练在HPC领域应用的综述...

❯ /status          # 查看所有任务
❯ /synthesize      # 合并 findings → deliverable.md
❯ /limits          # 查看所有阈值
❯ /set-iters 0     # 无限制迭代
❯ /quit
```

---

## 命令速查

| 命令 | 用途 |
|------|------|
| `zhuri "提示词" [--yes] [--direct] [--synthesize] [--detach] [-v]` | 入口 A：一键任务 |
| `zhuri` | 入口 B：交互式 REPL（主要方式） |
| `zhuri init <目录> [--template ...]` | 入口 C：创建任务脚手架 |
| `zhuri run <目录> [--interval 2h] [--max-iters N] [--once]` | 编排器循环 |
| `zhuri synthesize <任务目录>` | 合并 findings → deliverable.md |
| `zhuri watchdog <目录> [--interval 1h]` | L1 巡逻看门狗 |
| `zhuri guard <目录>` | L0 常驻守卫 |
| `zhuri work <任务目录> --direction "方向"` | 单次工作迭代 |
| `zhuri status <目录> [--watch] [--json]` | 只读状态查看 |
| `zhuri logs <任务目录> [--source ...] [--follow]` | 只读日志查看 |
| `zhuri config [get\|set\|path\|check]` | 管理提供商/智能体/密钥 |
| `zhuri doctor` | 验证环境、认证、依赖 |

---

## 能做什么？

| 任务类型 | 示例 |
|----------|------|
|  深度调研综述 | "研究大模型 agent 强化学习，给我一份深度调研综述" |
|  科研论文写作 | 完整流水线：文献 → 结构 → 实验 → 评审 |
|  代码分析 | "分析这个代码库，生成带优先级的重构方案" |
|  技术文档 | "为这个项目生成 API 参考文档" |
|  竞品分析 | "对比前 5 大向量数据库，推荐最优方案" |
|  数据分析 | "分析数据集，生成统计摘要和可视化方案" |
|  架构设计 | "为电商平台设计微服务架构方案" |

---

## 配置

双层模型：**providers**（有哪些端点）+ **agents**（哪个角色用什么模型）。

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-v4-flash", "deepseek-v4-pro"]

[agents.work]       # 干活的主力，用最强模型
provider = "deepseek"
model    = "deepseek-v4-pro"

[agents.review]     # 评审用不同厂商（防膨胀）
provider = "kimi"
model    = "kimi-k2.5"
```

解析顺序：`[agents.<角色>]` → `[agents.default]` → 报错。

---

## 状态文件

```
<任务>/state/
├── task_spec.md            # 目标 / 里程碑 / 成功标准
├── progress.json           # 迭代、状态、停滞计数、心跳
├── findings.jsonl          # 追加式可验证发现
├── directions_tried.json   # 多样性基础（每条的结构轴）
├── deliverable.md          # ★ 最终综合文档
└── iteration_log.jsonl     # 每轮迭代摘要
<任务>/logs/
├── work.jsonl              # 标记 level=decision 的决策
├── orchestrator.jsonl
└── heartbeat.jsonl
```

---

## 开发

```bash
pip install -e '.[dev]'
pytest                               # 184 测试
pytest --cov=zhuri --cov-report=term-missing
```

护栏规则：禁止 agent 框架依赖（A9）、文件 ≤ 300 行（EC1）、
运行路径禁止 `input()`（B1/A12）、覆盖率 ≥ 85%。

---

## 许可证

MIT © zhuri contributors

---

<p align="center">
  <sub>☀️ 逐日 ☀️</sub>
</p>
