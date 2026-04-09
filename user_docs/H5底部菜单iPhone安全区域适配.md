# H5 底部菜单 iPhone 安全区域适配

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 用户端 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 移动端主页面入口（经 Nginx 代理） |

---

## 功能简介

本次修复了 H5 移动端底部 TabBar 导航菜单在 **iPhone 全面屏机型**（带 Home Indicator 横线的机型，如 iPhone X 及以后的系列）上的显示问题。

**修复前**：底部 TabBar 的中间菜单项文字被 iPhone Home Indicator 横线遮盖，导致看不清楚、影响操作体验。

**修复后**：
- TabBar 菜单项全部显示在 Home Indicator 上方，图标和文字完整可见
- Home Indicator 下方区域使用白色背景填充，与 TabBar 视觉一体
- 在没有 Home Indicator 的设备上（安卓手机、老款 iPhone）显示效果不受影响

---

## 使用说明

### 1. 打开 H5 页面

在 iPhone 手机浏览器（Safari 或微信内置浏览器）中，访问以下链接：

[https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/)

### 2. 查看底部导航栏

页面加载后，注意观察屏幕底部的 TabBar 导航栏（4 个菜单项）：

- **修复后效果**：所有菜单项的图标和文字完整显示在 Home Indicator 横线上方
- 横线下方区域为白色背景，与 TabBar 融为一体
- 每个菜单项均可正常点击切换页面

### 3. 各页面验证

点击底部不同的菜单项，分别进入首页、AI 健康咨询、健康服务、我的页面，确认：
- 每个页面底部内容没有被 TabBar 遮挡
- 底部 TabBar 在每个页面上都正确适配了安全区域

---

## 注意事项

1. **适用设备**：本次修复主要针对带 Home Indicator 的 iPhone 全面屏机型（iPhone X 及以后），在安卓手机和老款 iPhone 上显示效果与修复前一致
2. **浏览器要求**：建议使用 Safari 浏览器或微信内置浏览器访问，以获得最佳的安全区域适配效果
3. **清除缓存**：如果看到的页面效果没有变化，请尝试清除浏览器缓存后刷新页面
4. **横屏模式**：本修复同样适配横屏模式下的安全区域

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 用户端 | [https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/](https://newbb.test.bangbangvip.com/autodev/3b7b999d-e51c-4c0d-8f6e-baf90cd26857/) | H5 移动端主页面入口（经 Nginx 代理） |
