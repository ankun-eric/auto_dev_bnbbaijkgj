'use client';

import React, { useEffect, useRef, useState } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, Tag, message,
  Typography, Popconfirm, Tabs, DatePicker, Row, Col, Tooltip, Alert,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, UploadOutlined, GiftOutlined,
  ArrowUpOutlined, ArrowDownOutlined, SearchOutlined, DownloadOutlined,
  CopyOutlined, HistoryOutlined, LockOutlined,
} from '@ant-design/icons';
import { get, post, put, del, upload as uploadFile } from '@/lib/api';
import { resolveAssetUrl } from '@/lib/asset-url';
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
  goodsStatus: string; // draft/on_sale/off_sale
  image: string;
  description: string;
  detailHtml: string;
  refCouponId?: number;
  refServiceId?: number;
  limitPerUser: number;
  sortWeight: number;
  replacedByGoodsId?: number;
  copiedFromGoodsId?: number;
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

interface ChangeLog {
  id: number;
  fieldKey: string;
  fieldName: string;
  oldValue: string;
  newValue: string;
  operatorName: string;
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

interface CouponOption {
  label: string;
  value: number;
  totalCount: number;
  available: number;
}

const TYPE_LABELS: Record<string, string> = {
  coupon: '优惠券',
  virtual: '虚拟商品',
  physical: '实物商品',
  service: '体验服务',
  third_party: '第三方商品',
};

const GOODS_STATUS_LABELS: Record<string, { text: string; color: string }> = {
  draft: { text: '草稿', color: 'default' },
  on_sale: { text: '在售', color: 'green' },
  off_sale: { text: '已下架', color: 'red' },
};

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
    goodsStatus: String(raw.goods_status ?? 'draft'),
    image: firstImage(raw.images),
    images: allImages(raw.images),
    description: String(raw.description ?? ''),
    detailHtml: String(raw.detail_html ?? ''),
    refCouponId: raw.ref_coupon_id ? Number(raw.ref_coupon_id) : undefined,
    refServiceId: raw.ref_service_id ? Number(raw.ref_service_id) : undefined,
    limitPerUser: Number(raw.limit_per_user ?? 0),
    sortWeight: Number(raw.sort_weight ?? 0),
    replacedByGoodsId: raw.replaced_by_goods_id ? Number(raw.replaced_by_goods_id) : undefined,
    copiedFromGoodsId: raw.copied_from_goods_id ? Number(raw.copied_from_goods_id) : undefined,
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
  const [statusFilter, setStatusFilter] = useState<string>('not_off_sale'); // 默认隐藏已下架
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [form] = Form.useForm();

  const [availableCoupons, setAvailableCoupons] = useState<CouponOption[]>([]);
  const [serviceProducts, setServiceProducts] = useState<ServiceProductOption[]>([]);
  const serviceSearchTimer = useRef<any>(null);

  const [category, setCategory] = useState<string>('coupon');
  const [refCouponId, setRefCouponId] = useState<number | undefined>();
  const [refServiceId, setRefServiceId] = useState<number | undefined>();
  const [detailHtml, setDetailHtml] = useState<string>('');
  const [stockWarn, setStockWarn] = useState<string>('');

  const [records, setRecords] = useState<ExchangeRecord[]>([]);
  const [recordsLoading, setRecordsLoading] = useState(false);
  const [recordsPagination, setRecordsPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [recordsKeyword, setRecordsKeyword] = useState('');
  const [recordsDateRange, setRecordsDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);

  // 修改历史
  const [historyVisible, setHistoryVisible] = useState(false);
  const [historyGoods, setHistoryGoods] = useState<MallGoods | null>(null);
  const [historyLogs, setHistoryLogs] = useState<ChangeLog[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [historyFieldFilter, setHistoryFieldFilter] = useState<string>('all');

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (searchText) params.keyword = searchText;
      if (statusFilter === 'draft') params.goods_status = 'draft';
      else if (statusFilter === 'on_sale') params.goods_status = 'on_sale';
      else if (statusFilter === 'off_sale') params.goods_status = 'off_sale';
      else if (statusFilter === 'all') params.goods_status = 'all';
      // 默认：不传 goods_status，后端默认隐藏 off_sale
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

  useEffect(() => { fetchData(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [statusFilter]);

  useEffect(() => {
    (async () => {
      try {
        const res = await get('/api/admin/coupons', { page: 1, page_size: 200 });
        const items = (res && (res.items || res.list || res)) as any[];
        const list: CouponOption[] = (Array.isArray(items) ? items : [])
          .filter((c: any) => String(c.status || '') === 'active' && !c.is_offline)
          .map((c: any) => ({
            label: `${c.name}（剩余 ${Number(c.total_count || 0) - Number(c.claimed_count || 0)} 张）`,
            value: Number(c.id),
            totalCount: Number(c.total_count || 0),
            available: Number(c.total_count || 0) - Number(c.claimed_count || 0),
          }));
        setAvailableCoupons(list);
      } catch {
        setAvailableCoupons([]);
      }
    })();
  }, []);

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
  }, [activeTab]); // eslint-disable-line

  const handleSearchGoods = () => fetchData(1, pagination.pageSize);
  const handleSearchRecords = () => fetchRecords(1, recordsPagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: true, stock: 100, category: 'coupon', limit_per_user: 0, sort_weight: 0 });
    setFileList([]);
    setCategory('coupon');
    setRefCouponId(undefined);
    setRefServiceId(undefined);
    setDetailHtml('');
    setStockWarn('');
    setModalVisible(true);
  };

  const handleEdit = (record: MallGoods) => {
    setEditingRecord(record);
    const cat = categoryOptions.some(o => o.value === record.category) ? record.category : 'virtual';
    setCategory(cat);
    setRefCouponId(record.refCouponId);
    setRefServiceId(record.refServiceId);
    setDetailHtml(record.detailHtml || '');
    setStockWarn('');
    form.setFieldsValue({
      name: record.name,
      category: cat,
      points: record.points,
      stock: record.stock,
      image: record.image,
      description: record.description,
      status: record.goodsStatus === 'on_sale',
      limit_per_user: record.limitPerUser || 0,
      sort_weight: record.sortWeight || 0,
    });
    const fl: UploadFile[] = (record.images || []).map((url, idx) => ({
      uid: `-${idx + 1}`,
      name: `image_${idx + 1}`,
      status: 'done',
      url,
    } as UploadFile));
    setFileList(fl);
    if (cat === 'service') {
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

  const handlePublish = async (record: MallGoods) => {
    try {
      await post(`/api/admin/points/mall/${record.id}/publish`, {});
      message.success('已发布上架');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(extractDetail(err, '发布失败'));
    }
  };

  const handleOffline = async (record: MallGoods) => {
    try {
      await post(`/api/admin/points/mall/${record.id}/offline`, {});
      message.success('已下架');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(extractDetail(err, '下架失败'));
    }
  };

  const handleDuplicate = async (record: MallGoods) => {
    try {
      const res: any = await post(`/api/admin/points/mall/${record.id}/duplicate`, {});
      message.success('已生成副本草稿');
      fetchData(pagination.current, pagination.pageSize);
      // 直接打开新副本编辑
      if (res?.id) {
        const copied = mapMallItemFromApi(res);
        setTimeout(() => handleEdit(copied), 300);
      }
    } catch (err: any) {
      message.error(extractDetail(err, '复制失败'));
    }
  };

  const handleShowHistory = async (record: MallGoods) => {
    setHistoryGoods(record);
    setHistoryVisible(true);
    setHistoryLoading(true);
    setHistoryFieldFilter('all');
    try {
      const res: any = await get(`/api/admin/points/mall/${record.id}/change-logs`, { page: 1, page_size: 200 });
      const items = res?.items || [];
      setHistoryLogs(items.map((r: any) => ({
        id: r.id,
        fieldKey: r.field_key,
        fieldName: r.field_name,
        oldValue: r.old_value || '',
        newValue: r.new_value || '',
        operatorName: r.operator_name || '未知',
        createdAt: r.created_at,
      })));
    } catch (err: any) {
      setHistoryLogs([]);
      message.error(extractDetail(err, '加载修改历史失败'));
    } finally {
      setHistoryLoading(false);
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

  const checkStockWarn = (stockVal: number) => {
    if (category !== 'coupon' || !refCouponId) {
      setStockWarn('');
      return;
    }
    const coupon = availableCoupons.find(c => c.value === refCouponId);
    if (!coupon) return;
    if (stockVal > coupon.totalCount) {
      setStockWarn(`⚠️ 当前填写 ${stockVal}，优惠券总量仅 ${coupon.totalCount}，超出 ${stockVal - coupon.totalCount} 张，兑换时可能因券不足而失败。`);
    } else {
      setStockWarn('');
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const onShelf = Boolean(values.status);
      const goodsStatus = onShelf ? 'on_sale' : (editingRecord ? editingRecord.goodsStatus : 'draft');
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

      const stockVal = Number(values.stock ?? 0);

      // 优惠券库存防呆二次确认
      if (category === 'coupon' && refCouponId) {
        const coupon = availableCoupons.find(c => c.value === refCouponId);
        if (coupon && stockVal > coupon.totalCount) {
          const confirmed = await new Promise<boolean>((resolve) => {
            Modal.confirm({
              title: '库存超过优惠券总量',
              content: `您填写的库存 ${stockVal} 超过优惠券总量 ${coupon.totalCount}，超出部分在兑换时会失败。确认要超量配置吗？`,
              okText: '确认超量保存',
              cancelText: '取消',
              onOk: () => resolve(true),
              onCancel: () => resolve(false),
            });
          });
          if (!confirmed) return;
        }
      }

      const payload: Record<string, unknown> = {
        name: values.name,
        type: values.category,
        price_points: values.points,
        stock: stockVal,
        description: values.description || '',
        status: statusStr,
        goods_status: goodsStatus,
        images: imageUrls,
        detail_html: detailHtml || '',
        limit_per_user: Number(values.limit_per_user || 0),
        sort_weight: Number(values.sort_weight || 0),
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

  const isOnSale = (record: MallGoods) => record.goodsStatus === 'on_sale';

  const goodsColumns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '商品', dataIndex: 'name', key: 'name', width: 200,
      render: (v: string, record: MallGoods) => (
        <Space>
          {record.image
            ? <img src={resolveAssetUrl(record.image)} alt="" style={{ width: 36, height: 36, objectFit: 'cover', borderRadius: 4 }} />
            : <GiftOutlined style={{ fontSize: 20, color: '#52c41a' }} />}
          <span>
            {v}
            {record.replacedByGoodsId && (
              <Tag color="purple" style={{ marginLeft: 4 }}>已被替代</Tag>
            )}
            {record.copiedFromGoodsId && (
              <Tag color="blue" style={{ marginLeft: 4 }}>副本</Tag>
            )}
          </span>
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
      title: '状态', dataIndex: 'goodsStatus', key: 'goodsStatus', width: 90,
      render: (v: string) => {
        const s = GOODS_STATUS_LABELS[v] || { text: v, color: 'default' };
        return <Tag color={s.color}>{s.text}</Tag>;
      },
    },
    {
      title: '操作', key: 'action', width: 360, fixed: 'right' as const,
      render: (_: unknown, record: MallGoods) => (
        <Space size={0} wrap>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          {record.goodsStatus === 'draft' && (
            <Popconfirm title="确定发布上架？" onConfirm={() => handlePublish(record)}>
              <Button type="link" size="small" icon={<ArrowUpOutlined />}>发布</Button>
            </Popconfirm>
          )}
          {record.goodsStatus === 'on_sale' && (
            <Popconfirm title="确定下架？下架后用户将不可见" onConfirm={() => handleOffline(record)}>
              <Button type="link" size="small" icon={<ArrowDownOutlined />}>下架</Button>
            </Popconfirm>
          )}
          {record.goodsStatus === 'off_sale' && (
            <Popconfirm title="重新上架该商品？" onConfirm={() => handlePublish(record)}>
              <Button type="link" size="small" icon={<ArrowUpOutlined />}>重新上架</Button>
            </Popconfirm>
          )}
          <Popconfirm title="复制为新草稿？锁定字段可在副本中修改" onConfirm={() => handleDuplicate(record)}>
            <Button type="link" size="small" icon={<CopyOutlined />}>复制新建</Button>
          </Popconfirm>
          <Button type="link" size="small" icon={<HistoryOutlined />} onClick={() => handleShowHistory(record)}>历史</Button>
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

  const currentIsOnSale = editingRecord ? isOnSale(editingRecord) : false;
  const lockTip = '商品在售中，此字段不可修改。如需修改，请先【下架商品】或使用【复制新建】。';

  const goodsTab = (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Input placeholder="搜索商品名称" prefix={<SearchOutlined />} value={searchText}
            onChange={e => setSearchText(e.target.value)} onPressEnter={handleSearchGoods}
            style={{ width: 220 }} allowClear />
        </Col>
        <Col>
          <Select
            value={statusFilter}
            onChange={setStatusFilter}
            style={{ width: 160 }}
            options={[
              { label: '全部（含已下架）', value: 'all' },
              { label: '默认（含草稿+在售）', value: 'not_off_sale' },
              { label: '仅草稿', value: 'draft' },
              { label: '仅在售', value: 'on_sale' },
              { label: '仅已下架', value: 'off_sale' },
            ]}
          />
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
        scroll={{ x: 1200 }}
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

  // 历史筛选
  const filteredLogs = historyFieldFilter === 'all'
    ? historyLogs
    : historyLogs.filter(l => l.fieldKey === historyFieldFilter);

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
        title={
          <Space>
            <span>{editingRecord ? '编辑商品' : '新增商品'}</span>
            {editingRecord && (
              <Tag color={GOODS_STATUS_LABELS[editingRecord.goodsStatus]?.color || 'default'}>
                {GOODS_STATUS_LABELS[editingRecord.goodsStatus]?.text || editingRecord.goodsStatus}
              </Tag>
            )}
          </Space>
        }
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={760}
        destroyOnClose
      >
        {currentIsOnSale && (
          <Alert
            message="商品在售中，部分关键字段已锁定不可修改"
            description="如需修改已锁定字段，请先【下架商品】或使用【复制新建】功能。"
            type="warning"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="商品名称" name="name" rules={[{ required: true, message: '请输入商品名称' }]}>
            <Input placeholder="请输入商品名称" />
          </Form.Item>
          <Form.Item
            label={<Space>商品分类 {currentIsOnSale && <Tooltip title={lockTip}><LockOutlined style={{ color: '#faad14' }} /></Tooltip>}</Space>}
            name="category"
            rules={[{ required: true, message: '请选择分类' }]}
          >
            <Select
              disabled={currentIsOnSale}
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
            <Form.Item
              label={
                <Space>
                  关联优惠券
                  {currentIsOnSale && <Tooltip title={lockTip}><LockOutlined style={{ color: '#faad14' }} /></Tooltip>}
                </Space>
              }
              required
              help="选择已上架且未兑完的券"
            >
              <Select
                disabled={currentIsOnSale}
                value={refCouponId}
                onChange={(v) => {
                  setRefCouponId(v as number);
                  const s = form.getFieldValue('stock');
                  if (s) checkStockWarn(Number(s));
                }}
                options={availableCoupons.map(c => ({ label: c.label, value: c.value }))}
                placeholder="请选择优惠券"
                showSearch
                optionFilterProp="label"
              />
              {refCouponId && (
                <div style={{ color: '#1890ff', fontSize: 12, marginTop: 4 }}>
                  📎 当前关联优惠券总量：{availableCoupons.find(c => c.value === refCouponId)?.totalCount || 0} 张（仅供参考，实际库存以下方填写为准）
                </div>
              )}
            </Form.Item>
          )}

          {category === 'service' && (
            <Form.Item
              label={
                <Space>
                  关联服务商品
                  {currentIsOnSale && <Tooltip title={lockTip}><LockOutlined style={{ color: '#faad14' }} /></Tooltip>}
                </Space>
              }
              required
              help="拉取商品库（products.fulfillment_type=in_store）。兑换后自动生成抵扣券"
            >
              <Select
                disabled={currentIsOnSale}
                value={refServiceId}
                onChange={(v) => {
                  const sid = v as number;
                  setRefServiceId(sid);
                  const p = serviceProducts.find((x) => x.value === sid);
                  if (p) {
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
            <Form.Item
              label={<Space>所需积分 {currentIsOnSale && <Tooltip title={lockTip}><LockOutlined style={{ color: '#faad14' }} /></Tooltip>}</Space>}
              name="points"
              rules={[{ required: true, message: '请输入积分' }]}
              style={{ flex: 1 }}
            >
              <InputNumber disabled={currentIsOnSale} min={1} style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item
              label="库存"
              name="stock"
              style={{ flex: 1 }}
              help={category === 'coupon' ? '可超量，兑换时若券不足会失败' : category === 'service' ? '0 表示不限' : '只能增加，不能低于已兑换数'}
            >
              <InputNumber
                min={0}
                style={{ width: '100%' }}
                onChange={(v) => checkStockWarn(Number(v || 0))}
              />
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
          {stockWarn && (
            <div style={{ color: '#faad14', fontSize: 12, marginTop: -12, marginBottom: 12 }}>{stockWarn}</div>
          )}

          <Form.Item label="排序权重" name="sort_weight" help="越大越靠前，默认 0">
            <InputNumber min={0} style={{ width: 200 }} />
          </Form.Item>

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

          <Form.Item label="富文本详情 (detail_html)" help="支持 HTML；在商品详情页展示。可直接粘贴图文模板。建议 ≤50KB">
            <TextArea
              rows={8}
              value={detailHtml}
              onChange={(e) => setDetailHtml(e.target.value)}
              placeholder='直接粘贴 HTML，例如：<p>适用场景</p><img src="https://..." />'
              maxLength={50000}
              showCount
            />
            <div style={{ marginTop: 8 }}>
              <Space wrap>
                <span style={{ color: '#666', fontSize: 12 }}>模板库（点击插入到末尾）：</span>
                <Button size="small" onClick={() => setDetailHtml(d => d + `\n<div style="padding:12px;background:#f6ffed;border-left:3px solid #52c41a;margin:8px 0;"><strong>✨ 商品亮点</strong><ul><li>亮点一</li><li>亮点二</li><li>亮点三</li></ul></div>`)}>T1 亮点卡</Button>
                <Button size="small" onClick={() => setDetailHtml(d => d + `\n<div style="padding:12px;background:#e6f7ff;border-left:3px solid #1890ff;margin:8px 0;"><strong>🧭 使用步骤</strong><ol><li>第 1 步：…</li><li>第 2 步：…</li><li>第 3 步：…</li><li>第 4 步：…</li></ol></div>`)}>T2 使用说明卡</Button>
                <Button size="small" onClick={() => setDetailHtml(d => d + `\n<div style="padding:12px;background:#fff7e6;border-left:3px solid #fa8c16;margin:8px 0;"><strong>⏰ 有效期</strong><p>自领取后 <b>30</b> 天内有效，请尽快使用。</p></div>`)}>T3 有效期卡</Button>
                <Button size="small" onClick={() => setDetailHtml(d => d + `\n<div style="padding:12px;background:#fffbe6;border-left:3px solid #faad14;margin:8px 0;"><strong>⚠️ 注意事项</strong><ul><li>请核对姓名与手机号</li><li>不与其他优惠叠加</li><li>最终解释权归商家所有</li></ul></div>`)}>T4 注意事项卡</Button>
              </Space>
            </div>
          </Form.Item>

          <Form.Item label="上架（打开=上架/关闭=下架）" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* 修改历史弹窗 */}
      <Modal
        title={<Space><HistoryOutlined /> 修改历史 {historyGoods && `— ${historyGoods.name}`}</Space>}
        open={historyVisible}
        onCancel={() => setHistoryVisible(false)}
        footer={null}
        width={820}
      >
        <div style={{ marginBottom: 12 }}>
          <Space>
            <span>按字段筛选：</span>
            <Select
              value={historyFieldFilter}
              onChange={setHistoryFieldFilter}
              style={{ width: 160 }}
              options={[
                { label: '全部', value: 'all' },
                { label: '商品标题', value: 'name' },
                { label: '主图/轮播图', value: 'images' },
                { label: '被替代', value: 'replaced_by' },
              ]}
            />
          </Space>
        </div>
        <Table
          dataSource={filteredLogs}
          rowKey="id"
          loading={historyLoading}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: '时间', dataIndex: 'createdAt', width: 160, render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            { title: '操作人', dataIndex: 'operatorName', width: 100 },
            { title: '字段', dataIndex: 'fieldName', width: 120 },
            {
              title: '修改前',
              dataIndex: 'oldValue',
              width: 180,
              render: (v: string, r: ChangeLog) => {
                if (r.fieldKey === 'images') {
                  try {
                    const arr = JSON.parse(v || '[]');
                    if (Array.isArray(arr) && arr[0]) {
                      return <img src={resolveAssetUrl(arr[0])} alt="" style={{ width: 48, height: 48, objectFit: 'cover' }} />;
                    }
                  } catch {}
                }
                return <span style={{ wordBreak: 'break-all' }}>{v || '-'}</span>;
              },
            },
            {
              title: '修改后',
              dataIndex: 'newValue',
              width: 180,
              render: (v: string, r: ChangeLog) => {
                if (r.fieldKey === 'images') {
                  try {
                    const arr = JSON.parse(v || '[]');
                    if (Array.isArray(arr) && arr[0]) {
                      return <img src={resolveAssetUrl(arr[0])} alt="" style={{ width: 48, height: 48, objectFit: 'cover' }} />;
                    }
                  } catch {}
                }
                return <span style={{ wordBreak: 'break-all' }}>{v || '-'}</span>;
              },
            },
          ]}
        />
      </Modal>
    </div>
  );
}
