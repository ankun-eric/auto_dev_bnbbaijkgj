'use client';

import React, { useEffect, useState } from 'react';
import {
  Table, Button, Space, Modal, Form, Input, InputNumber, Select, Switch, Upload, Tag, message,
  Typography, Popconfirm, Tabs, DatePicker, Row, Col, Card, Statistic,
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

const TYPE_LABELS: Record<string, string> = {
  coupon: '优惠券',
  virtual: '虚拟商品',
  physical: '实物商品',
  service: '体验服务',
  third_party: '第三方商品',
};

// v3: 虚拟商品 & 第三方商品 置灰 "开发中"
const categoryOptions = [
  { label: '优惠券', value: 'coupon' },
  { label: '体验服务', value: 'service' },
  { label: '实物商品', value: 'physical' },
  { label: '虚拟商品（开发中）', value: 'virtual', disabled: true },
  { label: '第三方商品（开发中）', value: 'third_party', disabled: true },
];

const serviceTypeOptions = [
  { label: '专家问诊', value: 'expert' },
  { label: '体检服务', value: 'physical_exam' },
  { label: 'TCM调理', value: 'tcm' },
  { label: '健康计划体验', value: 'health_plan' },
];

function firstImage(images: unknown): string {
  if (Array.isArray(images) && images.length > 0) return String(images[0]);
  if (typeof images === 'string') return images;
  return '';
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
    description: String(raw.description ?? ''),
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
  const [category, setCategory] = useState<string>('coupon');
  const [refCouponId, setRefCouponId] = useState<number | undefined>();
  const [refServiceType, setRefServiceType] = useState<string | undefined>();
  const [refServiceId, setRefServiceId] = useState<number | undefined>();

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
    } catch {
      setGoods([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
      message.error('加载商品失败');
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
    } catch {
      setRecords([]);
      setRecordsPagination(prev => ({ ...prev, current: page, total: 0 }));
    } finally {
      setRecordsLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  // 加载可选优惠券（仅 active 且未兑完）
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

  useEffect(() => {
    if (activeTab === 'records') fetchRecords();
  }, [activeTab]);

  const handleSearchGoods = () => fetchData(1, pagination.pageSize);
  const handleSearchRecords = () => fetchRecords(1, recordsPagination.pageSize);

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: true, stock: 100, category: 'coupon' });
    setFileList([]);
    setCategory('coupon');
    setRefCouponId(undefined);
    setRefServiceType(undefined);
    setRefServiceId(undefined);
    setModalVisible(true);
  };

  const parseRefFromDescription = (desc: string) => {
    const out: { refCouponId?: number; refServiceType?: string; refServiceId?: number; display: string } = { display: '' };
    const parts = String(desc || '').split(';').map((s) => s.trim()).filter(Boolean);
    const displayParts: string[] = [];
    for (const seg of parts) {
      if (seg.startsWith('ref_coupon_id=')) {
        out.refCouponId = Number(seg.split('=')[1]) || undefined;
      } else if (seg.startsWith('ref_service_type=')) {
        out.refServiceType = seg.split('=')[1];
      } else if (seg.startsWith('ref_service_id=')) {
        out.refServiceId = Number(seg.split('=')[1]) || undefined;
      } else {
        displayParts.push(seg);
      }
    }
    out.display = displayParts.join('; ');
    return out;
  };

  const handleEdit = (record: MallGoods) => {
    setEditingRecord(record);
    const parsed = parseRefFromDescription(record.description || '');
    const cat = categoryOptions.some(o => o.value === record.category) ? record.category : 'virtual';
    setCategory(cat);
    setRefCouponId(parsed.refCouponId);
    setRefServiceType(parsed.refServiceType);
    setRefServiceId(parsed.refServiceId);
    form.setFieldsValue({
      name: record.name,
      category: cat,
      points: record.points,
      stock: record.stock,
      image: record.image,
      description: parsed.display,
      status: isMallOnShelf(record.status),
    });
    setFileList(record.image ? [{ uid: '-1', name: 'cover', status: 'done', url: record.image }] : []);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await del(`/api/admin/points/mall/${id}`);
      message.success('删除成功');
      fetchData(pagination.current, pagination.pageSize);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '删除失败');
    }
  };

  const handleToggleStatus = async (record: MallGoods) => {
    const newStatus = isMallOnShelf(record.status) ? 'inactive' : 'active';
    try {
      await put(`/api/admin/points/mall/${record.id}`, { status: newStatus });
      message.success(isMallOnShelf(newStatus) ? '已上架' : '已下架');
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('操作失败');
    }
  };

  const handleBatchStatus = async (status: string) => {
    if (selectedRowKeys.length === 0) { message.warning('请先选择商品'); return; }
    try {
      await put('/api/admin/points/mall/batch-status', { item_ids: selectedRowKeys, status });
      message.success(`批量${status === 'active' ? '上架' : '下架'}成功`);
      setSelectedRowKeys([]);
      fetchData(pagination.current, pagination.pageSize);
    } catch {
      message.error('批量操作失败');
    }
  };

  const doUpload = async (file: RcFile): Promise<string> => {
    try {
      const res = await uploadFile('/api/admin/upload', file);
      return (res as any)?.url || (res as any)?.data?.url || '';
    } catch {
      message.error('图片上传失败');
      return '';
    }
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const onShelf = Boolean(values.status);
      const statusStr = onShelf ? 'active' : 'inactive';

      let imageUrl = values.image || '';
      if (fileList.length > 0 && fileList[0].originFileObj) {
        imageUrl = await doUpload(fileList[0].originFileObj as RcFile);
        if (!imageUrl) return;
      } else if (fileList.length > 0 && fileList[0].url) {
        imageUrl = fileList[0].url;
      }

      // 组装 description：把 ref_* 元信息嵌入（与后端 points_exchange.py 解析规则一致）
      const descSegs: string[] = [];
      if (values.category === 'coupon' && refCouponId) {
        descSegs.push(`ref_coupon_id=${refCouponId}`);
      }
      if (values.category === 'service') {
        if (refServiceType) descSegs.push(`ref_service_type=${refServiceType}`);
        if (refServiceId) descSegs.push(`ref_service_id=${refServiceId}`);
      }
      if (values.description) descSegs.push(String(values.description));
      const finalDesc = descSegs.join(';');

      // 券类型：库存字段由券的 total_count-claimed_count 决定，前端传 0 占位
      const stockVal = values.category === 'coupon' ? 0
        : values.category === 'service' ? 0
        : Number(values.stock);

      const payload = {
        name: values.name,
        type: values.category,
        price_points: values.points,
        stock: stockVal,
        description: finalDesc,
        status: statusStr,
        images: imageUrl ? [imageUrl] : [],
      };

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
      message.error(err?.response?.data?.detail || '操作失败');
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
      title: '已兑换', dataIndex: 'exchangeCount', key: 'exchangeCount', width: 80,
      render: (v: number) => v ?? 0,
    },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 80,
      render: (v: string) => <Tag color={isMallOnShelf(v) ? 'green' : 'red'}>{isMallOnShelf(v) ? '上架' : '下架'}</Tag>,
    },
    {
      title: '操作', key: 'action', width: 200,
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
        scroll={{ x: 1000 }}
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
        width={600}
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
              onChange={(v) => setCategory(String(v))}
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
            <Space style={{ width: '100%' }} size={12}>
              <Form.Item label="服务类型" required style={{ flex: 1 }}>
                <Select
                  value={refServiceType}
                  onChange={(v) => setRefServiceType(v as string)}
                  options={serviceTypeOptions}
                  placeholder="选择服务类型"
                />
              </Form.Item>
              <Form.Item label="关联服务ID" required style={{ flex: 1 }}>
                <InputNumber
                  value={refServiceId}
                  onChange={(v) => setRefServiceId((v as number) ?? undefined)}
                  min={1}
                  style={{ width: '100%' }}
                  placeholder="输入对应服务ID"
                />
              </Form.Item>
            </Space>
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
          </Space>
          <Form.Item label="商品图片" name="image">
            <div>
              <Upload
                listType="picture-card"
                maxCount={1}
                fileList={fileList}
                beforeUpload={() => false}
                onChange={({ fileList: fl }) => setFileList(fl)}
                onRemove={() => { setFileList([]); form.setFieldsValue({ image: '' }); }}
              >
                {fileList.length === 0 && (
                  <div><UploadOutlined /><div style={{ marginTop: 8 }}>上传图片</div></div>
                )}
              </Upload>
            </div>
          </Form.Item>
          <Form.Item label="商品描述" name="description">
            <TextArea rows={3} placeholder="请输入商品描述" />
          </Form.Item>
          <Form.Item label="上架" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
