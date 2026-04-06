'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Form, Input, Button, Space, message, Typography, Select, Switch, Spin, Alert,
} from 'antd';
import {
  SaveOutlined, ApiOutlined, CheckCircleOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { get, put, post } from '@/lib/api';

const { Title } = Typography;

interface OcrConfig {
  enabled: boolean;
  api_key: string;
  secret_key: string;
  ocr_type: string;
}

export default function OcrConfigPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [hasSecretKey, setHasSecretKey] = useState(false);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<OcrConfig>('/api/admin/ocr/config');
      form.setFieldsValue({
        enabled: !!res.enabled,
        api_key: res.api_key || '',
        ocr_type: res.ocr_type || 'general_basic',
      });
      setHasSecretKey(!!res.api_key);
    } catch {
      // config not yet set
    } finally {
      setLoading(false);
    }
  }, [form]);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const maskSecretKey = (key: string): string => {
    if (!key || key.length <= 4) return key ? '****' : '';
    return key.substring(0, 4) + '****';
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload: Record<string, any> = {
        enabled: values.enabled,
        api_key: values.api_key,
        ocr_type: values.ocr_type,
      };
      if (values.secret_key) {
        payload.secret_key = values.secret_key;
      }
      await put('/api/admin/ocr/config', payload);
      message.success('OCR配置保存成功');
      form.setFieldsValue({ secret_key: '' });
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
    try {
      await form.validateFields(['api_key']);
      setTesting(true);
      setTestResult(null);
      const res = await post<{ success: boolean; message: string }>('/api/admin/ocr/test');
      setTestResult({ success: res.success ?? false, message: res.message || '连接成功' });
      if (res.success) {
        message.success('连接测试成功');
      } else {
        message.error(res.message || '连接测试失败');
      }
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '连接测试失败';
      setTestResult({ success: false, message: typeof detail === 'string' ? detail : '连接测试失败' });
      message.error(typeof detail === 'string' ? detail : '连接测试失败');
    } finally {
      setTesting(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>OCR识别配置</Title>
      <Spin spinning={loading}>
        <Card style={{ borderRadius: 12, maxWidth: 720 }}>
          <Form
            form={form}
            labelCol={{ span: 6 }}
            wrapperCol={{ span: 14 }}
            initialValues={{ enabled: false, ocr_type: 'general_basic' }}
          >
            <Form.Item label="OCR功能开关" name="enabled" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="关闭" />
            </Form.Item>

            <Form.Item
              label="API Key"
              name="api_key"
              rules={[{ required: true, message: '请输入API Key' }]}
            >
              <Input placeholder="请输入API Key" />
            </Form.Item>

            <Form.Item
              label="Secret Key"
              name="secret_key"
            >
              <Input.Password
                placeholder={hasSecretKey ? '已设置（重新输入将覆盖）' : '请输入Secret Key'}
              />
            </Form.Item>
            {hasSecretKey && (
              <Form.Item wrapperCol={{ offset: 6, span: 14 }}>
                <span style={{ color: '#999', fontSize: 12 }}>
                  当前Secret Key：{maskSecretKey('****')}（已脱敏显示）
                </span>
              </Form.Item>
            )}

            <Form.Item
              label="识别类型"
              name="ocr_type"
              rules={[{ required: true, message: '请选择识别类型' }]}
            >
              <Select
                options={[
                  { label: '通用文字识别（标准版）', value: 'general_basic' },
                  { label: '通用文字识别（高精度版）', value: 'accurate_basic' },
                ]}
              />
            </Form.Item>

            <Form.Item wrapperCol={{ offset: 6, span: 14 }}>
              <Space>
                <Button
                  icon={<ApiOutlined />}
                  onClick={handleTest}
                  loading={testing}
                >
                  连接测试
                </Button>
                <Button
                  type="primary"
                  icon={<SaveOutlined />}
                  onClick={handleSave}
                  loading={saving}
                >
                  保存配置
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
        </Card>
      </Spin>
    </div>
  );
}
