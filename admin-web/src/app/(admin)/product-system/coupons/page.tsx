'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, Tag, message,
  Typography, Popconfirm, Row, Col, DatePicker,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SendOutlined, SearchOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface Coupon {
  id: number;
  name: string;
  type: string;
  condition_amount: number;
  discount_value: number;
  discount_rate: number;
  scope: string;
  scope_ids: any;
  total_count: number;
  claimed_count: number;
  used_count: number;
  valid_start: string | null;
  valid_end: string | null;
  status: string;
  created_at: string;
}

function mapCoupon(raw: Record<string, unknown>): Coupon {
  return {
    id: Number(raw.id),
    name: String(raw.name ?? ''),
    type: String(raw.type ?? ''),
    condition_amount: Number(raw.condition_amount ?? 0),
    discount_value: Number(raw.discount_value ?? 0),
    discount_rate: Number(raw.discount_rate ?? 1),
    scope: String(raw.scope ?? 'all'),
    scope_ids: raw.scope_ids,
    total_count: Number(raw.total_count ?? 0),
    claimed_count: Number(raw.claimed_count ?? 0),
    used_count: Number(raw.used_count ?? 0),
    valid_start: raw.valid_start ? String(raw.valid_start) : null,
    valid_end: raw.valid_end ? String(raw.valid_end) : null,
    status: String(raw.status ?? 'active'),
    created_at: String(raw.created_at ?? ''),
  };
}

const couponTypeOptions = [
  { label: '满减券', value: 'full_reduction' },
  { label: '折扣券', value: 'discount' },
  { label: '代金券', value: 'voucher' },
  { label: '免邮券', value: 'free_shipping' },
];

const couponTypeMap: Record<string, string> = {
  full_reduction: '满减券',
  discount: '折扣券',
  voucher: '代金券',
  free_shipping: '免邮券',
};

const couponTypeColorMap: Record<string, string> = {
  full_reduction: 'volcano',
  discount: 'blue',
  voucher: 'green',
  free_shipping: 'purple',
};

const scopeOptions = [
  { label: '全部商品', value: 'all' },
  { label: '指定分类', value: 'category' },
  { label: '指定商品', value: 'product' },
];

const statusOptions = [
  { label: '启用', value: 'active' },
  { label: '停用', value: 'inactive' },
];

export default function CouponsPage() {
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Coupon | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filterType, setFilterType] = useState<string | undefined>(undefined);
  const [searchText, setSearchText] = useState('');
  const [form] = Form.useForm();
  const [couponType, setCouponType] = useState<string>('full_reduction');
  const [scope, setScope] = useState<string>('all');

  const [distributeVisible, setDistributeVisible] = useState(false);
  const [distributeCoupon, setDistributeCoupon] = useState<Coupon | null>(null);
  const [distributeForm] = Form.useForm();

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterType) params.status = filterType;
      const res = await get('/api/admin/coupons', params);
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        let filtered = rawList.map((r: Record<string, unknown>) => mapCoupon(r));
        if (searchText) {
          const kw = searchText.toLowerCase();
          filtered = filtered.filter(c => c.name.toLowerCase().includes(kw));
        }
        setCoupons(filtered);
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? filtered.length }));
      }
    } catch {
      setCoupons([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
    } finally {
      setLoading(false);
    }
  }, [filterType, searchText]);

  useEffect(() => {
    fetchData();
  }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({
      type: 'full_reduction',
      scope: 'all',
      status: 'active',
      total_count: 100,
      condition_amount: 0,
      discount_value: 0,
      discount_rate: 1.0,
    });
    setCouponType('full_reduction');
    setScope('all');
    setModalVisible(true);
  };

  const handleEdit = (record: Coupon) => {
    setEditingRecord(record);
    setCouponType(record.type);
    setScope(record.scope);
    form.setFieldsValue({
      name: record.name,
      type: record.type,
      condition_amount: record.condition_amount,
      discount_value: record.discount_value,
      discount_rate: record.discount_rate,
      scope: record.scope,
      scope_ids: record.scope_ids ? (Array.isArray(record.scope_ids) ? record.scope_ids.join(',') : String(record.scope_ids)) : '',
      total_count: record.total_count,
      valid_range: record.valid_start && record.valid_end
        ? [dayjs(record.valid_start), dayjs(record.valid_end)]
        : null,
      status: record.status,
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/coupons/${id}`);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      let scopeIds = null;
      if (values.scope !== 'all' && values.scope_ids) {
        try {
          scopeIds = JSON.parse(values.scope_ids);
        } catch {
          scopeIds = values.scope_ids.split(',').map((s: string) => Number(s.trim())).filter((n: number) => !isNaN(n));
        }
      }

      const payload = {
        name: values.name,
        type: values.type,
        condition_amount: values.condition_amount ?? 0,
        discount_value: values.discount_value ?? 0,
        discount_rate: values.discount_rate ?? 1.0,
        scope: values.scope,
        scope_ids: scopeIds,
        total_count: values.total_count ?? 0,
        valid_start: values.valid_range?.[0] ? values.valid_range[0].toISOString() : null,
        valid_end: values.valid_range?.[1] ? values.valid_range[1].toISOString() : null,
        status: values.status,
      };

      if (editingRecord) {
        await put(`/api/admin/coupons/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/coupons', payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const handleDistribute = async () => {
    if (!distributeCoupon) return;
    try {
      const values = await distributeForm.validateFields();
      const userIds = values.user_ids
        .split(',')
        .map((s: string) => Number(s.trim()))
        .filter((n: number) => !isNaN(n) && n > 0);

      if (userIds.length === 0) {
        message.warning('请输入有效的用户ID');
        return;
      }

      await post(`/api/admin/coupons/${distributeCoupon.id}/distribute`, { user_ids: userIds });
      message.success('发放成功');
      setDistributeVisible(false);
      distributeForm.resetFields();
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '发放失败');
    }
  };

  const descriptionText = (record: Coupon) => {
    switch (record.type) {
      case 'full_reduction':
        return `满${record.condition_amount}减${record.discount_value}`;
      case 'discount':
        return `${record.discount_rate * 10}折${record.condition_amount > 0 ? ` (满${record.condition_amount})` : ''}`;
      case 'voucher':
        return `代金券 ¥${record.discount_value}`;
      case 'free_shipping':
        return `免邮${record.condition_amount > 0 ? ` (满${record.condition_amount})` : ''}`;
      default:
        return '-';
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '优惠券名称', dataIndex: 'name', key: 'name', width: 160 },
    {
      title: '类型', dataIndex: 'type', key: 'type', width: 90,
      render: (v: string) => <Tag color={couponTypeColorMap[v] || 'default'}>{couponTypeMap[v] || v}</Tag>,
    },
    {
      title: '优惠规则', key: 'rule', width: 180,
      render: (_: unknown, record: Coupon) => descriptionText(record),
    },
    {
      title: '适用范围', dataIndex: 'scope', key: 'scope', width: 100,
      render: (v: string) => {
        const map: Record<string, string> = { all: '全部商品', category: '指定分类', product: '指定商品' };
        return map[v] || v;
      },
    },
    {
      title: '库存/已领/已用', key: 'counts', width: 140,
      render: (_: unknown, record: Coupon) => (
        <span>{record.total_count} / {record.claimed_count} / {record.used_count}</span>
      ),
    },
    {
      title: '有效期', key: 'valid', width: 200,
      render: (_: unknown, record: Coupon) => {
        if (!record.valid_start && !record.valid_end) return '长期有效';
        return `${record.valid_start ? dayjs(record.valid_start).format('YYYY-MM-DD') : '—'} ~ ${record.valid_end ? dayjs(record.valid_end).format('YYYY-MM-DD') : '—'}`;
      },
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 220, fixed: 'right' as const,
      render: (_: unknown, record: Coupon) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<SendOutlined />}
            onClick={() => { setDistributeCoupon(record); distributeForm.resetFields(); setDistributeVisible(true); }}>
            发放
          </Button>
          <Popconfirm title="确定删除该优惠券？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>优惠券管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增优惠券</Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select
            placeholder="按状态筛选"
            allowClear
            style={{ width: 120 }}
            options={statusOptions}
            value={filterType}
            onChange={v => setFilterType(v)}
          />
        </Col>
        <Col>
          <Input
            placeholder="搜索优惠券名称"
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            onPressEnter={handleSearch}
            style={{ width: 220 }}
            allowClear
          />
        </Col>
        <Col>
          <Button type="primary" onClick={handleSearch}>搜索</Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={coupons}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1400 }}
      />

      {/* 新增/编辑弹窗 */}
      <Modal
        title={editingRecord ? '编辑优惠券' : '新增优惠券'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="优惠券名称" name="name" rules={[{ required: true, message: '请输入名称' }]}>
            <Input placeholder="请输入优惠券名称" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="优惠券类型" name="type" rules={[{ required: true, message: '请选择类型' }]}>
                <Select options={couponTypeOptions} onChange={v => setCouponType(v)} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="状态" name="status">
                <Select options={statusOptions} />
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="使用门槛金额" name="condition_amount">
                <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0 表示无门槛" />
              </Form.Item>
            </Col>
            {(couponType === 'full_reduction' || couponType === 'voucher') && (
              <Col span={12}>
                <Form.Item label="优惠金额" name="discount_value">
                  <InputNumber min={0} step={0.01} style={{ width: '100%' }} placeholder="0.00" />
                </Form.Item>
              </Col>
            )}
            {couponType === 'discount' && (
              <Col span={12}>
                <Form.Item label="折扣率" name="discount_rate" extra="如 0.8 表示八折">
                  <InputNumber min={0.01} max={1} step={0.01} style={{ width: '100%' }} placeholder="0.80" />
                </Form.Item>
              </Col>
            )}
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="适用范围" name="scope">
                <Select options={scopeOptions} onChange={v => setScope(v)} />
              </Form.Item>
            </Col>
            {scope !== 'all' && (
              <Col span={12}>
                <Form.Item label={scope === 'category' ? '分类ID (逗号分隔)' : '商品ID (逗号分隔)'} name="scope_ids">
                  <Input placeholder="如: 1,2,3" />
                </Form.Item>
              </Col>
            )}
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item label="发行总量" name="total_count">
                <InputNumber min={0} style={{ width: '100%' }} placeholder="0 表示不限量" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item label="有效期" name="valid_range">
                <RangePicker showTime style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 发放弹窗 */}
      <Modal
        title="发放优惠券"
        open={distributeVisible}
        onOk={handleDistribute}
        onCancel={() => setDistributeVisible(false)}
        destroyOnClose
      >
        {distributeCoupon && (
          <div style={{ marginBottom: 16, padding: '12px 16px', background: '#f6ffed', borderRadius: 8 }}>
            <div>优惠券: {distributeCoupon.name}</div>
            <div>类型: {couponTypeMap[distributeCoupon.type] || distributeCoupon.type}</div>
            <div>剩余: {distributeCoupon.total_count > 0 ? distributeCoupon.total_count - distributeCoupon.claimed_count : '不限'}</div>
          </div>
        )}
        <Form form={distributeForm} layout="vertical">
          <Form.Item
            label="用户ID"
            name="user_ids"
            rules={[{ required: true, message: '请输入用户ID' }]}
            extra="多个用户ID用逗号分隔，如: 1,2,3"
          >
            <Input.TextArea rows={3} placeholder="请输入用户ID，多个用逗号分隔" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
