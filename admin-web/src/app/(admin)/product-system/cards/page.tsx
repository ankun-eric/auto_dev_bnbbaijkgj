'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, message,
  Typography, Tag, Popconfirm, Row, Col, Divider, Radio, Switch, Checkbox, Tooltip,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import CardFace, {
  FACE_STYLES, BG_OPTIONS, SHOW_FLAGS,
  toggleShowFlag, isShowFlagOn, DEFAULT_FACE_SHOW_FLAGS,
} from '@/components/card/CardFacePreview';

const { Title, Text } = Typography;
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
  card_type: string;
  scope_type: string;
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
  renew_strategy: string;
  status: string;
  sales_count: number;
  sort_order: number;
  items: CardItemRef[];
  face_style?: string;
  face_bg_code?: string;
  face_show_flags?: number;
  face_layout?: string;
  created_at: string;
  updated_at: string;
}

interface ProductOption {
  label: string;
  value: number;
  name?: string;
}

interface MerchantOption {
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
  const [merchantOptions, setMerchantOptions] = useState<MerchantOption[]>([]);
  const [merchantSearching, setMerchantSearching] = useState(false);

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
          (items as any[]).map((p) => ({
            label: `${p.name} (¥${p.sale_price})`,
            value: p.id,
            name: p.name,
          })),
        );
      } catch {
        setProductOptions([]);
      }
    })();
  }, []);

  const searchMerchants = useCallback(async (kw: string) => {
    setMerchantSearching(true);
    try {
      const data = await get<any>('/api/admin/cards/_lookup/merchants', {
        keyword: kw || undefined,
        limit: 30,
      });
      const items = data?.items || [];
      setMerchantOptions(
        (items as any[]).map((m) => ({
          label: m.label || `档案#${m.id}`,
          value: m.id,
        })),
      );
    } catch {
      setMerchantOptions([]);
    } finally {
      setMerchantSearching(false);
    }
  }, []);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      card_type: 'times',
      scope_type: 'platform',
      renew_strategy: 'add_on',
      store_all: true,
      valid_days: 365,
      price: 0,
      total_times: 10,
      face_style: 'ST1',
      face_bg_code: 'BG1',
      face_show_flags: DEFAULT_FACE_SHOW_FLAGS,
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
      frequency_text: record.frequency_limit
        ? `每${record.frequency_limit.scope === 'day' ? '天' : '周'} ${record.frequency_limit.times} 次`
        : '',
      store_all: !record.store_scope || record.store_scope.type === 'all',
      stock: record.stock ?? undefined,
      per_user_limit: record.per_user_limit ?? undefined,
      renew_strategy: record.renew_strategy,
      item_product_ids: record.items.map((i) => i.product_id),
      face_style: record.face_style || 'ST1',
      face_bg_code: record.face_bg_code || 'BG1',
      face_show_flags: record.face_show_flags ?? DEFAULT_FACE_SHOW_FLAGS,
    });
    if (record.scope_type === 'merchant' && record.owner_merchant_id) {
      setMerchantOptions([
        {
          label: record.owner_merchant_name
            ? `${record.owner_merchant_name} (#${record.owner_merchant_id})`
            : `商家#${record.owner_merchant_id}`,
          value: record.owner_merchant_id,
        },
      ]);
    }
    setModalOpen(true);
  };

  const parseFrequencyText = (txt?: string): { scope: 'day' | 'week'; times: number } | null => {
    if (!txt) return null;
    const m = txt.match(/(每?天|每?周|day|week)\s*([0-9]+)/i);
    if (!m) return null;
    const scope: 'day' | 'week' = /周|week/i.test(m[1]) ? 'week' : 'day';
    const times = parseInt(m[2], 10);
    if (!times || times <= 0) return null;
    return { scope, times };
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
        frequency_limit: values.card_type === 'period'
          ? parseFrequencyText(values.frequency_text)
          : null,
        store_scope: values.store_all === false
          ? { type: 'list', store_ids: [] }
          : { type: 'all' },
        stock: values.stock ?? null,
        per_user_limit: values.per_user_limit ?? null,
        renew_strategy: values.renew_strategy,
        item_product_ids: values.item_product_ids || [],
        face_style: values.face_style || 'ST1',
        face_bg_code: values.face_bg_code || 'BG1',
        face_show_flags: Number(values.face_show_flags ?? DEFAULT_FACE_SHOW_FLAGS),
        face_layout: 'ON_CARD',
      };
      if (values.original_price && values.price && Number(values.original_price) <= Number(values.price)) {
        message.error('划线价必须大于售价');
        return;
      }
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
      title: '卡面',
      dataIndex: 'face_bg_code',
      width: 110,
      render: (_: any, r: CardDefinition) => (
        <div style={{ width: 90 }}>
          <CardFace
            faceStyle={r.face_style || 'ST1'}
            faceBgCode={r.face_bg_code || 'BG1'}
            faceShowFlags={r.face_show_flags ?? DEFAULT_FACE_SHOW_FLAGS}
            cardName={r.name}
            price={r.price}
            originalPrice={r.original_price ?? null}
            validDays={r.valid_days}
            cardType={r.card_type}
            totalTimes={r.total_times ?? null}
            scopeType={r.scope_type}
            size="sm"
          />
        </div>
      ),
    },
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
      title: '项目',
      width: 80,
      render: (_: any, r: CardDefinition) => <span>{r.items?.length || 0} 个</span>,
    },
    {
      title: '已售 / 库存',
      width: 110,
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

  // 实时预览所需值
  const watchedAll = Form.useWatch([], form);
  const cardType = watchedAll?.card_type;
  const scopeType = watchedAll?.scope_type;
  const storeAll = watchedAll?.store_all !== false;
  const previewName = watchedAll?.name || '示例卡名';
  const previewItems = (watchedAll?.item_product_ids || [])
    .map((pid: number) => productOptions.find((p) => p.value === pid)?.name)
    .filter(Boolean) as string[];
  const previewItemsSummary = previewItems.length
    ? previewItems.slice(0, 3).join(' / ') + (previewItems.length > 3 ? '…' : '')
    : '请选择卡内项目';
  const faceStyle = watchedAll?.face_style || 'ST1';
  const faceBgCode = watchedAll?.face_bg_code || 'BG1';
  const faceShowFlags = watchedAll?.face_show_flags ?? DEFAULT_FACE_SHOW_FLAGS;

  return (
    <div style={{ padding: 16 }}>
      <Title level={4} style={{ marginBottom: 12 }}>卡管理（PRD v1.1）</Title>
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
        width={1080}
        okText="保存"
        cancelText="取消"
        destroyOnClose
        maskClosable={false}
      >
        <Row gutter={16}>
          {/* 左侧：表单区 */}
          <Col span={15}>
            <Form form={form} layout="vertical">
              <Divider style={{ margin: '0 0 12px' }} orientation="left">基础信息</Divider>

              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item
                    name="name"
                    label="卡名（F01）"
                    rules={[
                      { required: true, message: '请输入卡名' },
                      { max: 30, message: '最多 30 字符' },
                    ]}
                  >
                    <Input maxLength={30} showCount placeholder="例如：美业 10 次卡" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="cover_image" label="封面图 URL（可选）">
                    <Input placeholder="https://..." />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item name="description" label="卡介绍">
                <TextArea rows={2} maxLength={500} placeholder="可选，用于详情页展示" />
              </Form.Item>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name="card_type" label="卡形态（F02）" rules={[{ required: true }]}>
                    <Radio.Group>
                      <Radio value="times">次卡</Radio>
                      <Radio value="period">时卡</Radio>
                    </Radio.Group>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="scope_type" label="归属范围（F03）" rules={[{ required: true }]}>
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
                      label="商家档案 ID（F04）"
                      rules={[{ required: true, message: '请选择商家档案' }]}
                    >
                      <Select
                        showSearch
                        allowClear
                        placeholder="搜索商家档案"
                        options={merchantOptions}
                        loading={merchantSearching}
                        filterOption={false}
                        onSearch={(v) => searchMerchants(v)}
                        onFocus={() => {
                          if (merchantOptions.length === 0) searchMerchants('');
                        }}
                      />
                    </Form.Item>
                  ) : null}
                </Col>
              </Row>

              {cardType === 'times' ? (
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name="total_times"
                      label="总次数（F05）"
                      rules={[{ required: true, message: '次卡必填总次数' }]}
                    >
                      <InputNumber min={1} style={{ width: '100%' }} />
                    </Form.Item>
                  </Col>
                </Row>
              ) : (
                <Row gutter={16}>
                  <Col span={12}>
                    <Form.Item
                      name="frequency_text"
                      label="频次（F06）"
                      tooltip="例如：每周 3 次 / 每天 1 次"
                      rules={[{ required: true, message: '时卡必填频次' }]}
                    >
                      <Input placeholder="如：每周 3 次" />
                    </Form.Item>
                  </Col>
                </Row>
              )}

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item name="price" label="售价（F07，元）" rules={[{ required: true }]}>
                    <InputNumber min={0} step={1} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="original_price"
                    label="划线价（F08，元）"
                    tooltip="留空则前端不显示划线价；填写时必须 > 售价"
                  >
                    <InputNumber min={0} step={1} style={{ width: '100%' }} placeholder="可选" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="valid_days"
                    label="有效期（F09，天）"
                    rules={[{ required: true }]}
                    tooltip="默认 365 天"
                  >
                    <InputNumber min={1} max={3650} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>

              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item
                    name="stock"
                    label="库存（F10）"
                    extra={<Text type="secondary" style={{ fontSize: 12 }}>留空 = 无限发售</Text>}
                  >
                    <InputNumber min={0} style={{ width: '100%' }} placeholder="留空=无限" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item
                    name="per_user_limit"
                    label="同款限购（F11）"
                    extra={<Text type="secondary" style={{ fontSize: 12 }}>留空 = 不限</Text>}
                  >
                    <InputNumber min={1} style={{ width: '100%' }} placeholder="留空=不限" />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item name="renew_strategy" label="续卡策略（F12）" rules={[{ required: true }]}>
                    <Select options={[
                      { label: '叠加在原卡', value: 'add_on' },
                      { label: '新发独立卡', value: 'new_card' },
                    ]} />
                  </Form.Item>
                </Col>
              </Row>

              <Form.Item label="可用门店（F13）" required>
                <Space direction="vertical" style={{ width: '100%' }}>
                  <Form.Item name="store_all" valuePropName="checked" noStyle>
                    <Switch checkedChildren="全门店通用" unCheckedChildren="指定门店" />
                  </Form.Item>
                  {storeAll === false ? (
                    <Tooltip title="开启「全门店通用」后忽略此选择">
                      <Select
                        mode="multiple"
                        disabled
                        placeholder="（指定门店列表第 2 期接入门店选择器）"
                      />
                    </Tooltip>
                  ) : (
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      已开启「全门店通用」，忽略多选门店
                    </Text>
                  )}
                </Space>
              </Form.Item>

              <Form.Item
                name="item_product_ids"
                label="卡内项目（F14）"
                tooltip="必须从已有商品库中选择，不允许手填"
                rules={[{ required: true, message: '至少选择一个商品' }]}
              >
                <Select
                  mode="multiple"
                  placeholder="选择卡内可用项目（普通商品）"
                  optionFilterProp="label"
                  options={productOptions}
                  maxTagCount={10}
                />
              </Form.Item>

              <Divider style={{ margin: '12px 0' }} orientation="left">卡面设置</Divider>

              <Form.Item
                name="face_style"
                label="卡面样式（4 风格）"
                rules={[{ required: true }]}
              >
                <Radio.Group>
                  {FACE_STYLES.map((s) => (
                    <Radio key={s.code} value={s.code}>
                      <Tooltip title={s.hint}>
                        <span>{s.code}·{s.name}</span>
                      </Tooltip>
                    </Radio>
                  ))}
                </Radio.Group>
              </Form.Item>

              <Form.Item
                name="face_bg_code"
                label="卡面背景（8 色板，不可自定义）"
                rules={[{ required: true }]}
              >
                <Radio.Group style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {BG_OPTIONS.map((b) => (
                    <Radio.Button key={b.code} value={b.code} style={{ padding: '0 8px' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          width: 14,
                          height: 14,
                          borderRadius: 4,
                          background: b.hex,
                          marginRight: 6,
                          verticalAlign: 'middle',
                          border: '1px solid rgba(0,0,0,0.08)',
                        }}
                      />
                      {b.code}·{b.name}
                    </Radio.Button>
                  ))}
                </Radio.Group>
              </Form.Item>

              <Form.Item label="卡面显示项（4 项勾选）" required>
                <Form.Item name="face_show_flags" noStyle>
                  <ShowFlagsCheckbox />
                </Form.Item>
              </Form.Item>
            </Form>
          </Col>

          {/* 右侧：实时预览 */}
          <Col span={9}>
            <div style={{
              position: 'sticky', top: 0,
              background: '#fafafa',
              border: '1px dashed #d9d9d9',
              borderRadius: 12,
              padding: 14,
            }}>
              <Text type="secondary" style={{ fontSize: 12 }}>实时卡面预览（所见即所得）</Text>
              <div style={{ marginTop: 10 }}>
                <CardFace
                  faceStyle={faceStyle}
                  faceBgCode={faceBgCode}
                  faceShowFlags={faceShowFlags}
                  cardName={previewName}
                  itemsSummary={previewItemsSummary}
                  price={watchedAll?.price ?? 0}
                  originalPrice={watchedAll?.original_price ?? null}
                  validDays={watchedAll?.valid_days ?? 365}
                  cardType={cardType}
                  totalTimes={watchedAll?.total_times}
                  scopeType={scopeType}
                  size="lg"
                />
              </div>
              <div style={{ marginTop: 10, fontSize: 12, color: '#888' }}>
                · 卡面样式：{faceStyle}
                <br />
                · 卡面背景：{faceBgCode}
                <br />
                · 显示项：{[
                  isShowFlagOn(faceShowFlags, 1) ? '卡名' : null,
                  isShowFlagOn(faceShowFlags, 2) ? '服务内容' : null,
                  isShowFlagOn(faceShowFlags, 4) ? '价格' : null,
                  isShowFlagOn(faceShowFlags, 8) ? '有效期' : null,
                ].filter(Boolean).join(' / ') || '无'}
              </div>
            </div>
          </Col>
        </Row>
      </Modal>
    </div>
  );
}

// 4 项勾选自定义控件，绑定 form 的 face_show_flags（int bitmask）
const ShowFlagsCheckbox: React.FC<{
  value?: number;
  onChange?: (v: number) => void;
}> = ({ value = DEFAULT_FACE_SHOW_FLAGS, onChange }) => {
  const flags = Number(value || 0);
  return (
    <Space wrap>
      {SHOW_FLAGS.map((f) => (
        <Checkbox
          key={f.code}
          checked={isShowFlagOn(flags, f.bit)}
          onChange={(e) => {
            const next = toggleShowFlag(flags, f.bit, e.target.checked);
            onChange?.(next);
          }}
        >
          {f.code}·{f.name}
        </Checkbox>
      ))}
    </Space>
  );
};
