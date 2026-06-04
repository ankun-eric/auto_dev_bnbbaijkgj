# Bug修复：新建咨询人后邀请提示「家庭成员不存在或不属于当前用户」

> 版本：v1（2026-06-04）
> 目标：修复 V3 状态机迁移后，`FamilyMember.status` 从 `active/removed/deleted` 改为 `bound/unbound/deleted`，导致部分接口仍用旧枚举值查询导致的 Bug。

---

## Bug 现象

用户操作路径：
1. AI首页左下角 → 点击「+ 新增咨询人」
2. 填写姓名/关系等信息 → 保存成功
3. 系统提示「是否邀请对方」→ 点击「是」
4. 弹出错误：「家庭成员不存在或不属于当前用户」

**正常预期**：应该弹出邀请二维码。

---

## 根因分析

POST `/api/family/invitation`（创建邀请）接口在查询 `FamilyMember` 时硬编码了 `status == "bound"`，但 POST `/api/family/members`（新建成员）接口在 V3 修复中将新建成员的 status 从 `"bound"` 改为了 `"unbound"`。

V3 状态机枚举值变更：
| 旧枚举 | 新枚举 | 含义 |
|--------|--------|------|
| active | bound | 守护关系生效中（邀请被接受后） |
| - | unbound | 未绑定/已解绑（新建成员的初始状态） |
| removed / deleted | deleted | 卡片已软删除 |

---

## 修复方案

### 修改点 1：`family_management.py` - `create_invitation` 接口

**状态**：✅ 已完成（第 115 行）

将查询条件从 `FamilyMember.status == "bound"` 改为 `FamilyMember.status.notin_(["deleted", "removed"])`，只排除已软删除的记录，不再限定 bound 状态。

### 修改点 2：`family_management.py` - `accept_invitation` 接口 existing_count

**状态**：✅ 已完成（第 466 行）

将 `existing_count` 的计数条件从 `FamilyMember.status == "bound"` 改为 `FamilyMember.status.notin_(["deleted", "removed"])`，确保颜色索引计算不受 V3 状态机影响。

### 修改点 3：`family.py` - `add_family_member` 接口 avatar_color_index 计数

**状态**：🔧 本次修复（第 222 行）

原代码：
```python
count_res = await db.execute(
    select(func.count(FamilyMember.id)).where(
        FamilyMember.user_id == current_user.id,
        FamilyMember.status == "bound",
    )
)
```

修复后：
```python
count_res = await db.execute(
    select(func.count(FamilyMember.id)).where(
        FamilyMember.user_id == current_user.id,
        FamilyMember.status.notin_(["deleted", "removed"]),
    )
)
```

**说明**：新建成员的 status 已改为 `"unbound"`，此处的颜色索引计数应基于所有非删除成员，而非仅限 bound 状态，否则会导致颜色分配错位。

### `family.py` - `send_sos` 接口（第 417 行）

**状态**：✅ 无需修改

该接口使用 `status == "bound"` 查询已绑定守护成员以发送 SOS 通知。在 V3 状态机中，`bound` 仍正确表示「守护关系生效中」，业务语义无误。
SOS 不应发给未绑定（unbound）的成员，当前逻辑符合业务预期。

---

## 涉及文件

| 文件 | 修改内容 | 状态 |
|------|----------|------|
| `backend/app/api/family_management.py` | 第115行 create_invitation 查询条件 | ✅ 已完成 |
| `backend/app/api/family_management.py` | 第466行 accept_invitation existing_count | ✅ 已完成 |
| `backend/app/api/family.py` | 第222行 add_family_member existing_count | 🔧 本次修复 |
| `backend/app/api/family.py` | 第417行 send_sos 查询 | ✅ 无需修改（业务正确） |

---

## 验证步骤

1. 打开 H5 主页，点击「+ 新增咨询人」
2. 填写姓名和关系，保存
3. 系统提示「是否邀请对方」，点击「是」
4. **预期**：弹出邀请二维码页，不再出现「家庭成员不存在或不属于当前用户」错误
5. 检查新建成员的 avatar 颜色是否正确轮换

---

## 访问链接

| 服务 | 链接 |
|------|------|
| H5 主页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/) |
| 邀请扫码页 | [https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth/](https://newbb.test.bangbangvip.com/autodev/6b099ed3-7175-4a78-91f4-44570c84ed27/family-auth/) |
