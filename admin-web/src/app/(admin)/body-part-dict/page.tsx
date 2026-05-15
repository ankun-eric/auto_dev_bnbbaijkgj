'use client';

/**
 * [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 管理后台 · 部位症状字典页面。
 *
 * - 列表：图标 / 名称 / 症状数量 / 排序 / 启用 / 操作
 * - 编辑弹窗：图标 + 名称（唯一） + 症状数组（标签输入） + 排序 + 启用开关
 * - 部位被模板引用时禁止删除（后端会拦截）
 */
import React, { useCallback, useEffect, useState } from 'react';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input,
  InputNumber, Typography, message, Select,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title, Text } = Typography;

interface BodyPart {
  id: number;
  name: string;
  icon: string;
  symptoms: string[];
  symptom_count: number;
  sort_order: number;
  enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export default function BodyPartDictPage() {
  const [items, setItems] = useState<BodyPart[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<BodyPart | null>(null);
  const [form] = Form.useForm();
  const [saving, setSaving] = useState(false);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/body-part-dict', { page, page_size: pageSize });
      setItems(res.items || []);
      setTotal(res.total || 0);
    } catch {
      message.error('获取部位字典失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openModal = (record?: BodyPart) => {
    setEditing(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        name: record.name,
        icon: record.icon,
        symptoms: record.symptoms || [],
        sort_order: record.sort_order ?? 100,
        enabled: record.enabled,
      });
    } else {
      form.setFieldsValue({ icon: '🧠', sort_order: 100, enabled: true, symptoms: [] });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      if (!values.symptoms || values.symptoms.length === 0) {
        message.warning('请至少输入 1 个症状');
        return;
      }
      setSaving(true);
      const payload = {
        name: values.name,
        icon: values.icon,
        symptoms: values.symptoms,
        sort_order: values.sort_order ?? 100,
        enabled: !!values.enabled,
      };
      if (editing) {
        await put(`/api/admin/body-part-dict/${editing.id}`, payload);
        message.success('部位更新成功');
      } else {
        await post('/api/admin/body-part-dict', payload);
        message.success('部位创建成功');
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

  const handleDelete = (record: BodyPart) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除部位「${record.name}」吗？如被模板引用将无法删除。`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await del(`/api/admin/body-part-dict/${record.id}`);
          message.success('删除成功');
          fetchData();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const toggleEnabled = async (record: BodyPart, checked: boolean) => {
    try {
      await put(`/api/admin/body-part-dict/${record.id}`, { enabled: checked });
      message.success(checked ? '已启用' : '已停用');
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '状态更新失败');
    }
  };

  const columns = [
    { title: '排序', dataIndex: 'sort_order', key: 'sort_order', width: 80 },
    {
      title: '图标', dataIndex: 'icon', key: 'icon', width: 80,
      render: (v: string) => <span style={{ fontSize: 24 }}>{v || '🧠'}</span>,
    },
    { title: '部位名称', dataIndex: 'name', key: 'name', width: 140 },
    {
      title: '症状数量', dataIndex: 'symptom_count', key: 'symptom_count', width: 100,
      render: (n: number) => <Tag color="blue">{n}</Tag>,
    },
    {
      title: '症状预览', dataIndex: 'symptoms', key: 'symptoms',
      render: (arr: string[]) => (
        <Space wrap size={[4, 4]}>
          {(arr || []).slice(0, 8).map((s) => <Tag key={s}>{s}</Tag>)}
          {(arr || []).length > 8 && <Text type="secondary">+{arr.length - 8}</Text>}
        </Space>
      ),
    },
    {
      title: '启用状态', dataIndex: 'enabled', key: 'enabled', width: 120,
      render: (v: boolean, r: BodyPart) => (
        <Switch checked={v} checkedChildren="启用" unCheckedChildren="停用"
          onChange={(c) => toggleEnabled(r, c)} />
      ),
    },
    {
      title: '操作', key: 'action', width: 160,
      render: (_: any, r: BodyPart) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openModal(r)}>编辑</Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(r)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>部位症状字典</Title>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => openModal()}>
          新增部位
        </Button>
        <Text type="secondary" style={{ marginLeft: 12 }}>
          字典内的部位将作为「健康自查问卷模板」的可选项
        </Text>
      </div>
      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page, pageSize, total,
          showSizeChanger: true, showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
        scroll={{ x: 800 }}
      />
      <Modal
        title={editing ? '编辑部位' : '新增部位'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical">
          <Form.Item
            label="部位图标（Emoji 或图标 URL）"
            name="icon"
            rules={[{ required: true, message: '请输入图标' }]}
            extra="可填 Emoji（如 🧠）或图标 URL"
          >
            <Input placeholder="例：🧠" maxLength={255} />
          </Form.Item>
          <Form.Item
            label="部位名称"
            name="name"
            rules={[
              { required: true, message: '请输入部位名称' },
              { max: 20, message: '最多 20 字' },
            ]}
          >
            <Input placeholder="例：头部、胸部、腹部" maxLength={20} />
          </Form.Item>
          <Form.Item
            label="症状列表"
            name="symptoms"
            rules={[{ required: true, message: '请至少输入 1 个症状' }]}
            extra="按回车追加；可多个；同一部位下不重复"
          >
            <Select
              mode="tags"
              placeholder="例：头痛 / 头晕 / 偏头痛（回车确认）"
              tokenSeparators={[',', '，']}
            />
          </Form.Item>
          <Form.Item label="排序值" name="sort_order" extra="数值越小越靠前，默认 100">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="启用状态" name="enabled" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
