"""
[PRD-440] AI 回答下方操作栏视觉与交互优化 — 源码层面非UI自动化测试

由于本次为纯前端视觉/交互改造（无后端 API 改动），故采用源码静态扫描的方式
验证五端代码均按 PRD 关键决策点完成改造，并验证已部署 H5 站点仍可达。

验证项：
1. H5 共享组件 AiActionBar 存在并包含关键设计 token（颜色、动效参数）
2. H5 ai-home 页面已接入 AiActionBar
3. H5 chat/[sessionId] 页面已接入 AiActionBar
4. H5 SharePanel 已升级为渐变风
5. 小程序 wxml/wxss 包含新的操作栏结构与 Wi-Fi 弧线动效
6. Flutter chat_screen.dart 已使用新的 _buildAiActionBar440 + 渐变 painter + Wi-Fi pulse rings
7. 已部署 H5 站点根 URL 可达
"""

import os
import re
import ssl
import urllib.request
import unittest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
PROJECT_BASE_URL = "https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/"


def read(rel_path: str) -> str:
    fp = os.path.join(ROOT, rel_path)
    with open(fp, encoding="utf-8") as f:
        return f.read()


class TestPrd440SourceLevel(unittest.TestCase):
    # ------------------ H5 共享组件 ------------------
    def test_01_h5_action_bar_component_exists(self):
        text = read("h5-web/src/components/ai-chat/AiActionBar.tsx")
        # PRD 4.1 配色：渐变主色起点/终点
        self.assertIn("#6a8dff", text)
        self.assertIn("#b07cff", text)
        # 提示文字默认值
        self.assertIn("AI 生成仅供参考", text)
        # Wi-Fi 弧线动效关键参数：1000ms 一圈，3 圈错位 333ms
        self.assertIn("1000ms", text)
        self.assertIn("333", text)
        # 提示文字与图标分隔虚线颜色
        self.assertIn("#E5E5E5", text)
        # Toast 顶部文案
        self.assertIn("已复制", text)
        # 默认未触发态浅灰
        self.assertIn("#999", text)
        # 三个图标 aria-label 顺序固定
        ic = text.index("复制")
        ish = text.index("转发")
        isp = text.index("语音播报")
        self.assertLess(ic, ish, "复制 应排在 转发 之前")
        self.assertLess(ish, isp, "转发 应排在 语音播报 之前")

    # ------------------ H5 ai-home ------------------
    def test_02_h5_ai_home_uses_action_bar(self):
        text = read("h5-web/src/app/(ai-chat)/ai-home/page.tsx")
        self.assertIn("AiActionBar", text)
        self.assertIn("notifyCopied", text)
        self.assertIn("PRD-440", text)

    # ------------------ H5 chat/[sessionId] ------------------
    def test_03_h5_chat_session_uses_action_bar(self):
        text = read("h5-web/src/app/chat/[sessionId]/page.tsx")
        self.assertIn("AiActionBar", text)
        self.assertIn("notifyCopied", text)
        self.assertIn("PRD-440", text)
        # 旧的「📋 复制」「停止播报」按钮应已被移除
        self.assertNotIn("已复制' : '复制'", text)

    # ------------------ H5 SharePanel ------------------
    def test_04_h5_share_panel_gradient(self):
        text = read("h5-web/src/components/ai-chat/SharePanel.tsx")
        # 不再使用 emoji 渠道图标，已切换到 SVG 渐变描边
        self.assertIn("AI_ACTION_BAR_GRADIENT_ID", text)
        self.assertIn("ChannelIcon", text)
        # 仍保留四个渠道
        for kind in ["wechat", "moments", "copy", "poster"]:
            self.assertIn(kind, text)

    # ------------------ 小程序 ------------------
    def test_05_miniprogram_action_bar(self):
        wxml = read("miniprogram/pages/chat/index.wxml")
        wxss = read("miniprogram/pages/chat/index.wxss")
        # wxml: 新的操作栏类名
        self.assertIn("ai-action-bar-440", wxml)
        self.assertIn("AI 生成仅供参考", wxml)
        # 三个按钮顺序：复制 → 转发 → 语音播报
        c = wxml.index("ai-action-bar-440-icon-copy")
        s = wxml.index("ai-action-bar-440-icon-share")
        sp = wxml.index("ai-action-bar-440-icon-speaker")
        self.assertLess(c, s)
        self.assertLess(s, sp)
        # Wi-Fi 三圈
        self.assertIn("ring1", wxml)
        self.assertIn("ring2", wxml)
        self.assertIn("ring3", wxml)
        # wxss: 渐变色值、虚线分隔线、动效参数
        self.assertIn("6a8dff", wxss)
        self.assertIn("b07cff", wxss)
        self.assertIn("#E5E5E5", wxss)
        self.assertIn("dashed", wxss)
        self.assertIn("1000ms", wxss)
        self.assertIn("333ms", wxss)
        # 旧 emoji 操作栏已移除
        self.assertNotIn(".ai-card-action-bar {", wxss)

    def test_06_miniprogram_copy_uses_native_toast(self):
        js = read("miniprogram/pages/chat/index.js")
        # 仍用 wx.showToast 调用系统原生提示
        self.assertIn("wx.showToast", js)
        self.assertIn("已复制", js)

    # ------------------ Flutter ------------------
    def test_07_flutter_action_bar(self):
        text = read("flutter_app/lib/screens/ai/chat_screen.dart")
        self.assertIn("PRD-440", text)
        self.assertIn("_buildAiActionBar440", text)
        # 旧 _buildAiActionRow 已被 PRD-440 替换
        self.assertNotIn("_buildAiActionRow(message)", text)
        # 渐变色值
        self.assertIn("0xFF6A8DFF", text)
        self.assertIn("0xFFB07CFF", text)
        # Wi-Fi 弧线扩散动效
        self.assertIn("_WifiPulseRings", text)
        # 三个图标 kind
        self.assertIn("_GradientIconKind.copy", text)
        self.assertIn("_GradientIconKind.share", text)
        self.assertIn("_GradientIconKind.speaker", text)
        # 提示文字
        self.assertIn("AI 生成仅供参考", text)
        # 移动端复制原生轻提示
        self.assertIn("已复制", text)
        # 全宽 1px 虚线
        self.assertIn("_DashedDivider", text)

    # ------------------ 服务器可达 ------------------
    def test_08_deployed_site_reachable(self):
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(
            PROJECT_BASE_URL,
            headers={"User-Agent": "prd440-test"},
        )
        with urllib.request.urlopen(req, timeout=20, context=ctx) as resp:
            self.assertEqual(resp.status, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
