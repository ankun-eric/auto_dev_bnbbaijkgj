'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Button, Form, Input, InputNumber, Select, Slider, Radio,
  Typography, message, Space, Divider, Spin, Alert,
} from 'antd';
import { SaveOutlined, UndoOutlined, ApiOutlined } from '@ant-design/icons';
import { get, put, post } from '@/lib/api';

const { Title, Text } = Typography;

const LANGUAGE_OPTIONS = [
  { value: 'zh', label: '中文普通话' },
  { value: 'yue', label: '粤语' },
  { value: 'en', label: '英语' },
];

const VAD_SENSITIVITY_OPTIONS = [
  { value: 'high', label: '高' },
  { value: 'medium', label: '中' },
  { value: 'low', label: '低' },
];

const DEFAULT_VAD_CONFIG = {
  silence_duration: 1.5,
  max_record_duration: 60,
  language: 'zh',
  vad_sensitivity: 'medium',
};

interface VoiceConfig {
  tencent_app_id: string;
  tencent_secret_id: string;
  tencent_secret_key: string;
  silence_duration: number;
  max_record_duration: number;
  language: string;
  vad_sensitivity: string;
}

export default function VoiceServicePage() {
  const [loading, setLoading] = useState(false);
  const [savingKeys, setSavingKeys] = useState(false);
  const [savingVad, setSavingVad] = useState(false);
  const [testing, setTesting] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [checked, setChecked] = useState(false);
  const [keyForm] = Form.useForm();
  const [vadForm] = Form.useForm();

  useEffect(() => {
    try {
      const stored = localStorage.getItem('admin_user');
      if (stored) {
        const user = JSON.parse(stored);
        if (user.role === 'admin' || user.is_superadmin) {
          setIsAdmin(true);
        }
      }
    } catch {}
    setChecked(true);
  }, []);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/voice-service/config');
      const items: Array<{ config_key: string; config_value: string }> = res.items || [];
      const configMap: Record<string, string> = {};
      for (const item of items) {
        configMap[item.config_key] = item.config_value;
      }
      keyForm.setFieldsValue({
        tencent_app_id: configMap['tts_api_key'] || '',
        tencent_secret_id: configMap['tts_api_url'] || '',
        tencent_secret_key: '',
      });
      vadForm.setFieldsValue({
        silence_duration: configMap['vad_silence_duration'] ? parseFloat(configMap['vad_silence_duration']) / 1000 : DEFAULT_VAD_CONFIG.silence_duration,
        max_record_duration: configMap['vad_max_speech_duration'] ? parseFloat(configMap['vad_max_speech_duration']) / 1000 : DEFAULT_VAD_CONFIG.max_record_duration,
        language: configMap['language'] || DEFAULT_VAD_CONFIG.language,
        vad_sensitivity: configMap['vad_sensitivity'] || DEFAULT_VAD_CONFIG.vad_sensitivity,
      });
    } catch {
      message.error('获取语音服务配置失败');
    } finally {
      setLoading(false);
    }
  }, [keyForm, vadForm]);

  useEffect(() => {
    if (isAdmin) {
      fetchConfig();
    }
  }, [isAdmin, fetchConfig]);

  const handleTestConnection = async () => {
    try {
      const values = await keyForm.validateFields();
      setTesting(true);
      const res = await post<any>('/api/admin/voice-service/test-connection', {
        tencent_app_id: values.tencent_app_id,
        tencent_secret_id: values.tencent_secret_id,
        tencent_secret_key: values.tencent_secret_key,
      });
      if (res.success) {
        message.success('连接测试成功');
      } else {
        message.error(res.message || '连接测试失败');
      }
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '连接测试失败');
    } finally {
      setTesting(false);
    }
  };

  const handleSaveKeys = async () => {
    try {
      const values = await keyForm.validateFields();
      setSavingKeys(true);
      const items = [
        { config_key: 'tts_api_key', config_value: values.tencent_app_id || '' },
        { config_key: 'tts_api_url', config_value: values.tencent_secret_id || '' },
      ];
      for (const item of items) {
        await put('/api/admin/voice-service/config', item);
      }
      message.success('密钥保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSavingKeys(false);
    }
  };

  const handleSaveVad = async () => {
    try {
      const values = await vadForm.validateFields();
      setSavingVad(true);
      const items = [
        { config_key: 'vad_silence_duration', config_value: String(Math.round((values.silence_duration || 1.5) * 1000)) },
        { config_key: 'vad_max_speech_duration', config_value: String(Math.round((values.max_record_duration || 60) * 1000)) },
      ];
      for (const item of items) {
        await put('/api/admin/voice-service/config', item);
      }
      message.success('参数保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSavingVad(false);
    }
  };

  const handleResetVad = () => {
    vadForm.setFieldsValue(DEFAULT_VAD_CONFIG);
    message.info('已恢复默认值，请点击保存生效');
  };

  if (!checked) return null;

  if (!isAdmin) {
    return (
      <div>
        <Title level={4} style={{ marginBottom: 24 }}>语音服务配置</Title>
        <Alert
          message="权限不足"
          description="语音服务配置仅超级管理员可访问"
          type="warning"
          showIcon
        />
      </div>
    );
  }

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>语音服务配置</Title>
      <Spin spinning={loading}>
        <Card title="腾讯云密钥配置" style={{ marginBottom: 24 }}>
          <Form form={keyForm} layout="vertical" style={{ maxWidth: 560 }}>
            <Form.Item
              label="AppID"
              name="tencent_app_id"
              rules={[{ required: true, message: '请输入AppID' }]}
            >
              <Input placeholder="请输入腾讯云AppID" />
            </Form.Item>
            <Form.Item
              label="SecretId"
              name="tencent_secret_id"
              rules={[{ required: true, message: '请输入SecretId' }]}
            >
              <Input placeholder="请输入腾讯云SecretId" />
            </Form.Item>
            <Form.Item
              label="SecretKey"
              name="tencent_secret_key"
              rules={[{ required: true, message: '请输入SecretKey' }]}
            >
              <Input.Password placeholder="请输入腾讯云SecretKey" />
            </Form.Item>
            <Form.Item>
              <Space>
                <Button icon={<ApiOutlined />} loading={testing} onClick={handleTestConnection}>
                  测试连接
                </Button>
                <Button type="primary" icon={<SaveOutlined />} loading={savingKeys} onClick={handleSaveKeys}>
                  保存密钥
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>

        <Card title="VAD 语音识别参数">
          <Form form={vadForm} layout="vertical" style={{ maxWidth: 560 }}>
            <Form.Item label="静音检测时长（秒）" name="silence_duration">
              <Slider min={0.5} max={5} step={0.1} marks={{ 0.5: '0.5s', 1.5: '1.5s', 3: '3s', 5: '5s' }} />
            </Form.Item>
            <Form.Item label="最大单次录音时长（秒）" name="max_record_duration">
              <InputNumber min={10} max={120} style={{ width: '100%' }} addonAfter="秒" />
            </Form.Item>
            <Form.Item label="语音识别语言" name="language">
              <Select options={LANGUAGE_OPTIONS} placeholder="请选择语言" />
            </Form.Item>
            <Form.Item label="VAD 灵敏度" name="vad_sensitivity">
              <Radio.Group>
                {VAD_SENSITIVITY_OPTIONS.map((opt) => (
                  <Radio.Button key={opt.value} value={opt.value}>{opt.label}</Radio.Button>
                ))}
              </Radio.Group>
            </Form.Item>
            <Form.Item>
              <Space>
                <Button icon={<UndoOutlined />} onClick={handleResetVad}>
                  恢复默认值
                </Button>
                <Button type="primary" icon={<SaveOutlined />} loading={savingVad} onClick={handleSaveVad}>
                  保存参数
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>
      </Spin>
    </div>
  );
}
