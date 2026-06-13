import os
import json
import random
import asyncio
import copy

from astrbot.api import logger, AstrBotConfig
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api.message_components import Plain


class Main(Star):
    """🎊 好想玩云原神🎊 v3.0 — 多匹配组 · 各配各的词库"""

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
        group_count = len(self.data.get("match_groups", []))
        total_kw = sum(len(g.get("keywords", [])) for g in self.data.get("match_groups", []))
        total_q = sum(len(g.get("quote_pool", [])) for g in self.data.get("match_groups", []))
        bl_count = len(self.data.get("blacklist_groups", []))
        mode = self.config.get("blacklist_mode", "blacklist")
        logger.info(
            f"🎊 好想玩云原神🎊 v3.0 已加载 | "
            f"{group_count}个匹配组 | "
            f"共{total_kw}个关键词 | "
            f"共{total_q}段梗 | "
            f"关键词触发: {'开' if self.config.get('enable_keyword_trigger', True) else '关'} | "
            f"黑名单模式: {mode} (共{bl_count}个群)"
        )

    # ==================== 持久化方法 ====================

    def _load_data(self) -> dict:
        """
        加载持久化数据 data.json。
        如果文件存在则读取，否则从配置（_conf_schema.json）获取默认值并保存。
        v3.0：检测旧版格式（包含 trigger_keywords 键）并自动迁移到 match_groups。
        """
        # 默认值模板（从配置获取）
        default_data = {
            "match_groups": [],
            "blacklist_groups": self.config.get("blacklist_groups", [])
        }

        # 确保类型
        if not isinstance(default_data["blacklist_groups"], list):
            default_data["blacklist_groups"] = []

        # 尝试从持久化文件加载
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            if os.path.exists(self.data_file):
                with open(self.data_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        # === v2.x → v3.0 自动迁移：检测旧格式（有 trigger_keywords 键） ===
                        if "trigger_keywords" in saved:
                            logger.info("🎊 检测到 v2.x 格式 data.json，自动迁移到 v3.0 match_groups...")
                            first_reply = str(saved.get("first_reply", "欸，云朵") or "欸，云朵")
                            # 迁移：将旧数据转为 match_groups 的第一组
                            new_groups = []
                            default_group = {
                                "name": "默认组",
                                "keywords": saved.get("trigger_keywords", self.config.get("trigger_keywords", ["云朵", "云原神"])),
                                "first_reply": first_reply,
                                "quote_pool": saved.get("quote_pool", self.config.get("quote_pool", [])),
                                "reply_delay_ms": saved.get("reply_delay_ms", self.config.get("reply_delay_ms", 800))
                            }
                            # 确保类型正确
                            if not isinstance(default_group["keywords"], list):
                                default_group["keywords"] = ["云朵", "云原神"]
                            if not isinstance(default_group["quote_pool"], list):
                                default_group["quote_pool"] = []
                            if not isinstance(default_group["reply_delay_ms"], (int, float)):
                                default_group["reply_delay_ms"] = 800
                            new_groups.append(default_group)
                            saved["match_groups"] = new_groups
                            # 清理旧字段避免下次再迁移
                            for old_key in ("trigger_keywords", "first_reply", "quote_pool", "reply_delay_ms"):
                                saved.pop(old_key, None)
                            logger.info("🎊 v2.x → v3.0 迁移完成！")
                        # === / 迁移结束 ===

                        # 加载 match_groups
                        if "match_groups" in saved and isinstance(saved["match_groups"], list):
                            default_data["match_groups"] = saved["match_groups"]
                        # 加载 blacklist_groups
                        if "blacklist_groups" in saved and isinstance(saved["blacklist_groups"], list):
                            default_data["blacklist_groups"] = saved["blacklist_groups"]
                        logger.info(f"🎊 从持久化文件加载配置成功")

                        # 如果迁移过，立即保存新格式
                        if "trigger_keywords" not in saved and "match_groups" in saved:
                            # 检查是否需要更新文件（迁移场景）
                            pass
        except Exception as e:
            logger.error(f"🎊 加载持久化文件失败: {e}")

        # 如果 match_groups 为空，从配置初始化第一组
        if not default_data["match_groups"]:
            first_reply = str(self.config.get("first_reply", "欸，云朵") or "欸，云朵")
            keywords = self.config.get("trigger_keywords", ["云朵", "云原神"])
            if not isinstance(keywords, list):
                keywords = ["云朵", "云原神"]
            quote_pool = self.config.get("quote_pool", [])
            if not isinstance(quote_pool, list):
                quote_pool = []
            delay = self.config.get("reply_delay_ms", 800)
            if not isinstance(delay, (int, float)):
                delay = 800
            default_data["match_groups"] = [
                {
                    "name": "默认组",
                    "keywords": keywords,
                    "first_reply": first_reply,
                    "quote_pool": quote_pool,
                    "reply_delay_ms": delay
                }
            ]
            # 立即保存初次初始化
            self._save_data_immediate(default_data)

        # 确保每个组结构完整
        for group in default_data["match_groups"]:
            if not isinstance(group, dict):
                continue
            if "keywords" not in group or not isinstance(group["keywords"], list):
                group["keywords"] = []
            if "first_reply" not in group or not isinstance(group["first_reply"], str):
                group["first_reply"] = "欸，云朵"
            if "quote_pool" not in group or not isinstance(group["quote_pool"], list):
                group["quote_pool"] = []
            if "reply_delay_ms" not in group or not isinstance(group["reply_delay_ms"], (int, float)):
                group["reply_delay_ms"] = 800
            if "name" not in group or not isinstance(group["name"], str):
                group["name"] = "未命名组"

        return default_data

    def _save_data_immediate(self, data: dict):
        """保存 data.json（用于初始化时的立即写入）"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"🎊 初始化保存持久化数据失败: {e}")

    def _save_data(self):
        """将当前数据持久化到 data.json"""
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"🎊 保存持久化数据失败: {e}")

    # ==================== 核心方法 ====================

    def _get_group_by_index(self, index: int) -> dict:
        """
        获取指定索引的匹配组。
        如果索引超限，返回 None。
        """
        groups = self.data.get("match_groups", [])
        if not isinstance(groups, list) or index < 0 or index >= len(groups):
            return None
        return groups[index]

    def _get_group_by_name(self, name: str) -> dict:
        """按组名查找匹配组，返回 (index, group) 或 (None, None)"""
        groups = self.data.get("match_groups", [])
        if not isinstance(groups, list):
            return None, None
        for i, g in enumerate(groups):
            if isinstance(g, dict) and g.get("name") == name:
                return i, g
        return None, None

    def _get_first_group(self) -> dict:
        """获取第一个匹配组"""
        groups = self.data.get("match_groups", [])
        if not isinstance(groups, list) or not groups:
            return None
        return groups[0]

    def _get_random_quote_from_group(self, group: dict) -> str:
        """从指定组的梗段词库中随机取一段"""
        quotes = group.get("quote_pool", [])
        if not isinstance(quotes, list) or not quotes:
            return "啊😲？云朵☁️😄，好想玩原神😨……"
        return random.choice(quotes)

    def _match_message(self, text: str) -> dict:
        """
        遍历 match_groups，按组顺序匹配。
        返回第一个匹配到的组 dict，若都没匹配返回 None。
        """
        groups = self.data.get("match_groups", [])
        if not isinstance(groups, list):
            return None
        for group in groups:
            if not isinstance(group, dict):
                continue
            keywords = group.get("keywords", [])
            if not isinstance(keywords, list):
                continue
            for kw in keywords:
                if isinstance(kw, str) and kw in text:
                    return group
        return None

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
        v3.0：按 match_groups 组顺序匹配，命中哪组的词就用哪组的回复。
        """
        # ① 检查是否启用关键词触发
        if not self.config.get("enable_keyword_trigger", True):
            return

        # ② 获取消息文本
        text = str(event.message_str or "").strip()
        if not text:
            return

        # ③ 过滤命令消息（排除管理命令）
        if text.startswith("云原神管理") or text == "cloudys":
            logger.debug(f"🎊 跳过命令消息: '{text}'")
            return

        # ④ 检查群聊黑/白名单
        if self._is_group_blocked(event):
            logger.debug(f"🎊 群 {event.get_group_id()} 在黑/白名单中，跳过触发")
            return

        # ⑤ 按组匹配关键词
        matched_group = self._match_message(text)
        if not matched_group:
            return

        # === 匹配成功！回复流程 ===
        matched_kw = None
        for kw in matched_group.get("keywords", []):
            if isinstance(kw, str) and kw in text:
                matched_kw = kw
                break

        logger.info(
            f"🎊 关键词触发 | group='{matched_group.get('name', '?')}' | "
            f"keyword='{matched_kw}' | "
            f"msg='{text[:40]}{'…' if len(text) > 40 else ''}'"
        )

        event.stop_event()

        # ⑥ 从匹配组获取配置
        delay_ms = matched_group.get("reply_delay_ms", 800)
        quote = self._get_random_quote_from_group(matched_group)
        asyncio.create_task(self._delayed_send(event, quote, delay_ms))

        # ⑦ 第一条用 yield 发送首次回复词
        first_reply = str(matched_group.get("first_reply", "欸，云朵") or "欸，云朵")
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
        """手动触发：从第一组随机回复一段云原神梗"""
        logger.info("🎊 手动触发 /云原神")
        group = self._get_first_group()
        if not group:
            yield event.plain_result("啊😲？云朵☁️😄，好想玩原神😨……")
            return
        quote = self._get_random_quote_from_group(group)
        yield event.plain_result(quote)

    @filter.command("cloudys")
    async def cmd_cloud_genshin_alias(self, event: AstrMessageEvent):
        """手动触发别名：/cloudys"""
        logger.info("🎊 手动触发 /cloudys")
        group = self._get_first_group()
        if not group:
            yield event.plain_result("啊😲？云朵☁️😄，好想玩原神😨……")
            return
        quote = self._get_random_quote_from_group(group)
        yield event.plain_result(quote)

    # ==================== 管理命令 ====================

    @filter.command("云原神管理")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def cmd_admin(self, event: AstrMessageEvent):
        """
        云原神管理命令 v3.0
        新增 group 管理子命令体系：
          /云原神管理 group list                        — 列出所有匹配组
          /云原神管理 group add <组名>                   — 新建匹配组
          /云原神管理 group remove <组名>                — 删除匹配组
          /云原神管理 group rename <旧名> <新名>          — 重命名组
          /云原神管理 group <组名>                        — 查看组详情
          /云原神管理 group <组名> add <关键词>            — 组内添加关键词
          /云原神管理 group <组名> remove <关键词>         — 组内删除关键词
          /云原神管理 group <组名> first_reply [文本]      — 查看/设首次回复词
          /云原神管理 group <组名> delay <毫秒>            — 设组回复延迟
          /云原神管理 group <组名> quote list              — 列出组梗段
          /云原神管理 group <组名> quote add <梗段>        — 组内添加梗段
          /云原神管理 group <组名> quote remove <编号>     — 组内删除梗段
          /云原神管理 group <组名> quote set <编号> <内容>  — 组内修改梗段
        快捷操作（操作第一个组）：
          add / remove / list / first_reply / quote / blacklist / status
        """
        text = (event.message_str or "").strip()
        parts = text.split(maxsplit=2)

        if len(parts) < 2:
            yield event.plain_result(
                "📋 好想玩云原神🎊 v3.0 管理命令：\n"
                "  /云原神管理 group list / add / remove / rename   — 管理匹配组\n"
                "  /云原神管理 group <组名> add/remove/first_reply/delay/quote  — 组内配置\n"
                "  /云原神管理 add/remove/list                     — 快捷操作默认组关键词\n"
                "  /云原神管理 first_reply <文本>                   — 设默认组首次回复词\n"
                "  /云原神管理 quote add/remove/list/set            — 管理默认组梗段\n"
                "  /云原神管理 blacklist add/remove/list            — 管理群名单\n"
                "  /云原神管理 status                              — 查看当前状态"
            )
            return

        subcmd = parts[1]

        # ============= 匹配组管理（核心） =============
        if subcmd == "group":
            await self._handle_group_admin(event, parts)
            return

        # ============= 快捷操作：默认组关键词管理 =============
        if subcmd in ("add", "remove", "list"):
            await self._handle_keyword_admin(event, subcmd, parts)
            return

        # ============= 快捷操作：默认组首次回复词管理 =============
        if subcmd == "first_reply":
            await self._handle_first_reply_admin(event, parts)
            return

        # ============= 快捷操作：默认组梗段词库管理 =============
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
            f"❌ 未知子命令: {subcmd}，可用: group / add / remove / list / first_reply / quote / blacklist / status"
        )

    # ==================== 匹配组管理子逻辑（v3.0 核心） ====================

    async def _handle_group_admin(self, event: AstrMessageEvent, parts: list):
        """处理匹配组管理命令（group 子命令）"""
        groups = self.data.get("match_groups", [])
        if not isinstance(groups, list):
            groups = []
            self.data["match_groups"] = groups

        # 没有子参数 -> 显示帮助
        if len(parts) < 3 or not parts[2].strip():
            lines = [
                "📋 匹配组管理：\n",
                "  /云原神管理 group list                  — 列出所有组",
                "  /云原神管理 group add <组名>             — 新建组",
                "  /云原神管理 group remove <组名>          — 删除组",
                "  /云原神管理 group rename <旧名> <新名>   — 重命名组",
                "  /云原神管理 group <组名>                  — 查看组详情",
                "  /云原神管理 group <组名> add <关键词>      — 添加关键词到组",
                "  /云原神管理 group <组名> remove <关键词>   — 从组删除关键词",
                "  /云原神管理 group <组名> first_reply [文本] — 查看/设首次回复词",
                "  /云原神管理 group <组名> delay <毫秒>      — 设回复延迟",
                "  /云原神管理 group <组名> quote list        — 列出组梗段",
                "  /云原神管理 group <组名> quote add <梗段>  — 添加梗段到组",
                "  /云原神管理 group <组名> quote remove <编号> — 删除组梗段",
                "  /云原神管理 group <组名> quote set <编号> <内容> — 修改组梗段",
            ]
            # 显示各组概况
            if groups:
                lines.append("\n📌 当前已有组：")
                for g in groups:
                    if isinstance(g, dict):
                        kw_count = len(g.get("keywords", []))
                        q_count = len(g.get("quote_pool", []))
                        lines.append(f"   • {g.get('name', '?')}（{kw_count}个关键词，{q_count}段梗）")
            await event.send(event.plain_result("\n".join(lines)))
            return

        sub2 = parts[2].strip()
        sub2_parts = sub2.split(maxsplit=1)
        action = sub2_parts[0]

        # ==== group list ====
        if action == "list":
            lines = [f"🗂️ 匹配组列表（共 {len(groups)} 组）：\n"]
            if groups:
                for i, g in enumerate(groups, 1):
                    if isinstance(g, dict):
                        kw_count = len(g.get("keywords", []))
                        q_count = len(g.get("quote_pool", []))
                        lines.append(f"  {i}. {g.get('name', '?')} — {kw_count}个关键词，{q_count}段梗，{g.get('reply_delay_ms', 800)}ms")
                lines.append("\n💡 用 /云原神管理 group <组名> 查看组详情")
            else:
                lines.append("  （暂无匹配组，用 add <组名> 创建）")
            await event.send(event.plain_result("\n".join(lines)))
            return

        # ==== group add <组名> ====
        if action == "add":
            if len(sub2_parts) < 2 or not sub2_parts[1].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 group add <组名>"))
                return
            name = sub2_parts[1].strip()

            # 检查重名
            existing_idx, _ = self._get_group_by_name(name)
            if existing_idx is not None:
                await event.send(event.plain_result(f"⚠️ 组「{name}」已存在"))
                return

            new_group = {
                "name": name,
                "keywords": [],
                "first_reply": "欸，云朵",
                "quote_pool": [],
                "reply_delay_ms": 800
            }
            groups.append(new_group)
            self.data["match_groups"] = groups
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 已创建匹配组「{name}」\n"
                f"当前共 {len(groups)} 组\n"
                f"💡 用以下命令配置：\n"
                f"  /云原神管理 group {name} add <关键词>\n"
                f"  /云原神管理 group {name} first_reply <文本>\n"
                f"  /云原神管理 group {name} quote add <梗段>"
            ))
            return

        # ==== group remove <组名> ====
        if action == "remove":
            if len(sub2_parts) < 2 or not sub2_parts[1].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 group remove <组名>"))
                return
            name = sub2_parts[1].strip()

            idx, _ = self._get_group_by_name(name)
            if idx is None:
                await event.send(event.plain_result(f"❌ 未找到组「{name}」"))
                return

            removed = groups.pop(idx)
            self.data["match_groups"] = groups
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 已删除组「{removed.get('name', '?')}」\n"
                f"剩余 {len(groups)} 组"
            ))
            return

        # ==== group rename <旧名> <新名> ====
        if action == "rename":
            rename_parts = sub2.split(maxsplit=2)
            if len(rename_parts) < 3 or not rename_parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 group rename <旧名> <新名>"))
                return
            old_name = rename_parts[1].strip()
            new_name = rename_parts[2].strip()

            if not new_name:
                await event.send(event.plain_result("❌ 新组名不能为空"))
                return

            idx, _ = self._get_group_by_name(old_name)
            if idx is None:
                await event.send(event.plain_result(f"❌ 未找到组「{old_name}」"))
                return

            # 检查新名是否冲突
            existing_idx, _ = self._get_group_by_name(new_name)
            if existing_idx is not None and existing_idx != idx:
                await event.send(event.plain_result(f"⚠️ 组名「{new_name}」已被使用"))
                return

            groups[idx]["name"] = new_name
            self.data["match_groups"] = groups
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 已重命名「{old_name}」→「{new_name}」"
            ))
            return

        # ==== 其他：视为 group <组名> [子命令] ====
        # 先尝试查找组名（可能包含空格，所以直接使用 sub2_parts[0] 作为组名？但组名可能含空格）
        # 这里：sub2 可能是 "组名" 或 "组名 add ..." 或 "组名 first_reply ..."
        # 用完整 sub2 来匹配组名
        target_group = None
        target_idx = None
        target_name = ""

        # 尝试从 sub2 提取组名（第一个词）
        first_word = sub2_parts[0]

        # 先尝试精确匹配第一个词作为组名
        idx, g = self._get_group_by_name(first_word)
        if idx is not None:
            target_group = g
            target_idx = idx
            target_name = first_word
            # 剩余部分作为组内子命令
            remaining = sub2[len(first_word):].strip()
        else:
            # 尝试完整 sub2 匹配（含空格的情况）
            idx, g = self._get_group_by_name(sub2)
            if idx is not None:
                target_group = g
                target_idx = idx
                target_name = sub2
                remaining = ""
            else:
                await event.send(event.plain_result(f"❌ 未找到组「{first_word}」\n💡 用 group list 查看已有组"))
                return

        # 如果没有剩余子命令 -> 显示组详情
        if not remaining:
            kw_count = len(target_group.get("keywords", []))
            q_count = len(target_group.get("quote_pool", []))
            delay = target_group.get("reply_delay_ms", 800)
            first_reply = target_group.get("first_reply", "欸，云朵")
            keywords_str = "、".join(target_group.get("keywords", [])) if target_group.get("keywords") else "（空）"
            await event.send(event.plain_result(
                f"📋 组详情：{target_name}\n"
                f"━━━━━━━━━━━━━\n"
                f"🔑 关键词（{kw_count}个）：{keywords_str}\n"
                f"💬 首次回复词：「{first_reply}」\n"
                f"🎭 梗段数：{q_count} 段\n"
                f"⏱️ 回复延迟：{delay}ms\n"
                f"━━━━━━━━━━━━━\n"
                f"💡 组内管理：\n"
                f"  /云原神管理 group {target_name} add <关键词>\n"
                f"  /云原神管理 group {target_name} remove <关键词>\n"
                f"  /云原神管理 group {target_name} first_reply [文本]\n"
                f"  /云原神管理 group {target_name} delay <毫秒>\n"
                f"  /云原神管理 group {target_name} quote list/add/remove/set"
            ))
            return

        # 解析组内子命令
        remain_parts = remaining.split(maxsplit=2)
        inner_action = remain_parts[0]

        # --- group <组名> add <关键词> ---
        if inner_action == "add":
            if len(remain_parts) < 2 or not remain_parts[1].strip():
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {target_name} add <关键词>"))
                return
            keyword = remain_parts[1].strip()

            if keyword in target_group.get("keywords", []):
                await event.send(event.plain_result(f"⚠️ 组「{target_name}」中已有关键词「{keyword}」"))
                return

            target_group.setdefault("keywords", []).append(keyword)
            self.data["match_groups"] = groups
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 已向组「{target_name}」添加关键词「{keyword}」\n"
                f"该组现有 {len(target_group.get('keywords', []))} 个关键词"
            ))
            return

        # --- group <组名> remove <关键词> ---
        if inner_action == "remove":
            if len(remain_parts) < 2 or not remain_parts[1].strip():
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {target_name} remove <关键词>"))
                return
            keyword = remain_parts[1].strip()

            kw_list = target_group.get("keywords", [])
            if keyword not in kw_list:
                await event.send(event.plain_result(f"❌ 组「{target_name}」中未找到关键词「{keyword}」"))
                return

            kw_list.remove(keyword)
            self.data["match_groups"] = groups
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 已从组「{target_name}」删除关键词「{keyword}」\n"
                f"该组剩余 {len(kw_list)} 个关键词"
            ))
            return

        # --- group <组名> first_reply [文本] ---
        if inner_action == "first_reply":
            if len(remain_parts) < 2 or not remain_parts[1].strip():
                # 查看
                current = target_group.get("first_reply", "欸，云朵")
                await event.send(event.plain_result(
                    f"📋 组「{target_name}」的首次回复词：\n"
                    f"「{current}」\n\n"
                    f"💡 设置新值：/云原神管理 group {target_name} first_reply <新文本>"
                ))
                return

            new_text = remain_parts[1].strip()
            if not new_text:
                await event.send(event.plain_result("❌ 首次回复词不能为空"))
                return

            target_group["first_reply"] = new_text
            self.data["match_groups"] = groups
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 组「{target_name}」的首次回复词已设为：\n「{new_text}」"
            ))
            return

        # --- group <组名> delay <毫秒> ---
        if inner_action == "delay":
            if len(remain_parts) < 2 or not remain_parts[1].strip():
                await event.send(event.plain_result(
                    f"⏱️ 组「{target_name}」当前延迟：{target_group.get('reply_delay_ms', 800)}ms\n"
                    f"💡 设置：/云原神管理 group {target_name} delay <毫秒数>"
                ))
                return

            try:
                delay_val = int(remain_parts[1].strip())
            except ValueError:
                await event.send(event.plain_result("❌ 延迟必须是整数毫秒"))
                return

            if delay_val < 0:
                await event.send(event.plain_result("❌ 延迟不能为负数"))
                return

            target_group["reply_delay_ms"] = delay_val
            self.data["match_groups"] = groups
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 组「{target_name}」的回复延迟已设为 {delay_val}ms"
            ))
            return

        # --- group <组名> quote ... ---
        if inner_action == "quote":
            # 委托给组内的梗段管理
            await self._handle_group_quote_admin(event, target_group, target_name, groups, remain_parts)
            return

        await event.send(event.plain_result(f"❌ 未知组内子命令: {inner_action}，可用：add / remove / first_reply / delay / quote"))

    async def _handle_group_quote_admin(self, event: AstrMessageEvent, group: dict, group_name: str, groups: list, parts: list):
        """处理组内梗段词库增删改查"""
        quotes = group.get("quote_pool", [])
        if not isinstance(quotes, list):
            quotes = []
            group["quote_pool"] = quotes

        if len(parts) < 2 or not parts[1].strip():
            lines = [
                f"📋 组「{group_name}」梗段管理：\n",
                f"  /云原神管理 group {group_name} quote list              — 列出梗段",
                f"  /云原神管理 group {group_name} quote add <梗段>        — 添加梗段",
                f"  /云原神管理 group {group_name} quote remove <编号>     — 删除梗段",
                f"  /云原神管理 group {group_name} quote set <编号> <内容>  — 修改梗段",
                f"\n当前共 {len(quotes)} 段梗"
            ]
            await event.send(event.plain_result("\n".join(lines)))
            return

        sub = parts[1].strip()
        sub_parts = sub.split(maxsplit=1)
        action = sub_parts[0]

        if action == "list":
            lines = [f"🗂️ 组「{group_name}」梗段词库（共 {len(quotes)} 段）：\n"]
            if quotes:
                for i, q in enumerate(quotes, 1):
                    display = q[:40] + "…" if len(q) > 40 else q
                    lines.append(f"  {i}. {display}")
                lines.append("\n💡 可用 quote add / remove / set 管理")
            else:
                lines.append("  （暂无梗段，可用 quote add <内容> 添加）")
            await event.send(event.plain_result("\n".join(lines)))

        elif action == "add":
            if len(sub_parts) < 2 or not sub_parts[1].strip():
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} quote add <梗段>"))
                return
            content = sub_parts[1].strip()
            quotes.append(content)
            group["quote_pool"] = quotes
            self.data["match_groups"] = groups
            self._save_data()
            display = content[:30] + "…" if len(content) > 30 else content
            await event.send(event.plain_result(
                f"✅ 已向组「{group_name}」添加梗段 #{len(quotes)}：\n「{display}」\n"
                f"该组现有 {len(quotes)} 段梗"
            ))

        elif action == "remove":
            if len(sub_parts) < 2 or not sub_parts[1].strip():
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} quote remove <编号>"))
                return
            try:
                idx = int(sub_parts[1].strip())
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return

            if idx < 1 or idx > len(quotes):
                await event.send(event.plain_result(f"❌ 编号 {idx} 超出范围（1~{len(quotes)}）"))
                return

            removed = quotes.pop(idx - 1)
            group["quote_pool"] = quotes
            self.data["match_groups"] = groups
            self._save_data()
            display = removed[:30] + "…" if len(removed) > 30 else removed
            await event.send(event.plain_result(
                f"✅ 已从组「{group_name}」删除梗段 #{idx}：\n「{display}」\n"
                f"该组剩余 {len(quotes)} 段梗"
            ))

        elif action == "set":
            # set <编号> <新内容>
            set_rest = sub[len("set"):].strip()
            set_parts = set_rest.split(maxsplit=1)
            if len(set_parts) < 2:
                await event.send(event.plain_result(f"❌ 用法：/云原神管理 group {group_name} quote set <编号> <新内容>"))
                return
            try:
                idx = int(set_parts[0])
            except ValueError:
                await event.send(event.plain_result("❌ 编号必须为数字"))
                return

            if idx < 1 or idx > len(quotes):
                await event.send(event.plain_result(f"❌ 编号 {idx} 超出范围（1~{len(quotes)}）"))
                return

            new_content = set_parts[1].strip()
            if not new_content:
                await event.send(event.plain_result("❌ 梗段内容不能为空"))
                return

            old = quotes[idx - 1]
            quotes[idx - 1] = new_content
            group["quote_pool"] = quotes
            self.data["match_groups"] = groups
            self._save_data()
            old_display = old[:20] + "…" if len(old) > 20 else old
            new_display = new_content[:20] + "…" if len(new_content) > 20 else new_content
            await event.send(event.plain_result(
                f"✅ 已修改组「{group_name}」梗段 #{idx}：\n"
                f"  旧: 「{old_display}」\n"
                f"  新: 「{new_display}」"
            ))

        else:
            await event.send(event.plain_result(f"❌ 未知操作: {action}，可用: list / add / remove / set"))

    # ==================== 关键词快捷管理子逻辑（操作第一组） ====================

    async def _handle_keyword_admin(self, event: AstrMessageEvent, subcmd: str, parts: list):
        """处理关键词的添加/删除/列出（操作第一个匹配组）"""
        group = self._get_first_group()
        if not group:
            await event.send(event.plain_result("❌ 没有可操作的匹配组，请先创建组"))
            return

        keywords = group.get("keywords", [])
        if not isinstance(keywords, list):
            keywords = []
            group["keywords"] = keywords

        if subcmd == "add":
            if len(parts) < 3 or not parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 add <关键词>"))
                return
            keyword = parts[2].strip()

            if keyword in keywords:
                await event.send(event.plain_result(f"⚠️ 关键词「{keyword}」已存在（默认组）"))
                return

            keywords.append(keyword)
            group["keywords"] = keywords
            self._save_data()
            await event.send(event.plain_result(
                f"✅ 已向默认组添加关键词「{keyword}」\n"
                f"默认组共 {len(keywords)} 个关键词"
            ))

        elif subcmd == "remove":
            if len(parts) < 3 or not parts[2].strip():
                await event.send(event.plain_result("❌ 用法：/云原神管理 remove <关键词>"))
                return
            keyword = parts[2].strip()

            if keyword in keywords:
                keywords.remove(keyword)
                group["keywords"] = keywords
                self._save_data()
                await event.send(event.plain_result(
                    f"✅ 已从默认组删除关键词「{keyword}」\n"
                    f"默认组剩余 {len(keywords)} 个关键词"
                ))
            else:
                await event.send(event.plain_result(f"❌ 默认组中未找到关键词「{keyword}」"))

        elif subcmd == "list":
            lines = [f"📋 默认组触发关键词列表（共 {len(keywords)} 个）：\n"]
            if keywords:
                for i, kw in enumerate(keywords, 1):
                    lines.append(f"  {i}. {kw}")
            else:
                lines.append("  （暂无关键词，可用 add <关键词> 添加）")
            lines.append("\n💡 可用 add / remove 管理，修改后自动持久化保存")
            await event.send(event.plain_result("\n".join(lines)))

    # ==================== 首次回复词快捷管理子逻辑（操作第一组） ====================

    async def _handle_first_reply_admin(self, event: AstrMessageEvent, parts: list):
        """处理首次回复词的查看和设置（操作第一个匹配组）"""
        group = self._get_first_group()
        if not group:
            await event.send(event.plain_result("❌ 没有可操作的匹配组"))
            return

        if len(parts) < 3:
            current = group.get("first_reply", "欸，云朵")
            await event.send(event.plain_result(
                f"📋 默认组当前首次回复词：\n「{current}」\n\n"
                "💡 设置新值：/云原神管理 first_reply <新文本>"
            ))
            return

        new_text = parts[2].strip()
        if not new_text:
            await event.send(event.plain_result("❌ 首次回复词不能为空"))
            return

        group["first_reply"] = new_text
        self._save_data()
        await event.send(event.plain_result(
            f"✅ 默认组首次回复词已设置为：\n「{new_text}」\n"
            "下次触发时将使用新文本"
        ))

    # ==================== 梗段词库快捷管理子逻辑（操作第一组） ====================

    async def _handle_quote_admin(self, event: AstrMessageEvent, parts: list):
        """处理梗段词库的增删改查（操作第一个匹配组）"""
        group = self._get_first_group()
        if not group:
            await event.send(event.plain_result("❌ 没有可操作的匹配组"))
            return

        quotes = group.get("quote_pool", [])
        if not isinstance(quotes, list):
            quotes = []
            group["quote_pool"] = quotes

        groups = self.data.get("match_groups", [])

        if len(parts) < 3 or not parts[2].strip():
            await event.send(event.plain_result(
                "📋 默认组梗段词库管理：\n"
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
            lines = [f"🗂️ 默认组梗段词库（共 {len(quotes)} 段）：\n"]
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
            group["quote_pool"] = quotes
            self._save_data()
            display = content[:30] + "…" if len(content) > 30 else content
            await event.send(event.plain_result(
                f"✅ 已向默认组添加梗段 #{len(quotes)}：\n「{display}」\n"
                f"默认组共 {len(quotes)} 段梗"
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
            group["quote_pool"] = quotes
            self._save_data()
            display = removed[:30] + "…" if len(removed) > 30 else removed
            await event.send(event.plain_result(
                f"✅ 已从默认组删除梗段 #{idx}：\n「{display}」\n"
                f"默认组剩余 {len(quotes)} 段梗"
            ))

        elif action == "set":
            rest = parts[2].strip()
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
            group["quote_pool"] = quotes
            self._save_data()
            old_display = old[:20] + "…" if len(old) > 20 else old
            new_display = new_content[:20] + "…" if len(new_content) > 20 else new_content
            await event.send(event.plain_result(
                f"✅ 已修改默认组梗段 #{idx}：\n"
                f"  旧: 「{old_display}」\n"
                f"  新: 「{new_display}」"
            ))

        else:
            await event.send(event.plain_result(f"❌ 未知操作: {action}，可用: add / remove / list / set"))

    # ==================== 黑名单管理子逻辑 ====================

    async def _handle_blacklist_admin(self, event: AstrMessageEvent, parts: list):
        """处理黑/白名单的添加/删除/列出"""
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
        """查看当前插件整体状态（v3.0 多组版）"""
        groups = self.data.get("match_groups", [])
        if not isinstance(groups, list):
            groups = []
        total_kw = sum(len(g.get("keywords", [])) for g in groups if isinstance(g, dict))
        total_q = sum(len(g.get("quote_pool", [])) for g in groups if isinstance(g, dict))
        bl_groups = self.data.get("blacklist_groups", [])
        if not isinstance(bl_groups, list):
            bl_groups = []
        trigger_enabled = self.config.get("enable_keyword_trigger", True)
        mode = self.config.get("blacklist_mode", "blacklist")

        lines = [
            "📊 好想玩云原神🎊 v3.0 状态",
            "━━━━━━━━━━━━━━━━━━",
            f"🔘 关键词触发: {'✅ 开启' if trigger_enabled else '❌ 关闭'}",
            f"📦 匹配组: {len(groups)} 组",
            f"🔑 总计关键词: {total_kw} 个",
            f"🎭 总计梗段: {total_q} 段",
            f"🚫 群名单模式: {mode}（{len(bl_groups)} 个群）",
            ""
        ]

        # 各组详情
        if groups:
            lines.append("━━━ 各组详情 ━━━")
            for i, g in enumerate(groups, 1):
                if isinstance(g, dict):
                    kw_count = len(g.get("keywords", []))
                    q_count = len(g.get("quote_pool", []))
                    delay = g.get("reply_delay_ms", 800)
                    fr = g.get("first_reply", "欸，云朵")
                    lines.append(f"  {i}. 「{g.get('name', '?')}」")
                    lines.append(f"     关键词: {kw_count}个 | 梗段: {q_count}段 | 延迟: {delay}ms")
                    lines.append(f"     首次回复: 「{fr}」")

        lines.append("\n━━━━━━━━━━━━━━━━━━")
        lines.append("💡 用 /云原神管理 查看完整帮助")
        lines.append("📋 用 /云原神管理 group 管理多组")

        await event.send(event.plain_result("\n".join(lines)))

    # ==================== 生命周期 ====================

    async def terminate(self):
        """插件卸载时保存数据"""
        self._save_data()
        logger.info("🎊 好想玩云原神🎊 v3.0 已卸载，数据已保存")
