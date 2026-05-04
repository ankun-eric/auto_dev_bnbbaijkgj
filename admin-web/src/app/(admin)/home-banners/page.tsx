'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input, Select, InputNumber,
  Typography, message, Popconfirm, Image, Upload,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ArrowUpOutlined, ArrowDownOutlined,
  UploadOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload } from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

const { Title } = Typography;

interface HomeBanner {
  id: number;
  image_url: string;
  link_type: string;
  link_url: string;
  miniprogram_appid?: string;
  sort_order: number;
  is_visible: boolean;
}

export default function HomeBannersPage() {
  const [banners, setBanners] = useState<HomeBanner[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingBanner, setEditingBanner] = useState<HomeBanner | null>(null);
  const [saving, setSaving] = useState(false);
  const [form] = Form.useForm();
  const [linkType, setLinkType] = useState<string>('none');
  const [uploading, setUploading] = useState(false);

  const fetchBanners = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<HomeBanner[]>('/api/admin/home-banners');
      const data = Array.isArray(res) ? res : (res as any).items || [];
      setBanners(data);
    } catch {
      message.error('获取Banner列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBanners();
  }, [fetchBanners]);

  const handleToggleVisible = async (record: HomeBanner, checked: boolean) => {
    try {
      await put(`/api/admin/home-banners/${record.id}`, { ...record, is_visible: checked });
      message.success('状态更新成功');
      fetchBanners();
    } catch {
      message.error('状态更新失败');
    }
  };

  const handleOpenModal = (record?: HomeBanner) => {
    setEditingBanner(record || null);
    form.resetFields();
    if (record) {
      form.setFieldsValue({
        image_url: record.image_url,
        link_type: record.link_type || 'none',
        link_url: record.link_url,
        miniprogram_appid: record.miniprogram_appid,
        sort_order: record.sort_order,
        is_visible: record.is_visible,
      });
      setLinkType(record.link_type || 'none');
    } else {
      form.setFieldsValue({ is_visible: true, sort_order: 0, link_type: 'none' });
      setLinkType('none');
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);
      if (editingBanner) {
        await put(`/api/admin/home-banners/${editingBanner.id}`, values);
        message.success('Banner更新成功');
      } else {
        await post('/api/admin/home-banners', values);
        message.success('Banner创建成功');
      }
      setModalOpen(false);
      fetchBanners();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/home-banners/${id}`);
      message.success('Banner删除成功');
      fetchBanners();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const handleMove = async (index: number, direction: 'up' | 'down') => {
    const newBanners = [...banners];
    const targetIndex = direction === 'up' ? index - 1 : index + 1;
    if (targetIndex < 0 || targetIndex >= newBanners.length) return;
    [newBanners[index], newBanners[targetIndex]] = [newBanners[targetIndex], newBanners[index]];
    const sortPayload = newBanners.map((b, i) => ({ id: b.id, sort_order: i }));
    try {
      await put('/api/admin/home-banners/sort', sortPayload);
      message.success('排序更新成功');
      fetchBanners();
    } catch {
      message.error('排序更新失败');
    }
  };

  const handleUploadImage = async (file: File) => {
    setUploading(true);
    try {
      const res = await upload<{ url: string }>('/api/upload/image', file);
      form.setFieldsValue({ image_url: res.url });
      message.success('图片上传成功');
    } catch {
      message.error('图片上传失败');
    } finally {
      setUploading(false);
    }
  };

  const linkTypeLabel = (type: string) => {
    const map: Record<string, string> = {
      internal: '内部页面',
      external: '外部链接',
      miniprogram: '小程序',
      none: '无跳转',
    };
    return map[type] || type;
  };

  const linkTypeColor = (type: string) => {
    const map: Record<string, string> = {
      internal: 'blue',
      external: 'green',
      miniprogram: 'purple',
      none: 'default',
    };
    return map[type] || 'default';
  };

  const columns = [
    {
      title: '排序',
      dataIndex: 'sort_order',
      key: 'sort_order',
      width: 120,
      render: (_: any, __: HomeBanner, index: number) => (
        <Space>
          <Button
            type="text"
            size="small"
            icon={<ArrowUpOutlined />}
            disabled={index === 0}
            onClick={() => handleMove(index, 'up')}
          />
          <Button
            type="text"
            size="small"
            icon={<ArrowDownOutlined />}
            disabled={index === banners.length - 1}
            onClick={() => handleMove(index, 'down')}
          />
        </Space>
      ),
    },
    {
      title: '预览图',
      dataIndex: 'image_url',
      key: 'image_url',
      width: 160,
      render: (val: string) =>
        val ? <Image src={resolveAssetUrl(val)} width={120} height={60} style={{ objectFit: 'cover', borderRadius: 4 }} /> : '-',
    },
    {
      title: '跳转类型',
      dataIndex: 'link_type',
      key: 'link_type',
      width: 120,
      render: (val: string) => <Tag color={linkTypeColor(val)}>{linkTypeLabel(val)}</Tag>,
    },
    {
      title: '跳转地址',
      dataIndex: 'link_url',
      key: 'link_url',
      ellipsis: true,
      render: (val: string) => val || '-',
    },
    {
      title: '显示状态',
      dataIndex: 'is_visible',
      key: 'is_visible',
      width: 100,
      render: (val: boolean, record: HomeBanner) => (
        <Switch checked={val} onChange={(checked) => handleToggleVisible(record, checked)} />
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 140,
      render: (_: any, record: HomeBanner) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
          </Button>
          <Popconfirm title="确定删除此Banner？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const currentImageUrl = Form.useWatch('image_url', form);

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>首页Banner管理</Title>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增Banner
        </Button>
      </div>
      <Table
        columns={columns}
        dataSource={banners}
        rowKey="id"
        loading={loading}
        pagination={false}
        scroll={{ x: 800 }}
      />
      <Modal
        title={editingBanner ? '编辑Banner' : '新增Banner'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" initialValues={{ is_visible: true, sort_order: 0, link_type: 'none' }}>
          <Form.Item label="Banner图片" name="image_url" rules={[{ required: true, message: '请上传Banner图片' }]}>
            <Input
              placeholder="请上传Banner图片"
              readOnly
              addonAfter={
                <Upload
                  showUploadList={false}
                  beforeUpload={(file) => {
                    handleUploadImage(file);
                    return false;
                  }}
                  accept="image/*"
                >
                  <Button type="link" size="small" icon={<UploadOutlined />} loading={uploading}>
                    上传
                  </Button>
                </Upload>
              }
            />
          </Form.Item>
          {currentImageUrl && (
            <div style={{ marginBottom: 16 }}>
              <Image src={resolveAssetUrl(currentImageUrl)} width={200} style={{ borderRadius: 4 }} />
            </div>
          )}
          <Form.Item label="跳转类型" name="link_type" rules={[{ required: true, message: '请选择跳转类型' }]}>
            <Select
              onChange={(val) => setLinkType(val)}
              options={[
                { label: '无跳转', value: 'none' },
                { label: '内部页面', value: 'internal' },
                { label: '外部链接', value: 'external' },
                { label: '小程序', value: 'miniprogram' },
              ]}
            />
          </Form.Item>
          {linkType !== 'none' && (
            <Form.Item label="跳转地址" name="link_url" rules={[{ required: true, message: '请输入跳转地址' }]}>
              <Input placeholder={linkType === 'external' ? '请输入完整URL' : '请输入页面路径'} />
            </Form.Item>
          )}
          {linkType === 'miniprogram' && (
            <Form.Item label="小程序AppID" name="miniprogram_appid" rules={[{ required: true, message: '请输入小程序AppID' }]}>
              <Input placeholder="请输入小程序AppID" />
            </Form.Item>
          )}
          <Form.Item label="排序值" name="sort_order">
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="是否显示" name="is_visible" valuePropName="checked">
            <Switch checkedChildren="显示" unCheckedChildren="隐藏" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
