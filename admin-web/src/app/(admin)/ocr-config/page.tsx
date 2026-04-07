'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Card, Form, Input, InputNumber, Button, Space, message, Typography, Select,
  Switch, Spin, Tabs, Table, Tag, Modal, Upload, Radio,
  Statistic, Row, Col, Tooltip,
} from 'antd';
import {
  SaveOutlined,
  UploadOutlined,
  ExperimentOutlined,
  StarOutlined, StopOutlined, CloudOutlined,
} from '@ant-design/icons';
import { get, put, post } from '@/lib/api';
import api from '@/lib/api';

const { Title, Text } = Typography;

// ────────────────────── Types ──────────────────────

interface ProviderConfig {
  id: number;
  provider_name: string;
  display_name: string;
  is_enabled: boolean;
  is_preferred: boolean;
  config_json: Record<string, string>;
  status_label: string;
}

interface StatisticsData {
  total_calls: number;
  success_calls: number;
  success_rate: number;
}

interface ProviderStatItem {
  provider_name: string;
  total_calls: number;
  success_calls: number;
  fail_calls: number;
  success_rate: number;
}

interface StatisticsResponse {
  period: string;
  providers: ProviderStatItem[];
  total_calls: number;
  total_success: number;
}

interface Scene {
  id: number;
  scene_name: string;
  prompt_content: string;
  is_preset: boolean;
}

// ────────────────────── Constants ──────────────────────

const PROVIDER_KEYS = ['baidu', 'tencent', 'aliyun'] as const;

const PROVIDER_LABELS: Record<string, string> = {
  baidu: '百度云',
  tencent: '腾讯云',
  aliyun: '阿里云',
};

const PROVIDER_FIELDS: Record<string, { key: string; label: string }[]> = {
  baidu: [
    { key: 'app_id', label: 'APP ID' },
    { key: 'api_key', label: 'API Key' },
    { key: 'secret_key', label: 'Secret Key' },
  ],
  tencent: [
    { key: 'secret_id', label: 'SecretId' },
    { key: 'secret_key', label: 'SecretKey' },
  ],
  aliyun: [
    { key: 'access_key_id', label: 'AccessKey ID' },
    { key: 'access_key_secret', label: 'AccessKey Secret' },
  ],
};

const SECRET_FIELD_KEYS = new Set([
  'secret_key', 'access_key_secret',
]);

const PERIOD_OPTIONS = [
  { label: '今天', value: 'today' },
  { label: '近7天', value: '7d' },
  { label: '近30天', value: '30d' },
  { label: '全部', value: 'all' },
];

// ────────────────────── Main Component ──────────────────────

export default function OcrConfigPage() {
  const [activeProvider, setActiveProvider] = useState<string>('baidu');
  const [providers, setProviders] = useState<ProviderConfig[]>([]);
  const [providersLoading, setProvidersLoading] = useState(false);

  // Provider form
  const [providerForm] = Form.useForm();
  const [providerSaving, setProviderSaving] = useState(false);

  // Statistics
  const [statPeriod, setStatPeriod] = useState('today');
  const [statistics, setStatistics] = useState<Record<string, StatisticsData>>({});
  const [statsLoading, setStatsLoading] = useState(false);

  // Scenes (only for test-full dropdown)
  const [scenes, setScenes] = useState<Scene[]>([]);

  // Test OCR modal
  const [testOcrOpen, setTestOcrOpen] = useState(false);
  const [testOcrFile, setTestOcrFile] = useState<File | null>(null);
  const [testOcrLoading, setTestOcrLoading] = useState(false);
  const [testOcrResult, setTestOcrResult] = useState<string | null>(null);

  // Test full modal
  const [testFullOpen, setTestFullOpen] = useState(false);
  const [testFullFile, setTestFullFile] = useState<File | null>(null);
  const [testFullScene, setTestFullScene] = useState<number | undefined>(undefined);
  const [testFullLoading, setTestFullLoading] = useState(false);
  const [testFullResult, setTestFullResult] = useState<any>(null);


  // ────────── Data Fetching ──────────

  const fetchProviders = useCallback(async () => {
    setProvidersLoading(true);
    try {
      const res = await get<ProviderConfig[]>('/api/admin/ocr/providers');
      setProviders(res || []);
    } catch {
      setProviders([]);
    } finally {
      setProvidersLoading(false);
    }
  }, []);

  const fetchStatistics = useCallback(async (period: string) => {
    setStatsLoading(true);
    try {
      const res = await get<StatisticsResponse>('/api/admin/ocr/statistics', { period });
      const map: Record<string, StatisticsData> = {};
      for (const p of res.providers || []) {
        map[p.provider_name] = { total_calls: p.total_calls, success_calls: p.success_calls, success_rate: p.success_rate };
      }
      setStatistics(map);
    } catch {
      setStatistics({});
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const fetchScenes = useCallback(async () => {
    try {
      const res = await get<Scene[]>('/api/admin/ocr/scenes');
      setScenes(Array.isArray(res) ? res : []);
    } catch {
      setScenes([]);
    }
  }, []);

  useEffect(() => {
    fetchProviders();
    fetchScenes();
  }, [fetchProviders, fetchScenes]);

  useEffect(() => {
    fetchStatistics(statPeriod);
  }, [statPeriod, fetchStatistics]);

  // Sync provider form when active provider or providers data changes
  useEffect(() => {
    const current = providers.find((p) => p.provider_name === activeProvider);
    if (current) {
      const formValues: Record<string, any> = { is_enabled: current.is_enabled };
      PROVIDER_FIELDS[activeProvider]?.forEach((field) => {
        formValues[field.key] = '';
      });
      providerForm.setFieldsValue(formValues);
    } else {
      providerForm.resetFields();
    }
  }, [activeProvider, providers, providerForm]);

  // ────────── Provider helpers ──────────

  const currentProvider = useMemo(
    () => providers.find((p) => p.provider_name === activeProvider),
    [providers, activeProvider],
  );

  const getProviderStatus = useCallback(
    (providerKey: string): 'enabled' | 'disabled' | 'unconfigured' => {
      const p = providers.find((item) => item.provider_name === providerKey);
      if (!p) return 'unconfigured';
      const hasConfig = p.config_json && Object.values(p.config_json).some((v) => v && v.length > 0);
      if (p.is_enabled && hasConfig) return 'enabled';
      if (hasConfig) return 'disabled';
      return 'unconfigured';
    },
    [providers],
  );

  const getTabLabel = useCallback(
    (providerKey: string) => {
      const status = getProviderStatus(providerKey);
      const name = PROVIDER_LABELS[providerKey];
      if (status === 'enabled') return <span>{name} <span style={{ color: '#52c41a' }}>✓ 已启用</span></span>;
      if (status === 'disabled') return <span>{name} <span style={{ color: '#999' }}>○ 已禁用</span></span>;
      return <span>{name} <span style={{ color: '#ff4d4f' }}>✗ 未配置</span></span>;
    },
    [getProviderStatus],
  );

  // ────────── Provider actions ──────────

  const handleSaveProvider = async () => {
    try {
      const values = await providerForm.validateFields();
      setProviderSaving(true);
      const payload: Record<string, any> = { is_enabled: values.is_enabled };
      const config: Record<string, string> = {};
      PROVIDER_FIELDS[activeProvider]?.forEach((field) => {
        if (values[field.key]) {
          config[field.key] = values[field.key];
        }
      });
      payload.config_json = config;
      await put(`/api/admin/ocr/providers/${activeProvider}`, payload);
      message.success('配置保存成功');
      fetchProviders();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setProviderSaving(false);
    }
  };

  const handleSetPreferred = async () => {
    try {
      await post(`/api/admin/ocr/providers/${activeProvider}/preferred`);
      message.success(`已将${PROVIDER_LABELS[activeProvider]}设为首选厂商`);
      fetchProviders();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '设置失败');
    }
  };

  const handleDisableProvider = async () => {
    try {
      await post(`/api/admin/ocr/providers/${activeProvider}/disable`);
      message.success(`已禁用${PROVIDER_LABELS[activeProvider]}`);
      fetchProviders();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  // ────────── Test OCR ──────────

  const handleTestOcr = async () => {
    if (!testOcrFile) {
      message.warning('请先选择图片');
      return;
    }
    setTestOcrLoading(true);
    setTestOcrResult(null);
    try {
      const formData = new FormData();
      formData.append('file', testOcrFile);
      formData.append('provider', activeProvider);
      const res = await api.post('/api/admin/ocr/test-ocr', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setTestOcrResult(res.data?.text || res.data?.ocr_text || JSON.stringify(res.data, null, 2));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'OCR识别测试失败');
    } finally {
      setTestOcrLoading(false);
    }
  };

  // ────────── Test Full Flow ──────────

  const handleTestFull = async () => {
    if (!testFullFile) {
      message.warning('请先选择图片');
      return;
    }
    if (!testFullScene) {
      message.warning('请选择业务场景');
      return;
    }
    setTestFullLoading(true);
    setTestFullResult(null);
    try {
      const formData = new FormData();
      formData.append('file', testFullFile);
      formData.append('provider', activeProvider);
      formData.append('scene_id', String(testFullScene));
      const res = await api.post('/api/admin/ocr/test-full', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setTestFullResult(res.data?.result || res.data);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '完整流程测试失败');
    } finally {
      setTestFullLoading(false);
    }
  };

  // ────────── Render: Test Full result table ──────────

  const renderFullTestResult = () => {
    if (!testFullResult) return null;
    if (typeof testFullResult === 'object' && !Array.isArray(testFullResult)) {
      const entries = Object.entries(testFullResult);
      return (
        <Table
          dataSource={entries.map(([key, value], idx) => ({ key: idx, field: key, value: typeof value === 'object' ? JSON.stringify(value) : String(value ?? '') }))}
          columns={[
            { title: '字段', dataIndex: 'field', key: 'field', width: 200 },
            { title: '值', dataIndex: 'value', key: 'value' },
          ]}
          pagination={false}
          size="small"
          style={{ marginTop: 16 }}
        />
      );
    }
    if (Array.isArray(testFullResult)) {
      if (testFullResult.length === 0) return <Text type="secondary">空结果</Text>;
      const cols = Object.keys(testFullResult[0]).map((k) => ({
        title: k,
        dataIndex: k,
        key: k,
        render: (v: any) => (typeof v === 'object' ? JSON.stringify(v) : String(v ?? '')),
      }));
      return (
        <Table
          dataSource={testFullResult.map((item: any, idx: number) => ({ ...item, key: idx }))}
          columns={cols}
          pagination={false}
          size="small"
          scroll={{ x: 'max-content' }}
          style={{ marginTop: 16 }}
        />
      );
    }
    return <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6, marginTop: 16 }}>{String(testFullResult)}</pre>;
  };


  // ────────── Current statistics ──────────

  const currentStats = useMemo<StatisticsData>(
    () => statistics[activeProvider] || { total_calls: 0, success_calls: 0, success_rate: 0 },
    [statistics, activeProvider],
  );

  // ────────── Render ──────────

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>
        {PROVIDER_LABELS[activeProvider]} OCR识别配置
      </Title>

      <Spin spinning={providersLoading}>
        <Tabs
          activeKey={activeProvider}
          onChange={(key) => setActiveProvider(key)}
          items={PROVIDER_KEYS.map((key) => ({
            key,
            label: getTabLabel(key),
            children: (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
                {/* ── Provider Config Form ── */}
                <Card title={<Space><CloudOutlined /><span>{PROVIDER_LABELS[key]}配置</span></Space>} style={{ borderRadius: 12 }}>
                  <Form
                    form={providerForm}
                    labelCol={{ span: 5 }}
                    wrapperCol={{ span: 14 }}
                    initialValues={{ is_enabled: false }}
                  >
                    <Form.Item label="启用状态" name="is_enabled" valuePropName="checked">
                      <Switch checkedChildren="启用" unCheckedChildren="关闭" />
                    </Form.Item>
                    {PROVIDER_FIELDS[key]?.map((field) => {
                      const isSecret = SECRET_FIELD_KEYS.has(field.key);
                      const existingVal = currentProvider?.config_json?.[field.key];
                      const hasExisting = !!existingVal && existingVal.length > 0;
                      return (
                        <Form.Item key={field.key} label={field.label} name={field.key}>
                          {isSecret ? (
                            <Input.Password
                              placeholder={hasExisting ? '已设置（重新输入将覆盖）' : `请输入${field.label}`}
                            />
                          ) : (
                            <Input
                              placeholder={hasExisting ? '已设置（重新输入将覆盖）' : `请输入${field.label}`}
                            />
                          )}
                        </Form.Item>
                      );
                    })}
                    {currentProvider?.config_json && Object.values(currentProvider.config_json).some((v) => v) && (
                      <Form.Item wrapperCol={{ offset: 5, span: 14 }}>
                        <div style={{ color: '#999', fontSize: 12 }}>
                          {PROVIDER_FIELDS[key]?.map((field) => {
                            const val = currentProvider.config_json[field.key];
                            if (!val) return null;
                            return (
                              <div key={field.key}>
                                {field.label}: {val}
                              </div>
                            );
                          })}
                        </div>
                      </Form.Item>
                    )}
                    <Form.Item wrapperCol={{ offset: 5, span: 14 }}>
                      <Space wrap>
                        <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveProvider} loading={providerSaving}>
                          保存配置
                        </Button>
                        <Button icon={<ExperimentOutlined />} onClick={() => { setTestOcrFile(null); setTestOcrResult(null); setTestOcrOpen(true); }}>
                          测试OCR
                        </Button>
                        <Button icon={<ExperimentOutlined />} onClick={() => { setTestFullFile(null); setTestFullScene(undefined); setTestFullResult(null); setTestFullOpen(true); }}>
                          测试完整流程
                        </Button>
                      </Space>
                    </Form.Item>
                  </Form>
                </Card>

                {/* ── Statistics ── */}
                <Card
                  title="成功率统计"
                  style={{ borderRadius: 12 }}
                  extra={
                    <Radio.Group
                      value={statPeriod}
                      onChange={(e) => setStatPeriod(e.target.value)}
                      optionType="button"
                      buttonStyle="solid"
                      size="small"
                      options={PERIOD_OPTIONS}
                    />
                  }
                >
                  <Spin spinning={statsLoading}>
                    <Row gutter={24} style={{ marginBottom: 16 }}>
                      <Col span={8}>
                        <Statistic title="调用次数" value={currentStats.total_calls} />
                      </Col>
                      <Col span={8}>
                        <Statistic title="成功次数" value={currentStats.success_calls} valueStyle={{ color: '#52c41a' }} />
                      </Col>
                      <Col span={8}>
                        <Statistic
                          title="成功率"
                          value={currentStats.success_rate}
                          suffix="%"
                          precision={1}
                          valueStyle={{ color: currentStats.success_rate >= 90 ? '#52c41a' : currentStats.success_rate >= 60 ? '#faad14' : '#ff4d4f' }}
                        />
                      </Col>
                    </Row>
                    <Space>
                      <Button
                        type="primary"
                        ghost
                        icon={<StarOutlined />}
                        onClick={handleSetPreferred}
                        disabled={currentProvider?.is_preferred}
                      >
                        {currentProvider?.is_preferred ? '已是首选厂商' : '指定为首选厂商'}
                      </Button>
                      <Button
                        danger
                        ghost
                        icon={<StopOutlined />}
                        onClick={handleDisableProvider}
                        disabled={!currentProvider?.is_enabled}
                      >
                        临时禁用此厂商
                      </Button>
                    </Space>
                  </Spin>
                </Card>
              </div>
            ),
          }))}
        />
      </Spin>

      {/* ── Test OCR Modal ── */}
      <Modal
        title={`测试OCR识别 - ${PROVIDER_LABELS[activeProvider]}`}
        open={testOcrOpen}
        onCancel={() => setTestOcrOpen(false)}
        footer={null}
        width={600}
        destroyOnClose
      >
        <div style={{ marginBottom: 16 }}>
          <Upload
            accept="image/*"
            maxCount={1}
            beforeUpload={(file) => {
              setTestOcrFile(file);
              return false;
            }}
            onRemove={() => setTestOcrFile(null)}
            listType="picture-card"
          >
            {!testOcrFile && (
              <div>
                <UploadOutlined style={{ fontSize: 24 }} />
                <div style={{ marginTop: 8 }}>选择图片</div>
              </div>
            )}
          </Upload>
        </div>
        <Button type="primary" onClick={handleTestOcr} loading={testOcrLoading} disabled={!testOcrFile}>
          开始识别
        </Button>
        {testOcrResult && (
          <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 6, whiteSpace: 'pre-wrap', maxHeight: 300, overflow: 'auto' }}>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>识别结果：</Text>
            {testOcrResult}
          </div>
        )}
      </Modal>

      {/* ── Test Full Flow Modal ── */}
      <Modal
        title={`测试完整流程 - ${PROVIDER_LABELS[activeProvider]}`}
        open={testFullOpen}
        onCancel={() => setTestFullOpen(false)}
        footer={null}
        width={700}
        destroyOnClose
      >
        <div style={{ marginBottom: 16 }}>
          <Upload
            accept="image/*"
            maxCount={1}
            beforeUpload={(file) => {
              setTestFullFile(file);
              return false;
            }}
            onRemove={() => setTestFullFile(null)}
            listType="picture-card"
          >
            {!testFullFile && (
              <div>
                <UploadOutlined style={{ fontSize: 24 }} />
                <div style={{ marginTop: 8 }}>选择图片</div>
              </div>
            )}
          </Upload>
        </div>
        <div style={{ marginBottom: 16 }}>
          <Text style={{ display: 'block', marginBottom: 8 }}>业务场景：</Text>
          <Select
            placeholder="请选择业务场景"
            value={testFullScene}
            onChange={(v) => setTestFullScene(v)}
            style={{ width: '100%' }}
            options={scenes.map((s) => ({ label: s.scene_name, value: s.id }))}
          />
        </div>
        <Button type="primary" onClick={handleTestFull} loading={testFullLoading} disabled={!testFullFile || !testFullScene}>
          开始测试
        </Button>
        {testFullResult && (
          <div style={{ marginTop: 16 }}>
            <Text strong>AI 结构化结果：</Text>
            {renderFullTestResult()}
          </div>
        )}
      </Modal>
    </div>
  );
}
