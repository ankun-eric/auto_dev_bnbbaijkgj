'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Tabs, Form, Input, InputNumber, Switch, Button, Table, Tag, Space, Card, Alert, Spin, Select, message, Typography,
} from 'antd';
import {
  SettingOutlined, UnorderedListOutlined, SendOutlined, SaveOutlined,
  SearchOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { get, put, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { TextArea } = Input;

interface EmailConfig {
  enable_email_notify: boolean;
  smtp_host: string;
  smtp_port: number;
  smtp_user: string;
  has_smtp_password: boolean;
}

interface EmailLog {
  id: number;
  to_email: string;
  subject: string;
  status: string;
  error_message: string;
  is_test: boolean;
  created_at: string;
}

export default function EmailNotifyPage() {
  const [activeTab, setActiveTab] = useState('config');

  // Config state
  const [configForm] = Form.useForm();
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [hasSmtpPassword, setHasSmtpPassword] = useState(false);

  // Logs state
  const [logs, setLogs] = useState<EmailLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsPagination, setLogsPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [searchToEmail, setSearchToEmail] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  // Test state
  const [testForm] = Form.useForm();
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const fetchConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const res = await get<EmailConfig>('/api/admin/email-notify/config');
      setHasSmtpPassword(!!res.has_smtp_password);
      configForm.setFieldsValue({
        enable_email_notify: !!res.enable_email_notify,
        smtp_host: res.smtp_host || '',
        smtp_port: res.smtp_port || 465,
        smtp_user: res.smtp_user || '',
      });
    } catch {
      // config not yet set
    } finally {
      setConfigLoading(false);
    }
  }, [configForm]);

  const fetchLogs = useCallback(async (page = 1, pageSize = 20) => {
    setLogsLoading(true);
    try {
      const res = await get<{ items: EmailLog[]; total: number; page: number; page_size: number }>(
        '/api/admin/email-notify/logs',
        { page, page_size: pageSize, to_email: searchToEmail, status: filterStatus },
      );
      setLogs(res.items || []);
      setLogsPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取发送记录失败');
    } finally {
      setLogsLoading(false);
    }
  }, [searchToEmail, filterStatus]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  useEffect(() => {
    if (activeTab === 'logs') fetchLogs();
  }, [activeTab, fetchLogs]);

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      const payload: Record<string, any> = {};
      for (const [k, v] of Object.entries(values)) {
        if (v !== undefined && v !== '') payload[k] = v;
      }
      payload.enable_email_notify = !!values.enable_email_notify;
      payload.smtp_port = values.smtp_port;
      await put('/api/admin/email-notify/config', payload);
      message.success('邮件配置保存成功');
      fetchConfig();
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setConfigSaving(false);
    }
  };

  const handleTestSend = async () => {
    try {
      const values = await testForm.validateFields();
      setTestSending(true);
      setTestResult(null);
      const res = await post<{ message: string; success: boolean }>('/api/admin/email-notify/test', {
        to_email: values.to_email,
        subject: values.subject,
        ...(values.content ? { content: values.content } : {}),
      });
      setTestResult({ success: res.success, message: res.message });
      if (res.success) message.success('测试邮件发送成功');
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '发送失败';
      setTestResult({ success: false, message: typeof detail === 'string' ? detail : '发送失败' });
    } finally {
      setTestSending(false);
    }
  };

  const logsColumns = [
    {
      title: '发送时间', dataIndex: 'created_at', key: 'created_at', width: 180,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    { title: '收件人', dataIndex: 'to_email', key: 'to_email', width: 200 },
    { title: '邮件主题', dataIndex: 'subject', key: 'subject', ellipsis: true },
    {
      title: '发送状态', dataIndex: 'status', key: 'status', width: 100,
      render: (v: string) => <Tag color={v === 'success' ? 'green' : 'red'}>{v === 'success' ? '成功' : '失败'}</Tag>,
    },
    {
      title: '失败原因', dataIndex: 'error_message', key: 'error_message', width: 200,
      render: (v: string) => v || '-',
    },
    {
      title: '测试邮件', dataIndex: 'is_test', key: 'is_test', width: 90,
      render: (v: boolean) => v ? <Tag color="blue">测试</Tag> : <Tag>正常</Tag>,
    },
  ];

  const tabItems = [
    {
      key: 'config',
      label: <Space><SettingOutlined />邮件配置</Space>,
      children: (
        <Spin spinning={configLoading}>
          <Card style={{ borderRadius: 12, maxWidth: 640 }}>
            <Form form={configForm} layout="vertical" initialValues={{ enable_email_notify: false, smtp_port: 465 }}>
              <Form.Item label="启用邮件通知" name="enable_email_notify" valuePropName="checked">
                <Switch />
              </Form.Item>
              <Form.Item label="SMTP服务器" name="smtp_host" rules={[{ required: true, message: '请输入SMTP服务器' }]}>
                <Input placeholder="smtp.example.com" />
              </Form.Item>
              <Form.Item label="SMTP端口" name="smtp_port" rules={[{ required: true, message: '请输入SMTP端口' }]}>
                <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="465" />
              </Form.Item>
              <Form.Item label="SMTP用户名" name="smtp_user" rules={[{ required: true, message: '请输入SMTP用户名' }]}>
                <Input placeholder="请输入SMTP用户名" />
              </Form.Item>
              <Form.Item label="SMTP密码" name="smtp_password">
                <Input.Password placeholder={hasSmtpPassword ? '已设置（重新输入将覆盖）' : '请输入SMTP密码'} />
              </Form.Item>
              <Form.Item>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveConfig} loading={configSaving}>
                  保存配置
                </Button>
              </Form.Item>
            </Form>
          </Card>
        </Spin>
      ),
    },
    {
      key: 'logs',
      label: <Space><UnorderedListOutlined />发送记录</Space>,
      children: (
        <div>
          <Space style={{ marginBottom: 16 }} wrap>
            <Input
              placeholder="搜索收件人邮箱"
              prefix={<SearchOutlined />}
              value={searchToEmail}
              onChange={(e) => setSearchToEmail(e.target.value)}
              onPressEnter={() => fetchLogs(1, logsPagination.pageSize)}
              style={{ width: 240 }}
              allowClear
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
            <Button onClick={() => { setSearchToEmail(''); setFilterStatus(''); setTimeout(() => fetchLogs(1, logsPagination.pageSize), 0); }}>重置</Button>
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
          <Form form={testForm} layout="vertical" initialValues={{ subject: '测试邮件', content: '这是一封测试邮件，用于验证邮件配置是否正确。' }}>
            <Form.Item
              label="收件人邮箱"
              name="to_email"
              rules={[
                { required: true, message: '请输入收件人邮箱' },
                { type: 'email', message: '请输入正确的邮箱格式' },
              ]}
            >
              <Input placeholder="请输入收件人邮箱" />
            </Form.Item>
            <Form.Item label="邮件主题" name="subject" rules={[{ required: true, message: '请输入邮件主题' }]}>
              <Input placeholder="请输入邮件主题" />
            </Form.Item>
            <Form.Item label="邮件内容" name="content">
              <TextArea rows={4} placeholder="请输入邮件内容（可选）" />
            </Form.Item>
            <Form.Item>
              <Button type="primary" icon={<SendOutlined />} onClick={handleTestSend} loading={testSending}>
                发送测试邮件
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
      <Title level={4} style={{ marginBottom: 24 }}>邮件通知管理</Title>
      <Tabs items={tabItems} activeKey={activeTab} onChange={setActiveTab} />
    </div>
  );
}
