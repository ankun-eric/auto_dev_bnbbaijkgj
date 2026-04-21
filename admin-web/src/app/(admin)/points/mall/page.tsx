'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, Tag, message,
  Typography, Popconfirm, Tabs, DatePicker, Row, Col,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, GiftOutlined,
  ArrowUpOutlined, ArrowDownOutlined, SearchOutlined, DownloadOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload as uploadFile } from '@/lib/api';
import dayjs from 'dayjs';
import type { RcFile, UploadFile } from 'antd/es/upload/interface';

const { Title } = Typography;
const { TextArea } = Input;
const { RangePicker } = DatePicker;

interface MallGoods {
  id: number;
  name: string;
  category: string;
  points: number;
  stock: number;
  exchangeCount: number;
  status: string;
  image: string;
  description: string;
  detailHtml: string;
  refCouponId?: number;
  refServiceId?: number;
  limitPerUser: number;
  images: string[];
  createdAt: string;
}

interface ExchangeRecord {
  id: number;
  userId: number;
  userName: string;
  goodsName: string;
  points: number;
  status: string;
  createdAt: string;
}

interface ServiceProductOption {
  value: number;
  label: string;
  name: string;
  image?: string;
  category_name?: string;
  sale_price?: number;
}

const TYPE_LABELS: Record<string, string> = {
  coupon: '优惠券',
  virtual: '虚拟商品',
  physical: '实物商品',
  service: '体验服务',
  third_party: '第三方商品',
};

// v3.1：保留 coupon，严格不做硬编码 serviceTypeOptions（Bug2 修复）
const categoryOptions = [
  { label: '优惠券', value: 'coupon' },
  { label: '体验服务', value: 'service' },
  { label: '实物商品', value: 'physical' },
  { label: '虚拟商品（开发中）', value: 'virtual', disabled: true },
  { label: '第三方商品（开发中）', value: 'third_party', disabled: true },
];

function firstImage(images: unknown): string {
  if (Array.isArray(images) && images.length > 0) return String(images[0]);
  if (typeof images === 'string') return images;
  return '';
}

function allImages(images: unknown): string[] {
  if (Array.isArray(images)) return images.map((x) => String(x)).filter(Boolean);
  if (typeof images === 'string' && images) return [images];
  return [];
}

function mapMallItemFromApi(raw: Record<string, unknown>): MallGoods {
  return {
    id: Number(raw.id),
    name: String(raw.name ?? ''),
    category: String(raw.type ?? ''),
    points: Number(raw.price_points ?? 0),
    stock: Number(raw.stock ?? 0),
    exchangeCount: Number(raw.exchange_count ?? 0),
    status: String(raw.status ?? ''),
    image: firstImage(raw.images),
    images: allImages(raw.images),
    description: String(raw.description ?? ''),
    detailHtml: String(raw.detail_html ?? ''),
    refCouponId: raw.ref_coupon_id ? Number(raw.ref_coupon_id) : undefined,
    refServiceId: raw.ref_service_id ? Number(raw.ref_service_id) : undefined,
    limitPerUser: Number(raw.limit_per_user ?? 0),
    createdAt: String(raw.created_at ?? ''),
  };
}

function mapExchangeRecord(raw: Record<string, unknown>): ExchangeRecord {
  return {
    id: Number(raw.id),
    userId: Number(raw.user_id ?? 0),
    userName: String(raw.user_nickname || raw.user_name || `用户#${raw.user_id}`),
    goodsName: String(raw.goods_name || raw.item_name || ''),
    points: Number(raw.points ?? raw.price_points ?? 0),
    status: String(raw.status ?? ''),
    createdAt: String(raw.created_at ?? ''),
  };
}

function isMallOnShelf(status: string) {
  return status === 'active';
}

/** v3.1: 统一错误提示 —— 尽量暴露后端 detail */
function extractDetail(err: any, fallback = '操作失败'): string {
  return (
    err?.response?.data?.detail
    || err?.response?.data?.message
    || err?.data?.detail
    || err?.detail
    || err?.message
    || fallback
  );
}

export default function PointsMallPage() {
  const [activeTab, setActiveTab] = useState('goods');

  const [goods, setGoods] = useState<MallGoods[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<MallGoods | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [searchText, setSearchText] = useState('');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [form] = Form.useForm();

  const [availableCoupons, setAvailableCoupons] = useState<{label: string; value: number}[]>([]);
  const [serviceProducts, setServiceProducts] = useState<ServiceProductOption[]>([]);
  const serviceSearchTimer = useRef<any>(null);

  const [category, setCategory] = useState<string>('coupon');
  const [refCouponId, setRefCouponId] = useState<number | undefined>();
  const [refServiceId, setRefServiceId] = useState<number | undefined>();
  const [detailHtml, setDetailHtml] = useState<string>('');

  const [records, setRecords] = useState<ExchangeRecord[]>([]);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [recordsPagination, setRecordsPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [recordsKeyword, setRecordsKeyword] = useState('');
  const [recordsDateRange, setRecordsDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (searchText) params.keyword = searchText;
      const res = await get('/api/admin/points/mall', params);
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        setGoods(rawList.map((r: Record<string, unknown>) => mapMallItemFromApi(r)));
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch (err: any) {
      setGoods([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
      message.error(extractDetail(err, '加载商品失败'));
    } finally {
      setLoading(false);
    }
  };

  const fetchRecords = async (page = 1, pageSize = 10) => {
    setRecordsLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (recordsKeyword) params.keyword = recordsKeyword;
      if (recordsDateRange?.[0]) params.start_date = recordsDateRange[0].format('YYYY-MM-DD');
      if (recordsDateRange?.[1]) params.end_date = recordsDateRange[1].format('YYYY-MM-DD');
      const res = await get('/api/admin/points/exchange-records', params);
      if (res) {
        const items = res.items || res.list || res;
        const rawList = Array.isArray(items) ? items : [];
        setRecords(rawList.map((r: Record<string, unknown>) => mapExchangeRecord(r)));
        setRecordsPagination(prev => ({ ...prev, current: page, total: res.total ?? rawList.length }));
      }
    } catch (err: any) {
      setRecords([]);
      setRecordsPagination(prev => ({ ...prev, current: page, total: 0 }));
      message.error(extractDetail(err, '加载兑换记录失败'));
    } finally {
      setRecordsLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  useEffect(() => {
    (async () => {
      try {
        const res = await get('/api/admin/coupons', { page: 1, page_size: 200 });
        const items = (res && (res.items || res.list || res)) as any[];
        const list = (Array.isArray(items) ? items : [])
          .filter((c: any) => String(c.status || '') === 'active' && !c.is_offline)
          .map((c: any) => ({
            label: `${c.name}（剩余 ${Number(c.total_count || 0) - Number(c.claimed_count || 0)} 张）`,
            value: Number(c.id),
          }));
        setAvailableCoupons(list);
      } catch {
        setAvailableCoupons([]);
      }
    })();
  }, []);

  // v3.1 Bug2 修复：动态加载服务类商品（products.fulfillment_type=in_store）
  const loadServiceProducts = async (keyword = '') => {
    try {
      const params: Record<string, unknown> = { page: 1, page_size: 50 };
      if (keyword) params.keyword = keyword;
      const res = await get('/api/admin/products/services', params);
      const items = (res && (res.items || res.list || res)) as any[];
      const list: ServiceProductOption[] = (Array.isArray(items) ? items : []).map((p: any) => ({
        value: Number(p.id),
        label: `${p.name}${p.category_name ? `（${p.category_name}）` : ''}`,
        name: String(p.name || ''),
        image: p.image || undefined,
        category_name: p.category_name || undefined,
        sale_price: p.sale_price,
      }));
      setServiceProducts(list);
    } catch (err: any) {
      setServiceProducts([]);
      message.warning(extractDetail(err, '加载服务商品列表失败'));
    }
  };

  useEffect(() => {
    if (activeTab === 'records') fetchRecords();
  }, [activeTab]);

  const handleSearchGoods = () => fetchData(1, pagination.pageSize);
  const handleSearchRecords = () => fetchRecords(1, recordsPagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: true, stock: 100, category: 'coupon', limit_per_user: 0 });
    setFileList([]);
    setCategory('coupon');
    setRefCouponId(undefined);
    setRefServiceId(undefined);
    setDetailHtml('');
    setModalVisible(true);
  };

  const handleEdit = (record: MallGoods) => {
    setEditingRecord(record);
    const cat = categoryOptions.some(o => o.value === record.category) ? record.category : 'virtual';
    setCategory(cat);
    setRefCouponId(record.refCouponId);
    setRefServiceId(record.refServiceId);
    setDetailHtml(record.detailHtml || '');
    form.setFieldsValue({
      name: record.name,
      category: cat,
      points: record.points,
      stock: record.stock,
      image: record.image,
      description: record.description,
      status: isMallOnShelf(record.status),
      limit_per_user: record.limitPerUser || 0,
    });
    const fl: UploadFile[] = (record.images || []).map((url, idx) => ({
      uid: `-${idx + 1}`,
      name: `image_${idx + 1}`,
      status: 'done',
      url,
    } as UploadFile));
    setFileList(fl);
    if (cat === 'service') {
      // 保证当前编辑的服务商品在下拉里可见
      loadServiceProducts();
    }
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/points/mall/${id}`);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(extractDetail(err, '删除失败'));
    }
  };

  const handleToggleStatus = async (record: MallGoods) => {
    const newStatus = isMallOnShelf(record.status) ? 'inactive' : 'active';
    try {
      await put(`/api/admin/points/mall/${record.id}`, { status: newStatus });
      message.success(isMallOnShelf(newStatus) ? '已上架' : '已下架');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(extractDetail(err));
    }
  };

  const handleBatchStatus = async (status: string) => {
    if (selectedRowKeys.length === 0) { message.warning('请先选择商品'); return; }
    try {
      await put('/api/admin/points/mall/batch-status', { item_ids: selectedRowKeys, status });
      message.success(`批量${status === 'active' ? '上架' : '下架'}成功`);
      setSelectedRowKeys([]);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(extractDetail(err, '批量操作失败'));
    }
  };

  const doUpload = async (file: RcFile): Promise<string> => {
    try {
      const res = await uploadFile('/api/admin/upload', file);
      return (res as any)?.url || (res as any)?.data?.url || '';
    } catch (err: any) {
      message.error(extractDetail(err, '图片上传失败'));
      return '';
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const onShelf = Boolean(values.status);
      const statusStr = onShelf ? 'active' : 'inactive';

      const imageUrls: string[] = [];
      for (const f of fileList) {
        if (f.originFileObj) {
          const u = await doUpload(f.originFileObj as RcFile);
          if (u) imageUrls.push(u);
        } else if (f.url) {
          imageUrls.push(f.url);
        }
      }

      const stockVal = values.category === 'coupon' ? 0
        : values.category === 'service' ? 0
        : Number(values.stock);

      const payload: Record<string, unknown> = {
        name: values.name,
        type: values.category,
        price_points: values.points,
        stock: stockVal,
        description: values.description || '',
        status: statusStr,
        images: imageUrls,
        detail_html: detailHtml || '',
        limit_per_user: Number(values.limit_per_user || 0),
      };
      if (values.category === 'coupon') {
        payload.ref_coupon_id = refCouponId || null;
      } else if (values.category === 'service') {
        payload.ref_service_id = refServiceId || null;
      }

      if (editingRecord) {
        await put(`/api/admin/points/mall/${editingRecord.id}`, payload);
        message.success('编辑成功');
      } else {
        await post('/api/admin/points/mall', payload);
        message.success('新增成功');
      }
      setModalVisible(false);
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      if (err?.errorFields) return;
      // Bug1/Bug2 核心修复：把后端 detail 直接亮出来
      message.error(extractDetail(err));
    }
  };

  const handleExportCSV = () => {
    if (records.length === 0) { message.warning('暂无数据可导出'); return; }
    const header = ['ID', '用户', '商品', '积分', '状态', '时间'];
    const rows = records.map(r => [r.id, r.userName, r.goodsName, r.points, r.status, r.createdAt]);
    const bom = '\uFEFF';
    const csv = bom + [header, ...rows].map(row => row.map(c => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `兑换记录_${dayjs().format('YYYYMMDD_HHmmss')}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const stockColor = (stock: number) => {
    if (stock === 0) return 'red';
    if (stock <= 10) return 'orange';
    return 'green';
  };

  const stockLabel = (stock: number) => {
    if (stock === 0) return '已兑完';
    return String(stock);
  };

  const goodsColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '商品', dataIndex: 'name', key: 'name', width: 200,
      render: (v: string, record: MallGoods) => (
        <Space>
          {record.image
            ? <img src={record.image} alt="" style={{ width: 36, height: 36, objectFit: 'cover', borderRadius: 4 }} />
            : <GiftOutlined style={{ fontSize: 20, color: '#52c41a' }} />}
          {v}
        </Space>
      ),
    },
    {
      title: '分类', dataIndex: 'category', key: 'category', width: 100,
      render: (v: string) => <Tag color="orange">{TYPE_LABELS[v] ?? v}</Tag>,
    },
    {
      title: '所需积分', dataIndex: 'points', key: 'points', width: 100,
      render: (v: number) => <span style={{ color: '#faad14', fontWeight: 600 }}>{v}</span>,
    },
    {
      title: '库存', dataIndex: 'stock', key: 'stock', width: 80,
      render: (v: number) => <Tag color={stockColor(v)}>{stockLabel(v)}</Tag>,
    },
    {
      title: '限兑', dataIndex: 'limitPerUser', key: 'limitPerUser', width: 80,
      render: (v: number) => (v && v > 0 ? `每人${v}次` : '不限'),
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={isMallOnShelf(v) ? 'green' : 'red'}>{isMallOnShelf(v) ? '上架' : '下架'}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 240,
      render: (_: unknown, record: MallGoods) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Popconfirm title={isMallOnShelf(record.status) ? '确定下架？' : '确定上架？'} onConfirm={() => handleToggleStatus(record)}>
            <Button type="link" size="small" icon={isMallOnShelf(record.status) ? <ArrowDownOutlined /> : <ArrowUpOutlined />}>
              {isMallOnShelf(record.status) ? '下架' : '上架'}
            </Button>
          </Popconfirm>
          <Popconfirm title="确定删除该商品？" onConfirm={() => handleDelete(record.id)}>
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const recordColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: '用户', dataIndex: 'userName', key: 'userName', width: 120 },
    { title: '商品', dataIndex: 'goodsName', key: 'goodsName', width: 180 },
    {
      title: '积分', dataIndex: 'points', key: 'points', width: 100,
      render: (v: number) => <span style={{ color: '#faad14', fontWeight: 600 }}>{v}</span>,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (v: string) => {
        const map: Record<string, { color: string; text: string }> = {
          pending: { color: 'orange', text: '待处理' },
          success: { color: 'green', text: '成功' },
          completed: { color: 'green', text: '已完成' },
          shipped: { color: 'blue', text: '已发货' },
          cancelled: { color: 'red', text: '已取消' },
        };
        const c = map[v] || { color: 'default', text: v };
        return <Tag color={c.color}>{c.text}</Tag>;
      },
    },
    {
      title: '兑换时间', dataIndex: 'createdAt', key: 'createdAt', width: 170,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-',
    },
  ];

  const goodsTab = (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Input placeholder="搜索商品名称" prefix={<SearchOutlined />} value={searchText}
            onChange={e => setSearchText(e.target.value)} onPressEnter={handleSearchGoods}
            style={{ width: 220 }} allowClear />
        </Col>
        <Col><Button type="primary" onClick={handleSearchGoods}>搜索</Button></Col>
        <Col flex="auto" />
        {selectedRowKeys.length > 0 && (
          <>
            <Col>
              <Popconfirm title={`批量上架 ${selectedRowKeys.length} 项？`} onConfirm={() => handleBatchStatus('active')}>
                <Button icon={<ArrowUpOutlined />}>批量上架</Button>
              </Popconfirm>
            </Col>
            <Col>
              <Popconfirm title={`批量下架 ${selectedRowKeys.length} 项？`} onConfirm={() => handleBatchStatus('inactive')}>
                <Button danger icon={<ArrowDownOutlined />}>批量下架</Button>
              </Popconfirm>
            </Col>
          </>
        )}
        <Col>
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增商品</Button>
        </Col>
      </Row>

      <Table
        rowSelection={{ selectedRowKeys, onChange: keys => setSelectedRowKeys(keys) }}
        columns={goodsColumns}
        dataSource={goods}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1100 }}
      />
    </div>
  );

  const recordsTab = (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Input placeholder="搜索用户" prefix={<SearchOutlined />} value={recordsKeyword}
            onChange={e => setRecordsKeyword(e.target.value)} onPressEnter={handleSearchRecords}
            style={{ width: 200 }} allowClear />
        </Col>
        <Col>
          <RangePicker value={recordsDateRange as any} onChange={vals => setRecordsDateRange(vals as any)} />
        </Col>
        <Col><Button type="primary" onClick={handleSearchRecords}>搜索</Button></Col>
        <Col flex="auto" />
        <Col><Button icon={<DownloadOutlined />} onClick={handleExportCSV}>导出CSV</Button></Col>
      </Row>

      <Table
        columns={recordColumns}
        dataSource={records}
        rowKey="id"
        loading={recordsLoading}
        pagination={{
          ...recordsPagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchRecords(page, pageSize),
        }}
        scroll={{ x: 800 }}
      />
    </div>
  );

  return (
    <div>
      <Title level={4} style={{ marginBottom: 16 }}>积分商城管理</Title>

      <Tabs
        activeKey={activeTab}
        onChange={key => setActiveTab(key)}
        items={[
          { key: 'goods', label: '商品管理', children: goodsTab },
          { key: 'records', label: '兑换记录', children: recordsTab },
        ]}
      />

      <Modal
        title={editingRecord ? '编辑商品' : '新增商品'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={720}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="商品名称" name="name" rules={[{ required: true, message: '请输入商品名称' }]}>
            <Input placeholder="请输入商品名称" />
          </Form.Item>
          <Form.Item label="商品分类" name="category" rules={[{ required: true, message: '请选择分类' }]}>
            <Select
              options={categoryOptions}
              placeholder="请选择分类"
              onChange={(v) => {
                const c = String(v);
                setCategory(c);
                if (c === 'service' && serviceProducts.length === 0) {
                  loadServiceProducts();
                }
              }}
            />
          </Form.Item>

          {category === 'coupon' && (
            <Form.Item label="关联优惠券" required help="选择已上架且未兑完的券；库存跟随券本体">
              <Select
                value={refCouponId}
                onChange={(v) => setRefCouponId(v as number)}
                options={availableCoupons}
                placeholder="请选择优惠券"
                showSearch
                optionFilterProp="label"
              />
            </Form.Item>
          )}

          {category === 'service' && (
            <Form.Item
              label="关联服务商品"
              required
              help="拉取商品库（products.fulfillment_type=in_store）。兑换后自动生成抵扣券"
            >
              <Select
                value={refServiceId}
                onChange={(v) => {
                  const sid = v as number;
                  setRefServiceId(sid);
                  const p = serviceProducts.find((x) => x.value === sid);
                  if (p) {
                    // 自动带出商品名
                    const cur = form.getFieldValue('name');
                    if (!cur) {
                      form.setFieldsValue({ name: p.name });
                    }
                  }
                }}
                options={serviceProducts}
                placeholder="请选择服务商品"
                showSearch
                filterOption={(input, option) =>
                  (option?.label as string)?.toLowerCase().includes(input.toLowerCase())
                }
                onSearch={(kw) => {
                  if (serviceSearchTimer.current) clearTimeout(serviceSearchTimer.current);
                  serviceSearchTimer.current = setTimeout(() => {
                    loadServiceProducts(kw);
                  }, 300);
                }}
                onFocus={() => {
                  if (serviceProducts.length === 0) loadServiceProducts();
                }}
              />
            </Form.Item>
          )}

          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="所需积分" name="points" rules={[{ required: true, message: '请输入积分' }]} style={{ flex: 1 }}>
              <InputNumber min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              label="库存"
              name="stock"
              rules={category === 'physical' ? [{ required: true, message: '请输入库存' }] : []}
              style={{ flex: 1 }}
              help={category === 'coupon' ? '跟随券本体' : category === 'service' ? '由服务本体管控' : ''}
            >
              <InputNumber min={0} style={{ width: '100%' }} disabled={category !== 'physical'} />
            </Form.Item>
            <Form.Item
              label="每人限兑次数"
              name="limit_per_user"
              style={{ flex: 1 }}
              help="0 = 不限"
            >
              <InputNumber min={0} style={{ width: '100%' }} />
            </Form.Item>
          </Space>

          <Form.Item label="商品图片（支持多图，首图为封面）" name="image">
            <Upload
              listType="picture-card"
              multiple
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList: fl }) => setFileList(fl)}
              onRemove={(file) => { setFileList(prev => prev.filter(x => x.uid !== file.uid)); }}
            >
              {fileList.length < 6 && (
                <div><UploadOutlined /><div style={{ marginTop: 8 }}>上传图片</div></div>
              )}
            </Upload>
          </Form.Item>

          <Form.Item label="商品简介" name="description">
            <TextArea rows={2} placeholder="一行简介，用于列表页展示" />
          </Form.Item>

          <Form.Item label="富文本详情 (detail_html)" help="支持 HTML；在商品详情页展示。建议图文混排">
            <TextArea
              rows={6}
              value={detailHtml}
              onChange={(e) => setDetailHtml(e.target.value)}
              placeholder='直接粘贴 HTML，例如：<p>适用场景</p><img src="https://..." />'
            />
          </Form.Item>

          <Form.Item label="上架" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
