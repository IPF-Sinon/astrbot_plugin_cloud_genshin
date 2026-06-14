import os
import json
import random
import asyncio
import copy

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api.message_components import Plain, Image, Record, Video

# ==================== 常量 ====================

REPLY_MODES = ["text", "media", "text_media", "media_text", "mixed"]
MEDIA_TYPES = ["image", "record", "video"]
SOURCE_TYPES = ["url", "local"]

MODE_HELP = {
    "text": "纯文本回复（从 quote_pool 随机取文本）",
    "media": "纯媒体回复（从 media_pool 随机取媒体）",
    "text_media": "文本 + 媒体",
    "media_text": "媒体 + 文本",
    "mixed": "随机混合模式（默认）"
}


# ==================== 默认匹配组工厂 ====================

def _make_default_group(config: AstrBotConfig) -> dict:
    return {
        "name": "默认组",
        "keywords": config.get("trigger_keywords", ["云朵", "云原神"]),
        "first_reply": str(config.get("first_reply", "欸，云朵") or "欸，云朵"),
        "quote_pool": config.get("quote_pool", [
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
        "reply_delay_ms": config.get("reply_delay_ms", 800),
        "media_pool": [],
        "reply_mode": "mixed"
    }


# ==================== 主插件类 ====================

class Main(Star):
    """🎊 好想玩云原神🎊 v4.3 — 多媒体 · 灵活回复模式"""

    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config

        # ====== 数据持久化目录 ======
        data_dir = StarTools.get_data_dir()
        self.plugin_data_dir = os.path.join(data_dir, "astrbot_plugin_cloud_genshin")
        self.data_file = os.path.join(self.plugin_data_dir, "data.json")

        # ====== 加载数据 ======
        self.data = self._load_data()

        # 启动日志
        groups = self.data.get("match_groups", [])
        total_kw = sum(len(g.get("keywords", [])) for g in groups)
        total_qp = sum(len(g.get("quote_pool", [])) for g in groups)
        total_mp = sum(len(g.get("media_pool", [])) for g in groups)
        bl_count = len(self.data.get("blacklist_groups", []))
        mode = self.config.get("blacklist_mode", "blacklist")

        logger.info(
            f"🎊 好想玩云原神🎊 v4.3 已加载 | "
            f"{len(groups)} 个匹配组 | "
            f"总关键词: {total_kw}个 | "
            f"总梗段: {total_qp}段 | "
            f"总媒体: {total_mp}个 | "
            f"关键词触发: {'开' if self.config.get('enable_keyword_trigger', True) else '关'} | "
            f"黑名单模式: {mode} (共{bl_count}个群)"
        )

    # ==================== 持久化方法 ====================

    def _load_data(self) -> dict:
        """加载持久化数据。兼容 v2.x 旧格式，自动迁移到 match_groups。"""
        default_group = _make_default_group(self.config)

        # 确保必要字段
        data = {
            "match_groups": [dict(default_group)],
            "blacklist_groups": self.config.get("blacklist_groups", []),
            "_version": "4.0"
        }

        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        # ── v3.0+ 格式 ──
                        if "match_groups" in saved:
                            data["match_groups"] = saved["match_groups"]
                            if "blacklist_groups" in saved:
                                data["blacklist_groups"] = saved["blacklist_groups"]
                            logger.info("🎊 v3.0+ 格式加载成功")
                        # ── v2.x 格式迁移 ──
                        elif "trigger_keywords" in saved:
                            old_kw = saved.get("trigger_keywords", ["云朵", "云原神"])
                            old_fr = str(saved.get("first_reply", "欸，云朵") or "欸，云朵")
                            old_qp = saved.get("quote_pool", default_group["quote_pool"])
                            old_bl = saved.get("blacklist_groups", [])
                            if not isinstance(old_kw, list): old_kw = ["云朵", "云原神"]
                            if not isinstance(old_qp, list): old_qp = default_group["quote_pool"]
                            if not isinstance(old_bl, list): old_bl = []
                            data["match_groups"] = [{
                                "name": "默认组",
                                "keywords": old_kw,
                                "first_reply": old_fr,
                                "quote_pool": old_qp,
                                "reply_delay_ms": self.config.get("reply_delay_ms", 800),
                                "media_pool": [],
                                "reply_mode": "mixed"
                            }]
                            data["blacklist_groups"] = old_bl
                            logger.info("🎊 已从 v2.x 格式迁移到 v4.3")
                            self._save_data_inner(data)
        except Exception as e:
            logger.error(f"🎊 加载持久化文件失败: {e}")

        # 校验 match_groups
        mg = data.get("match_groups", [])
        if not isinstance(mg, list) or not mg:
            mg = [dict(default_group)]

        for i, g in enumerate(mg):
            if not isinstance(g, dict):
                mg[i] = dict(default_group)
                continue
            if "name" not in g or not g["name"]:
                g["name"] = f"组{i+1}"
            if "keywords" not in g or not isinstance(g["keywords"], list):
                g["keywords"] = []
            if "first_reply" not in g or not g["first_reply"]:
                g["first_reply"] = default_group["first_reply"]
            if "quote_pool" not in g or not isinstance(g["quote_pool"], list):
                g["quote_pool"] = list(default_group["quote_pool"])
            if "reply_delay_ms" not in g or not isinstance(g["reply_delay_ms"], (int, float)):
                g["reply_delay_ms"] = self.config.get("reply_delay_ms", 800)
            # v4.3 新增字段
            if "media_pool" not in g or not isinstance(g["media_pool"], list):
                g["media_pool"] = []
            if "reply_mode" not in g or g["reply_mode"] not in REPLY_MODES:
                g["reply_mode"] = "mixed"

        data["match_groups"] = mg

        # 校验 blacklist_groups
        bl = data.get("blacklist_groups", [])
        if not isinstance(bl, list): bl = []
        data["blacklist_groups"] = bl

        # ====== 面板配置 → 全量同步 ======
        # 优先级：面板 match_groups（全量）> 面板各独立字段（仅默认组）
        panel_mg = self.config.get("match_groups", None)
        if panel_mg is not None and isinstance(panel_mg, list) and len(panel_mg) > 0:
            # 面板有全量 match_groups，用面板配置全覆盖
            data["match_groups"] = copy.deepcopy(panel_mg)
            logger.info(f"🎊 面板配置 match_groups 已全量同步（{len(panel_mg)} 个组）")
        elif data["match_groups"]:
            # 面板没有 match_groups，用各独立字段仅刷新默认组
            default = data["match_groups"][0]
            kw = self.config.get("trigger_keywords", None)
            if kw is not None and isinstance(kw, list):
                default["keywords"] = list(kw)
            fr = self.config.get("first_reply", None)
            if fr is not None and isinstance(fr, str):
                default["first_reply"] = fr
            dl = self.config.get("reply_delay_ms", None)
            if dl is not None and isinstance(dl, (int, float)):
                default["reply_delay_ms"] = dl
            qp = self.config.get("quote_pool", None)
            if qp is not None and isinstance(qp, list):
                default["quote_pool"] = list(qp)
            rm = self.config.get("reply_mode", None)
            if rm is not None and rm in REPLY_MODES:
                default["reply_mode"] = rm
            mp = self.config.get("media_pool", None)
            if mp is not None and isinstance(mp, list):
                default["media_pool"] = list(mp)

        return data

    def _sync_config_to_data(self):
        """将面板配置同步到所有匹配组（运行时调用）。
        
        优先使用面板的 match_groups 全量覆盖 data.json；
        若无则用各独立字段仅同步默认组。
        """
        panel_mg = self.config.get("match_groups", None)
        if panel_mg is not None and isinstance(panel_mg, list) and len(panel_mg) > 0:
            # 全量同步：面板 match_groups → data.json
            self.data["match_groups"] = copy.deepcopy(panel_mg)
            # 校验补全字段
            for g in self.data["match_groups"]:
                if "name" not in g or not g["name"]: g["name"] = "未命名组"
                if "keywords" not in g or not isinstance(g["keywords"], list): g["keywords"] = []
                if "first_reply" not in g or not g["first_reply"]: g["first_reply"] = "欸，云朵"
                if "quote_pool" not in g or not isinstance(g["quote_pool"], list): g["quote_pool"] = []
                if "reply_delay_ms" not in g or not isinstance(g["reply_delay_ms"], (int, float)): g["reply_delay_ms"] = 800
                if "media_pool" not in g or not isinstance(g["media_pool"], list): g["media_pool"] = []
                if "reply_mode" not in g or g["reply_mode"] not in REPLY_MODES: g["reply_mode"] = "mixed"
            self._save_data()
            logger.info(f"🎊 configsync: 面板 match_groups 已全量同步（{len(panel_mg)} 个组）")
        else:
            # 无面板 match_groups，仅同步默认组各独立字段
            groups = self.data.get("match_groups", [])
            if not groups:
                return
            default = groups[0]
            kw = self.config.get("trigger_keywords", None)
            if kw is not None and isinstance(kw, list): default["keywords"] = list(kw)
            fr = self.config.get("first_reply", None)
            if fr is not None and isinstance(fr, str): default["first_reply"] = fr
            dl = self.config.get("reply_delay_ms", None)
            if dl is not None and isinstance(dl, (int, float)): default["reply_delay_ms"] = dl
            qp = self.config.get("quote_pool", None)
            if qp is not None and isinstance(qp, list): default["quote_pool"] = list(qp)
            rm = self.config.get("reply_mode", None)
            if rm is not None and rm in REPLY_MODES: default["reply_mode"] = rm
            mp = self.config.get("media_pool", None)
            if mp is not None and isinstance(mp, list): default["media_pool"] = list(mp)
            self._save_data()

    def _save_data_inner(self, data: dict):
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"🎊 保存数据失败: {e}")

    def _save_data(self):
        self._save_data_inner(self.data)

    # ==================== 核心方法 ====================

    def _find_group(self, name: str) -> int:
        """按名称查找组，返回索引，未找到返回 -1"""
        groups = self.data.get("match_groups", [])
        for i, g in enumerate(groups):
            if g.get("name") == name:
                return i
        return -1

    def _get_default_group(self) -> dict:
        groups = self.data.get("match_groups", [])
        if groups:
            return groups[0]
        g = _make_default_group(self.config)
        self.data["match_groups"] = [g]
        return g

    def _match_message(self, text: str) -> dict:
        """按组顺序匹配消息，返回匹配到的组，未匹配返回 None"""
        groups = self.data.get("match_groups", [])
        for g in groups:
            keywords = g.get("keywords", [])
            if isinstance(keywords, list):
                for kw in keywords:
                    if kw and kw in text:
                        return g
        return None

    def _is_group_blocked(self, event: AstrMessageEvent) -> bool:
        group_id = event.get_group_id()
        if not group_id:
            return False
        mode = self.config.get("blacklist_mode", "blacklist")
        all_groups = self.data.get("blacklist_groups", [])
        if not isinstance(all_groups, list):
            all_groups = []
        all_groups = set(str(g) for g in all_groups)
        if mode == "blacklist":
            return str(group_id) in all_groups
        else:
            return str(group_id) not in all_groups

    # ==================== 回复方法 ====================

    def _get_random_quote_from_group(self, group: dict) -> str:
        quotes = group.get("quote_pool", [])
        if not isinstance(quotes, list) or not quotes:
            return "啊😲？云朵☁️😄，好想玩原神😨……"
        return random.choice(quotes)

    def _get_random_media(self, group: dict) -> dict:
        """从组内媒体池随机取一个媒体，没有返回 None"""
        mp = group.get("media_pool", [])
        if not isinstance(mp, list) or not mp:
            return None
        return random.choice(mp)

    async def _send_text_reply(self, event: AstrMessageEvent, group: dict):
        """发送文本梗段"""
        quote = self._get_random_quote_from_group(group)
        await event.send(event.plain_result(quote))
        logger.info(f"🎊 发送文本梗段成功 | '{quote[:20]}…'")

    async def _send_media(self, event: AstrMessageEvent, media_item: dict):
        """发送单个媒体组件"""
        try:
            mtype = media_item.get("type", "image")
            src = media_item.get("src", "")
            source = media_item.get("source", "url")

            if not src:
                logger.warning("🎊 媒体 src 为空，跳过")
                return

            if mtype == "image":
                if source == "url":
                    comp = Image(url=src)
                else:
                    comp = Image(file=src)
            elif mtype == "record":
                if source == "url":
                    comp = Record(url=src)
                else:
                    comp = Record(file=src)
            elif mtype == "video":
                if source == "url":
                    comp = Video(url=src)
                else:
                    comp = Video(file=src)
            else:
                logger.warning(f"🎊 未知媒体类型: {mtype}")
                return

            await event.send(comp)
            logger.info(f"🎊 发送媒体成功: {mtype} ({src[:40]}…)")
        except Exception as e:
            logger.error(f"🎊 发送媒体失败: {e}")
            # 降级：发送文本提示
            await event.send(event.plain_result(f"⚠️ (媒体发送失败) {e}"))

    async def _send_media_reply(self, event: AstrMessageEvent, group: dict):
        """发送媒体回复（从 media_pool 随机取）"""
        media_item = self._get_random_media(group)
        if not media_item:
            # 媒体池为空，降级到文本
            logger.info("🎊 media_pool 为空，降级到文本回复")
            await self._send_text_reply(event, group)
            return
        await self._send_media(event, media_item)

    async def _execute_reply(self, event: AstrMessageEvent, group: dict, delay_ms: int):
        """后台执行回复（根据 reply_mode 决定回复方式）"""
        try:
            await asyncio.sleep(delay_ms / 1000.0)

            mode = group.get("reply_mode", "mixed")
            has_media = bool(self._get_random_media(group))

            # 如果 mode 需要媒体但 media_pool 为空，降级到 text
            if not has_media and mode != "text":
                mode = "text"

            if mode == "text":
                await self._send_text_reply(event, group)
            elif mode == "media":
                await self._send_media_reply(event, group)
            elif mode == "text_media":
                await self._send_text_reply(event, group)
                await self._send_media_reply(event, group)
            elif mode == "media_text":
                await self._send_media_reply(event, group)
                await self._send_text_reply(event, group)
            elif mode == "mixed":
                # 随机选择一种回复模式
                choices = ["text"]
                if has_media:
                    choices.extend(["media", "text_media", "media_text"])
                choice = random.choice(choices)
                if choice == "text":
                    await self._send_text_reply(event, group)
                elif choice == "media":
                    await self._send_media_reply(event, group)
                elif choice == "text_media":
                    await self._send_text_reply(event, group)
                    await self._send_media_reply(event, group)
                elif choice == "media_text":
                    await self._send_media_reply(event, group)
                    await self._send_text_reply(event, group)
        except Exception as e:
            logger.error(f"🎊 后台回复执行失败: {e}")

    # ==================== 关键词自动触发 ====================

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息 — 多组匹配 + 多媒体回复"""
        if not self.config.get("enable_keyword_trigger", True):
            return

        text = str(event.message_str or "").strip()
        if not text:
            return

        if text.startswith("云原神管理") or text == "cloudys":
            return

        if self._is_group_blocked(event):
            return

        matched_group = self._match_message(text)
        if not matched_group:
            return

        matched_kw = None
        for kw in matched_group.get("keywords", []):
            if kw in text:
                matched_kw = kw
                break

        logger.info(
            f"🎊 组「{matched_group.get('name', '?')}」关键词触发 | "
            f"keyword='{matched_kw}' | "
            f"msg='{text[:40]}{'…' if len(text) > 40 else ''}'"
        )

        event.stop_event()

        delay_ms = matched_group.get("reply_delay_ms", 800)
        asyncio.create_task(self._execute_reply(event, matched_group, delay_ms))

        first_reply = str(matched_group.get("first_reply", "") or "")
        if first_reply:
            yield event.plain_result(first_reply)

    # ==================== 手动命令 ====================

    @filter.command("云原神")
    async def cmd_cloud_genshin(self, event: AstrMessageEvent):
        """手动触发：从第一个组随机取文本梗段"""
        logger.info("🎊 手动触发 /云原神")
        group = self._get_default_group()
        quote = self._get_random_quote_from_group(group)
        yield event.plain_result(quote)

    @filter.command("cloudys")
    async def cmd_cloud_genshin_alias(self, event: AstrMessageEvent):
        logger.info("🎊 手动触发 /cloudys")
        group = self._get_default_group()
        quote = self._get_random_quote_from_group(group)
        yield event.plain_result(quote)

    # ==================== 管理命令 ====================

    @filter.command("云原神管理")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_admin(self, event: AstrMessageEvent):
        """
        云原神管理命令 v4.3
        组管理：
          /云原神管理 group list/add/remove/rename
          /云原神管理 group <组名> add/remove/first_reply/delay/quote/media/mode
        快捷命令（操作第一个组）：
          add/remove/list/first_reply/quote/media/mode/blacklist/status
        """
        text = (event.message_str or "").strip()
        parts = text.split(maxsplit=2)

        if len(parts) < 2:
            yield event.plain_result(
                "📋 好想玩云原神🎊 v4.3 管理命令：\n"
                "  组管理：\n"
                "  /云原神管理 group list/add/remove/rename\n"
                "  /云原神管理 group <组名> add/remove/first_reply/delay\n"
                "  /云原神管理 group <组名> quote list/add/remove/set\n"
                "  /云原神管理 group <组名> media list/add/remove/info\n"
                "  /云原神管理 group <组名> mode <模式>\n"
                "  快捷操作（操作第一组）：\n"
                "  /云原神管理 add/remove/list/first_reply/quote\n"
                "  /云原神管理 media list/add/remove\n"
                "  /云原神管理 mode <模式>\n"
                "  /云原神管理 blacklist add/remove/list\n"
                "  /云原神管理 status\n"
                "  /云原神管理 configsync — 同步面板配置到默认组"
            )
            return

        subcmd = parts[1]

        # ── 组管理 ──
        if subcmd == "group":
            await self._handle_group_admin(event, parts)
            return

        # ── 快捷命令（操作第一个组） ──
        if subcmd in ("add", "remove", "list"):
            await self._handle_keyword_admin(event, subcmd, parts)
            return
        if subcmd == "first_reply":
            await self._handle_first_reply_admin(event, parts)
            return
        if subcmd == "quote":
            await self._handle_quote_admin(event, parts)
            return
        if subcmd == "media":
            await self._handle_media_admin_quick(event, parts)
            return
        if subcmd == "mode":
            await self._handle_mode_admin_quick(event, parts)
            return
        if subcmd == "blacklist":
            await self._handle_blacklist_admin(event, parts)
            return
        if subcmd == "status":
            await self._handle_status(event)
            return
        if subcmd == "configsync":
            self._sync_config_to_data()
            yield event.plain_result("✅ 面板配置已同步到默认组！")
            return

        yield event.plain_result(
            f"❌ 未知子命令: {subcmd}，可用: group / add / remove / list / first_reply / quote / media / mode / blacklist / status / configsync"
        )

    # ==================== 匹配组管理（核心） ====================

    async def _handle_group_admin(self, event: AstrMessageEvent, parts: list):
        """处理完整的 match_group 管理"""
        groups = self.data.get("match_groups", [])
        if not isinstance(groups, list):
            groups = []
            self.data["match_groups"] = groups

        if len(parts) < 3 or not parts[2].strip():
            await self._list_groups(event, groups)
            return

        rest = parts[2].strip()
        rest_parts = rest.split(maxsplit=2)
        op = rest_parts[0]
        arg1 = rest_parts[1] if len(rest_parts) > 1 else ""
        arg2 = rest_parts[2] if len(rest_parts) > 2 else ""

        # ── 全局组操作 ──
        if op == "list":
            await self._list_groups(event, groups)
            return

        if op == "add":
            if not arg1:
                await event.send(event.plain_result("❌ 用法：/云原神管理 group add <组名>"))
                return
            name = arg1.strip()
            if self._find_group(name) != -1:
                await event.send(event.plain_result(f"⚠️ 组「{name}」已存在"))
                return
            default_grp = _make_default_group(self.config)
            new_group = {
                "name": name,
                "keywords": [],
                "first_reply": str(default_grp["first_reply"]),
                "quote_pool": list(default_grp["quote_pool"]),
                "reply_delay_ms": default_grp["reply_delay_ms"],
                "media_pool": [],
                "reply_mode": "mixed"
            }
            groups.append(new_group)
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 已创建匹配组「{name}」\n"
                f"当前共 {len(groups)} 个组"
            ))
            return

        if op == "remove":
            if not arg1:
                await event.send(event.plain_result("❌ 用法：/云原神管理 group remove <组名>"))
                return
            name = arg1.strip()
            idx = self._find_group(name)
            if idx == -1:
                await event.send(event.plain_result(f"❌ 未找到组「{name}」"))
                return
            if len(groups) <= 1:
                await event.send(event.plain_result("❌ 不能删除最后一个组"))
                return
            removed = groups.pop(idx)
            self._save_data()
            await event.send(event.plain_result(f"✅ 已删除组「{removed['name']}」，剩余 {len(groups)} 个组"))
            return

        if op == "rename":
            if not arg1 or not arg2:
                await event.send(event.plain_result("❌ 用法：/云原神管理 group rename <旧名> <新名>"))
                return
            old_name = arg1.strip()
            new_name = arg2.strip()
            if not new_name:
                await event.send(event.plain_result("❌ 新组名不能为空"))
                return
            idx = self._find_group(old_name)
            if idx == -1:
                await event.send(event.plain_result(f"❌ 未找到组「{old_name}」"))
                return
            if self._find_group(new_name) != -1 and new_name != old_name:
                await event.send(event.plain_result(f"⚠️ 组名「{new_name}」已存在"))
                return
            groups[idx]["name"] = new_name
            self._save_data()
            await event.send(event.plain_result(f"✅ 组已重命名：{old_name} → {new_name}"))
            return

        # ── 组内操作（op 为组名） ──
        group_name = op
        idx = self._find_group(group_name)
        if idx == -1:
            await event.send(event.plain_result(f"❌ 未找到组「{group_name}」"))
            return

        if not arg1:
            # 查看组详情
            await self._show_group_detail(event, groups[idx])
            return

        # 组内子命令：arg1 可能是 add/remove/first_reply/delay/quote/media/mode
        sub_op = arg1
        sub_arg = arg2  # 剩余参数

        if sub_op == "add":
            if not sub_arg:
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} add <关键词>"))
                return
            kw = sub_arg.strip()
            if kw in groups[idx].get("keywords", []):
                await event.send(event.plain_result(f"⚠️ 组「{group_name}」中已有关键词「{kw}」"))
                return
            groups[idx].setdefault("keywords", []).append(kw)
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」已添加关键词「{kw}」\n"
                f"该组当前共 {len(groups[idx]['keywords'])} 个关键词"
            ))
            return

        if sub_op == "remove":
            if not sub_arg:
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} remove <关键词>"))
                return
            kw = sub_arg.strip()
            kws = groups[idx].get("keywords", [])
            if kw not in kws:
                await event.send(event.plain_result(f"❌ 组「{group_name}」中未找到关键词「{kw}」"))
                return
            kws.remove(kw)
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」已删除关键词「{kw}」\n"
                f"该组剩余 {len(kws)} 个关键词"
            ))
            return

        if sub_op == "first_reply":
            if not sub_arg:
                current = groups[idx].get("first_reply", "欸，云朵")
                await event.send(event.plain_result(
                    f"📋 组「{group_name}」当前首次回复词：\n「{current}」\n\n"
                    f"💡 设置：/云原神管理 group {group_name} first_reply <新文本>"
                ))
                return
            new_text = sub_arg.strip()
            if not new_text:
                await event.send(event.plain_result("❌ 首次回复词不能为空"))
                return
            groups[idx]["first_reply"] = new_text
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」首次回复词已设为：\n「{new_text}」"
            ))
            return

        if sub_op == "delay":
            if not sub_arg:
                current = groups[idx].get("reply_delay_ms", 800)
                await event.send(event.plain_result(
                    f"📋 组「{group_name}」当前回复延迟：{current}ms\n"
                    f"💡 设置：/云原神管理 group {group_name} delay <毫秒数>"
                ))
                return
            try:
                ms = int(sub_arg.strip())
                if ms < 0:
                    raise ValueError
            except ValueError:
                await event.send(event.plain_result("❌ 延迟必须为非负整数（毫秒）"))
                return
            groups[idx]["reply_delay_ms"] = ms
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」回复延迟已设为 {ms}ms"
            ))
            return

        if sub_op == "quote":
            await self._handle_quote_admin_in_group(event, groups[idx], group_name, groups, sub_arg)
            return

        if sub_op == "media":
            await self._handle_media_admin(event, groups[idx], group_name, groups, sub_arg)
            return

        if sub_op == "mode":
            await self._handle_mode_admin(event, groups[idx], group_name, groups, sub_arg)
            return

        await event.send(event.plain_result(f"❌ 未知组操作: {sub_op}，可用: add / remove / first_reply / delay / quote / media / mode"))

    # ==================== 组内细节展示 ====================

    async def _show_group_detail(self, event: AstrMessageEvent, group: dict):
        """展示单个组的完整详情"""
        kw_list = group.get("keywords", [])
        qp = group.get("quote_pool", [])
        mp = group.get("media_pool", [])
        fr = group.get("first_reply", "")
        dl = group.get("reply_delay_ms", 800)
        mode = group.get("reply_mode", "mixed")

        img_count = sum(1 for m in mp if m.get("type") == "image")
        rec_count = sum(1 for m in mp if m.get("type") == "record")
        vid_count = sum(1 for m in mp if m.get("type") == "video")

        lines = [f"📋 匹配组「{group['name']}」详情：\n━━━━━━━━━━━━━━━━"]
        lines.append(f"🔑 关键词 ({len(kw_list)} 个)：")
        if kw_list:
            lines.extend(f"  {i+1}. {kw}" for i, kw in enumerate(kw_list))
        else:
            lines.append("  （空）")
        lines.append(f"💬 首次回复词：「{fr}」")
        lines.append(f"🎭 梗段词库: {len(qp)} 段")
        lines.append(f"🖼️ 媒体池: {len(mp)} 个 (图片{img_count} 语音{rec_count} 视频{vid_count})")
        lines.append(f"📋 回复模式: {mode} — {MODE_HELP.get(mode, '')}")
        lines.append(f"⏱️ 回复延迟: {dl}ms")
        lines.append("━━━━━━━━━━━━━━━━\n"
                     f"💡 管理: group {group['name']} add/remove/first_reply/delay/quote/media/mode")
        await event.send(event.plain_result("\n".join(lines)))

    async def _list_groups(self, event: AstrMessageEvent, groups: list):
        """列出所有匹配组"""
        if not groups:
            await event.send(event.plain_result("📋 暂无匹配组"))
            return

        lines = [f"📋 好想玩云原神🎊 v4.3 匹配组（共 {len(groups)} 个）：\n"]
        for i, g in enumerate(groups, 1):
            kw = g.get("keywords", [])
            qp = g.get("quote_pool", [])
            mp = g.get("media_pool", [])
            fr = g.get("first_reply", "")
            dl = g.get("reply_delay_ms", 800)
            mode = g.get("reply_mode", "mixed")
            lines.append(f"  {i}. 「{g.get('name', '?')}」")
            lines.append(f"     🔑 {len(kw)}词 · 🎭 {len(qp)}段 · 🖼️ {len(mp)}媒体 · ⏱️ {dl}ms · {mode}模式")
            lines.append(f"     💬 「{fr}」")
        lines.append("\n💡 可用 group <组名> 查看详情，group add/remove/rename 管理组")
        await event.send(event.plain_result("\n".join(lines)))

    # ==================== 组内 Quote 管理（从 v3 搬过来的内联逻辑） ====================

    async def _handle_quote_admin_in_group(self, event: AstrMessageEvent, group: dict, group_name: str, groups: list, sub_arg: str):
        """处理组内梗段词库增删改查"""
        quotes = group.get("quote_pool", [])
        if not isinstance(quotes, list):
            quotes = []
            group["quote_pool"] = quotes

        if not sub_arg:
            await event.send(event.plain_result(
                f"📋 组「{group_name}」梗段管理：\n"
                f"  group {group_name} quote list              — 列出梗段\n"
                f"  group {group_name} quote add <梗段>        — 添加梗段\n"
                f"  group {group_name} quote remove <编号>     — 删除梗段\n"
                f"  group {group_name} quote set <编号> <内容>  — 修改梗段\n\n"
                f"当前共 {len(quotes)} 段梗"
            ))
            return

        q_parts = sub_arg.split(maxsplit=1)
        q_action = q_parts[0]
        q_arg = q_parts[1] if len(q_parts) > 1 else ""

        if q_action == "list":
            lines = [f"🗂️ 组「{group_name}」梗段词库（共 {len(quotes)} 段）：\n"]
            if quotes:
                for i, q in enumerate(quotes, 1):
                    d = q[:40] + "…" if len(q) > 40 else q
                    lines.append(f"  {i}. {d}")
            else:
                lines.append("  （暂无梗段）")
            await event.send(event.plain_result("\n".join(lines)))

        elif q_action == "add":
            if not q_arg:
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} quote add <梗段>"))
                return
            content = q_arg.strip()
            group.setdefault("quote_pool", []).append(content)
            self._save_data()
            d = content[:30] + "…" if len(content) > 30 else content
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」已添加梗段：\n「{d}」\n"
                f"当前共 {len(group['quote_pool'])} 段"
            ))

        elif q_action == "remove":
            if not q_arg:
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} quote remove <编号>"))
                return
            try:
                q_idx = int(q_arg.strip())
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return
            if q_idx < 1 or q_idx > len(quotes):
                await event.send(event.plain_result(f"❌ 编号 {q_idx} 超出范围（1~{len(quotes)}）"))
                return
            removed = quotes.pop(q_idx - 1)
            self._save_data()
            d = removed[:30] + "…" if len(removed) > 30 else removed
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」已删除梗段 #{q_idx}：\n「{d}」\n剩余 {len(quotes)} 段"
            ))

        elif q_action == "set":
            set_parts = q_arg.split(maxsplit=1)
            if len(set_parts) < 2:
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} quote set <编号> <新内容>"))
                return
            try:
                q_idx = int(set_parts[0])
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return
            new_content = set_parts[1].strip()
            if not new_content:
                await event.send(event.plain_result("❌ 梗段内容不能为空"))
                return
            if q_idx < 1 or q_idx > len(quotes):
                await event.send(event.plain_result(f"❌ 编号 {q_idx} 超出范围（1~{len(quotes)}）"))
                return
            old = quotes[q_idx - 1]
            quotes[q_idx - 1] = new_content
            self._save_data()
            od = old[:20] + "…" if len(old) > 20 else old
            nd = new_content[:20] + "…" if len(new_content) > 20 else new_content
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」已修改梗段 #{q_idx}：\n"
                f"  旧: 「{od}」\n  新: 「{nd}」"
            ))
        else:
            await event.send(event.plain_result(f"❌ 未知操作: {q_action}，可用: list / add / remove / set"))

    # ==================== 组内 Media 管理（v4.3 新增） ====================

    async def _handle_media_admin(self, event: AstrMessageEvent, group: dict, group_name: str, groups: list, sub_arg: str):
        """处理组内媒体池增删查"""
        mp = group.get("media_pool", [])
        if not isinstance(mp, list):
            mp = []
            group["media_pool"] = mp

        if not sub_arg:
            img_c = sum(1 for m in mp if m.get("type") == "image")
            rec_c = sum(1 for m in mp if m.get("type") == "record")
            vid_c = sum(1 for m in mp if m.get("type") == "video")
            await event.send(event.plain_result(
                f"📋 组「{group_name}」媒体管理：\n"
                f"  group {group_name} media list                     — 列出所有媒体\n"
                f"  group {group_name} media add <type> <src> [source]  — 添加媒体\n"
                f"  group {group_name} media remove <编号>             — 删除媒体\n"
                f"  group {group_name} media info <编号>               — 查看媒体详情\n"
                f"  type: image/record/video, source: url(默认)/local\n\n"
                f"当前共 {len(mp)} 个媒体 (图片{img_c} 语音{rec_c} 视频{vid_c})"
            ))
            return

        q_parts = sub_arg.split(maxsplit=1)
        q_action = q_parts[0]
        q_arg = q_parts[1] if len(q_parts) > 1 else ""

        if q_action == "list":
            lines = [f"🗂️ 组「{group_name}」媒体池（共 {len(mp)} 个）：\n"]
            if mp:
                for i, m in enumerate(mp, 1):
                    mtype = m.get("type", "?")
                    src = m.get("src", "")
                    source = m.get("source", "url")
                    d = src[:40] + "…" if len(src) > 40 else src
                    icon = {"image": "🖼️", "record": "🎵", "video": "🎬"}.get(mtype, "📁")
                    lines.append(f"  {i}. {icon} [{mtype}] ({source}) {d}")
            else:
                lines.append("  （暂无媒体）")
            await event.send(event.plain_result("\n".join(lines)))

        elif q_action == "add":
            # 格式: add <type> <src> [source]
            # q_arg = "image https://..." 或 "image /path/file.jpg local"
            add_parts = q_arg.split(maxsplit=2)
            if len(add_parts) < 2:
                await event.send(event.plain_result(
                    f"❌ 用法：/云原神管理 group {group_name} media add <type> <src> [source]\n"
                    f"  type: image/record/video, source: url(默认)/local"
                ))
                return
            mtype = add_parts[0].strip().lower()
            src = add_parts[1].strip()
            source = add_parts[2].strip().lower() if len(add_parts) > 2 else "url"

            if mtype not in MEDIA_TYPES:
                await event.send(event.plain_result(f"❌ 类型必须为: {'/'.join(MEDIA_TYPES)}"))
                return
            if source not in SOURCE_TYPES:
                await event.send(event.plain_result(f"❌ 来源必须为: {'/'.join(SOURCE_TYPES)}"))
                return
            if not src:
                await event.send(event.plain_result("❌ 媒体地址不能为空"))
                return

            mp.append({"type": mtype, "src": src, "source": source})
            group["media_pool"] = mp
            self._save_data()
            icon = {"image": "🖼️", "record": "🎵", "video": "🎬"}.get(mtype, "📁")
            d = src[:40] + "…" if len(src) > 40 else src
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」已添加媒体 #{len(mp)}：\n"
                f"  {icon} [{mtype}] ({source}) {d}"
            ))

        elif q_action == "remove":
            if not q_arg:
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} media remove <编号>"))
                return
            try:
                m_idx = int(q_arg.strip())
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return
            if m_idx < 1 or m_idx > len(mp):
                await event.send(event.plain_result(f"❌ 编号 {m_idx} 超出范围（1~{len(mp)}）"))
                return
            removed = mp.pop(m_idx - 1)
            group["media_pool"] = mp
            self._save_data()
            mtype = removed.get("type", "?")
            src = removed.get("src", "")
            d = src[:30] + "…" if len(src) > 30 else src
            await event.send(event.plain_result(
                f"✅ 组「{group_name}」已删除媒体 #{m_idx}：[{mtype}] {d}\n"
                f"剩余 {len(mp)} 个媒体"
            ))

        elif q_action == "info":
            if not q_arg:
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} media info <编号>"))
                return
            try:
                m_idx = int(q_arg.strip())
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return
            if m_idx < 1 or m_idx > len(mp):
                await event.send(event.plain_result(f"❌ 编号 {m_idx} 超出范围（1~{len(mp)}）"))
                return
            m = mp[m_idx - 1]
            mtype = m.get("type", "?")
            src = m.get("src", "")
            source = m.get("source", "url")
            icon = {"image": "🖼️", "record": "🎵", "video": "🎬"}.get(mtype, "📁")
            await event.send(event.plain_result(
                f"📋 媒体 #{m_idx} 详情：\n"
                f"  {icon} 类型: {mtype}\n"
                f"  来源: {source}\n"
                f"  地址: {src}"
            ))
        else:
            await event.send(event.plain_result(f"❌ 未知操作: {q_action}，可用: list / add / remove / info"))

    # ==================== 组内 Mode 管理（v4.3 新增） ====================

    async def _handle_mode_admin(self, event: AstrMessageEvent, group: dict, group_name: str, groups: list, sub_arg: str):
        """处理组内回复模式设置"""
        if not sub_arg:
            current = group.get("reply_mode", "mixed")
            lines = [f"📋 组「{group_name}」当前回复模式：{current}\n"]
            lines.append("可用模式：")
            for m in REPLY_MODES:
                marker = " 👈 当前" if m == current else ""
                lines.append(f"  {m} — {MODE_HELP.get(m, '')}{marker}")
            lines.append(f"\n💡 设置：/云原神管理 group {group_name} mode <模式名>")
            await event.send(event.plain_result("\n".join(lines)))
            return

        new_mode = sub_arg.strip().lower()
        if new_mode not in REPLY_MODES:
            await event.send(event.plain_result(
                f"❌ 无效模式: {new_mode}，可用: {'/'.join(REPLY_MODES)}\n"
                f"  text=纯文本, media=纯媒体, text_media=文本+媒体, media_text=媒体+文本, mixed=随机混合"
            ))
            return

        group["reply_mode"] = new_mode
        self._save_data()
        await event.send(event.plain_result(
            f"✅ 组「{group_name}」回复模式已设为: {new_mode}\n"
            f"  {MODE_HELP.get(new_mode, '')}"
        ))

    # ==================== 快捷命令（操作第一个组） ====================

    async def _handle_keyword_admin(self, event: AstrMessageEvent, subcmd: str, parts: list):
        """快捷关键词管理：操作第一个组"""
        group = self._get_default_group()
        keywords = group.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
            group["keywords"] = keywords

        if subcmd == "add":
            if len(parts) < 3 or not parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 add <关键词>"))
                return
            kw = parts[2].strip()
            if kw in keywords:
                await event.send(event.plain_result(f"⚠️ 关键词「{kw}」已在默认组中"))
                return
            keywords.append(kw)
            self._save_data()
            await event.send(event.plain_result(f"✅ 默认组已添加关键词「{kw}」，当前共 {len(keywords)} 个"))

        elif subcmd == "remove":
            if len(parts) < 3 or not parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 remove <关键词>"))
                return
            kw = parts[2].strip()
            if kw not in keywords:
                await event.send(event.plain_result(f"❌ 默认组中未找到关键词「{kw}」"))
                return
            keywords.remove(kw)
            self._save_data()
            await event.send(event.plain_result(f"✅ 默认组已删除关键词「{kw}」，剩余 {len(keywords)} 个"))

        elif subcmd == "list":
            lines = [f"📋 默认组关键词列表（共 {len(keywords)} 个）：\n"]
            if keywords:
                for i, kw in enumerate(keywords, 1):
                    lines.append(f"  {i}. {kw}")
            else:
                lines.append("  （暂无）")
            lines.append("\n💡 使用 group <组名> 管理其他组")
            await event.send(event.plain_result("\n".join(lines)))

    async def _handle_first_reply_admin(self, event: AstrMessageEvent, parts: list):
        """快捷首次回复词管理：操作第一个组"""
        group = self._get_default_group()
        if len(parts) < 3:
            current = group.get("first_reply", "欸，云朵")
            await event.send(event.plain_result(
                f"📋 默认组当前首次回复词：\n「{current}」\n\n"
                "💡 设置：/云原神管理 first_reply <新文本>\n"
                "💡 其他组用：group <组名> first_reply <文本>"
            ))
            return
        new_text = parts[2].strip()
        if not new_text:
            await event.send(event.plain_result("❌ 首次回复词不能为空"))
            return
        group["first_reply"] = new_text
        self._save_data()
        await event.send(event.plain_result(f"✅ 默认组首次回复词已设为：\n「{new_text}」"))

    async def _handle_quote_admin(self, event: AstrMessageEvent, parts: list):
        """快捷梗段管理：操作第一个组"""
        group = self._get_default_group()
        quotes = group.get("quote_pool", [])
        if not isinstance(quotes, list):
            quotes = []
            group["quote_pool"] = quotes

        if len(parts) < 3 or not parts[2].strip():
            await event.send(event.plain_result(
                "📋 默认组梗段管理：\n"
                "  /云原神管理 quote list              — 列出梗段\n"
                "  /云原神管理 quote add <梗段>        — 添加梗段\n"
                "  /云原神管理 quote remove <编号>     — 删除梗段\n"
                "  /云原神管理 quote set <编号> <内容>  — 修改梗段\n\n"
                "💡 其他组用：group <组名> quote ...\n"
                f"当前共 {len(quotes)} 段梗"
            ))
            return

        sub2 = parts[2].strip()
        sub2_parts = sub2.split(maxsplit=1)
        action = sub2_parts[0]
        arg = sub2_parts[1].strip() if len(sub2_parts) > 1 else ""

        if action == "list":
            lines = [f"🗂️ 默认组梗段词库（共 {len(quotes)} 段）：\n"]
            if quotes:
                for i, q in enumerate(quotes, 1):
                    d = q[:40] + "…" if len(q) > 40 else q
                    lines.append(f"  {i}. {d}")
            else:
                lines.append("  （暂无）")
            await event.send(event.plain_result("\n".join(lines)))

        elif action == "add":
            if not arg:
                await event.send(event.plain_result("❌ 用法：/云原神管理 quote add <梗段>"))
                return
            quotes.append(arg.strip())
            self._save_data()
            d = arg[:30] + "…" if len(arg) > 30 else arg
            await event.send(event.plain_result(f"✅ 默认组已添加梗段 #{len(quotes)}：\n「{d}」"))

        elif action == "remove":
            if not arg:
                await event.send(event.plain_result("❌ 用法：/云原神管理 quote remove <编号>"))
                return
            try:
                q_idx = int(arg)
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return
            if q_idx < 1 or q_idx > len(quotes):
                await event.send(event.plain_result(f"❌ 编号 {q_idx} 超出范围（1~{len(quotes)}）"))
                return
            removed = quotes.pop(q_idx - 1)
            self._save_data()
            d = removed[:30] + "…" if len(removed) > 30 else removed
            await event.send(event.plain_result(f"✅ 默认组已删除梗段 #{q_idx}：\n「{d}」"))

        elif action == "set":
            set_parts = arg.split(maxsplit=1)
            if len(set_parts) < 2:
                await event.send(event.plain_result("❌ 用法：/云原神管理 quote set <编号> <新内容>"))
                return
            try:
                q_idx = int(set_parts[0])
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return
            new_content = set_parts[1].strip()
            if not new_content:
                await event.send(event.plain_result("❌ 梗段内容不能为空"))
                return
            if q_idx < 1 or q_idx > len(quotes):
                await event.send(event.plain_result(f"❌ 编号 {q_idx} 超出范围（1~{len(quotes)}）"))
                return
            old = quotes[q_idx - 1]
            quotes[q_idx - 1] = new_content
            self._save_data()
            od = old[:20] + "…" if len(old) > 20 else old
            nd = new_content[:20] + "…" if len(new_content) > 20 else new_content
            await event.send(event.plain_result(f"✅ 默认组已修改梗段 #{q_idx}：\n  旧: 「{od}」\n  新: 「{nd}」"))
        else:
            await event.send(event.plain_result(f"❌ 未知操作: {action}，可用: list / add / remove / set"))

    # ==================== 快捷 Media 管理（v4.3 新增） ====================

    async def _handle_media_admin_quick(self, event: AstrMessageEvent, parts: list):
        """快捷媒体管理：操作第一个组"""
        group = self._get_default_group()
        group_name = group.get("name", "默认组")
        groups = self.data.get("match_groups", [])

        if len(parts) < 3 or not parts[2].strip():
            mp = group.get("media_pool", [])
            img_c = sum(1 for m in mp if m.get("type") == "image")
            rec_c = sum(1 for m in mp if m.get("type") == "record")
            vid_c = sum(1 for m in mp if m.get("type") == "video")
            await event.send(event.plain_result(
                "📋 默认组媒体管理：\n"
                "  /云原神管理 media list                    — 列出媒体\n"
                "  /云原神管理 media add <type> <src> [source] — 添加媒体\n"
                "  /云原神管理 media remove <编号>            — 删除媒体\n"
                "  type: image/record/video, source: url(默认)/local\n\n"
                f"当前共 {len(mp)} 个媒体 (图片{img_c} 语音{rec_c} 视频{vid_c})\n"
                "💡 其他组用：group <组名> media ..."
            ))
            return

        sub2 = parts[2].strip()
        sub2_parts = sub2.split(maxsplit=1)
        action = sub2_parts[0]
        arg = sub2_parts[1].strip() if len(sub2_parts) > 1 else ""

        if action == "list":
            mp = group.get("media_pool", [])
            lines = [f"🗂️ 默认组媒体池（共 {len(mp)} 个）：\n"]
            if mp:
                for i, m in enumerate(mp, 1):
                    mtype = m.get("type", "?")
                    src = m.get("src", "")
                    source = m.get("source", "url")
                    d = src[:40] + "…" if len(src) > 40 else src
                    icon = {"image": "🖼️", "record": "🎵", "video": "🎬"}.get(mtype, "📁")
                    lines.append(f"  {i}. {icon} [{mtype}] ({source}) {d}")
            else:
                lines.append("  （暂无媒体）")
            await event.send(event.plain_result("\n".join(lines)))

        elif action == "add":
            # add <type> <src> [source]
            add_parts = arg.split(maxsplit=2)
            if len(add_parts) < 2:
                await event.send(event.plain_result("❌ 用法：/云原神管理 media add <type> <src> [source]"))
                return
            mtype = add_parts[0].strip().lower()
            src = add_parts[1].strip()
            source = add_parts[2].strip().lower() if len(add_parts) > 2 else "url"

            if mtype not in MEDIA_TYPES:
                await event.send(event.plain_result(f"❌ 类型必须为: {'/'.join(MEDIA_TYPES)}"))
                return
            if source not in SOURCE_TYPES:
                await event.send(event.plain_result(f"❌ 来源必须为: {'/'.join(SOURCE_TYPES)}"))
                return
            if not src:
                await event.send(event.plain_result("❌ 媒体地址不能为空"))
                return

            group.setdefault("media_pool", []).append({"type": mtype, "src": src, "source": source})
            self._save_data()
            icon = {"image": "🖼️", "record": "🎵", "video": "🎬"}.get(mtype, "📁")
            d = src[:40] + "…" if len(src) > 40 else src
            await event.send(event.plain_result(
                f"✅ 默认组已添加媒体 #{len(group['media_pool'])}：\n"
                f"  {icon} [{mtype}] ({source}) {d}"
            ))

        elif action == "remove":
            if not arg:
                await event.send(event.plain_result("❌ 用法：/云原神管理 media remove <编号>"))
                return
            try:
                m_idx = int(arg)
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return
            mp = group.get("media_pool", [])
            if m_idx < 1 or m_idx > len(mp):
                await event.send(event.plain_result(f"❌ 编号 {m_idx} 超出范围（1~{len(mp)}）"))
                return
            removed = mp.pop(m_idx - 1)
            self._save_data()
            mtype = removed.get("type", "?")
            src = removed.get("src", "")
            d = src[:30] + "…" if len(src) > 30 else src
            await event.send(event.plain_result(
                f"✅ 默认组已删除媒体 #{m_idx}：[{mtype}] {d}\n剩余 {len(mp)} 个媒体"
            ))
        else:
            await event.send(event.plain_result(f"❌ 未知操作: {action}，可用: list / add / remove"))

    async def _handle_mode_admin_quick(self, event: AstrMessageEvent, parts: list):
        """快捷模式管理：操作第一个组"""
        group = self._get_default_group()
        group_name = group.get("name", "默认组")

        if len(parts) < 3 or not parts[2].strip():
            current = group.get("reply_mode", "mixed")
            lines = [f"📋 默认组当前回复模式：{current}\n"]
            lines.append("可用模式：")
            for m in REPLY_MODES:
                marker = " 👈 当前" if m == current else ""
                lines.append(f"  {m} — {MODE_HELP.get(m, '')}{marker}")
            lines.append(f"\n💡 设置：/云原神管理 mode <模式名>\n💡 其他组用：group <组名> mode <模式名>")
            await event.send(event.plain_result("\n".join(lines)))
            return

        new_mode = parts[2].strip().lower()
        if new_mode not in REPLY_MODES:
            await event.send(event.plain_result(f"❌ 无效模式: {new_mode}，可用: {'/'.join(REPLY_MODES)}"))
            return

        group["reply_mode"] = new_mode
        self._save_data()
        await event.send(event.plain_result(
            f"✅ 默认组回复模式已设为: {new_mode}\n{MODE_HELP.get(new_mode, '')}"
        ))

    # ==================== 黑名单管理 ====================

    async def _handle_blacklist_admin(self, event: AstrMessageEvent, parts: list):
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
            gid = str(arg).strip()
            if gid in groups:
                await event.send(event.plain_result(f"⚠️ 群 {gid} 已在名单中"))
                return
            groups.append(gid)
            self._save_data()
            mode = self.config.get("blacklist_mode", "blacklist")
            await event.send(event.plain_result(
                f"✅ 已将群 {gid} 添加到{'黑' if mode == 'blacklist' else '白'}名单\n"
                f"当前共 {len(groups)} 个群"
            ))

        elif action == "remove":
            if not arg:
                await event.send(event.plain_result("❌ 用法：/云原神管理 blacklist remove <群号>"))
                return
            gid = str(arg).strip()
            if gid not in groups:
                await event.send(event.plain_result(f"❌ 名单中未找到群 {gid}"))
                return
            groups.remove(gid)
            self._save_data()
            mode = self.config.get("blacklist_mode", "blacklist")
            await event.send(event.plain_result(
                f"✅ 已将群 {gid} 从{'黑' if mode == 'blacklist' else '白'}名单移除\n"
                f"剩余 {len(groups)} 个群"
            ))

        elif action == "list":
            mode = self.config.get("blacklist_mode", "blacklist")
            lines = [f"📋 群组{'黑' if mode == 'blacklist' else '白'}名单（共 {len(groups)} 个）：\n"]
            if groups:
                for i, g in enumerate(groups, 1):
                    lines.append(f"  {i}. {g}")
            else:
                lines.append("  （暂无）")
            lines.append(f"\n📌 模式: {mode} | blacklist=黑名单 whitelist=白名单")
            await event.send(event.plain_result("\n".join(lines)))
        else:
            await event.send(event.plain_result(f"❌ 未知操作: {action}，可用: add / remove / list"))

    # ==================== 状态查看 ====================

    async def _handle_status(self, event: AstrMessageEvent):
        groups = self.data.get("match_groups", [])
        if not isinstance(groups, list): groups = []
        bl = self.data.get("blacklist_groups", [])
        if not isinstance(bl, list): bl = []
        trigger_enabled = self.config.get("enable_keyword_trigger", True)
        mode = self.config.get("blacklist_mode", "blacklist")

        lines = ["📊 好想玩云原神🎊 v4.3 状态\n━━━━━━━━━━━━━━━━━━"]
        lines.append(f"🔘 关键词触发: {'✅ 开启' if trigger_enabled else '❌ 关闭'}")
        lines.append(f"📦 匹配组: {len(groups)} 个\n")

        for i, g in enumerate(groups, 1):
            kw = g.get("keywords", [])
            qp = g.get("quote_pool", [])
            mp = g.get("media_pool", [])
            fr = g.get("first_reply", "")
            dl = g.get("reply_delay_ms", 800)
            rmode = g.get("reply_mode", "mixed")
            lines.append(f"  {i}. 「{g.get('name', '?')}」")
            lines.append(f"     🔑 {len(kw)}词 · 🎭 {len(qp)}段 · 🖼️ {len(mp)}媒体 · ⏱️ {dl}ms · {rmode}模式")
            lines.append(f"     💬 「{fr}」")

        lines.append(f"\n🚫 群名单模式: {mode}（{len(bl)} 个群）")
        lines.append("━━━━━━━━━━━━━━━━━━")
        lines.append("💡 使用 /云原神管理 group 管理多组")
        lines.append("📋 新模式: text/media/text_media/media_text/mixed")
        await event.send(event.plain_result("\n".join(lines)))

    # ==================== 生命周期 ====================

    async def terminate(self):
        self._save_data()
        logger.info("🎊 好想玩云原神🎊 v4.3 已卸载，数据已保存")
