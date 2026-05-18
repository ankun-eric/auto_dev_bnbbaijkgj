'use client';

/**
 * [PRD-FAMILY-GUARDIAN-V1] 异常文案模板 CRUD
 * 占位符：{relationship} {nickname} {count}
 */

import React, { useCallback, useEffect, useState } from 'react';
import {
  Button,
  Card,
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
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title, Text, Paragraph } = Typography;

interface TemplateRow {
  id: number;
  code: string;
  channel: string;
  scene: string;
  title: string;
  content: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

const CHANNEL_OPTIONS = [
  { value: 'wechat_mp', label: '微信公众号' },
  { value: 'mini_subscribe', label: '小程序订阅消息' },
  { value: 'app_push', label: 'App 推送' },
];

const SCENE_OPTIONS = [
  { value: 'checkup_abnormal', label: '体检异常' },
  { value: 'family_bind', label: '家庭绑定' },
  { value: 'family_unbind', label: '家庭解绑' },
];

const PLACEHOLDERS = ['{relationship}', '{nickname}', '{count}'];

export default function AlertTemplatesPage() {
  const [data, setData] = useState<TemplateRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<TemplateRow | null>(null);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<{ items: TemplateRow[] }>('/api/admin/alert-templates');
      setData(res.items || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({ channel: 'mini_subscribe', scene: 'checkup_abnormal', is_active: true });
    setModalOpen(true);
  };

  const openEdit = (row: TemplateRow) => {
    setEditing(row);
    form.setFieldsValue(row);
    setModalOpen(true);
  };

  const onSubmit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await put(`/api/admin/alert-templates/${editing.id}`, values);
        message.success('已更新');
      } else {
        await post('/api/admin/alert-templates', values);
        message.success('已创建');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  const onDelete = async (row: TemplateRow) => {
    Modal.confirm({
      title: '删除模板',
      content: `确定删除「${row.code}」吗？`,
      onOk: async () => {
        try {
          await del(`/api/admin/alert-templates/${row.id}`);
          message.success('已删除');
          fetchData();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const insertPlaceholder = (ph: string) => {
    const cur = form.getFieldValue('content') || '';
    form.setFieldValue('content', cur + ph);
  };

  const renderPreview = (content: string) => {
    let out = content || '';
    out = out.replace('{relationship}', '父亲');
    out = out.replace('{nickname}', '张大爷');
    out = out.replace('{count}', '5');
    return out;
  };

  const columns = [
    { title: '编码', dataIndex: 'code', key: 'code', width: 200 },
    {
      title: '通道',
      dataIndex: 'channel',
      key: 'channel',
      width: 140,
      render: (v: string) => CHANNEL_OPTIONS.find((c) => c.value === v)?.label || v,
    },
    {
      title: '场景',
      dataIndex: 'scene',
      key: 'scene',
      width: 120,
      render: (v: string) => SCENE_OPTIONS.find((c) => c.value === v)?.label || v,
    },
    { title: '标题', dataIndex: 'title', key: 'title' },
    {
      title: '内容预览',
      dataIndex: 'content',
      key: 'content',
      render: (v: string) => <Text style={{ color: '#666' }}>{renderPreview(v)}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (v: boolean) => v ? <Tag color="green">生效</Tag> : <Tag>停用</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, row: TemplateRow) => (
        <Space>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(row)}>编辑</Button>
          <Button size="small" danger icon={<DeleteOutlined />} onClick={() => onDelete(row)}>删除</Button>
        </Space>
      ),
    },
  ];

  return (
    <Card>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>异常文案模板</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新增模板</Button>
      </div>

      <Paragraph type="secondary">
        极简三占位：<Tag>{`{relationship}`}</Tag><Tag>{`{nickname}`}</Tag><Tag>{`{count}`}</Tag>
        ；编辑器右侧可点击占位符按钮插入。
      </Paragraph>

      <Table
        rowKey="id"
        columns={columns}
        dataSource={data}
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title={editing ? '编辑模板' : '新增模板'}
        open={modalOpen}
        onOk={onSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="code" label="模板编码" rules={[{ required: true }]}>
            <Input placeholder="如 checkup_abnormal_mini" />
          </Form.Item>
          <Form.Item name="channel" label="通道" rules={[{ required: true }]}>
            <Select options={CHANNEL_OPTIONS} />
          </Form.Item>
          <Form.Item name="scene" label="场景" rules={[{ required: true }]}>
            <Select options={SCENE_OPTIONS} />
          </Form.Item>
          <Form.Item name="title" label="标题" rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="content" label="内容（支持三占位）" rules={[{ required: true }]}>
            <Input.TextArea rows={4} />
          </Form.Item>
          <Space wrap style={{ marginBottom: 12 }}>
            {PLACEHOLDERS.map((p) => (
              <Button key={p} size="small" onClick={() => insertPlaceholder(p)}>{p}</Button>
            ))}
          </Space>
          <Form.Item shouldUpdate>
            {() => (
              <div style={{ background: '#fafafa', padding: 12, borderRadius: 8 }}>
                <Text strong>预览：</Text>
                <div style={{ color: '#666', marginTop: 6 }}>{renderPreview(form.getFieldValue('content') || '')}</div>
              </div>
            )}
          </Form.Item>
          <Form.Item name="is_active" label="是否生效" valuePropName="checked" initialValue={true}>
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
}
