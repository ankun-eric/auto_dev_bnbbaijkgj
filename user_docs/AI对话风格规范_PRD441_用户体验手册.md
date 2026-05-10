# bini-health · AI 对话风格规范 PRD-441（宾尼小康）· 用户体验使用手册

> 本手册面向**设计师 / 前端工程师 / 测试工程师 / 产品经理**，介绍如何在线访问与查阅 PRD-441「AI 对话风格规范 v1.0」全套交付物（设计 Token + PRD 文档 + 29 屏 HTML 原型核对版）。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 设计系统首页（推荐入口） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/index.html](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/index.html) | 本次 PRD-441 全部 4 大交付物的导航入口 |
| 29 屏 HTML 原型核对版 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/prototype.html](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/prototype.html) | 5 大分组共 29 屏完整视觉基线，可直接看截屏效果 |
| PRD Markdown 文档 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/PRD-441.md](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/PRD-441.md) | 9 章节完整规范文档（设计哲学/Token/组件/页面/交互/辅助色控量等） |
| design-tokens.css | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.css](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.css) | 完整 CSS 变量与组件类（11 级天蓝色阶+ 16 类组件） |
| design-tokens.json | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.json](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.json) | 结构化设计 token，可被 Style Dictionary / iOS / Android 消费 |
| 项目主页（回归验证） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 原 AI 对话首页继续可用，本次未影响线上功能 |

---

## 功能简介

本次 PRD-441 是 **bini-health AI 对话模式视觉与交互规范**的奠基交付，确立了「**方案 A · 宾尼小康**」为后续所有 AI 对话相关页面的唯一设计基线。

**三大设计原则**：
1. **主色调铁律** — 整个 App 严格使用「淡天蓝」单一主色调，禁止引入红/橙/绿等对撞色作为视觉主体
2. **病历卡感** — AI 卡片统一采用「白底 + 左侧 3px 天蓝竖线」的"病历卡"形态，强化「医疗专业」品牌锚点
3. **中老年友好** — 顶栏使用最舒适的 A1 淡天蓝渐变（`#f0f9ff → #dbeafe`），关键正文字号不低于 14px，关键指标数字不低于 22px

**4 大可在线访问的交付物**：
- 🖼 **29 屏 HTML 原型核对版**（5 分组：对话基础态 3 屏 / 对话扩展态 6 屏 / 业务交互态 7 屏 / 核心业务页 7 屏 / 其余业务页 6 屏）
- 📄 **PRD Markdown 规范文档**（9 章节，含设计哲学 / Token 体系 / 组件库 / 页面规范 / 交互规范 / 辅助色控量等）
- 🎨 **design-tokens.css**（11 级天蓝色阶 + 5 大渐变 + 9 级字号 + 7 级圆角 + 4 级阴影 + 16 类组件类）
- 📦 **design-tokens.json**（机器可读格式，可被任意端消费）

---

## 使用说明

### 路径 A：设计师 / PM 走查 — 看 29 屏原型

1. 打开 [设计系统首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/index.html)
2. 点击「**29 屏核对版 HTML 原型**」卡片，进入 prototype.html
3. 顶部导航栏列出 5 大分组（对话基础 3 屏 / 对话扩展 6 屏 / 业务交互 7 屏 / 核心业务 7 屏 / 其余业务 6 屏），点击锚点直接跳转到对应分组
4. 每屏页面都模拟真机尺寸，可直接对照设计走查、切图标注
5. 每张屏的左上角标号对应 PRD 第五章页面规范的编号（① ~ ㉙）

### 路径 B：前端工程师 — 接入 design-tokens.css

在任意 H5 / Next.js 页面中引入：

```html
<link rel="stylesheet" href="https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.css" />
```

或下载到本地工程：

```bash
curl -O https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.css
```

然后即可在任意 CSS / 内联样式中直接使用变量：

```css
.my-ai-bubble {
  background: var(--gradient-user-bubble);
  border-radius: var(--radius-lg);
  padding: var(--space-3) var(--space-4);
  font-size: var(--font-size-md);
  box-shadow: var(--shadow-card);
}
```

或直接复用预设组件类：

```html
<div class="bh-ai-card">小康为您解读...</div>
<button class="bh-btn-primary">立即咨询</button>
<span class="bh-badge bh-badge--high">血压偏高</span>
```

### 路径 C：iOS / Android / 跨端 — 消费 design-tokens.json

```ts
// JS / TS 端
import tokens from './design-tokens.json';
const primary = tokens.color.brand['400'].value; // "#38bdf8"
```

```python
# Python 端
import json, requests
tokens = requests.get('https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.json').json()
print(tokens['color']['brand']['400']['value'])  # #38bdf8
```

可使用 [Style Dictionary](https://amzn.github.io/style-dictionary/) 或自定义脚本将 JSON 转换为 iOS `Colors.swift` / Android `colors.xml`。

### 路径 D：测试工程师 — UI 走查

1. 对照 [PRD Markdown 文档](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/PRD-441.md) 第七章「辅助色控量（红线规范）」，校验线上页面是否违规使用红/橙/绿等辅助色作为视觉主体
2. 校验所有 AI 卡片是否带「左侧 3px 天蓝竖线」（病历卡形态）
3. 校验顶栏渐变是否符合 `--gradient-topbar`（A1 淡天蓝）
4. 校验关键指标字号是否 ≥ 22px（中老年友好原则）
5. 校验阴影是否使用天蓝色阴影（`rgba(56, 189, 248, …)`），不应出现纯黑阴影 `rgba(0, 0, 0, …)`

---

## 注意事项

### 重要约束（红线，不可违反）
- ✅ **主色调铁律**：所有 AI 对话相关页面只允许使用 11 级天蓝色阶 + 中性色 + 渐变 token，**严禁**使用绿/橙/红/紫等其他主色调作为大面积底色或主操作按钮
- ⚠️ **辅助色仅限 4 类语义场景使用**：
  - 暖橙 `#fbbf24` → 仅会员等级 / 星级评价 / 倒计时高亮
  - 红 `#ef4444` → 仅紧急徽标 / 错误重试 / 危险操作
  - 绿 `#22c55e` → 仅在线状态 / 达标徽章 / 成功 Toast
  - 黄 `#eab308` → 仅"偏高/临界"指标徽章
- ❌ **任何"既可以用主色也可以用辅助色"的场景，一律使用主色**。设计评审若发现辅助色用于非红线场景，**必须打回**

### 与现有线上业务的关系
- 本次 PRD-441 是**新建**的 AI 对话风格规范基线，作为后续所有 AI 对话相关页面的设计依据
- 本次**未变更**线上现有的 H5 / 小程序 / Flutter 业务页面（这些页面继续使用既有的绿色品牌色 `#52c41a`）
- 后续将通过单独的迁移任务（PRD-442/PRD-443 等）逐步将 AI 对话相关模块切换为本规范
- 业务页面（如订单、商城、支付等）不在本规范覆盖范围内，仍按各业务线 PRD 执行

### 暗色模式
- 本规范 v1.0 仅覆盖**亮色模式**
- 暗色模式 token 计划在 v1.1 补充

### 浏览器兼容性
- 所有交付物使用 CSS 自定义属性（CSS Variables）+ 现代 CSS 特性
- 推荐浏览器：Chrome 90+ / Safari 14+ / Firefox 90+ / Edge 90+
- 移动端：iOS Safari 14+ / Android Chrome 90+

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 设计系统首页（推荐入口） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/index.html](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/index.html) | 本次 PRD-441 全部 4 大交付物的导航入口 |
| 29 屏 HTML 原型核对版 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/prototype.html](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/prototype.html) | 5 大分组共 29 屏完整视觉基线，可直接看截屏效果 |
| PRD Markdown 文档 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/PRD-441.md](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/PRD-441.md) | 9 章节完整规范文档（设计哲学/Token/组件/页面/交互/辅助色控量等） |
| design-tokens.css | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.css](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.css) | 完整 CSS 变量与组件类（11 级天蓝色阶 + 16 类组件） |
| design-tokens.json | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.json](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system/design-tokens.json) | 结构化设计 token，可被 Style Dictionary / iOS / Android 消费 |
| 项目主页（回归验证） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 原 AI 对话首页继续可用，本次未影响线上功能 |

---

> 本手册基于 PRD-441 v1.0 定稿基线编制，由 小白 AI 自动生成于 2026-05-10。
> 后续如对设计 token 或组件规范有变更，请按变更评审流程更新版本历史并重新发布。
