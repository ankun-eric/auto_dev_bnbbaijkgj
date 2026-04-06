'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Card, Form, Switch, InputNumber, Radio, Button, Table, Space,
  Select, Modal, message, Spin, Divider, Tag,
} from 'antd';
import { SaveOutlined, EditOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';

const { Title, Text } = Typography;

interface GlobalSearchConfig {
  exact_match_enabled: boolean;
  semantic_match_enabled: boolean;
  keyword_match_enabled: boolean;
  exact_match_priority: number;
  semantic_match_priority: number;
  keyword_match_priority: number;
  similarity_threshold: string;
  max_display_count: number;
}

interface KbSearchConfig {
  knowledge_base_id: number;
  knowledge_base_name: string;
  use_custom: boolean;
  config?: GlobalSearchConfig;
}

interface SceneBinding {
  scene: string;
  scene_label: string;
  knowledge_base_ids: number[];
}

interface KnowledgeBaseOption {
  id: number;
  name: string;
}

const SCENES = [
  { value: 'health_qa', label: '健康问答' },
  { value: 'symptom_analysis', label: '症状分析' },
  { value: 'tcm_diagnosis', label: '中医辨证' },
  { value: 'drug_query', label: '药品查询' },
  { value: 'customer_service', label: '客服' },
];

export default function SearchConfigPage() {
  const [globalForm] = Form.useForm();
  const [globalLoading, setGlobalLoading] = useState(false);
  const [globalSaving, setGlobalSaving] = useState(false);

  const [kbConfigs, setKbConfigs] = useState<KbSearchConfig[]>([]);
  const [kbLoading, setKbLoading] = useState(false);

  const [kbModalOpen, setKbModalOpen] = useState(false);
  const [editingKb, setEditingKb] = useState<KbSearchConfig | null>(null);
  const [kbForm] = Form.useForm();
  const [kbSaving, setKbSaving] = useState(false);

  const [sceneBindings, setSceneBindings] = useState<SceneBinding[]>([]);
  const [sceneLoading, setSceneLoading] = useState(false);
  const [sceneSaving, setSceneSaving] = useState(false);
  const [kbOptions, setKbOptions] = useState<KnowledgeBaseOption[]>([]);

  const fetchGlobalConfig = useCallback(async () => {
    setGlobalLoading(true);
    try {
      const res = await get<{ scope: string; config_json: GlobalSearchConfig | null }>('/api/admin/knowledge-bases/search-config');
      if (res.config_json) {
        globalForm.setFieldsValue(res.config_json);
      }
    } catch {
      // defaults
    } finally {
      setGlobalLoading(false);
    }
  }, [globalForm]);

  const fetchKbConfigs = useCallback(async () => {
    setKbLoading(true);
    try {
      const kbRes = await get<{ items: any[] }>('/api/admin/knowledge-bases', { page: 1, page_size: 200 });
      const kbs = kbRes.items || [];
      setKbOptions(kbs.map((k: any) => ({ id: k.id, name: k.name })));

      const configs: KbSearchConfig[] = [];
      for (const kb of kbs) {
        try {
          const res = await get<{ scope: string; config_json: GlobalSearchConfig | null }>(`/api/admin/knowledge-bases/${kb.id}/search-config`);
          configs.push({
            knowledge_base_id: kb.id,
            knowledge_base_name: kb.name,
            use_custom: res.config_json != null,
            config: res.config_json || undefined,
          });
        } catch {
          configs.push({
            knowledge_base_id: kb.id,
            knowledge_base_name: kb.name,
            use_custom: false,
          });
        }
      }
      setKbConfigs(configs);
    } catch {
      message.error('获取知识库配置失败');
    } finally {
      setKbLoading(false);
    }
  }, []);

  const fetchSceneBindings = useCallback(async () => {
    setSceneLoading(true);
    try {
      const res = await get<{ items: Array<{ id: number; scene: string; kb_id: number; is_primary: boolean }> }>('/api/admin/knowledge-bases/scene-bindings');
      const rawBindings = res.items || [];
      const grouped: Record<string, number[]> = {};
      for (const b of rawBindings) {
        if (!grouped[b.scene]) grouped[b.scene] = [];
        grouped[b.scene].push(b.kb_id);
      }
      const merged = SCENES.map((s) => ({
        scene: s.value,
        scene_label: s.label,
        knowledge_base_ids: grouped[s.value] || [],
      }));
      setSceneBindings(merged);
    } catch {
      setSceneBindings(SCENES.map((s) => ({ scene: s.value, scene_label: s.label, knowledge_base_ids: [] })));
    } finally {
      setSceneLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGlobalConfig();
    fetchKbConfigs();
    fetchSceneBindings();
  }, [fetchGlobalConfig, fetchKbConfigs, fetchSceneBindings]);

  const handleSaveGlobal = async () => {
    try {
      const values = await globalForm.validateFields();
      setGlobalSaving(true);
      await put('/api/admin/knowledge-bases/search-config', {
        scope: 'global',
        config_json: values,
      });
      message.success('全局策略保存成功');
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setGlobalSaving(false);
    }
  };

  const handleOpenKbModal = (record: KbSearchConfig) => {
    setEditingKb(record);
    kbForm.resetFields();
    if (record.config) {
      kbForm.setFieldsValue(record.config);
    }
    setKbModalOpen(true);
  };

  const handleSaveKbConfig = async () => {
    if (!editingKb) return;
    try {
      const values = await kbForm.validateFields();
      setKbSaving(true);
      await put(`/api/admin/knowledge-bases/${editingKb.knowledge_base_id}/search-config`, {
        scope: `kb_${editingKb.knowledge_base_id}`,
        config_json: values,
      });
      message.success('知识库策略保存成功');
      setKbModalOpen(false);
      fetchKbConfigs();
    } catch (e: any) {
      if (e?.errorFields) return;
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setKbSaving(false);
    }
  };

  const handleSceneBindingChange = (scene: string, ids: number[]) => {
    setSceneBindings((prev) =>
      prev.map((b) => (b.scene === scene ? { ...b, knowledge_base_ids: ids } : b))
    );
  };

  const handleSaveSceneBindings = async () => {
    setSceneSaving(true);
    try {
      const flatBindings: Array<{ scene: string; kb_id: number; is_primary: boolean }> = [];
      for (const b of sceneBindings) {
        for (let i = 0; i < b.knowledge_base_ids.length; i++) {
          flatBindings.push({
            scene: b.scene,
            kb_id: b.knowledge_base_ids[i],
            is_primary: i === 0,
          });
        }
      }
      await put('/api/admin/knowledge-bases/scene-bindings', flatBindings);
      message.success('场景绑定保存成功');
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '保存失败';
      message.error(typeof detail === 'string' ? detail : '保存失败');
    } finally {
      setSceneSaving(false);
    }
  };

  const kbColumns = [
    { title: '知识库名称', dataIndex: 'knowledge_base_name', key: 'knowledge_base_name', ellipsis: true },
    {
      title: '策略类型',
      key: 'use_custom',
      width: 120,
      render: (_: any, record: KbSearchConfig) =>
        record.use_custom ? <Tag color="blue">自定义</Tag> : <Tag>全局默认</Tag>,
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: KbSearchConfig) => (
        <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenKbModal(record)}>
          编辑策略
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>检索策略配置</Title>

      <Card title="全局默认策略" style={{ borderRadius: 12, marginBottom: 24 }}>
        <Spin spinning={globalLoading}>
          <Form
            form={globalForm}
            layout="vertical"
            initialValues={{
              exact_match_enabled: true,
              semantic_match_enabled: true,
              keyword_match_enabled: true,
              exact_match_priority: 1,
              semantic_match_priority: 2,
              keyword_match_priority: 3,
              similarity_threshold: 'standard',
              max_display_count: 3,
            }}
            style={{ maxWidth: 600 }}
          >
            <div style={{ display: 'flex', gap: 48, marginBottom: 16 }}>
              <Form.Item label="精确匹配" name="exact_match_enabled" valuePropName="checked" style={{ marginBottom: 8 }}>
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
              <Form.Item label="语义匹配" name="semantic_match_enabled" valuePropName="checked" style={{ marginBottom: 8 }}>
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
              <Form.Item label="关键词匹配" name="keyword_match_enabled" valuePropName="checked" style={{ marginBottom: 8 }}>
                <Switch checkedChildren="启用" unCheckedChildren="禁用" />
              </Form.Item>
            </div>

            <div style={{ display: 'flex', gap: 24, marginBottom: 16 }}>
              <Form.Item label="精确匹配优先级" name="exact_match_priority" style={{ flex: 1 }}>
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="语义匹配优先级" name="semantic_match_priority" style={{ flex: 1 }}>
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item label="关键词匹配优先级" name="keyword_match_priority" style={{ flex: 1 }}>
                <InputNumber min={1} max={10} style={{ width: '100%' }} />
              </Form.Item>
            </div>

            <Form.Item label="语义匹配相似度阈值" name="similarity_threshold">
              <Radio.Group>
                <Radio value="loose">宽松</Radio>
                <Radio value="standard">标准</Radio>
                <Radio value="strict">严格</Radio>
              </Radio.Group>
            </Form.Item>

            <Form.Item label="最大命中展示数量" name="max_display_count">
              <InputNumber min={1} max={5} />
            </Form.Item>

            <Form.Item>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveGlobal} loading={globalSaving}>
                保存全局策略
              </Button>
            </Form.Item>
          </Form>
        </Spin>
      </Card>

      <Card title="知识库级别策略" style={{ borderRadius: 12, marginBottom: 24 }}>
        <Table
          columns={kbColumns}
          dataSource={kbConfigs}
          rowKey="knowledge_base_id"
          loading={kbLoading}
          pagination={false}
        />
      </Card>

      <Card title="场景-知识库绑定" style={{ borderRadius: 12 }}>
        <Spin spinning={sceneLoading}>
          <Table
            dataSource={sceneBindings}
            rowKey="scene"
            pagination={false}
            columns={[
              { title: '场景', dataIndex: 'scene_label', key: 'scene_label', width: 160 },
              {
                title: '绑定知识库',
                key: 'knowledge_base_ids',
                render: (_: any, record: SceneBinding) => (
                  <Select
                    mode="multiple"
                    value={record.knowledge_base_ids}
                    onChange={(ids) => handleSceneBindingChange(record.scene, ids)}
                    options={kbOptions.map((k) => ({ label: k.name, value: k.id }))}
                    placeholder="选择知识库"
                    style={{ width: '100%', minWidth: 300 }}
                    allowClear
                  />
                ),
              },
            ]}
          />
          <div style={{ marginTop: 16 }}>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveSceneBindings} loading={sceneSaving}>
              保存场景绑定
            </Button>
          </div>
        </Spin>
      </Card>

      <Modal
        title={`编辑检索策略 - ${editingKb?.knowledge_base_name || ''}`}
        open={kbModalOpen}
        onOk={handleSaveKbConfig}
        onCancel={() => setKbModalOpen(false)}
        confirmLoading={kbSaving}
        destroyOnClose
        width={560}
      >
        <Form
          form={kbForm}
          layout="vertical"
          initialValues={{
            exact_match_enabled: true,
            semantic_match_enabled: true,
            keyword_match_enabled: true,
            exact_match_priority: 1,
            semantic_match_priority: 2,
            keyword_match_priority: 3,
            similarity_threshold: 'standard',
            max_display_count: 3,
          }}
        >
          <div style={{ display: 'flex', gap: 24, marginBottom: 8 }}>
            <Form.Item label="精确匹配" name="exact_match_enabled" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
            <Form.Item label="语义匹配" name="semantic_match_enabled" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
            <Form.Item label="关键词匹配" name="keyword_match_enabled" valuePropName="checked">
              <Switch checkedChildren="启用" unCheckedChildren="禁用" />
            </Form.Item>
          </div>
          <div style={{ display: 'flex', gap: 16 }}>
            <Form.Item label="精确匹配优先级" name="exact_match_priority" style={{ flex: 1 }}>
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="语义匹配优先级" name="semantic_match_priority" style={{ flex: 1 }}>
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="关键词匹配优先级" name="keyword_match_priority" style={{ flex: 1 }}>
              <InputNumber min={1} max={10} style={{ width: '100%' }} />
            </Form.Item>
          </div>
          <Form.Item label="语义匹配相似度阈值" name="similarity_threshold">
            <Radio.Group>
              <Radio value="loose">宽松</Radio>
              <Radio value="standard">标准</Radio>
              <Radio value="strict">严格</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item label="最大命中展示数量" name="max_display_count">
            <InputNumber min={1} max={5} />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
