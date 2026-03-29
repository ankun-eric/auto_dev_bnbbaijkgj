'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Tabs, Form, Input, Button, Table, Tag, Space, Card, message, Typography, Select, Alert, Spin,
} from 'antd';
import {
  SettingOutlined, UnorderedListOutlined, SendOutlined, SaveOutlined,
  SearchOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { get, put, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

interface SmsConfig {
  id?: number;
  secret_id: string;
  sdk_app_id: string;
  sign_name: string;
  template_id: string;
  app_key: string;
  is_active: boolean;
  has_secret_key: boolean;
  created_at?: string;
  updated_at?: string;
}

interface SmsLog {
  id: number;
  phone: string;
  code: string;
  template_id: string;
  status: string;
  error_message: string;
  is_test: boolean;
  operator_id: number | null;
  created_at: string;
}

export default function SmsPage() {
  const [activeTab, setActiveTab] = useState('config');

  const [configForm] = Form.useForm();
  const [configLoading, setConfigLoading] = useState(false);
  const [configSaving, setConfigSaving] = useState(false);
  const [hasSecretKey, setHasSecretKey] = useState(false);

  const [logs, setLogs] = useState<SmsLog[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsPagination, setLogsPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [searchPhone, setSearchPhone] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('');

  const [testForm] = Form.useForm();
  const [testSending, setTestSending] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const fetchConfig = useCallback(async () => {
    setConfigLoading(true);
    try {
      const res = await get<SmsConfig>('/api/admin/sms/config');
      setHasSecretKey(!!res.has_secret_key);
      configForm.setFieldsValue({
        secret_id: res.secret_id || '',
        sdk_app_id: res.sdk_app_id || '',
        sign_name: res.sign_name || '',
        template_id: res.template_id || '',
        app_key: res.app_key || '',
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
      const res = await get<{ items: SmsLog[]; total: number; page: number; page_size: number }>(
        '/api/admin/sms/logs',
        { page, page_size: pageSize, phone: searchPhone, status: filterStatus },
      );
      setLogs(res.items || []);
      setLogsPagination({ current: res.page, pageSize: res.page_size, total: res.total });
    } catch {
      message.error('获取发送记录失败');
    } finally {
      setLogsLoading(false);
    }
  }, [searchPhone, filterStatus]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  useEffect(() => {
    if (activeTab === 'logs') {
      fetchLogs();
    }
  }, [activeTab, fetchLogs]);

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      setConfigSaving(true);
      const payload: Record<string, string> = {};
      for (const [k, v] of Object.entries(values)) {
        if (v !== undefined && v !== '') {
          payload[k] = v as string;
        }
      }
      await put('/api/admin/sms/config', payload);
      message.success('短信配置保存成功');
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
      const res = await post<{ message: string; success: boolean }>('/api/admin/sms/test', {
        phone: values.phone,
        ...(values.template_id ? { template_id: values.template_id } : {}),
      });
      setTestResult({ success: res.success, message: res.message });
      if (res.success) {
        message.success('测试短信发送成功');
      }
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '发送失败';
      setTestResult({ success: false, message: typeof detail === 'string' ? detail : '发送失败' });
    } finally {
      setTestSending(false);
    }
  };

  const logsColumns = [
    {
      title: '发送时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm:ss'),
    },
    { title: '手机号', dataIndex: 'phone', key: 'phone', width: 130 },
    { title: '验证码', dataIndex: 'code', key: 'code', width: 100 },
    {
      title: '发送状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => (
        <Tag color={v === 'success' ? 'green' : 'red'}>
          {v === 'success' ? '成功' : '失败'}
        </Tag>
      ),
    },
    {
      title: '失败原因',
      dataIndex: 'error_message',
      key: 'error_message',
      width: 200,
      render: (v: string) => v || '-',
    },
    {
      title: '测试发送',
      dataIndex: 'is_test',
      key: 'is_test',
      width: 90,
      render: (v: boolean) => v ? <Tag color="blue">测试</Tag> : <Tag>正常</Tag>,
    },
  ];

  const tabItems = [
    {
      key: 'config',
      label: <Space><SettingOutlined />短信配置</Space>,
      children: (
        <Spin spinning={configLoading}>
          <Card style={{ borderRadius: 12, maxWidth: 640 }}>
            <Form form={configForm} layout="vertical">
              <Form.Item label="SecretID" name="secret_id" rules={[{ required: true, message: '请输入SecretID' }]}>
                <Input placeholder="请输入SecretID" />
              </Form.Item>
              <Form.Item label="SecretKey" name="secret_key">
                <Input.Password
                  placeholder={hasSecretKey ? '已设置（重新输入将覆盖）' : '未设置'}
                />
              </Form.Item>
              <Form.Item label="SDK AppID" name="sdk_app_id" rules={[{ required: true, message: '请输入SDK AppID' }]}>
                <Input placeholder="请输入SDK AppID" />
              </Form.Item>
              <Form.Item label="短信签名" name="sign_name" rules={[{ required: true, message: '请输入短信签名' }]}>
                <Input placeholder="请输入短信签名" />
              </Form.Item>
              <Form.Item label="模板ID" name="template_id" rules={[{ required: true, message: '请输入模板ID' }]}>
                <Input placeholder="请输入短信模板ID" />
              </Form.Item>
              <Form.Item label="App Key" name="app_key">
                <Input.Password placeholder="请输入App Key" />
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
              placeholder="搜索手机号"
              prefix={<SearchOutlined />}
              value={searchPhone}
              onChange={(e) => setSearchPhone(e.target.value)}
              onPressEnter={() => fetchLogs(1, logsPagination.pageSize)}
              style={{ width: 200 }}
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
            <Button onClick={() => { setSearchPhone(''); setFilterStatus(''); setTimeout(() => fetchLogs(1, logsPagination.pageSize), 0); }}>重置</Button>
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
            scroll={{ x: 800 }}
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
