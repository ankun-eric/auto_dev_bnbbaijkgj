'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Table, Radio, Input, InputNumber, Button, Card, Space, message, Spin,
} from 'antd';
import { SaveOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';

const { Title, Text } = Typography;

interface FallbackConfig {
  scene: string;
  scene_label: string;
  strategy: string;
  custom_text: string;
  recommend_count: number;
}

const SCENES = [
  { value: 'health_qa', label: '健康问答' },
  { value: 'symptom_analysis', label: '症状分析' },
  { value: 'tcm_diagnosis', label: '中医辨证' },
  { value: 'drug_query', label: '药品查询' },
  { value: 'customer_service', label: '客服' },
];

export default function FallbackConfigPage() {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [configs, setConfigs] = useState<FallbackConfig[]>(
    SCENES.map((s) => ({
      scene: s.value,
      scene_label: s.label,
      strategy: 'ai_fallback',
      custom_text: '',
      recommend_count: 3,
    }))
  );

  const fetchConfig = useCallback(async () => {
    setLoading(true);
    try {
      const results: FallbackConfig[] = [];
      for (const s of SCENES) {
        try {
          const res = await get<{ scene: string; strategy: string; custom_text: string | null; recommend_count: number }>(
            '/api/admin/knowledge-bases/fallback-config', { scene: s.value }
          );
          results.push({
            scene: s.value,
            scene_label: s.label,
            strategy: res.strategy || 'ai_fallback',
            custom_text: res.custom_text || '',
            recommend_count: res.recommend_count ?? 3,
          });
        } catch {
          results.push({
            scene: s.value,
            scene_label: s.label,
            strategy: 'ai_fallback',
            custom_text: '',
            recommend_count: 3,
          });
        }
      }
      setConfigs(results);
    } catch {
      // use defaults
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchConfig();
  }, [fetchConfig]);

  const handleFieldChange = (scene: string, field: string, value: any) => {
    setConfigs((prev) =>
      prev.map((c) => (c.scene === scene ? { ...c, [field]: value } : c))
    );
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      for (const c of configs) {
        await put('/api/admin/knowledge-bases/fallback-config', {
          scene: c.scene,
          strategy: c.strategy,
          custom_text: c.custom_text || null,
          recommend_count: c.recommend_count,
        });
      }
      message.success('兜底策略保存成功');
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const columns = [
    {
      title: '对话场景',
      dataIndex: 'scene_label',
      key: 'scene_label',
      width: 140,
      render: (v: string) => <Text strong>{v}</Text>,
    },
    {
      title: '兜底策略',
      key: 'strategy',
      width: 360,
      render: (_: any, record: FallbackConfig) => (
        <Radio.Group
          value={record.strategy}
          onChange={(e) => handleFieldChange(record.scene, 'strategy', e.target.value)}
        >
          <Space direction="vertical">
            <Radio value="ai_fallback">回退AI生成</Radio>
            <Radio value="fixed_text">固定文案</Radio>
            <Radio value="human_service">转人工客服</Radio>
            <Radio value="recommend">推荐相关内容</Radio>
          </Space>
        </Radio.Group>
      ),
    },
    {
      title: '配置详情',
      key: 'detail',
      render: (_: any, record: FallbackConfig) => (
        <Space direction="vertical" style={{ width: '100%' }}>
          {record.strategy === 'fixed_text' && (
            <div>
              <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>固定文案：</Text>
              <Input.TextArea
                rows={3}
                value={record.custom_text}
                onChange={(e) => handleFieldChange(record.scene, 'custom_text', e.target.value)}
                placeholder="请输入兜底回复文案"
                style={{ maxWidth: 400 }}
              />
            </div>
          )}
          {record.strategy === 'recommend' && (
            <div>
              <Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>推荐条目数：</Text>
              <InputNumber
                min={1}
                max={10}
                value={record.recommend_count}
                onChange={(v) => handleFieldChange(record.scene, 'recommend_count', v)}
              />
            </div>
          )}
          {(record.strategy === 'ai_fallback' || record.strategy === 'human_service') && (
            <Text type="secondary">无需额外配置</Text>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>兜底策略配置</Title>
      <Card style={{ borderRadius: 12 }}>
        <Spin spinning={loading}>
          <Table
            columns={columns}
            dataSource={configs}
            rowKey="scene"
            pagination={false}
            scroll={{ x: 800 }}
          />
          <div style={{ marginTop: 24 }}>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave} loading={saving} size="large">
              保存兜底策略
            </Button>
          </div>
        </Spin>
      </Card>
    </div>
  );
}
