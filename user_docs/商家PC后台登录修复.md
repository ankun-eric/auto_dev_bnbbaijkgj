# 商家 PC 后台登录修复 · 用户体验使用手册

本次更新修复了一个会导致**商家 PC 后台完全无法使用**的严重问题：用户明明在登录页输入了正确的手机号和密码，系统也提示"登录成功"，但页面跳转到工作台之后**立刻被踢回登录页**，无法进入后台任何功能模块。本次修复后，该问题彻底解决，商家 PC 后台全部 8 大模块（工作台、订单、核销、对账、报表、员工、门店设置、消息等）均可正常使用。

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端主页（C 端用户入口） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 经 Nginx 代理（HTTPS/443） |
| 商家 PC 后台登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login) | 本次修复的核心入口 |
| 商家 PC 工作台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard) | 登录后自动跳转进入此页（单门店账号） |
| 多门店选择页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/select-store](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/select-store) | 多门店账号登录后会先跳转到此页选门店 |
| 平台管理后台（Admin） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login) | 平台管理员在此创建/管理商家账号 |

## 功能简介

### 本次修复了什么

**现象**：商家在 PC 后台登录页输入正确的账号密码，系统提示"登录成功"后跳转到工作台 `/merchant/dashboard`，但页面会在短暂闪现 1 秒后被强制踢回登录页，并提示「无效的认证凭证」。所有商家账号、所有角色（老板 / 店长 / 核销员 / 财务 / 店员）100% 必现。

**原因**：商家 PC 后台登录接口在签发登录凭证（JWT token）时，把用户编号写成了数字类型，而 JWT 规范要求该字段必须是字符串。结果是：登录接口本身可以成功返回 token，但紧接着的任何一个需要鉴权的后续接口（比如工作台数据接口）在校验这个 token 时都会直接拒绝，返回 401「无效的认证凭证」，前端的拦截器捕获 401 后就把用户踢回登录页。

**修复**：将 token 签发时的用户编号字段统一改为字符串形式，并在签发工具函数中加了一层防御性自动转换，未来任何新加的登录入口都不会再踩这个坑；同时在 token 解码环节增加了详细日志，便于未来快速定位类似问题。

### 本次影响范围

- **会变好**：商家 PC 后台从"完全不可用"恢复为"完全可用"，所有商家侧角色均可正常登录使用全部 8 大模块
- **不受影响**：C 端用户小程序 / H5、商家移动端 H5、平台 Admin 后台登录链路都未受本次改动影响，行为与修复前一致

## 使用说明

### 场景一：老板 / 店长 / 核销员 / 财务 / 店员 登录商家 PC 后台

1. **打开登录页**：浏览器访问 [商家 PC 后台登录页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login)

2. **输入账号密码**：
   - 在"手机号"输入框中填入由平台管理员在 Admin 后台为您创建的商家账号手机号
   - 在"密码"输入框中填入对应的登录密码
   - 点击【登录】按钮

3. **进入工作台**：
   - **单门店账号**：登录成功后会直接跳转到[工作台首页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard)，展示今日订单数、今日核销数、本月 GMV、待结算金额、待审核附件、未读消息等关键指标
   - **多门店账号**：登录成功后会先跳转到[门店选择页](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/select-store)，选择您要进入的门店后再进入该门店的工作台

4. **使用其它模块**：从工作台左侧菜单可以进入订单管理、核销记录、对账单、报表、员工管理、门店设置、消息中心等 8 大模块，各模块菜单项会根据您的角色权限自动显示/隐藏。

### 场景二：用短信验证码登录

当您忘记密码或需要临时登录时，可使用短信验证码登录方式：

1. 在登录页切换到"短信验证码登录"模式
2. 输入手机号，点击"获取验证码"
3. 当前测试环境万能验证码为 **8888**（正式环境请使用实际收到的短信验证码）
4. 点击【登录】即可

### 场景三：切换门店

多门店账号在进入某个门店的工作台后，可随时通过顶部导航返回"选择门店"页切换到其它门店。

## 注意事项

### 1. 商家账号的创建渠道

商家 PC 后台的账号**必须由平台管理员在 Admin 后台「商家/门店/员工管理」模块中创建**，创建时会自动完成以下三项绑定，缺一不可：

- 创建 `User`（用户本身）
- 为该用户添加 `merchant_owner` 或 `merchant_staff` 身份（`AccountIdentity`）
- 为该用户添加一个或多个门店的成员关系（`MerchantStoreMembership`）

如果缺少身份绑定，登录时后端会返回 **403「非商家账号，无法登录商家后台」**；如果缺少门店成员关系，登录时后端会返回 **403「您还未被绑定到任何门店，请联系平台客服」**。这两类报错都是**业务规则拦截**，不是 token 故障，不要与本次修复的 Bug 混淆。

### 2. 修复不需要用户端做任何操作

本次修复完全在后端完成，**前端、H5、小程序、APP 代码均未发生变更**，用户侧无需执行以下任何操作：

- ❌ 不需要清浏览器缓存
- ❌ 不需要重新安装 APP
- ❌ 不需要重新导入小程序包
- ✅ 修复上线后，直接打开登录页输入账号密码即可

### 3. 如果登录后仍被踢回登录页

理论上本次修复已覆盖所有场景，但如遇到异常请按以下顺序排查：

1. 确认使用的是**由平台管理员在 Admin 后台创建的商家账号**，而不是 C 端用户账号
2. 确认账号处于 active 状态，未被平台管理员禁用
3. 确认账号至少被绑定到一个有效门店
4. 如果浏览器里仍有历史缓存的损坏 token，可手动清一次浏览器的 localStorage 后重新登录
5. 以上仍无法解决的，请联系平台客服提供手机号和浏览器控制台的 Network 截图，便于快速定位

### 4. 与「商家 H5 移动端登录跳转 Bug」的区别

本次修复的是**商家 PC 后台（电脑浏览器大屏版）** 的后端鉴权问题，修复点在后端 `merchant_v1.py` 和 `security.py`。

此前修复的「商家端 H5 移动端登录后跳到 C 端登录页」Bug 位于前端路由层，修复点在 `merchant/m/layout` 和前端 axios 拦截器，与本次修复**不是同一个问题**。两者虽都表现为"登录后被踢"，但根因和修改点完全不同，且两套修复彼此独立、互不影响。

## 验收要点

用户验收本次修复可参照以下检查表：

| 项 | 验收方法 | 预期结果 |
|----|---------|---------|
| 老板账号登录 | 用 owner 账号在 PC 登录 | 进入工作台，能看到工作台指标 |
| 店长账号登录 | 用 store_manager 账号登录 | 进入工作台，菜单按角色正常显示 |
| 核销员账号登录 | 用 verifier 账号登录 | 进入工作台，仅看到受限菜单 |
| 财务账号登录 | 用 finance 账号登录 | 进入工作台，看到对账/发票模块 |
| 店员账号登录 | 用 staff 账号登录 | 进入工作台，仅看到受限菜单 |
| 多门店账号 | 用有多个门店的账号登录 | 先跳选门店页，选完进工作台 |
| 单门店账号 | 用单门店账号登录 | 直接进工作台 |
| 刷新页面 | 登录后刷新浏览器 | 保持登录态，不掉线 |
| 切换路由 | 从工作台跳订单/核销/对账等 | 全部返回 200，鉴权通过 |
| 错误密码 | 输入错误密码 | 返回"账号不存在或密码错误"（登录层拦截，不是 token 层） |

## 访问链接

以下是当前项目的体验链接，点击即可打开：

> ⚠️ 所有链接均使用宿主机 Nginx 代理端口（80/443），请勿使用 Docker 容器内部端口。

| 服务 | 链接 | 说明 |
|------|------|------|
| 前端主页（C 端用户入口） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) | 经 Nginx 代理（HTTPS/443） |
| 商家 PC 后台登录页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/login) | 本次修复的核心入口 |
| 商家 PC 工作台 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/dashboard) | 登录后自动跳转进入此页（单门店账号） |
| 多门店选择页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/select-store](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/merchant/select-store) | 多门店账号登录后会先跳转到此页选门店 |
| 平台管理后台（Admin） | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login) | 平台管理员在此创建/管理商家账号 |
