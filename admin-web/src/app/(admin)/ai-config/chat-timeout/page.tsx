'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Card, Select, Button, Typography, Spin, message, Alert, Space,
} from 'antd';
import { ClockCircleOutlined, SaveOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';

const { Title, Text } = Typography;

interface ChatIdleTimeoutConfig {
  timeout_minutes: number;
}

const TIMEOUT_OPTIONS = [
  { label: '30分钟', value: 30 },
  { label: '60分钟', value: 60 },
];

export default function ChatTimeoutConfigPage() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [timeoutMinutes, setTimeoutMinutes] = useState<number>(30);

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<ChatIdleTimeoutConfig>('/api/admin/app-settings/chat-idle-timeout');
      setTimeoutMinutes(res.timeout_minutes ?? 30);
    } catch {
      message.error('获取对话超时配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      await put('/api/admin/app-settings/chat-idle-timeout', {
        timeout_minutes: timeoutMinutes,
      });
      message.success('对话超时配置保存成功');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        <ClockCircleOutlined style={{ marginRight: 8 }} />
        对话空闲超时配置
      </Title>

      <Spin spinning={loading}>
        <Card style={{ borderRadius: 12, maxWidth: 720 }}>
          <Text type="secondary" style={{ display: 'block', marginBottom: 24 }}>
            设置用户对话的空闲超时时间，超过该时间后用户发送新消息将自动创建新对话
          </Text>

          <div style={{ marginBottom: 24 }}>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>空闲超时时间</Text>
            <Select
              value={timeoutMinutes}
              onChange={setTimeoutMinutes}
              options={TIMEOUT_OPTIONS}
              style={{ width: 200 }}
            />
          </div>

          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
              loading={saving}
            >
              保存配置
            </Button>
          </Space>
        </Card>

        <Alert
          message="配置说明"
          description="当用户在对话中空闲超过设定时间后，再次发送消息时系统将自动创建一个新的对话会话，而非继续之前的对话。"
          type="info"
          showIcon
          style={{ maxWidth: 720, marginTop: 16, borderRadius: 8 }}
        />
      </Spin>
    </div>
  );
}
