# zhuri (逐日)

> *逐日* — 源自夸父逐日的神话。`zhuri` 如夸父般不懈追逐长期目标，一轮接一轮，
> 永不停歇直至完成。

`zhuri` 是一个**无框架多智能体编排器**，实现了 **Deli_AutoResearch** 协议：
一个终端优先的驱动器（风格类似 Claude Code / OpenCode），用于运行**长周期、
零交互**的自主研究/编码任务。它**不使用任何智能体框架**（不用 crewai、langgraph、
langchain-agents、autogen 或 llama-index agents）。智能体是**独立的操作系统进程**，
所有智能体间通信**仅通过文件系统**进行。

详细规格请参阅 [`SPEC.md`](./SPEC.md)。
使用教程请参阅 [`TUTORIAL_zh.md`](./TUTORIAL_zh.md)。
English documentation: [`README.md`](./README.md) and [`TUTORIAL.md`](./TUTORIAL.md)

---

## zhuri 能做什么？

zhuri 是一个**通用自主任务执行器**。它不仅限于学术论文写作——任何可以分解为
迭代研究、分析或生成步骤的任务都是其擅长的领域：

| 任务类型 | 示例 |
|---|---|
| **深度调研综述** | "研究大模型 agent 强化学习，给我一份深度调研综述" |
| **科研论文写作** | 完整流水线：文献→结构→实验→图表→同行评审 |
| **代码分析与重构** | "分析这个代码库，生成一份带优先级的重构方案" |
| **技术文档生成** | "为这个项目生成 API 参考文档" |
| **竞品分析** | "对比前 5 大向量数据库，为我们的场景推荐最优方案" |
| **数据分析报告** | "分析数据集并生成统计摘要和可视化方案" |
| **文献综述** | "总结最近 3 年联邦学习领域的研究进展" |
| **架构设计** | "为电商平台设计微服务架构方案" |

### 两种执行模式

| 模式 | 命令 | 行为 |
|---|---|---|
| **直接模式**（一步到位） | `zhuri "提示词" --direct --yes` | 单次 LLM 调用 → 立即出结果 |
| **迭代模式**（深度研究） | `zhuri "提示词" --yes` | 多轮迭代循环 → 深度、验证过的发现 |
| **迭代 + 综合** | `zhuri "提示词" --yes --synthesize` | 迭代后 → 汇总生成最终文档 |

**直接模式** 适合快速问答或范围明确的任务。**迭代模式** 适合复杂开放性任务，
可以从多个视角和结构多样性中获益。

### 实时监控与自动停止

入口 A（`zhuri "提示词" --yes`）现在会展示**实时运行状态**——迭代进度、findings 数量、
停滞信号、结构转向——全程无需交互（符合 B1 零交互原则）。编排器会在 escalated 任务
无法改善时**自动停止**，避免浪费 API 额度。

```bash
zhuri "提示词" --yes -v          # 完整日志：LLM 调用、耗时、token 用量
zhuri "提示词" --yes             # 每轮迭代一行摘要（默认最多 20 轮）
zhuri "提示词" --yes --max-iters 0  # 无限制（靠自动停止判定）
zhuri "提示词" --yes --detach    # 后台运行（不显示监控）
zhuri "提示词" --yes --no-search # 跳过 ArXiv + Semantic Scholar 搜索
```

### 学术论文搜索

每轮工作迭代前自动搜索 **ArXiv** 和 **Semantic Scholar** 获取真实论文（两个 API 均免费、
无需认证）。结果注入 LLM prompt，确保引用基于真实出版物。搜索失败不中断执行。
使用 `--no-search` 可禁用。

### 内置任务包

`zhuri` 配备了可扩展的任务包系统（`tasks/`）。首个任务包是**论文写作**，包含 5 个子技能：

| 子技能 | 说明 |
|--------|------|
| **文献调研** | 4 阶段流水线：Recall → LQS 评分 → A/B/C/D 分级 → 会议升级 |
| **论文结构与逻辑** | 章节架构、段落逻辑模式、MECE 分类法、分层声明 |
| **实验设计** | 设计 → 执行(API/GPU) → 迭代(≤5) → 报告(JSON) |
| **学术图表** | Booktabs 表格、矢量图、质量检查清单、学术配色 |
| **同行评审** | 5 个评审人设、中位数评分、反膨胀规则 |

每个子技能将专家工作流编码到 LLM prompt 中。编排器会自动将评审发现的弱点路由到对应子技能。
详细路线图见 [`SPEC-TODO.md`](./SPEC-TODO.md)。

---

## 快速开始（5 分钟）

### 1. 前提条件

- **Python 3.10+**（检查：`python --version`）
- **pip**（Python 自带）
- **Git Bash**（Windows）或任意终端（macOS/Linux）
- 一个 LLM API Key（DeepSeek / 通义千问 / Kimi / 任何 OpenAI 兼容端点）

### 2. 安装

```bash
# 克隆项目
git clone git@github.com:igeng/zhuri.git
cd zhuri

# 以可编辑模式安装（开发模式）
pip install -e .

# 验证安装
zhuri --help
```

开发环境（含 pytest + 覆盖率）：
```bash
pip install -e '.[dev]'
```

安装后，`zhuri` 命令全局可用。

### 3. 配置 LLM 提供商

zhuri 至少需要配置一个 LLM 提供商。创建配置文件：

```bash
# 方式 A：项目本地配置
mkdir -p .zhuri
cp examples/config.toml .zhuri/config.toml

# 方式 B：全局用户配置
mkdir -p ~/.config/zhuri
cp examples/config.toml ~/.config/zhuri/config.toml
```

编辑配置文件并填入 API Key。

> ⚠️ **安全提醒：永远不要在配置文件中硬编码真实 API Key。**
> 始终使用 `${ENV_VAR}` 语法引用环境变量，将真实的 key 保存在 shell profile 中。

例如使用 DeepSeek：

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-chat", "deepseek-reasoner"]

[agents.default]
provider = "deepseek"
model    = "deepseek-chat"
```

然后在你的 shell profile（`~/.bashrc` / `~/.zshrc` / `~/.bash_profile`）中设置环境变量：

```bash
# 将真实的 key 只保存在环境变量中，不要写入任何文件
export DEEPSEEK_API_KEY="sk-your-deepseek-key"
export QWEN_API_KEY="sk-your-qwen-key"
export MOONSHOT_API_KEY="sk-your-moonshot-key"
```

使配置生效：
```bash
source ~/.bashrc    # 或对应的 profile 文件
```

验证配置：
```bash
zhuri config check    # 检查配置文件
zhuri doctor          # 在线验证 API Key 有效性
```

配置文件查找顺序：`--config 路径` → `$ZHURI_CONFIG` → `./.zhuri/config.toml` → `~/.config/zhuri/config.toml`。

### 4. 开始使用

#### 最快方式：直接模式（立即出结果）

```bash
zhuri "研究大模型 agent 强化学习，给我一份深度调研综述" --direct --yes
```

通过**单次 LLM 调用**直接生成最终文档——无需等待多轮迭代。结果输出到标准输出
并保存到 `state/deliverable.md`。

#### 深度模式：迭代研究

```bash
zhuri "研究大模型 agent 强化学习，给我一份深度调研综述" --yes --synthesize
```

运行多轮迭代研究（探索不同结构轴），然后将所有发现汇总为最终文档。

#### 交互式 REPL（主要交互方式）

```bash
zhuri
```

输入自然语言任务后回车，zhuri 会：
1. 将你的提示词合成为结构化的 `task_spec.md`
2. 展示规格文件供一次性确认
3. 启动编排器，**无人值守**运行

---

## 三种启动任务的方式

三种方式最终都汇聚到同一产物：`state/task_spec.md` + 编排器。

### 入口 A — 一键启动（"提示词即任务"）
```bash
zhuri "研究大模型 agent 强化学习，给我一份深度调研综述" --yes
```
合成结构化 `task_spec.md`，展示一次确认（`--yes` 跳过），然后无人值守运行。
加 `--direct` 立即出结果，加 `--synthesize` 迭代后生成最终文档，加 `--detach` 后台运行。

### 入口 B — 交互式 REPL（主要方式）
```bash
zhuri
```
长驻终端：输入自然语言任务回车——合成规格后**立即前台运行**，逐行输出每轮迭代
进展。斜杠命令仅用于控制：`/status`、`/logs`、`/pause`、`/resume`、
`/pivot <task>`、`/stop`、`/spec`、`/new "提示词"`、`/config`、`/quit`。

### 入口 C — 配置文件/脚手架（可复现/CI）
```bash
zhuri init my-task --template paper-writing   # 或：blank
#   编辑 my-task/state/task_spec.md
zhuri run ./                                    # 编排 base 目录下所有任务
```

---

## 命令速查

| 命令 | 用途 |
|---|---|
| `zhuri "提示词" [--dir D] [--yes] [--direct] [--synthesize] [--detach] [-v]` | 入口 A：一键任务 |
| `zhuri` | 入口 B：交互式 REPL |
| `zhuri --verbose` 或 `zhuri -v` | 入口 B：开启详细日志的 REPL |
| `zhuri --dir <路径>` | 入口 B：指定工作目录的 REPL |
| `zhuri init <任务目录> [--template ...]` | 入口 C：创建任务脚手架 |
| `zhuri run <基础目录> [--interval 2h] [--max-iters N] [--once]` | 编排器循环 |
| `zhuri synthesize <任务目录>` | 将 findings 综合为最终文档 |
| `zhuri watchdog <基础目录> [--interval 1h]` | L1 巡逻看门狗 |
| `zhuri guard <基础目录>` | L0 常驻守卫 |
| `zhuri work <任务目录> --direction "方向" [--max-rounds 15] [--max-minutes 30]` | 执行一次工作迭代 |
| `zhuri status <基础目录> [--watch] [--json]` | 只读状态查看 |
| `zhuri logs <任务目录> [--source ...] [--level ...] [--follow]` | 只读日志尾 |
| `zhuri config [get\|set\|path\|check]` | 管理提供商/智能体/密钥 |
| `zhuri doctor` | 验证环境、认证、依赖 |

全局标志：`-v` / `--verbose` 为任何命令启用实时 stderr 日志输出。

退出码：`0` 正常，`1` 通用错误，`2` 配置错误，`3` 提供商/认证错误。

---

## REPL 斜杠命令

在 zhuri REPL 中可随时使用以下命令：

| 命令 | 说明 |
|---|---|
| `/status` | 显示所有运行中任务的状态 |
| `/logs [work\|orchestrator\|heartbeat]` | 查看指定日志流 |
| `/new "提示词"` | 启动新的并发任务 |
| `/pause` | 暂停编排器调度 |
| `/resume` | 恢复已暂停的任务 |
| `/pivot <任务>` | 强制对任务进行结构性转向 |
| `/stop` | 停止所有运行中的任务 |
| `/spec` | 显示当前 task_spec.md |
| `/synthesize [任务目录]` | 将 findings 综合为最终文档 |
| `/config` | 显示当前提供商配置 |
| `/config verbose on\|off` | 开启/关闭详细日志模式 |
| `/quit` | 退出 zhuri |

这些命令**仅用于控制**——不会违反 B1（运行路径零交互）原则。

---

## 文件通信总线

智能体之间从不共享内存；它们**仅通过文件**通信。每个任务拥有：

```
<任务>/state/
├── task_spec.md            # 目标 / 里程碑 / 成功标准
├── progress.json           # 迭代次数、状态、停滞计数、存活时间戳
├── findings.jsonl          # 追加式可验证发现
├── directions_tried.json   # 多样性基础（每条记录的结构轴）
├── deliverable.md          # 最终综合文档（综合后生成）
└── iteration_log.jsonl     # 每轮迭代摘要
<任务>/logs/
├── work.jsonl              # 标记 level=decision 的决策日志
├── orchestrator.jsonl
└── heartbeat.jsonl
```

每次迭代启动**全新会话**，仅注入精选状态——禁止恢复会话（B4）。写入采用原子操作
（临时文件 + 重命名），加跨进程文件锁，确保并发工作智能体不会损坏状态。

---

## 双层配置

配置分为**端点定义层**（`[providers.*]`）和**角色路由层**（`[agents.*]`）。
这是实现"不同智能体 → 不同密钥/模型"的方式。v1 只提供一种提供商类型：
`openai_compat`（OpenAI 兼容 Chat Completions），可对接通义千问、Kimi（Moonshot）、
DeepSeek 或任何本地 OpenAI 兼容服务器。

角色解析顺序：`[agents.<角色>]` → `[agents.default]` → 报错。
子角色（如 `subagent.verification`）未设置时继承父角色。任意字符串可内插 `${ENV_VAR}`。

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-chat", "deepseek-reasoner"]

[agents.default]
provider = "deepseek"
model    = "deepseek-chat"

[agents.work]            # 工作智能体用最强模型
provider = "qwen"
model    = "qwen-max"

[agents.review]          # 评审用不同供应商，支持模型池
provider = "kimi"
models   = ["kimi-k2-0905-preview", "moonshot-v1-128k"]
```

示例配置文件：[`examples/config.toml`](./examples/config.toml)。

---

## 三层心跳看门狗

业务循环本身不可靠，因此有独立的守护层监控它：

- **L2** — 每个业务循环（编排器 + 工作智能体）在每次回调的**第一个操作**写入 `last_seen`。
- **L1** — 每小时巡逻：重启 `last_seen` 超过 `interval × 3` 的循环；对停滞 > 2 小时
  的任务进行推送；3 次无效推送后升级。
- **L0** — 常驻的、会话无关的守卫：如果心跳停滞 > 2 小时则启动紧急巡逻。

守护层对非自身任务只能执行三种操作：**检查 / 重启 / 推送**——永远不读取
findings 或修改结果（B5）。

---

## 开发

```bash
pip install -e '.[dev]'              # 安装开发依赖
pytest                               # 完整测试套件
pytest --cov=zhuri --cov-report=term-missing
```

CI 强制执行的护栏：禁止智能体框架依赖（A9），单文件不超 300 行（EC1/A11），
运行路径禁止阻塞式 `input()`（B1/A12），看门狗跨任务接口仅限 check/restart/nudge（B5），
覆盖率底线（总体 ≥85%；`state/`、`orchestrator/`、`watchdog/`、`config.py` ≥90%）。

---

## 故障排除

| 问题 | 解决方案 |
|---|---|
| `zhuri: command not found` | 重新运行 `pip install -e .`，或检查 Python Scripts 是否在 PATH 中 |
| `config error: config file not found` | 创建 `.zhuri/config.toml` 或 `~/.config/zhuri/config.toml` |
| `provider error: auth failed` | 检查环境变量：`echo $DEEPSEEK_API_KEY` |
| `zhuri doctor` 报告问题 | 按照 doctor 输出的建议操作 |
| 看不到欢迎横幅 | 横幅需要 TTY 环境；管道/脚本中会优雅降级 |

---

## 许可证

MIT
