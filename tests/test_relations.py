"""真实 SDK 下验证关系解析和钩子提示；只使用虚构号码。"""

import asyncio
import json
import logging
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from plugin import IdentityPlugin, IdentityPluginConfig


class RelationTests(unittest.TestCase):
    def setUp(self):
        self.plugin = IdentityPlugin()
        self.plugin._ctx = SimpleNamespace(logger=logging.getLogger("family-test"))
        self.plugin._plugin_config_instance = IdentityPluginConfig()
        self.plugin.config.identity.roster = (
            "100000001 = 爸爸: 优先回应\n"
            "100000002＝妈妈：自然亲近\n"
            "100000003 = 哥哥: 互怼但不暧昧\n"
            "100000004 = 朋友: 喜欢聊游戏\n"
            "# 100000005 = 忽略\n"
        )
        self.plugin._rebuild_roster()

    def test_custom_and_legacy_roster(self):
        self.assertEqual(len(self.plugin._labels), 4)
        self.assertEqual(self.plugin._label_for("100000002"), ("妈妈", True))
        self.assertEqual(self.plugin._label_for("100000099"), ("群友", False))
        self.assertEqual(self.plugin._rule_for("100000003", "哥哥"), "互怼但不暧昧")
        self.assertIn("喜欢聊游戏", self.plugin._rule_for("100000004", "朋友"))

    def test_unknown_names_are_not_invented(self):
        self.assertEqual(self.plugin._known_relations("100000001"), [])

    def test_known_relations_and_broken_timestamp(self):
        self.plugin._recent = {
            "m1": {"user_id": "100000002", "name": "小花", "ts": "broken"},
            "m2": {"user_id": "100000003", "name": "小树", "ts": 2},
        }
        note = self.plugin._render_note(
            {"user_id": "100000001", "name": "小河"}, "爸爸"
        )
        self.assertIn("小花是你的妈妈", note)
        self.assertIn("小树是你的哥哥", note)
        self.assertNotRegex(note, r"\d{5,}")

    def test_long_numbers_in_admin_description_are_removed(self):
        self.plugin.config.identity.roster = "100000001 = 爸爸: 编号123456789自然回应"
        self.plugin._rebuild_roster()
        self.assertEqual(self.plugin._descs["100000001"], "编号自然回应")

    def test_injection_and_deduplication(self):
        self.plugin._recent["message-a"] = {
            "user_id": "100000003", "name": "小树", "session": "test"
        }
        kwargs = {
            "session_id": "test",
            "items": [{"parts": [{"type": "text", "text": '[msg_id:message-a]你好'}]}],
        }
        result = self.plugin._handle_injection(kwargs, "replyer")
        self.assertEqual(result["action"], "continue")
        self.assertIn("你的哥哥", json.dumps(kwargs, ensure_ascii=False))
        count = len(kwargs["items"])
        self.plugin._handle_injection(kwargs, "replyer")
        self.assertEqual(count, len(kwargs["items"]))
        self.assertNotIn("100000003", json.dumps(kwargs))

    def test_numeric_name_blocks_injection(self):
        self.plugin._recent["message-b"] = {
            "user_id": "100000001", "name": "123456789", "session": "test"
        }
        kwargs = {"session_id": "test", "items": [
            {"parts": [{"type": "text", "text": "[msg_id:message-b]你好"}]}]}
        self.plugin._handle_injection(kwargs, "replyer")
        self.assertEqual(len(kwargs["items"]), 1)

    def test_config_hot_reload(self):
        self.plugin.config.identity.roster = "100000001 = 闺蜜: 爱聊电影"
        asyncio.run(self.plugin.on_config_update("identity", {}, "2"))
        self.assertEqual(self.plugin._label_for("100000001"), ("闺蜜", True))
        self.assertEqual(self.plugin._descs["100000001"], "爱聊电影")


if __name__ == "__main__":
    unittest.main()
