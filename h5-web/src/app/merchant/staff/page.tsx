'use client';

import React, { useEffect, useMemo, useState } from 'react';
import { Table, Typography, Tag, Alert, Button, Space, Modal, Form, Select, Checkbox, message } from 'antd';
import api from '@/lib/api';
import { getProfile } from '../lib';

const { Title } = Typography;

const roleLabel: Record<string, string> = {
  owner: '老板', store_manager: '店长', verifier: '核销员', finance: '财务', staff: '员工',
};

const roleCodeLabel: Record<string, string> = {
  boss: '老板', manager: '店长', finance: '财务', clerk: '店员',
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
}

export default function StaffPage() {
  const [rows, setRows] = useState<StaffRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [permOpen, setPermOpen] = useState(false);
  const [target, setTarget] = useState<StaffRow | null>(null);
  const [permForm] = Form.useForm();
  const profile = useMemo(() => getProfile(), []);
  const canManage = profile?.role === 'owner' || profile?.role === 'store_manager';

  const fetchList = () => {
    setLoading(true);
    api.get('/api/merchant/v1/staff')
      .then((d: any) => setRows(d || []))
      .catch((e: any) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchList();
  }, []);

  const openPerm = (row: StaffRow) => {
    setTarget(row);
    const defaultStore = row.store_ids?.[0];
    permForm.resetFields();
    permForm.setFieldsValue({ store_id: defaultStore, module_codes: [] });
    setPermOpen(true);
  };

  const submitPerm = async () => {
    if (!target) return;
    const values = await permForm.validateFields();
    try {
      await api.put(`/api/merchant/v1/staff/${target.user_id}/permissions`, {
        store_id: values.store_id,
        module_codes: values.module_codes || [],
      });
      message.success('权限已更新');
      setPermOpen(false);
      fetchList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const toggleStatus = async (row: StaffRow) => {
    const next = row.status === 'active' ? 'disabled' : 'active';
    Modal.confirm({
      title: next === 'disabled' ? '确认停用该员工？' : '确认启用该员工？',
      onOk: async () => {
        try {
          await api.put(`/api/merchant/v1/staff/${row.user_id}/status`, { status: next });
          message.success('状态已更新');
          fetchList();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '更新失败');
        }
      },
    });
  };

  return (
    <div>
      <Title level={4}>员工管理</Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message={canManage
          ? '店长可编辑本店下属（财务/店员）的模块权限和停用/启用。新增员工请联系老板/平台管理员。'
          : '员工的增删与权限变更由老板或平台管理员负责。'}
      />
      <Table
        rowKey="user_id"
        loading={loading}
        dataSource={rows}
        pagination={false}
        columns={[
          { title: '手机号', dataIndex: 'phone' },
          { title: '昵称', dataIndex: 'nickname' },
          {
            title: '角色',
            render: (_: any, row: StaffRow) => (
              <Tag color="purple">
                {row.role_name || roleCodeLabel[row.role_code || ''] || roleLabel[row.member_role] || row.member_role}
              </Tag>
            ),
          },
          { title: '所属门店ID', dataIndex: 'store_ids', render: (v: number[]) => (v || []).join(', ') },
          {
            title: '状态',
            dataIndex: 'status',
            render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '启用' : '停用'}</Tag>,
          },
          canManage ? {
            title: '操作',
            render: (_: any, row: StaffRow) => {
              const rc = row.role_code || (row.member_role === 'owner' ? 'boss' : 'clerk');
              const isProtected = rc === 'boss' || (profile?.role === 'store_manager' && rc === 'manager');
              if (isProtected) return <Tag>不可编辑</Tag>;
              return (
                <Space>
                  <Button type="link" onClick={() => openPerm(row)}>编辑权限</Button>
                  <Button type="link" danger={row.status === 'active'} onClick={() => toggleStatus(row)}>
                    {row.status === 'active' ? '停用' : '启用'}
                  </Button>
                </Space>
              );
            },
          } : null,
        ].filter(Boolean) as any}
      />

      <Modal
        title={target ? `编辑 ${target.nickname || target.phone} 的模块权限` : '编辑权限'}
        open={permOpen}
        onCancel={() => setPermOpen(false)}
        onOk={submitPerm}
      >
        <Form form={permForm} layout="vertical">
          <Form.Item
            name="store_id"
            label="门店"
            rules={[{ required: true, message: '请选择门店' }]}
          >
            <Select
              options={(target?.store_ids || []).map((id) => ({ label: `门店 #${id}`, value: id }))}
              placeholder="请选择门店"
            />
          </Form.Item>
          <Form.Item name="module_codes" label="模块权限">
            <Checkbox.Group options={moduleOptions} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
