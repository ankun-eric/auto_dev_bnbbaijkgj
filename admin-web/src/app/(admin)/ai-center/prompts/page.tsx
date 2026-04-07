'use client';

import React, { useEffect, useState, useCallback } from 'react';
import { Typography, Tabs, Input, Button, Spin, message, Card } from 'antd';
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
  { key: 'ocr_checkup_report', label: '体检报告识别' },
  { key: 'ocr_drug_identify', label: '拍照识药' },
];

interface PromptConfig {
  chat_type: string;
  system_prompt: string;
  updated_at?: string;
}

export default function PromptsPage() {
  const [activeTab, setActiveTab] = useState('health_qa');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [configs, setConfigs] = useState<Record<string, PromptConfig>>({});

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<PromptConfig[] | { items: PromptConfig[] }>('/api/admin/ai-center/prompts');
      const items = Array.isArray(res) ? res : (res.items || []);
      const map: Record<string, PromptConfig> = {};
      items.forEach((item) => {
        map[item.chat_type] = item;
      });
      setConfigs(map);
    } catch {
      message.error('获取提示词配置失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handlePromptChange = (chatType: string, value: string) => {
    setConfigs((prev) => ({
      ...prev,
      [chatType]: {
        ...prev[chatType],
        chat_type: chatType,
        system_prompt: value,
      },
    }));
  };

  const handleSave = async (chatType: string) => {
    const config = configs[chatType];
    if (!config?.system_prompt?.trim()) {
      message.warning('请输入提示词内容');
      return;
    }
    setSaving(true);
    try {
      await put(`/api/admin/ai-center/prompts/${chatType}`, {
        system_prompt: config.system_prompt,
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
            <Title level={5} style={{ margin: 0 }}>{type.label} - 系统提示词</Title>
          </div>
          <TextArea
            rows={15}
            value={config?.system_prompt || ''}
            onChange={(e) => handlePromptChange(type.key, e.target.value)}
            placeholder={`请输入${type.label}的系统提示词...`}
            style={{ marginBottom: 16 }}
          />
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
      <Title level={4} style={{ marginBottom: 24 }}>提示词配置</Title>
      <Spin spinning={loading}>
        <Tabs items={tabItems} activeKey={activeTab} onChange={setActiveTab} />
      </Spin>
    </div>
  );
}
