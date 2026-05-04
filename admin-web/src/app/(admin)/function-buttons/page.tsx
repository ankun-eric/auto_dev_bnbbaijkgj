'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Tag, Switch, Modal, Form, Input, Select,
  InputNumber, Typography, message, Image,
} from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';

const { Title } = Typography;
const { TextArea } = Input;

const BUTTON_TYPE_OPTIONS = [
  { value: 'digital_human_call', label: '数字人通话' },
  { value: 'photo_upload', label: '拍照上传' },
  { value: 'file_upload', label: '文件上传' },
  { value: 'ai_dialog_trigger', label: 'AI对话触发' },
  { value: 'external_link', label: '外部链接' },
  { value: 'drug_identify', label: '拍照识药' },
];

const BUTTON_TYPE_MAP: Record<string, { label: string; color: string }> = {
  digital_human_call: { label: '数字人通话', color: 'blue' },
  photo_upload: { label: '拍照上传', color: 'green' },
  file_upload: { label: '文件上传', color: 'orange' },
  ai_dialog_trigger: { label: 'AI对话触发', color: 'purple' },
  external_link: { label: '外部链接', color: 'default' },
  drug_identify: { label: '拍照识药', color: 'cyan' },
};

const AI_REPLY_MODE_OPTIONS = [
  { value: 'complete_analysis', label: '完整分析（含药物相互作用）' },
  { value: 'basic_advice', label: '仅用药建议' },
  { value: 'ai_auto', label: 'AI 自动判断' },
];

interface FunctionButton {
  id: number;
  name: string;
  icon_url: string;
  button_type: string;
  sort_weight: number;
  is_enabled: boolean;
  params: any;
  created_at?: string;
  updated_at?: string;
}

export default function FunctionButtonsPage() {
  const [items, setItems] = useState<FunctionButton[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalOpen, setModalOpen] = useState(false);
  const [editingItem, setEditingItem] = useState<FunctionButton | null>(null);
  const [saving, setSaving] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [form] = Form.useForm();
  const watchedButtonType = Form.useWatch('button_type', form);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const res = await get<any>('/api/admin/function-buttons', { page, page_size: pageSize });
      if (Array.isArray(res)) {
        setItems(res);
        setTotal(res.length);
      } else {
        setItems(res.items || []);
        setTotal(res.total || 0);
      }
    } catch {
      message.error('获取功能按钮列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleOpenModal = (record?: FunctionButton) => {
    setEditingItem(record || null);
    form.resetFields();
    if (record) {
      const parsedParams = typeof record.params === 'string'
        ? (() => { try { return JSON.parse(record.params); } catch { return null; } })()
        : record.params;

      const formValues: Record<string, any> = {
        name: record.name,
        icon_url: record.icon_url,
        button_type: record.button_type,
        sort_weight: record.sort_weight,
        is_enabled: record.is_enabled,
        params: record.params
          ? (typeof record.params === 'string' ? record.params : JSON.stringify(record.params, null, 2))
          : '',
      };

      if (record.button_type === 'drug_identify' && parsedParams) {
        formValues.ai_reply_mode = parsedParams.ai_reply_mode || 'ai_auto';
        formValues.photo_tip_text = parsedParams.photo_tip_text || '请确保药品名称、品牌、规格完整，拍摄清晰';
        formValues.max_photo_count = parsedParams.max_photo_count ?? 5;
      }

      form.setFieldsValue(formValues);
    } else {
      form.setFieldsValue({
        is_enabled: true,
        sort_weight: 0,
        ai_reply_mode: 'ai_auto',
        photo_tip_text: '请确保药品名称、品牌、规格完整，拍摄清晰',
        max_photo_count: 5,
      });
    }
    setModalOpen(true);
  };

  const handleSave = async () => {
    try {
      const values = await form.validateFields();
      setSaving(true);

      let parsedParams = values.params;
      if (parsedParams && typeof parsedParams === 'string') {
        try {
          parsedParams = JSON.parse(parsedParams);
        } catch {
          parsedParams = values.params;
        }
      }

      let finalParams = parsedParams || null;
      if (values.button_type === 'drug_identify') {
        const base = (typeof finalParams === 'object' && finalParams) ? finalParams : {};
        finalParams = {
          ...base,
          ai_reply_mode: values.ai_reply_mode || 'ai_auto',
          photo_tip_text: values.photo_tip_text || '请确保药品名称、品牌、规格完整，拍摄清晰',
          max_photo_count: values.max_photo_count ?? 5,
        };
      }

      const payload = {
        name: values.name,
        icon_url: values.icon_url,
        button_type: values.button_type,
        sort_weight: values.sort_weight ?? 0,
        is_enabled: values.is_enabled,
        params: finalParams,
      };

      if (editingItem) {
        await put(`/api/admin/function-buttons/${editingItem.id}`, payload);
        message.success('功能按钮更新成功');
      } else {
        await post('/api/admin/function-buttons', payload);
        message.success('功能按钮创建成功');
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

  const handleDelete = (record: FunctionButton) => {
    Modal.confirm({
      title: '确认删除',
      content: `确定要删除功能按钮「${record.name}」吗？`,
      okText: '确定',
      cancelText: '取消',
      okButtonProps: { danger: true },
      onOk: async () => {
        try {
          await del(`/api/admin/function-buttons/${record.id}`);
          message.success('删除成功');
          fetchData();
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '删除失败');
        }
      },
    });
  };

  const handleToggleEnabled = async (record: FunctionButton, checked: boolean) => {
    try {
      await put(`/api/admin/function-buttons/${record.id}`, { is_enabled: checked });
      message.success('状态更新成功');
      fetchData();
    } catch {
      message.error('状态更新失败');
    }
  };

  const columns = [
    {
      title: '排序权重',
      dataIndex: 'sort_weight',
      key: 'sort_weight',
      width: 100,
      sorter: (a: FunctionButton, b: FunctionButton) => a.sort_weight - b.sort_weight,
    },
    {
      title: '图标',
      dataIndex: 'icon_url',
      key: 'icon_url',
      width: 80,
      render: (val: string) =>
        val ? <Image src={resolveAssetUrl(val)} width={36} height={36} style={{ objectFit: 'contain' }} fallback="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mN8/+F/PQAJpAN42kRfMwAAAABJRU5ErkJggg==" /> : '-',
    },
    {
      title: '按钮名称',
      dataIndex: 'name',
      key: 'name',
      width: 140,
    },
    {
      title: '按钮类型',
      dataIndex: 'button_type',
      key: 'button_type',
      width: 130,
      render: (val: string) => {
        const info = BUTTON_TYPE_MAP[val];
        return info ? <Tag color={info.color}>{info.label}</Tag> : <Tag>{val}</Tag>;
      },
    },
    {
      title: '启用状态',
      dataIndex: 'is_enabled',
      key: 'is_enabled',
      width: 100,
      render: (val: boolean, record: FunctionButton) => (
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
      width: 140,
      render: (_: any, record: FunctionButton) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleOpenModal(record)}>
            编辑
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
      <Title level={4} style={{ marginBottom: 24 }}>功能按钮管理</Title>
      <div style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => handleOpenModal()}>
          新增按钮
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
        title={editingItem ? '编辑功能按钮' : '新增功能按钮'}
        open={modalOpen}
        onOk={handleSave}
        onCancel={() => setModalOpen(false)}
        confirmLoading={saving}
        destroyOnClose
        width={560}
      >
        <Form form={form} layout="vertical" initialValues={{ is_enabled: true, sort_weight: 0 }}>
          <Form.Item
            label="按钮名称"
            name="name"
            rules={[{ required: true, message: '请输入按钮名称' }]}
          >
            <Input placeholder="请输入按钮名称" maxLength={20} />
          </Form.Item>
          <Form.Item
            label="按钮图标"
            name="icon_url"
            rules={[{ required: true, message: '请输入图标URL' }]}
          >
            <Input placeholder="请输入图标URL" />
          </Form.Item>
          <Form.Item
            label="按钮类型"
            name="button_type"
            rules={[{ required: true, message: '请选择按钮类型' }]}
          >
            <Select placeholder="请选择按钮类型" options={BUTTON_TYPE_OPTIONS} />
          </Form.Item>
          {watchedButtonType === 'drug_identify' && (
            <>
              <Form.Item label="AI 回复模式" name="ai_reply_mode" rules={[{ required: true, message: '请选择AI回复模式' }]}>
                <Select placeholder="请选择AI回复模式" options={AI_REPLY_MODE_OPTIONS} />
              </Form.Item>
              <Form.Item label="拍照提示语" name="photo_tip_text">
                <Input placeholder="请确保药品名称、品牌、规格完整，拍摄清晰" />
              </Form.Item>
              <Form.Item label="最大图片数" name="max_photo_count">
                <InputNumber min={1} max={10} style={{ width: '100%' }} placeholder="默认5张" />
              </Form.Item>
            </>
          )}
          <Form.Item label="排序权重" name="sort_weight">
            <InputNumber min={0} max={9999} style={{ width: '100%' }} placeholder="数值越大越靠前" />
          </Form.Item>
          <Form.Item label="启用状态" name="is_enabled" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
          <Form.Item label="关联参数" name="params">
            <TextArea rows={4} placeholder='请输入JSON格式参数，例如: {"url": "https://..."}' />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
