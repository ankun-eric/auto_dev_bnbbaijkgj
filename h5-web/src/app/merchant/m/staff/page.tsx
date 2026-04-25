'use client';

// [PRD V1.0 §M5 / §M6] 商家 H5 - 员工管理
// 字段：姓名 / 手机号 / 角色 / 所属门店（单门店时隐藏）
// 操作：查看权限（所有角色可见）；新增 / 重置密码（仅老板可见）；启停（老板+店长可见，老板不可被操作）
// 修复 Bug：仅在 POST /api/merchant/staff/toggle-status 200 后才更新 UI 状态，失败回退保持原状

import React, { useEffect, useMemo, useState } from 'react';
import {
  NavBar, List, Tag, Toast, Empty, Dialog, Switch, Button, Form, Input, Selector,
  Modal, Radio, TextArea,
} from 'antd-mobile';
import { useRouter } from 'next/navigation';
import api from '@/lib/api';
import { getProfile } from '../mobile-lib';
import { PASSWORD_REGEX, PASSWORD_HINT } from '@/lib/captcha';

const roleCodeLabel: Record<string, string> = {
  boss: '老板', manager: '店长', finance: '财务', clerk: '店员',
};
const memberRoleToCode: Record<string, string> = {
  owner: 'boss', store_manager: 'manager', finance: 'finance', verifier: 'clerk', staff: 'clerk',
};

const moduleLabel: Record<string, string> = {
  dashboard: '工作台', verify: '核销', records: '记录', messages: '消息',
  profile: '我的', finance: '财务对账', staff: '员工管理', settings: '门店设置',
};

interface StaffRow {
  user_id: number;
  phone: string;
  nickname?: string;
  member_role: string;
  role_code?: string;
  role_name?: string;
  store_ids: number[];
  status: string;
  module_codes?: string[];
}

export default function StaffMobilePage() {
  const router = useRouter();
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const [permVisible, setPermVisible] = useState(false);
  const [permTarget, setPermTarget] = useState<StaffRow | null>(null);

  const [createVisible, setCreateVisible] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm] = Form.useForm();

  const [resetVisible, setResetVisible] = useState(false);
  const [resetTarget, setResetTarget] = useState<StaffRow | null>(null);
  const [resetType, setResetType] = useState<'default' | 'custom'>('default');
  const [resetPwd, setResetPwd] = useState('');
  const [resetLoading, setResetLoading] = useState(false);

  const profile = getProfile();
  const isOwner = profile?.role === 'owner';
  const isManager = profile?.role === 'store_manager';
  const canToggle = isOwner || isManager;
  const myStores = profile?.stores || [];
  const isSingleStore = myStores.length <= 1;

  const storeNameMap = useMemo(() => {
    const m: Record<number, string> = {};
    myStores.forEach((s) => { m[s.id] = s.name; });
    return m;
  }, [myStores]);

  const load = async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/v1/staff');
      // 兼容返回 array 或 {items}
      const list: StaffRow[] = Array.isArray(res) ? res : (res?.items || []);
      setRows(list);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '加载失败' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const onToggle = async (row: StaffRow, to: boolean) => {
    const next = to ? 'active' : 'disabled';
    const isBossTarget = (row.role_code || memberRoleToCode[row.member_role]) === 'boss';
    if (isBossTarget) {
      Toast.show({ icon: 'fail', content: '不能启停老板账号' });
      return;
    }
    const ok = await Dialog.confirm({
      title: next === 'disabled' ? '确认停用？' : '确认启用？',
      content: next === 'disabled' ? '停用后该员工将无法登录商家工作台。' : undefined,
    });
    if (!ok) return;

    setTogglingId(row.user_id);
    try {
      await api.post('/api/merchant/staff/toggle-status', {
        target_user_id: row.user_id,
        status: next,
      });
      // 仅成功后更新本地 state，避免乐观更新被回滚
      setRows((prev) => prev.map((r) => (r.user_id === row.user_id ? { ...r, status: next } : r)));
      Toast.show({ icon: 'success', content: next === 'disabled' ? '已停用' : '已启用' });
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '操作失败' });
      // 失败：保持原状态（不更新 state）
    } finally {
      setTogglingId(null);
    }
  };

  const openPerm = (row: StaffRow) => {
    setPermTarget(row);
    setPermVisible(true);
  };

  const openCreate = () => {
    createForm.resetFields();
    setCreateVisible(true);
  };
  const submitCreate = async () => {
    try {
      const v = await createForm.validateFields();
      setCreateLoading(true);
      const payload: any = {
        name: v.name,
        phone: v.phone,
        role_code: Array.isArray(v.role_code) ? v.role_code[0] : v.role_code,
        store_ids: v.store_ids || [],
        remark: v.remark || undefined,
      };
      if (!payload.role_code) {
        Toast.show({ icon: 'fail', content: '请选择角色' });
        setCreateLoading(false);
        return;
      }
      if (!payload.store_ids.length) {
        Toast.show({ icon: 'fail', content: '请选择所属门店' });
        setCreateLoading(false);
        return;
      }
      const res: any = await api.post('/api/merchant/staff/create', payload);
      Toast.show({ icon: 'success', content: '创建成功' });
      Dialog.alert({ title: '员工创建成功', content: res?.message || '初始密码为手机号后 6 位' });
      setCreateVisible(false);
      load();
    } catch (e: any) {
      if (e?.errorFields) return;
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '创建失败' });
    } finally {
      setCreateLoading(false);
    }
  };

  const openReset = (row: StaffRow) => {
    setResetTarget(row);
    setResetType('default');
    setResetPwd('');
    setResetVisible(true);
  };
  const submitReset = async () => {
    if (!resetTarget) return;
    if (resetType === 'custom' && !PASSWORD_REGEX.test(resetPwd)) {
      Toast.show({ icon: 'fail', content: PASSWORD_HINT });
      return;
    }
    setResetLoading(true);
    try {
      await api.post('/api/merchant/staff/reset-password', {
        target_user_id: resetTarget.user_id,
        reset_type: resetType,
        new_password: resetType === 'custom' ? resetPwd : undefined,
      });
      const hint = resetType === 'default'
        ? `已重置为手机号后 6 位（${(resetTarget.phone || '').slice(-6)}）`
        : '已设为您输入的自定义密码';
      Dialog.alert({ title: '重置成功', content: `${hint}，请告知员工首次登录修改密码。` });
      setResetVisible(false);
    } catch (e: any) {
      Toast.show({ icon: 'fail', content: e?.response?.data?.detail || '重置失败' });
    } finally {
      setResetLoading(false);
    }
  };

  return (
    <div style={{ minHeight: '100vh', background: '#f7f8fa', paddingBottom: 24 }}>
      <NavBar
        onBack={() => router.back()}
        right={
          isOwner && (
            <span onClick={openCreate} style={{ color: '#52c41a', fontSize: 14 }}>
              + 新增
            </span>
          )
        }
      >
        员工管理
      </NavBar>

      <div style={{ padding: 12 }}>
        {rows.length === 0 ? (
          <Empty description={loading ? '加载中...' : '暂无员工'} />
        ) : (
          rows.map((s) => {
            const active = s.status === 'active';
            const rc = s.role_code || memberRoleToCode[s.member_role] || 'clerk';
            const isBossTarget = rc === 'boss';
            return (
              <div
                key={s.user_id}
                style={{
                  background: '#fff',
                  borderRadius: 10,
                  padding: 14,
                  marginBottom: 10,
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                  <div
                    style={{
                      width: 44,
                      height: 44,
                      borderRadius: '50%',
                      background: '#52c41a22',
                      color: '#52c41a',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      fontSize: 18,
                      fontWeight: 600,
                    }}
                  >
                    {(s.nickname || '员')[0]}
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontSize: 15, fontWeight: 600 }}>{s.nickname || '员工'}</div>
                    <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>
                      <Tag color="primary" fill="outline" style={{ marginRight: 6 }}>
                        {s.role_name || roleCodeLabel[rc] || rc}
                      </Tag>
                      {s.phone || ''}
                    </div>
                    {!isSingleStore && (
                      <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
                        {(s.store_ids || []).map((id) => storeNameMap[id] || `门店#${id}`).join('、') || '—'}
                      </div>
                    )}
                  </div>
                  {canToggle && !isBossTarget && (
                    <Switch
                      checked={active}
                      loading={togglingId === s.user_id}
                      onChange={(v) => onToggle(s, v)}
                    />
                  )}
                  {isBossTarget && <Tag color="warning">老板</Tag>}
                </div>
                <div style={{ marginTop: 10, display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <Button size="mini" fill="outline" onClick={() => openPerm(s)}>查看权限</Button>
                  {isOwner && !isBossTarget && (
                    <Button size="mini" fill="outline" color="primary" onClick={() => openReset(s)}>
                      重置密码
                    </Button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* 查看权限 */}
      <Modal
        visible={permVisible}
        onClose={() => setPermVisible(false)}
        closeOnMaskClick
        title={permTarget ? `${permTarget.nickname || permTarget.phone} 的权限` : '查看权限'}
        content={
          <div style={{ paddingTop: 8 }}>
            <div style={{ color: '#ad8b00', background: '#fffbe6', border: '1px solid #ffe58f', padding: 8, borderRadius: 6, fontSize: 12, marginBottom: 10 }}>
              角色权限由系统统一配置，此处仅可查看。
            </div>
            <div style={{ marginBottom: 8, fontSize: 13 }}>
              角色：<Tag color="primary">{permTarget?.role_name || roleCodeLabel[permTarget?.role_code || ''] || '—'}</Tag>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {(permTarget?.module_codes || []).length === 0 && (
                <span style={{ color: '#999', fontSize: 13 }}>暂无授权模块</span>
              )}
              {(permTarget?.module_codes || []).map((m) => (
                <Tag key={m} color="success">{moduleLabel[m] || m}</Tag>
              ))}
            </div>
          </div>
        }
        actions={[{ key: 'close', text: '关闭' }]}
        onAction={() => setPermVisible(false)}
      />

      {/* 新增员工 */}
      <Modal
        visible={createVisible}
        onClose={() => setCreateVisible(false)}
        showCloseButton
        title="新增员工"
        content={
          <Form form={createForm} layout="vertical" mode="card" style={{ background: 'transparent', marginTop: 8 }}>
            <Form.Item name="name" label="姓名" rules={[{ required: true, message: '请输入姓名' }]}>
              <Input placeholder="员工姓名" />
            </Form.Item>
            <Form.Item
              name="phone"
              label="手机号"
              rules={[
                { required: true, message: '请输入手机号' },
                { pattern: /^1\d{10}$/, message: '手机号格式错误' },
              ]}
            >
              <Input placeholder="员工手机号" type="tel" />
            </Form.Item>
            <Form.Item name="role_code" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
              <Selector
                columns={3}
                options={[
                  { label: '店长', value: 'manager' },
                  { label: '财务', value: 'finance' },
                  { label: '店员', value: 'clerk' },
                ]}
              />
            </Form.Item>
            <Form.Item name="store_ids" label="所属门店（可多选）" rules={[{ required: true, message: '请选择所属门店' }]}>
              <Selector
                multiple
                columns={2}
                options={myStores.map((s) => ({ label: s.name, value: s.id }))}
              />
            </Form.Item>
            <Form.Item name="remark" label="备注（可选）">
              <TextArea rows={2} maxLength={200} showCount placeholder="备注信息" />
            </Form.Item>
            <div style={{ color: '#999', fontSize: 12 }}>
              创建后初始密码为该员工手机号后 6 位，员工首次登录会被强制修改密码。
            </div>
          </Form>
        }
        actions={[
          { key: 'cancel', text: '取消' },
          { key: 'submit', text: createLoading ? '提交中...' : '创建', primary: true, disabled: createLoading },
        ]}
        onAction={(action) => {
          if (action.key === 'submit') submitCreate();
          else setCreateVisible(false);
        }}
      />

      {/* 重置密码 */}
      <Modal
        visible={resetVisible}
        onClose={() => setResetVisible(false)}
        showCloseButton
        title={resetTarget ? `重置 ${resetTarget.nickname || resetTarget.phone} 的密码` : '重置密码'}
        content={
          <div style={{ marginTop: 8 }}>
            <Radio.Group
              value={resetType}
              onChange={(v) => setResetType(v as any)}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                <Radio value="default">默认密码（手机号后 6 位）</Radio>
                <Radio value="custom">自定义密码</Radio>
              </div>
            </Radio.Group>
            {resetType === 'custom' && (
              <div style={{ marginTop: 12 }}>
                <Input
                  placeholder="请输入自定义密码"
                  type="password"
                  value={resetPwd}
                  onChange={setResetPwd}
                  clearable
                />
                <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>{PASSWORD_HINT}</div>
              </div>
            )}
            <div style={{ color: '#ad8b00', background: '#fffbe6', border: '1px solid #ffe58f', padding: 8, borderRadius: 6, fontSize: 12, marginTop: 12 }}>
              重置后该员工的所有登录会话将被注销，需用新密码重新登录，并强制修改密码。
            </div>
          </div>
        }
        actions={[
          { key: 'cancel', text: '取消' },
          { key: 'submit', text: resetLoading ? '提交中...' : '确定重置', primary: true, disabled: resetLoading },
        ]}
        onAction={(action) => {
          if (action.key === 'submit') submitReset();
          else setResetVisible(false);
        }}
      />
    </div>
  );
}
