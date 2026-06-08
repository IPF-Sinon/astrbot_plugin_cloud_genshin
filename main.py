import os
import json
import random
import asyncio

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api.message_components import Plain


class Main(Star):
    """🎊 好想玩云原神🎊 v2.0 — 全功能可配置云原神梗插件"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # ====== 数据持久化目录 ======
        data_dir = StarTools.get_data_dir()
        self.plugin_data_dir = os.path.join(data_dir, "astrbot_plugin_cloud_genshin")
        self.data_file = os.path.join(self.plugin_data_dir, "data.json")

        # ====== 初始化数据（从持久化加载，不存在则从配置获取默认值） ======
        self.data = self._load_data()

        # 启动日志
        kw_count = len(self.data.get("trigger_keywords", []))
        qp_count = len(self.data.get("quote_pool", []))
        bl_count = len(self.data.get("blacklist_groups", []))
        mode = self.config.get("blacklist_mode", "blacklist")
        logger.info(
            f"🎊 好想玩云原神🎊 v2.0 已加载 | "
            f"梗段池: {qp_count}段 | "
            f"关键词: {kw_count}个 | "
            f"关键词触发: {'开' if self.config.get('enable_keyword_trigger', True) else '关'} | "
            f"黑名单模式: {mode} (共{bl_count}个群)"
        )

    # ==================== 持久化方法 ====================

    def _load_data(self) -> dict:
        """
        加载持久化数据 data.json。
        如果文件存在则读取，否则从配置（_conf_schema.json）获取默认值并保存。
        """
        # 默认值模板（从配置获取）
        default_data = {
            "trigger_keywords": self.config.get("trigger_keywords", ["云朵", "云原神"]),
            "first_reply": str(self.config.get("first_reply", "欸，云朵") or "欸，云朵"),
            "quote_pool": self.config.get("quote_pool", [
                "啊😲？云朵☁️😄，哒↘哒↗哒↘哒↗哒↘，好想玩原神😨，云☁️原神😙",
                "当当当当当😊，看精彩纷纷👍🎊😆，云☁️原神😄，呜呜呜呜呜，好想玩原神😭😭😭云☁️原神",
                "朋友已就位😊😃😆，一起玩原神，云☁️原神！啊啊啊啊啊😙，好想玩原神😙云☁️原神，哈哈哈哈哈🤣🤣🤣，一起玩原神",
                "云☁️原神，好好好想，🤩想玩玩原神😋网页云端，低功耗不失真😌，WiFi网线🥰，都可以60帧😍",
                "来来来来👏，进入云☁️原神",
                "空间快爆炸，好想玩原神～✌🏻😀 / 云原神！",
                "进度软趴趴，好想玩原神～😀👌🏻 / 云原神！",
                "潜入了深海，想玩原神～🥴👍🏻 / 云原神！",
                "冲出了云层，也想玩原神！✌🏻🤪 / 云原神！！！",
                "低延迟高像素，随时玩原神～😤👌🏻 / 云原神！",
                "小体积大用处，快快玩原神～🙄🤚🏻 / 云原神！/ 好 好 好想，"
            ]),
            "blacklist_groups": self.config.get("blacklist_groups", [])
        }

        # 确保类型正确
        if not isinstance(default_data["trigger_keywords"], list):
            default_data["trigger_keywords"] = ["云朵", "云原神"]
        if not isinstance(default_data["quote_pool"], list):
            default_data["quote_pool"] = []
        if not isinstance(default_data["blacklist_groups"], list):
            default_data["blacklist_groups"] = []

        # 尝试从持久化文件加载
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        # 用持久化值覆盖默认值（保留已有字段）
                        for key in default_data:
                            if key in saved and saved[key] is not None:
                                default_data[key] = saved[key]
                        logger.info(f"🎊 从持久化文件加载配置成功")
        except Exception as e:
            logger.error(f"🎊 加载持久化文件失败: {e}")

        # 确保数组类型
        for key in ("trigger_keywords", "quote_pool", "blacklist_groups"):
            if not isinstance(default_data.get(key), list):
                default_data[key] = []

        return default_data

    def _save_data(self):
        """将当前数据持久化到 data.json"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"🎊 保存持久化数据失败: {e}")

    # ==================== 核心方法 ====================

    def _get_random_quote(self) -> str:
        """从梗段词库中随机取一段"""
        quotes = self.data.get("quote_pool", [])
        if not isinstance(quotes, list) or not quotes:
            return "啊😲？云朵☁️😄，好想玩原神😨……"
        return random.choice(quotes)

    def _is_group_blocked(self, event: AstrMessageEvent) -> bool:
        """
        检查当前群聊是否被屏蔽。
        - blacklist 模式：名单中的群不触发
        - whitelist 模式：仅名单中的群触发
        - 私聊永远不屏蔽
        """
        group_id = event.get_group_id()
        if not group_id:
            return False  # 私聊不屏蔽

        mode = self.config.get("blacklist_mode", "blacklist")

        # 从持久化数据中读取群列表
        all_groups = self.data.get("blacklist_groups", [])
        if not isinstance(all_groups, list):
            all_groups = []
        all_groups = set(str(g) for g in all_groups)

        if mode == "blacklist":
            return str(group_id) in all_groups
        else:
            return str(group_id) not in all_groups

    # ==================== 关键词自动触发 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """
        监听所有消息 — 检测到关键词时自动回复。

        架构说明：
        ① 只用 event.message_str，永不为 None
        ② 过滤命令消息：/云原神管理、/cloudys 跳过，但 /云原神 保留触发
        ③ create_task 在 yield 前，保证后台任务被事件循环调度
        """
        # ① 检查是否启用关键词触发
        if not self.config.get("enable_keyword_trigger", True):
            return

        # ② 获取消息文本
        text = str(event.message_str or "").strip()
        if not text:
            return

        # ③ 过滤命令消息
        if text.startswith("云原神管理") or text == "cloudys":
            logger.debug(f"🎊 跳过命令消息: '{text}'")
            return

        # ④ 检查群聊黑/白名单
        if self._is_group_blocked(event):
            logger.debug(f"🎊 群 {event.get_group_id()} 在黑/白名单中，跳过触发")
            return

        # ⑤ 关键词匹配
        keywords = self.data.get("trigger_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        matched_kw = None
        for kw in keywords:
            if kw in text:
                matched_kw = kw
                break

        if not matched_kw:
            return

        # === 匹配成功！回复流程 ===
        logger.info(
            f"🎊 关键词触发 | keyword='{matched_kw}' | "
            f"msg='{text[:40]}{'…' if len(text) > 40 else ''}'"
        )

        event.stop_event()

        # ⑥ 创建后台协程延迟发送梗段
        delay_ms = self.config.get("reply_delay_ms", 800)
        quote = self._get_random_quote()
        asyncio.create_task(self._delayed_send(event, quote, delay_ms))

        # ⑦ 第一条用 yield 发送首次回复词
        first_reply = str(self.data.get("first_reply", "欸，云朵") or "欸，云朵")
        yield event.plain_result(first_reply)

    async def _delayed_send(self, event: AstrMessageEvent, quote: str, delay_ms: int):
        """后台延迟发送梗段"""
        try:
            await asyncio.sleep(delay_ms / 1000.0)
            await event.send(event.plain_result(quote))
            logger.info(f"🎊 后台发送梗段成功 | '{quote[:20]}…'")
        except Exception as e:
            logger.error(f"🎊 后台发送梗段失败: {e}")

    # ==================== 手动命令 ====================

    @filter.command("云原神")
    async def cmd_cloud_genshin(self, event: AstrMessageEvent):
        """手动触发：随机回复一段云原神梗"""
        logger.info("🎊 手动触发 /云原神")
        quote = self._get_random_quote()
        yield event.plain_result(quote)

    @filter.command("cloudys")
    async def cmd_cloud_genshin_alias(self, event: AstrMessageEvent):
        """手动触发别名：/cloudys"""
        logger.info("🎊 手动触发 /cloudys")
        quote = self._get_random_quote()
        yield event.plain_result(quote)

    # ==================== 管理命令 ====================

    @filter.command("云原神管理")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_admin(self, event: AstrMessageEvent):
        """
        云原神管理命令 v2.0
        用法：
          /云原神管理 add <关键词>                  — 添加触发关键词
          /云原神管理 remove <关键词>               — 删除触发关键词
          /云原神管理 list                         — 列出所有触发关键词
          /云原神管理 first_reply <文本>             — 设置首次回复词
          /云原神管理 quote list                    — 列出所有梗段
          /云原神管理 quote add <梗段>              — 添加梗段
          /云原神管理 quote remove <编号>           — 删除指定编号的梗段
          /云原神管理 quote set <编号> <新内容>      — 修改指定编号的梗段
          /云原神管理 blacklist add <群号>           — 添加群到黑/白名单
          /云原神管理 blacklist remove <群号>        — 从黑/白名单移除群
          /云原神管理 blacklist list                 — 列出黑/白名单中的群
        """
        text = (event.message_str or "").strip()
        parts = text.split(maxsplit=2)

        if len(parts) < 2:
            yield event.plain_result(
                "📋 好想玩云原神🎊 v2.0 管理命令：\n"
                "  /云原神管理 add <关键词>                    — 添加关键词\n"
                "  /云原神管理 remove <关键词>                 — 删除关键词\n"
                "  /云原神管理 list                           — 列出关键词\n"
                "  /云原神管理 first_reply <文本>              — 设首次回复词\n"
                "  /云原神管理 quote add/remove/list/set       — 管理梗段词库\n"
                "  /云原神管理 blacklist add/remove/list       — 管理群名单\n"
                "  /云原神管理 status                         — 查看当前状态"
            )
            return

        subcmd = parts[1]

        # ============= 关键词管理 =============
        if subcmd in ("add", "remove", "list"):
            await self._handle_keyword_admin(event, subcmd, parts)
            return

        # ============= 首次回复词管理 =============
        if subcmd == "first_reply":
            await self._handle_first_reply_admin(event, parts)
            return

        # ============= 梗段词库管理 =============
        if subcmd == "quote":
            await self._handle_quote_admin(event, parts)
            return

        # ============= 群组黑/白名单管理 =============
        if subcmd == "blacklist":
            await self._handle_blacklist_admin(event, parts)
            return

        # ============= 状态查看 =============
        if subcmd == "status":
            await self._handle_status(event)
            return

        yield event.plain_result(
            f"❌ 未知子命令: {subcmd}，可用: add / remove / list / first_reply / quote / blacklist / status"
        )

    # ==================== 关键词管理子逻辑 ====================

    async def _handle_keyword_admin(self, event: AstrMessageEvent, subcmd: str, parts: list):
        """处理关键词的添加/删除/列出（统一操作持久化数据中的 trigger_keywords）"""
        keywords = self.data.get("trigger_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
            self.data["trigger_keywords"] = keywords

        if subcmd == "add":
            if len(parts) < 3 or not parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 add <关键词>"))
                return
            keyword = parts[2].strip()

            if keyword in keywords:
                await event.send(event.plain_result(f"⚠️ 关键词「{keyword}」已存在"))
                return

            keywords.append(keyword)
            self.data["trigger_keywords"] = keywords
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 已添加关键词「{keyword}」\n"
                f"当前共 {len(keywords)} 个关键词"
            ))

        elif subcmd == "remove":
            if len(parts) < 3 or not parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 remove <关键词>"))
                return
            keyword = parts[2].strip()

            if keyword in keywords:
                keywords.remove(keyword)
                self.data["trigger_keywords"] = keywords
                self._save_data()
                await event.send(event.plain_result(
                    f"✅ 已删除关键词「{keyword}」\n"
                    f"剩余 {len(keywords)} 个关键词"
                ))
            else:
                await event.send(event.plain_result(f"❌ 未找到关键词「{keyword}」"))

        elif subcmd == "list":
            lines = ["📋 好想玩云原神🎊 触发关键词列表：\n"]
            if keywords:
                for i, kw in enumerate(keywords, 1):
                    lines.append(f"  {i}. {kw}")
            else:
                lines.append("  （暂无关键词，可用 add <关键词> 添加）")

            lines.append("\n💡 可用 add / remove 管理，修改后自动持久化保存")
            await event.send(event.plain_result("\n".join(lines)))

    # ==================== 首次回复词管理子逻辑 ====================

    async def _handle_first_reply_admin(self, event: AstrMessageEvent, parts: list):
        """处理首次回复词的查看和设置"""
        if len(parts) < 3:
            current = str(self.data.get("first_reply", "欸，云朵"))
            await event.send(event.plain_result(
                f"📋 当前首次回复词：\n「{current}」\n\n"
                "💡 设置新值：/云原神管理 first_reply <新文本>"
            ))
            return

        new_text = parts[2].strip()
        if not new_text:
            await event.send(event.plain_result("❌ 首次回复词不能为空"))
            return

        self.data["first_reply"] = new_text
        self._save_data()
        await event.send(event.plain_result(
            f"✅ 首次回复词已设置为：\n「{new_text}」\n"
            "下次触发时将使用新文本"
        ))

    # ==================== 梗段词库管理子逻辑 ====================

    async def _handle_quote_admin(self, event: AstrMessageEvent, parts: list):
        """处理梗段词库的增删改查"""
        quotes = self.data.get("quote_pool", [])
        if not isinstance(quotes, list):
            quotes = []
            self.data["quote_pool"] = quotes

        if len(parts) < 3 or not parts[2].strip():
            # 显示帮助
            await event.send(event.plain_result(
                "📋 梗段词库管理：\n"
                "  /云原神管理 quote list              — 列出所有梗段\n"
                "  /云原神管理 quote add <梗段>        — 添加新梗段\n"
                "  /云原神管理 quote remove <编号>     — 删除指定梗段\n"
                "  /云原神管理 quote set <编号> <内容>  — 修改指定梗段\n\n"
                f"当前共 {len(quotes)} 段梗"
            ))
            return

        sub2 = parts[2].strip()
        sub2_parts = sub2.split(maxsplit=1)
        action = sub2_parts[0]

        if action == "list":
            lines = [f"🗂️ 梗段词库（共 {len(quotes)} 段）：\n"]
            if quotes:
                for i, q in enumerate(quotes, 1):
                    display = q[:40] + "…" if len(q) > 40 else q
                    lines.append(f"  {i}. {display}")
                lines.append("\n💡 可用 quote add / remove / set 管理")
            else:
                lines.append("  （暂无梗段，可用 quote add <内容> 添加）")
            await event.send(event.plain_result("\n".join(lines)))

        elif action == "add":
            if len(sub2_parts) < 2 or not sub2_parts[1].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 quote add <梗段内容>"))
                return
            content = sub2_parts[1].strip()
            quotes.append(content)
            self.data["quote_pool"] = quotes
            self._save_data()
            display = content[:30] + "…" if len(content) > 30 else content
            await event.send(event.plain_result(
                f"✅ 已添加梗段 #{len(quotes)}：\n「{display}」\n"
                f"当前共 {len(quotes)} 段梗"
            ))

        elif action == "remove":
            if len(sub2_parts) < 2 or not sub2_parts[1].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 quote remove <编号>"))
                return
            try:
                idx = int(sub2_parts[1].strip())
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return

            if idx < 1 or idx > len(quotes):
                await event.send(event.plain_result(f"❌ 编号 {idx} 超出范围（1~{len(quotes)}）"))
                return

            removed = quotes.pop(idx - 1)
            self.data["quote_pool"] = quotes
            self._save_data()
            display = removed[:30] + "…" if len(removed) > 30 else removed
            await event.send(event.plain_result(
                f"✅ 已删除梗段 #{idx}：\n「{display}」\n"
                f"剩余 {len(quotes)} 段梗"
            ))

        elif action == "set":
            # set 需要编号 + 内容，格式：/云原神管理 quote set 3 新内容
            # 由于 split 限制，需要特殊处理
            # parts[2] 是 "set 3 新内容..." 或 "set 3"
            rest = parts[2].strip() if len(parts) >= 3 else ""
            # rest 格式: "set <编号> <内容>"
            set_parts = rest.split(maxsplit=2)
            if len(set_parts) < 3:
                await event.send(event.plain_result("❌ 用法：/云原神管理 quote set <编号> <新内容>"))
                return
            try:
                idx = int(set_parts[1])
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return

            if idx < 1 or idx > len(quotes):
                await event.send(event.plain_result(f"❌ 编号 {idx} 超出范围（1~{len(quotes)}）"))
                return

            new_content = set_parts[2].strip()
            if not new_content:
                await event.send(event.plain_result("❌ 梗段内容不能为空"))
                return

            old = quotes[idx - 1]
            quotes[idx - 1] = new_content
            self.data["quote_pool"] = quotes
            self._save_data()
            old_display = old[:20] + "…" if len(old) > 20 else old
            new_display = new_content[:20] + "…" if len(new_content) > 20 else new_content
            await event.send(event.plain_result(
                f"✅ 已修改梗段 #{idx}：\n"
                f"  旧: 「{old_display}」\n"
                f"  新: 「{new_display}」"
            ))

        else:
            await event.send(event.plain_result(f"❌ 未知操作: {action}，可用: add / remove / list / set"))

    # ==================== 黑名单管理子逻辑 ====================

    async def _handle_blacklist_admin(self, event: AstrMessageEvent, parts: list):
        """
        处理黑/白名单的添加/删除/列出。
        统一操作持久化数据中的 blacklist_groups。
        """
        groups = self.data.get("blacklist_groups", [])
        if not isinstance(groups, list):
            groups = []
            self.data["blacklist_groups"] = groups

        if len(parts) < 3 or not parts[2].strip():
            mode = self.config.get("blacklist_mode", "blacklist")
            await event.send(event.plain_result(
                f"📋 群组管理（当前模式: {mode}）：\n"
                "  /云原神管理 blacklist add <群号>    — 添加群\n"
                "  /云原神管理 blacklist remove <群号> — 移除群\n"
                "  /云原神管理 blacklist list          — 列出群"
            ))
            return

        sub2 = parts[2].strip()
        sub2_parts = sub2.split(maxsplit=1)
        action = sub2_parts[0]
        arg = sub2_parts[1].strip() if len(sub2_parts) > 1 else ""

        if action == "add":
            if not arg:
                await event.send(event.plain_result("❌ 用法：/云原神管理 blacklist add <群号>"))
                return

            group_id = str(arg).strip()
            if group_id in groups:
                await event.send(event.plain_result(f"⚠️ 群 {group_id} 已在名单中"))
                return

            groups.append(group_id)
            self.data["blacklist_groups"] = groups
            self._save_data()

            mode = self.config.get("blacklist_mode", "blacklist")
            await event.send(event.plain_result(
                f"✅ 已将群 {group_id} 添加到{'黑' if mode == 'blacklist' else '白'}名单\n"
                f"当前共 {len(groups)} 个群"
            ))

        elif action == "remove":
            if not arg:
                await event.send(event.plain_result("❌ 用法：/云原神管理 blacklist remove <群号>"))
                return

            group_id = str(arg).strip()
            if group_id not in groups:
                await event.send(event.plain_result(f"❌ 名单中未找到群 {group_id}"))
                return

            groups.remove(group_id)
            self.data["blacklist_groups"] = groups
            self._save_data()

            mode = self.config.get("blacklist_mode", "blacklist")
            await event.send(event.plain_result(
                f"✅ 已将群 {group_id} 从{'黑' if mode == 'blacklist' else '白'}名单移除\n"
                f"剩余 {len(groups)} 个群"
            ))

        elif action == "list":
            mode = self.config.get("blacklist_mode", "blacklist")
            lines = [f"📋 群组{'黑' if mode == 'blacklist' else '白'}名单（共 {len(groups)} 个）：\n"]
            if groups:
                for i, g in enumerate(groups, 1):
                    lines.append(f"  {i}. {g}")
            else:
                lines.append("  （暂无群，可用 blacklist add <群号> 添加）")

            lines.append(f"\n📌 当前模式: {mode}")
            lines.append(
                "   blacklist = 名单中的群不触发 | "
                "whitelist = 仅名单中的群触发"
            )
            lines.append("\n💡 切换模式请到 AstrBot 管理面板修改 blacklist_mode 配置")
            await event.send(event.plain_result("\n".join(lines)))

        else:
            await event.send(event.plain_result(f"❌ 未知操作: {action}，可用: add / remove / list"))

    # ==================== 状态查看 ====================

    async def _handle_status(self, event: AstrMessageEvent):
        """查看当前插件整体状态"""
        keywords = self.data.get("trigger_keywords", [])
        if not isinstance(keywords, list):
            keywords = []
        quotes = self.data.get("quote_pool", [])
        if not isinstance(quotes, list):
            quotes = []
        groups = self.data.get("blacklist_groups", [])
        if not isinstance(groups, list):
            groups = []
        first_reply = str(self.data.get("first_reply", "欸，云朵"))
        trigger_enabled = self.config.get("enable_keyword_trigger", True)
        mode = self.config.get("blacklist_mode", "blacklist")
        delay = self.config.get("reply_delay_ms", 800)

        await event.send(event.plain_result(
            "📊 好想玩云原神🎊 v2.0 状态\n"
            "━━━━━━━━━━━━━━━━━━\n"
            f"🔘 关键词触发: {'✅ 开启' if trigger_enabled else '❌ 关闭'}\n"
            f"🗂️ 触发关键词: {len(keywords)} 个\n"
            f"💬 首次回复词: 「{first_reply}」\n"
            f"🎭 梗段词库: {len(quotes)} 段\n"
            f"⏱️ 回复延迟: {delay}ms\n"
            f"🚫 群名单模式: {mode}（{len(groups)} 个群）\n"
            "━━━━━━━━━━━━━━━━━━\n"
            "可用 /云原神管理 查看完整帮助"
        ))

    # ==================== 生命周期 ====================

    async def terminate(self):
        """插件卸载时保存数据"""
        self._save_data()
        logger.info("🎊 好想玩云原神🎊 v2.0 已卸载，数据已保存")
