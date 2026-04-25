'use client';

// [PRD V1.0 §M5 / §M6] 商家 PC 端 - 员工管理
// - 列表：姓名 / 手机号 / 角色 / 所属门店 / 状态 / 操作
// - 操作列：查看权限（所有角色可见，只读）+ 重置密码（仅老板可见）+ 启停（老板/店长可见，老板不可被操作）
// - 新增员工：仅老板可见
// - 启停：仅 POST /api/merchant/staff/toggle-status 200 后才更新本地 state，避免回滚

import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert, Button, Card, Checkbox, DatePicker, Form, Input, Modal, Radio, Select,
  Space, Table, Tag, Typography, message,
} from 'antd';
import api from '@/lib/api';
import { getProfile } from '../lib';
import { PASSWORD_REGEX, PASSWORD_HINT } from '@/lib/captcha';
import dayjs from 'dayjs';

const { Title } = Typography;

const roleCodeLabel: Record<string, string> = {
  boss: '老板', manager: '店长', finance: '财务', clerk: '店员',
};
const memberRoleToCode: Record<string, string> = {
  owner: 'boss', store_manager: 'manager', finance: 'finance', verifier: 'clerk', staff: 'clerk',
};

const moduleOptions = [
  { label: '工作台', value: 'dashboard' },
  { label: '核销', value: 'verify' },
  { label: '记录', value: 'records' },
  { label: '消息', value: 'messages' },
  { label: '我的', value: 'profile' },
  { label: '财务对账', value: 'finance' },
  { label: '员工管理', value: 'staff' },
  { label: '门店设置', value: 'settings' },
];

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

export default function StaffPage() {
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [permOpen, setPermOpen] = useState(false);
  const [permTarget, setPermTarget] = useState<StaffRow | null>(null);
  const [createOpen, setCreateOpen] = useState(false);
  const [createLoading, setCreateLoading] = useState(false);
  const [createForm] = Form.useForm();
  const [resetOpen, setResetOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<StaffRow | null>(null);
  const [resetType, setResetType] = useState<'default' | 'custom'>('default');
  const [resetCustomPwd, setResetCustomPwd] = useState('');
  const [resetLoading, setResetLoading] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);

  const profile = useMemo(() => getProfile(), []);
  const isOwner = profile?.role === 'owner';
  const isManager = profile?.role === 'store_manager';
  const canToggle = isOwner || isManager; // 启停按钮可见

  const myStores = useMemo(() => profile?.stores || [], [profile]);

  const fetchList = () => {
    setLoading(true);
    api
      .get<StaffRow[], StaffRow[]>('/api/merchant/v1/staff')
      .then((d) => setRows(d || []))
      .catch((e: any) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchList();
  }, []);

  // ==================== 查看权限（只读） ====================
  const openPerm = (row: StaffRow) => {
    setPermTarget(row);
    setPermOpen(true);
  };

  // ==================== 启停（仅成功后更新本地 state） ====================
  const toggleStatus = (row: StaffRow) => {
    const next = row.status === 'active' ? 'disabled' : 'active';
    const isOwnerTarget = (row.role_code || memberRoleToCode[row.member_role]) === 'boss';
    if (isOwnerTarget) {
      message.warning('不能启停老板账号');
      return;
    }
    Modal.confirm({
      title: next === 'disabled' ? '确认停用该员工？' : '确认启用该员工？',
      content: next === 'disabled' ? '停用后该员工将无法登录商家工作台。' : undefined,
      onOk: async () => {
        setTogglingId(row.user_id);
        try {
          await api.post('/api/merchant/staff/toggle-status', {
            target_user_id: row.user_id,
            status: next,
          });
          message.success('状态已更新');
          // 仅成功后更新本地 state，避免乐观更新被回滚
          setRows((prev) => prev.map((r) => (r.user_id === row.user_id ? { ...r, status: next } : r)));
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '操作失败');
        } finally {
          setTogglingId(null);
        }
      },
    });
  };

  // ==================== 新增员工 ====================
  const openCreate = () => {
    createForm.resetFields();
    setCreateOpen(true);
  };
  const submitCreate = async () => {
    try {
      const v = await createForm.validateFields();
      setCreateLoading(true);
      const payload: any = {
        name: v.name,
        phone: v.phone,
        role_code: v.role_code,
        store_ids: v.store_ids,
        avatar: v.avatar || undefined,
        hire_date: v.hire_date ? dayjs(v.hire_date).format('YYYY-MM-DD') : undefined,
        remark: v.remark || undefined,
      };
      const res: any = await api.post('/api/merchant/staff/create', payload);
      message.success(res?.message || '员工创建成功');
      setCreateOpen(false);
      fetchList();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '创建失败');
    } finally {
      setCreateLoading(false);
    }
  };

  // ==================== 重置密码 ====================
  const openReset = (row: StaffRow) => {
    setResetTarget(row);
    setResetType('default');
    setResetCustomPwd('');
    setResetOpen(true);
  };
  const submitReset = async () => {
    if (!resetTarget) return;
    if (resetType === 'custom') {
      if (!PASSWORD_REGEX.test(resetCustomPwd)) {
        message.error(PASSWORD_HINT);
        return;
      }
    }
    setResetLoading(true);
    try {
      const res: any = await api.post('/api/merchant/staff/reset-password', {
        target_user_id: resetTarget.user_id,
        reset_type: resetType,
        new_password: resetType === 'custom' ? resetCustomPwd : undefined,
      });
      const hint = resetType === 'default'
        ? `已重置为手机号后 6 位（${(resetTarget.phone || '').slice(-6)}），请告知员工首次登录修改密码。`
        : '已设为您输入的自定义密码，请安全告知员工。';
      Modal.success({ title: '重置成功', content: res?.message ? `${res.message}。${hint}` : hint });
      setResetOpen(false);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '重置失败');
    } finally {
      setResetLoading(false);
    }
  };

  // ==================== 表格 ====================
  const storeNameMap = useMemo(() => {
    const m: Record<number, string> = {};
    myStores.forEach((s) => { m[s.id] = s.name; });
    return m;
  }, [myStores]);

  const columns = [
    { title: '姓名', dataIndex: 'nickname', render: (v: string) => v || '—' },
    { title: '手机号', dataIndex: 'phone' },
    {
      title: '角色',
      render: (_: any, row: StaffRow) => (
        <Tag color="purple">
          {row.role_name || roleCodeLabel[row.role_code || memberRoleToCode[row.member_role] || ''] || row.member_role}
        </Tag>
      ),
    },
    {
      title: '所属门店',
      dataIndex: 'store_ids',
      render: (v: number[]) => (
        <Space wrap size={4}>
          {(v || []).map((id) => (
            <Tag key={id} color="green">{storeNameMap[id] || `门店#${id}`}</Tag>
          ))}
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作',
      key: 'op',
      render: (_: any, row: StaffRow) => {
        const rc = row.role_code || memberRoleToCode[row.member_role];
        const isBossTarget = rc === 'boss';
        return (
          <Space>
            <Button type="link" onClick={() => openPerm(row)}>查看权限</Button>
            {isOwner && !isBossTarget && (
              <Button type="link" onClick={() => openReset(row)}>重置密码</Button>
            )}
            {canToggle && !isBossTarget && (
              <Button
                type="link"
                danger={row.status === 'active'}
                loading={togglingId === row.user_id}
                onClick={() => toggleStatus(row)}
              >
                {row.status === 'active' ? '停用' : '启用'}
              </Button>
            )}
            {isBossTarget && <Tag>老板账号</Tag>}
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>员工管理</Title>
        {isOwner && (
          <Button type="primary" onClick={openCreate}>+ 新增员工</Button>
        )}
      </div>
      <Alert
        type="info"
        showIcon
        style={{ margin: '16px 0' }}
        message={isOwner
          ? '老板可新增员工、查看权限、重置员工密码、启停员工。角色权限由系统统一配置，不可在此修改。'
          : (isManager
            ? '店长可启停所辖门店的财务/店员账号；新增/重置密码请联系老板。'
            : '本页仅供查看。员工的增删改与权限调整由老板/店长负责。')}
      />
      <Card>
        <Table
          rowKey="user_id"
          loading={loading}
          dataSource={rows}
          pagination={false}
          columns={columns as any}
        />
      </Card>

      {/* 查看权限（只读） */}
      <Modal
        title={permTarget ? `查看 ${permTarget.nickname || permTarget.phone} 的模块权限` : '查看权限'}
        open={permOpen}
        onCancel={() => setPermOpen(false)}
        footer={<Button onClick={() => setPermOpen(false)}>关闭</Button>}
      >
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 12 }}
          message="角色权限由系统统一配置，此处仅可查看。"
        />
        <div style={{ marginBottom: 8, color: '#666' }}>
          角色：<Tag color="purple">{permTarget?.role_name || roleCodeLabel[permTarget?.role_code || ''] || '—'}</Tag>
        </div>
        <Checkbox.Group
          options={moduleOptions}
          value={permTarget?.module_codes || []}
          disabled
          style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}
        />
      </Modal>

      {/* 新增员工 */}
      <Modal
        title="新增员工"
        open={createOpen}
        onCancel={() => setCreateOpen(false)}
        onOk={submitCreate}
        confirmLoading={createLoading}
        okText="创建"
        width={520}
      >
        <Form form={createForm} layout="vertical" preserve={false}>
          <Form.Item
            name="name"
            label="姓名"
            rules={[{ required: true, message: '请输入姓名' }, { max: 50, message: '不超过 50 字' }]}
          >
            <Input placeholder="请输入员工姓名" />
          </Form.Item>
          <Form.Item
            name="phone"
            label="手机号"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '手机号格式错误' },
            ]}
          >
            <Input placeholder="请输入员工手机号" />
          </Form.Item>
          <Form.Item
            name="role_code"
            label="角色"
            rules={[{ required: true, message: '请选择角色' }]}
          >
            <Select
              options={[
                { label: '店长', value: 'manager' },
                { label: '财务', value: 'finance' },
                { label: '店员', value: 'clerk' },
              ]}
              placeholder="请选择角色"
            />
          </Form.Item>
          <Form.Item
            name="store_ids"
            label="所属门店"
            rules={[{ required: true, message: '请选择所属门店（可多选）' }]}
          >
            <Select
              mode="multiple"
              options={myStores.map((s) => ({ label: s.name, value: s.id }))}
              placeholder="请选择所属门店（可多选）"
            />
          </Form.Item>
          <Form.Item name="avatar" label="头像 URL（可选）">
            <Input placeholder="可粘贴员工头像图片链接" />
          </Form.Item>
          <Form.Item name="hire_date" label="入职日期（可选）">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="remark" label="备注（可选）" rules={[{ max: 200, message: '不超过 200 字' }]}>
            <Input.TextArea rows={3} maxLength={200} showCount placeholder="备注信息" />
          </Form.Item>
          <div style={{ color: '#999', fontSize: 12 }}>
            创建成功后，初始密码为该员工手机号的后 6 位，员工首次登录会被强制修改密码。
          </div>
        </Form>
      </Modal>

      {/* 重置密码 */}
      <Modal
        title={resetTarget ? `重置 ${resetTarget.nickname || resetTarget.phone} 的密码` : '重置密码'}
        open={resetOpen}
        onCancel={() => setResetOpen(false)}
        onOk={submitReset}
        confirmLoading={resetLoading}
        okText="确定重置"
      >
        <Radio.Group
          value={resetType}
          onChange={(e) => setResetType(e.target.value)}
          style={{ display: 'flex', flexDirection: 'column', gap: 8 }}
        >
          <Radio value="default">
            重置为默认密码（手机号后 6 位）
          </Radio>
          <Radio value="custom">
            自定义密码
          </Radio>
        </Radio.Group>
        {resetType === 'custom' && (
          <div style={{ marginTop: 12 }}>
            <Input.Password
              placeholder="请输入自定义密码"
              value={resetCustomPwd}
              onChange={(e) => setResetCustomPwd(e.target.value)}
            />
            <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>{PASSWORD_HINT}</div>
          </div>
        )}
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 12 }}
          message="重置后该员工的所有登录会话将被注销，需用新密码重新登录，并强制修改密码。"
        />
      </Modal>
    </div>
  );
}
