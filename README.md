# 🎊 好想玩云原神🎊 v4.5 — 多媒体 · 灵活回复模式

> "啊😲？云朵☁️😄，哒↘哒↗哒↘哒↗哒↘，好想玩原神😨……"

一个 AstrBot 插件，自动检测关键词并回复经典云原神梗。支持多媒体发送（图片/语音/视频）+ 5种灵活回复模式！每组可独立配置文本梗段池 + 媒体池 + 回复模式，消息匹配到哪组就用哪组的配置回复，互不干扰。

---

## ✨ 功能

| 功能 | 说明 |
|------|------|
| 🎯 **多匹配组** | 创建多个组，每组独立配置关键词、首次回复词、梗段词库、媒体池、回复模式、延迟 |
| 📦 **各组独立** | 消息匹配到对应组，回复该组专属内容，互不干扰 |
| 🎲 **梗段随机池** | 每组各配各的梗段池，每次随机取一段 |
| 🖼️ **多媒体发送** | 每组独立媒体池，支持图片(image)/语音(record)/视频(video)，URL和本地文件双支持 |
| 🔀 **灵活回复模式** | 5种模式：纯文本 / 纯媒体 / 文本+媒体 / 媒体+文本 / 随机混合 |
| 👋 **先打招呼** | 各组独立配置首次回复词 |
| 💬 **手动命令** | `/云原神` / `/cloudys` 从第一组随机回复 |
| 🔧 **管理命令体系** | 丰富的 `group` 子命令管理多组：增删改查、命名、配置、媒体、模式 |
| 🚫 **群聊黑/白名单** | 全局统一，所有组共享 |
| 🔄 **面板配置实时生效** | 修改 AstrBot 面板配置后，重启插件或执行 `/云原神管理 configsync` 即可同步到所有组 |
| 📥 **v2.x/v3.x 自动迁移** | 旧版 data.json 自动迁移到 v4.x 格式 |

---

## 📦 安装

### 方式一：ZIP 安装（推荐）
1. 将 `astrbot_plugin_cloud_genshin.zip` 上传到 AstrBot
2. 在 AstrBot 管理面板 → 插件管理 → 安装插件 → 选择 ZIP 文件
3. 启用插件即可

### 方式二：手动放置
将 `astrbot_plugin_cloud_genshin/` 整个文件夹复制到 AstrBot 的 `addons/` 目录下，重启 AstrBot。

---

## 📖 命令列表

### 用户命令

| 命令 | 说明 |
|------|------|
| `/云原神` | 从默认组随机回复一段梗 |
| `/cloudys` | 同上，英文别名 |

### 管理员命令 — 匹配组管理（核心）

| 命令 | 说明 |
|------|------|
| `/云原神管理 group list` | 列出所有匹配组 |
| `/云原神管理 group add <组名>` | 新建匹配组 |
| `/云原神管理 group remove <组名>` | 删除匹配组 |
| `/云原神管理 group rename <旧名> <新名>` | 重命名组 |
| `/云原神管理 group <组名>` | 查看组详情 |
| `/云原神管理 group <组名> add <关键词>` | 组内添加关键词 |
| `/云原神管理 group <组名> remove <关键词>` | 组内删除关键词 |
| `/云原神管理 group <组名> first_reply [文本]` | 查看/设首次回复词 |
| `/云原神管理 group <组名> delay <毫秒>` | 设组回复延迟 |
| `/云原神管理 group <组名> quote list` | 列出组梗段 |
| `/云原神管理 group <组名> quote add <梗段>` | 组内添加梗段 |
| `/云原神管理 group <组名> quote remove <编号>` | 组内删除梗段 |
| `/云原神管理 group <组名> quote set <编号> <内容>` | 组内修改梗段 |
| `/云原神管理 group <组名> media list` | 列出组媒体 |
| `/云原神管理 group <组名> media add <type> <src> [source]` | 组内添加媒体（type: image/record/video, source: url/local） |
| `/云原神管理 group <组名> media remove <编号>` | 组内删除媒体 |
| `/云原神管理 group <组名> media info <编号>` | 查看媒体详情 |
| `/云原神管理 group <组名> mode <模式>` | 设回复模式（text/media/text_media/media_text/mixed） |

### 管理员命令 — 快捷操作（操作第一个组）

| 命令 | 说明 |
|------|------|
| `/云原神管理 add <关键词>` | 添加关键词到默认组 |
| `/云原神管理 remove <关键词>` | 从默认组删除关键词 |
| `/云原神管理 list` | 列出默认组关键词 |
| `/云原神管理 first_reply [文本]` | 查看/设默认组首次回复词 |
| `/云原神管理 quote list` | 列出默认组梗段 |
| `/云原神管理 quote add <梗段>` | 默认组添加梗段 |
| `/云原神管理 quote remove <编号>` | 默认组删除梗段 |
| `/云原神管理 quote set <编号> <内容>` | 默认组修改梗段 |
| `/云原神管理 media list` | 列出默认组媒体 |
| `/云原神管理 media add <type> <src> [source]` | 默认组添加媒体 |
| `/云原神管理 media remove <编号>` | 默认组删除媒体 |
| `/云原神管理 mode [模式]` | 查看/设默认组回复模式 |
| `/云原神管理 blacklist add <群号>` | 添加到黑/白名单 |
| `/云原神管理 blacklist remove <群号>` | 从名单移除 |
| `/云原神管理 blacklist list` | 列出名单 |
| `/云原神管理 status` | 查看全部状态 |
| `/云原神管理 configsync` | 将面板配置同步到插件 |

### 命令示例

```
/云原神

/云原神管理 group list
/云原神管理 group add 原神启动组
/云原神管理 group 原神启动组 add 原神启动
/云原神管理 group 原神启动组 first_reply 原神启动！
/云原神管理 group 原神启动组 quote add 一起玩原神吧！
/云原神管理 group 原神启动组 delay 1000
/云原神管理 group 默认组 add 云原神
/云原神管理 group 默认组 quote list
/云原神管理 group 默认组 quote remove 3

/云原神管理 status
/云原神管理 add 云原神
/云原神管理 first_reply 欸，云朵
```

---

## ⚙️ 配置说明

AstrBot 管理面板的各个配置项 **修改后重启插件或执行 `/云原神管理 configsync` 即可同步到默认组**。管理命令修改默认组时也会自动保存到 `data.json`，与面板配置保持双向同步。

| 配置项 | 类型 | 说明 |
|--------|------|------|
| `enable_keyword_trigger` | bool | 主开关 |
| `blacklist_mode` | string | 黑/白名单模式（blacklist/whitelist） |
| `match_groups` | list | 全量匹配组，在面板编辑所有组的完整配置 |
| `default_new_group` | list | 新建组模板，管理命令新建组时自动拷贝 |
| `blacklist_groups` | list | 群聊黑/白名单列表 |

> ⚠️ v4.5 已去除 `trigger_keywords`、`first_reply`、`quote_pool`、`reply_delay_ms`、`media_pool`、`reply_mode` 等独立字段。所有组的配置通过 `match_groups` 全量编辑，新建组时从 `default_new_group` 自动拷贝模板。

---

## 🧩 默认梗段一览

默认组内置 **11段** 梗段词库：

1. 啊😲？云朵☁️😄，哒↘哒↗哒↘哒↗哒↘，好想玩原神😨，云☁️原神😙
2. 当当当当当😊，看精彩纷纷👍🎊😆，云☁️原神😄，呜呜呜呜呜，好想玩原神😭😭😭云☁️原神
3. 朋友已就位😊😃😆，一起玩原神，云☁️原神！啊啊啊啊啊😙，好想玩原神😙云☁️原神，哈哈哈哈哈🤣🤣🤣，一起玩原神
4. 云☁️原神，好好好想，🤩想玩玩原神😋网页云端，低功耗不失真😌，WiFi网线🥰，都可以60帧😍
5. 来来来来👏，进入云☁️原神
6. 空间快爆炸，好想玩原神～✌🏻😀 / 云原神！
7. 进度软趴趴，好想玩原神～😀👌🏻 / 云原神！
8. 潜入了深海，想玩原神～🥴👍🏻 / 云原神！
9. 冲出了云层，也想玩原神！✌🏻🤪 / 云原神！！！
10. 低延迟高像素，随时玩原神～😤👌🏻 / 云原神！
11. 小体积大用处，快快玩原神～🙄🤚🏻 / 云原神！/ 好 好 好想，

新建组从空关键词开始，可自由添加专属梗段。

---

## 📁 数据持久化

| 文件 | 说明 |
|------|------|
| `data/plugin_data/astrbot_plugin_cloud_genshin/data.json` | 统一持久化（match_groups + blacklist_groups） |

所有管理命令修改即时保存，启动时自动加载。面板配置通过 configsync 或重启插件同步到 data.json。

---

## 📜 依赖

无外部依赖，纯 Python 标准库实现。

---

## 🧑‍💻 开发信息

- **插件名**: 好想玩云原神🎊
- **作者**: 极夜System
- **版本**: 4.5.0
- **兼容**: AstrBot v3.5+
- **分类**: 娱乐 / 梗

---

## ⚠️ 注意事项

- 关键词自动触发只对非命令消息生效
- **v2.x/v3.x 用户首次升级**：data.json 会自动迁移到 v4.x 的 `match_groups` 格式
- 私聊不受黑/白名单影响
- `enable_keyword_trigger` 关闭后自动触发全停，不影响手动命令

---

## 🤖 AI创作声明

本插件由 AI（Claude，Anthropic）辅助生成。

## 💬 问题反馈

[https://github.com/IPF-Sinon/astrbot_plugin_cloud_genshin/issues](https://github.com/IPF-Sinon/astrbot_plugin_cloud_genshin/issues)
