'use client';

/**
 * [PRD-TIZHI-OPTIM-V1 2026-06-01] 体质测评运营内容配置
 *
 * 运营在此维护「专属膳食套餐 / 门店服务」内容卡，按体质类型智能匹配，
 * 展示在体质测评结果详情页。未配置或全部停用时，结果页对应整块隐藏（无占位假文案）。
 */
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Table, Tag, Space, Typography, message, Button, Modal, Form, Switch,
  InputNumber, Input, Select, Popconfirm,
} from 'antd';
import { PlusOutlined, ReloadOutlined, EditOutlined, DeleteOutlined } from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Text } = Typography;

const BRAND = '#0EA5E9';

interface ContentConfig {
  id: number;
  constitution_type: string;
  section: 'meal' | 'store';
  title: string;
  subtitle?: string | null;
  image?: string | null;
  tag?: string | null;
  tag_color?: string | null;
  price?: number | null;
  original_price?: number | null;
  link_type: string;
  link_value?: string | null;
  button_text?: string | null;
  sort_order: number;
  enabled: boolean;
}

interface Meta {
  constitution_types: string[];
  sections: { value: string; label: string }[];
  link_types: { value: string; label: string }[];
}

const SECTION_LABEL: Record<string, string> = { meal: '专属膳食套餐', store: '门店服务' };

export default function ConstitutionContentPage() {
  const [items, setItems] = useState<ContentConfig[]>([]);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(false);
  const [filterType, setFilterType] = useState<string | undefined>(undefined);
  const [filterSection, setFilterSection] = useState<string | undefined>(undefined);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<ContentConfig | null>(null);
  const [form] = Form.useForm();

  const fetchMeta = useCallback(async () => {
    try {
      const res: any = await get('/api/admin/constitution/meta');
      setMeta(res?.data || res);
    } catch {
      /* noop */
    }
  }, []);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (filterType) params.constitution_type = filterType;
      if (filterSection) params.section = filterSection;
      const res: any = await get('/api/admin/constitution/content-configs', { params });
      const data = res?.data || res;
      setItems(Array.isArray(data?.items) ? data.items : []);
    } catch (e) {
      message.error('加载配置失败');
    } finally {
      setLoading(false);
    }
  }, [filterType, filterSection]);

  useEffect(() => { fetchMeta(); }, [fetchMeta]);
  useEffect(() => { fetchList(); }, [fetchList]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      constitution_type: filterType || (meta?.constitution_types?.[0] ?? '平和质'),
      section: filterSection || 'meal',
      link_type: 'none',
      tag_color: BRAND,
      sort_order: 0,
      enabled: true,
    });
    setModalOpen(true);
  };

  const openEdit = (row: ContentConfig) => {
    setEditing(row);
    form.setFieldsValue({ ...row });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    try {
      if (editing) {
        await put(`/api/admin/constitution/content-configs/${editing.id}`, values);
        message.success('已更新');
      } else {
        await post('/api/admin/constitution/content-configs', values);
        message.success('已新增');
      }
      setModalOpen(false);
      fetchList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/constitution/content-configs/${id}`);
      message.success('已删除');
      fetchList();
    } catch {
      message.error('删除失败');
    }
  };

  const toggleEnabled = async (row: ContentConfig, enabled: boolean) => {
    try {
      await put(`/api/admin/constitution/content-configs/${row.id}`, { ...row, enabled });
      fetchList();
    } catch {
      message.error('操作失败');
    }
  };

  const columns = useMemo(() => [
    { title: '体质', dataIndex: 'constitution_type', width: 90,
      render: (t: string) => <Tag color={BRAND}>{t}</Tag> },
    { title: '板块', dataIndex: 'section', width: 110,
      render: (s: string) => <Tag>{SECTION_LABEL[s] || s}</Tag> },
    { title: '标题', dataIndex: 'title', width: 160 },
    { title: '描述', dataIndex: 'subtitle', ellipsis: true,
      render: (v: string) => <Text type="secondary">{v || '—'}</Text> },
    { title: '推荐理由', dataIndex: 'tag', width: 110,
      render: (v: string, r: ContentConfig) => v ? <Tag color={r.tag_color || BRAND}>{v}</Tag> : '—' },
    { title: '跳转', dataIndex: 'link_type', width: 90,
      render: (v: string) => meta?.link_types?.find((l) => l.value === v)?.label || v },
    { title: '排序', dataIndex: 'sort_order', width: 70 },
    { title: '启用', dataIndex: 'enabled', width: 80,
      render: (v: boolean, r: ContentConfig) => (
        <Switch checked={v} size="small" onChange={(c) => toggleEnabled(r, c)} />
      ) },
    { title: '操作', width: 130, render: (_: any, r: ContentConfig) => (
      <Space>
        <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)} />
        <Popconfirm title="确认删除该配置？" onConfirm={() => handleDelete(r.id)}>
          <Button size="small" danger icon={<DeleteOutlined />} />
        </Popconfirm>
      </Space>
    ) },
  ], [meta]);

  return (
    <div style={{ padding: 24 }}>
      <div style={{ marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>体质测评运营内容配置</Typography.Title>
        <Text type="secondary">
          维护各体质的「专属膳食套餐 / 门店服务」内容卡，按体质智能匹配展示；停用或不配置则结果页对应整块隐藏。
        </Text>
      </div>

      <Space style={{ marginBottom: 16 }} wrap>
        <Select
          allowClear placeholder="按体质筛选" style={{ width: 140 }}
          value={filterType} onChange={setFilterType}
          options={(meta?.constitution_types || []).map((t) => ({ value: t, label: t }))}
        />
        <Select
          allowClear placeholder="按板块筛选" style={{ width: 160 }}
          value={filterSection} onChange={setFilterSection}
          options={(meta?.sections || []).map((s) => ({ value: s.value, label: s.label }))}
        />
        <Button icon={<ReloadOutlined />} onClick={fetchList}>刷新</Button>
        <Button type="primary" icon={<PlusOutlined />} style={{ background: BRAND }} onClick={openCreate}>
          新增内容卡
        </Button>
      </Space>

      <Table
        rowKey="id"
        loading={loading}
        dataSource={items}
        columns={columns as any}
        pagination={{ pageSize: 20 }}
        size="middle"
      />

      <Modal
        title={editing ? '编辑内容卡' : '新增内容卡'}
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        okText="保存"
        width={560}
      >
        <Form form={form} layout="vertical">
          <Space style={{ display: 'flex' }} size={12}>
            <Form.Item name="constitution_type" label="体质类型" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={(meta?.constitution_types || []).map((t) => ({ value: t, label: t }))} />
            </Form.Item>
            <Form.Item name="section" label="板块" rules={[{ required: true }]} style={{ flex: 1 }}>
              <Select options={(meta?.sections || []).map((s) => ({ value: s.value, label: s.label }))} />
            </Form.Item>
          </Space>
          <Form.Item name="title" label="标题" rules={[{ required: true, message: '请输入标题' }]}>
            <Input placeholder="如：补气养元餐 / 预约艾灸调理" maxLength={120} />
          </Form.Item>
          <Form.Item name="subtitle" label="描述">
            <Input.TextArea rows={2} placeholder="一句话描述" maxLength={255} />
          </Form.Item>
          <Space style={{ display: 'flex' }} size={12}>
            <Form.Item name="tag" label="推荐理由标签" style={{ flex: 1 }}>
              <Input placeholder="如：补气固本" maxLength={60} />
            </Form.Item>
            <Form.Item name="tag_color" label="标签颜色" style={{ width: 130 }}>
              <Input placeholder="#0EA5E9" />
            </Form.Item>
          </Space>
          <Form.Item name="image" label="封面图 URL">
            <Input placeholder="可选，图片地址" maxLength={500} />
          </Form.Item>
          <Space style={{ display: 'flex' }} size={12}>
            <Form.Item name="price" label="价格" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} min={0} placeholder="可选" />
            </Form.Item>
            <Form.Item name="original_price" label="原价" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} min={0} placeholder="可选" />
            </Form.Item>
          </Space>
          <Space style={{ display: 'flex' }} size={12}>
            <Form.Item name="link_type" label="跳转类型" style={{ flex: 1 }}>
              <Select options={(meta?.link_types || []).map((l) => ({ value: l.value, label: l.label }))} />
            </Form.Item>
            <Form.Item name="link_value" label="跳转值（SKU ID / 项目 / URL）" style={{ flex: 1 }}>
              <Input placeholder="如商品ID或moxibustion" />
            </Form.Item>
          </Space>
          <Space style={{ display: 'flex' }} size={12}>
            <Form.Item name="button_text" label="按钮文案" style={{ flex: 1 }}>
              <Input placeholder="如：立即下单 / 预约" maxLength={40} />
            </Form.Item>
            <Form.Item name="sort_order" label="排序" style={{ width: 120 }}>
              <InputNumber style={{ width: '100%' }} min={0} />
            </Form.Item>
            <Form.Item name="enabled" label="启用" valuePropName="checked" style={{ width: 80 }}>
              <Switch />
            </Form.Item>
          </Space>
        </Form>
      </Modal>
    </div>
  );
}
