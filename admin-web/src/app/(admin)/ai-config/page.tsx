'use client';

import React, { useEffect, useState } from 'react';
import {
  Card, Form, Input, InputNumber, Button, Space, message, Typography,
  Table, Tag, Popconfirm, Modal, Alert, Spin, Switch,
} from 'antd';
import {
  SaveOutlined, ApiOutlined, CheckCircleOutlined,
  ExclamationCircleOutlined, PlusOutlined, EditOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;

interface AIConfig {
  id?: number;
  provider_name: string;
  base_url: string;
  model_name: string;
  api_key: string;
  is_active: boolean;
  max_tokens: number;
  temperature: number;
  created_at?: string;
  updated_at?: string;
}

export default function AIConfigPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [configs, setConfigs] = useState<AIConfig[]>([]);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);

  useEffect(() => {
    fetchConfigs();
  }, []);

  const fetchConfigs = async () => {
    setLoading(true);
    try {
      const res = await get('/api/admin/ai-config');
      setConfigs(res?.items || []);
    } catch {
      setConfigs([]);
    } finally {
      setLoading(false);
    }
  };

  const openCreateModal = () => {
    setEditingId(null);
    form.resetFields();
    form.setFieldsValue({
      provider_name: 'OpenAI',
      base_url: 'https://api.openai.com/v1',
      model_name: 'gpt-4',
      api_key: '',
      is_active: false,
      max_tokens: 4096,
      temperature: 0.7,
    });
    setTestResult(null);
    setModalOpen(true);
  };

  const openEditModal = (record: AIConfig) => {
    setEditingId(record.id ?? null);
    form.resetFields();
    form.setFieldsValue({
      provider_name: record.provider_name,
      base_url: record.base_url,
      model_name: record.model_name,
      api_key: '',
      is_active: record.is_active,
      max_tokens: record.max_tokens ?? 4096,
      temperature: record.temperature ?? 0.7,
    });
    setTestResult(null);
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      try {
        if (editingId) {
          const payload: any = { ...values };
          if (!payload.api_key) delete payload.api_key;
          await put(`/api/admin/ai-config/${editingId}`, payload);
          message.success('配置更新成功');
        } else {
          await post('/api/admin/ai-config', values);
          message.success('配置创建成功');
        }
        setModalOpen(false);
        fetchConfigs();
      } catch (e: any) {
        const detail = e?.response?.data?.detail || e?.message || '保存失败';
        message.error(`保存失败: ${detail}`);
      }
    } catch {
      message.error('请完善表单信息');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/ai-config/${id}`);
      message.success('删除成功');
      fetchConfigs();
    } catch {
      message.error('删除失败');
    }
  };

  const handleTest = async () => {
    try {
      const values = await form.validateFields();
      if (!values.api_key) {
        message.warning('测试连接需要填写 API Key');
        return;
      }
      setTesting(true);
      setTestResult(null);
      try {
        const res = await post('/api/admin/ai-config/test', {
          provider_name: values.provider_name || 'OpenAI',
          base_url: values.base_url,
          model_name: values.model_name,
          api_key: values.api_key,
        });
        setTestResult({
          success: res.success ?? false,
          message: res.message || '连接成功',
        });
      } catch (e: any) {
        const detail = e?.response?.data?.detail || e?.message || '网络请求失败';
        setTestResult({ success: false, message: `连接失败: ${detail}` });
      }
    } catch {
      message.error('请完善表单信息');
    } finally {
      setTesting(false);
    }
  };

  const columns = [
    {
      title: '服务商',
      dataIndex: 'provider_name',
      key: 'provider_name',
      width: 120,
    },
    {
      title: 'Base URL',
      dataIndex: 'base_url',
      key: 'base_url',
      ellipsis: true,
    },
    {
      title: '模型名称',
      dataIndex: 'model_name',
      key: 'model_name',
      width: 160,
    },
    {
      title: 'API Key',
      dataIndex: 'api_key',
      key: 'api_key',
      width: 150,
      render: (val: string) => <span style={{ fontFamily: 'monospace' }}>{val || '未设置'}</span>,
    },
    {
      title: 'Max Tokens',
      dataIndex: 'max_tokens',
      key: 'max_tokens',
      width: 110,
      render: (val: number) => val ?? 4096,
    },
    {
      title: 'Temperature',
      dataIndex: 'temperature',
      key: 'temperature',
      width: 110,
      render: (val: number) => val ?? 0.7,
    },
    {
      title: '状态',
      dataIndex: 'is_active',
      key: 'is_active',
      width: 80,
      render: (val: boolean) => (
        <Tag color={val ? 'green' : 'default'}>{val ? '启用' : '停用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: AIConfig) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditModal(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此配置？" onConfirm={() => record.id && handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Spin spinning={loading}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>AI 大模型配置</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateModal}>
          新增配置
        </Button>
      </div>

      <Card style={{ borderRadius: 12 }}>
        <Table
          dataSource={configs}
          columns={columns}
          rowKey="id"
          pagination={false}
          locale={{ emptyText: '暂无 AI 模型配置，请点击「新增配置」添加' }}
        />
      </Card>

      <Modal
        title={editingId ? '编辑 AI 模型配置' : '新增 AI 模型配置'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        footer={null}
        width={560}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="服务商名称" name="provider_name" rules={[{ required: true, message: '请输入服务商名称' }]}>
            <Input placeholder="例如: OpenAI, DeepSeek, 通义千问" />
          </Form.Item>
          <Form.Item label="API Base URL" name="base_url" rules={[{ required: true, message: '请输入 Base URL' }]}>
            <Input placeholder="例如: https://api.openai.com/v1" />
          </Form.Item>
          <Form.Item label="模型名称" name="model_name" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="例如: gpt-4, deepseek-chat" />
          </Form.Item>
          <Form.Item
            label={editingId ? 'API Key（留空则不修改）' : 'API Key'}
            name="api_key"
            rules={editingId ? [] : [{ required: true, message: '请输入 API Key' }]}
          >
            <Input.Password placeholder="请输入 API Key" />
          </Form.Item>
          <div style={{ display: 'flex', gap: 16 }}>
            <Form.Item label="最大 Token 数" name="max_tokens" rules={[{ required: true, message: '请输入最大 Token 数' }]} style={{ flex: 1 }}>
              <InputNumber min={1} max={128000} style={{ width: '100%' }} placeholder="4096" />
            </Form.Item>
            <Form.Item label="Temperature" name="temperature" rules={[{ required: true, message: '请输入 Temperature' }]} style={{ flex: 1 }}>
              <InputNumber min={0} max={2} step={0.1} style={{ width: '100%' }} placeholder="0.7" />
            </Form.Item>
          </div>
          <Form.Item label="设为活跃配置" name="is_active" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="停用" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
                保存
              </Button>
              <Button icon={<ApiOutlined />} onClick={handleTest} loading={testing}>
                测试连接
              </Button>
            </Space>
          </Form.Item>
        </Form>

        {testResult && (
          <Alert
            type={testResult.success ? 'success' : 'error'}
            message={testResult.success ? '连接成功' : '连接失败'}
            description={testResult.message}
            icon={testResult.success ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
            showIcon
            style={{ marginTop: 8 }}
          />
        )}
      </Modal>
    </Spin>
  );
}
