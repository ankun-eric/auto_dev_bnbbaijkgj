'use client';

import React, { useEffect, useMemo, useState } from 'react';
import {
  Button,
  Checkbox,
  Form,
  Input,
  Modal,
  Select,
  Space,
  Switch,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { get, post, put } from '@/lib/api';

const { Title, Text } = Typography;

const merchantModules = [
  { label: '工作台', value: 'dashboard' },
  { label: '扫码核销', value: 'verify' },
  { label: '核销记录', value: 'records' },
  { label: '商家消息', value: 'messages' },
  { label: '个人中心', value: 'profile' },
];

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
  stores: MerchantStoreItem[];
}

export default function MerchantAccountsPage() {
  const [items, setItems] = useState<MerchantAccount[]>([]);
  const [stores, setStores] = useState<StoreOption[]>([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [editing, setEditing] = useState<MerchantAccount | null>(null);
  const [form] = Form.useForm();
  const [importForm] = Form.useForm();
  const merchantIdentityType = Form.useWatch('merchant_identity_type', form);
  const selectedStaffStores = Form.useWatch('staff_store_ids', form) || [];

  const storeOptions = useMemo(
    () => stores.map((item) => ({ label: item.store_name, value: item.id })),
    [stores]
  );

  const fetchStores = async () => {
    const res = await get('/api/admin/merchant/stores');
    setStores(res.items || []);
  };

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/merchant/accounts');
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

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      enable_user_identity: false,
      merchant_identity_type: 'staff',
      status: 'active',
      staff_store_ids: [],
      store_ids: [],
    });
    setOpen(true);
  };

  const openEdit = (item: MerchantAccount) => {
    setEditing(item);
    const staffPermissions: Record<number, string[]> = {};
    item.stores.forEach((store) => {
      staffPermissions[store.id] = store.module_codes || [];
    });
    form.setFieldsValue({
      phone: item.phone,
      password: '',
      user_nickname: item.user_nickname,
      merchant_nickname: item.merchant_nickname,
      enable_user_identity: item.identity_codes.includes('user'),
      merchant_identity_type: item.merchant_identity_type || 'staff',
      status: item.status,
      store_ids: item.stores.map((store) => store.id),
      staff_store_ids: item.stores.map((store) => store.id),
      staff_permissions: staffPermissions,
    });
    setOpen(true);
  };

  const submit = async () => {
    const values = await form.validateFields();
    const payload: any = {
      phone: values.phone,
      password: values.password || undefined,
      user_nickname: values.user_nickname,
      enable_user_identity: !!values.enable_user_identity,
      merchant_identity_type: values.merchant_identity_type,
      merchant_nickname: values.merchant_nickname,
      status: values.status,
      store_ids: [],
      store_permissions: [],
    };

    if (values.merchant_identity_type === 'owner') {
      payload.store_ids = values.store_ids || [];
    } else {
      payload.store_permissions = (values.staff_store_ids || []).map((storeId: number) => ({
        store_id: storeId,
        module_codes: values.staff_permissions?.[storeId] || [],
      }));
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
      message.error(error?.response?.data?.detail || '保存失败');
    }
  };

  const submitImport = async () => {
    const values = await importForm.validateFields();
    try {
      const items = JSON.parse(values.payload);
      await post('/api/admin/merchant/accounts/import', { items });
      message.success('批量导入成功');
      setImportOpen(false);
      importForm.resetFields();
      fetchAccounts();
    } catch (error: any) {
      message.error(error?.response?.data?.detail || error?.message || '导入失败，请检查 JSON 格式');
    }
  };

  return (
    <div>
      <Space style={{ width: '100%', justifyContent: 'space-between', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>商家账号</Title>
        <Space>
          <Button onClick={() => setImportOpen(true)}>批量导入员工</Button>
          <Button type="primary" onClick={openCreate}>新建商家账号</Button>
        </Space>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={[
          { title: '手机号', dataIndex: 'phone' },
          { title: '用户昵称', dataIndex: 'user_nickname' },
          { title: '商家昵称', dataIndex: 'merchant_nickname' },
          {
            title: '身份',
            render: (_: any, item: MerchantAccount) => (
              <Space wrap>
                {item.identity_codes.includes('user') && <Tag color="blue">用户身份</Tag>}
                {item.merchant_identity_type === 'owner' && <Tag color="green">商家主账号</Tag>}
                {item.merchant_identity_type === 'staff' && <Tag color="orange">商家员工</Tag>}
              </Space>
            ),
          },
          {
            title: '门店 / 模块',
            render: (_: any, item: MerchantAccount) => (
              <Space direction="vertical" size={4}>
                {item.stores.map((store) => (
                  <Text key={store.id}>
                    {store.store_name}
                    {store.member_role === 'owner' ? '（全部权限）' : `（${store.module_codes.join(' / ')}）`}
                  </Text>
                ))}
              </Space>
            ),
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
              <Button type="link" onClick={() => openEdit(item)}>编辑</Button>
            ),
          },
        ]}
      />

      <Modal
        title={editing ? '编辑商家账号' : '新建商家账号'}
        open={open}
        onCancel={() => setOpen(false)}
        onOk={submit}
        width={760}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item name="phone" label="手机号" rules={[{ required: true, message: '请输入手机号' }]} style={{ flex: 1 }}>
              <Input placeholder="请输入手机号" />
            </Form.Item>
            <Form.Item name="password" label="初始密码" style={{ flex: 1 }}>
              <Input.Password placeholder="可选，留空则沿用原密码/SMS 登录" />
            </Form.Item>
          </Space>

          <Space style={{ width: '100%' }} size={16}>
            <Form.Item name="user_nickname" label="用户端昵称" style={{ flex: 1 }}>
              <Input placeholder="开启双身份时可填写" />
            </Form.Item>
            <Form.Item name="merchant_nickname" label="商家端昵称" style={{ flex: 1 }}>
              <Input placeholder="请输入商家端昵称" />
            </Form.Item>
          </Space>

          <Space style={{ width: '100%' }} size={16}>
            <Form.Item name="enable_user_identity" label="同时开通用户身份" valuePropName="checked" style={{ flex: 1 }}>
              <Switch checkedChildren="双身份" unCheckedChildren="仅商家" />
            </Form.Item>
            <Form.Item name="merchant_identity_type" label="商家身份类型" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select
                options={[
                  { label: '商家主账号', value: 'owner' },
                  { label: '商家员工账号', value: 'staff' },
                ]}
              />
            </Form.Item>
            <Form.Item name="status" label="账号状态" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select
                options={[
                  { label: '启用', value: 'active' },
                  { label: '停用', value: 'disabled' },
                ]}
              />
            </Form.Item>
          </Space>

          {merchantIdentityType === 'owner' ? (
            <Form.Item
              name="store_ids"
              label="可管理门店"
              rules={[{ required: true, message: '请选择至少一个门店' }]}
            >
              <Select mode="multiple" options={storeOptions} placeholder="请选择主账号可管理的门店" />
            </Form.Item>
          ) : (
            <>
              <Form.Item
                name="staff_store_ids"
                label="员工授权门店"
                rules={[{ required: true, message: '请选择至少一个门店' }]}
              >
                <Select mode="multiple" options={storeOptions} placeholder="请选择员工可进入的门店" />
              </Form.Item>
              {selectedStaffStores.map((storeId: number) => {
                const currentStore = stores.find((item) => item.id === storeId);
                return (
                  <Form.Item
                    key={storeId}
                    name={['staff_permissions', storeId]}
                    label={`${currentStore?.store_name || `门店${storeId}`} 模块权限`}
                    rules={[{ required: true, message: '请至少勾选一个模块' }]}
                  >
                    <Checkbox.Group options={merchantModules} />
                  </Form.Item>
                );
              })}
            </>
          )}
        </Form>
      </Modal>

      <Modal
        title="批量导入员工"
        open={importOpen}
        onCancel={() => setImportOpen(false)}
        onOk={submitImport}
        width={760}
        destroyOnClose
      >
        <Form form={importForm} layout="vertical">
          <Form.Item
            name="payload"
            label="JSON 数组"
            rules={[{ required: true, message: '请输入导入 JSON' }]}
            extra='示例：[{ "phone":"13800001111","merchant_nickname":"门店员工A","merchant_identity_type":"staff","enable_user_identity":true,"store_permissions":[{"store_id":1,"module_codes":["dashboard","verify","records"]}] }]'
          >
            <Input.TextArea rows={10} placeholder="请输入批量导入 JSON 数组" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
