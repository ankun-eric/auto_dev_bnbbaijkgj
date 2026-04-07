'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Typography, Tabs, Card, Button, Space, Modal, Form, Input,
  InputNumber, Spin, message, Tooltip, Popconfirm, Tag, Row, Col,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SaveOutlined,
  FileTextOutlined, UploadOutlined,
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
    } catch {
      limitsForm.setFieldsValue({ max_batch_count: 10, max_file_size_mb: 5 });
    } finally {
      setLimitsLoading(false);
    }
  }, [limitsForm]);

  useEffect(() => {
    fetchScenes();
    fetchUploadLimits();
  }, [fetchScenes, fetchUploadLimits]);

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
