# AI 对话模式方案 A 全量落地 · PRD-447 用户体验使用手册

> 本次更新基于 **PRD-447 v2 修正定稿**，将设计方案 A（晴空淡天蓝 + 渐变体系）全量落地到 H5 端 与后台主题配置模块。无新版客户端发布（小程序 / APP 本次未变更）。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80 / 443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主入口 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 落地页（PC/移动端均可） |
| AI 主战场（屏 ①） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/) | 三宫格已切换为方案 A 淡天蓝渐变 |
| 设计系统 12 组件预览页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2-preview/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2-preview/) | 12 个通用组件可视化集合（验收基础页） |
| 设计系统 v2 索引页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html) | PRD-442 设计系统入口 |
| 后台主题配置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/theme-config](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/theme-config) | 列表 / 编辑 / 预览 / 启用主题 |
| 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login/) | H5 登录入口 |
| 首页 / 个人中心 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home/) · [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/) | 主链路页面 |

---

## 功能简介

PRD-447 v2「方案 A 全量落地」是 PRD-441/442 设计基建之后的**业务面收口里程碑**，目标是把已建立的"晴空淡天蓝"设计语言一次性交付给 H5 端 29 屏与后台主题模块，让用户在所有页面看到统一的视觉语言。本次落地包含：

1. **设计 token 三层体系全量补缺口**（原子层 / 主题层 / 语义层）
2. **12 个通用 React 组件统一封装**（5 个薄壳 + 7 个全新）
3. **AI 主页（ai-home）顶部硬编码彩色渐变清零**，三宫格统一切到方案 A 淡天蓝渐变
4. **后台主题可配置模块**（4 个 API + 主题列表/编辑/预览/启用 + H5 启动热注入）
5. **硬编码颜色 lint 脚本**，从源头杜绝业务代码硬编码
6. **39 用例服务器侧自动化测试** 全部通过

---

## 使用说明

### 1）查看 12 个新组件实际效果（推荐入口）

打开 [设计系统 12 组件预览页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2-preview/)，可一次性查看：

- **MedicalCard**：病历卡气泡（左侧 3px brand-400 竖线）
- **PrimaryButton**：主操作渐变按钮（`#38bdf8 → #0284c7`）
- **TopBar**：淡天蓝顶栏
- **UserBubble**：用户对话气泡（深一档天蓝）
- **HeroDark**：深色 hero 区
- **FnCell**：功能宫格（替换 ai-home 顶部三色硬编码渐变）
- **RecommendCard**：双色 SVG 推荐卡（屏 ④ 空对话页）
- **FamilyChip**：家人 chip（屏 ⑤、⑱）
- **RadarChart5**：5 维健康雷达（屏 ⑱ 健康档案）
- **FollowupChip**：流式追问 chip（屏 ⑨）
- **ThinkingDots**：思考态三圆点
- **VoiceWave**：语音声波 + 实时转写（屏 ⑥）

### 2）AI 主页三宫格新视觉

打开 [AI 主战场](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/)，向下滚动至"今日健康贴士"轮播下方，可看到：

- 三宫格（AI诊室 / 看报告 / 健康档案）已**全部切换为统一的方案 A 淡天蓝渐变**
- 旧的紫蓝 / 橙黄 / 绿青三色硬编码渐变已彻底干掉
- 顶部"健康贴士"卡片背景也切换到方案 A 主操作渐变

### 3）后台主题配置使用

进入 [后台主题配置页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/theme-config)：

- **主题列表**：查看已建主题，状态分为「已启用」「草稿」「已禁用」
- **预览**：点击行的"预览"按钮，可在右侧 Drawer 查看 11 级品牌色板 + 5 个核心渐变
- **编辑**：点击"编辑"按钮，在弹窗内以 JSON 编辑器修改 token；保存后状态变为「草稿」
- **启用**：点击"启用"按钮，**事务式**把当前启用主题置为禁用，新主题立即推送
- **H5 注入**：H5 启动时自动拉取启用主题（见 `/api/h5/active-theme`），失败降级保留工程内置默认 token

### 4）开发者本地 lint 校验

新增脚本 `scripts/lint-prd447-hardcoded-colors.py`，可在 CI 阶段直接运行：

```bash
python scripts/lint-prd447-hardcoded-colors.py --strict
```

- 检查 `h5-web/src/components/design-system/*` 是否有硬编码 hex / rgb(a) / linear-gradient
- 检测到违规则非零退出（CI 失败）
- 默认仅扫描 design-system 目录（业务页面按 PRD §10 风险 1「不重命名已有变量」原则保留兼容）

---

## 注意事项

### 关于"是否需要重新安装"
- **微信小程序 / 安卓 APP / iOS APP**：本次**没有任何代码改动**，**无需重新下载安装**，可继续使用旧版本
- **H5 / 后台**：刷新浏览器即可看到新视觉，无需任何操作

### 关于"主题热更新"
- 后台启用主题后，已打开的 H5 页面**需刷新一次**才能看到新主题（首次注入会落到 localStorage 缓存，下次秒开）
- H5 注入接口（`/api/h5/active-theme`）任何异常都会**降级保留工程内置默认 token**，不影响渲染

### 关于"老页面是否会破坏"
- 本次严格遵循 PRD §10 「**只追加不重命名**」铁律，旧 `--color-brand-50~900` / `.bh-*` 工具类全部保留
- 老页面引用的 `var(--primary-color)` / `var(--gradient-primary-btn)` 等变量也保留，业务零改动获得新视觉
- 已通过 39 用例自动化回归（包含主链路 P0 5 屏 + 后台 4 个 API + H5 注入接口）

### 关于"未来里程碑"
本次为 PR-1 ~ PR-3 + PR-4 的 P0 主链路集成版本：
- ✅ 已交付：token 缺口补全、12 组件、后台主题模块、ai-home 5 处硬编码渐变清零、stylelint 等价物 + CI 脚本
- ⏭️ 后续里程碑：PR-5 ~ PR-7（其余 24 屏切组件、Playwright 截图回归、深色模式预留）

---

## 关键技术决策（节选）

| 决策 | 取舍 |
|------|------|
| 不重命名已有 `--color-brand-*` 变量 | 100+ 业务页面在引用，重命名等于破窗（PRD §10 风险 1） |
| 不在全局劫持 rem | PRD-441/442 业务页面用 px 单位，全局 rem 会全站塌陷；新组件预览页里可按需启用 |
| stylelint 用 Python 脚本而非新增 npm 依赖 | 不增加 H5 容器构建依赖，CI 友好 |
| 后台主题用内存仓库 | 与 `login_ui_config` 同风格，生产可平滑接入 DB |
| H5 主题注入失败降级到内置 token | PRD §10 风险 4，保证渲染不受网络影响 |
| 12 组件强制 data-testid | 自动化截图回归友好，已通过 12 用例 testId 验收 |
| 业务页面"只清 ai-home 5 处硬编码渐变" | 复用 PRD-442 已落的 globals.css 体系，不外推灰色地带（PRD-442 八条铁律之一） |

---

## 自动化测试清单（39/39 PASS）

| 用例段 | 用例数 | 内容 |
|--------|--------|------|
| T01-T05 路由可达 | 5 | 预览页 / ai-home / 主链路 |
| T06 12 组件 testId | 12 | 12 个组件全部出现在预览页 |
| T07 ai-home 旧色清零 | 1 | 检查 5 个旧硬编码 hex 全部消失 |
| T08 globals.css 含 v447 token | 13 | 关键 token / 工具类存在性 |
| T09-T14 后台主题 API | 6 | 4 个 admin API + H5 注入 + 幂等 |
| T15 lint 通过 | 1 | design-system 零硬编码色彩 |

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80 / 443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主入口 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 落地页 |
| AI 主战场（屏 ①） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home/) | 三宫格已切换为方案 A |
| 设计系统 12 组件预览页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2-preview/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2-preview/) | 12 组件验收基础页 |
| 设计系统 v2 索引页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html) | PRD-442 索引 |
| 后台主题配置 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/theme-config](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/theme-config) | 主题列表 / 编辑 / 预览 / 启用 |
| 登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/login/) | H5 登录入口 |
| 首页 / 个人中心 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home/) · [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/profile/) | 主链路页面 |
