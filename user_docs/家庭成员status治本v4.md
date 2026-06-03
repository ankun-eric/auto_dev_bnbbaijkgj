# 家庭成员状态治本 v4 · 用户体验使用手册

> 版本：v4 最终版（2026-06-03）
> 目标：让"家庭成员"的绑定状态成为唯一可信来源，彻底消灭"邀请中却显示已绑定"、"未绑定却打勾"等状态错乱问题。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主入口（经 Nginx 80/443 代理） |
| 健康档案页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/) | 顶部成员 Tab + 健康档案展示 |
| 家庭守护列表 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-guardian-list/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-guardian-list/) | 我守护的人/守护我的人 列表 |
| 邀请扫码页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth/) | 扫描邀请二维码后的接受/拒绝页面 |
| 微信小程序包 | [miniprogram_family_status_v4_20260603_172108_70d6.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_family_status_v4_20260603_172108_70d6.zip) | 微信小程序代码压缩包，本次同步打包 |

---

## 功能简介

本次更新是一次对"家庭成员绑定状态"的**底层治本修复**，重点解决以下用户可见的状态错乱：

- **现象 A**：成员卡片显示已绑定（绿色 ✓），但其实邀请还在进行中 / 已过期 / 已被拒绝
- **现象 B**：解除守护后，成员卡片仍然显示打勾，需要刷新或重新登录才正确
- **现象 C**：误删已绑定档案后留下残留守护关系数据，导致后续异常

治本方法：
1. 把"邀请过期 / 邀请拒绝 / 守护关系取消"这 3 类事件，从"只改一张业务表"升级为**双表原子事务**——业务表（邀请/管理）和成员表（FamilyMember.status）要么一起成功，要么一起回滚
2. 新增"删除前 status='bound' 拒绝"硬校验，提醒用户**先解除守护再删除档案**
3. 新增"新增家庭成员不允许直接传 member_user_id"硬校验，从源头切断"建档即假绑定"的脏数据路径
4. 删除接口里"v3_main_status"等冗余字段，前端直接读取 `status` 即可

---

## 本次客户端变更

本次更新涉及以下终端的代码改动，请下载最新版本体验：

| 终端 | 变更说明 | 新版本下载 |
|------|----------|------------|
| H5（Web 端） | 健康档案页、家庭守护列表、家庭成员 Tab 组件三处打勾判断改为正向 `status==='bound'`；移除 v3_main_status 字段引用 | （已在线生效，无需下载，刷新浏览器即可） |
| 微信小程序 | 同步本次涉及的家庭页面文案微调，与 H5 行为对齐 | [miniprogram_family_status_v4_20260603_172108_70d6.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_family_status_v4_20260603_172108_70d6.zip) |

> ⚠️ H5 端无需用户下载，**刷新浏览器**即可获得最新代码；微信小程序需要重新导入压缩包到【微信开发者工具】体验。

---

## 使用说明

### 场景 1：邀请家人接受守护

1. 在【健康档案】或【家庭守护列表】页面，点击"+ 添加家人"按钮
2. 填写昵称、关系等信息，**注意**：本次治本起，**不允许在新增表单里直接指定守护人账号**——必须先建档，再单独走"邀请"流程
3. 创建档案后，在该成员卡片上点击"邀请守护"，扫描二维码或分享链接给对方
4. 对方接受邀请后，该成员卡片**才会出现绿色 ✓ 打勾**，标记为已绑定（status=bound）
5. 在对方接受之前，卡片不会打勾——这是本次治本的核心修复

### 场景 2：邀请过期、被拒绝、被取消

任一情况发生时：

- 对应的 FamilyMember 卡片会**自动从 bound 回滚为 unbound**，sub_status 标注为 `invited_expired` / `rejected` / `unbinded`
- 列表中的绿色 ✓ 立即消失，UI 与库状态保持一致
- 之前可能出现的"邀请已过期 24h，卡片还在显示已绑定"的问题彻底消失

### 场景 3：解除守护关系

1. 在【家庭守护列表】或成员详情页，点击"解除守护"
2. 系统会原子事务执行：
   - `FamilyManagement.status` 改为 `cancelled` / `cancelled_by_target`
   - `FamilyMember.status` 同步改为 `unbound`，`sub_status='unbinded'`
3. 卡片打勾立即消失，可点"重新邀请"

### 场景 4：尝试删除已绑定档案（被拦截）

1. 选中状态为"已绑定"的成员卡片，点击删除按钮
2. 系统返回提示：**"请先解除绑定关系再删除档案"**
3. 用户需要：
   - 先到守护列表点"解除守护"
   - 等卡片回滚为 unbound 状态后
   - 再次执行删除即可成功

> 此校验只在后端生效（前端列表里已绑定成员的删除按钮原本就是隐藏的），属于"双保险"。

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_family_status_v4_20260603_172108_70d6.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_family_status_v4_20260603_172108_70d6.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将 zip 解压到任意目录（建议路径不含中文/空格）
3. **下载微信开发者工具**（如尚未安装）：前往 [微信开发者工具官方下载页](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**：启动开发者工具，使用微信扫码登录
5. **导入项目**：
   - 点击首页【导入项目】
   - 在【目录】栏选择第 2 步解压后的文件夹
   - 【AppID】栏可填写项目 AppID，或选择【测试号】
   - 点击【导入】
6. **预览体验**：导入成功后，可在模拟器中进入"家庭健康档案"→"家人 Tab"页面体验本次的治本修复

---

## 注意事项

- **打勾判断**：UI 中"绿色 ✓ 已绑定"的判定从今天起**只看后端真实的 `status` 字段**，不再由前端反推。所以任何治本前残留的"假打勾"成员，刷新页面后会自动恢复正确状态。
- **数据迁移**：库里历史遗留的"status='bound' 但其实没有 active 守护关系"的脏成员，部署后可由运维通过 `backend/scripts/fix_fake_bound_20260603.py` 跑一次性回填脚本（先 `--dry-run` 查看报告，确认后 `--apply` 真改）。普通用户无需关心。
- **接口字段变更**：`/api/family/members` 接口已不再返回 `v3_main_status` / `v3_sub_status` 字段，前端如有依赖请直接读取同义的 `status` / `sub_status`。
- **预先存在的 baseline 用例**：`test_emergency_fix_member_tab_and_archive_consistent_for_removed/_deleted` 两条用例与本次治本无关，标记为 `xfail` 不影响本次发布。

---

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主入口（经 Nginx 80/443 代理） |
| 健康档案页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/) | 顶部成员 Tab + 健康档案展示 |
| 家庭守护列表 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-guardian-list/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-guardian-list/) | 我守护的人/守护我的人 列表 |
| 邀请扫码页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth/) | 扫描邀请二维码后的接受/拒绝页面 |
| 微信小程序包 | [miniprogram_family_status_v4_20260603_172108_70d6.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_family_status_v4_20260603_172108_70d6.zip) | 微信小程序代码压缩包，本次同步打包 |

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包：

> 📦 下载地址：[miniprogram_family_status_v4_20260603_172108_70d6.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_family_status_v4_20260603_172108_70d6.zip)

### 体验步骤

1. **下载压缩包**：点击上方链接，将 zip 压缩包下载到本地电脑
2. **解压文件**：将 zip 解压到任意目录
3. **打开微信开发者工具**：使用微信扫码登录
4. **导入项目**：选择解压后的文件夹，填写 AppID 或选"测试号"
5. **预览体验**：在模拟器中进入"家庭健康档案"→"家人 Tab"页面体验
