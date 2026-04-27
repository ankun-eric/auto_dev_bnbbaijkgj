'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Form, Input, InputNumber, Switch, Button, Space, TimePicker,
  Typography, Spin, message, Alert,
} from 'antd';
import { SaveOutlined, ReloadOutlined, VideoCameraOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface VideoConsultConfig {
  enabled: boolean;
  seat_url: string;
  service_start_time: string;
  service_end_time: string;
  max_queue: number;
  welcome_message: string;
  wait_message: string;
  timeout_seconds: number;
  offline_message: string;
}

export default function VideoConsultConfigPage() {
  const [form] = Form.useForm();
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [initialValues, setInitialValues] = useState<VideoConsultConfig | null>(null);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<VideoConsultConfig>('/api/admin/video-consult-config');
      const config: VideoConsultConfig = {
        enabled: res.enabled ?? false,
        seat_url: res.seat_url ?? '',
        service_start_time: res.service_start_time ?? '09:00',
        service_end_time: res.service_end_time ?? '18:00',
        max_queue: res.max_queue ?? 10,
        welcome_message: res.welcome_message ?? '',
        wait_message: res.wait_message ?? '',
        timeout_seconds: res.timeout_seconds ?? 300,
        offline_message: res.offline_message ?? '',
      };
      setInitialValues(config);
      form.setFieldsValue({
        ...config,
        service_start_time: dayjs(config.service_start_time, 'HH:mm'),
        service_end_time: dayjs(config.service_end_time, 'HH:mm'),
      });
    } catch {
      message.error('获取视频客服配置失败');
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
      const payload: VideoConsultConfig = {
        enabled: values.enabled ?? false,
        seat_url: values.seat_url ?? '',
        service_start_time: values.service_start_time?.format('HH:mm') ?? '09:00',
        service_end_time: values.service_end_time?.format('HH:mm') ?? '18:00',
        max_queue: values.max_queue ?? 10,
        welcome_message: values.welcome_message ?? '',
        wait_message: values.wait_message ?? '',
        timeout_seconds: values.timeout_seconds ?? 300,
        offline_message: values.offline_message ?? '',
      };
      await put('/api/admin/video-consult-config', payload);
      message.success('视频客服配置保存成功');
      setInitialValues(payload);
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    if (initialValues) {
      form.setFieldsValue({
        ...initialValues,
        service_start_time: dayjs(initialValues.service_start_time, 'HH:mm'),
        service_end_time: dayjs(initialValues.service_end_time, 'HH:mm'),
      });
      message.info('已重置为上次保存的配置');
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        <VideoCameraOutlined style={{ marginRight: 8 }} />
        视频客服配置
      </Title>

      <Spin spinning={loading}>
        <Card style={{ borderRadius: 12, maxWidth: 720 }}>
          <Form form={form} layout="vertical">
            <Form.Item
              label="视频客服总开关"
              name="enabled"
              valuePropName="checked"
            >
              <Switch checkedChildren="开启" unCheckedChildren="关闭" />
            </Form.Item>

            <Form.Item
              label="坐席服务URL"
              name="seat_url"
              rules={[{ required: true, message: '请输入坐席服务URL' }]}
            >
              <Input placeholder="请输入第三方视频客服服务地址，如 https://video.example.com" />
            </Form.Item>

            <Space style={{ width: '100%' }} size={16}>
              <Form.Item
                label="服务时段开始"
                name="service_start_time"
                rules={[{ required: true, message: '请选择服务开始时间' }]}
                style={{ flex: 1 }}
              >
                <TimePicker format="HH:mm" style={{ width: '100%' }} placeholder="开始时间" />
              </Form.Item>
              <Form.Item
                label="服务时段结束"
                name="service_end_time"
                rules={[{ required: true, message: '请选择服务结束时间' }]}
                style={{ flex: 1 }}
              >
                <TimePicker format="HH:mm" style={{ width: '100%' }} placeholder="结束时间" />
              </Form.Item>
            </Space>

            <Space style={{ width: '100%' }} size={16}>
              <Form.Item
                label="排队上限"
                name="max_queue"
                rules={[{ required: true, message: '请输入排队上限' }]}
                style={{ flex: 1 }}
              >
                <InputNumber min={1} max={999} style={{ width: '100%' }} placeholder="最大同时排队人数" />
              </Form.Item>
              <Form.Item
                label="超时时长(秒)"
                name="timeout_seconds"
                rules={[{ required: true, message: '请输入超时时长' }]}
                style={{ flex: 1 }}
              >
                <InputNumber min={10} max={600} style={{ width: '100%' }} placeholder="无应答超时时间" />
              </Form.Item>
            </Space>

            <Form.Item
              label="欢迎问候语"
              name="welcome_message"
            >
              <TextArea rows={2} placeholder="用户接入时的欢迎消息" maxLength={200} showCount />
            </Form.Item>

            <Form.Item
              label="等待提示语"
              name="wait_message"
            >
              <TextArea rows={2} placeholder="排队等待时的提示文案" maxLength={200} showCount />
            </Form.Item>

            <Form.Item
              label="非服务时段提示"
              name="offline_message"
            >
              <TextArea rows={2} placeholder="非服务时间的提示语" maxLength={200} showCount />
            </Form.Item>

            <Form.Item style={{ marginBottom: 0 }}>
              <Space>
                <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving}>
                  保存配置
                </Button>
                <Button icon={<ReloadOutlined />} onClick={handleReset}>
                  重置
                </Button>
              </Space>
            </Form.Item>
          </Form>
        </Card>

        <Alert
          message="配置说明"
          description="视频客服功能开启后，用户端在服务时段内可发起视频客服请求。非服务时段将显示提示语。"
          type="info"
          showIcon
          style={{ maxWidth: 720, marginTop: 16, borderRadius: 8 }}
        />
      </Spin>
    </div>
  );
}
