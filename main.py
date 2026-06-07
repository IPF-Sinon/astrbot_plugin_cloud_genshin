import os
import json
import random
import asyncio

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api.message_components import Plain


class Main(Star):
    """🎊 好想玩云原神🎊 — 关键词自动触发 + 手动命令，内置11段随机池 + 群聊黑名单"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # ====== 11段梗随机池 ======
        self.quotes = [
            # 长版拆段 ①
            "啊😲？云朵☁️😄，哒↘哒↗哒↘哒↗哒↘，好想玩原神😨，云☁️原神😙",
            # 长版拆段 ②
            "当当当当当😊，看精彩纷纷👍🎊😆，云☁️原神😄，呜呜呜呜呜，好想玩原神😭😭😭云☁️原神",
            # 长版拆段 ③
            "朋友已就位😊😃😆，一起玩原神，云☁️原神！啊啊啊啊啊😙，好想玩原神😙云☁️原神，哈哈哈哈哈🤣🤣🤣，一起玩原神",
            # 长版拆段 ④
            "云☁️原神，好好好想，🤩想玩玩原神😋网页云端，低功耗不失真😌，WiFi网线🥰，都可以60帧😍",
            # 长版拆段 ⑤
            "来来来来👏，进入云☁️原神",
            # 短版 ⑥
            "空间快爆炸，好想玩原神～✌🏻😀\n云原神！",
            # 短版 ⑦
            "进度软趴趴，好想玩原神～😀👌🏻\n云原神！",
            # 短版 ⑧
            "潜入了深海，想玩原神～🥴👍🏻\n云原神！",
            # 短版 ⑨
            "冲出了云层，也想玩原神！✌🏻🤪\n云原神！！！",
            # 短版 ⑩
            "低延迟高像素，随时玩原神～😤👌🏻\n云原神！",
            # 短版 ⑪
            "小体积大用处，快快玩原神～🙄🤚🏻\n云原神！\n好 好 好想，",
        ]

        # ====== 数据持久化目录 ======
        data_dir = StarTools.get_data_dir()
        self.plugin_data_dir = os.path.join(data_dir, "astrbot_plugin_cloud_genshin")
        self.keywords_file = os.path.join(self.plugin_data_dir, "custom_keywords.json")
        self.blacklist_file = os.path.join(self.plugin_data_dir, "custom_blacklist.json")

        # ====== 加载持久化数据 ======
        self.custom_keywords = self._load_json_list(self.keywords_file)
        self.custom_blacklist = self._load_json_list(self.blacklist_file)

        mode = self.config.get("blacklist_mode", "blacklist")
        config_groups = self.config.get("blacklist_groups", [])
        if not isinstance(config_groups, list):
            config_groups = []
        total_blacklisted = len(set(
            str(g) for g in config_groups + self.custom_blacklist
        ))

        logger.info(
            f"🎊 好想玩云原神🎊 已加载 | "
            f"梗段池: {len(self.quotes)}段 | "
            f"自定义关键词: {len(self.custom_keywords)}个 | "
            f"关键词触发: {'开' if self.config.get('enable_keyword_trigger', True) else '关'} | "
            f"黑名单模式: {mode} (共{total_blacklisted}个群)"
        )

    # ==================== 持久化方法 ====================

    def _load_json_list(self, filepath: str) -> list:
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list) and all(isinstance(k, str) for k in data):
                        return data
        except Exception as e:
            logger.error(f"加载文件失败 {filepath}: {e}")
        return []

    def _save_json_list(self, filepath: str, data: list):
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"保存文件失败 {filepath}: {e}")

    def _save_keywords(self):
        self._save_json_list(self.keywords_file, self.custom_keywords)

    def _save_blacklist(self):
        self._save_json_list(self.blacklist_file, self.custom_blacklist)

    # ==================== 核心方法 ====================

    def _get_random_quote(self) -> str:
        return random.choice(self.quotes)

    def _get_all_keywords(self) -> list:
        trigger = self.config.get("trigger_keywords", ["云朵", "云原神"])
        if not isinstance(trigger, list):
            trigger = ["云朵", "云原神"]
        return list(set(trigger + self.custom_keywords))

    def _is_group_blocked(self, event: AstrMessageEvent) -> bool:
        group_id = event.get_group_id()
        if not group_id:
            return False
        mode = self.config.get("blacklist_mode", "blacklist")
        config_groups = self.config.get("blacklist_groups", [])
        if not isinstance(config_groups, list):
            config_groups = []
        all_groups = set(str(g) for g in config_groups + self.custom_blacklist)
        if mode == "blacklist":
            return str(group_id) in all_groups
        else:
            return str(group_id) not in all_groups

    # ==================== 关键词自动触发 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        if not self.config.get("enable_keyword_trigger", True):
            return
        text = str(event.message_str or "").strip()
        if not text:
            return
        if text.startswith("云原神管理") or text == "cloudys":
            logger.debug(f"🎊 跳过命令消息: '{text}'")
            return
        if self._is_group_blocked(event):
            logger.debug(f"🎊 群 {event.get_group_id()} 在黑/白名单中，跳过触发")
            return
        keywords = self._get_all_keywords()
        matched_kw = None
        for kw in keywords:
            if kw in text:
                matched_kw = kw
                break
        if not matched_kw:
            return
        logger.info(
            f"🎊 关键词触发 | keyword='{matched_kw}' | "
            f"msg='{text[:40]}{'…' if len(text) > 40 else ''}'"
        )
        event.stop_event()
        delay_ms = self.config.get("reply_delay_ms", 800)
        quote = self._get_random_quote()
        asyncio.create_task(self._delayed_send(event, quote, delay_ms))
        yield event.plain_result("欸，云朵")

    async def _delayed_send(self, event: AstrMessageEvent, quote: str, delay_ms: int):
        try:
            await asyncio.sleep(delay_ms / 1000.0)
            await event.send(event.plain_result(quote))
            logger.info(f"🎊 后台发送梗段成功 | '{quote[:20]}…'")
        except Exception as e:
            logger.error(f"🎊 后台发送梗段失败: {e}")

    # ==================== 手动命令 ====================

    @filter.command("云原神")
    async def cmd_cloud_genshin(self, event: AstrMessageEvent):
        logger.info("🎊 手动触发 /云原神")
        quote = self._get_random_quote()
        yield event.plain_result(quote)

    @filter.command("cloudys")
    async def cmd_cloud_genshin_alias(self, event: AstrMessageEvent):
        logger.info("🎊 手动触发 /cloudys")
        quote = self._get_random_quote()
        yield event.plain_result(quote)

    # ==================== 管理命令 ====================

    @filter.command("云原神管理")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_admin(self, event: AstrMessageEvent):
        text = (event.message_str or "").strip()
        parts = text.split(maxsplit=2)

        if len(parts) < 2:
            yield event.plain_result(
                "📋 好想玩云原神🎊 管理命令：\n"
                "  /云原神管理 add <关键词>                  — 添加关键词\n"
                "  /云原神管理 remove <关键词>               — 删除关键词\n"
                "  /云原神管理 list                         — 列出关键词\n"
                "  /云原神管理 blacklist add <群号>          — 添加群到黑/白名单\n"
                "  /云原神管理 blacklist remove <群号>       — 从黑/白名单移除群\n"
                "  /云原神管理 blacklist list                — 列出黑/白名单群"
            )
            return

        subcmd = parts[1]

        # ----------- 关键词管理 -----------
        if subcmd in ("add", "remove", "list"):
            await self._handle_keyword_admin(event, subcmd, parts)
            return

        # ----------- 群组黑/白名单管理 -----------
        if subcmd == "blacklist":
            await self._handle_blacklist_admin(event, parts)
            return

        yield event.plain_result(f"❌ 未知子命令: {subcmd}，可用: add / remove / list / blacklist")

    # ==================== 关键词管理 ====================

    async def _handle_keyword_admin(self, event: AstrMessageEvent, subcmd: str, parts: list):
        """纯 async 函数，用 event.send() 发送消息"""
        if subcmd == "add":
            if len(parts) < 3 or not parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 add <关键词>"))
                return
            keyword = parts[2].strip()
            all_kw = self._get_all_keywords()
            if keyword in all_kw:
                await event.send(event.plain_result(f"⚠️ 关键词「{keyword}」已存在（可在管理面板或 list 查看来源）"))
                return
            self.custom_keywords.append(keyword)
            self._save_keywords()
            await event.send(event.plain_result(
                f"✅ 已添加关键词「{keyword}」\n"
                f"当前共 {len(self.custom_keywords)} 个持久化自定义关键词"
            ))

        elif subcmd == "remove":
            if len(parts) < 3 or not parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 remove <关键词>"))
                return
            keyword = parts[2].strip()
            if keyword in self.custom_keywords:
                self.custom_keywords.remove(keyword)
                self._save_keywords()
                await event.send(event.plain_result(
                    f"✅ 已从持久化自定义关键词中删除「{keyword}」\n"
                    f"剩余 {len(self.custom_keywords)} 个持久化自定义关键词"
                ))
                return
            trigger = self.config.get("trigger_keywords", [])
            if not isinstance(trigger, list):
                trigger = []
            if keyword in trigger:
                await event.send(event.plain_result(
                    f"💡 「{keyword}」在管理面板的 trigger_keywords 配置中，"
                    f"请到 AstrBot 管理面板 → 插件配置 → 好想玩云原神🎊 → "
                    f"trigger_keywords 中编辑移除"
                ))
                return
            await event.send(event.plain_result(f"❌ 未在任何关键词源中找到「{keyword}」"))

        elif subcmd == "list":
            trigger = self.config.get("trigger_keywords", ["云朵", "云原神"])
            if not isinstance(trigger, list):
                trigger = ["云朵", "云原神"]
            lines = ["📋 好想玩云原神🎊 触发关键词列表：\n"]
            lines.append("🔵 配置关键词（来源 _conf_schema.json → trigger_keywords）：")
            if trigger:
                for kw in trigger:
                    lines.append(f"   • {kw}")
                lines.append("   💡 可到管理面板编辑增删")
            else:
                lines.append("   （空）")
            if self.custom_keywords:
                lines.append("\n🟡 持久化自定义关键词（可通过管理命令增删）：")
                for i, kw in enumerate(self.custom_keywords, 1):
                    lines.append(f"   {i}. {kw}")
            else:
                lines.append("\n🟡 持久化自定义关键词：（暂无）")
            await event.send(event.plain_result("\n".join(lines)))

    # ==================== 黑名单管理 ====================

    async def _handle_blacklist_admin(self, event: AstrMessageEvent, parts: list):
        """纯 async 函数，用 event.send() 发送消息"""
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
            if group_id in self.custom_blacklist:
                await event.send(event.plain_result(f"⚠️ 群 {group_id} 已在名单中"))
                return
            self.custom_blacklist.append(group_id)
            self._save_blacklist()
            mode = self.config.get("blacklist_mode", "blacklist")
            await event.send(event.plain_result(
                f"✅ 已将群 {group_id} 添加到{'黑' if mode == 'blacklist' else '白'}名单\n"
                f"当前共 {len(self.custom_blacklist)} 个群（通过管理命令管理）"
            ))

        elif action == "remove":
            if not arg:
                await event.send(event.plain_result("❌ 用法：/云原神管理 blacklist remove <群号>"))
                return
            group_id = str(arg).strip()
            if group_id not in self.custom_blacklist:
                await event.send(event.plain_result(f"❌ 名单中未找到群 {group_id}"))
                config_groups = self.config.get("blacklist_groups", [])
                if not isinstance(config_groups, list):
                    config_groups = []
                if group_id in [str(g) for g in config_groups]:
                    await event.send(event.plain_result(
                        "💡 该群在 _conf_schema.json 的 blacklist_groups 配置中，"
                        "请到 AstrBot 管理面板修改配置来移除"
                    ))
                return
            self.custom_blacklist.remove(group_id)
            self._save_blacklist()
            mode = self.config.get("blacklist_mode", "blacklist")
            await event.send(event.plain_result(
                f"✅ 已将群 {group_id} 从{'黑' if mode == 'blacklist' else '白'}名单移除\n"
                f"剩余 {len(self.custom_blacklist)} 个群（通过管理命令管理）"
            ))

        elif action == "list":
            mode = self.config.get("blacklist_mode", "blacklist")
            config_groups = self.config.get("blacklist_groups", [])
            if not isinstance(config_groups, list):
                config_groups = []
            lines = [f"📋 群组{'黑' if mode == 'blacklist' else '白'}名单：\n"]
            if config_groups:
                lines.append(f"🔶 面板配置（来源 _conf_schema.json）：")
                for g in config_groups:
                    lines.append(f"   • {g}")
                lines.append("   💡 需到管理面板修改配置来增删")
                lines.append("")
            if self.custom_blacklist:
                lines.append(f"🟠 管理命令管理（可通过 blacklist add/remove 增删）：")
                for i, g in enumerate(self.custom_blacklist, 1):
                    lines.append(f"   {i}. {g}")
            else:
                lines.append("🟠 管理命令管理：（暂无，可使用 blacklist add <群号> 添加）")
            lines.append(f"\n📌 当前模式: {mode}")
            lines.append(
                "   blacklist = 名单中的群不触发 | "
                "whitelist = 仅名单中的群触发"
            )
            await event.send(event.plain_result("\n".join(lines)))

        else:
            await event.send(event.plain_result(f"❌ 未知操作: {action}，可用: add / remove / list"))

    # ==================== 生命周期 ====================

    async def terminate(self):
        self._save_keywords()
        self._save_blacklist()
        logger.info("🎊 好想玩云原神🎊 已卸载，数据已保存")
