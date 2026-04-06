'use client';

import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Card, Form, Input, InputNumber, Button, Space, message, Typography, Select,
  Switch, Spin, Tabs, Table, Tag, Modal, Upload, DatePicker, Image, Radio,
  Statistic, Row, Col, Tooltip, Popconfirm,
} from 'antd';
import {
  SaveOutlined, CheckCircleOutlined, CloseCircleOutlined,
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined,
  ExperimentOutlined, SearchOutlined, ReloadOutlined, EyeOutlined,
  StarOutlined, StopOutlined, CloudOutlined,
} from '@ant-design/icons';
import { get, put, post, del } from '@/lib/api';
import api from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { RangePicker } = DatePicker;
const { TextArea } = Input;

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
  ai_model_id: number | null;
  ocr_provider: string;
  is_preset: boolean;
}

interface AIModel {
  id: number;
  provider_name: string;
  model_name: string;
}

interface UploadLimits {
  max_batch_count: number;
  max_file_size_mb: number;
}

interface OcrRecord {
  id: number;
  created_at: string;
  scene_name: string;
  provider_name: string;
  status: string;
  original_image_url: string;
  ocr_raw_text: string;
  ai_structured_result: any;
  error_message: string;
}

interface RecordsResponse {
  items: OcrRecord[];
  total: number;
  page: number;
  page_size: number;
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

  // Scenes
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [scenesLoading, setScenesLoading] = useState(false);
  const [sceneModalOpen, setSceneModalOpen] = useState(false);
  const [editingScene, setEditingScene] = useState<Scene | null>(null);
  const [sceneForm] = Form.useForm();
  const [sceneSaving, setSceneSaving] = useState(false);

  // AI models
  const [aiModels, setAiModels] = useState<AIModel[]>([]);

  // Upload limits
  const [limitsForm] = Form.useForm();
  const [limitsLoading, setLimitsLoading] = useState(false);
  const [limitsSaving, setLimitsSaving] = useState(false);

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

  // Records
  const [records, setRecords] = useState<OcrRecord[]>([]);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [recordsPagination, setRecordsPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [recordFilters, setRecordFilters] = useState<{
    dateRange: [dayjs.Dayjs | null, dayjs.Dayjs | null] | null;
    provider: string | undefined;
    status: string | undefined;
    scene: string | undefined;
    keyword: string;
  }>({ dateRange: null, provider: undefined, status: undefined, scene: undefined, keyword: '' });
  const [selectedRecordKeys, setSelectedRecordKeys] = useState<React.Key[]>([]);

  // AI result detail modal
  const [aiResultModalOpen, setAiResultModalOpen] = useState(false);
  const [aiResultDetail, setAiResultDetail] = useState<any>(null);

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
    setScenesLoading(true);
    try {
      const res = await get<Scene[]>('/api/admin/ocr/scenes');
      setScenes(Array.isArray(res) ? res : []);
    } catch {
      setScenes([]);
    } finally {
      setScenesLoading(false);
    }
  }, []);

  const fetchAiModels = useCallback(async () => {
    try {
      const res = await get<{ items: AIModel[] }>('/api/admin/ai-config/models');
      setAiModels(res.items || res as any || []);
    } catch {
      setAiModels([]);
    }
  }, []);

  const fetchUploadLimits = useCallback(async () => {
    setLimitsLoading(true);
    try {
      const res = await get<UploadLimits>('/api/admin/ocr/upload-limits');
      limitsForm.setFieldsValue({
        max_batch_count: res.max_batch_count ?? 10,
        max_file_size_mb: res.max_file_size_mb ?? 5,
      });
    } catch {
      limitsForm.setFieldsValue({ max_batch_count: 10, max_file_size_mb: 5 });
    } finally {
      setLimitsLoading(false);
    }
  }, [limitsForm]);

  const fetchRecords = useCallback(async (page = 1, pageSize = 20) => {
    setRecordsLoading(true);
    try {
      const params: Record<string, any> = { page, page_size: pageSize };
      if (recordFilters.dateRange?.[0]) params.start_date = recordFilters.dateRange[0].format('YYYY-MM-DD');
      if (recordFilters.dateRange?.[1]) params.end_date = recordFilters.dateRange[1].format('YYYY-MM-DD');
      if (recordFilters.provider) params.provider_name = recordFilters.provider;
      if (recordFilters.status) params.status = recordFilters.status;
      if (recordFilters.scene) params.scene_name = recordFilters.scene;
      if (recordFilters.keyword) params.keyword = recordFilters.keyword;
      const res = await get<RecordsResponse>('/api/admin/ocr/records', params);
      setRecords(res.items || []);
      setRecordsPagination({ current: res.page || page, pageSize: res.page_size || pageSize, total: res.total || 0 });
    } catch {
      setRecords([]);
    } finally {
      setRecordsLoading(false);
    }
  }, [recordFilters]);

  useEffect(() => {
    fetchProviders();
    fetchScenes();
    fetchAiModels();
    fetchUploadLimits();
    fetchRecords();
  }, [fetchProviders, fetchScenes, fetchAiModels, fetchUploadLimits, fetchRecords]);

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

  // ────────── Scenes CRUD ──────────

  const openCreateScene = () => {
    setEditingScene(null);
    sceneForm.resetFields();
    sceneForm.setFieldsValue({ scene_name: '', prompt_content: '', ai_model_id: null, ocr_provider: 'auto' });
    setSceneModalOpen(true);
  };

  const openEditScene = (record: Scene) => {
    setEditingScene(record);
    sceneForm.resetFields();
    sceneForm.setFieldsValue({
      scene_name: record.scene_name,
      prompt_content: record.prompt_content,
      ai_model_id: record.ai_model_id,
      ocr_provider: record.ocr_provider || 'auto',
    });
    setSceneModalOpen(true);
  };

  const handleSaveScene = async () => {
    try {
      const values = await sceneForm.validateFields();
      setSceneSaving(true);
      if (editingScene) {
        await put(`/api/admin/ocr/scenes/${editingScene.id}`, values);
        message.success('场景更新成功');
      } else {
        await post('/api/admin/ocr/scenes', values);
        message.success('场景创建成功');
      }
      setSceneModalOpen(false);
      fetchScenes();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSceneSaving(false);
    }
  };

  const handleDeleteScene = async (id: number) => {
    try {
      await del(`/api/admin/ocr/scenes/${id}`);
      message.success('场景删除成功');
      fetchScenes();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  // ────────── Upload Limits ──────────

  const handleSaveLimits = async () => {
    try {
      const values = await limitsForm.validateFields();
      setLimitsSaving(true);
      await put('/api/admin/ocr/upload-limits', values);
      message.success('上传限制配置保存成功');
      fetchUploadLimits();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setLimitsSaving(false);
    }
  };

  // ────────── Records ──────────

  const handleSearchRecords = () => {
    setSelectedRecordKeys([]);
    fetchRecords(1, recordsPagination.pageSize);
  };

  const handleResetRecordFilters = () => {
    setRecordFilters({ dateRange: null, provider: undefined, status: undefined, scene: undefined, keyword: '' });
    setSelectedRecordKeys([]);
  };

  const handleBatchDelete = async () => {
    if (selectedRecordKeys.length === 0) {
      message.warning('请先选择要删除的记录');
      return;
    }
    try {
      await post('/api/admin/ocr/records/batch-delete', selectedRecordKeys);
      message.success('批量删除成功');
      setSelectedRecordKeys([]);
      fetchRecords(recordsPagination.current, recordsPagination.pageSize);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  // ────────── AI model options ──────────

  const aiModelOptions = useMemo(
    () => aiModels.map((m) => ({
      label: `${m.provider_name} - ${m.model_name}`,
      value: m.id,
    })),
    [aiModels],
  );

  const ocrProviderOptions = useMemo(
    () => [
      { label: '自动', value: 'auto' },
      ...PROVIDER_KEYS.map((k) => ({ label: PROVIDER_LABELS[k], value: k })),
    ],
    [],
  );

  // ────────── Scene columns ──────────

  const sceneColumns = [
    { title: '场景名称', dataIndex: 'scene_name', key: 'scene_name', width: 160 },
    {
      title: '提示词摘要',
      dataIndex: 'prompt_content',
      key: 'prompt_content',
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v}>
          <span>{v && v.length > 40 ? v.slice(0, 40) + '...' : v || '-'}</span>
        </Tooltip>
      ),
    },
    {
      title: 'AI模型',
      dataIndex: 'ai_model_id',
      key: 'ai_model_id',
      width: 200,
      render: (v: number | null) => {
        if (!v) return <Text type="secondary">默认</Text>;
        const m = aiModels.find((item) => item.id === v);
        return m ? `${m.provider_name} - ${m.model_name}` : `模型#${v}`;
      },
    },
    {
      title: 'OCR厂商',
      dataIndex: 'ocr_provider',
      key: 'ocr_provider',
      width: 120,
      render: (v: string) => (v === 'auto' || !v) ? '自动' : (PROVIDER_LABELS[v] || v),
    },
    {
      title: '操作',
      key: 'action',
      width: 160,
      render: (_: any, record: Scene) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEditScene(record)}>
            编辑
          </Button>
          {!record.is_preset ? (
            <Popconfirm title="确定删除此场景？" onConfirm={() => handleDeleteScene(record.id)}>
              <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          ) : (
            <Tag color="blue">预设</Tag>
          )}
        </Space>
      ),
    },
  ];

  // ────────── Record columns ──────────

  const recordColumns = [
    {
      title: '调用时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
    { title: '业务场景', dataIndex: 'scene_name', key: 'scene_name', width: 120 },
    {
      title: '使用厂商',
      dataIndex: 'provider_name',
      key: 'provider_name',
      width: 100,
      render: (v: string) => PROVIDER_LABELS[v] || v || '-',
    },
    {
      title: '识别状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => {
        if (v === 'success') return <Tag color="green">成功</Tag>;
        if (v === 'failed') return <Tag color="red">失败</Tag>;
        return <Tag>{v || '未知'}</Tag>;
      },
    },
    {
      title: '原始图片',
      dataIndex: 'original_image_url',
      key: 'original_image_url',
      width: 100,
      render: (v: string) =>
        v ? (
          <Image
            src={v}
            width={48}
            height={48}
            style={{ objectFit: 'cover', borderRadius: 4 }}
            preview={{ mask: <EyeOutlined /> }}
            fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F/PQAJpAN4kNMRdQAAAABJRU5ErkJggg=="
          />
        ) : '-',
    },
    {
      title: 'OCR原始文字',
      dataIndex: 'ocr_raw_text',
      key: 'ocr_raw_text',
      width: 180,
      ellipsis: true,
      render: (v: string) => (
        <Tooltip title={v} placement="topLeft">
          <span>{v && v.length > 30 ? v.slice(0, 30) + '...' : v || '-'}</span>
        </Tooltip>
      ),
    },
    {
      title: 'AI结构化结果',
      key: 'ai_structured_result',
      width: 120,
      render: (_: any, record: OcrRecord) =>
        record.ai_structured_result ? (
          <Button
            type="link"
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              setAiResultDetail(record.ai_structured_result);
              setAiResultModalOpen(true);
            }}
          >
            查看
          </Button>
        ) : (
          <Text type="secondary">-</Text>
        ),
    },
  ];

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

  // ────────── Render: AI result detail ──────────

  const renderAiResultDetail = () => {
    if (!aiResultDetail) return null;
    if (typeof aiResultDetail === 'object') {
      const entries = Array.isArray(aiResultDetail) ? aiResultDetail : Object.entries(aiResultDetail);
      if (!Array.isArray(aiResultDetail)) {
        return (
          <Table
            dataSource={Object.entries(aiResultDetail).map(([key, value], idx) => ({
              key: idx,
              field: key,
              value: typeof value === 'object' ? JSON.stringify(value, null, 2) : String(value ?? ''),
            }))}
            columns={[
              { title: '字段', dataIndex: 'field', key: 'field', width: 200 },
              { title: '值', dataIndex: 'value', key: 'value' },
            ]}
            pagination={false}
            size="small"
          />
        );
      }
      return <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6 }}>{JSON.stringify(entries, null, 2)}</pre>;
    }
    return <pre style={{ whiteSpace: 'pre-wrap', background: '#f5f5f5', padding: 12, borderRadius: 6 }}>{String(aiResultDetail)}</pre>;
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

                {/* ── AI Scene Config ── */}
                <Card
                  title="AI 处理配置"
                  style={{ borderRadius: 12 }}
                  extra={
                    <Button type="primary" icon={<PlusOutlined />} onClick={openCreateScene}>
                      新增场景
                    </Button>
                  }
                >
                  <Spin spinning={scenesLoading}>
                    <Table
                      dataSource={scenes}
                      columns={sceneColumns}
                      rowKey="id"
                      pagination={false}
                      locale={{ emptyText: '暂无场景配置' }}
                    />
                  </Spin>
                </Card>

                {/* ── Upload Limits ── */}
                <Card title="上传限制配置" style={{ borderRadius: 12 }}>
                  <Spin spinning={limitsLoading}>
                    <Form
                      form={limitsForm}
                      labelCol={{ span: 7 }}
                      wrapperCol={{ span: 10 }}
                      initialValues={{ max_batch_count: 10, max_file_size_mb: 5 }}
                    >
                      <Form.Item
                        label="单次最多上传张数"
                        name="max_batch_count"
                        rules={[{ required: true, message: '请输入最大张数' }]}
                      >
                        <InputNumber min={1} max={100} style={{ width: '100%' }} addonAfter="张" />
                      </Form.Item>
                      <Form.Item
                        label="单张图片大小上限"
                        name="max_file_size_mb"
                        rules={[{ required: true, message: '请输入大小上限' }]}
                      >
                        <InputNumber min={0.1} max={50} step={0.5} style={{ width: '100%' }} addonAfter="MB" />
                      </Form.Item>
                      <Form.Item wrapperCol={{ offset: 7, span: 10 }}>
                        <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveLimits} loading={limitsSaving}>
                          保存限制配置
                        </Button>
                      </Form.Item>
                    </Form>
                  </Spin>
                </Card>
              </div>
            ),
          }))}
        />
      </Spin>

      {/* ── Records Section ── */}
      <Card title="识别记录管理" style={{ borderRadius: 12, marginTop: 24 }}>
        <Space style={{ marginBottom: 16 }} wrap>
          <RangePicker
            value={recordFilters.dateRange as any}
            onChange={(dates) => setRecordFilters((prev) => ({ ...prev, dateRange: dates as [dayjs.Dayjs | null, dayjs.Dayjs | null] | null }))}
          />
          <Select
            placeholder="OCR厂商"
            value={recordFilters.provider}
            onChange={(v) => setRecordFilters((prev) => ({ ...prev, provider: v }))}
            allowClear
            style={{ width: 130 }}
            options={PROVIDER_KEYS.map((k) => ({ label: PROVIDER_LABELS[k], value: k }))}
          />
          <Select
            placeholder="识别状态"
            value={recordFilters.status}
            onChange={(v) => setRecordFilters((prev) => ({ ...prev, status: v }))}
            allowClear
            style={{ width: 120 }}
            options={[
              { label: '成功', value: 'success' },
              { label: '失败', value: 'failed' },
            ]}
          />
          <Select
            placeholder="业务场景"
            value={recordFilters.scene}
            onChange={(v) => setRecordFilters((prev) => ({ ...prev, scene: v }))}
            allowClear
            style={{ width: 150 }}
            options={scenes.map((s) => ({ label: s.scene_name, value: s.scene_name }))}
          />
          <Input.Search
            placeholder="关键词搜索"
            value={recordFilters.keyword}
            onChange={(e) => setRecordFilters((prev) => ({ ...prev, keyword: e.target.value }))}
            onSearch={handleSearchRecords}
            style={{ width: 200 }}
            allowClear
          />
          <Button type="primary" icon={<SearchOutlined />} onClick={handleSearchRecords}>搜索</Button>
          <Button icon={<ReloadOutlined />} onClick={() => { handleResetRecordFilters(); setTimeout(() => fetchRecords(1, recordsPagination.pageSize), 0); }}>重置</Button>
        </Space>
        {selectedRecordKeys.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <Space>
              <Text>已选择 {selectedRecordKeys.length} 条记录</Text>
              <Popconfirm title={`确定删除选中的 ${selectedRecordKeys.length} 条记录？`} onConfirm={handleBatchDelete}>
                <Button danger size="small" icon={<DeleteOutlined />}>批量删除</Button>
              </Popconfirm>
            </Space>
          </div>
        )}
        <Table
          dataSource={records}
          columns={recordColumns}
          rowKey="id"
          loading={recordsLoading}
          rowSelection={{
            selectedRowKeys: selectedRecordKeys,
            onChange: (keys) => setSelectedRecordKeys(keys),
          }}
          pagination={{
            current: recordsPagination.current,
            pageSize: recordsPagination.pageSize,
            total: recordsPagination.total,
            showSizeChanger: true,
            showQuickJumper: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => fetchRecords(page, pageSize),
          }}
          scroll={{ x: 1100 }}
        />
      </Card>

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

      {/* ── Scene Edit Modal ── */}
      <Modal
        title={editingScene ? '编辑场景' : '新增场景'}
        open={sceneModalOpen}
        onCancel={() => setSceneModalOpen(false)}
        footer={null}
        width={560}
        destroyOnClose
      >
        <Form form={sceneForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="场景名称" name="scene_name" rules={[{ required: true, message: '请输入场景名称' }]}>
            <Input placeholder="请输入场景名称" />
          </Form.Item>
          <Form.Item label="提示词" name="prompt_content" rules={[{ required: true, message: '请输入提示词' }]}>
            <TextArea rows={4} placeholder="请输入AI处理提示词" />
          </Form.Item>
          <Form.Item label="AI模型" name="ai_model_id">
            <Select
              placeholder="默认模型"
              allowClear
              options={aiModelOptions}
            />
          </Form.Item>
          <Form.Item label="OCR厂商" name="ocr_provider">
            <Select options={ocrProviderOptions} />
          </Form.Item>
          <Form.Item>
            <Space>
              <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveScene} loading={sceneSaving}>
                保存
              </Button>
              <Button onClick={() => setSceneModalOpen(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* ── AI Result Detail Modal ── */}
      <Modal
        title="AI 结构化结果详情"
        open={aiResultModalOpen}
        onCancel={() => setAiResultModalOpen(false)}
        footer={<Button onClick={() => setAiResultModalOpen(false)}>关闭</Button>}
        width={600}
      >
        {renderAiResultDetail()}
      </Modal>
    </div>
  );
}
