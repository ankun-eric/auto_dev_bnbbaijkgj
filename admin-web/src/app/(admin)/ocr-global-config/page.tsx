'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Tabs, Card, Button, Space, Modal, Form, Input,
  InputNumber, Spin, message, Tooltip, Popconfirm, Tag, Row, Col,
  Upload, Select, Collapse, Divider, Alert,
} from 'antd';
import type { UploadFile } from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SaveOutlined,
  FileTextOutlined, UploadOutlined, ExperimentOutlined,
  CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons';
import { get, put, post, del } from '@/lib/api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

interface Scene {
  id: number;
  scene_name: string;
  prompt_content: string;
  is_preset: boolean;
}

interface UploadLimits {
  max_batch_count: number;
  max_file_size_mb: number;
}

interface OcrProvider {
  provider: string;
  name: string;
}

interface OcrSingleResult {
  success: boolean;
  provider_name: string;
  ocr_text?: string;
  ai_result?: any;
  error?: string;
}

interface OcrTestBatchResponse {
  success: boolean;
  provider_name: string;
  results: OcrSingleResult[];
  merged_ocr_text?: string;
  error?: string;
}

interface OcrTestFullBatchResponse {
  success: boolean;
  provider_name: string;
  results: OcrSingleResult[];
  merged_ocr_text?: string;
  merged_ai_result?: any;
  error?: string;
}

export default function OcrGlobalConfigPage() {
  const [activeTab, setActiveTab] = useState('scenes');

  // Scenes
  const [scenes, setScenes] = useState<Scene[]>([]);
  const [scenesLoading, setScenesLoading] = useState(false);
  const [sceneModalOpen, setSceneModalOpen] = useState(false);
  const [editingScene, setEditingScene] = useState<Scene | null>(null);
  const [sceneForm] = Form.useForm();
  const [sceneSaving, setSceneSaving] = useState(false);

  // Upload limits
  const [limitsForm] = Form.useForm();
  const [limitsLoading, setLimitsLoading] = useState(false);
  const [limitsSaving, setLimitsSaving] = useState(false);

  // OCR Test
  const [testFiles, setTestFiles] = useState<UploadFile[]>([]);
  const [providers, setProviders] = useState<OcrProvider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<string>('');
  const [selectedSceneId, setSelectedSceneId] = useState<number | undefined>(undefined);
  const [uploadLimits, setUploadLimits] = useState<UploadLimits>({ max_batch_count: 10, max_file_size_mb: 5 });
  const [testLoading, setTestLoading] = useState(false);
  const [testOcrResult, setTestOcrResult] = useState<OcrTestBatchResponse | null>(null);
  const [testFullResult, setTestFullResult] = useState<OcrTestFullBatchResponse | null>(null);

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

  const fetchUploadLimits = useCallback(async () => {
    setLimitsLoading(true);
    try {
      const res = await get<UploadLimits>('/api/admin/ocr/upload-limits');
      limitsForm.setFieldsValue({
        max_batch_count: res.max_batch_count ?? 10,
        max_file_size_mb: res.max_file_size_mb ?? 5,
      });
      setUploadLimits({ max_batch_count: res.max_batch_count ?? 10, max_file_size_mb: res.max_file_size_mb ?? 5 });
    } catch {
      limitsForm.setFieldsValue({ max_batch_count: 10, max_file_size_mb: 5 });
    } finally {
      setLimitsLoading(false);
    }
  }, [limitsForm]);

  const fetchProviders = useCallback(async () => {
    try {
      const res = await get<OcrProvider[]>('/api/admin/ocr/providers');
      const list = Array.isArray(res) ? res : [];
      setProviders(list);
      if (list.length > 0 && !selectedProvider) {
        setSelectedProvider(list[0].provider);
      }
    } catch {
      setProviders([]);
    }
  }, [selectedProvider]);

  useEffect(() => {
    fetchScenes();
    fetchUploadLimits();
    fetchProviders();
  }, [fetchScenes, fetchUploadLimits, fetchProviders]);

  // ────────── Scenes CRUD ──────────

  const openCreateScene = () => {
    setEditingScene(null);
    sceneForm.resetFields();
    setSceneModalOpen(true);
  };

  const openEditScene = (record: Scene) => {
    setEditingScene(record);
    sceneForm.setFieldsValue({
      scene_name: record.scene_name,
      prompt_content: record.prompt_content,
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
      message.success('上传限制保存成功');
      fetchUploadLimits();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setLimitsSaving(false);
    }
  };

  // ────────── OCR Test ──────────

  const handleTestOcr = async () => {
    if (testFiles.length === 0) { message.warning('请先选择图片'); return; }
    if (!selectedProvider) { message.warning('请选择OCR提供商'); return; }
    setTestLoading(true);
    setTestOcrResult(null);
    setTestFullResult(null);
    try {
      const formData = new FormData();
      testFiles.forEach((f) => { if (f.originFileObj) formData.append('files', f.originFileObj); });
      formData.append('provider', selectedProvider);
      const res = await post<OcrTestBatchResponse>('/api/admin/ocr/test-ocr', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setTestOcrResult(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || 'OCR测试失败');
    } finally {
      setTestLoading(false);
    }
  };

  const handleTestFull = async () => {
    if (testFiles.length === 0) { message.warning('请先选择图片'); return; }
    if (!selectedProvider) { message.warning('请选择OCR提供商'); return; }
    setTestLoading(true);
    setTestOcrResult(null);
    setTestFullResult(null);
    try {
      const formData = new FormData();
      testFiles.forEach((f) => { if (f.originFileObj) formData.append('files', f.originFileObj); });
      formData.append('provider', selectedProvider);
      if (selectedSceneId !== undefined) formData.append('scene_id', String(selectedSceneId));
      const res = await post<OcrTestFullBatchResponse>('/api/admin/ocr/test-full', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setTestFullResult(res);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '完整测试失败');
    } finally {
      setTestLoading(false);
    }
  };

  // ────────── Render ──────────

  const renderSceneCards = () => (
    <Spin spinning={scenesLoading}>
      <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'flex-end' }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreateScene}>
          新增场景
        </Button>
      </div>
      <Row gutter={[16, 16]}>
        {scenes.map((scene) => (
          <Col span={8} key={scene.id}>
            <Card
              title={
                <Space>
                  <span>{scene.scene_name}</span>
                  {scene.is_preset && <Tag color="blue">预设</Tag>}
                </Space>
              }
              style={{ borderRadius: 12, height: '100%' }}
              actions={[
                <Button
                  key="edit"
                  type="link"
                  icon={<EditOutlined />}
                  onClick={() => openEditScene(scene)}
                >
                  编辑
                </Button>,
                scene.is_preset ? (
                  <Button key="delete" type="link" disabled icon={<DeleteOutlined />}>
                    删除
                  </Button>
                ) : (
                  <Popconfirm
                    key="delete"
                    title="确定删除此场景？"
                    onConfirm={() => handleDeleteScene(scene.id)}
                  >
                    <Button type="link" danger icon={<DeleteOutlined />}>
                      删除
                    </Button>
                  </Popconfirm>
                ),
              ]}
            >
              <Tooltip title={scene.prompt_content} placement="topLeft">
                <Paragraph
                  ellipsis={{ rows: 3 }}
                  style={{ marginBottom: 0, color: '#666', minHeight: 66 }}
                >
                  {scene.prompt_content || '-'}
                </Paragraph>
              </Tooltip>
            </Card>
          </Col>
        ))}
        {scenes.length === 0 && !scenesLoading && (
          <Col span={24}>
            <div style={{ textAlign: 'center', padding: '40px 0', color: '#999' }}>
              暂无场景模板，请点击右上角"新增场景"按钮创建
            </div>
          </Col>
        )}
      </Row>
    </Spin>
  );

  const renderUploadLimits = () => (
    <Card style={{ borderRadius: 12, maxWidth: 600 }}>
      <Spin spinning={limitsLoading}>
        <Form
          form={limitsForm}
          labelCol={{ span: 8 }}
          wrapperCol={{ span: 12 }}
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
            label="单张图片最大尺寸"
            name="max_file_size_mb"
            rules={[{ required: true, message: '请输入大小上限' }]}
          >
            <InputNumber min={0.1} max={50} step={0.5} style={{ width: '100%' }} addonAfter="MB" />
          </Form.Item>
          <Form.Item wrapperCol={{ offset: 8, span: 12 }}>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSaveLimits} loading={limitsSaving}>
              保存
            </Button>
          </Form.Item>
        </Form>
      </Spin>
    </Card>
  );

  const renderOcrTest = () => {
    const activeResult = testFullResult ?? testOcrResult;
    return (
      <div>
        <Card style={{ borderRadius: 12, marginBottom: 16 }}>
          <Row gutter={[16, 16]}>
            <Col span={24}>
              <Text strong>选择图片</Text>
              <div style={{ marginTop: 8 }}>
                <Upload
                  multiple
                  listType="picture-card"
                  fileList={testFiles}
                  beforeUpload={() => false}
                  onChange={({ fileList }) => setTestFiles(fileList)}
                  accept="image/*"
                  maxCount={uploadLimits.max_batch_count}
                >
                  {testFiles.length < uploadLimits.max_batch_count && (
                    <div>
                      <PlusOutlined />
                      <div style={{ marginTop: 8 }}>上传图片</div>
                    </div>
                  )}
                </Upload>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  最多 {uploadLimits.max_batch_count} 张，单张不超过 {uploadLimits.max_file_size_mb} MB
                </Text>
              </div>
            </Col>
            <Col xs={24} md={12}>
              <Text strong>OCR 提供商</Text>
              <Select
                style={{ width: '100%', marginTop: 8 }}
                value={selectedProvider || undefined}
                onChange={setSelectedProvider}
                placeholder="请选择OCR提供商"
                options={providers.map((p) => ({ value: p.provider, label: p.name }))}
              />
            </Col>
            <Col xs={24} md={12}>
              <Text strong>场景模板（可选）</Text>
              <Select
                style={{ width: '100%', marginTop: 8 }}
                value={selectedSceneId}
                onChange={setSelectedSceneId}
                placeholder="不选则不使用AI处理"
                allowClear
                options={scenes.map((s) => ({ value: s.id, label: s.scene_name }))}
              />
            </Col>
            <Col span={24}>
              <Space>
                <Button
                  type="primary"
                  icon={<ExperimentOutlined />}
                  onClick={handleTestOcr}
                  loading={testLoading}
                  disabled={testFiles.length === 0 || !selectedProvider}
                >
                  仅OCR测试
                </Button>
                <Button
                  type="default"
                  icon={<ExperimentOutlined />}
                  onClick={handleTestFull}
                  loading={testLoading}
                  disabled={testFiles.length === 0 || !selectedProvider}
                >
                  完整测试（含AI）
                </Button>
              </Space>
            </Col>
          </Row>
        </Card>

        {activeResult && (
          <Card style={{ borderRadius: 12 }} title="测试结果">
            <Spin spinning={testLoading}>
              {activeResult.error && (
                <Alert type="error" message={activeResult.error} style={{ marginBottom: 16 }} />
              )}
              <div style={{ marginBottom: 8 }}>
                <Tag color={activeResult.success ? 'success' : 'error'}>
                  {activeResult.success ? '成功' : '失败'}
                </Tag>
                <Text type="secondary">提供商：{activeResult.provider_name}</Text>
              </div>

              {activeResult.results && activeResult.results.length > 0 && (
                <>
                  <Divider orientation="left">逐图结果</Divider>
                  <Collapse
                    size="small"
                    items={activeResult.results.map((r, idx) => ({
                      key: idx,
                      label: (
                        <Space>
                          {r.success
                            ? <CheckCircleOutlined style={{ color: '#52c41a' }} />
                            : <CloseCircleOutlined style={{ color: '#ff4d4f' }} />}
                          <span>图片 {idx + 1}</span>
                          {!r.success && r.error && <Text type="danger" style={{ fontSize: 12 }}>{r.error}</Text>}
                        </Space>
                      ),
                      children: r.success ? (
                        <div>
                          {r.ocr_text && (
                            <div style={{ marginBottom: 8 }}>
                              <Text strong>OCR 文本：</Text>
                              <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-all', marginTop: 4 }}>
                                {r.ocr_text}
                              </pre>
                            </div>
                          )}
                          {r.ai_result !== undefined && (
                            <div>
                              <Text strong>AI 结果：</Text>
                              <pre style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-all', marginTop: 4 }}>
                                {typeof r.ai_result === 'string' ? r.ai_result : JSON.stringify(r.ai_result, null, 2)}
                              </pre>
                            </div>
                          )}
                        </div>
                      ) : (
                        <Alert type="error" message={r.error || '识别失败'} />
                      ),
                    }))}
                  />
                </>
              )}

              {activeResult.merged_ocr_text && (
                <>
                  <Divider orientation="left">合并 OCR 文本</Divider>
                  <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 6, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {activeResult.merged_ocr_text}
                  </pre>
                </>
              )}

              {(activeResult as OcrTestFullBatchResponse).merged_ai_result !== undefined && (
                <>
                  <Divider orientation="left">合并 AI 结果</Divider>
                  <pre style={{ background: '#f5f5f5', padding: 12, borderRadius: 6, whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {typeof (activeResult as OcrTestFullBatchResponse).merged_ai_result === 'string'
                      ? (activeResult as OcrTestFullBatchResponse).merged_ai_result
                      : JSON.stringify((activeResult as OcrTestFullBatchResponse).merged_ai_result, null, 2)}
                  </pre>
                </>
              )}
            </Spin>
          </Card>
        )}
      </div>
    );
  };

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>OCR全局设置</Title>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={[
          {
            key: 'scenes',
            label: (
              <span><FileTextOutlined style={{ marginRight: 6 }} />场景模板管理</span>
            ),
            children: renderSceneCards(),
          },
          {
            key: 'upload-limits',
            label: (
              <span><UploadOutlined style={{ marginRight: 6 }} />上传限制</span>
            ),
            children: renderUploadLimits(),
          },
          {
            key: 'ocr-test',
            label: (
              <span><ExperimentOutlined style={{ marginRight: 6 }} />OCR测试</span>
            ),
            children: renderOcrTest(),
          },
        ]}
      />

      <Modal
        title={editingScene ? '编辑场景' : '新增场景'}
        open={sceneModalOpen}
        onCancel={() => setSceneModalOpen(false)}
        footer={null}
        width={560}
        destroyOnClose
      >
        <Form form={sceneForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            label="场景名称"
            name="scene_name"
            rules={[{ required: true, message: '请输入场景名称' }]}
          >
            <Input placeholder="请输入场景名称" />
          </Form.Item>
          <Form.Item
            label="AI 提示词"
            name="prompt_content"
            rules={[{ required: true, message: '请输入AI提示词' }]}
          >
            <TextArea rows={6} placeholder="请输入AI提示词" />
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
    </div>
  );
}
