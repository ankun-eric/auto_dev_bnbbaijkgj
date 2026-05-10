# PRD-442 · AI 对话风格全域迁移（晴空诊室落地）— 用户体验手册

> 版本：v1.0 · 实施基线  
> 上线日期：2026-05-10  
> 关联基线：PRD-441《AI 对话风格规范 v1.0 · 晴空诊室》

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 全域设计系统 v2 入口页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html) | 11 级色板 / 8 图标种子集 / 病历卡铁律 demo |
| design-tokens.css 文件 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/design-tokens.css](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/design-tokens.css) | H5 端 token CSS（脚本生成） |
| icons.json 资源 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/icons.json](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/icons.json) | 8 个种子图标 SVG map |
| PRD-442 实施版文档 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/PRD-442.md](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/PRD-442.md) | 本轮已交付与未交付清单 |
| AI 主入口（PRD-441 已部署） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 回归校验入口（无副作用） |
| 安卓 APK 下载 | [app_prd443_20260510115642_bcb3.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_prd443_20260510115642_bcb3.apk) | 安卓客户端安装包，本次新版（80.8 MB） |
| iOS 端下载 | [iOS Build ios-prd443-v20260510-114747-3858](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd443-v20260510-114747-3858) | iOS 客户端安装包，前往 GitHub Release 下载 |
| 微信小程序下载 | [miniprogram_prd443_20260510114745_be9e.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd443_20260510114745_be9e.zip) | 微信小程序代码包（412 KB） |

## 功能简介

本次将 PRD-441「晴空诊室」从**设计基线**推进到**全域三端落地**的核心基建：

- **单一真相源**：`design-system/design-tokens.json` 成为 H5 / 小程序 / Flutter 三端的唯一可手改 token 源
- **三端 token 自动同步**：脚本一键把 JSON 生成 H5 css / 小程序 wxss / Flutter dart，确保三端永远一致
- **Flutter token 包**：`packages/bini_design_tokens` 通过 Monorepo `path:` 引用接入 Flutter App
- **图标库**：8 个双色 SVG 种子图标 + 三端组件 API 统一参数（name / size / color / weight）
- **CI Lint**：旧绿色清退脚本（三层扫描——色值 / 语义关键词 / 图片资源）
- **可视化入口**：H5 端访问 `/design-system-v2/index.html` 即可查看 11 级色板、8 图标、病历卡铁律演示

## 本次客户端变更

本次更新涉及以下终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| 微信小程序 | `miniprogram/styles/design-tokens.wxss` 全新 token 文件（11 级 brand sky-* + 5 渐变 + 字号/间距/圆角/阴影），`app.wxss` 顶部 `@import` 引入；旧 `--primary-color` 暂保留以兼容现有页面，按 PRD §7 渐进式清退 | [miniprogram_prd443_20260510114745_be9e.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd443_20260510114745_be9e.zip) |
| 安卓端 | `flutter_app/pubspec.yaml` 新增 `bini_design_tokens` path 依赖；新增 `flutter_app/lib/theme/bh_design_v2.dart` PRD-442 设计 v2 适配器；新增 `packages/bini_design_tokens/` Flutter 包（`BhTokens` / `BhGradients` / `BhShadows` / `BhTheme.lightTheme()` / `BhIcon` Widget） | [app_prd443_20260510115642_bcb3.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_prd443_20260510115642_bcb3.apk) |
| iOS 端 | 同安卓（Flutter 共享 lib/） | [iOS Build ios-prd443-v20260510-114747-3858](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd443-v20260510-114747-3858) |

> 以上终端的代码在本次更新中有改动，请务必下载最新版本。H5 网页端无需用户额外操作，访问 `design-system-v2/index.html` 即可看到新内容。

## 使用说明

### 一、查看设计系统入口（H5）

1. 打开浏览器访问 [全域设计系统 v2 入口页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html)
2. 滚动浏览以下内容：
   - **顶部 hero**：深蓝渐变 + 5 个 metadata 标签
   - **11 级色板**：从 brand-50（极浅）到 brand-900（最深）共 11 级天蓝色阶
   - **核心交付物卡片**：6 张介绍卡（单一真相源 / H5 / 小程序 / Flutter / 图标 / Lint）
   - **图标种子集**：8 个双色 SVG 图标（health-report / heart-rate / medication / family / bell / camera / voice / chevron-down）
   - **病历卡铁律演示**：左侧 3px 天蓝竖线 + 主按钮渐变
3. 点击「查看 design-tokens.css」可查看完整 token 文件内容

### 二、查看完整 PRD-442 实施版文档

直接打开 [PRD-442.md 浏览](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/PRD-442.md)，包含：

- 一、本轮已交付（7 项）
- 二、本轮未交付（剩余 30 天排期内的项目）
- 三、铁律（8 条）
- 四、运行命令速查
- 五、与 PRD-442（菜单模式 v1）的关系

### 三、Flutter 端：使用 token 包

App 工程师在新模块中可直接：

```dart
import 'package:bini_design_tokens/bini_design_tokens.dart';

Container(
  color: BhTokens.colorBrand400,
  decoration: BoxDecoration(
    gradient: BhGradients.primaryBtn,
    boxShadow: BhShadows.shadow2,
  ),
);

BhIcon(name: 'health-report', size: 24, color: BhTokens.colorBrand600);
```

### 四、小程序端：使用 token 变量

任意 page 的 wxss 中可直接使用：

```css
.my-card {
  background: var(--color-brand-50);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-2);
  font-size: var(--fs-md);
}
.bh-card-medical { /* 病历卡铁律已内建 */ }
```

### 五、运行 token 同步与 lint 命令（开发者）

```bash
# 重新生成三端 token 文件（编辑 design-tokens.json 后必须执行）
node scripts/gen-tokens.mjs

# 重新生成三端图标资源（向 design-system/icons/ 添加 SVG 后执行）
node scripts/gen-icons.mjs

# 旧绿色清退扫描（仅报告）
node scripts/lint-legacy-green.mjs

# 旧绿色清退（CI 阻断模式）
node scripts/lint-legacy-green.mjs --strict
```

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 下载地址：[miniprogram_prd443_20260510114745_be9e.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd443_20260510114745_be9e.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将下载的 zip 文件解压到任意目录
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击「导入项目」
   - 在「目录」栏选择第 2 步解压后的文件夹
   - 「AppID」可填入项目的 AppID 或选择「测试号」
   - 点击「导入」
6. **预览体验**：导入后开发者工具会自动编译，可在模拟器中操作体验，本次更新后 `app.wxss` 全局已可使用 `var(--color-brand-*)` 等新 token

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 下载地址：[app_prd443_20260510115642_bcb3.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_prd443_20260510115642_bcb3.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接将 APK 安装包下载到手机（也可先下载到电脑再传到手机）
2. **允许安装**：如果手机提示「不允许安装未知来源应用」，请在手机设置中开启「允许安装未知来源应用」
3. **安装应用**：点击下载的 APK 文件，按照提示完成安装
4. **打开体验**：安装完成后，在桌面找到应用图标，点击打开即可

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> GitHub Release 页面：[iOS Build ios-prd443-v20260510-114747-3858](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd443-v20260510-114747-3858)
>
> IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-prd443-v20260510-114747-3858/bini_health_ios.ipa)

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方「IPA 直接下载」链接将 IPA 安装包下载到电脑
2. **安装到设备**（任选其一）：
   - **AltStore / Sideloadly 侧载**：在电脑安装 [AltStore](https://altstore.io/) 或 [Sideloadly](https://sideloadly.io/)，连接 iPhone/iPad，将 IPA 安装到设备
   - **Apple Configurator 2（Mac）**：连接设备，将 IPA 拖拽到设备
   - **TestFlight**（如已配置）：根据邀请链接加入测试
3. **信任开发者证书**（如需）：「设置 → 通用 → VPN 与设备管理」中信任对应证书
4. **打开体验**：在桌面找到应用图标，点击打开

## 注意事项

1. **本次未触碰存量业务代码**：不动任何现有 H5 业务页面 / 小程序业务 page / Flutter screen 的代码，因此不存在线上回滚风险；阶段 2 部署后回归校验 PRD-441 ai-home / design-system / menu-mode-design-system 入口均 200 OK。
2. **小程序旧 `--primary-color: #52c41a` 暂保留**：是为了兼容现有页面避免视觉断裂；后续按 PRD §7 渐进式清退，全部替换为 `var(--color-brand-*)`。
3. **图标种子集 8 个 ≠ 全量 80 个**：本轮先把生成基建跑通，后续设计师按 §5.1 七大分类补齐 60~80 个，再次运行 `node scripts/gen-icons.mjs` 即可同步三端。
4. **lint 当前为非 strict 模式**：仅报告不阻断；CI 接入时建议加 `--strict`，并先把现有 `app.wxss` 旧绿色与商城/订单/支付页绿色清理干净，避免大面积阻断。
5. **AA 无障碍**：base 字号 14px、关键指标字号 ≥ 22px、可点击区域 ≥ 44pt 均已写入 token 与铁律；字号四档无障碍开关 UI 待后续业务接入。
6. **Flutter 包路径引用**：本期 Monorepo 内部通过 `path: ../packages/bini_design_tokens` 引用，未来若拆多仓库改 `git: url:` 即可，改造成本 < 30 分钟。

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 全域设计系统 v2 入口页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/index.html) | 11 级色板 / 8 图标种子集 / 病历卡铁律 demo |
| design-tokens.css 文件 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/design-tokens.css](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/design-tokens.css) | H5 端 token CSS（脚本生成） |
| icons.json 资源 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/icons.json](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/icons.json) | 8 个种子图标 SVG map |
| PRD-442 实施版文档 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/PRD-442.md](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/design-system-v2/PRD-442.md) | 本轮已交付与未交付清单 |
| AI 主入口（PRD-441 已部署） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ai-home) | 回归校验入口（无副作用） |
| 安卓 APK 下载 | [app_prd443_20260510115642_bcb3.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/apk/app_prd443_20260510115642_bcb3.apk) | 安卓客户端安装包，本次新版（80.8 MB） |
| iOS 端下载 | [iOS Build ios-prd443-v20260510-114747-3858](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-prd443-v20260510-114747-3858) | iOS 客户端安装包，前往 GitHub Release 下载 |
| 微信小程序下载 | [miniprogram_prd443_20260510114745_be9e.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/miniprogram/miniprogram_prd443_20260510114745_be9e.zip) | 微信小程序代码包（412 KB） |
