# 用户体验使用手册 — 支付宝 H5 测试连接 Bug 修复

> 部署 ID: `6b099ed3-7175-4a78-91f4-44570c84ed27`
> 部署日期: 2026-05-05
> 适用角色: 平台超级管理员（管理后台）

---

## 一、本次修复解决了什么问题

### Bug ① — "字段 app_private_key 解密后为空"

**修复前**：在管理后台首次配置支付宝 H5（或微信支付）通道时，把"应用私钥 / API V3 Key"等敏感字段填好后点击"保存"，再点"测试连接"，会弹出红色错误：

```
测试失败：自检失败：字段 app_private_key 解密后为空
```

**根因**：前端没把敏感字段标成必填；后端把"留空"当成"保留旧值"。但**首次保存时数据库里根本没有旧值**，导致私钥被静默丢弃，看似保存成功，实际未落库。

**修复后**：
- 首次配置该通道时，应用私钥/V3 Key 等敏感字段会有红色 `*` 必填标记。
- 抽屉顶部 Alert 文案变成 `首次配置：敏感字段（如应用私钥/V3 Key）必须填写完整...`。
- 如果你绕过前端用接口直接 PUT 一个空敏感字段，后端会返回 **HTTP 422** 并提示：
  `字段「应用私钥」是首次创建场景下的必填项，不能为空`

### Bug ② — "未安装 python-alipay-sdk，无法发起真实支付宝调用"

**修复前**：把 Bug ① 的提示解决掉、私钥确实存进去了之后，再点"测试连接"，会变成新的报错：

```
测试失败：调用支付宝异常：未安装 python-alipay-sdk，无法发起真实支付宝调用；
请在 backend 容器中安装：pip install python-alipay-sdk
```

**根因 1**：后端 `requirements.txt` 已加了 `python-alipay-sdk==3.3.0`，但服务器上沿用了旧 docker 镜像缓存，新依赖没装进去。

**根因 2**（修复过程中追加发现）：代码 `from alipay import AliPay, AliPayCert` 中 `AliPayCert` 在 `python-alipay-sdk 3.3.0` 中并不存在，触发 ImportError，被错误识别成"SDK 未安装"。

**修复后**：
- 用 `docker compose build --no-cache backend` 强制重装依赖，容器内 `python-alipay-sdk 3.3.0` 已就位。
- 公钥模式不再依赖 `AliPayCert`，证书模式则按 4.x 命名 + 3.x 兜底两条路径兼容。
- 测试连接现在会真实发起对支付宝网关的调用。

### 附带改进：解密错因更精准

如果将来你/运维同学**改了 `PAYMENT_CONFIG_ENCRYPTION_KEY` 环境变量**导致旧密文解不开，"测试连接"的报错会明确写：
`解密失败，可能是 PAYMENT_CONFIG_ENCRYPTION_KEY 被更换过，无法解开旧密文：xxxx`

而不是和"数据库里数据为空"混淆。

---

## 二、访问入口

| 页面 | 链接 | 说明 |
| --- | --- | --- |
| 管理后台登录 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login | 平台超级管理员登录 |
| 支付配置页 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/payment-config | 管理支付通道（支付宝 H5、微信支付等） |
| H5 用户端 | https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/ | 终端用户购买/支付入口 |

测试账号：管理员 `13800000000 / admin123`

---

## 三、操作步骤（首次配置支付宝 H5）

> 重点：**首次保存时，应用私钥、支付宝公钥（或证书三件套）必须填完整**。

### 3.1 进入页面
1. 浏览器打开 [管理后台登录](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/admin/login)。
2. 登录后左侧菜单 → "支付配置"。
3. 在通道列表中找到 `支付宝H5支付` 这一行 → 点 "编辑"。

### 3.2 填写参数（公钥模式）
| 字段 | 必填 | 备注 |
| --- | --- | --- |
| 应用 ID（app_id） | 是 | 16 位以 2021/2099 开头 |
| 接入方式 | 是 | 选 "公钥模式（alipay_public_key）" |
| **应用私钥（app_private_key）** | **是（首次配置）** | 从支付宝控制台「开发助手」生成的 RSA2 私钥，PEM 格式 |
| **支付宝公钥（alipay_public_key）** | **是（首次配置）** | 控制台「应用 → 开发设置 → 接口加签方式」复制 |

> 💡 抽屉顶部如果显示 ⚠️ 黄色 Alert "首次配置..."，说明系统检测到你正在**初次创建**该通道——此时所有敏感字段都强制必填。
> 后续编辑时，敏感字段会显示成 `****xxxx` 掩码，留空表示**保留旧值**，这是正常行为。

### 3.3 保存 → 测试
1. 点底部 "保存"。
2. 列表中该通道的 `配置完整` 列变为 ✅。
3. 点同一行的 "测试" 按钮。
4. 等待 1~3 秒，弹出绿色 Toast `测试成功`，表示打通支付宝网关无误。

### 3.4 常见报错与解读（修复后版本）

| 红色提示 | 含义 | 处理方法 |
| --- | --- | --- |
| `字段「应用私钥」是首次创建场景下的必填项` | 你提交的 payload 该字段为空 | 重新填写并保存 |
| `字段 app_private_key 在数据库中不存在或为空` | 数据库里这条没存进去（理论上修复后不再出现） | 重新走一次 3.2 |
| `解密失败，可能是 PAYMENT_CONFIG_ENCRYPTION_KEY 被更换过` | 加密密钥被运维换过，旧密文解不开 | 联系运维核对 `.env`，或把所有敏感字段重新填一遍并保存 |
| `调用支付宝异常：RSA key format is not supported` | 私钥不是合法的 RSA2 PEM | 用合法的 PKCS8 私钥重填 |
| `调用支付宝异常：xxxx`（其他业务错误） | 调用确实发出去了但被支付宝拒绝 | 按提示中的 sub_code 查支付宝官方文档 |

---

## 四、回归验证（已自动化跑过）

### 4.1 容器内冒烟测试（8/8 PASS）
- ✅ `DecryptionError` 类已部署
- ✅ `decrypt_value(raise_on_error=True)` 正确抛 `DecryptionError`
- ✅ 默认行为返回 "" 向后兼容
- ✅ 加解密往返正常
- ✅ `python-alipay-sdk` 已安装到容器
- ✅ `alipay_service._build_client_from_config` 可导入
- ✅ `payment_config` / `ENC_PREFIX` 模块正常
- ✅ `app_private_key` 为必填敏感字段

### 4.2 端到端 API 测试
- ✅ `/api/health` 返回 200
- ✅ admin 登录获取 token 正常
- ✅ 编辑场景下空敏感字段保留旧值（向后兼容）
- ✅ 测试连接接口不再返回"未安装 python-alipay-sdk"
- ✅ 测试连接接口现在能真正调到支付宝网关（返回具体业务错误如 RSA key format）

---

## 五、变更文件清单

| 类型 | 文件 |
| --- | --- |
| 后端 | `backend/app/utils/crypto.py`（新增 `DecryptionError`、`raise_on_error` 参数） |
| 后端 | `backend/app/api/payment_config.py`（首次创建强校验 422、解密错因区分、SDK 未装明确文案） |
| 后端 | `backend/app/services/alipay_service.py`（去掉对 `AliPayCert` 的硬依赖、4.x/3.x 双兼容） |
| 后端 | `backend/requirements.txt`（已含 `python-alipay-sdk==3.3.0`，本次重新构建生效） |
| 前端 | `admin-web/src/app/(admin)/payment-config/page.tsx`（`isFirstTime` 状态 + 条件 required + 顶部 Alert） |
| 测试 | `backend/tests/test_payment_config_first_time_secret.py`（8 个用例） |

---

## 六、回滚方案

如线上出现意外，可在服务器执行：

```bash
ssh ubuntu@newbb.test.bangbangvip.com
cd ~/auto_output/bnbbaijkgj
git log --oneline -5
git checkout 5c4bd60  # 修复前的 commit
docker compose -f docker-compose.prod.yml build --no-cache backend admin-web
docker compose -f docker-compose.prod.yml up -d backend admin-web
```

回滚后行为退回到 Bug 修复前的"silent discard"。
