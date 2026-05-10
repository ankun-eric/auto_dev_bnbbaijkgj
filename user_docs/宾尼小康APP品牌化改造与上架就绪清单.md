# 宾尼小康 APP 品牌化改造决策记录与上架就绪清单

> 文档版本：v1.0
> 编写日期：2026-05-10
> 适用范围：宾尼小康健康管理 APP（Android / iOS 双端）

---

## 一、本次品牌化改造完成情况速览

| 项目 | 改造前 | 改造后 |
|------|--------|--------|
| Android 包名 (applicationId) | `com.binihealth.app` | `com.benekang.app` |
| Android namespace | `com.binihealth.app` | `com.benekang.app` |
| Android Manifest package | `com.binihealth.app` | `com.benekang.app` |
| Kotlin 源码 package 路径 | `com/binihealth/app/` | `com/benekang/app/` |
| iOS Bundle Identifier | `com.binihealth.app` | `com.benekang.app` |
| iOS 工程 org（GitHub Actions） | `com.binihealth` | `com.benekang` |
| 显示名（Android `android:label` / iOS `CFBundleDisplayName`） | 宾尼小康 | 宾尼小康（不变） |
| 应用图标 | 现有图标 | 现有图标（不变） |

> 已实施的改造均落在「不可逆部分」，符合 PRD 第 5 章"在上架前一次性收口包名/Bundle ID"的核心目标。

---

## 二、候选拼写对比与最终决策

### 2.1 候选清单与对比

| 候选 | Android 包名 | iOS Bundle ID | 字符长度 | 品牌词独立性 | 易记性 | 推荐指数 |
|------|--------------|---------------|----------|-------------|--------|----------|
| **A（已选定）** | `com.benekang.app` | `com.benekang.app` | 16 | ★★★★ | ★★★★★ | ★★★★★ |
| B | `com.bene.kang` | `com.bene.kang` | 13 | ★★★★★ | ★★★★ | ★★★★ |
| C | `com.bene.xiaokang` | `com.bene.xiaokang` | 18 | ★★★★ | ★★★ | ★★★★ |
| D | `com.beneai.binikang` | `com.beneai.binikang` | 20 | ★★★ | ★★★ | ★★★ |
| E | `com.benehealth.app` | `com.benehealth.app` | 18 | ★★★ | ★★★ | ★★★ |

### 2.2 最终决策

✅ **采用候选 A：`com.benekang.app`**

**决策理由：**

1. **简洁好记**：3 段式命名，整体字符短，方便业务方在与第三方 SDK 平台沟通时书写、传达
2. **品牌强绑定**："Bene" + "Kang" 既保留了母品牌 Bene，又呼应中文产品名「宾尼小康」中的"康"
3. **后缀规范**：`.app` 是 2020 年后移动端主流的命名习惯（参考 Google / Apple 官方推荐范例）
4. **风险最低**：无歧义、无敏感词、无与现有大厂应用包名冲突的风险

> ⚠️ **不可逆约束（已落地）**：自本次提交后，工程内**不再保留任何旧包名引用**，亦不保留"备选包名开关"。后续如需更换包名，必须走"重新上架新应用"流程。

---

## 三、改造范围核查（已完成项）

### 3.1 Android 端

| 文件 | 改动点 | 状态 |
|------|--------|------|
| `flutter_app/android/app/build.gradle` | `namespace` 与 `applicationId` | ✅ |
| `flutter_app/android/app/src/main/AndroidManifest.xml` | `manifest package` | ✅ |
| `flutter_app/android/app/src/main/kotlin/com/benekang/app/MainActivity.kt` | Kotlin `package` 声明与目录路径 | ✅ |
| 旧目录 `kotlin/com/binihealth/app/` | 已物理删除 | ✅ |

### 3.2 iOS 端

| 文件 | 改动点 | 状态 |
|------|--------|------|
| `flutter_app/ios/Runner.xcodeproj/project.pbxproj` | Debug + Release 两套 `PRODUCT_BUNDLE_IDENTIFIER` | ✅ |
| `.github/workflows/ios-build.yml` | `flutter create --org` 由 `com.binihealth` 改为 `com.benekang` | ✅ |
| `flutter_app/ios/Runner/Info.plist` | `CFBundleIdentifier` 引用 `$(PRODUCT_BUNDLE_IDENTIFIER)` 占位符，自动随 pbxproj 更新 | ✅ |
| 显示名 `CFBundleDisplayName` | 保持「宾尼小康」 | ✅（不变） |

### 3.3 保留不动的应用标识（合规说明）

下列代码中 `binihealth` 作为**第三方地图 App 唤起协议的 sourceApplication / referer / src 标识**，与 Android 包名 / iOS Bundle ID 是**两套独立体系**，地图开放平台对这些参数不强制要求与包名一致：

- `flutter_app/lib/utils/map_nav_util.dart`（高德 / 百度 / 腾讯地图唤起参数）
- `h5-web/src/components/MapNavSheet.tsx`（H5 端地图唤起 fallback 参数）

为避免影响已联调好的地图导航功能，本期保持现状。后续如需统一也可在另一轮迭代中处理，**不影响应用商店上架**。

---

## 四、上架就绪清单（待公司专人按此清单回填）

> ⚠️ 以下内容请通过加密渠道（如 1Password / Bitwarden / 加密邮件）传输，**严禁以明文方式发送至任何 IM 群、邮箱附件或 Git 仓库**。

### 4.1 Android 端 —— Google Play

| 序号 | 项目 | 类型 | 用途 | 是否必填 |
|------|------|------|------|----------|
| A1 | Google Play 服务账号 JSON Key | `.json` 文件 | CI/CD 自动化发布 | 必填 |
| A2 | 上传密钥 Keystore（`upload-keystore.jks`） | `.jks` 文件 + 密钥别名 + 别名密码 + 仓库密码 | APK 签名（首次上架后由 Google 托管） | 必填 |
| A3 | 包名 | 字符串 | `com.benekang.app`（已锁定） | 已确定 |
| A4 | Play Console App ID | 字符串 | 应用标识 | 创建后自动生成 |

### 4.2 Android 端 —— 国内安卓应用市场

| 市场 | 必备项 |
|------|--------|
| 华为应用市场 | 开发者账号 + AppID + AppSecret + 签名证书 SHA-256 指纹 + IAP 公钥（如使用支付） |
| 小米应用商店 | 开发者账号 + AppID + 签名证书 SHA-1 / SHA-256 指纹 |
| OPPO 软件商店 | 开发者账号 + AppKey + AppSecret + 签名证书指纹 |
| vivo 应用商店 | 开发者账号 + 应用签名（MD5 / SHA-1 / SHA-256） |
| 应用宝（腾讯） | 开发者账号 + AppID + 签名指纹 |

### 4.3 iOS 端

| 序号 | 项目 | 类型 | 用途 |
|------|------|------|------|
| I1 | Apple Developer Team ID | 字符串（10 位） | 开发者团队标识 |
| I2 | App Store Connect API Key | `.p8` 文件 + Key ID + Issuer ID | 自动化发布 |
| I3 | iOS Distribution Certificate | `.cer` / `.p12` + 密码 | 上架商店签名 |
| I4 | Provisioning Profile（App Store） | `.mobileprovision` | 上架打包 |
| I5 | Provisioning Profile（Ad Hoc） | `.mobileprovision` | 内测分发 |
| I6 | Provisioning Profile（Development） | `.mobileprovision` | 真机调试 |
| I7 | APNs Auth Key | `.p8` 文件 + Key ID + Team ID | 苹果推送服务 |
| I8 | App Store Connect 应用记录 | Bundle ID = `com.benekang.app` | 创建应用 |

### 4.4 推送服务

| 服务 | 必备项 |
|------|--------|
| Firebase Cloud Messaging（FCM） | `google-services.json`（Android）+ Server Key + Sender ID |
| 个推 | AppID + AppKey + AppSecret + MasterSecret |
| 极光推送 | AppKey + Master Secret |
| APNs（iOS） | Auth Key 文件 + Key ID + Team ID（已包含在 I7） |

### 4.5 第三方登录 / 分享 / 支付 SDK

| 平台 | 必备项 | 备注 |
|------|--------|------|
| 微信开放平台 | iOS AppID + Android AppID + AppSecret + 包名 + 签名 MD5 | iOS 与 Android 的 AppID 通常相同，需在开放平台后台配置签名 |
| QQ 互联 | AppID + AppKey | 同时配置 iOS Bundle ID 与 Android 包名签名 |
| 支付宝 | 商户号（PID）+ APPID + 应用 RSA 私钥 + 支付宝公钥 | 需在支付宝开放平台后台绑定包名 / Bundle ID |
| 微博开放平台 | AppKey + AppSecret + 重定向 URL | 需绑定签名 |
| Apple Pay（iOS） | Merchant ID + 商户证书 | 仅 iOS |

### 4.6 服务端配置同步

公司服务端需要同步以下配置：

1. **推送平台后台**（FCM / APNs / 个推 / 极光）的"应用包名/Bundle ID"全部更新为 `com.benekang.app`
2. **深链 Universal Links** 相关：
   - `apple-app-site-association` 文件中的 `appID` 更新为 `<TeamID>.com.benekang.app`
   - `assetlinks.json` 文件中的 `package_name` 更新为 `com.benekang.app`，并补齐新签名的 `sha256_cert_fingerprints`
3. **微信、QQ、支付宝、微博开放平台后台** 的应用配置中：包名 / Bundle ID 改为 `com.benekang.app`，并补齐新签名的 SHA-1 / MD5 指纹

---

## 五、签名密钥管理策略

### 5.1 当前阶段（内测）

- 使用 **GitHub Actions 自动生成的 debug 签名**进行 APK 构建（见 `flutter_app/android/app/build.gradle` 中 `release { signingConfig signingConfigs.debug }`）
- 此签名**仅用于内测**，不可作为上架商店的签名
- 内测 APK 文件命名：`bini_health_<tag>.apk`，配套生成 SHA-256 校验和

### 5.2 未来阶段（正式上架）

| 步骤 | 操作 | 责任人 |
|------|------|--------|
| 1 | 公司专人申请到开发者账号后，本地生成正式签名 keystore | 公司专人 |
| 2 | 将 keystore 文件、别名、密码以加密方式提供给小白 AI | 公司专人 |
| 3 | 小白 AI 在 GitHub Actions Secrets 中配置签名信息（`KEYSTORE_BASE64` / `KEY_ALIAS` / `KEY_PASSWORD` / `STORE_PASSWORD`） | 小白 AI |
| 4 | 修改 `build.gradle` 增加 `signingConfigs.release`，并在 release buildType 中引用 | 小白 AI |
| 5 | 同步将新签名指纹回填到所有第三方 SDK 平台后台（微信 / QQ / 支付宝 / 推送 / 应用市场） | 小白 AI + 公司专人 |
| 6 | 出正式 Release APK，灰度内测后正式上架 | 小白 AI |

⚠️ **关键铁律**：

- 临时内测签名 keystore 与正式上架 keystore 必须**物理分离**
- Google Play 一旦使用 Play App Signing，**上架后无法更换签名**，正式 keystore 须妥善备份至少 3 份独立位置
- 严禁将任何 keystore 文件提交至 Git 仓库

---

## 六、风险提示

| 风险项 | 等级 | 应对建议 |
|--------|------|---------|
| 已选定包名 `com.benekang.app` 在上架后永久不可更改 | 高 | 业务方在使用前请进行最后一次商标 / 域名查询，确认 `benekang.com` 等域名可用 |
| 旧版 APP（`com.binihealth.app`）用户无法平滑覆盖升级 | 中 | 在内测说明与未来上架公告中明确"需卸载旧版后重装"，并提供数据迁移指引 |
| 第三方 SDK 后台未及时更新包名 | 中 | 在正式上架前完成"SDK 后台配置 Checklist"逐项核对（详见第四章） |
| 内测密钥外泄 | 中 | 蒲公英分发启用安装密码；密钥本地加密存储，禁止入库 |
| iOS 端 Ad Hoc / TestFlight 包暂未产出 | 中 | 等苹果开发者账号到位后，本周已完成的代码改造可立即出包，无额外阻塞 |

---

## 七、后续衔接事项

本次品牌化改造仅覆盖"不可逆的标识层"。后续以下事项不在本期范围，需在另行迭代中规划：

- 应用图标的品牌化升级（等品牌设计部门提供素材）
- 启动页 / 引导页的视觉升级
- 应用商店上架素材（应用截图、应用描述、隐私政策、用户协议）
- 正式上架的运营推广方案
- 地图导航 SDK sourceApplication 标识统一为 `benekang`（如有需要）

---

**文档结束**
