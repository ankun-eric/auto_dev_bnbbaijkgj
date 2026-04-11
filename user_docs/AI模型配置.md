# AI 大模型配置 — 用户体验使用手册

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 管理后台 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/) | 管理后台入口（经 Nginx 代理，端口 80） |
| H5 用户端 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 用户端入口 |

---

## 功能简介

**AI 大模型配置**是管理后台中的一个功能模块，允许管理员对接和管理多种 AI 大模型服务（如 OpenAI、DeepSeek、通义千问等）。通过该功能，管理员可以：

- 添加、编辑、删除 AI 模型配置
- 设置 API Base URL、模型名称、API Key 等参数
- 配置最大 Token 数和 Temperature 参数
- 启用/停用不同的 AI 模型配置
- 在线测试 AI 模型连接是否正常

系统会使用当前启用（活跃）的 AI 模型配置来处理用户的 AI 对话、健康分析、中医辨证等智能服务。

---

## 使用说明

### 第一步：登录管理后台

1. 打开管理后台链接：[https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/)
2. 输入管理员手机号和密码
3. 点击「登录」按钮进入管理后台

### 第二步：进入 AI 模型配置页面

1. 在左侧菜单栏中找到「AI 模型配置」菜单项
2. 点击进入 AI 大模型配置页面
3. 页面显示当前所有 AI 模型配置的列表

### 第三步：新增 AI 模型配置

1. 点击页面右上角的「新增配置」按钮
2. 在弹出的表单中填写以下信息：
   - **服务商名称**：如 OpenAI、DeepSeek、通义千问等
   - **API Base URL**：AI 服务的 API 地址（如 `https://api.openai.com/v1`）
   - **模型名称**：要使用的具体模型（如 `gpt-4`、`deepseek-chat`）
   - **API Key**：AI 服务提供商分配的密钥
   - **最大 Token 数**：单次调用允许的最大 Token 数量（默认 4096）
   - **Temperature**：控制 AI 回答的随机性，范围 0~2（默认 0.7）
   - **设为活跃配置**：开启后，此配置将被用于系统的 AI 服务调用
3. 填写完毕后，可以先点击「测试连接」验证配置是否有效
4. 确认无误后点击「保存」按钮

### 第四步：编辑已有配置

1. 在配置列表中找到需要修改的配置
2. 点击对应行的「编辑」按钮
3. 在弹出的表单中修改相关信息（API Key 留空则不修改）
4. 点击「保存」完成修改

### 第五步：删除配置

1. 在配置列表中找到需要删除的配置
2. 点击对应行的「删除」按钮
3. 在确认弹框中点击「确定」完成删除

### 第六步：测试连接

1. 新增或编辑配置时，填写完 API 信息后
2. 点击「测试连接」按钮
3. 系统会尝试调用 AI 模型接口，显示连接成功或失败的结果

---

## 注意事项

1. **活跃配置唯一**：系统同一时间只能有一个活跃的 AI 模型配置。启用新配置时，其他配置会自动变为停用状态。
2. **API Key 安全**：API Key 在列表页面以脱敏形式显示（仅显示前几位 + ****），保障密钥安全。
3. **测试连接**：建议在保存前先进行连接测试，确保 API 地址和密钥填写正确。
4. **Temperature 说明**：值越低（接近 0），AI 回答越确定和保守；值越高（接近 2），回答越随机和发散。推荐值为 0.7。
5. **Max Tokens 说明**：控制 AI 单次回答的最大长度。根据业务需求调整，过小可能导致回答被截断。
6. **权限要求**：仅管理员账号可以访问和操作 AI 模型配置功能。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 管理后台 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/admin/) | 管理后台入口（经 Nginx 代理，端口 80） |
| H5 用户端 | [https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 用户端入口 |
