'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Form, Input, InputNumber, Button, Space, message, Typography,
  Table, Tag, Popconfirm, Modal, Alert, Spin, Tabs, Tooltip,
} from 'antd';
import {
  SaveOutlined, ApiOutlined, CheckCircleOutlined,
  ExclamationCircleOutlined, PlusOutlined, EditOutlined, DeleteOutlined,
  ThunderboltOutlined, CloudOutlined, RobotOutlined, CodeOutlined,
  GlobalOutlined, CloudServerOutlined, ExperimentOutlined, BulbOutlined,
  AimOutlined, ToolOutlined, SyncOutlined,
} from '@ant-design/icons';
import { get, post, put, del, patch } from '@/lib/api';

const { Title, Text } = Typography;

// ────────────────────── Types ──────────────────────

interface AIConfig {
  id?: number;
  provider_name: string;
  base_url: string;
  model_name: string;
  api_key: string;
  is_active: boolean;
  max_tokens: number;
  temperature: number;
  template_id?: number | null;
  template_synced_at?: string | null;
  created_at?: string;
  updated_at?: string;
}

interface AITemplate {
  id: number;
  name: string;
  base_url: string;
  model_name: string;
  icon: string;
  description: string;
  status: number;
  created_at?: string;
  updated_at?: string;
}

interface IconOption {
  key: string;
  label: string;
  color: string;
}

interface SyncChange {
  config_id: number;
  config_name: string;
  template_id: number;
  template_name: string;
  template_updated_at: string;
  config_synced_at: string | null;
}

// ────────────────────── Icon Map ──────────────────────

const ICON_MAP: Record<string, { icon: React.ReactNode; color: string; label: string }> = {
  volcano: { icon: <ThunderboltOutlined />, color: '#FF6B35', label: '火山引擎' },
  tencent: { icon: <CloudOutlined />, color: '#006eff', label: '腾讯云' },
  openai: { icon: <RobotOutlined />, color: '#10a37f', label: 'OpenAI' },
  deepseek: { icon: <CodeOutlined />, color: '#4D6BFE', label: 'DeepSeek' },
  baidu: { icon: <GlobalOutlined />, color: '#2932E1', label: '百度文心' },
  alibaba: { icon: <CloudServerOutlined />, color: '#FF6A00', label: '阿里通义' },
  zhipu: { icon: <ExperimentOutlined />, color: '#5B5EA6', label: '智谱AI' },
  moonshot: { icon: <BulbOutlined />, color: '#000000', label: '月之暗面' },
  anthropic: { icon: <AimOutlined />, color: '#D97757', label: 'Anthropic' },
  custom: { icon: <ToolOutlined />, color: '#8c8c8c', label: '自定义' },
};

function renderIcon(iconKey: string, size = 32) {
  const entry = ICON_MAP[iconKey] || ICON_MAP.custom;
  return (
    <div
      style={{
        width: size,
        height: size,
        borderRadius: '50%',
        backgroundColor: entry.color,
        display: 'inline-flex',
        alignItems: 'center',
        justifyContent: 'center',
        color: '#fff',
        fontSize: size * 0.5,
        flexShrink: 0,
      }}
    >
      {entry.icon}
    </div>
  );
}

// ────────────────────── Main Component ──────────────────────

export default function AIConfigPage() {
  const [activeTab, setActiveTab] = useState('configs');

  // Config list state
  const [configForm] = Form.useForm();
  const [configs, setConfigs] = useState<AIConfig[]>([]);
  const [configLoading, setConfigLoading] = useState(false);
  const [configModalOpen, setConfigModalOpen] = useState(false);
  const [editingConfigId, setEditingConfigId] = useState<number | null>(null);
  const [configSaving, setConfigSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);

  // Template selector modal
  const [templateSelectorOpen, setTemplateSelectorOpen] = useState(false);
  const [enabledTemplates, setEnabledTemplates] = useState<AITemplate[]>([]);

  // Sync check state
  const [syncModalOpen, setSyncModalOpen] = useState(false);
  const [syncChanges, setSyncChanges] = useState<SyncChange[]>([]);
  const [syncing, setSyncing] = useState(false);

  // Template management state
  const [templateForm] = Form.useForm();
  const [templates, setTemplates] = useState<AITemplate[]>([]);
  const [templateLoading, setTemplateLoading] = useState(false);
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [editingTemplateId, setEditingTemplateId] = useState<number | null>(null);
  const [templateSaving, setTemplateSaving] = useState(false);
  const [iconOptions, setIconOptions] = useState<IconOption[]>([]);

  // ────────── Config CRUD ──────────

  const fetchConfigs = useCallback(async () => {
    setConfigLoading(true);
    try {
      const res = await get('/api/admin/ai-config');
      setConfigs(res?.items || []);
    } catch {
      setConfigs([]);
    } finally {
      setConfigLoading(false);
    }
  }, []);

  const checkSync = useCallback(async () => {
    try {
      const res = await get('/api/admin/ai-config/sync-check');
      if (res?.count > 0 && res?.need_sync?.length > 0) {
        setSyncChanges(res.need_sync);
        setSyncModalOpen(true);
      }
    } catch {
      // ignore sync check failure
    }
  }, []);

  useEffect(() => {
    fetchConfigs();
    checkSync();
  }, [fetchConfigs, checkSync]);

  const handleActivate = async (id: number) => {
    try {
      await patch(`/api/admin/ai-config/${id}/activate`);
      message.success('已设为活跃配置');
      fetchConfigs();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '设置失败');
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      await post('/api/admin/ai-config/sync');
      message.success('同步成功');
      setSyncModalOpen(false);
      fetchConfigs();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '同步失败');
    } finally {
      setSyncing(false);
    }
  };

  const fetchEnabledTemplates = async () => {
    try {
      const res = await get('/api/admin/ai-model-templates');
      const all: AITemplate[] = res?.items || [];
      setEnabledTemplates(all.filter((t) => t.status === 1));
    } catch {
      setEnabledTemplates([]);
    }
  };

  const openTemplateSelector = async () => {
    await fetchEnabledTemplates();
    setTemplateSelectorOpen(true);
  };

  const selectTemplate = (tpl: AITemplate | null) => {
    setTemplateSelectorOpen(false);
    setEditingConfigId(null);
    setSelectedTemplateId(tpl?.id ?? null);
    configForm.resetFields();
    if (tpl) {
      configForm.setFieldsValue({
        provider_name: tpl.name,
        base_url: tpl.base_url,
        model_name: tpl.model_name,
        api_key: '',
        max_tokens: 4096,
        temperature: 0.7,
      });
    } else {
      configForm.setFieldsValue({
        provider_name: '',
        base_url: '',
        model_name: '',
        api_key: '',
        max_tokens: 4096,
        temperature: 0.7,
      });
    }
    setTestResult(null);
    setConfigModalOpen(true);
  };

  const openEditConfig = (record: AIConfig) => {
    setEditingConfigId(record.id ?? null);
    setSelectedTemplateId(null);
    configForm.resetFields();
    configForm.setFieldsValue({
      provider_name: record.provider_name,
      base_url: record.base_url,
      model_name: record.model_name,
      api_key: '',
      max_tokens: record.max_tokens ?? 4096,
      temperature: record.temperature ?? 0.7,
    });
    setTestResult(null);
    setConfigModalOpen(true);
  };

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      try {
        if (editingConfigId) {
          const payload: any = { ...values };
          if (!payload.api_key) delete payload.api_key;
          await put(`/api/admin/ai-config/${editingConfigId}`, payload);
          message.success('配置更新成功');
        } else {
          const payload: any = { ...values };
          if (selectedTemplateId) {
            payload.template_id = selectedTemplateId;
          }
          await post('/api/admin/ai-config', payload);
          message.success('配置创建成功');
        }
        setConfigModalOpen(false);
        fetchConfigs();
      } catch (e: any) {
        message.error(`保存失败: ${e?.response?.data?.detail || e?.message || '未知错误'}`);
      }
    } catch {
      message.error('请完善表单信息');
    } finally {
      setConfigSaving(false);
    }
  };

  const handleDeleteConfig = async (id: number) => {
    try {
      await del(`/api/admin/ai-config/${id}`);
      message.success('删除成功');
      fetchConfigs();
    } catch {
      message.error('删除失败');
    }
  };

  const handleTestConfig = async () => {
    try {
      const values = await configForm.validateFields();
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
        setTestResult({ success: res.success ?? false, message: res.message || '连接成功' });
      } catch (e: any) {
        setTestResult({ success: false, message: `连接失败: ${e?.response?.data?.detail || e?.message || '网络请求失败'}` });
      }
    } catch {
      message.error('请完善表单信息');
    } finally {
      setTesting(false);
    }
  };

  // ────────── Template CRUD ──────────

  const fetchTemplates = useCallback(async () => {
    setTemplateLoading(true);
    try {
      const res = await get('/api/admin/ai-model-templates');
      setTemplates(res?.items || []);
    } catch {
      setTemplates([]);
    } finally {
      setTemplateLoading(false);
    }
  }, []);

  const fetchIcons = useCallback(async () => {
    try {
      const res = await get('/api/admin/ai-model-templates/icons');
      setIconOptions(res?.items || res || []);
    } catch {
      setIconOptions([]);
    }
  }, []);

  useEffect(() => {
    if (activeTab === 'templates') {
      fetchTemplates();
      fetchIcons();
    }
  }, [activeTab, fetchTemplates, fetchIcons]);

  const openCreateTemplate = () => {
    setEditingTemplateId(null);
    templateForm.resetFields();
    templateForm.setFieldsValue({ name: '', base_url: '', model_name: '', icon: '', description: '' });
    setTemplateModalOpen(true);
  };

  const openEditTemplate = (record: AITemplate) => {
    setEditingTemplateId(record.id);
    templateForm.resetFields();
    templateForm.setFieldsValue({
      name: record.name,
      base_url: record.base_url,
      model_name: record.model_name,
      icon: record.icon,
      description: record.description,
    });
    setTemplateModalOpen(true);
  };

  const handleSaveTemplate = async () => {
    try {
      const values = await templateForm.validateFields();
      setTemplateSaving(true);
      try {
        if (editingTemplateId) {
          await put(`/api/admin/ai-model-templates/${editingTemplateId}`, values);
          message.success('模板更新成功');
        } else {
          await post('/api/admin/ai-model-templates', values);
          message.success('模板创建成功');
        }
        setTemplateModalOpen(false);
        fetchTemplates();
      } catch (e: any) {
        message.error(`保存失败: ${e?.response?.data?.detail || e?.message || '未知错误'}`);
      }
    } catch {
      message.error('请完善表单信息');
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleToggleTemplateStatus = async (record: AITemplate) => {
    const newStatus = record.status === 1 ? 0 : 1;
    try {
      await patch(`/api/admin/ai-model-templates/${record.id}/status`, { status: newStatus });
      message.success(newStatus === 1 ? '模板已启用' : '模板已停用');
      fetchTemplates();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  const handleDeleteTemplate = async (id: number) => {
    try {
      await del(`/api/admin/ai-model-templates/${id}`);
      message.success('模板删除成功');
      fetchTemplates();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败，可能存在关联配置');
    }
  };

  // ────────── Config Columns ──────────

  const configColumns = [
    {
      title: '服务商',
      dataIndex: 'provider_name',
      key: 'provider_name',
      width: 140,
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
      width: 180,
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
      key: 'is_active',
      width: 120,
      render: (_: any, record: AIConfig) =>
        record.is_active ? (
          <Tag color="green" icon={<CheckCircleOutlined />}>当前活跃</Tag>
        ) : (
          <Button type="primary" ghost size="small" onClick={() => record.id && handleActivate(record.id)}>
            设为活跃
          </Button>
        ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: AIConfig) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditConfig(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此配置？" onConfirm={() => record.id && handleDeleteConfig(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ────────── Template Columns ──────────

  const templateColumns = [
    {
      title: '图标',
      dataIndex: 'icon',
      key: 'icon',
      width: 70,
      render: (val: string) => renderIcon(val, 36),
    },
    {
      title: '模板名称',
      dataIndex: 'name',
      key: 'name',
      width: 140,
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
      width: 180,
    },
    {
      title: '说明',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
      width: 200,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (val: number) => (
        <Tag color={val === 1 ? 'green' : 'red'}>{val === 1 ? '启用' : '停用'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: AITemplate) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditTemplate(record)}>
            编辑
          </Button>
          <Button
            type="link"
            size="small"
            onClick={() => handleToggleTemplateStatus(record)}
          >
            {record.status === 1 ? '停用' : '启用'}
          </Button>
          <Popconfirm title="确定删除此模板？" onConfirm={() => handleDeleteTemplate(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  // ────────── Icon selector in template form ──────────

  const IconSelector: React.FC<{ value?: string; onChange?: (v: string) => void }> = ({ value, onChange }) => {
    const allKeys = iconOptions.length > 0
      ? iconOptions.map((o) => o.key)
      : Object.keys(ICON_MAP);

    return (
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
        {allKeys.map((key) => {
          const entry = ICON_MAP[key] || { icon: <ToolOutlined />, color: '#8c8c8c', label: key };
          const isSelected = value === key;
          return (
            <Tooltip title={entry.label} key={key}>
              <div
                onClick={() => onChange?.(key)}
                style={{
                  width: 48,
                  height: 48,
                  borderRadius: '50%',
                  backgroundColor: entry.color,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: '#fff',
                  fontSize: 22,
                  cursor: 'pointer',
                  border: isSelected ? '3px solid #1677ff' : '3px solid transparent',
                  boxShadow: isSelected ? '0 0 0 2px rgba(22,119,255,0.3)' : 'none',
                  transition: 'all 0.2s',
                }}
              >
                {entry.icon}
              </div>
            </Tooltip>
          );
        })}
      </div>
    );
  };

  // ────────── Render ──────────

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>AI 大模型配置</Title>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'configs',
            label: '配置列表',
            children: (
              <Spin spinning={configLoading}>
                <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end' }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={openTemplateSelector}>
                    添加配置
                  </Button>
                </div>
                <Card style={{ borderRadius: 12 }}>
                  <Table
                    dataSource={configs}
                    columns={configColumns}
                    rowKey="id"
                    pagination={false}
                    locale={{ emptyText: '暂无 AI 模型配置，请点击「添加配置」添加' }}
                  />
                </Card>
              </Spin>
            ),
          },
          {
            key: 'templates',
            label: '模板管理',
            children: (
              <Spin spinning={templateLoading}>
                <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end' }}>
                  <Button type="primary" icon={<PlusOutlined />} onClick={openCreateTemplate}>
                    添加模板
                  </Button>
                </div>
                <Card style={{ borderRadius: 12 }}>
                  <Table
                    dataSource={templates}
                    columns={templateColumns}
                    rowKey="id"
                    pagination={false}
                    locale={{ emptyText: '暂无模板' }}
                  />
                </Card>
              </Spin>
            ),
          },
        ]}
      />

      {/* ── Template selector modal ── */}
      <Modal
        title="选择模板"
        open={templateSelectorOpen}
        onCancel={() => setTemplateSelectorOpen(false)}
        footer={null}
        width={720}
        destroyOnClose
      >
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16, padding: '8px 0' }}>
          {enabledTemplates.map((tpl) => {
            return (
              <Card
                key={tpl.id}
                hoverable
                onClick={() => selectTemplate(tpl)}
                style={{
                  width: 200,
                  textAlign: 'center',
                  borderRadius: 12,
                  cursor: 'pointer',
                }}
                bodyStyle={{ padding: 20 }}
              >
                <div style={{ marginBottom: 12 }}>
                  {renderIcon(tpl.icon, 48)}
                </div>
                <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>{tpl.name}</div>
                <Text type="secondary" style={{ fontSize: 12 }} ellipsis={{ tooltip: tpl.description }}>
                  {tpl.description}
                </Text>
              </Card>
            );
          })}
          {/* Custom entry card */}
          <Card
            hoverable
            onClick={() => selectTemplate(null)}
            style={{
              width: 200,
              textAlign: 'center',
              borderRadius: 12,
              cursor: 'pointer',
              borderStyle: 'dashed',
            }}
            bodyStyle={{ padding: 20 }}
          >
            <div style={{ marginBottom: 12 }}>
              {renderIcon('custom', 48)}
            </div>
            <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>自定义配置</div>
            <Text type="secondary" style={{ fontSize: 12 }}>手动填写所有字段</Text>
          </Card>
        </div>
      </Modal>

      {/* ── Config form modal ── */}
      <Modal
        title={editingConfigId ? '编辑 AI 模型配置' : '新增 AI 模型配置'}
        open={configModalOpen}
        onCancel={() => setConfigModalOpen(false)}
        footer={null}
        width={560}
        destroyOnClose
      >
        <Form form={configForm} layout="vertical" style={{ marginTop: 16 }}>
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
            label={editingConfigId ? 'API Key（留空则不修改）' : 'API Key'}
            name="api_key"
            rules={editingConfigId ? [] : [{ required: true, message: '请输入 API Key' }]}
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
          <Form.Item>
            <Space>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveConfig} loading={configSaving}>
                保存
              </Button>
              <Button icon={<ApiOutlined />} onClick={handleTestConfig} loading={testing}>
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

      {/* ── Sync check modal ── */}
      <Modal
        title={
          <Space>
            <SyncOutlined style={{ color: '#faad14' }} />
            <span>模板已更新</span>
          </Space>
        }
        open={syncModalOpen}
        onCancel={() => setSyncModalOpen(false)}
        footer={
          <Space>
            <Button onClick={() => setSyncModalOpen(false)}>忽略</Button>
            <Button type="primary" icon={<SyncOutlined />} loading={syncing} onClick={handleSync}>
              同步更新
            </Button>
          </Space>
        }
        width={600}
      >
        <div style={{ marginBottom: 12 }}>
          <Text>以下配置关联的模板有更新，是否同步到当前配置？</Text>
        </div>
        {syncChanges.map((sc) => (
          <Card
            key={sc.config_id}
            size="small"
            title={<Text strong>{sc.config_name}</Text>}
            style={{ marginBottom: 12, borderRadius: 8 }}
          >
            <div style={{ marginBottom: 4 }}>
              <Text type="secondary">关联模板：</Text>
              <Text>{sc.template_name}</Text>
            </div>
            <div style={{ marginBottom: 4 }}>
              <Text type="secondary">模板更新时间：</Text>
              <Text>{sc.template_updated_at}</Text>
            </div>
            <div>
              <Text type="secondary">配置同步时间：</Text>
              <Text>{sc.config_synced_at || '未同步'}</Text>
            </div>
          </Card>
        ))}
      </Modal>

      {/* ── Template form modal ── */}
      <Modal
        title={editingTemplateId ? '编辑模板' : '添加模板'}
        open={templateModalOpen}
        onCancel={() => setTemplateModalOpen(false)}
        footer={null}
        width={560}
        destroyOnClose
      >
        <Form form={templateForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="模板名称" name="name" rules={[{ required: true, message: '请输入模板名称' }]}>
            <Input placeholder="例如: DeepSeek V3" />
          </Form.Item>
          <Form.Item label="Base URL" name="base_url" rules={[{ required: true, message: '请输入 Base URL' }]}>
            <Input placeholder="例如: https://api.deepseek.com/v1" />
          </Form.Item>
          <Form.Item label="模型名称" name="model_name" rules={[{ required: true, message: '请输入模型名称' }]}>
            <Input placeholder="例如: deepseek-chat" />
          </Form.Item>
          <Form.Item label="图标" name="icon" rules={[{ required: true, message: '请选择图标' }]}>
            <IconSelector />
          </Form.Item>
          <Form.Item label="说明" name="description" rules={[{ required: true, message: '请输入说明' }]}>
            <Input.TextArea rows={3} placeholder="模板简短说明" />
          </Form.Item>
          <Form.Item>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveTemplate} loading={templateSaving}>
              保存
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
