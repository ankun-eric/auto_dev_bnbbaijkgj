'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Card,
  Drawer,
  Empty,
  Form,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Select,
  Space,
  Spin,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import { get, post, put, del } from '@/lib/api';

const { Title, Text } = Typography;

const PASSWORD_RULE = {
  pattern: /^(?=.*[A-Za-z])(?=.*\d).{8,}$/,
  message: '密码至少 8 位且含字母 + 数字',
};

interface StoreOption {
  id: number;
  store_name: string;
}

interface MerchantStoreItem {
  id: number;
  store_name: string;
  member_role: string;
  module_codes: string[];
}

interface MerchantAccount {
  id: number;
  phone: string;
  status: string;
  user_nickname?: string;
  merchant_nickname?: string;
  identity_codes: string[];
  merchant_identity_type?: string;
  role_code?: string | null;
  role_name?: string | null;
  stores: MerchantStoreItem[];
  // [2026-04-26] 后端返回每个老板的非老板员工数量
  staff_count?: number;
}

interface MerchantStaffItem {
  id: number;
  phone: string;
  name?: string | null;
  role_code?: string | null;
  role_name?: string | null;
  status: string;
  status_text?: string | null;
  created_at?: string | null;
  last_login_at?: string | null;
  store_names: string[];
}

interface MerchantStaffListResp {
  items: MerchantStaffItem[];
  total: number;
  merchant_name?: string | null;
}

// [2026-04-26] 角色 → 中文名 + Tag 颜色映射；前端按真实 role_code 渲染，
// 不再硬编码"老板"。即使列表已收紧到 boss，本映射仍保留多角色，避免后续放开过滤再次踩坑。
const ROLE_LABEL_MAP: Record<string, { text: string; color: string }> = {
  boss: { text: '老板', color: 'gold' },
  store_manager: { text: '店长', color: 'blue' },
  manager: { text: '店长', color: 'blue' }, // 历史别名
  finance: { text: '财务', color: 'purple' },
  verifier: { text: '核销员', color: 'green' },
  clerk: { text: '核销员', color: 'green' }, // 历史别名
  staff: { text: '店员', color: 'default' },
};

function renderRoleTag(roleCode?: string | null, roleName?: string | null) {
  const code = (roleCode || '').toLowerCase();
  const meta = ROLE_LABEL_MAP[code];
  if (meta) {
    return <Tag color={meta.color}>{meta.text}</Tag>;
  }
  // 未知角色兜底，显示原始 role_name 或 role_code，不再固定"老板"
  return <Tag>{roleName || roleCode || '-'}</Tag>;
}

function formatDateTime(value?: string | null): string {
  if (!value) return '-';
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return '-';
    const pad = (n: number) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  } catch {
    return '-';
  }
}

export default function MerchantAccountsPage() {
  const [items, setItems] = useState<MerchantAccount[]>([]);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<MerchantAccount | null>(null);
  const [form] = Form.useForm();

  const [resetOpen, setResetOpen] = useState(false);
  const [resetTarget, setResetTarget] = useState<MerchantAccount | null>(null);
  const [resetForm] = Form.useForm();
  const resetType = Form.useWatch('reset_type', resetForm);

  // [2026-04-26] 员工列表抽屉
  const [staffDrawerOpen, setStaffDrawerOpen] = useState(false);
  const [staffLoading, setStaffLoading] = useState(false);
  const [staffData, setStaffData] = useState<MerchantStaffListResp | null>(null);
  const [staffOwner, setStaffOwner] = useState<MerchantAccount | null>(null);

  const storeOptions = useMemo(
    () => stores.map((item) => ({ label: item.store_name, value: item.id })),
    [stores]
  );

  const fetchStores = async () => {
    try {
      const res = await get('/api/admin/merchant/stores');
      setStores(res.items || []);
    } catch {
      // 静默
    }
  };

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      // [2026-04-26] 后端默认 role_code=boss，列表只返回老板账号；显式声明语义更清晰
      const res = await get('/api/admin/merchant/accounts?role_code=boss');
      setItems(res.items || []);
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '商家账号加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStores();
    fetchAccounts();
  }, []);

  const filteredItems = useMemo(() => {
    const kw = keyword.trim();
    if (!kw) return items;
    return items.filter((item) => {
      const name = item.user_nickname || item.merchant_nickname || '';
      return name.includes(kw) || item.phone.includes(kw);
    });
  }, [items, keyword]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ store_ids: [] });
    setOpen(true);
  };

  const openEdit = (item: MerchantAccount) => {
    setEditing(item);
    form.setFieldsValue({
      phone: item.phone,
      password: '',
      name: item.user_nickname || item.merchant_nickname || '',
      store_ids: item.stores.map((store) => store.id),
    });
    setOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    const payload: any = {
      phone: values.phone,
      user_nickname: values.name,
      merchant_nickname: values.name,
      enable_user_identity: false,
      merchant_identity_type: 'owner',
      role_code: 'boss',
      status: 'active',
      store_ids: values.store_ids || [],
    };
    if (values.password) {
      payload.password = values.password;
    }

    try {
      if (editing) {
        await put(`/api/admin/merchant/accounts/${editing.id}`, payload);
        message.success('商家账号更新成功');
      } else {
        await post('/api/admin/merchant/accounts', payload);
        message.success('商家账号创建成功');
      }
      setOpen(false);
      fetchAccounts();
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : '保存失败');
    }
  };

  const toggleStatus = async (item: MerchantAccount) => {
    try {
      await put(`/api/admin/merchant/accounts/${item.id}`, {
        status: item.status === 'active' ? 'disabled' : 'active',
      });
      message.success('状态已更新');
      fetchAccounts();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '状态更新失败');
    }
  };

  const removeAccount = async (item: MerchantAccount) => {
    try {
      await del(`/api/admin/merchant/accounts/${item.id}`);
      message.success('删除成功');
      fetchAccounts();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '删除失败');
    }
  };

  const openReset = (item: MerchantAccount) => {
    setResetTarget(item);
    resetForm.resetFields();
    resetForm.setFieldsValue({ reset_type: 'default', new_password: '' });
    setResetOpen(true);
  };

  const submitReset = async () => {
    if (!resetTarget) return;
    const values = await resetForm.validateFields();
    const payload: any = { reset_type: values.reset_type };
    if (values.reset_type === 'custom') {
      payload.new_password = values.new_password;
    }
    try {
      await post(`/api/admin/merchant/accounts/${resetTarget.id}/reset-password`, payload);
      message.success('密码重置成功');
      setResetOpen(false);
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      message.error(typeof detail === 'string' ? detail : '重置失败');
    }
  };

  // [2026-04-26] 打开员工列表抽屉
  const openStaffDrawer = async (item: MerchantAccount) => {
    setStaffOwner(item);
    setStaffDrawerOpen(true);
    setStaffData(null);
    setStaffLoading(true);
    try {
      const res = await get(`/api/admin/merchant/accounts/${item.id}/staff`);
      setStaffData(res || { items: [], total: 0 });
    } catch (error: any) {
      message.error(error?.response?.data?.detail || '员工列表加载失败');
      setStaffData({ items: [], total: 0 });
    } finally {
      setStaffLoading(false);
    }
  };

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>商家账号</Title>
        <Button type="primary" onClick={openCreate}>新建商家账号</Button>
      </Space>

      <Card style={{ marginBottom: 16 }}>
        <Space>
          <Input.Search
            allowClear
            placeholder="按姓名/手机号搜索"
            style={{ width: 280 }}
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
            onSearch={(v) => setKeyword(v)}
          />
        </Space>
      </Card>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={filteredItems}
        columns={[
          {
            title: '姓名',
            render: (_: any, item: MerchantAccount) => (
              <Text>{item.user_nickname || item.merchant_nickname || '-'}</Text>
            ),
          },
          { title: '手机号', dataIndex: 'phone' },
          {
            title: '所属商家',
            render: (_: any, item: MerchantAccount) => (
              <Space wrap>
                {item.stores.length === 0 ? (
                  <Text type="secondary">-</Text>
                ) : (
                  item.stores.map((store) => (
                    <Tag key={store.id} color="blue">{store.store_name}</Tag>
                  ))
                )}
              </Space>
            ),
          },
          {
            title: '角色',
            // [2026-04-26] 修复硬编码"老板"问题：按真实 role_code 渲染对应中文 Tag
            render: (_: any, item: MerchantAccount) => renderRoleTag(item.role_code, item.role_name),
          },
          {
            title: '状态',
            dataIndex: 'status',
            render: (value: string) => (
              <Tag color={value === 'active' ? 'green' : 'red'}>
                {value === 'active' ? '启用' : '停用'}
              </Tag>
            ),
          },
          {
            title: '操作',
            render: (_: any, item: MerchantAccount) => (
              <Space wrap>
                <Button type="link" onClick={() => openEdit(item)}>编辑</Button>
                <Popconfirm
                  title={item.status === 'active' ? '确认停用该账号？' : '确认启用该账号？'}
                  onConfirm={() => toggleStatus(item)}
                >
                  <Button type="link">{item.status === 'active' ? '停用' : '启用'}</Button>
                </Popconfirm>
                <Popconfirm
                  title="确认删除该账号？"
                  okType="danger"
                  onConfirm={() => removeAccount(item)}
                >
                  <Button type="link" danger>删除</Button>
                </Popconfirm>
                <Button type="link" onClick={() => openReset(item)}>重置密码</Button>
                {/* [2026-04-26] 新增：员工列表入口 */}
                <Button type="link" onClick={() => openStaffDrawer(item)}>
                  员工列表 ({item.staff_count ?? 0})
                </Button>
              </Space>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? '编辑商家账号' : '新建商家账号'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="name"
            label="姓名"
            rules={[{ required: true, message: '请输入姓名' }]}
          >
            <Input placeholder="请输入姓名" maxLength={32} />
          </Form.Item>
          <Form.Item
            name="phone"
            label="手机号"
            rules={[
              { required: true, message: '请输入手机号' },
              { pattern: /^1\d{10}$/, message: '请输入 11 位手机号' },
            ]}
          >
            <Input placeholder="请输入手机号" maxLength={11} />
          </Form.Item>
          <Form.Item
            name="password"
            label="登录密码"
            rules={
              editing
                ? [PASSWORD_RULE]
                : [{ required: true, message: '请输入登录密码' }, PASSWORD_RULE]
            }
            extra={editing ? '留空则不修改密码' : undefined}
          >
            <Input.Password placeholder="≥ 8 位且含字母 + 数字" autoComplete="new-password" />
          </Form.Item>
          <Form.Item
            name="store_ids"
            label="所属商家/门店"
            rules={[{ required: true, message: '请选择至少一个门店' }]}
          >
            <Select
              mode="multiple"
              options={storeOptions}
              placeholder="请选择该账号可管理的门店"
              showSearch
              optionFilterProp="label"
            />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`重置密码${resetTarget ? ` - ${resetTarget.user_nickname || resetTarget.merchant_nickname || resetTarget.phone}` : ''}`}
        open={resetOpen}
        onCancel={() => setResetOpen(false)}
        onOk={submitReset}
        destroyOnClose
        width={460}
      >
        <Form form={resetForm} layout="vertical">
          <Form.Item name="reset_type" label="重置方式" rules={[{ required: true }]}>
            <Radio.Group>
              <Space direction="vertical">
                <Radio value="default">
                  默认密码（手机号后 6 位
                  {resetTarget?.phone ? `:${resetTarget.phone.slice(-6)}` : ''}）
                </Radio>
                <Radio value="custom">自定义密码</Radio>
              </Space>
            </Radio.Group>
          </Form.Item>
          {resetType === 'custom' && (
            <Form.Item
              name="new_password"
              label="新密码"
              rules={[{ required: true, message: '请输入新密码' }, PASSWORD_RULE]}
            >
              <Input.Password placeholder="≥ 8 位且含字母 + 数字" autoComplete="new-password" />
            </Form.Item>
          )}
        </Form>
      </Modal>

      {/* [2026-04-26] 员工列表抽屉 */}
      <Drawer
        title={`员工列表${staffData?.merchant_name ? ` - ${staffData.merchant_name}` : (staffOwner ? ` - ${staffOwner.user_nickname || staffOwner.merchant_nickname || staffOwner.phone}` : '')}`}
        placement="right"
        width={920}
        open={staffDrawerOpen}
        onClose={() => setStaffDrawerOpen(false)}
        destroyOnClose
      >
        {staffLoading ? (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin />
          </div>
        ) : !staffData || staffData.items.length === 0 ? (
          <Empty description="该商家暂无员工" style={{ marginTop: 80 }} />
        ) : (
          <Table
            rowKey="id"
            pagination={{ pageSize: 20, showSizeChanger: false }}
            dataSource={staffData.items}
            columns={[
              { title: '账号', dataIndex: 'phone', width: 130 },
              {
                title: '姓名',
                width: 120,
                render: (_: any, it: MerchantStaffItem) => it.name || '-',
              },
              { title: '手机号', dataIndex: 'phone', width: 130 },
              {
                title: '角色',
                width: 90,
                render: (_: any, it: MerchantStaffItem) => renderRoleTag(it.role_code, it.role_name),
              },
              {
                title: '状态',
                width: 80,
                render: (_: any, it: MerchantStaffItem) => (
                  <Tag color={it.status === 'active' ? 'green' : 'red'}>
                    {it.status_text || (it.status === 'active' ? '正常' : '禁用')}
                  </Tag>
                ),
              },
              {
                title: '创建时间',
                width: 160,
                render: (_: any, it: MerchantStaffItem) => formatDateTime(it.created_at),
              },
              {
                title: '最后登录时间',
                width: 160,
                render: (_: any, it: MerchantStaffItem) => formatDateTime(it.last_login_at),
              },
              {
                title: '绑定门店',
                render: (_: any, it: MerchantStaffItem) => {
                  if (!it.store_names || it.store_names.length === 0) return '-';
                  const text = it.store_names.join('、');
                  return (
                    <Tooltip title={text}>
                      <Text style={{ maxWidth: 200, display: 'inline-block' }} ellipsis>
                        {text}
                      </Text>
                    </Tooltip>
                  );
                },
              },
            ]}
          />
        )}
      </Drawer>
    </div>
  );
}
