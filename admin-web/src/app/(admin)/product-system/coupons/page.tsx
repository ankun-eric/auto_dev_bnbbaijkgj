'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, Tag, message,
  Typography, Popconfirm, Row, Col, Drawer, DatePicker, Checkbox, Divider, Tabs, Upload,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, SendOutlined, SearchOutlined,
  HistoryOutlined, RollbackOutlined, DownloadOutlined, KeyOutlined,
} from '@ant-design/icons';
import { get, post, put, del } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

const VALIDITY_OPTIONS = [3, 7, 15, 30, 60, 90, 180, 365];

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
  validity_days: number;
  status: string;
  created_at: string;
}

interface GrantItem {
  id: number;
  coupon_id: number;
  user_id: number | null;
  user_phone: string | null;
  method: string;
  status: string;
  granted_at: string | null;
  used_at: string | null;
  order_no: string | null;
  operator_name: string | null;
  redeem_code: string | null;
  recall_reason: string | null;
}

const couponTypeOptions = [
  { label: '满减券', value: 'full_reduction' },
  { label: '折扣券', value: 'discount' },
  { label: '代金券', value: 'voucher' },
  { label: '免费试用', value: 'free_trial' },
];

const couponTypeMap: Record<string, string> = {
  full_reduction: '满减券', discount: '折扣券', voucher: '代金券', free_trial: '免费试用',
};

const couponTypeColorMap: Record<string, string> = {
  full_reduction: 'volcano', discount: 'blue', voucher: 'green', free_trial: 'purple',
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

const grantMethodMap: Record<string, string> = {
  self: '自助领取', direct: '定向发放', new_user: '新人券', redeem_code: '兑换码',
};

const grantStatusMap: Record<string, { label: string; color: string }> = {
  granted: { label: '已发放', color: 'blue' },
  used: { label: '已使用', color: 'green' },
  recalled: { label: '已回收', color: 'red' },
  expired: { label: '已过期', color: 'default' },
};

export default function CouponsPage() {
  const [coupons, setCoupons] = useState<Coupon[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Coupon | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [filterStatus, setFilterStatus] = useState<string | undefined>(undefined);
  const [searchText, setSearchText] = useState('');
  const [form] = Form.useForm();
  const [couponType, setCouponType] = useState<string>('full_reduction');
  const [scope, setScope] = useState<string>('all');

  // 发放记录抽屉
  const [grantsVisible, setGrantsVisible] = useState(false);
  const [grantsCoupon, setGrantsCoupon] = useState<Coupon | null>(null);
  const [grants, setGrants] = useState<GrantItem[]>([]);
  const [grantsLoading, setGrantsLoading] = useState(false);
  const [grantFilters, setGrantFilters] = useState<{ phone?: string; status?: string; method?: string; range?: any[] }>({});
  const [selectedGrantIds, setSelectedGrantIds] = useState<number[]>([]);

  // 4 种发放方式
  const [grantTypeModalVisible, setGrantTypeModalVisible] = useState(false);
  const [grantTypeCoupon, setGrantTypeCoupon] = useState<Coupon | null>(null);
  const [grantTypeForm] = Form.useForm();
  const [grantTypeMethod, setGrantTypeMethod] = useState<string>('direct');

  // 兑换码批次
  const [codeBatchModalVisible, setCodeBatchModalVisible] = useState(false);
  const [codeBatchCoupon, setCodeBatchCoupon] = useState<Coupon | null>(null);
  const [codeBatchForm] = Form.useForm();
  const [partners, setPartners] = useState<Array<{ id: number; name: string }>>([]);

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterStatus) params.status = filterStatus;
      if (searchText) params.keyword = searchText;
      const res = await get('/api/admin/coupons', params);
      if (res) {
        const items = res.items || res.list || [];
        setCoupons(Array.isArray(items) ? items : []);
        setPagination(prev => ({ ...prev, current: page, pageSize, total: res.total ?? items.length }));
      }
    } catch (err: any) {
      setCoupons([]);
      message.error(err?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [filterStatus, searchText]);

  useEffect(() => { fetchData(); }, []);
  useEffect(() => { get('/api/admin/partners').then((r: any) => setPartners(r?.items || [])).catch(() => {}); }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({
      type: 'full_reduction', scope: 'all', status: 'active',
      total_count: 100, condition_amount: 0, discount_value: 0,
      discount_rate: 0.8, validity_days: 30,
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
      validity_days: record.validity_days || 30,
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
        try { scopeIds = JSON.parse(values.scope_ids); }
        catch { scopeIds = String(values.scope_ids).split(',').map((s: string) => Number(s.trim())).filter((n: number) => !isNaN(n)); }
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
        validity_days: values.validity_days ?? 30,
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

  // ─── 发放记录 ───
  const openGrants = async (record: Coupon) => {
    setGrantsCoupon(record);
    setGrantFilters({});
    setSelectedGrantIds([]);
    setGrantsVisible(true);
    await loadGrants(record.id, {});
  };

  const loadGrants = async (couponId: number, filters: any) => {
    setGrantsLoading(true);
    try {
      const params: any = { page: 1, page_size: 100 };
      if (filters.phone) params.phone = filters.phone;
      if (filters.status) params.status = filters.status;
      if (filters.method) params.method = filters.method;
      if (filters.range?.[0]) params.start = filters.range[0].toISOString();
      if (filters.range?.[1]) params.end = filters.range[1].toISOString();
      const res: any = await get(`/api/admin/coupons/${couponId}/grants`, params);
      setGrants(res?.items || []);
    } catch (err: any) {
      setGrants([]);
      message.error(err?.response?.data?.detail || '加载发放记录失败');
    } finally {
      setGrantsLoading(false);
    }
  };

  const exportGrants = () => {
    if (!grantsCoupon) return;
    const url = `/api/admin/coupons/${grantsCoupon.id}/grants/export`;
    window.open(url, '_blank');
  };

  const recallGrants = async () => {
    if (selectedGrantIds.length === 0) {
      message.warning('请先选择要回收的记录');
      return;
    }
    let reason = '';
    Modal.confirm({
      title: `回收 ${selectedGrantIds.length} 条发放记录`,
      content: (
        <Input.TextArea
          rows={3}
          placeholder="请填写回收原因（必填）"
          onChange={(e) => { reason = e.target.value; }}
        />
      ),
      okText: '确认回收',
      onOk: async () => {
        if (!reason.trim()) {
          message.error('回收原因必填');
          return Promise.reject();
        }
        try {
          await post('/api/admin/coupons/grants/recall', { grant_ids: selectedGrantIds, reason });
          message.success('回收成功');
          setSelectedGrantIds([]);
          if (grantsCoupon) await loadGrants(grantsCoupon.id, grantFilters);
        } catch (err: any) {
          message.error(err?.response?.data?.detail || '回收失败');
        }
      },
    });
  };

  // ─── 4 种发放 ───
  const openGrantType = (record: Coupon) => {
    setGrantTypeCoupon(record);
    setGrantTypeMethod('direct');
    grantTypeForm.resetFields();
    grantTypeForm.setFieldsValue({ method: 'direct' });
    setGrantTypeModalVisible(true);
  };

  const submitGrantType = async () => {
    if (!grantTypeCoupon) return;
    try {
      const values = await grantTypeForm.validateFields();
      if (grantTypeMethod === 'direct') {
        const payload: any = {
          coupon_id: grantTypeCoupon.id,
          user_ids: values.user_ids
            ? String(values.user_ids).split(',').map((s: string) => Number(s.trim())).filter((n: number) => !isNaN(n) && n > 0)
            : null,
          phones: values.phones
            ? String(values.phones).split(/[,\s]+/).map((s: string) => s.trim()).filter(Boolean)
            : null,
          filter_tags: {},
        };
        if (values.member_level !== undefined && values.member_level !== null && values.member_level !== '')
          payload.filter_tags.member_level = values.member_level;
        if (values.registered_within_days)
          payload.filter_tags.registered_within_days = values.registered_within_days;
        const res: any = await post(`/api/admin/coupons/${grantTypeCoupon.id}/grant/direct`, payload);
        message.success(res?.message || '发放成功');
        setGrantTypeModalVisible(false);
        fetchData(pagination.current, pagination.pageSize);
      } else if (grantTypeMethod === 'new_user') {
        // 写入新人券规则
        const cur: any = await get('/api/admin/new-user-coupons');
        const ids = Array.from(new Set([...(cur?.coupon_ids || []), grantTypeCoupon.id]));
        await put('/api/admin/new-user-coupons', { coupon_ids: ids });
        message.success('已加入新人券（注册后自动发放）');
        setGrantTypeModalVisible(false);
      } else if (grantTypeMethod === 'self') {
        // 自助领取直接由用户在「领券中心」领，无需后端动作
        message.success('该券为启用状态时，用户即可在「领券中心」自助领取');
        setGrantTypeModalVisible(false);
      } else if (grantTypeMethod === 'redeem_code') {
        // 跳转去打开兑换码批次弹窗
        setGrantTypeModalVisible(false);
        setCodeBatchCoupon(grantTypeCoupon);
        codeBatchForm.resetFields();
        codeBatchForm.setFieldsValue({ code_type: 'unique', total_count: 100, per_user_limit: 1 });
        setCodeBatchModalVisible(true);
      }
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const submitCodeBatch = async () => {
    if (!codeBatchCoupon) return;
    try {
      const values = await codeBatchForm.validateFields();
      const payload = {
        coupon_id: codeBatchCoupon.id,
        code_type: values.code_type,
        name: values.name,
        total_count: values.total_count,
        universal_code: values.universal_code,
        per_user_limit: values.per_user_limit ?? 1,
        partner_id: values.partner_id || null,
      };
      const res: any = await post('/api/admin/coupons/redeem-code-batches', payload);
      message.success(values.code_type === 'universal'
        ? `通用兑换码：${res.universal_code}`
        : `已生成 ${res.total_count} 个一次性唯一码`);
      setCodeBatchModalVisible(false);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '操作失败');
    }
  };

  const descriptionText = (record: Coupon) => {
    switch (record.type) {
      case 'full_reduction': return `满${record.condition_amount}减${record.discount_value}`;
      case 'discount': return `${(record.discount_rate * 10).toFixed(1)}折${record.condition_amount > 0 ? ` (满${record.condition_amount})` : ''}`;
      case 'voucher': return `代金券 ¥${record.discount_value}`;
      case 'free_trial': return `免费试用`;
      default: return '-';
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '优惠券名称', dataIndex: 'name', key: 'name', width: 180 },
    {
      title: '类型', dataIndex: 'type', key: 'type', width: 90,
      render: (v: string) => <Tag color={couponTypeColorMap[v] || 'default'}>{couponTypeMap[v] || v}</Tag>,
    },
    { title: '优惠规则', key: 'rule', width: 180, render: (_: unknown, r: Coupon) => descriptionText(r) },
    {
      title: '适用范围', dataIndex: 'scope', key: 'scope', width: 100,
      render: (v: string) => ({ all: '全部商品', category: '指定分类', product: '指定商品' } as Record<string, string>)[v] || v,
    },
    {
      title: '库存/已领/已用', key: 'counts', width: 140,
      render: (_: unknown, r: Coupon) => `${r.total_count} / ${r.claimed_count} / ${r.used_count}`,
    },
    {
      title: '有效期', key: 'valid', width: 140,
      render: (_: unknown, r: Coupon) => <Tag color="cyan">领取后 {r.validity_days || 30} 天</Tag>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '启用' : '停用'}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 320, fixed: 'right' as const,
      render: (_: unknown, record: Coupon) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<SendOutlined />} onClick={() => openGrantType(record)}>发放</Button>
          <Button type="link" size="small" icon={<HistoryOutlined />} onClick={() => openGrants(record)}>发放记录</Button>
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
          <Select placeholder="按状态筛选" allowClear style={{ width: 120 }}
            options={statusOptions} value={filterStatus} onChange={v => setFilterStatus(v)} />
        </Col>
        <Col>
          <Input placeholder="搜索优惠券名称" prefix={<SearchOutlined />}
            value={searchText} onChange={e => setSearchText(e.target.value)}
            onPressEnter={handleSearch} style={{ width: 220 }} allowClear />
        </Col>
        <Col>
          <Button type="primary" onClick={handleSearch}>搜索</Button>
        </Col>
      </Row>

      <Table columns={columns} dataSource={coupons} rowKey="id" loading={loading}
        pagination={{
          ...pagination, showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1500 }} />

      {/* 新增/编辑弹窗 */}
      <Modal title={editingRecord ? '编辑优惠券' : '新增优惠券'} open={modalVisible}
        onOk={handleSubmit} onCancel={() => setModalVisible(false)} width={680} destroyOnClose>
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
              <Form.Item label="有效期" name="validity_days" extra="从用户领取时刻起算 N 天后失效"
                rules={[{ required: true, message: '请选择有效期' }]}>
                <Select
                  options={VALIDITY_OPTIONS.map(d => ({ label: `${d} 天`, value: d }))}
                  placeholder="请选择" />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 4 种发放方式 */}
      <Modal title={`发放优惠券：${grantTypeCoupon?.name || ''}`}
        open={grantTypeModalVisible} onOk={submitGrantType}
        onCancel={() => setGrantTypeModalVisible(false)} width={680} destroyOnClose>
        <Form form={grantTypeForm} layout="vertical">
          <Form.Item label="发放方式" name="method" initialValue="direct">
            <Select onChange={v => setGrantTypeMethod(v)}
              options={[
                { label: 'A 自助领取（用户在领券中心自助领取）', value: 'self' },
                { label: 'B 定向发放（指定用户/手机号/标签）', value: 'direct' },
                { label: 'D 新人券（注册自动发放）', value: 'new_user' },
                { label: 'F 兑换码（一码通用 / 一次性唯一码）', value: 'redeem_code' },
              ]} />
          </Form.Item>
          {grantTypeMethod === 'direct' && (
            <>
              <Form.Item label="用户ID（多个用逗号分隔）" name="user_ids">
                <Input placeholder="如: 1,2,3" />
              </Form.Item>
              <Form.Item label="手机号（多个用逗号或空格分隔）" name="phones">
                <Input.TextArea rows={2} placeholder="13800000000,13800000001" />
              </Form.Item>
              <Divider plain>标签筛选（可选）</Divider>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item label="用户等级" name="member_level" extra="0=普通会员，1+=付费/高级">
                    <InputNumber min={0} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item label="注册时长 ≤ N 天" name="registered_within_days">
                    <InputNumber min={0} style={{ width: '100%' }} placeholder="如 30 表示新注册 30 天内" />
                  </Form.Item>
                </Col>
              </Row>
            </>
          )}
          {grantTypeMethod === 'new_user' && (
            <div style={{ padding: 16, background: '#f6ffed', borderRadius: 8 }}>
              <p>✅ 确定后，新注册用户将自动获得本券（每人 1 张）</p>
              <p style={{ color: '#999', marginBottom: 0 }}>已加入新人券池后，可在「新人券池」中管理。</p>
            </div>
          )}
          {grantTypeMethod === 'self' && (
            <div style={{ padding: 16, background: '#e6f7ff', borderRadius: 8 }}>
              <p>📣 启用状态的优惠券将自动出现在用户「领券中心」。</p>
              <p style={{ color: '#999', marginBottom: 0 }}>每人每券限领 1 张。</p>
            </div>
          )}
          {grantTypeMethod === 'redeem_code' && (
            <div style={{ padding: 16, background: '#fff7e6', borderRadius: 8 }}>
              <p>📦 确定后将打开兑换码批次创建窗口</p>
            </div>
          )}
        </Form>
      </Modal>

      {/* 兑换码批次 */}
      <Modal title={`生成兑换码：${codeBatchCoupon?.name || ''}`}
        open={codeBatchModalVisible} onOk={submitCodeBatch}
        onCancel={() => setCodeBatchModalVisible(false)} width={600} destroyOnClose>
        <Form form={codeBatchForm} layout="vertical">
          <Form.Item label="批次名称" name="name">
            <Input placeholder="如：2026Q2 双11 通用券" />
          </Form.Item>
          <Form.Item label="码类型" name="code_type" rules={[{ required: true }]}>
            <Select options={[
              { label: 'A 一码通用（所有用户使用同一个码）', value: 'universal' },
              { label: 'C+ 一次性唯一码（每码每人 1 次）', value: 'unique' },
            ]} />
          </Form.Item>
          <Form.Item shouldUpdate noStyle>
            {() => codeBatchForm.getFieldValue('code_type') === 'universal' ? (
              <>
                <Form.Item label="自定义通用码（留空自动生成）" name="universal_code">
                  <Input placeholder="如 NEW2026" />
                </Form.Item>
                <Form.Item label="每用户限兑次数" name="per_user_limit" initialValue={1}>
                  <InputNumber min={1} style={{ width: '100%' }} />
                </Form.Item>
              </>
            ) : (
              <Form.Item label="生成数量" name="total_count" rules={[{ required: true }]}
                extra="单批最多 100000 个，16 位随机字符">
                <InputNumber min={1} max={100000} style={{ width: '100%' }} />
              </Form.Item>
            )}
          </Form.Item>
          <Form.Item label="第三方合作方（可选，C+ 模式必填）" name="partner_id">
            <Select allowClear placeholder="选择合作方"
              options={partners.map(p => ({ label: p.name, value: p.id }))} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 发放记录抽屉 */}
      <Drawer title={`发放记录：${grantsCoupon?.name || ''}`} width={1100}
        open={grantsVisible} onClose={() => setGrantsVisible(false)}
        extra={
          <Space>
            <Button icon={<DownloadOutlined />} onClick={exportGrants}>导出 Excel</Button>
            <Button danger icon={<RollbackOutlined />} onClick={recallGrants}
              disabled={selectedGrantIds.length === 0}>批量回收</Button>
          </Space>
        }>
        <Row gutter={8} style={{ marginBottom: 12 }}>
          <Col><Input placeholder="手机号" allowClear style={{ width: 160 }}
            value={grantFilters.phone} onChange={e => setGrantFilters(f => ({ ...f, phone: e.target.value }))} /></Col>
          <Col><Select placeholder="状态" allowClear style={{ width: 120 }}
            options={Object.entries(grantStatusMap).map(([k, v]) => ({ label: v.label, value: k }))}
            value={grantFilters.status} onChange={v => setGrantFilters(f => ({ ...f, status: v }))} /></Col>
          <Col><Select placeholder="发放方式" allowClear style={{ width: 140 }}
            options={Object.entries(grantMethodMap).map(([k, v]) => ({ label: v, value: k }))}
            value={grantFilters.method} onChange={v => setGrantFilters(f => ({ ...f, method: v }))} /></Col>
          <Col><DatePicker.RangePicker showTime
            value={grantFilters.range as any}
            onChange={v => setGrantFilters(f => ({ ...f, range: v as any }))} /></Col>
          <Col><Button type="primary" onClick={() => grantsCoupon && loadGrants(grantsCoupon.id, grantFilters)}>筛选</Button></Col>
        </Row>
        <Table size="small" rowKey="id" loading={grantsLoading} dataSource={grants}
          rowSelection={{
            selectedRowKeys: selectedGrantIds,
            onChange: (keys) => setSelectedGrantIds(keys as number[]),
          }}
          columns={[
            { title: '用户/手机号', key: 'who', width: 160,
              render: (_: any, r: GrantItem) => `${r.user_id ?? ''} ${r.user_phone ?? ''}`.trim() || '-' },
            { title: '发放时间', dataIndex: 'granted_at', width: 160,
              render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            { title: '方式', dataIndex: 'method', width: 100,
              render: (v: string) => grantMethodMap[v] || v },
            { title: '状态', dataIndex: 'status', width: 90,
              render: (v: string) => {
                const s = grantStatusMap[v] || { label: v, color: 'default' };
                return <Tag color={s.color}>{s.label}</Tag>;
              } },
            { title: '使用时间', dataIndex: 'used_at', width: 160,
              render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            { title: '订单号', dataIndex: 'order_no', width: 160,
              render: (v: string) => v ? <a>{v}</a> : '-' },
            { title: '操作人', dataIndex: 'operator_name', width: 120,
              render: (v: string) => v || '-' },
            { title: '兑换码', dataIndex: 'redeem_code', width: 160,
              render: (v: string) => v || '-' },
            { title: '回收原因', dataIndex: 'recall_reason', width: 160,
              render: (v: string) => v || '-' },
          ]} />
      </Drawer>
    </div>
  );
}
