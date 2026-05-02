'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, message,
  Typography, Tag, Popconfirm, Row, Col, Divider, Radio,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

interface CardItemRef {
  product_id: number;
  product_name?: string;
  product_image?: string;
}

interface CardDefinition {
  id: number;
  name: string;
  cover_image?: string | null;
  description?: string | null;
  card_type: string; // 'times' | 'period'
  scope_type: string; // 'platform' | 'merchant'
  owner_merchant_id?: number | null;
  owner_merchant_name?: string | null;
  price: number;
  original_price?: number | null;
  total_times?: number | null;
  valid_days: number;
  frequency_limit?: { scope: 'day' | 'week'; times: number } | null;
  store_scope?: { type: 'all' | 'list'; store_ids?: number[] } | null;
  stock?: number | null;
  per_user_limit?: number | null;
  renew_strategy: string; // 'add_on' | 'new_card'
  status: string; // 'draft' | 'active' | 'inactive'
  sales_count: number;
  sort_order: number;
  items: CardItemRef[];
  created_at: string;
  updated_at: string;
}

interface ProductOption {
  label: string;
  value: number;
}

const CARD_TYPE_LABEL: Record<string, string> = {
  times: '次卡',
  period: '时卡',
};

const SCOPE_TYPE_LABEL: Record<string, string> = {
  platform: '平台通用',
  merchant: '商家专属',
};

const STATUS_TAG: Record<string, { color: string; text: string }> = {
  draft: { color: 'default', text: '草稿' },
  active: { color: 'green', text: '已上架' },
  inactive: { color: 'orange', text: '已下架' },
};

export default function CardsAdminPage() {
  const [list, setList] = useState<CardDefinition[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);

  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<CardDefinition | null>(null);
  const [form] = Form.useForm();
  const [productOptions, setProductOptions] = useState<ProductOption[]>([]);

  const fetchList = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = { page, page_size: pageSize };
      if (keyword) params.keyword = keyword;
      if (statusFilter) params.status = statusFilter;
      const data = await get<{ total: number; items: CardDefinition[] }>(
        '/api/admin/cards',
        params,
      );
      setList(data.items || []);
      setTotal(data.total || 0);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载卡列表失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, keyword, statusFilter]);

  useEffect(() => {
    fetchList();
  }, [fetchList]);

  // 加载商品选项（用于卡内项目绑定）
  useEffect(() => {
    (async () => {
      try {
        const data = await get<any>('/api/admin/products', { page: 1, page_size: 200 });
        const items = data?.items || data || [];
        setProductOptions(
          (items as any[]).map((p) => ({ label: `${p.name} (¥${p.sale_price})`, value: p.id })),
        );
      } catch {
        setProductOptions([]);
      }
    })();
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      card_type: 'times',
      scope_type: 'platform',
      renew_strategy: 'add_on',
      store_scope_type: 'all',
      valid_days: 365,
      price: 0,
      total_times: 10,
    });
    setModalOpen(true);
  };

  const openEdit = (record: CardDefinition) => {
    setEditing(record);
    form.resetFields();
    form.setFieldsValue({
      name: record.name,
      cover_image: record.cover_image || '',
      description: record.description || '',
      card_type: record.card_type,
      scope_type: record.scope_type,
      owner_merchant_id: record.owner_merchant_id ?? undefined,
      price: record.price,
      original_price: record.original_price ?? undefined,
      total_times: record.total_times ?? undefined,
      valid_days: record.valid_days,
      frequency_scope: record.frequency_limit?.scope,
      frequency_times: record.frequency_limit?.times,
      store_scope_type: record.store_scope?.type || 'all',
      stock: record.stock ?? undefined,
      per_user_limit: record.per_user_limit ?? undefined,
      renew_strategy: record.renew_strategy,
      item_product_ids: record.items.map((i) => i.product_id),
    });
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const payload: any = {
        name: values.name,
        cover_image: values.cover_image || null,
        description: values.description || null,
        card_type: values.card_type,
        scope_type: values.scope_type,
        owner_merchant_id: values.scope_type === 'merchant' ? values.owner_merchant_id : null,
        price: Number(values.price),
        original_price: values.original_price ? Number(values.original_price) : null,
        total_times: values.card_type === 'times' ? Number(values.total_times) : null,
        valid_days: Number(values.valid_days),
        frequency_limit:
          values.card_type === 'period' && values.frequency_scope && values.frequency_times
            ? { scope: values.frequency_scope, times: Number(values.frequency_times) }
            : null,
        store_scope: { type: values.store_scope_type || 'all' },
        stock: values.stock ?? null,
        per_user_limit: values.per_user_limit ?? null,
        renew_strategy: values.renew_strategy,
        item_product_ids: values.item_product_ids || [],
      };
      if (editing) {
        await put(`/api/admin/cards/${editing.id}`, payload);
        message.success('卡已更新');
      } else {
        await post('/api/admin/cards', payload);
        message.success('卡已创建（草稿）');
      }
      setModalOpen(false);
      fetchList();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || '保存失败');
    }
  };

  const handleStatusChange = async (record: CardDefinition, target: 'active' | 'inactive') => {
    try {
      await put(`/api/admin/cards/${record.id}/status`, { status: target });
      message.success(target === 'active' ? '已上架' : '已下架');
      fetchList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (record: CardDefinition) => {
    try {
      await del(`/api/admin/cards/${record.id}`);
      message.success('已删除');
      fetchList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    {
      title: '卡名',
      dataIndex: 'name',
      render: (v: string, r: CardDefinition) => (
        <Space direction="vertical" size={0}>
          <span style={{ fontWeight: 500 }}>{v}</span>
          {r.description ? (
            <span style={{ color: '#999', fontSize: 12 }}>{r.description.slice(0, 40)}</span>
          ) : null}
        </Space>
      ),
    },
    {
      title: '类型',
      dataIndex: 'card_type',
      width: 80,
      render: (v: string) => (
        <Tag color={v === 'times' ? 'blue' : 'purple'}>{CARD_TYPE_LABEL[v] || v}</Tag>
      ),
    },
    {
      title: '范围',
      dataIndex: 'scope_type',
      width: 100,
      render: (v: string, r: CardDefinition) => (
        <Space direction="vertical" size={0}>
          <Tag color={v === 'platform' ? 'gold' : 'cyan'}>{SCOPE_TYPE_LABEL[v] || v}</Tag>
          {v === 'merchant' && r.owner_merchant_name ? (
            <span style={{ fontSize: 12, color: '#999' }}>{r.owner_merchant_name}</span>
          ) : null}
        </Space>
      ),
    },
    {
      title: '价格',
      dataIndex: 'price',
      width: 100,
      render: (v: number, r: CardDefinition) => (
        <Space direction="vertical" size={0}>
          <span style={{ color: '#f5222d', fontWeight: 600 }}>¥{Number(v).toFixed(2)}</span>
          {r.original_price ? (
            <span style={{ color: '#999', textDecoration: 'line-through', fontSize: 12 }}>
              ¥{Number(r.original_price).toFixed(2)}
            </span>
          ) : null}
        </Space>
      ),
    },
    {
      title: '次数 / 有效期',
      width: 120,
      render: (_: any, r: CardDefinition) => (
        <Space direction="vertical" size={0}>
          {r.card_type === 'times' ? <span>{r.total_times} 次</span> : <span>—</span>}
          <span style={{ color: '#999', fontSize: 12 }}>有效 {r.valid_days} 天</span>
        </Space>
      ),
    },
    {
      title: '项目数',
      width: 80,
      render: (_: any, r: CardDefinition) => <span>{r.items?.length || 0}</span>,
    },
    {
      title: '已售 / 库存',
      width: 100,
      render: (_: any, r: CardDefinition) => (
        <Space direction="vertical" size={0}>
          <span>已售 {r.sales_count || 0}</span>
          <span style={{ color: '#999', fontSize: 12 }}>
            库存 {r.stock === null || r.stock === undefined ? '不限' : r.stock}
          </span>
        </Space>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 90,
      render: (v: string) => {
        const t = STATUS_TAG[v] || { color: 'default', text: v };
        return <Tag color={t.color}>{t.text}</Tag>;
      },
    },
    {
      title: '操作',
      width: 220,
      render: (_: any, r: CardDefinition) => (
        <Space size={4}>
          <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>
            编辑
          </Button>
          {r.status === 'active' ? (
            <Button size="small" onClick={() => handleStatusChange(r, 'inactive')}>下架</Button>
          ) : (
            <Button size="small" type="primary" onClick={() => handleStatusChange(r, 'active')}>
              上架
            </Button>
          )}
          {r.status === 'draft' ? (
            <Popconfirm title="确认删除该草稿卡?" onConfirm={() => handleDelete(r)}>
              <Button size="small" danger icon={<DeleteOutlined />}>删除</Button>
            </Popconfirm>
          ) : null}
        </Space>
      ),
    },
  ];

  const cardType = Form.useWatch('card_type', form);
  const scopeType = Form.useWatch('scope_type', form);

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginBottom: 12 }}>卡管理（PRD v1.1 第 1 期）</Title>
      <Space style={{ marginBottom: 12 }} wrap>
        <Input.Search
          placeholder="按卡名搜索"
          allowClear
          style={{ width: 240 }}
          onSearch={(v) => { setPage(1); setKeyword(v); }}
        />
        <Select
          placeholder="状态"
          allowClear
          style={{ width: 140 }}
          options={[
            { label: '草稿', value: 'draft' },
            { label: '已上架', value: 'active' },
            { label: '已下架', value: 'inactive' },
          ]}
          value={statusFilter}
          onChange={(v) => { setPage(1); setStatusFilter(v); }}
        />
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建卡
        </Button>
      </Space>

      <Table
        rowKey="id"
        size="middle"
        loading={loading}
        dataSource={list}
        columns={columns as any}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (p, ps) => { setPage(p); setPageSize(ps); },
        }}
      />

      <Modal
        open={modalOpen}
        onCancel={() => setModalOpen(false)}
        onOk={handleSubmit}
        title={editing ? `编辑卡 #${editing.id}` : '新建卡'}
        width={760}
        okText="保存"
        cancelText="取消"
        destroyOnClose
        maskClosable={false}
      >
        <Form form={form} layout="vertical">
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="name" label="卡名" rules={[{ required: true, message: '请输入卡名' }]}>
                <Input maxLength={200} placeholder="例如：美业 10 次卡" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="cover_image" label="封面图 URL">
                <Input placeholder="https://..." />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="卡介绍">
            <TextArea rows={2} maxLength={500} placeholder="可选，用于详情页展示" />
          </Form.Item>

          <Divider style={{ margin: '8px 0' }} orientation="left">基本属性</Divider>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="card_type" label="卡形态" rules={[{ required: true }]}>
                <Radio.Group>
                  <Radio value="times">次卡</Radio>
                  <Radio value="period">时卡</Radio>
                </Radio.Group>
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="scope_type" label="归属范围" rules={[{ required: true }]}>
                <Radio.Group>
                  <Radio value="platform">平台通用</Radio>
                  <Radio value="merchant">商家专属</Radio>
                </Radio.Group>
              </Form.Item>
            </Col>
            <Col span={8}>
              {scopeType === 'merchant' ? (
                <Form.Item
                  name="owner_merchant_id"
                  label="所属商家档案 ID"
                  rules={[{ required: true, message: '请输入商家档案 ID' }]}
                >
                  <InputNumber min={1} style={{ width: '100%' }} placeholder="merchant_profile.id" />
                </Form.Item>
              ) : null}
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="price" label="售价(元)" rules={[{ required: true }]}>
                <InputNumber min={0} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="original_price" label="划线价(元)">
                <InputNumber min={0} step={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="valid_days" label="有效期(自购买起 N 天)" rules={[{ required: true }]}>
                <InputNumber min={1} max={3650} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          {cardType === 'times' ? (
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item
                  name="total_times"
                  label="总次数"
                  rules={[{ required: true, message: '次卡必填总次数' }]}
                >
                  <InputNumber min={1} style={{ width: '100%' }} />
                </Form.Item>
              </Col>
            </Row>
          ) : (
            <Row gutter={16}>
              <Col span={8}>
                <Form.Item name="frequency_scope" label="频次单位">
                  <Select allowClear options={[
                    { label: '每天', value: 'day' },
                    { label: '每周', value: 'week' },
                  ]} />
                </Form.Item>
              </Col>
              <Col span={8}>
                <Form.Item name="frequency_times" label="频次次数">
                  <InputNumber min={1} style={{ width: '100%' }} placeholder="例如：每天 1 次" />
                </Form.Item>
              </Col>
            </Row>
          )}

          <Row gutter={16}>
            <Col span={8}>
              <Form.Item name="stock" label="总库存(留空=无限)">
                <InputNumber min={0} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="per_user_limit" label="同款限购(留空=不限)">
                <InputNumber min={1} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={8}>
              <Form.Item name="renew_strategy" label="续卡策略" rules={[{ required: true }]}>
                <Select options={[
                  { label: '叠加在原卡（推荐次卡）', value: 'add_on' },
                  { label: '新发独立卡（推荐月卡/年卡）', value: 'new_card' },
                ]} />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="store_scope_type" label="可用门店" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="all">全门店通用</Radio>
              <Radio value="list" disabled>
                指定门店列表（第 2 期支持）
              </Radio>
            </Radio.Group>
          </Form.Item>

          <Divider style={{ margin: '8px 0' }} orientation="left">卡内项目（核销时可选用）</Divider>
          <Form.Item
            name="item_product_ids"
            label="绑定商品（必须先绑定后才能上架）"
          >
            <Select
              mode="multiple"
              placeholder="选择卡内可用项目（普通商品）"
              optionFilterProp="label"
              options={productOptions}
              maxTagCount={10}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
