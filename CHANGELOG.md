# 🎊 好想玩云原神🎊 更新日志

## [2.0.0] - 2026-06-08

### 🎨 重大重构
- **关键词统一管理**：移除独立的 `custom_keywords` 持久化文件，所有关键词统一到持久化数据中的 `trigger_keywords`，命令与配置来源合一
- **数据持久化重构**：移除 `custom_keywords.json` 和 `custom_blacklist.json`，改用统一的 `data.json` 单文件存储
- **配置优先级优化**：启动时优先从 `data.json` 加载，不存在时从 `_conf_schema.json` 获取默认值；管理命令修改即时持久化

### ✨ 新增功能
- **首次回复词命令管理**：新增 `/云原神管理 first_reply <文本>` 命令，可直接设置首次回复词并持久化保存
- **梗段词库命令管理**：新增 `/云原神管理 quote add/remove/list/set` 命令，可增删改查梗段词库，即时生效无需重载插件
- **状态查看命令**：新增 `/云原神管理 status` 命令，可查看关键词、梗段池、首次回复词、群名单等当前状态总览

### 🔧 变更
- 所有命令帮助列表同步更新，新增 first_reply / quote / status 子命令说明
- 版本号更新至 2.0.0

## [1.5.2] - 2026-06-08

### 🎨 增强
- **首次回复词可配置**：新增 `first_reply` 配置项（默认"欸，云朵"），可在管理面板自由修改
- **梗段词库可配置**：新增 `quote_pool` 配置项（默认11段梗），移除硬编码 `self.quotes`，可在管理面板自由增删改
- **README 配置表同步更新**：新增 `first_reply` 和 `quote_pool` 说明

### 🔧 变更
- 版本号更新至 1.5.2

## [1.5.1] - 2026-06-07

### 🐛 修复
- **管理命令 async_generator 错误**：将 `_handle_keyword_admin` 和 `_handle_blacklist_admin` 从异步生成器（yield）重构为纯 async 函数（await event.send()），修复 `TypeError: object async_generator can't be used in 'await' expression`

### 🔧 变更
- 版本号更新至 1.5.1

## [1.5.0] - 2026-06-07

### 📝 新增
- 创建 GitHub Release 并发布 ZIP 包
- README.md 添加纯 AI 创作声明和 Issue 引导
- CHANGELOG.md 更新日志

### 🔧 变更
- 版本号更新至 1.5.0

## [1.4.0] - 2026-06-07

### 🐛 修复
- **命令自身触发关键词**：改用 `event.message_obj.raw_message` 获取原始消息（保留 "/" 前缀），防止 `/云原神` 和 `/云原神管理` 被"云原神"关键词误触发
- **后台任务未执行**：将 `asyncio.create_task` 移到 `yield` 之前执行，确保事件循环调度延迟发送梗段的后台任务
- **管理命令无参数时返回帮助**：`/云原神管理` 无参数时现在显示完整帮助列表

### 📝 新增
- CHANGELOG.md 更新日志文件

### 🔧 变更
- 合并 `default_keywords` 和 `extra_keywords` 为统一的 `trigger_keywords` 配置项
- 关键词管理逻辑优化，支持通过管理面板自由增删所有关键词

## [1.3.0] - 2026-06-07

### 🔧 变更
- 合并 `default_keywords` 和 `extra_keywords` 配置项为 `trigger_keywords`
- 移除默认关键词硬编码，所有关键词均可通过管理面板编辑

### 🐛 修复
- 第二条梗段发送机制改为 `asyncio.create_task` + `context.send_message` 独立后台任务

## [1.2.0] - 2026-06-07

### ✨ 新增
- `default_keywords` 配置项，默认关键词可从管理面板自由增删

### 🔧 变更
- 移除对"云朵""云原神"的硬编码保护，管理员可完全控制关键词列表

## [1.1.0] - 2026-06-07

### ✨ 新增
- 群聊黑/白名单功能（blacklist_mode + blacklist_groups 配置）
- `/云原神管理 blacklist add/remove/list` 管理命令
- 持久化黑名单存储（custom_blacklist.json）
- 插件显示名改为"好想玩云原神🎊"

## [1.0.0] - 2026-06-07

### ✨ 初始版本
- 基础关键词自动触发（"云朵""云原神"）
- 手动命令 `/云原神` 和 `/cloudys`
- 11段随机梗段池（长版拆5段 + 6段短版变体）
- 先发"欸，云朵"→延迟→发梗段的回复流程
- `/云原神管理 add/remove/list` 关键词管理命令
- 自定义关键词持久化存储（custom_keywords.json）
- AstrBot 管理面板配置支持
