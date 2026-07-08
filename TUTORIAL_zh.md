# TUTORIAL_zh.md — zhuri 使用手册

> English version: [`TUTORIAL.md`](./TUTORIAL.md)

本教程详细介绍 zhuri 的所有功能、命令用法和配置方法。

---

## 目录

1. [安装与验证](#1-安装与验证)
2. [配置说明](#2-配置说明)
3. [直接模式（一步出结果）](#3-直接模式一步出结果)
4. [启动方式速查](#启动方式速查)
5. [迭代模式（深度研究）](#5-迭代模式深度研究)
6. [交互式 REPL](#6-交互式-repl)
7. [任务脚手架与批量运行](#7-任务脚手架与批量运行)
8. [状态与日志](#8-状态与日志)
9. [综合模式（Findings → 文档）](#9-综合模式findings--文档)
10. [看门狗配置](#10-看门狗配置)
11. [学术搜索（ArXiv + Semantic Scholar）](#11-学术搜索arxiv--semantic-scholar)
12. [论文写作任务包（Sub-skill 系统）](#12-论文写作任务包sub-skill-系统)
13. [典型工作流](#13-典型工作流)
14. [常见问题](#14-常见问题)

---

## 1. 安装与验证

### 前提条件

- **Python 3.10+**（`python --version`）
- **pip**（Python 自带）
- **Git Bash**（Windows）或任意终端（macOS/Linux）
- 一个 LLM API Key（DeepSeek / 通义千问 / Kimi / 任何 OpenAI 兼容端点）

### 安装

```bash
git clone git@github.com:igeng/zhuri.git
cd zhuri

# 可编辑模式安装（推荐，改代码立刻生效）
pip install -e .

# 含开发依赖（pytest + coverage）
pip install -e '.[dev]'

# 验证
zhuri --help
```

### 快速配置

```bash
mkdir -p ~/.config/zhuri
cp examples/config.toml ~/.config/zhuri/config.toml
# 编辑文件，使用 ${ENV_VAR} 语法引用 API Key（永远不要硬编码！）
```

> **安全提醒：永远不要在配置文件中硬编码真实 API Key。**
> 始终使用 `${ENV_VAR}` 语法，将真实 key 只保存在 shell profile
> （`~/.bashrc` / `~/.zshrc`）中：
> ```bash
> export DEEPSEEK_API_KEY="sk-your-deepseek-key"
> export QWEN_API_KEY="sk-your-qwen-key"
> export MOONSHOT_API_KEY="sk-your-moonshot-key"
> ```

验证配置：
```bash
zhuri config check      # 语法 + provider 校验
zhuri doctor            # 在线探测 API Key（用 --offline 跳过）
```

---

## 2. 配置说明

zhuri 使用双层配置模型：

- **`[providers.*]`** — 有哪些模型端点，各自用什么 Key
- **`[agents.*]`** — 每个智能体角色用哪个 provider/model

示例（`~/.config/zhuri/config.toml`）：

```toml
[providers.deepseek]
type     = "openai_compat"
base_url = "https://api.deepseek.com/v1"
api_key  = "${DEEPSEEK_API_KEY}"
models   = ["deepseek-v4-flash", "deepseek-v4-pro"]

[agents.default]
provider = "deepseek"
model    = "deepseek-v4-flash"

[agents.work]           # 干活的主力，用最强模型
provider = "deepseek"
model    = "deepseek-v4-pro"

[agents.review]         # 评审用不同厂商，保持独立性
provider = "kimi"
model    = "kimi-k2.5"
```

### 解析顺序

`[agents.<角色>]` → `[agents.default]` → 报错。子角色（如 `subagent.verification`）未设置时继承父角色。

### 查看生效配置

```bash
zhuri config get --effective              # 所有角色
zhuri config get --effective --role work  # 单个角色
zhuri config get --effective --json       # 机器可读
```

---

## 3. 直接模式（一步出结果）

单次 LLM 调用 → 立即出结果。适合快速问答、范围明确的任务。

```bash
zhuri "你的提示词" --direct --yes
```

输出：stdout + `state/deliverable.md`。

---

## 启动方式速查

zhuri 共有 5 种启动方式。**最终目标都是拿到综合后的综述文档 `deliverable.md`。**

| 方式 | 命令 | 确认？ | 如何拿到最终文档 |
|------|------|--------|-----------------|
| **REPL 交互** | `zhuri` → `❯ 粘贴任务` | spec + y/N | REPL 中 `/synthesize` |
| **直接跑** | `zhuri "任务"` | spec + y/N | `zhuri synthesize .zhuri/tasks/<task-id>` |
| **跳过确认** | `zhuri "任务" --yes` | 无 | `zhuri synthesize .zhuri/tasks/<task-id>` |
| **后台运行** | `zhuri "任务" --yes --detach` | 无 | `zhuri status` 等 done → `zhuri synthesize <dir>` |
| **后台+综合** | `zhuri "任务" --yes --detach --synthesize` | 无 | 自动完成：`state/deliverable.md` |

### Flag 说明

| Flag | 效果 |
|------|------|
| 无 flag | 显示 spec 供一次性确认（B1 豁免），然后前台监控运行 |
| `--yes` | 跳过确认，直接开始（零交互） |
| `--direct` | 单次 LLM 调用，不走迭代 |
| `--detach` | 后台运行，终端立即返回 |
| `--synthesize` | 所有迭代完成后自动合并 findings 为最终文档 |
| `--max-iters N` | 最大编排器 tick 数（默认 30；0 = 无限制） |
| `--interval N` | tick 间隔秒数（默认 5s 前台，2h cron 模式） |
| `--no-search` | 跳过 ArXiv + Semantic Scholar 搜索 |
| `-v` / `--verbose` | 输出完整 LLM 调用日志到 stderr |

### 运行时阈值

zhuri 有合理的默认值防止无限运行，同时允许深度探索：

| 阈值 | 值 | 说明 |
|------|-----|------|
| 转向 (pivot) | stale ≥ 2 | 强制切换结构轴 |
| 升级 (escalate) | stale ≥ 4 | 标记需人工关注 |
| 自动停止 | stale ≥ 8 | 停止任务，避免浪费 API 额度 |
| Entry A 默认最大 tick | 30 | 编排器 30 轮后自动停（`--max-iters 0` 取消限制） |
| Work agent 上限 | 15 轮 / 30 分钟 | 单次工作会话 |

在 REPL 中查看：`/limits`。调整：`/set-iters N`。

### 输出位置

```
<工作目录>/.zhuri/tasks/<task-id>/state/
├── task_spec.md          # 目标 / 里程碑 / 成功标准
├── findings.jsonl         # 所有中间发现（追加模式）
├── deliverable.md         # ★ 最终综述文档
├── progress.json          # 迭代次数、状态、停滞计数
├── directions_tried.json  # 已探索的结构轴
└── iteration_log.jsonl    # 每轮迭代摘要
```

---

## 5. 迭代模式（深度研究）

多轮迭代，每轮沿不同结构轴探索。适合复杂开放性任务。

### 基本用法

```bash
zhuri "你的研究主题" --yes          # 持续运行（默认最多 30 tick）
zhuri "主题" --yes --max-iters 50   # 最多 50 tick
zhuri "主题" --yes --max-iters 0    # 无限制（靠自动停止判定）
zhuri "主题" --yes --once            # 单次 tick
zhuri "主题" --yes --detach          # 后台运行
zhuri "主题" --yes --synthesize      # 跑完自动综合
```

### 实时进度输出

入口 A 自动进入**监控模式**（B1 安全：纯展示、不交互）：

```
  [search] querying ArXiv + Semantic Scholar: large language model HPC post-training...
  [search] found 15 papers
  [orch] > spawning work agent for task-001  direction='method_comparison'
  [work] > round 1/15  sending to deepseek-v4-pro  (elapsed=0s)...
  [work] ok  round 1/15  557 chars  19047ms  findings=2
  [work] DONE signal received
  [orch] ok  work agent done  rc=0  new_findings=13
  [running ] iter=1  findings=13  gain
```

### 迭代生命周期

| 状态 | 触发条件 | 含义 |
|------|---------|------|
| `running` | 默认 | 运行中，持续产出 |
| `pivoting` | stale ≥ 2 | 强制切换结构轴 |
| `escalated` | stale ≥ 4 | 标记需人工关注 |
| `done` | 终止状态 | 任务完成，编排器停止 |
| auto-stop | escalated + stale ≥ 8 | 无法改善 → 自动停止 |

### Verbose 模式

```bash
zhuri "任务" --yes -v    # 完整 LLM 调用详情：timing、tokens、model 路由
```

在 REPL 中：`/config verbose on` / `/config verbose off`

---

## 6. 交互式 REPL

### 启动

```bash
zhuri                    # 默认工作目录
zhuri --dir ~/projects   # 指定目录
```

### 提交任务

在 `❯` 提示符后输入或粘贴你的研究问题，按回车即可。
**支持多行粘贴**——直接粘贴包含空行的整段文本，全部收进一个 prompt。

### 斜杠命令

| 命令 | 说明 |
|------|------|
| `/status` | 显示所有任务状态 |
| `/logs [work\|orchestrator\|heartbeat]` | 查看日志流 |
| `/new "提示词"` | 启动新的并发任务 |
| `/pause` | 暂停编排器调度 |
| `/resume` | 恢复调度 |
| `/pivot [task-id]` | 强制结构转向 |
| `/stop` | 停止所有任务 |
| `/spec` | 显示当前 task_spec.md |
| `/synthesize [task-id]` | 合并 findings 为 deliverable.md |
| `/config` | 显示 provider 配置 |
| `/config verbose on\|off` | 开关 verbose 日志 |
| `/set-iters N` | 设置前台最大迭代数（0=无限制） |
| `/limits` | 显示所有阈值 |
| `/help` | 显示所有命令 |
| `/quit` | 退出 REPL |

---

## 7. 任务脚手架与批量运行

### 创建任务（Entry C）

```bash
zhuri init my-task --template paper-writing    # 或 blank
# 编辑 my-task/state/task_spec.md
zhuri run ./                                     # 编排所有任务
```

### 批量编排

```bash
zhuri run <base-dir> --interval 2h --max-iters 10
zhuri run <base-dir> --once          # 单次 tick
```

---

## 8. 状态与日志

```bash
# 状态
zhuri status <base-dir>              # 一次性
zhuri status <base-dir> --watch      # 实时刷新（Ctrl+C 退出）
zhuri status <base-dir> --json       # 机器可读

# 日志
zhuri logs <task-dir> --source work              # work agent 日志
zhuri logs <task-dir> --source orchestrator      # 编排器日志
zhuri logs <task-dir> --level decision           # 仅决策日志
zhuri logs <task-dir> --tail 100                 # 最近 100 行
```

---

## 9. 综合模式（Findings → 文档）

将所有累积 findings 合并为最终文档：

```bash
# CLI
zhuri synthesize .zhuri/tasks/task-0001baf93b2d

# REPL
❯ /synthesize                      # 最近一个任务
❯ /synthesize task-0001baf93b2d    # 指定任务
```

输出：stdout + `state/deliverable.md`。

---

## 10. 看门狗配置

zhuri 有三层心跳看门狗，确保进程崩溃和停滞能自动恢复：

| 层 | 命令 | 职责 |
|-----|------|------|
| L0 | `zhuri guard <base-dir>` | 常驻会话无关守护 |
| L1 | `zhuri watchdog <base-dir>` | 每小时巡逻：重启超时循环、推动停滞任务 |
| L2 | 内置 | 每个回调第一个动作写入 `last_seen` |

看门狗对非自身任务只能执行三种操作：**检查 / 重启 / 推动**（B5 原则）。

---

## 11. 学术搜索（ArXiv + Semantic Scholar）

默认每轮 work agent 迭代前自动搜索 ArXiv 和 Semantic Scholar
获取真实论文。结果注入 LLM prompt，确保引用基于真实出版物。

### 工作原理

1. 第一轮 LLM 调用前，从任务描述自动提取搜索查询
2. 查询 ArXiv API + Semantic Scholar API（均免费，无需认证）
3. 合并去重
4. 格式化为参考块注入 prompt
5. 搜索失败不中断执行（记录警告，继续运行）

### 禁用搜索

```bash
zhuri "任务" --yes --no-search     # 纯 LLM 模式
ZHURI_NO_SEARCH=1 zhuri "任务" --yes  # 环境变量覆盖
```

测试环境下自动跳过搜索。

---

## 12. 论文写作任务包（Sub-skill 系统）

zhuri 内置可扩展的任务包系统（`tasks/`）。首个完整实现是**论文写作包**，含 5 个子技能：

| 子技能 | 方向键 | 工作流 |
|--------|--------|--------|
| **文献调研** | `subskill:literature` | 4 阶段：Recall → LQS 评分 → A/B/C/D 分级 → 会议升级 |
| **论文结构** | `subskill:structure` | 章节架构 + 段落逻辑模式 + MECE 分类法 + 分层声明 |
| **实验设计** | `subskill:experiment` | 设计(假设)→执行(API/GPU)→迭代(≤5)→报告(JSON) |
| **学术图表** | `subskill:figures` | Booktabs 表格 + 矢量图 + 质量清单 + 学术调色板 |
| **同行评审** | `subskill:review` | 5 个评审 persona → 中位数评分 → 弱点路由 → 反膨胀 |

### 自动反馈闭环

评审发现的弱点**自动路由**到对应子技能：

```
评审 agent 输出 → 弱点路由表 → 注入 direction → 下一轮 work agent
                                              ↓
"缺少实验"       → subskill:experiment  → 实验设计 skill
"引用不足"       → subskill:literature  → 文献调研 skill
```

### LQS 评分（文献调研）

文献调研使用 5 维加权评分自动筛选论文：

| 维度 | 权重 | 评分规则 |
|------|------|---------|
| 时效性 | 30% | ≤6个月=10分, ≤1年=8分 |
| 引用影响力 | 25% | cites/月 ≥50=10分 |
| 发表场合 | 20% | 顶会=10分, 强会=7分 |
| 机构 | 10% | 顶尖实验室=10分 |
| 录用状态 | 15% | 已录用=10分 |

LQS ≥ 7.0 必引，5.0–7.0 条件引用，<5.0 丢弃。

### 自定义任务包

实现 `tasks/base.py` 中的 `TaskPack` 和 `SubSkill` 接口：

```python
from zhuri.tasks.base import TaskPack, SubSkill, SubSkillContext

class MyCodeReviewPack(TaskPack):
    name = "code_review"
    sub_skills = {"security": SecurityReviewSkill(), ...}
    ...
```

---

## 13. 典型工作流

### 快速调研

```bash
zhuri "总结联邦学习近三年进展" --direct --yes
```

### 深度论文写作

```bash
zhuri "写一篇关于 LLM 后训练技术在 HPC 领域应用的综述..." --yes --synthesize
```

### 后台长任务

```bash
# 启动
zhuri "关于强化学习的全面文献综述" --yes --detach --synthesize

# 定期查看进度
zhuri status .zhuri/tasks/
zhuri logs .zhuri/tasks/task-xxx --source work --tail 20
```

### REPL 多任务会话

```
❯ 研究向量数据库在 RAG 中的应用
(任务在前台运行，结果实时输出)

❯ /new "对比 PyTorch 和 JAX 在科学计算中的表现"
(第二个任务并发启动)

❯ /status
(两个任务都完成后)
❯ /synthesize
❯ /quit
```

---

## 14. 常见问题

### Q: 直接模式和迭代模式该怎么选？

- **直接模式**：快速问答、范围明确、单一答案
- **迭代模式**：复杂研究、开放性探索、需要多角度分析

### Q: `zhuri: command not found`？

重新运行 `pip install -e .`，确认 Python Scripts 在 PATH 中。

### Q: `config error: config file not found`？

在 `.zhuri/config.toml` 或 `~/.config/zhuri/config.toml` 创建配置文件。

### Q: `provider error: auth failed`？

检查环境变量：`echo $DEEPSEEK_API_KEY`。运行 `zhuri doctor` 诊断。

### Q: 任务看起来卡住了？

运行 `zhuri status <base-dir>`。如果 `stale_count` 很高，说明 easy findings 已耗尽。
编排器会在 escalated + 8 次连续 stall 后自动停止以节省 API 额度。

### Q: 怎么停止正在运行的任务？

- 前台：`Ctrl+C`
- 后台：`zhuri status` 找到任务，kill 进程
- REPL：`/stop`

### Q: 可以用多个提供商吗？

可以。每个 agent 角色可以路由到不同的 provider/model。`review` 角色应该
使用与 `work` 不同的厂商，保持独立评审。

### Q: 我的 API Key 安全吗？

zhuri 从不在项目文件中存储 API Key。始终使用 `${ENV_VAR}` 语法，真实 key
只保存在 shell profile 中。项目 `.gitignore` 已排除所有凭证文件。
