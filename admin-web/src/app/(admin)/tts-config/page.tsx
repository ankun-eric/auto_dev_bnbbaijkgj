'use client';

import React, { useEffect, useState } from 'react';
import { Form, Input, Switch, Button, Card, Space, message, Typography, Radio, Select, Slider, Divider } from 'antd';
import { SaveOutlined, SoundOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';

const { Title, Text } = Typography;

type TtsScheme = 'free' | 'cloud';
type TtsOverride = 'follow_global' | 'free' | 'cloud';

interface TtsConfig {
  enabled: boolean;
  default_mode: TtsScheme;
  h5_mode: TtsOverride | null;
  miniprogram_mode: TtsOverride | null;
  app_mode: TtsOverride | null;
  cloud_provider: 'aliyun' | 'tencent';
  cloud_api_key: string;
  voice_gender: 'male' | 'female';
  speed: number;
  pitch: number;
}

const overrideOptions = [
  { label: '跟随全局', value: 'follow_global' },
  { label: '免费方案', value: 'free' },
  { label: '云端TTS', value: 'cloud' },
];

const speedMarks: Record<number, string> = {
  0.5: '0.5x',
  1.0: '1.0x',
  1.5: '1.5x',
  2.0: '2.0x',
};

export default function TtsConfigPage() {
  const [form] = Form.useForm<TtsConfig>();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const enabled = Form.useWatch('enabled', form);
  const defaultMode = Form.useWatch('default_mode', form);
  const h5Mode = Form.useWatch('h5_mode', form);
  const miniprogramMode = Form.useWatch('miniprogram_mode', form);
  const appMode = Form.useWatch('app_mode', form);

  const cloudDisabled = (() => {
    if (defaultMode === 'cloud') return false;
    const overrides = [h5Mode, miniprogramMode, appMode];
    return !overrides.some((o) => o === 'cloud');
  })();

  useEffect(() => {
    const loadConfig = async () => {
      setLoading(true);
      try {
        const res = await get<{ code: number; data: TtsConfig }>('/api/admin/settings/tts-config');
        if (res?.data) {
          const d = res.data;
          form.setFieldsValue({
            ...d,
            h5_mode: d.h5_mode || 'follow_global',
            miniprogram_mode: d.miniprogram_mode || 'follow_global',
            app_mode: d.app_mode || 'follow_global',
          });
        }
      } catch {
        // use defaults
      } finally {
        setLoading(false);
      }
    };
    loadConfig();
  }, [form]);

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        ...values,
        h5_mode: values.h5_mode === 'follow_global' ? null : values.h5_mode,
        miniprogram_mode: values.miniprogram_mode === 'follow_global' ? null : values.miniprogram_mode,
        app_mode: values.app_mode === 'follow_global' ? null : values.app_mode,
      };
      await put('/api/admin/settings/tts-config', payload);
      message.success('保存成功');
    } catch (e: unknown) {
      if ((e as { errorFields?: unknown })?.errorFields) return;
      message.error('保存失败，请稍后重试');
    } finally {
      setSaving(false);
    }
  };

  const setSpeed = (v: number) => {
    form.setFieldsValue({ speed: v });
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        <Space>
          <SoundOutlined />
          TTS 语音播报配置
        </Space>
      </Title>

      <Card style={{ borderRadius: 12 }} loading={loading}>
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            enabled: false,
            default_mode: 'free',
            h5_mode: 'follow_global',
            miniprogram_mode: 'follow_global',
            app_mode: 'follow_global',
            cloud_provider: 'aliyun',
            cloud_api_key: '',
            voice_gender: 'female',
            speed: 1.0,
            pitch: 1.0,
          }}
        >
          <Title level={5}>基础设置</Title>

          <Form.Item label="TTS 功能开关" name="enabled" valuePropName="checked">
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>

          <Divider />
          <Title level={5}>方案配置</Title>

          <Form.Item label="TTS 方案 — 全局默认" name="default_mode">
            <Radio.Group disabled={!enabled}>
              <Radio value="free">免费方案</Radio>
              <Radio value="cloud">云端TTS</Radio>
            </Radio.Group>
          </Form.Item>

          <Space style={{ width: '100%' }} size={16} wrap>
            <Form.Item label="H5端方案覆盖" name="h5_mode" style={{ minWidth: 200 }}>
              <Select options={overrideOptions} disabled={!enabled} />
            </Form.Item>
            <Form.Item label="小程序端方案覆盖" name="miniprogram_mode" style={{ minWidth: 200 }}>
              <Select options={overrideOptions} disabled={!enabled} />
            </Form.Item>
            <Form.Item label="App端方案覆盖" name="app_mode" style={{ minWidth: 200 }}>
              <Select options={overrideOptions} disabled={!enabled} />
            </Form.Item>
          </Space>

          <Divider />
          <Title level={5}>
            <Space>
              云端TTS设置
              {cloudDisabled && <Text type="secondary" style={{ fontSize: 12, fontWeight: 400 }}>（当前无端使用云端TTS，以下配置暂不生效）</Text>}
            </Space>
          </Title>

          <Form.Item label="云端TTS服务商" name="cloud_provider">
            <Radio.Group disabled={!enabled || cloudDisabled}>
              <Radio value="aliyun">阿里云</Radio>
              <Radio value="tencent">腾讯云</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item label="云端TTS API Key" name="cloud_api_key">
            <Input.Password
              placeholder="请输入 API Key"
              disabled={!enabled || cloudDisabled}
              style={{ maxWidth: 480 }}
            />
          </Form.Item>

          <Divider />
          <Title level={5}>语音参数</Title>

          <Form.Item label="语音性别" name="voice_gender">
            <Radio.Group disabled={!enabled}>
              <Radio value="male">男声</Radio>
              <Radio value="female">女声</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item label="语速" name="speed">
            <Slider
              min={0.5}
              max={2.0}
              step={0.1}
              marks={speedMarks}
              disabled={!enabled}
              style={{ maxWidth: 480 }}
              tooltip={{ formatter: (v) => `${v}x` }}
            />
          </Form.Item>
          <Space size={8} style={{ marginTop: -8, marginBottom: 16 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>预设：</Text>
            {[0.8, 1.0, 1.2, 1.5].map((v) => (
              <Button key={v} size="small" disabled={!enabled} onClick={() => setSpeed(v)}>
                {v}x
              </Button>
            ))}
          </Space>

          <Form.Item label="语调(pitch)" name="pitch">
            <Slider
              min={0.5}
              max={2.0}
              step={0.1}
              disabled={!enabled}
              style={{ maxWidth: 480 }}
              tooltip={{ formatter: (v) => `${v}` }}
            />
          </Form.Item>

          <Divider />
          <Form.Item>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
              保存配置
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
