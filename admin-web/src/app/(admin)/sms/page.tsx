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

interface SmsTemplate {
  id: number;
  name: string;
  provider: string;
  template_id: string;
  content: string;
  sign_name: string;
  scene: string;
  variables: string;
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
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

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
    if (activeTab === 'templates') fetchTemplates();
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
        variables: record.variables,
        status: record.status,
      });
    }
    setTemplateModalOpen(true);
  };

  const handleSaveTemplate = async () => {
    try {
      const values = await templateForm.validateFields();
      setTemplateSaving(true);
      if (editingTemplate) {
        await put(`/api/admin/sms/templates/${editingTemplate.id}`, values);
        message.success('模板更新成功');
      } else {
        await post('/api/admin/sms/templates', values);
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

  const handleTestSend = async () => {
    try {
      const values = await testForm.validateFields();
      setTestSending(true);
      setTestResult(null);
      const res = await post<{ message: string; success: boolean }>('/api/admin/sms/test', {
        phone: values.phone,
        provider: values.provider,
        ...(values.template_id ? { template_id: values.template_id } : {}),
      });
      setTestResult({ success: res.success, message: res.message });
      if (res.success) message.success('测试短信发送成功');
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '发送失败';
      setTestResult({ success: false, message: typeof detail === 'string' ? detail : '发送失败' });
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
    { title: '变量说明', dataIndex: 'variables', key: 'variables', width: 160, ellipsis: true },
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
              <Form.Item label="变量说明" name="variables">
                <Input placeholder="如: {code}=验证码, {name}=用户名" />
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
        <Card style={{ borderRadius: 12, maxWidth: 480 }}>
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
            <Form.Item label="模板ID（可选）" name="template_id">
              <Input placeholder="留空则使用配置中的默认模板ID" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" icon={<SendOutlined />} onClick={handleTestSend} loading={testSending}>
                发送测试短信
              </Button>
            </Form.Item>
          </Form>
          {testResult && (
            <Alert
              type={testResult.success ? 'success' : 'error'}
              message={testResult.success ? '发送成功' : '发送失败'}
              description={testResult.message}
              icon={testResult.success ? <CheckCircleOutlined /> : <ExclamationCircleOutlined />}
              showIcon
              style={{ marginTop: 16 }}
            />
          )}
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
