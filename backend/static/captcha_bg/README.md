# Captcha Background Images

将 30 张 320x160 的背景图（jpg/png，建议 < 30KB / 张，无版权图片如 Unsplash CC0）放入此目录。

`slider_captcha_service.py` 会随机抽一张作为滑块拼图底图。

如果该目录为空，服务会自动降级为程序生成的渐变背景图（仍可正常完成验证流程，
仅视觉上较朴素）。
