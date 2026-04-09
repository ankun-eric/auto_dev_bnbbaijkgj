'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input, Select,
  Typography, message, Popconfirm, Tooltip,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
  ArrowUpOutlined, ArrowDownOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

const ICON_OPTIONS: { key: string; name: string; emoji: string }[] = [
  { key: 'home', name: '首页', emoji: '🏠' },
  { key: 'chat', name: '咨询', emoji: '💬' },
  { key: 'service', name: '服务', emoji: '🏥' },
  { key: 'order', name: '订单', emoji: '📋' },
  { key: 'record', name: '档案', emoji: '📁' },
  { key: 'mall', name: '商城', emoji: '🛒' },
  { key: 'health', name: '健康', emoji: '❤️' },
  { key: 'report', name: '报告', emoji: '📊' },
  { key: 'bell', name: '消息', emoji: '🔔' },
  { key: 'profile', name: '我的', emoji: '👤' },
];

const ICON_MAP: Record<string, string> = Object.fromEntries(
  ICON_OPTIONS.map((i) => [i.key, i.emoji])
);

const ICON_NAME_MAP: Record<string, string> = Object.fromEntries(
  ICON_OPTIONS.map((i) => [i.key, i.name])
);

const PAGE_PATH_OPTIONS = [
  { label: 'AI健康咨询 (/ai)', value: '/ai' },
  { label: '服务列表 (/services)', value: '/services' },
  { label: '我的订单 (/orders)', value: '/orders' },
  { label: '健康档案 (/health-profile)', value: '/health-profile' },
  { label: '积分商城 (/points-mall)', value: '/points-mall' },
];

interface BottomNavItem {
  id: number;
  name: string;
  icon_key: string;
  path: string;
  is_visible: boolean;
  is_fixed: boolean;
  sort_order: number;
  created_at?: string;
  updated_at?: string;
}

export default function BottomNavPage() {
  const [items, setItems] = useState<BottomNavItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<BottomNavItem | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();

  const configurableItems = items.filter((i) => !i.is_fixed);
  const canAddMore = configurableItems.length < 3;

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<BottomNavItem[] | { items: BottomNavItem[] }>('/api/admin/bottom-nav');
      const data = Array.isArray(res) ? res : (res as any).items || [];
      setItems(data);
    } catch {
      message.error('获取底部导航配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenModal = (record?: BottomNavItem) => {
    setEditingItem(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        name: record.name,
        icon_key: record.icon_key,
        path: record.path,
        is_visible: record.is_visible,
      });
    } else {
      form.setFieldsValue({ is_visible: true });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        name: values.name,
        icon_key: values.icon_key,
        path: values.path,
        is_visible: values.is_visible,
      };
      if (editingItem) {
        await put(`/api/admin/bottom-nav/${editingItem.id}`, payload);
        message.success('导航项更新成功');
      } else {
        await post('/api/admin/bottom-nav', payload);
        message.success('导航项创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/bottom-nav/${id}`);
      message.success('导航项删除成功');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const handleToggleVisible = async (record: BottomNavItem, checked: boolean) => {
    try {
      await put(`/api/admin/bottom-nav/${record.id}`, {
        is_visible: checked,
      });
      message.success('状态更新成功');
      fetchData();
    } catch {
      message.error('状态更新失败');
    }
  };

  const handleMove = async (index: number, direction: 'up' | 'down') => {
    const newItems = [...items];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= newItems.length) return;

    const current = newItems[index];
    const target = newItems[targetIndex];
    if (current.is_fixed || target.is_fixed) return;

    [newItems[index], newItems[targetIndex]] = [newItems[targetIndex], newItems[index]];
    const sortPayload = newItems.map((m, i) => ({ id: m.id, sort_order: i }));
    try {
      await put('/api/admin/bottom-nav/sort', sortPayload);
      message.success('排序更新成功');
      fetchData();
    } catch {
      message.error('排序更新失败');
    }
  };

  const canMoveUp = (index: number) => {
    if (items[index].is_fixed) return false;
    if (index === 0) return false;
    const target = items[index - 1];
    return !target.is_fixed;
  };

  const canMoveDown = (index: number) => {
    if (items[index].is_fixed) return false;
    if (index === items.length - 1) return false;
    const target = items[index + 1];
    return !target.is_fixed;
  };

  const columns = [
    {
      title: '排序',
      key: 'sort',
      width: 100,
      render: (_: any, __: BottomNavItem, index: number) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<ArrowUpOutlined />}
            disabled={!canMoveUp(index)}
            onClick={() => handleMove(index, 'up')}
          />
          <Button
            type="text"
            size="small"
            icon={<ArrowDownOutlined />}
            disabled={!canMoveDown(index)}
            onClick={() => handleMove(index, 'down')}
          />
        </Space>
      ),
    },
    {
      title: 'Tab名称',
      dataIndex: 'name',
      key: 'name',
      width: 120,
    },
    {
      title: '图标预览',
      dataIndex: 'icon_key',
      key: 'icon_preview',
      width: 100,
      render: (val: string) => (
        <Tooltip title={`${ICON_NAME_MAP[val] || val} (${val})`}>
          <span style={{ fontSize: 24 }}>{ICON_MAP[val] || '❓'}</span>
        </Tooltip>
      ),
    },
    {
      title: '跳转路径',
      dataIndex: 'path',
      key: 'path',
      width: 180,
      ellipsis: true,
      render: (val: string) => val || '-',
    },
    {
      title: '显示状态',
      dataIndex: 'is_visible',
      key: 'is_visible',
      width: 100,
      render: (val: boolean, record: BottomNavItem) => (
        <Switch
          checked={val}
          checkedChildren="显示"
          unCheckedChildren="隐藏"
          disabled={record.is_fixed}
          onChange={(checked) => handleToggleVisible(record, checked)}
        />
      ),
    },
    {
      title: '类型',
      dataIndex: 'is_fixed',
      key: 'is_fixed',
      width: 100,
      render: (val: boolean) => (
        <Tag color={val ? 'default' : 'blue'}>
          {val ? '固定' : '可配置'}
        </Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: BottomNavItem) => {
        if (record.is_fixed) {
          return <span style={{ color: '#999' }}>—</span>;
        }
        return (
          <Space>
            <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
              编辑
            </Button>
            <Popconfirm title="确定删除此导航项？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>底部导航配置</Title>
      <div style={{ marginBottom: 16 }}>
        <Tooltip title={canAddMore ? '' : '可配置导航项最多3个'}>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            disabled={!canAddMore}
            onClick={() => handleOpenModal()}
          >
            新增导航项
          </Button>
        </Tooltip>
        {!canAddMore && (
          <span style={{ marginLeft: 12, color: '#999', fontSize: 13 }}>
            可配置导航项已达上限（3个）
          </span>
        )}
      </div>
      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 800 }}
      />
      <Modal
        title={editingItem ? '编辑导航项' : '新增导航项'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={520}
      >
        <Form form={form} layout="vertical" initialValues={{ is_visible: true }}>
          <Form.Item
            label="Tab名称"
            name="name"
            rules={[
              { required: true, message: '请输入Tab名称' },
              { max: 6, message: 'Tab名称最多6个字' },
            ]}
          >
            <Input placeholder="请输入Tab名称（最多6字）" maxLength={6} showCount />
          </Form.Item>
          <Form.Item
            label="图标"
            name="icon_key"
            rules={[{ required: true, message: '请选择图标' }]}
          >
            <Select placeholder="请选择图标">
              {ICON_OPTIONS.map((icon) => (
                <Select.Option key={icon.key} value={icon.key}>
                  <span style={{ fontSize: 18, marginRight: 8 }}>{icon.emoji}</span>
                  {icon.name}（{icon.key}）
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
          <Form.Item
            label="跳转路径"
            name="path"
            rules={[{ required: true, message: '请选择或输入跳转路径' }]}
          >
            <Select
              placeholder="请选择或输入跳转路径"
              showSearch
              allowClear
              options={PAGE_PATH_OPTIONS}
              mode={undefined}
              filterOption={(input, option) =>
                (option?.label as string)?.toLowerCase().includes(input.toLowerCase()) ||
                (option?.value as string)?.toLowerCase().includes(input.toLowerCase())
              }
              dropdownRender={(menu) => (
                <>
                  {menu}
                  <div style={{ padding: '8px 12px', color: '#999', fontSize: 12, borderTop: '1px solid #f0f0f0' }}>
                    可直接输入自定义路径
                  </div>
                </>
              )}
              onSearch={() => {}}
            />
          </Form.Item>
          <Form.Item label="显示状态" name="is_visible" valuePropName="checked">
            <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
