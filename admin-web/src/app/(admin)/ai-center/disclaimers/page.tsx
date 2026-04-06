'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Typography, Tabs, Input, Button, Spin, Switch, message, Card } from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { TextArea } = Input;

const CHAT_TYPES = [
  { key: 'health_qa', label: '健康问答' },
  { key: 'symptom_check', label: '健康自查' },
  { key: 'tcm', label: '中医养生' },
  { key: 'drug_query', label: '用药参考' },
  { key: 'customer_service', label: '在线客服' },
];

interface DisclaimerConfig {
  chat_type: string;
  disclaimer_text: string;
  is_enabled: boolean;
  updated_at?: string;
}

export default function DisclaimersPage() {
  const [activeTab, setActiveTab] = useState('health_qa');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [configs, setConfigs] = useState<Record<string, DisclaimerConfig>>({});

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<DisclaimerConfig[] | { items: DisclaimerConfig[] }>('/api/admin/ai-center/disclaimers');
      const items = Array.isArray(res) ? res : (res.items || []);
      const map: Record<string, DisclaimerConfig> = {};
      items.forEach((item) => {
        map[item.chat_type] = item;
      });
      setConfigs(map);
    } catch {
      message.error('获取免责提示配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleTextChange = (chatType: string, value: string) => {
    setConfigs((prev) => ({
      ...prev,
      [chatType]: {
        ...prev[chatType],
        chat_type: chatType,
        disclaimer_text: value,
        is_enabled: prev[chatType]?.is_enabled ?? true,
      },
    }));
  };

  const handleEnabledChange = (chatType: string, checked: boolean) => {
    setConfigs((prev) => ({
      ...prev,
      [chatType]: {
        ...prev[chatType],
        chat_type: chatType,
        disclaimer_text: prev[chatType]?.disclaimer_text || '',
        is_enabled: checked,
      },
    }));
  };

  const handleSave = async (chatType: string) => {
    const config = configs[chatType];
    setSaving(true);
    try {
      await put(`/api/admin/ai-center/disclaimers/${chatType}`, {
        disclaimer_text: config?.disclaimer_text || '',
        is_enabled: config?.is_enabled ?? true,
      });
      message.success('保存成功');
      fetchData();
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const tabItems = CHAT_TYPES.map((type) => {
    const config = configs[type.key];
    return {
      key: type.key,
      label: type.label,
      children: (
        <Card style={{ borderRadius: 12 }}>
          <div style={{ marginBottom: 16 }}>
            <Title level={5} style={{ margin: 0 }}>{type.label} - 免责提示</Title>
          </div>
          <TextArea
            rows={10}
            value={config?.disclaimer_text || ''}
            onChange={(e) => handleTextChange(type.key, e.target.value)}
            placeholder={`请输入${type.label}的免责提示内容...`}
            style={{ marginBottom: 16 }}
          />
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
            <Text>是否启用：</Text>
            <Switch
              checked={config?.is_enabled ?? true}
              onChange={(checked) => handleEnabledChange(type.key, checked)}
              checkedChildren="启用"
              unCheckedChildren="停用"
            />
          </div>
          {config?.updated_at && (
            <div style={{ marginBottom: 16 }}>
              <Text type="secondary">
                最后修改时间：{dayjs(config.updated_at).format('YYYY-MM-DD HH:mm:ss')}
              </Text>
            </div>
          )}
          <Button
            type="primary"
            icon={<SaveOutlined />}
            onClick={() => handleSave(type.key)}
            loading={saving}
          >
            保存
          </Button>
        </Card>
      ),
    };
  });

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>免责提示配置</Title>
      <Spin spinning={loading}>
        <Tabs items={tabItems} activeKey={activeTab} onChange={setActiveTab} />
      </Spin>
    </div>
  );
}
