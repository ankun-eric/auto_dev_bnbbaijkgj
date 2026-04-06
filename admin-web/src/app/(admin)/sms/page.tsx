'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Tabs, Form, Input, Button, Table, Tag, Space, Card, message, Typography, Select, Alert, Spin,
  Switch, Modal, Popconfirm, InputNumber,
} from 'antd';
import {
  SettingOutlined, UnorderedListOutlined, SendOutlined, SaveOutlined,
  SearchOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
  PlusOutlined, EditOutlined, DeleteOutlined, FileTextOutlined,
  MinusCircleOutlined, EyeOutlined, SwapOutlined,
} from '@ant-design/icons';
import { get, put, post, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

interface TencentConfig {
  id?: number;
  is_active: boolean;
  secret_id: string;
  secret_key?: string;
  sdk_app_id: string;
  sign_name: string;
  template_id: string;
  app_key: string;
  has_secret_key: boolean;
  created_at?: string;
  updated_at?: string;
}

interface AliyunConfig {
  id?: number;
  is_active: boolean;
  access_key_id: string;
  sign_name: string;
  template_id: string;
  has_access_key_secret: boolean;
  created_at?: string;
  updated_at?: string;
}

interface SmsConfigResponse {
  tencent: TencentConfig;
  aliyun: AliyunConfig;
}

interface TemplateVariable {
  name: string;
  description?: string;
  default_value?: string;
}

interface SmsTemplate {
  id: number;
  name: string;
  provider: string;
  template_id: string;
  content: string;
  sign_name: string;
  scene: string;
  variables: TemplateVariable[] | null;
  status: boolean;
  created_at: string;
  updated_at?: string;
}

interface SmsLog {
  id: number;
  phone: string;
  code: string;
  template_id: string;
  provider: string;
  status: string;
  error_message: string;
  is_test: boolean;
  operator_id: number | null;
  created_at: string;
}

export default function SmsPage() {
  const [activeTab, setActiveTab] = useState('config');

  // Config state
  const [tencentForm] = Form.useForm();
  const [aliyunForm] = Form.useForm();
  const [configLoading, setConfigLoading] = useState(false);
  const [tencentSaving, setTencentSaving] = useState(false);
  const [aliyunSaving, setAliyunSaving] = useState(false);
  const [tencentEnabled, setTencentEnabled] = useState(false);
  const [aliyunEnabled, setAliyunEnabled] = useState(false);
  const [tencentHasSecret, setTencentHasSecret] = useState(false);
  const [aliyunHasSecret, setAliyunHasSecret] = useState(false);

  // Template state
  const [templates, setTemplates] = useState<SmsTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [templatesPagination, setTemplatesPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [templateProvider, setTemplateProvider] = useState<string>('');
  const [templateScene, setTemplateScene] = useState<string>('');
  const [templateSearch, setTemplateSearch] = useState('');
  const [templateModalOpen, setTemplateModalOpen] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<SmsTemplate | null>(null);
  const [templateForm] = Form.useForm();
  const [templateSaving, setTemplateSaving] = useState(false);

  // Logs state
  const [logs, setLogs] = useState<SmsLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsPagination, setLogsPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [searchPhone, setSearchPhone] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [filterProvider, setFilterProvider] = useState<string>('');

  // Test state
  const [testForm] = Form.useForm();
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string; params_used?: string[]; preview_content?: string } | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<SmsTemplate | null>(null);
  const [inputMode, setInputMode] = useState<'auto' | 'advanced'>('auto');

  // Preview modal state
  const [previewModalOpen, setPreviewModalOpen] = useState(false);
  const [previewData, setPreviewData] = useState<{
    phone: string;
    provider: string;
    templateName: string;
    templateId: string;
    params: { name: string; value: string }[];
    previewContent: string;
  } | null>(null);

  const fetchConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const res = await get<SmsConfigResponse>('/api/admin/sms/config');
      const t = res.tencent || {} as TencentConfig;
      const a = res.aliyun || {} as AliyunConfig;
      setTencentEnabled(!!t.is_active);
      setAliyunEnabled(!!a.is_active);
      setTencentHasSecret(!!t.has_secret_key);
      setAliyunHasSecret(!!a.has_access_key_secret);
      tencentForm.setFieldsValue({
        secret_id: t.secret_id || '',
        sdk_app_id: t.sdk_app_id || '',
        sign_name: t.sign_name || '',
      });
      aliyunForm.setFieldsValue({
        access_key_id: a.access_key_id || '',
        sign_name: a.sign_name || '',
      });
    } catch {
      // config not yet set
    } finally {
      setConfigLoading(false);
    }
  }, [tencentForm, aliyunForm]);

  const fetchTemplates = useCallback(async (page = 1, pageSize = 20) => {
    setTemplatesLoading(true);
    try {
      const res = await get<{ items: SmsTemplate[]; total: number; page: number; page_size: number }>(
        '/api/admin/sms/templates',
        { page, page_size: pageSize, provider: templateProvider, scene: templateScene, name: templateSearch },
      );
      setTemplates(res.items || []);
      setTemplatesPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取短信模板失败');
    } finally {
      setTemplatesLoading(false);
    }
  }, [templateProvider, templateScene, templateSearch]);

  const fetchLogs = useCallback(async (page = 1, pageSize = 20) => {
    setLogsLoading(true);
    try {
      const res = await get<{ items: SmsLog[]; total: number; page: number; page_size: number }>(
        '/api/admin/sms/logs',
        { page, page_size: pageSize, phone: searchPhone, status: filterStatus, provider: filterProvider },
      );
      setLogs(res.items || []);
      setLogsPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取发送记录失败');
    } finally {
      setLogsLoading(false);
    }
  }, [searchPhone, filterStatus, filterProvider]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  useEffect(() => {
    if (activeTab === 'templates' || activeTab === 'test') fetchTemplates();
  }, [activeTab, fetchTemplates]);

  useEffect(() => {
    if (activeTab === 'logs') fetchLogs();
  }, [activeTab, fetchLogs]);

  const handleToggleProvider = (provider: 'tencent' | 'aliyun', checked: boolean) => {
    const otherEnabled = provider === 'tencent' ? aliyunEnabled : tencentEnabled;
    if (checked && otherEnabled) {
      Modal.confirm({
        title: '切换服务商',
        content: '切换服务商将禁用当前已启用的服务商，是否继续？',
        onOk: () => {
          if (provider === 'tencent') {
            setTencentEnabled(true);
            setAliyunEnabled(false);
          } else {
            setAliyunEnabled(true);
            setTencentEnabled(false);
          }
        },
      });
    } else {
      if (provider === 'tencent') setTencentEnabled(checked);
      else setAliyunEnabled(checked);
    }
  };

  const handleSaveTencent = async () => {
    try {
      const values = await tencentForm.validateFields();
      setTencentSaving(true);
      const payload: Record<string, any> = { provider: 'tencent', is_active: tencentEnabled };
      for (const [k, v] of Object.entries(values)) {
        if (v !== undefined && v !== '') payload[k] = v;
      }
      await put('/api/admin/sms/config', payload);
      message.success('腾讯云配置保存成功');
      fetchConfig();
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setTencentSaving(false);
    }
  };

  const handleSaveAliyun = async () => {
    try {
      const values = await aliyunForm.validateFields();
      setAliyunSaving(true);
      const payload: Record<string, any> = { provider: 'aliyun', is_active: aliyunEnabled };
      for (const [k, v] of Object.entries(values)) {
        if (v !== undefined && v !== '') payload[k] = v;
      }
      await put('/api/admin/sms/config', payload);
      message.success('阿里云配置保存成功');
      fetchConfig();
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setAliyunSaving(false);
    }
  };

  const handleOpenTemplateModal = (record?: SmsTemplate) => {
    setEditingTemplate(record || null);
    templateForm.resetFields();
    if (record) {
      templateForm.setFieldsValue({
        name: record.name,
        provider: record.provider,
        template_id: record.template_id,
        content: record.content,
        sign_name: record.sign_name,
        scene: record.scene,
        variables: Array.isArray(record.variables) ? record.variables : [],
        status: record.status,
      });
    }
    setTemplateModalOpen(true);
  };

  const handleSaveTemplate = async () => {
    try {
      const values = await templateForm.validateFields();
      setTemplateSaving(true);
      const payload = {
        ...values,
        variables: Array.isArray(values.variables) && values.variables.length > 0
          ? values.variables.map((v: any) => ({ name: v.name, description: v.description || '', default_value: v.default_value || '' }))
          : null,
      };
      if (editingTemplate) {
        await put(`/api/admin/sms/templates/${editingTemplate.id}`, payload);
        message.success('模板更新成功');
      } else {
        await post('/api/admin/sms/templates', payload);
        message.success('模板创建成功');
      }
      setTemplateModalOpen(false);
      fetchTemplates(templatesPagination.current, templatesPagination.pageSize);
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setTemplateSaving(false);
    }
  };

  const handleDeleteTemplate = async (id: number) => {
    try {
      await del(`/api/admin/sms/templates/${id}`);
      message.success('模板删除成功');
      fetchTemplates(templatesPagination.current, templatesPagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '删除失败';
      message.error(typeof detail === 'string' ? detail : '删除失败');
    }
  };

  const buildTemplateParams = (): { params: string[]; paramPairs: { name: string; value: string }[] } | null => {
    if (!selectedTemplate) return null;
    const vars = selectedTemplate.variables;
    if (inputMode === 'auto') {
      if (!Array.isArray(vars) || vars.length === 0) return null;
      const paramPairs: { name: string; value: string }[] = [];
      const params: string[] = [];
      const formVars = testForm.getFieldValue('template_vars') || {};
      for (const v of vars) {
        const val = formVars[v.name] ?? v.default_value ?? '';
        params.push(String(val));
        paramPairs.push({ name: v.name, value: String(val) });
      }
      return { params, paramPairs };
    } else {
      const raw = testForm.getFieldValue('advanced_params') || '';
      const params = raw ? raw.split(',').map((s: string) => s.trim()) : [];
      const paramPairs = params.map((val: string, idx: number) => ({
        name: Array.isArray(vars) && vars[idx] ? vars[idx].name : `参数${idx + 1}`,
        value: val,
      }));
      return { params, paramPairs };
    }
  };

  const generatePreviewContent = (content: string, params: string[]): string => {
    let result = content;
    params.forEach((val, idx) => {
      result = result.replace(new RegExp(`\\{${idx + 1}\\}`, 'g'), val);
    });
    return result;
  };

  const handlePreviewAndSend = async () => {
    try {
      await testForm.validateFields(['provider', 'phone', 'template_select']);
      if (!selectedTemplate) {
        message.warning('请选择短信模板');
        return;
      }
      const result = buildTemplateParams();
      if (inputMode === 'auto') {
        const vars = selectedTemplate.variables;
        if (!Array.isArray(vars) || vars.length === 0) {
          message.warning('该模板未配置变量信息，请切换到高级输入模式');
          return;
        }
        if (result) {
          const missing = result.paramPairs.filter(p => !p.value);
          if (missing.length > 0) {
            message.warning(`请填写变量: ${missing.map(m => m.name).join(', ')}`);
            return;
          }
        }
      } else {
        const vars = selectedTemplate.variables;
        if (result && Array.isArray(vars) && vars.length > 0 && result.params.length !== vars.length) {
          message.warning(`参数个数不匹配，模板需要 ${vars.length} 个参数，当前输入 ${result.params.length} 个`);
          return;
        }
      }

      const params = result?.params || [];
      const paramPairs = result?.paramPairs || [];
      const previewContent = generatePreviewContent(selectedTemplate.content, params);

      setPreviewData({
        phone: testForm.getFieldValue('phone'),
        provider: testForm.getFieldValue('provider'),
        templateName: selectedTemplate.name,
        templateId: selectedTemplate.template_id,
        params: paramPairs,
        previewContent,
      });
      setPreviewModalOpen(true);
    } catch {
      // validation error
    }
  };

  const handleConfirmSend = async () => {
    if (!previewData || !selectedTemplate) return;
    setPreviewModalOpen(false);
    setTestSending(true);
    setTestResult(null);
    try {
      const res = await post<{ message: string; success: boolean; params_used?: string[]; preview_content?: string }>('/api/admin/sms/test', {
        phone: previewData.phone,
        provider: previewData.provider,
        template_id: selectedTemplate.template_id,
        template_params: previewData.params.map(p => p.value),
      });
      setTestResult({
        success: res.success,
        message: res.message,
        params_used: res.params_used,
        preview_content: res.preview_content || previewData.previewContent,
      });
      if (res.success) message.success('测试短信发送成功');
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '发送失败';
      setTestResult({
        success: false,
        message: typeof detail === 'string' ? detail : '发送失败',
        params_used: previewData.params.map(p => p.value),
        preview_content: previewData.previewContent,
      });
    } finally {
      setTestSending(false);
    }
  };

  const providerLabel = (v: string) => (v === 'tencent' ? '腾讯云' : v === 'aliyun' ? '阿里云' : v);
  const sceneLabel = (v: string) => {
    const map: Record<string, string> = { verification: '验证码', notification: '通知', marketing: '营销', other: '其他' };
    return map[v] || v;
  };
  const sceneColor = (v: string) => {
    const map: Record<string, string> = { verification: 'blue', notification: 'green', marketing: 'orange', other: 'default' };
    return map[v] || 'default';
  };

  const templateColumns = [
    { title: '模板名称', dataIndex: 'name', key: 'name', width: 140 },
    {
      title: '服务商', dataIndex: 'provider', key: 'provider', width: 100,
      render: (v: string) => <Tag color={v === 'tencent' ? 'blue' : 'orange'}>{providerLabel(v)}</Tag>,
    },
    { title: '模板ID', dataIndex: 'template_id', key: 'template_id', width: 140 },
    { title: '模板内容', dataIndex: 'content', key: 'content', ellipsis: true },
    { title: '签名名称', dataIndex: 'sign_name', key: 'sign_name', width: 120 },
    {
      title: '用途场景', dataIndex: 'scene', key: 'scene', width: 100,
      render: (v: string) => <Tag color={sceneColor(v)}>{sceneLabel(v)}</Tag>,
    },
    {
      title: '变量说明', dataIndex: 'variables', key: 'variables', width: 160,
      render: (v: TemplateVariable[] | null) => {
        if (Array.isArray(v) && v.length > 0) {
          return v.map(item => item.name).join(', ');
        }
        return <Tag color="warning">未配置</Tag>;
      },
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: boolean) => <Tag color={v ? 'green' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    {
      title: '创建时间', dataIndex: 'created_at', key: 'created_at', width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    {
      title: '操作', key: 'action', width: 140,
      render: (_: any, record: SmsTemplate) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenTemplateModal(record)}>编辑</Button>
          <Popconfirm title="确定删除此模板？" onConfirm={() => handleDeleteTemplate(record.id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const logsColumns = [
    {
      title: '发送时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    { title: '手机号', dataIndex: 'phone', key: 'phone', width: 130 },
    { title: '验证码', dataIndex: 'code', key: 'code', width: 100 },
    {
      title: '服务商', dataIndex: 'provider', key: 'provider', width: 100,
      render: (v: string) => <Tag color={v === 'tencent' ? 'blue' : 'orange'}>{providerLabel(v)}</Tag>,
    },
    {
      title: '发送状态', dataIndex: 'status', key: 'status', width: 100,
      render: (v: string) => <Tag color={v === 'success' ? 'green' : 'red'}>{v === 'success' ? '成功' : '失败'}</Tag>,
    },
    {
      title: '失败原因', dataIndex: 'error_message', key: 'error_message', width: 200,
      render: (v: string) => v || '-',
    },
    {
      title: '测试发送', dataIndex: 'is_test', key: 'is_test', width: 90,
      render: (v: boolean) => v ? <Tag color="blue">测试</Tag> : <Tag>正常</Tag>,
    },
  ];

  const tabItems = [
    {
      key: 'config',
      label: <Space><SettingOutlined />短信配置</Space>,
      children: (
        <Spin spinning={configLoading}>
          <Card style={{ borderRadius: 12, maxWidth: 640, marginBottom: 24 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <Title level={5} style={{ margin: 0 }}>腾讯云短信配置</Title>
              <Switch checked={tencentEnabled} onChange={(v) => handleToggleProvider('tencent', v)} />
            </div>
            <Form form={tencentForm} layout="vertical">
              <Form.Item label="SecretID" name="secret_id" rules={[{ required: true, message: '请输入SecretID' }]}>
                <Input placeholder="请输入SecretID" />
              </Form.Item>
              <Form.Item label="SecretKey" name="secret_key">
                <Input.Password placeholder={tencentHasSecret ? '已设置（重新输入将覆盖）' : '未设置'} />
              </Form.Item>
              <Form.Item label="SDK AppID" name="sdk_app_id" rules={[{ required: true, message: '请输入SDK AppID' }]}>
                <Input placeholder="请输入SDK AppID" />
              </Form.Item>
              <Form.Item label="短信签名" name="sign_name" rules={[{ required: true, message: '请输入短信签名' }]}>
                <Input placeholder="请输入短信签名" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveTencent} loading={tencentSaving}>
                  保存腾讯云配置
                </Button>
              </Form.Item>
            </Form>
          </Card>

          <Card style={{ borderRadius: 12, maxWidth: 640 }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <Title level={5} style={{ margin: 0 }}>阿里云短信配置</Title>
              <Switch checked={aliyunEnabled} onChange={(v) => handleToggleProvider('aliyun', v)} />
            </div>
            <Form form={aliyunForm} layout="vertical">
              <Form.Item label="AccessKey ID" name="access_key_id" rules={[{ required: true, message: '请输入AccessKey ID' }]}>
                <Input placeholder="请输入AccessKey ID" />
              </Form.Item>
              <Form.Item label="AccessKey Secret" name="access_key_secret">
                <Input.Password placeholder={aliyunHasSecret ? '已设置（重新输入将覆盖）' : '未设置'} />
              </Form.Item>
              <Form.Item label="短信签名" name="sign_name" rules={[{ required: true, message: '请输入短信签名' }]}>
                <Input placeholder="请输入短信签名" />
              </Form.Item>
              <Form.Item>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveAliyun} loading={aliyunSaving}>
                  保存阿里云配置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Spin>
      ),
    },
    {
      key: 'templates',
      label: <Space><FileTextOutlined />短信模板</Space>,
      children: (
        <div>
          <Space style={{ marginBottom: 16 }} wrap>
            <Select
              placeholder="服务商"
              value={templateProvider || undefined}
              onChange={(v) => setTemplateProvider(v || '')}
              allowClear
              style={{ width: 140 }}
              options={[
                { label: '全部', value: '' },
                { label: '腾讯云', value: 'tencent' },
                { label: '阿里云', value: 'aliyun' },
              ]}
            />
            <Select
              placeholder="用途场景"
              value={templateScene || undefined}
              onChange={(v) => setTemplateScene(v || '')}
              allowClear
              style={{ width: 140 }}
              options={[
                { label: '全部', value: '' },
                { label: '验证码', value: 'verification' },
                { label: '通知', value: 'notification' },
                { label: '营销', value: 'marketing' },
                { label: '其他', value: 'other' },
              ]}
            />
            <Input
              placeholder="搜索模板名称"
              prefix={<SearchOutlined />}
              value={templateSearch}
              onChange={(e) => setTemplateSearch(e.target.value)}
              onPressEnter={() => fetchTemplates(1, templatesPagination.pageSize)}
              style={{ width: 200 }}
              allowClear
            />
            <Button type="primary" onClick={() => fetchTemplates(1, templatesPagination.pageSize)}>搜索</Button>
            <Button onClick={() => { setTemplateProvider(''); setTemplateScene(''); setTemplateSearch(''); setTimeout(() => fetchTemplates(1, templatesPagination.pageSize), 0); }}>重置</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenTemplateModal()}>新增模板</Button>
          </Space>
          <Table
            columns={templateColumns}
            dataSource={templates}
            rowKey="id"
            loading={templatesLoading}
            pagination={{
              current: templatesPagination.current,
              pageSize: templatesPagination.pageSize,
              total: templatesPagination.total,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 条`,
              onChange: (page, pageSize) => fetchTemplates(page, pageSize),
            }}
            scroll={{ x: 1200 }}
          />
          <Modal
            title={editingTemplate ? '编辑短信模板' : '新增短信模板'}
            open={templateModalOpen}
            onOk={handleSaveTemplate}
            onCancel={() => setTemplateModalOpen(false)}
            confirmLoading={templateSaving}
            destroyOnClose
            width={600}
          >
            <Form form={templateForm} layout="vertical" initialValues={{ status: true, provider: 'tencent', scene: 'verification' }}>
              <Form.Item label="模板名称" name="name" rules={[{ required: true, message: '请输入模板名称' }]}>
                <Input placeholder="请输入模板名称" />
              </Form.Item>
              <Form.Item label="服务商" name="provider" rules={[{ required: true, message: '请选择服务商' }]}>
                <Select options={[{ label: '腾讯云', value: 'tencent' }, { label: '阿里云', value: 'aliyun' }]} />
              </Form.Item>
              <Form.Item label="模板ID" name="template_id" rules={[{ required: true, message: '请输入模板ID' }]}>
                <Input placeholder="请输入模板ID" />
              </Form.Item>
              <Form.Item label="模板内容" name="content" rules={[{ required: true, message: '请输入模板内容' }]}>
                <Input.TextArea rows={3} placeholder="请输入模板内容" />
              </Form.Item>
              <Form.Item label="签名名称" name="sign_name" rules={[{ required: true, message: '请输入签名名称' }]}>
                <Input placeholder="请输入签名名称" />
              </Form.Item>
              <Form.Item label="用途场景" name="scene" rules={[{ required: true, message: '请选择用途场景' }]}>
                <Select options={[
                  { label: '验证码', value: 'verification' },
                  { label: '通知', value: 'notification' },
                  { label: '营销', value: 'marketing' },
                  { label: '其他', value: 'other' },
                ]} />
              </Form.Item>
              <Form.Item label="模板变量配置">
                <Form.List name="variables">
                  {(fields, { add, remove }) => (
                    <>
                      {fields.map((field, index) => (
                        <Space key={field.key} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                          <span style={{ color: '#999', minWidth: 32 }}>{`{${index + 1}}`}</span>
                          <Form.Item
                            {...field}
                            name={[field.name, 'name']}
                            rules={[{ required: true, message: '请输入变量名称' }]}
                            style={{ marginBottom: 0 }}
                          >
                            <Input placeholder="变量名称" style={{ width: 120 }} />
                          </Form.Item>
                          <Form.Item {...field} name={[field.name, 'description']} style={{ marginBottom: 0 }}>
                            <Input placeholder="变量说明（选填）" style={{ width: 140 }} />
                          </Form.Item>
                          <Form.Item {...field} name={[field.name, 'default_value']} style={{ marginBottom: 0 }}>
                            <Input placeholder="默认值（选填）" style={{ width: 120 }} />
                          </Form.Item>
                          <MinusCircleOutlined onClick={() => remove(field.name)} style={{ color: '#ff4d4f' }} />
                        </Space>
                      ))}
                      <Button type="dashed" onClick={() => add()} block icon={<PlusOutlined />}>
                        添加变量
                      </Button>
                    </>
                  )}
                </Form.List>
              </Form.Item>
              <Form.Item label="状态" name="status" valuePropName="checked">
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </Form>
          </Modal>
        </div>
      ),
    },
    {
      key: 'logs',
      label: <Space><UnorderedListOutlined />发送记录</Space>,
      children: (
        <div>
          <Space style={{ marginBottom: 16 }} wrap>
            <Input
              placeholder="搜索手机号"
              prefix={<SearchOutlined />}
              value={searchPhone}
              onChange={(e) => setSearchPhone(e.target.value)}
              onPressEnter={() => fetchLogs(1, logsPagination.pageSize)}
              style={{ width: 200 }}
              allowClear
            />
            <Select
              placeholder="服务商"
              value={filterProvider || undefined}
              onChange={(v) => setFilterProvider(v || '')}
              allowClear
              style={{ width: 140 }}
              options={[
                { label: '全部', value: '' },
                { label: '腾讯云', value: 'tencent' },
                { label: '阿里云', value: 'aliyun' },
              ]}
            />
            <Select
              placeholder="发送状态"
              value={filterStatus || undefined}
              onChange={(v) => setFilterStatus(v || '')}
              allowClear
              style={{ width: 140 }}
              options={[
                { label: '全部', value: '' },
                { label: '成功', value: 'success' },
                { label: '失败', value: 'failed' },
              ]}
            />
            <Button type="primary" onClick={() => fetchLogs(1, logsPagination.pageSize)}>搜索</Button>
            <Button onClick={() => { setSearchPhone(''); setFilterStatus(''); setFilterProvider(''); setTimeout(() => fetchLogs(1, logsPagination.pageSize), 0); }}>重置</Button>
          </Space>
          <Table
            columns={logsColumns}
            dataSource={logs}
            rowKey="id"
            loading={logsLoading}
            pagination={{
              current: logsPagination.current,
              pageSize: logsPagination.pageSize,
              total: logsPagination.total,
              showSizeChanger: true,
              showQuickJumper: true,
              showTotal: (total) => `共 ${total} 条`,
              onChange: (page, pageSize) => fetchLogs(page, pageSize),
            }}
            scroll={{ x: 900 }}
          />
        </div>
      ),
    },
    {
      key: 'test',
      label: <Space><SendOutlined />测试发送</Space>,
      children: (
        <Card style={{ borderRadius: 12, maxWidth: 560 }}>
          <Form form={testForm} layout="vertical">
            <Form.Item label="服务商" name="provider" rules={[{ required: true, message: '请选择服务商' }]}>
              <Select
                placeholder="请选择服务商"
                options={[
                  { label: '腾讯云', value: 'tencent' },
                  { label: '阿里云', value: 'aliyun' },
                ]}
              />
            </Form.Item>
            <Form.Item
              label="手机号"
              name="phone"
              rules={[
                { required: true, message: '请输入手机号' },
                { pattern: /^1\d{10}$/, message: '请输入正确的手机号' },
              ]}
            >
              <Input placeholder="请输入接收手机号" maxLength={11} />
            </Form.Item>
            <Form.Item label="短信模板" name="template_select" rules={[{ required: true, message: '请选择短信模板' }]}>
              <Select
                placeholder="请选择短信模板"
                showSearch
                optionFilterProp="label"
                onChange={(val: number) => {
                  const tpl = templates.find(t => t.id === val) || null;
                  setSelectedTemplate(tpl);
                  setTestResult(null);
                  setInputMode('auto');
                }}
                options={templates.map(t => ({
                  label: `${t.name}（${providerLabel(t.provider)} - ${t.template_id}）`,
                  value: t.id,
                }))}
              />
            </Form.Item>

            {selectedTemplate && (
              <Form.Item
                label={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
                    <span>{`模板参数（${inputMode === 'auto' ? '自动模式' : '高级模式'}）`}</span>
                    <Button
                      type="link"
                      size="small"
                      icon={<SwapOutlined />}
                      onClick={() => setInputMode(inputMode === 'auto' ? 'advanced' : 'auto')}
                      style={{ padding: 0 }}
                    >
                      {inputMode === 'auto' ? '切换到高级输入' : '切换到自动模式'}
                    </Button>
                  </div>
                }
              >
                {inputMode === 'auto' ? (
                  Array.isArray(selectedTemplate.variables) && selectedTemplate.variables.length > 0 ? (
                    <div style={{ border: '1px solid #f0f0f0', borderRadius: 8, padding: 16 }}>
                      {selectedTemplate.variables.map((v, idx) => (
                        <Form.Item
                          key={v.name}
                          label={<span>{`{${idx + 1}} ${v.name}`}{v.description && <span style={{ color: '#999', marginLeft: 8, fontSize: 12 }}>({v.description})</span>}</span>}
                          name={['template_vars', v.name]}
                          initialValue={v.default_value || ''}
                          style={{ marginBottom: idx < (selectedTemplate.variables?.length || 0) - 1 ? 12 : 0 }}
                        >
                          <Input placeholder={v.description || `请输入${v.name}`} />
                        </Form.Item>
                      ))}
                    </div>
                  ) : (
                    <Alert
                      type="warning"
                      message="该模板尚未配置变量信息，请先在模板管理中补全，或切换到高级输入模式"
                      showIcon
                    />
                  )
                ) : (
                  <Form.Item name="advanced_params" noStyle>
                    <Input.TextArea
                      rows={3}
                      placeholder="请按英文逗号分隔输入参数值，如：123456,5"
                    />
                  </Form.Item>
                )}
              </Form.Item>
            )}

            <Form.Item>
              <Button type="primary" icon={<EyeOutlined />} onClick={handlePreviewAndSend} loading={testSending}>
                发送测试短信
              </Button>
            </Form.Item>
          </Form>

          {testResult && (
            <div style={{ marginTop: 16 }}>
              <Alert
                type={testResult.success ? 'success' : 'error'}
                message={testResult.success ? '发送成功' : '发送失败'}
                description={testResult.message}
                icon={testResult.success ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
                showIcon
              />
              {previewData && (
                <div style={{
                  marginTop: 12,
                  border: `1px solid ${testResult.success ? '#b7eb8f' : '#ffa39e'}`,
                  borderRadius: 8,
                  padding: 16,
                  background: testResult.success ? '#f6ffed' : '#fff2f0',
                }}>
                  <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>参数列表：</Typography.Text>
                  <div style={{ marginBottom: 12 }}>
                    {previewData.params.map((p, idx) => (
                      <Tag key={idx} style={{ marginBottom: 4 }}>{`${p.name}: ${p.value}`}</Tag>
                    ))}
                  </div>
                  <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>短信预览内容：</Typography.Text>
                  <div style={{
                    background: '#fff',
                    border: '1px solid #d9d9d9',
                    borderRadius: 6,
                    padding: 12,
                    color: '#333',
                    lineHeight: 1.6,
                  }}>
                    {testResult.preview_content || previewData.previewContent}
                  </div>
                </div>
              )}
            </div>
          )}

          <Modal
            title="发送确认"
            open={previewModalOpen}
            onOk={handleConfirmSend}
            onCancel={() => setPreviewModalOpen(false)}
            okText="确认发送"
            cancelText="取消"
            width={480}
          >
            {previewData && (
              <div>
                <div style={{ marginBottom: 12 }}>
                  <Typography.Text type="secondary">收信手机号：</Typography.Text>
                  <Typography.Text strong>{previewData.phone}</Typography.Text>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <Typography.Text type="secondary">服务商：</Typography.Text>
                  <Typography.Text>{providerLabel(previewData.provider)}</Typography.Text>
                </div>
                <div style={{ marginBottom: 12 }}>
                  <Typography.Text type="secondary">模板名称：</Typography.Text>
                  <Typography.Text>{previewData.templateName}</Typography.Text>
                  <Typography.Text type="secondary" style={{ marginLeft: 8 }}>({previewData.templateId})</Typography.Text>
                </div>
                {previewData.params.length > 0 && (
                  <div style={{ marginBottom: 12 }}>
                    <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>模板参数：</Typography.Text>
                    {previewData.params.map((p, idx) => (
                      <div key={idx} style={{ paddingLeft: 16, marginBottom: 2 }}>
                        <Typography.Text>{`{${idx + 1}} ${p.name}：`}</Typography.Text>
                        <Typography.Text strong>{p.value}</Typography.Text>
                      </div>
                    ))}
                  </div>
                )}
                <div style={{ marginBottom: 0 }}>
                  <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>短信预览内容：</Typography.Text>
                  <div style={{
                    background: '#f5f5f5',
                    borderRadius: 6,
                    padding: 12,
                    border: '1px solid #e8e8e8',
                    lineHeight: 1.6,
                  }}>
                    {previewData.previewContent}
                  </div>
                </div>
              </div>
            )}
          </Modal>
        </Card>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>短信管理</Title>
      <Tabs items={tabItems} activeKey={activeTab} onChange={setActiveTab} />
    </div>
  );
}
