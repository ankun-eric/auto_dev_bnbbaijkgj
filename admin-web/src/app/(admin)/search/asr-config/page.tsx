'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Card, Form, Input, Button, Switch, Alert, Space, Spin, message,
} from 'antd';
import { SaveOutlined, ApiOutlined, SoundOutlined } from '@ant-design/icons';
import { get, put, post } from '@/lib/api';

const { Title, Text } = Typography;

interface AsrConfig {
  id: number;
  provider: string;
  app_id: string;
  secret_id: string;
  secret_key_encrypted: string | null;
  is_enabled: boolean;
  supported_dialects: string | null;
  updated_at: string | null;
}

export default function AsrConfigPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [hasSecretKey, setHasSecretKey] = useState(false);
  const [configSaved, setConfigSaved] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<AsrConfig>('/api/admin/search/asr-config');
      form.setFieldsValue({
        app_id: res.app_id || '',
        secret_id: res.secret_id || '',
        is_enabled: !!res.is_enabled,
      });
      setHasSecretKey(!!res.secret_key_encrypted);
      setConfigSaved(!!(res.app_id || res.secret_id));
    } catch {
      // config may not exist yet
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      setTestResult(null);
      const payload: Record<string, any> = {
        app_id: values.app_id,
        secret_id: values.secret_id,
        is_enabled: values.is_enabled,
      };
      if (values.secret_key_raw) {
        payload.secret_key_raw = values.secret_key_raw;
      }
      await put('/api/admin/search/asr-config', payload);
      message.success('语音配置保存成功');
      setConfigSaved(true);
      fetchConfig();
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      const res = await post<{ success: boolean; message: string }>('/api/admin/search/asr-config/test');
      setTestResult({
        success: res.success,
        message: res.message || (res.success ? '配置验证通过' : '配置错误'),
      });
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '测试失败';
      setTestResult({
        success: false,
        message: `配置错误：${typeof detail === 'string' ? detail : '未知错误'}`,
      });
    } finally {
      setTesting(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>语音识别配置</Title>
      <Spin spinning={loading}>
        <Card style={{ borderRadius: 12, maxWidth: 640 }}>
          <Form form={form} layout="vertical" initialValues={{ is_enabled: false }}>
            <Form.Item
              label="腾讯云 AppID"
              name="app_id"
              rules={[{ required: true, message: '请输入腾讯云 AppID' }]}
            >
              <Input placeholder="请输入腾讯云 AppID" />
            </Form.Item>
            <Form.Item
              label="腾讯云 SecretId"
              name="secret_id"
              rules={[{ required: true, message: '请输入腾讯云 SecretId' }]}
            >
              <Input placeholder="请输入腾讯云 SecretId" />
            </Form.Item>
            <Form.Item label="腾讯云 SecretKey" name="secret_key_raw">
              <Input.Password
                placeholder={hasSecretKey ? '已设置（重新输入将覆盖）' : '请输入腾讯云 SecretKey'}
              />
            </Form.Item>
            <Form.Item label="启用/禁用" name="is_enabled" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
            <Alert
              type="info"
              message="方言支持说明"
              description="当前支持普通话和粤语"
              showIcon
              icon={<SoundOutlined />}
              style={{ marginBottom: 24 }}
            />
            <Form.Item>
              <Space>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
                  保存配置
                </Button>
                <Button
                  icon={<ApiOutlined />}
                  onClick={handleTest}
                  loading={testing}
                  disabled={!configSaved}
                >
                  测试识别
                </Button>
              </Space>
            </Form.Item>
          </Form>

          {testResult && (
            <Alert
              type={testResult.success ? 'success' : 'error'}
              message={testResult.success ? '配置验证通过' : '配置错误'}
              description={testResult.message}
              showIcon
              style={{ marginTop: 8 }}
            />
          )}
        </Card>
      </Spin>
    </div>
  );
}
