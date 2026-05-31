# 新增家庭成员 → 邀请二维码跳转 Bug 修复 使用手册

> 版本：v1.0　发布日期：2026-05-31
> 范围：H5、微信小程序、安卓 App、iOS App（四端口径完全统一）

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端页面 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 主入口，浏览器打开即可登录体验 |
| 微信小程序 zip 下载 | [miniprogram_invite_bugfix_20260531_234116_dff9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_invite_bugfix_20260531_234116_dff9.zip) | 导入微信开发者工具体验小程序 |
| 安卓 APK 下载 | [app_invite_bugfix_20260531_234323_073d.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_invite_bugfix_20260531_234323_073d.apk) | 安卓客户端安装包，点击下载后安装 |
| iOS 端下载 | [iOS Build ios-v20260531-234323-073d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260531-234323-073d) | iOS 客户端安装包，前往 GitHub Release 下载 IPA |

---

## 功能简介

本次解决了「AI 首页 → 咨询人 → 新增 → 去邀请 TA」流程的关键 Bug：

- **修复前**：保存新成员后点「去邀请 TA」，会跳到一个让人**重新填写姓名/关系的旧表单页面**，看不到刚加那个人的二维码。
- **修复后**：
  1. 点击「去邀请 TA」会**直接跳到刚新建成员的二维码邀请页**，立刻展示二维码图。
  2. 「完善本人资料」拦截**前移到点新增成员那一刻**——如果本人姓名/性别/出生日期没填全，先弹「完善健康档案」抽屉，填完保存后**自动接着**查名额、开添加成员表单（一气呵成）。
  3. 若直接访问二维码邀请页但**没带成员 id**，页面正中显示红字提示「⚠️ 缺少成员信息，无法生成邀请，请从成员档案进入」，**不再出现重填表单**。
  4. **H5 / 小程序 / 安卓 App / iOS App 四端行为完全一致**，调用同一套后端接口。

---

## 本次客户端变更

本次更新涉及以下终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| H5 | 「咨询人选择器」加完善档案拦截 + 跳转带 member_id；「二维码邀请页」删旧表单兜底、删本页完善资料逻辑、没 id 显示红字错误 | 直接访问 [H5 入口](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) |
| 微信小程序 | chat 页「新增咨询人」加完善档案拦截前移；「成员已添加成功 → 去邀请 TA」无 id 兜底改为报错；family-invite 页文案更新 | [miniprogram_invite_bugfix_20260531_234116_dff9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_invite_bugfix_20260531_234116_dff9.zip) |
| 安卓 App | chat 页「+ 新建家庭成员」加完善档案拦截前移弹窗 | [app_invite_bugfix_20260531_234323_073d.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_invite_bugfix_20260531_234323_073d.apk) |
| iOS App | chat 页「+ 新建家庭成员」加完善档案拦截前移弹窗 | [iOS Build ios-v20260531-234323-073d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260531-234323-073d) |

> ⚠️ 以上终端的代码在本次更新中均有改动，请务必下载最新版本。

---

## 使用说明（端无关）

### 步骤一：本人资料完善拦截（前移到点新增时）

1. 进入 AI 首页，点左下角「咨询人」按钮 → 弹「选择咨询人」面板。
2. 点底部「+ 新增咨询人」（小程序/App 称为「+ 新建家庭成员」）。
3. **若本人资料未完善**（缺姓名 / 性别 / 出生日期任一）→ 弹「完善健康档案」抽屉：
    - 填写姓名（必填）、性别（必填）、出生日期（必填）
    - 其它字段（身高、体重、既往病史、过敏史）为选填，可在「其他（选填）」折叠区填写
    - 点「保存」→ Toast「保存成功」后**自动**进入下一步（查名额、开添加成员表单），无需重新点击「新增」
4. **若本人资料已完善** → 直接进入下一步。

### 步骤二：查名额

- 自动调用后端 `/api/family/member/quota`：
    - **名额已满**：弹「家庭成员名额已满」框，按钮「暂不升级」/「去升级」（去升级 → 跳会员中心）
    - **名额未满**：进入添加成员表单

### 步骤三：填写并保存成员

1. 选择关系（父亲 / 母亲 / 配偶 等）
2. 填写姓名（必填）、性别（必填）、出生日期（必填）
3. 选填：身高、体重、既往病史、过敏史
4. 点「保存」→ Toast「添加成功」

### 步骤四：成员已添加成功 → 去邀请 TA

保存成功后自动弹「成员已添加成功🎉」框：

- 「暂不邀请」→ 关闭弹框，回到选择咨询人面板
- 「去邀请 TA」→ **直接跳到二维码邀请页**，立刻展示该成员的二维码（不再出现"重填表单"）
    - 浏览器地址会变为 `…/family-invite?member_id=XXX`（XXX 为刚保存成员的 id）
    - 卡片顶部蓝色渐变，标题：**「邀请 TA 加入我的健康守护」**
    - 三个标签：📋 档案管理 · 💊 用药提醒 · 🔔 异常提醒
    - 二维码下方提示：**「邀请 24 小时内有效」**
    - 三个按钮：**保存到本地**（实心蓝） / **复制链接**（实心蓝） / **转发微信好友**（微信绿）

### 步骤五（备选）：异常处理

- 若直接访问 `/family-invite`（不带 `member_id`）→ 页面正中显示红字 **「⚠️ 缺少成员信息，无法生成邀请，请从成员档案进入」**，不再渲染旧表单。
- 若需要邀请已存在的成员，可从「健康档案 → 档案列表」中找到该成员卡片，点「邀请」按钮进入二维码页（带 id）。

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_invite_bugfix_20260531_234116_dff9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_invite_bugfix_20260531_234116_dff9.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将下载的 zip 文件解压到任意目录（记住解压后的文件夹路径）
3. **下载微信开发者工具**：如尚未安装，请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击开发者工具首页的「导入项目」（或「+」号）
   - 在「目录」栏点击浏览，选择第 2 步解压后的 `miniprogram` 子目录
   - 「AppID」栏可填入项目的 AppID，或选择「测试号」进行体验
   - 点击「导入」按钮
6. **预览体验**：导入成功后，开发者工具会自动编译并在模拟器中展示小程序界面
   - 进入「AI 助手」Tab → 点击咨询人 → 点「+ 新建家庭成员」即可体验本次修复

---

## 安卓端体验

### 下载安装包

点击以下链接下载安卓客户端安装包：

> 📱 下载地址：[app_invite_bugfix_20260531_234323_073d.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_invite_bugfix_20260531_234323_073d.apk)

### 安装与体验步骤

1. **下载 APK**：点击上方链接，将 APK 安装包下载到手机（或先下载到电脑再传输到手机）
2. **允许安装**：如手机提示「不允许安装未知来源应用」，请在「设置 → 安全」或「设置 → 隐私」中开启「允许安装未知来源应用」
3. **安装应用**：点击下载的 APK 文件，按提示完成安装
4. **打开体验**：在桌面找到「宾尼小康」图标，点击打开
   - 进入「AI 助手」Tab → 点击咨询人按钮 → 点「+ 新建家庭成员」即可体验本次修复

---

## iOS 端体验

### 下载安装包

点击以下链接前往 GitHub Release 页面下载 iOS 客户端安装包：

> 🍎 GitHub Release 页面：[iOS Build ios-v20260531-234323-073d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260531-234323-073d)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260531-234323-073d/bini_health_ios.ipa)

### 安装与体验步骤

1. **下载 IPA 文件**：点击上方「IPA 直接下载」链接，将 IPA 安装包下载到电脑
2. **安装到设备**（任选其一）：
   - **方式一：使用 AltStore / Sideloadly 侧载**
     - 安装 [AltStore](https://altstore.io/) 或 [Sideloadly](https://sideloadly.io/)
     - 用数据线连接 iPhone/iPad 到电脑
     - 用工具将 IPA 安装到设备
   - **方式二：使用 Apple Configurator 2（需 Mac 电脑）**
     - 在 Mac 上打开 Apple Configurator 2，连接 iPhone/iPad，将 IPA 拖入设备
3. **信任开发者证书**：首次打开如提示不可信，前往「设置 → 通用 → VPN 与设备管理」找到对应证书点击「信任」
4. **打开体验**：在桌面找到应用图标，点击打开
   - 进入「AI 助手」Tab → 点击咨询人 → 点「+ 新建家庭成员」即可体验本次修复

---

## 注意事项

1. **本次只动「我邀请别人当我的家庭成员」这条线**（管理者邀请被守护者）。「守护我的人」反向邀请（健康档案 → 「守护我的人」卡片 → 邀请按钮）**完全不受影响**。
2. **完善档案拦截判断标准**：后端按「姓名 + 性别 + 出生日期」三项跨表（health_profiles / family_members / users）取并集判定，老用户不会误弹。
3. **邀请有效期**：每条邀请二维码有效期为 **24 小时**，超期需重新生成。
4. **接口口径**：H5、小程序、App 调用同一套后端接口：
    - `GET /api/health-profile/self`（拦截判断）
    - `GET /api/family/member/quota`（查名额）
    - `POST /api/family/members`（保存成员，返回新成员 id）
    - `POST /api/family/invitation`（按 member_id 生成邀请码）

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端页面 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | H5 主入口，浏览器打开即可登录体验 |
| 微信小程序 zip 下载 | [miniprogram_invite_bugfix_20260531_234116_dff9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_invite_bugfix_20260531_234116_dff9.zip) | 导入微信开发者工具体验小程序 |
| 安卓 APK 下载 | [app_invite_bugfix_20260531_234323_073d.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_invite_bugfix_20260531_234323_073d.apk) | 安卓客户端安装包，点击下载后安装 |
| iOS 端下载 | [iOS Build ios-v20260531-234323-073d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260531-234323-073d) | iOS 客户端安装包，前往 GitHub Release 下载 IPA |

### 微信小程序体验

> 📦 下载地址：[miniprogram_invite_bugfix_20260531_234116_dff9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_invite_bugfix_20260531_234116_dff9.zip)

下载后解压 → 微信开发者工具「导入项目」选择解压目录 → 编译预览。

### 安卓端体验

> 📱 下载地址：[app_invite_bugfix_20260531_234323_073d.apk](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/app_invite_bugfix_20260531_234323_073d.apk)

下载后在手机上打开 APK 安装，需开启「允许安装未知来源应用」。

### iOS 端体验

> 🍎 GitHub Release 页面：[iOS Build ios-v20260531-234323-073d](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/tag/ios-v20260531-234323-073d)
>
> 📦 IPA 直接下载：[bini_health_ios.ipa](https://github.com/ankun-eric/auto_dev_bnbbaijkgj/releases/download/ios-v20260531-234323-073d/bini_health_ios.ipa)

通过 AltStore / Sideloadly / Apple Configurator 2 侧载安装，首次打开需在「设置 → 通用 → VPN 与设备管理」中信任开发者证书。
