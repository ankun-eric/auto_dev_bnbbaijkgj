# Bug 修复 V1 · 家庭成员状态与邀请按钮（用户体验手册）

> 发布日期：2026-06-03
> 范围：H5 + 微信小程序 + 后端
> 服务器：`https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27`

---

## 访问链接

以下是当前项目的体验链接,点击即可打开:

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口(80/443),请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主入口(H5) |
| 健康档案(本次修复重点页) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/) | Hero 卡邀请按钮配色修复 |
| 居家安全设备(本次修复重点页) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety/) | 顶部档案 Tab 状态文字优化 |
| 微信小程序下载(zip) | [miniprogram_bugfix_v1_20260603_152053_34d9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_bugfix_v1_20260603_152053_34d9.zip) | 解压后导入微信开发者工具体验 |

---

## 功能简介

本次修复一共解决了 **5 项问题** = **3 个历史小瑕疵**(零业务影响,顺手清理) + **2 个新发现的 UI 体验问题**:

| 序号 | 类型 | 问题简述 | 影响范围 |
|------|------|----------|----------|
| 1 | 旧瑕疵 | 新建家人卡片时 `sub_status` 写入为 NULL | 数据层(零业务影响) |
| 2 | 旧瑕疵 | 调度任务 2.4 回扫 SQL 引用了不存在的 `updated_at` 列 | 后端启动(零运行时影响) |
| 3 | 旧瑕疵 | 历史已存在的小型语法/Lint 告警 | 历史遗留 |
| 4 | 新 Bug | 居家设备安全页:顶部档案下方"已解绑"等冗余文字啰嗦 | H5(可见) |
| 5 | 新 Bug | 非本人档案 Hero 卡片:"邀请"按钮白底白字看不见 | H5 + 小程序(可见) |

---

## 本次客户端变更

本次更新涉及以下终端的代码改动,请下载/访问最新版本体验:

| 终端 | 变更说明 | 新版本入口 |
|------|----------|------------|
| H5(已部署) | 居家设备安全顶部档案 Tab 隐藏"已解绑"文字、改为右上角绿色 ✓ 角标;健康档案 Hero 卡邀请按钮改为橙色渐变 + 白字 | [打开 H5 首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) |
| 微信小程序 | 健康档案非本人档案下「邀请守护」按钮配色由蓝色改为橙色渐变 + 白字,与 H5 风格统一 | [miniprogram_bugfix_v1_20260603_152053_34d9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_bugfix_v1_20260603_152053_34d9.zip) |
| 后端 | `sub_status` 显式赋默认值;迁移 SQL 列名修复;新增 3 项回归测试 | 已随后端容器重启生效 |

> ⚠️ H5 端已经随 Docker 容器重新部署生效,刷新页面即可看到新效果。
> ⚠️ 微信小程序请重新下载 zip 包并导入开发者工具体验。
> ⚠️ 安卓/iOS 端本次未改动相关代码,可继续使用当前版本。

---

## 使用说明

### 体验 ① 居家设备安全 — 顶部档案 Tab 视觉优化

1. 登录 H5,进入「居家安全设备」页:[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety/)
2. 观察顶部家庭成员头像横排,**确认**:
   - 头像下方仅显示称谓(如「我 / 妻 / 友 / 添加」)
   - **不再显示** "已解绑/已绑定" 等小字状态
   - 已绑定的非本人头像 **右上角有绿色 ✓ 角标**(直径 14px,白色描边)
   - 已解绑/未绑定的成员头像右上角不显示角标
   - 本人头像不显示角标(本人无需绑定关系)

### 体验 ② 健康档案 — 非本人档案 Hero 邀请按钮配色

1. 登录 H5,进入「健康档案」页:[https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/)
2. 在顶部家庭成员 Tab 中切换到 **非本人 + 未绑定/未邀请** 的成员
3. 观察 Hero 卡片右上角的「邀请」按钮:
   - 背景:**橙色线性渐变** `#FF8A3D → #FF6B1A`
   - 文字:**白色 #FFFFFF**,清晰可见
   - 圆角胶囊形,带轻微橙色阴影,有质感
4. 点击「邀请」按钮,验证跳转/邀请逻辑正常

### 体验 ③ 后端数据自洽 — 新建家人 `sub_status` 不再为 NULL

1. 通过 H5 健康档案页 → 顶部「+ 添加」按钮 → 填写家人信息并保存
2. 后台 DB 中该行的 `sub_status` 字段会显式落入:
   - 直接绑定到已存在用户:`status='bound'` + `sub_status='bound'`
   - 仅创建档案(无关联用户):`status='unbound'` + `sub_status='not_applied'`
3. **不再依赖二次派生兜底**,数据自洽

> 已自动化覆盖:在容器内运行 `pytest tests/test_bugfix_v1_20260603.py -v`,本次新增 3 项回归测试全部通过(3 passed)。

### 体验 ④ 后端启动日志清洁 — 迁移 SQL 列名修复

1. 历史 `schema_sync.py` 中调度任务 2.4 回扫 SQL 引用了 `family_management.updated_at`,但该表实际只有 `created_at + cancelled_at`,SQL 会报"列不存在"告警。
2. 本次将引用替换为 `COALESCE(mg.cancelled_at, mg.created_at, NOW())`,保持时间语义一致。
3. 重启后端容器后,启动日志不再出现该告警。

---

## 微信小程序体验

### 下载小程序代码

点击以下链接下载微信小程序代码压缩包:

> 📦 下载地址:[miniprogram_bugfix_v1_20260603_152053_34d9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_bugfix_v1_20260603_152053_34d9.zip)

### 体验步骤

1. **下载压缩包**:点击上方链接,将 zip 压缩包下载到本地电脑
2. **解压文件**:将下载的 zip 文件解压到任意目录,记住解压后路径(通常含 `miniprogram/` 子目录)
3. **下载微信开发者工具**:如尚未安装,请前往 [微信开发者工具官方下载页面](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html) 下载并安装
4. **打开微信开发者工具**:启动工具,使用微信扫码登录
5. **导入项目**:
   - 点击「导入项目」(或「+」)
   - 「目录」栏选择第 2 步解压后的 `miniprogram/` 文件夹
   - 「AppID」栏填入项目 AppID 或选择「测试号」
   - 点击「导入」
6. **预览体验**:导入成功后,打开「健康档案」页 → 切换到非本人家庭成员 → 观察 Hero 卡下方「邀请守护」按钮已变为**橙色渐变 + 白字**配色

---

## 注意事项

1. **H5 端** 本次修改已经随 Docker 容器自动重新部署,刷新页面即可看到效果,无需用户做任何操作
2. **微信小程序端** 需要重新下载 zip 包导入开发者工具,旧版本仍是蓝色按钮
3. **安卓 / iOS 端** 本次未改动客户端代码,无需更新
4. **数据兼容**:本次后端改动仅影响新建数据的初始 `sub_status` 字段,**对历史数据零影响**(derive 逻辑仍兜底)
5. **已部署验证**:
   - 后端 `/api/health` 健康检查:HTTP 200 ✓
   - H5 `/health-profile/`:HTTP 200 ✓
   - H5 `/home-safety/`:HTTP 200 ✓
   - 微信小程序 zip 下载:HTTP 200 ✓
   - 本次新增 3 项回归测试在容器内全部通过 ✓

---

## 访问链接

以下是当前项目的体验链接,点击即可打开:

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口(80/443),请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| H5 首页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 项目主入口(H5) |
| 健康档案(本次修复重点页) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/health-profile/) | Hero 卡邀请按钮配色修复 |
| 居家安全设备(本次修复重点页) | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/home-safety/) | 顶部档案 Tab 状态文字优化 |
| 微信小程序下载(zip) | [miniprogram_bugfix_v1_20260603_152053_34d9.zip](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/downloads/miniprogram_bugfix_v1_20260603_152053_34d9.zip) | 解压后导入微信开发者工具体验 |
