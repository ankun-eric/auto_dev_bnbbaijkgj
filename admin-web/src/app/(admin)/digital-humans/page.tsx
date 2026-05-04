'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Switch, Modal, Form, Input, Typography, message, Tag, Image,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, PlayCircleOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

const { Title } = Typography;
const { TextArea } = Input;

interface DigitalHuman {
  id: number;
  name: string;
  silent_video_url: string;
  speaking_video_url: string;
  tts_voice_id: string;
  description: string;
  thumbnail_url: string;
  is_enabled: boolean;
  created_at?: string;
  updated_at?: string;
}

export default function DigitalHumansPage() {
  const [items, setItems] = useState<DigitalHuman[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewItem, setPreviewItem] = useState<DigitalHuman | null>(null);
  const [editingItem, setEditingItem] = useState<DigitalHuman | null>(null);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [form] = Form.useForm();

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/digital-humans', { page, page_size: pageSize });
      if (Array.isArray(res)) {
        setItems(res);
        setTotal(res.length);
      } else {
        setItems(res.items || []);
        setTotal(res.total || 0);
      }
    } catch {
      message.error('获取数字人形象列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenModal = (record?: DigitalHuman) => {
    setEditingItem(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        name: record.name,
        silent_video_url: record.silent_video_url,
        speaking_video_url: record.speaking_video_url,
        tts_voice_id: record.tts_voice_id,
        description: record.description,
        thumbnail_url: record.thumbnail_url,
        is_enabled: record.is_enabled,
      });
    } else {
      form.setFieldsValue({ is_enabled: true });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      const payload = {
        name: values.name,
        silent_video_url: values.silent_video_url,
        speaking_video_url: values.speaking_video_url,
        tts_voice_id: values.tts_voice_id,
        description: values.description || '',
        thumbnail_url: values.thumbnail_url || '',
        is_enabled: values.is_enabled,
      };

      if (editingItem) {
        await put(`/api/admin/digital-humans/${editingItem.id}`, payload);
        message.success('数字人形象更新成功');
      } else {
        await post('/api/admin/digital-humans', payload);
        message.success('数字人形象创建成功');
      }
      setModalOpen(false);
      fetchData();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = (record: DigitalHuman) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除数字人形象「${record.name}」吗？`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await del(`/api/admin/digital-humans/${record.id}`);
          message.success('删除成功');
          fetchData();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const handleToggleEnabled = async (record: DigitalHuman, checked: boolean) => {
    try {
      await put(`/api/admin/digital-humans/${record.id}`, { is_enabled: checked });
      message.success('状态更新成功');
      fetchData();
    } catch {
      message.error('状态更新失败');
    }
  };

  const handlePreview = (record: DigitalHuman) => {
    setPreviewItem(record);
    setPreviewOpen(true);
  };

  const columns = [
    {
      title: '缩略图',
      dataIndex: 'thumbnail_url',
      key: 'thumbnail_url',
      width: 90,
      render: (val: string) =>
        val ? <Image src={resolveAssetUrl(val)} width={48} height={48} style={{ objectFit: 'cover', borderRadius: 4 }} fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F/PQAJpAN42kRfMwAAAABJRU5ErkJggg==" /> : '-',
    },
    {
      title: '形象名称',
      dataIndex: 'name',
      key: 'name',
      width: 150,
    },
    {
      title: 'TTS音色',
      dataIndex: 'tts_voice_id',
      key: 'tts_voice_id',
      width: 150,
      render: (val: string) => val || '-',
    },
    {
      title: '状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      width: 100,
      render: (val: boolean, record: DigitalHuman) => (
        <Switch
          checked={val}
          checkedChildren="启用"
          unCheckedChildren="禁用"
          onChange={(checked) => handleToggleEnabled(record, checked)}
        />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: DigitalHuman) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Button type="link" size="small" icon={<PlayCircleOutlined />} onClick={() => handlePreview(record)}>
            预览
          </Button>
          <Button type="link" size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(record)}>
            删除
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>数字人形象管理</Title>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增形象
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={items}
        rowKey="id"
        loading={loading}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
        scroll={{ x: 800 }}
      />
      <Modal
        title={editingItem ? '编辑数字人形象' : '新增数字人形象'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" initialValues={{ is_enabled: true }}>
          <Form.Item
            label="形象名称"
            name="name"
            rules={[{ required: true, message: '请输入形象名称' }]}
          >
            <Input placeholder="请输入形象名称" maxLength={30} />
          </Form.Item>
          <Form.Item
            label="静默视频URL"
            name="silent_video_url"
            rules={[{ required: true, message: '请输入静默视频URL' }]}
          >
            <Input placeholder="请输入静默状态视频URL" />
          </Form.Item>
          <Form.Item
            label="说话视频URL"
            name="speaking_video_url"
            rules={[{ required: true, message: '请输入说话视频URL' }]}
          >
            <Input placeholder="请输入说话状态视频URL" />
          </Form.Item>
          <Form.Item
            label="TTS音色ID"
            name="tts_voice_id"
            rules={[{ required: true, message: '请输入TTS音色ID' }]}
          >
            <Input placeholder="请输入TTS音色ID" />
          </Form.Item>
          <Form.Item label="形象描述" name="description">
            <TextArea rows={3} placeholder="请输入形象描述" maxLength={200} />
          </Form.Item>
          <Form.Item label="缩略图URL" name="thumbnail_url">
            <Input placeholder="请输入缩略图URL" />
          </Form.Item>
          <Form.Item label="启用状态" name="is_enabled" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title={`预览 - ${previewItem?.name || ''}`}
        open={previewOpen}
        onCancel={() => setPreviewOpen(false)}
        footer={null}
        destroyOnClose
        width={640}
      >
        {previewItem && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
            <div>
              <Tag color="blue" style={{ marginBottom: 8 }}>静默状态</Tag>
              {previewItem.silent_video_url ? (
                <video
                  src={previewItem.silent_video_url}
                  controls
                  loop
                  style={{ width: '100%', maxHeight: 300, borderRadius: 8, background: '#000' }}
                />
              ) : (
                <div style={{ padding: 24, textAlign: 'center', color: '#999', background: '#f5f5f5', borderRadius: 8 }}>
                  暂无视频
                </div>
              )}
            </div>
            <div>
              <Tag color="green" style={{ marginBottom: 8 }}>说话状态</Tag>
              {previewItem.speaking_video_url ? (
                <video
                  src={previewItem.speaking_video_url}
                  controls
                  loop
                  style={{ width: '100%', maxHeight: 300, borderRadius: 8, background: '#000' }}
                />
              ) : (
                <div style={{ padding: 24, textAlign: 'center', color: '#999', background: '#f5f5f5', borderRadius: 8 }}>
                  暂无视频
                </div>
              )}
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
}
