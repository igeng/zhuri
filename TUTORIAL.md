# TUTORIAL.md — zhuri 使用手册

本教程详细介绍 zhuri 的所有功能、命令用法和配置方法。

---

## 目录

1. [安装与验证](#1-安装与验证)
2. [配置文件详解](#2-配置文件详解)
3. [直接模式（一步出结果）](#3-直接模式一步出结果)
  - [启动方式速查](#启动方式速查)
4. [迭代模式（深度研究）](#4-迭代模式深度研究)
5. [交互式 REPL 使用](#5-交互式-repl-使用)
6. [任务脚手架与批量运行](#6-任务脚手架与批量运行)
7. [查看任务状态与日志](#7-查看任务状态与日志)
8. [综合模式（合并 findings 为文档）](#8-综合模式合并-findings-为文档)
9. [看门狗配置](#9-看门狗配置)
10. [高级配置：多提供商与模型池](#10-高级配置多提供商与模型池)
11. [典型工作流示例](#11-典型工作流示例)
12. [论文写作任务包（Sub-skill 系统）](#12-论文写作任务包sub-skill-系统)
13. [常见问题](#13-常见问题)

---

## 1. 安装与验证

### 安装

```bash
# 从源码安装
git clone <your-repo-url>
cd zhuri
pip install -e .

# 验证
zhuri --help
```

### 开发模式安装

```bash
pip install -e '.[dev]'
pytest   # 运行完整测试套件
```

### 验证安装成功

```bash
$ zhuri --help
usage: zhuri [-h] [--config CONFIG]
             {init,run,watchdog,guard,work,status,logs,config,doctor,repl,synthesize} ...
```

---

## 2. 配置文件详解

### 配置文件位置

zhuri 按以下顺序查找配置文件（首个找到的生效）：

1. `--config <路径>` 命令行参数
2. `$ZHURI_CONFIG` 环境变量
3. `./.zhuri/config.toml`（当前目录）
4. `~/.config/zhuri/config.toml`（用户全局）

### 创建配置文件

```bash
# 方式一：复制示例到项目本地
mkdir -p .zhuri
cp examples/config.toml .zhuri/config.toml

# 方式二：复制到全局位置
mkdir -p ~/.config/zhuri
cp examples/config.toml ~/.config/zhuri/config.toml
```

### 配置文件结构

配置分为两层：

#### 第一层：提供商定义 `[providers.*]`

定义可用的 LLM 端点：

```toml
[providers.deepseek]
type     = "openai_compat"          # v1 仅支持此类型
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"    # 支持环境变量插值
models   = ["deepseek-chat", "deepseek-reasoner"]

[providers.qwen]
type     = "openai_compat"
base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
api_key  = "${QWEN_API_KEY}"
models   = ["qwen-max", "qwen-plus"]

[providers.kimi]
type     = "openai_compat"
base_url = "https://api.moonshot.cn/v1"
api_key  = "${MOONSHOT_API_KEY}"
models   = ["kimi-k2-0905-preview", "moonshot-v1-128k"]
```

#### 第二层：角色路由 `[agents.*]`

定义每个智能体角色使用哪个提供商和模型：

```toml
[agents.default]              # 未明确指定时的回退
provider = "deepseek"
model    = "deepseek-chat"

[agents.orchestrator]         # 编排器（稳定、低成本）
provider = "deepseek"
model    = "deepseek-chat"

[agents.spec]                 # 任务规格合成
provider = "deepseek"
model    = "deepseek-reasoner"

[agents.work]                 # 工作智能体（用最强模型）
provider = "qwen"
model    = "qwen-max"

[agents.review]               # 评审（用不同供应商以增加多样性）
provider = "kimi"
models   = ["kimi-k2-0905-preview", "moonshot-v1-128k"]
```

### 设置 API Key

```bash
# 设置环境变量
export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxxxxx"
export QWEN_API_KEY="sk-xxxxxxxxxxxxxxxx"
export MOONSHOT_API_KEY="sk-xxxxxxxxxxxxxxxx"

# 持久化（加入 shell 配置文件）
echo 'export DEEPSEEK_API_KEY="sk-xxx"' >> ~/.bashrc
source ~/.bashrc
```

### 验证配置

```bash
# 检查配置文件语法和完整性
zhuri config check

# 验证 API Key 有效性（会发起真实请求）
zhuri doctor

# 查看配置文件路径
zhuri config path

# 查看某个角色的生效配置
zhuri config get --role work --effective
```

---

## 3. 直接模式（一步出结果）

直接模式跳过多轮迭代，通过一次 LLM 调用直接生成最终结果。适合范围明确、
不需要多角度探索的任务。

### 使用方法

```bash
zhuri "你的任务描述" --direct --yes
```

### 参数说明

| 参数 | 说明 |
|---|---|
| `--direct` | 启用直接模式（单次 LLM 调用） |
| `--yes` | 跳过确认步骤，直接执行 |
| `--dir <路径>` | 指定工作目录（默认当前目录） |
| `--config <路径>` | 指定配置文件路径 |
| `-v` / `--verbose` | 启用实时详细日志输出到 stderr |

### 示例

```bash
# 生成调研综述
zhuri "研究大模型 agent 强化学习，给我一份深度调研综述" --direct --yes

# 生成架构设计方案
zhuri "为在线教育平台设计系统架构" --direct --yes

# 指定工作目录
zhuri "分析 React 和 Vue 的优劣对比" --direct --yes --dir ~/projects/research
```

### 输出位置

- 标准输出：直接打印结果
- 文件：`<工作目录>/.zhuri/tasks/<task-id>/state/deliverable.md`

---

## 启动方式速查

zhuri 共有 5 种启动方式。**最终目标都是拿到合并后的综述文档 `deliverable.md`。**

| 方式 | 启动命令 | 确认 | 如何拿到最终文档 |
|------|---------|------|-----------------|
| **REPL 交互** | `zhuri` → `❯ 粘贴任务` | spec + y/N | 跑完后在 REPL 中 `/synthesize` |
| **直接跑** | `zhuri "任务"` | spec + y/N | 跑完后 `zhuri synthesize .zhuri/tasks/<task-id>` |
| **跳过确认** | `zhuri "任务" --yes` | 无 | 跑完后 `zhuri synthesize .zhuri/tasks/<task-id>` |
| **后台运行** | `zhuri "任务" --yes --detach` | 无 | `zhuri status` 等 done → `zhuri synthesize <task-dir>` |
| **后台+综合** | `zhuri "任务" --yes --detach --synthesize` | 无 | 自动合成，直接看 `state/deliverable.md` |

**推荐新手用方式 1 或 2**（能看到过程、有确认步骤）。**熟练后用方式 5**（全自动，最终文档直接到手）。

### flag 说明

| flag | 效果 |
|------|------|
| 无 flag | 显示 spec 供一次性确认（B1 豁免），然后前台监控运行 |
| `--yes` | 跳过确认，直接开始（零交互） |
| `--detach` | 后台运行，终端立即返回 |
| `--synthesize` | 所有迭代完成后，自动合并 findings 为最终文档 |
| `--max-iters N` | 限制最大迭代轮数 |
| `--interval N` | 编排器 tick 间隔秒数（默认 5s） |
| `-v` / `--verbose` | 输出完整 LLM 调用日志 |

### 如何拿到最终文档

无论哪种启动方式，最终产物路径相同：

```
<工作目录>/.zhuri/tasks/<task-id>/state/
├── task_spec.md          # 任务规格
├── findings.jsonl         # 所有中间发现
├── deliverable.md         # ★ 最终综述文档
└── progress.json          # 运行状态
```

**手动合成**（方式 1-4 跑完后执行）：

```bash
# 1. 找到 task-id
ls .zhuri/tasks/

# 2. 合并 findings 为综述文档
zhuri synthesize .zhuri/tasks/task-0001baf93b2d

# 3. 查看结果
cat .zhuri/tasks/task-0001baf93b2d/state/deliverable.md
```

**REPL 内合成**（方式 1）：

```
❯ /synthesize                    # 合并最近一个任务
❯ /synthesize task-0001baf93b2d  # 合并指定任务
```

**自动合成**（方式 5）：加 `--synthesize`，跑完自动调用，无需手动操作。

---

## 4. 迭代模式（深度研究）

迭代模式通过多轮探索不同的结构轴来深入研究问题，适合复杂开放性任务。

### 基本用法

```bash
# 运行迭代（默认 3 轮前台迭代）
zhuri "研究大模型 agent 强化学习，给我一份深度调研综述" --yes

# 指定最大迭代数
zhuri "研究大模型 agent 强化学习" --yes --max-iters 5

# 只运行一次编排器 tick
zhuri "研究主题" --yes --once
```

### 迭代 + 自动综合

```bash
# 迭代完成后自动将 findings 合成为最终文档
zhuri "研究大模型 agent 强化学习" --yes --synthesize --max-iters 5
```

### 后台运行

```bash
# 后台运行（适合长时间任务）
zhuri "写一篇关于 Transformer 的论文" --yes --detach
```

### 迭代过程输出（实时监控）

Entry A 启动后会自动进入**监控模式**（B1 安全：纯展示、不交互），实时展示运行状态：

```
$ zhuri "研究xxx综述" --yes

[zhuri] task_id=task-001  synthesizing spec...
[spec]  task_spec.md done (3.2s)
[orch]  launching orchestrator...
  [running ] iter=1  findings=3   gain
  [running ] iter=2  findings=7   gain
  [pivoting] iter=3  findings=7   stale=2    ← 触发结构转向
  [running ] iter=4  findings=12  gain
  [running ] iter=5  findings=18  gain
  [running ] iter=6  findings=24  gain
  [done    ] iter=7  findings=42  gain
  [work] round 5/15  850 chars  2340ms  findings_this_round=6
  [orch] tick  task=task-001  iteration=5
  [work] ⚠ stall signal — model ended on a question
  [zhuri] task-001 DONE  7 iterations  42 findings
```

每行含义：
- `iter=N`：当前迭代轮次
- `findings=N`：累计发现的 insight 数量
- `gain`：本轮有新发现 / `stale=N`：连续停滞 N 次（≥2 触发结构转向，≥4 升级）
- `[work] round N/15`：工作代理内部的 LLM 调用轮次
- `[orch] tick`：编排器的调度心跳

### verbose 模式（完整日志）

```bash
zhuri "任务" --yes -v    # 所有 LLM 调用、耗时、日志详情输出到 stderr
```

在 REPL 中也可以通过 `/config verbose on` 随时开启。

---

## 5. 交互式 REPL 使用

### 启动 REPL

```bash
# 默认工作目录
zhuri

# 指定工作目录
zhuri --dir ~/projects/research
```

### 提交任务

在 `❯` 提示符后直接输入自然语言任务：

```
❯ 研究大模型 agent 强化学习，给我一份深度调研综述
```

zhuri 会自动：合成 task_spec → 确认 → 前台运行迭代 → 输出结果。

### 斜杠命令

| 命令 | 用途 | 示例 |
|---|---|---|
| `/help` | 显示所有可用斜杠命令 | `/help` |
| `/status` | 查看所有任务状态 | `/status` |
| `/logs [source]` | 查看日志 | `/logs work` |
| `/new "提示词"` | 启动新并发任务 | `/new "对比 PyTorch 和 JAX"` |
| `/pause` | 暂停编排调度 | `/pause` |
| `/resume` | 恢复调度 | `/resume` |
| `/pivot [task]` | 强制结构转向 | `/pivot task-000122b967c7` |
| `/stop` | 停止所有任务 | `/stop` |
| `/spec` | 查看当前任务规格 | `/spec` |
| `/synthesize [task]` | 综合 findings 为文档 | `/synthesize task-000122b967c7` |
| `/config` | 查看配置 | `/config` |
| `/config verbose on\|off` | 开关详细日志 | `/config verbose on` |
| `/quit` | 退出 REPL | `/quit` |

### 斜杠命令详解

#### `/help` — 查看帮助

显示 REPL 中所有可用的斜杠命令及其简要说明。当你不确定有哪些命令可用时，
随时输入 `/help` 即可。

```
❯ /help
Available slash-commands:
  /status              show all task status
  /logs [source]       tail task logs (default: work)
  /new "prompt"        start a new concurrent task
  ...
```

#### `/status` — 查看任务状态

显示当前 REPL 会话中所有已启动任务的运行状态，包括迭代次数、发现数量和
停滞计数。用于了解任务进展是否正常。

```
❯ /status
task-001  running  iter=3 findings=18 stale=0
task-002  running  iter=1 findings=6  stale=0
```

各字段含义：
- `iter=N`：已完成的迭代轮数
- `findings=N`：累计发现总数
- `stale=N`：连续停滞次数（0 表示正常推进）

#### `/logs [source]` — 查看任务日志

显示指定来源的最近 10 条日志。`source` 参数可选，默认为 `work`（工作智能体）。

可用的 source 值：
- `work` — 工作智能体日志（默认）
- `orchestrator` — 编排器日志
- `spec` — 规格合成日志

```
❯ /logs
[14:03:22] [info] work_start axis=framing
[14:03:28] [info] work_done findings=5

❯ /logs orchestrator
[14:03:20] [decision] tick_start iteration=3
[14:03:30] [decision] tick_done action=continue
```

#### `/new "提示词"` — 启动新并发任务

在当前 REPL 会话中启动一个新的并发任务。提示词用引号包裹。新任务会自动
进行规格合成并在前台运行默认轮数的迭代。

```
❯ /new "对比三大云服务商的 GPU 定价"
launched task: .zhuri/tasks/task-000122c4a8e2
running in foreground (B1: zero-interaction)…
[iter 1] axis=framing → gain status=running stale=0
...
```

#### `/pause` — 暂停调度

暂停编排器的自动调度。已在运行的迭代会完成，但不会启动新的迭代。
配合 `/resume` 使用，适合需要临时查看中间结果的场景。

```
❯ /pause
paused
```

#### `/resume` — 恢复调度

恢复被 `/pause` 暂停的编排调度，任务继续自动迭代。

```
❯ /resume
resumed
```

#### `/pivot [task-id]` — 强制结构转向

当任务陷入停滞（反复在同一方向上无新发现）时，使用 `/pivot` 强制编排器
在下一轮切换探索方向。不提供 `task-id` 则对所有任务生效。

```
❯ /pivot task-000122b967c7
forcing structural pivot on task-000122b967c7

❯ /pivot
forcing structural pivot on task-001
forcing structural pivot on task-002
```

#### `/stop` — 停止所有任务

停止当前 REPL 会话中所有正在运行的任务。

```
❯ /stop
stopping all tasks
```

#### `/spec` — 查看任务规格

显示当前所有任务的 `task_spec.md` 内容，包括目标、里程碑和成功标准。
用于回顾任务的原始规格定义。

```
❯ /spec
# Goal
研究大模型 agent 强化学习的最新进展

## Milestones
1. 收集关键论文和开源项目
2. 分析主流方法的优劣对比
...
```

#### `/synthesize [task]` — 一键生成最终文档

将任务积累的所有 findings 综合为一份结构化最终文档（`deliverable.md`）。
这是获取最终结果的最快方式——无论任务处于何种状态，只要有 findings，
就可以一键生成文档。

不指定 `task` 时，默认对最近的任务执行综合。

```
❯ /synthesize
synthesized 2048 chars → .zhuri/tasks/task-001/state/deliverable.md

❯ /synthesize task-000122b967c7
synthesized 3200 chars → .zhuri/tasks/task-000122b967c7/state/deliverable.md
```

生成的文档保存在 `state/deliverable.md`，可直接查看或导出。

#### `/config` — 查看与管理配置

不带参数时，显示当前的提供商配置和 verbose 模式状态。

```
❯ /config
providers=['deepseek', 'qwen', 'kimi']
verbose=off
```

带 `verbose` 子命令可动态开关详细日志输出：

```
❯ /config verbose on
verbose mode: on

❯ /config verbose off
verbose mode: off
```

#### `/quit` — 退出 REPL

安全退出 zhuri 交互式 REPL。也可以使用 `Ctrl+C` 或 `Ctrl+D` 退出。

```
❯ /quit
```

### REPL 中的并发任务

你可以同时运行多个任务：

```
❯ 研究联邦学习最新进展
... (运行中) ...
❯ /new "对比三大云服务商的 GPU 定价"
... (启动第二个任务) ...
❯ /status
task-001  running  iter=3 findings=18 stale=0
task-002  running  iter=1 findings=6  stale=0
```

### REPL 中一键生成文档

在 REPL 中使用 `/synthesize` 可随时将已有的 findings 一键生成最终文档，
无需退出后用命令行操作：

```
❯ /synthesize
synthesized 2048 chars → .zhuri/tasks/task-001/state/deliverable.md

❯ /synthesize task-000122b967c7
synthesized 3200 chars → .zhuri/tasks/task-000122b967c7/state/deliverable.md
```

> **提示**：即使任务仍在运行中，也可以执行 `/synthesize` 生成阶段性文档。
> 后续可随时再次执行以获取包含更多 findings 的更新版本。

### Verbose 模式（详细日志）

verbose 模式会将所有日志事件实时输出到 stderr，便于调试和观察 LLM 调用过程。

#### 启动时开启

```bash
# CLI 方式
zhuri "研究主题" --yes --verbose
zhuri -v synthesize .zhuri/tasks/task-001

# REPL 方式
zhuri --verbose
```

#### REPL 中动态开关

```
❯ /config verbose on
verbose mode: on

❯ /config verbose off
verbose mode: off
```

#### verbose 输出示例

```
[14:03:22] ✓ synthesis_start | direct synthesis mode
[14:03:22] ▶ llm_request | provider=deepseek model=deepseek-reasoner findings=5 spec_len=320
[14:03:28] ▶ llm_response | chars=2100
[14:03:28] ✓ synthesis_done | len=2100
```

---

## 6. 任务脚手架与批量运行

### 创建任务脚手架

```bash
# 空白模板
zhuri init my-research --template blank

# 论文写作模板
zhuri init my-paper --template paper-writing
```

### 编辑任务规格

```bash
# 手动编辑生成的 task_spec.md
vim my-research/state/task_spec.md
```

`task_spec.md` 结构：
```markdown
# Goal
研究大模型 agent 强化学习的最新进展

## Milestones
1. 收集关键论文和开源项目
2. 分析主流方法的优劣对比
3. 总结发展趋势和未来方向

## Success criteria
- 覆盖 2023-2024 年的主要工作
- 包含方法对比表格
- 给出清晰的分类体系

## Initial direction seed
从 RLHF、DPO、PPO 三个关键方法入手
```

### 运行编排器

```bash
# 编排当前目录下所有任务
zhuri run ./

# 带参数运行
zhuri run ./ --interval 1h --max-iters 10

# 只运行一个 tick
zhuri run ./ --once
```

---

## 7. 查看任务状态与日志

### 查看状态

```bash
# 文本格式
zhuri status .zhuri/tasks/

# JSON 格式
zhuri status .zhuri/tasks/ --json

# 持续监控
zhuri status .zhuri/tasks/ --watch
```

输出示例：
```
task-000122b967c7    running    iter=3 findings=25 stale=1
task-000122c4a8e2    done       iter=7 findings=42 stale=0
```

### 查看日志

```bash
# 查看工作智能体日志
zhuri logs .zhuri/tasks/task-000122b967c7 --source work

# 查看编排器日志
zhuri logs .zhuri/tasks/task-000122b967c7 --source orchestrator

# 只看决策级别日志
zhuri logs .zhuri/tasks/task-000122b967c7 --level decision

# 查看最近 100 条
zhuri logs .zhuri/tasks/task-000122b967c7 --tail 100
```

---

## 8. 综合模式（合并 findings 为文档）

当迭代完成后，可以手动触发综合，将所有 findings 合并为结构化最终文档。

### 手动触发综合

```bash
zhuri synthesize .zhuri/tasks/task-000122b967c7
```

这会：
1. 读取 `state/findings.jsonl` 中的所有发现
2. 读取 `state/task_spec.md` 中的任务规格
3. 通过一次 LLM 调用生成综合文档
4. 输出到 `state/deliverable.md`
5. 将任务状态标记为 `done`

### 自动综合（Entry A）

```bash
# 迭代完成后自动综合
zhuri "研究主题" --yes --synthesize --max-iters 5
```

---

## 9. 看门狗配置

zhuri 有三层看门狗确保任务不会无声死亡。

### L1 巡逻（推荐设为定时任务）

```bash
# 手动运行一次
zhuri watchdog ./ --interval 1h
```

#### Linux (systemd)

```ini
# /etc/systemd/system/zhuri-watchdog.timer
[Timer]
OnCalendar=hourly
Persistent=true
[Install]
WantedBy=timers.target
```

```bash
systemctl enable --now zhuri-watchdog.timer
```

#### Linux (cron)

```cron
0 * * * * zhuri watchdog /path/to/base --interval 1h
```

#### Windows (Task Scheduler)

```powershell
schtasks /create /tn "zhuri-watchdog" /tr "zhuri watchdog D:\Projects --interval 1h" /sc hourly
```

### L0 常驻守卫

```bash
# 作为守护进程运行
zhuri guard ./
```

---

## 10. 高级配置：多提供商与模型池

### 为不同角色使用不同模型

```toml
[agents.work]
provider = "qwen"
model    = "qwen-max"       # 工作用最强模型

[agents.orchestrator]
provider = "deepseek"
model    = "deepseek-chat"  # 编排器用便宜模型

[agents.review]
provider = "kimi"
models   = ["kimi-k2-0905-preview", "moonshot-v1-128k"]  # 评审用模型池轮换
```

### 模型池轮换

当 `models` 是数组时，zhuri 在每轮自动轮换模型（`pool[round % len(pool)]`），
确保评审多样性。

### 子角色继承

```toml
[agents.subagent.verification]
provider = "deepseek"
model    = "deepseek-reasoner"

# 未定义的子角色自动继承父角色配置
# [agents.subagent.nudge]  → 继承 [agents.work] 或 [agents.default]
```

### 使用本地 LLM

```toml
[providers.local]
type     = "openai_compat"
base_url = "http://localhost:8000/v1"    # 本地 vLLM/Ollama/LiteLLM 端点
api_key  = "not-needed"
models   = ["local-model"]

[agents.default]
provider = "local"
model    = "local-model"
```

---

## 11. 典型工作流示例

### 工作流 A：快速调研（直接模式）

```bash
# 1. 配置好 API Key
export DEEPSEEK_API_KEY="sk-xxx"

# 2. 直接出结果
zhuri "对比 RAG 和 Fine-tuning 的优劣，给出选择建议" --direct --yes

# 结果直接输出到终端，同时保存到 state/deliverable.md
```

### 工作流 B：深度研究（迭代 + 综合）

```bash
# 1. 启动迭代研究（5 轮）
zhuri "研究大模型 agent 强化学习" --yes --max-iters 5 --synthesize

# 2. 查看进度
zhuri status .zhuri/tasks/

# 3. 查看最终文档
cat .zhuri/tasks/<task-id>/state/deliverable.md
```

### 工作流 C：论文写作（脚手架模式）

```bash
# 1. 创建论文项目
zhuri init my-paper --template paper-writing

# 2. 编辑任务规格
vim my-paper/state/task_spec.md

# 3. 运行编排器（持续运行直到完成）
zhuri run my-paper --max-iters 12

# 4. 查看进度
zhuri status my-paper --watch
```

### 工作流 D：交互式多任务

```bash
# 1. 启动 REPL
zhuri

# 2. 查看可用命令
❯ /help

# 3. 提交第一个任务
❯ 研究 MoE 架构的最新进展

# 4. 查看状态
❯ /status

# 5. 同时启动第二个任务
❯ /new "对比 GPT-4、Claude、Gemini 的技术路线"

# 6. 查看日志
❯ /logs work

# 7. 强制转向
❯ /pivot task-xxx

# 8. 一键生成文档
❯ /synthesize

# 9. 退出
❯ /quit
```

---

## 12. 论文写作任务包（Sub-skill 系统）

zhuri 内置了可扩展的任务包系统（`tasks/`），首个完整实现是**论文写作包**，包含
5 个由上游协议定义的子技能。

### 子技能概览

| 子技能 | 方向键 | 工作流 |
|--------|--------|--------|
| **文献调研** | `subskill:literature` | 4 阶段：Recall → LQS 多维评分 → A/B/C/D 深度分类 → 会议升级 |
| **论文结构** | `subskill:structure` | 章节架构 + 段落逻辑模式 + MECE 分类法 + 分层声明 |
| **实验设计** | `subskill:experiment` | 设计(假设)→执行(API/GPU)→迭代(≤5次)→报告(JSON) |
| **学术图表** | `subskill:figures` | Booktabs 表格 + 矢量图 + 质量检查清单 + 学术调色板 |
| **同行评审** | `subskill:review` | 5 个评审 persona 独立评分 → 中位数 → 弱点路由回子技能 |

### 自动反馈闭环

评审发现的弱点会**自动路由**到对应子技能：

```
评审 agent 产出 → 弱点路由表 → 注入 direction → 下一轮 work agent
                                          ↓
"缺少实验"      → subskill:experiment  → 实验设计 skill
"引用不足"      → subskill:literature  → 文献调研 skill
"结构不清"      → subskill:structure   → 论文结构 skill
```

### LQS 评分体系（文献调研专用）

文献调研使用 5 维加权评分自动筛选论文：

| 维度 | 权重 | 评分规则 |
|------|------|---------|
| 时效性 | 30% | ≤6个月=10分, ≤1年=8分 |
| 引用影响力 | 25% | cites/月 ≥50=10分 |
| 发表场合 | 20% | 顶会=10分, 强会=7分 |
| 机构 | 10% | 顶尖实验室=10分 |
| 录用状态 | 15% | 已录用=10分 |

LQS≥7.0 必引，5.0-7.0 条件引用，<5.0 丢弃。

### 扩展自定义任务包

实现 `tasks/base.py` 中的 `TaskPack` 和 `SubSkill` 接口即可创建新的任务包：

```python
from zhuri.tasks.base import TaskPack, SubSkill, SubSkillContext

class MyCodeReviewPack(TaskPack):
    name = "code_review"
    sub_skills = {"security": SecurityReviewSkill(), ...}
    ...
```

---

## 13. 常见问题

### Q: 直接模式和迭代模式该如何选择？

| 场景 | 推荐模式 |
|---|---|
| 问题范围明确、只需一次输出 | `--direct` |
| 开放性研究、需要多角度探索 | 默认迭代模式 |
| 需要深度验证的复杂任务 | 迭代 + `--synthesize` |
| 论文写作等有多阶段的任务 | 脚手架 + `zhuri run` |

### Q: 如何查看已完成任务的结果？

```bash
# 查看 findings（原始发现）
cat .zhuri/tasks/<task-id>/state/findings.jsonl

# 查看最终文档（需先执行 synthesize）
cat .zhuri/tasks/<task-id>/state/deliverable.md

# 查看任务规格
cat .zhuri/tasks/<task-id>/state/task_spec.md
```

### Q: 任务停滞了怎么办？

```bash
# 查看停滞状态
zhuri status .zhuri/tasks/

# 强制结构转向（在 REPL 中）
/pivot <task-id>

# 或者手动触发新迭代
zhuri work .zhuri/tasks/<task-id> --direction "尝试从应用场景角度分析"
```

### Q: 如何在 CI/CD 中使用 zhuri？

```bash
# 使用非交互模式
zhuri "生成 API 文档" --direct --yes --config ./ci-config.toml

# 或者脚手架模式
zhuri init doc-task --template blank
echo "# Goal\nGenerate API docs..." > doc-task/state/task_spec.md
zhuri run doc-task --once
```

### Q: 支持哪些 LLM 提供商？

v1 支持任何 **OpenAI 兼容** 的 Chat Completions API，包括但不限于：

- DeepSeek（deepseek-chat, deepseek-reasoner）
- 通义千问（qwen-max, qwen-plus）
- Kimi / Moonshot（kimi-k2, moonshot-v1）
- 本地部署（vLLM, Ollama, LiteLLM 等）
- 其他兼容 OpenAI API 格式的服务

### Q: 配置文件中 `${ENV_VAR}` 无法解析？

确保环境变量已正确导出：

```bash
# 检查
echo $DEEPSEEK_API_KEY

# 如果为空，设置它
export DEEPSEEK_API_KEY="sk-xxx"

# 使用 zhuri doctor 验证
zhuri doctor
```

---

## 附录：退出码

| 退出码 | 含义 |
|---|---|
| `0` | 正常完成 |
| `1` | 通用错误 |
| `2` | 配置错误（文件缺失、格式错误） |
| `3` | 提供商/认证错误（Key 无效、网络不通） |
