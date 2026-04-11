# director-actor-drama

导演-演员戏剧创作系统 —— 基于 STORM 框架的多 Agent A2A 架构。

## 项目介绍

这是一个智能戏剧创作系统，通过 A2A（Agent-to-Agent）协议实现真正的多 Agent 协作：

- **导演 Agent**：统筹全局、编写剧本、旁白叙述
- **演员 Agent**：独立运行，各自拥有会话和记忆，认知边界通过 A2A 物理隔离保证
- **STORM 框架**：多视角发现 → 深度研究 → 大纲合成 → 场景执行

## 项目结构

```
director-actor-drama/
├── app/
│   ├── agent.py           # STORM 框架 Agent 逻辑
│   ├── actor_service.py  # 演员 A2A 服务管理
│   ├── state_manager.py  # 状态管理与数据持久化
│   └── tools.py          # 导演工具集
├── cli.py                # 命令行交互界面
└── pyproject.toml        # 项目依赖
```

## 数据存储结构

每个剧本创建独立的文件夹，完整隔离：

```
dramas/
└── <剧本名>/
    ├── state.json              # 主状态（角色、场景、旁白、STORM数据）
    ├── actors/                 # 演员数据
    ├── scenes/                 # 场景数据
    ├── conversations/          # 对话记录
    │   ├── conversation_log.json  # 原始记录
    │   └── conversation_log.md    # Markdown 导出
    └── exports/                # 导出的剧本文件
```

## 快速开始

```bash
# 安装依赖
make install

# 启动系统
make playground
```

## 命令列表

| 命令 | 说明 |
|------|------|
| `/start <主题>` | 开始新剧作，自动创建剧本文件夹 |
| `/next` | 推进下一场 |
| `/action <描述>` | 注入事件 |
| `/save [名称]` | 保存进度（同时导出对话记录） |
| `/load <名称>` | 加载进度 |
| `/export` | 导出剧本和对话记录 |
| `/list` | 列出所有已保存的剧本 |
| `/cast` | 查看角色列表（含 A2A 服务状态） |
| `/status` | 查看当前状态 |
| `/quit` | 退出（自动保存） |

## STORM 框架四阶段

1. **Discovery 发现阶段**：从多视角生成探索性问题
2. **Research 研究阶段**：深入挖掘每个视角的戏剧潜力
3. **Outline 大纲合成**：将多视角结果融合为戏剧大纲
4. **Directing 导演阶段**：执行戏剧演出

## 架构特点

- **A2A 物理隔离**：每个演员是独立的 A2A 服务，认知边界天然保证
- **自动数据持久化**：状态变更自动保存到剧本文件夹
- **对话记录**：自动记录所有对话到 `conversations/` 目录
- **命名快照**：支持创建多个命名保存点

## 环境配置

在 `app/.env` 文件中配置：

```
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
MODEL_NAME=openai/claude-sonnet-4-6
```
