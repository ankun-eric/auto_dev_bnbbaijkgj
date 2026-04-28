'use client';

import React, { useEffect, useMemo, useState, useCallback } from 'react';
import {
  Button,
  Card,
  DatePicker,
  Descriptions,
  Divider,
  Form,
  Image as AntImage,
  Input,
  InputNumber,
  Modal,
  Row,
  Col,
  Select,
  Space,
  Table,
  Tag,
  Tooltip,
  Typography,
  Upload,
  message,
} from 'antd';
import type { ColumnsType, TablePaginationConfig } from 'antd/es/table';
import type { SorterResult } from 'antd/es/table/interface';
import type { UploadFile } from 'antd/es/upload/interface';
import {
  CloudUploadOutlined,
  DownOutlined,
  EyeOutlined,
  FilePdfOutlined,
  PlusOutlined,
  ReloadOutlined,
  UpOutlined,
} from '@ant-design/icons';
import { get, post, upload as apiUpload } from '@/lib/api';
import dayjs, { Dayjs } from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { RangePicker } = DatePicker;

interface MerchantBrief { id: number; name: string; }
interface StoreBrief { id: number; name: string; merchant_profile_id?: number | null; }

interface SettlementRow {
  id: number;
  statement_no: string;
  merchant_profile_id: number;
  merchant_name?: string | null;
  store_id?: number | null;
  store_name?: string | null;
  display_name?: string | null;
  dim: 'merchant' | 'store';
  period_start: string;
  period_end: string;
  order_count: number;
  total_amount: number;
  settlement_amount: number;
  status: 'pending' | 'confirmed' | 'settled' | 'dispute' | string;
  generated_at?: string | null;
  settled_at?: string | null;
  has_proof: boolean;
}

interface SettlementListResp {
  total: number;
  items: SettlementRow[];
  page: number;
  page_size: number;
}

interface ProofDetail {
  voucher_type?: 'image' | 'pdf' | string | null;
  voucher_files: string[];
  amount: number;
  paid_at?: string | null;
  remark?: string | null;
  uploaded_by?: number | null;
  uploaded_by_name?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface DetailLine {
  order_no?: string | null;
  biz_type?: string | null;
  happened_at?: string | null;
  amount: number;
  remark?: string | null;
}

interface DetailResp {
  info: SettlementRow;
  lines: DetailLine[];
  lines_total_amount: number;
  proof?: ProofDetail | null;
}

const STATUS_META: Record<string, { label: string; color: string }> = {
  pending: { label: '未结清', color: 'default' },
  confirmed: { label: '未结清', color: 'default' },
  dispute: { label: '争议中', color: 'error' },
  settled: { label: '已结清', color: 'success' },
};

function renderStatus(status: string) {
  const m = STATUS_META[status] || { label: status, color: 'default' };
  return <Tag color={m.color}>{m.label}</Tag>;
}

function renderDim(dim: string) {
  return dim === 'store'
    ? <Tag color="blue">门店维度</Tag>
    : <Tag color="purple">机构维度</Tag>;
}

function fmtAmount(n: number | null | undefined): string {
  const v = Number(n || 0);
  return String(v);
}

function fmtDateTime(d?: string | null): string {
  if (!d) return '-';
  return dayjs(d).format('YYYY-MM-DD HH:mm');
}

function fmtDate(d?: string | null): string {
  if (!d) return '-';
  return dayjs(d).format('YYYY-MM-DD');
}

function fileExtOf(url: string): string {
  const u = (url || '').toLowerCase();
  const clean = u.split('?')[0];
  const i = clean.lastIndexOf('.');
  return i >= 0 ? clean.slice(i + 1) : '';
}

export default function AdminSettlementsPage() {
  const [rows, setRows] = useState<SettlementRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(false);
  const [sortBy, setSortBy] = useState<string>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [filterForm] = Form.useForm();

  const [merchants, setMerchants] = useState<MerchantBrief[]>([]);
  const [stores, setStores] = useState<StoreBrief[]>([]);

  const [genOpen, setGenOpen] = useState(false);
  const [genForm] = Form.useForm();
  const [genLoading, setGenLoading] = useState(false);

  const [proofOpen, setProofOpen] = useState(false);
  const [proofForm] = Form.useForm();
  const [proofLoading, setProofLoading] = useState(false);
  const [proofTarget, setProofTarget] = useState<SettlementRow | null>(null);
  const [voucherType, setVoucherType] = useState<'image' | 'pdf' | null>(null);
  const [voucherFiles, setVoucherFiles] = useState<string[]>([]);
  const [uploadingFile, setUploadingFile] = useState(false);

  const [detailOpen, setDetailOpen] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detail, setDetail] = useState<DetailResp | null>(null);

  const loadMerchants = useCallback(async () => {
    try {
      const data = await get<MerchantBrief[]>('/api/admin/settlements/merchant-options');
      setMerchants(data || []);
    } catch { /* ignore */ }
  }, []);

  const loadStores = useCallback(async (merchantId?: number) => {
    try {
      const data = await get<StoreBrief[]>(
        '/api/admin/settlements/store-options',
        merchantId ? { merchant_profile_id: merchantId } : undefined,
      );
      setStores(data || []);
    } catch { /* ignore */ }
  }, []);

  const load = useCallback(async (override?: { page?: number; pageSize?: number; sortBy?: string; sortOrder?: 'asc' | 'desc' }) => {
    setLoading(true);
    try {
      const v = filterForm.getFieldsValue();
      const params: any = {
        page: override?.page ?? page,
        page_size: override?.pageSize ?? pageSize,
        sort_by: override?.sortBy ?? sortBy,
        sort_order: override?.sortOrder ?? sortOrder,
      };
      if (v.merchant_profile_id) params.merchant_profile_id = v.merchant_profile_id;
      if (v.store_id) params.store_id = v.store_id;
      if (v.period) params.period = (v.period as Dayjs).format('YYYY-MM');
      if (v.status && v.status !== 'all') params.status = v.status;
      if (v.dim && v.dim !== 'all') params.dim = v.dim;
      if (v.generated_range?.length === 2) {
        params.generated_start = (v.generated_range[0] as Dayjs).format('YYYY-MM-DD');
        params.generated_end = (v.generated_range[1] as Dayjs).format('YYYY-MM-DD');
      }
      if (v.settled_range?.length === 2) {
        params.settled_start = (v.settled_range[0] as Dayjs).format('YYYY-MM-DD');
        params.settled_end = (v.settled_range[1] as Dayjs).format('YYYY-MM-DD');
      }
      if (v.amount_min !== undefined && v.amount_min !== null && v.amount_min !== '') params.amount_min = v.amount_min;
      if (v.amount_max !== undefined && v.amount_max !== null && v.amount_max !== '') params.amount_max = v.amount_max;
      if (v.keyword) params.keyword = v.keyword;

      const data = await get<SettlementListResp>('/api/admin/settlements', params);
      setRows(data.items || []);
      setTotal(data.total || 0);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载对账单失败');
    } finally {
      setLoading(false);
    }
  }, [filterForm, page, pageSize, sortBy, sortOrder]);

  useEffect(() => {
    loadMerchants();
    loadStores();
  }, [loadMerchants, loadStores]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, sortBy, sortOrder]);

  const onQuery = () => {
    setPage(1);
    load({ page: 1 });
  };
  const onReset = () => {
    filterForm.resetFields();
    loadStores();
    setPage(1);
    load({ page: 1 });
  };

  const onTableChange = (p: TablePaginationConfig, _f: any, sorter: SorterResult<SettlementRow> | SorterResult<SettlementRow>[]) => {
    let newSortBy = sortBy;
    let newSortOrder: 'asc' | 'desc' = sortOrder;
    const s = Array.isArray(sorter) ? sorter[0] : sorter;
    if (s && s.field && s.order) {
      const fieldMap: Record<string, string> = {
        period_start: 'period_start',
        settlement_amount: 'settlement_amount',
        generated_at: 'created_at',
        settled_at: 'settled_at',
      };
      newSortBy = fieldMap[String(s.field)] || 'created_at';
      newSortOrder = s.order === 'ascend' ? 'asc' : 'desc';
    } else if (s && !s.order) {
      newSortBy = 'created_at';
      newSortOrder = 'desc';
    }
    setPage(p.current || 1);
    setPageSize(p.pageSize || 20);
    setSortBy(newSortBy);
    setSortOrder(newSortOrder);
  };

  const openProof = async (row: SettlementRow) => {
    setProofTarget(row);
    setVoucherType(null);
    setVoucherFiles([]);
    proofForm.resetFields();
    proofForm.setFieldsValue({
      amount: row.settlement_amount,
      paid_at: dayjs(),
      remark: '',
    });
    setProofOpen(true);
    // 带出已有凭证
    try {
      const d = await get<DetailResp>(`/api/admin/settlements/${row.id}`);
      if (d.proof && d.proof.voucher_files?.length) {
        setVoucherType((d.proof.voucher_type as any) || 'image');
        setVoucherFiles(d.proof.voucher_files);
        proofForm.setFieldsValue({
          amount: d.proof.amount ?? row.settlement_amount,
          paid_at: d.proof.paid_at ? dayjs(d.proof.paid_at) : dayjs(),
          remark: d.proof.remark || '',
        });
      }
    } catch { /* 首次无凭证 */ }
  };

  const doUploadFile = async (file: File, mode: 'image' | 'pdf'): Promise<string | null> => {
    setUploadingFile(true);
    try {
      const url = mode === 'image' ? '/api/upload/image' : '/api/upload/file';
      const res: any = await apiUpload(url, file);
      return res?.url || null;
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '上传失败');
      return null;
    } finally {
      setUploadingFile(false);
    }
  };

  const beforeImageUpload = async (file: File) => {
    if (voucherType === 'pdf' && voucherFiles.length > 0) {
      await new Promise<void>((resolve, reject) => {
        Modal.confirm({
          title: '切换为图片凭证？',
          content: '已有 PDF 凭证，继续将清空后改为图片模式。',
          okText: '确认切换',
          cancelText: '取消',
          onOk: () => { setVoucherFiles([]); setVoucherType('image'); resolve(); },
          onCancel: () => reject(new Error('cancelled')),
        });
      }).catch(() => { throw new Error('cancelled'); });
    }
    if (!file.type.startsWith('image/')) {
      message.error('仅支持 JPG / PNG 格式');
      return Upload.LIST_IGNORE;
    }
    if (file.size > 5 * 1024 * 1024) {
      message.error('单张图片不能超过 5MB');
      return Upload.LIST_IGNORE;
    }
    if (voucherType === 'image' && voucherFiles.length >= 5) {
      message.error('最多上传 5 张图片');
      return Upload.LIST_IGNORE;
    }
    const url = await doUploadFile(file, 'image');
    if (url) {
      setVoucherType('image');
      setVoucherFiles((prev) => [...prev, url]);
    }
    return Upload.LIST_IGNORE;
  };

  const beforePdfUpload = async (file: File) => {
    if (voucherType === 'image' && voucherFiles.length > 0) {
      await new Promise<void>((resolve, reject) => {
        Modal.confirm({
          title: '切换为 PDF 凭证？',
          content: '已有图片凭证，继续将清空后改为 PDF 模式。',
          okText: '确认切换',
          cancelText: '取消',
          onOk: () => { setVoucherFiles([]); setVoucherType('pdf'); resolve(); },
          onCancel: () => reject(new Error('cancelled')),
        });
      }).catch(() => { throw new Error('cancelled'); });
    }
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      message.error('仅支持 PDF 格式');
      return Upload.LIST_IGNORE;
    }
    if (file.size > 10 * 1024 * 1024) {
      message.error('PDF 不能超过 10MB');
      return Upload.LIST_IGNORE;
    }
    const url = await doUploadFile(file, 'pdf');
    if (url) {
      setVoucherType('pdf');
      setVoucherFiles([url]);
    }
    return Upload.LIST_IGNORE;
  };

  const removeVoucher = (index: number) => {
    setVoucherFiles((prev) => {
      const next = prev.filter((_, i) => i !== index);
      if (next.length === 0) setVoucherType(null);
      return next;
    });
  };

  const moveVoucher = (index: number, dir: -1 | 1) => {
    setVoucherFiles((prev) => {
      const next = [...prev];
      const target = index + dir;
      if (target < 0 || target >= next.length) return prev;
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
  };

  const submitProof = async (values: any) => {
    if (!proofTarget) return;
    if (!voucherType || voucherFiles.length === 0) {
      message.error('请上传至少 1 张图片或 1 份 PDF 凭证');
      return;
    }
    const amt = Number(values.amount);
    if (isNaN(amt) || amt < 0) {
      message.error('打款金额必须 ≥ 0');
      return;
    }
    const paid = values.paid_at as Dayjs;
    if (!paid) {
      message.error('请选择打款时间');
      return;
    }
    if (paid.isAfter(dayjs())) {
      message.error('打款时间不能晚于当前时间');
      return;
    }
    if (Math.abs(amt - proofTarget.settlement_amount) > 0.001) {
      const ok = await new Promise<boolean>((resolve) => {
        Modal.confirm({
          title: '打款金额与应结金额不一致',
          content: `应结 ¥${fmtAmount(proofTarget.settlement_amount)}，打款 ¥${fmtAmount(amt)}。是否继续提交？`,
          okText: '继续提交',
          cancelText: '再核对',
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
      });
      if (!ok) return;
    }
    setProofLoading(true);
    try {
      await post(`/api/admin/settlements/${proofTarget.id}/payment-proof`, {
        voucher_type: voucherType,
        voucher_files: voucherFiles,
        amount: amt,
        paid_at: paid.toISOString(),
        remark: values.remark || null,
      });
      message.success('凭证已保存，对账单已结清');
      setProofOpen(false);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setProofLoading(false);
    }
  };

  const openDetail = async (row: SettlementRow) => {
    setDetailOpen(true);
    setDetailLoading(true);
    setDetail(null);
    try {
      const d = await get<DetailResp>(`/api/admin/settlements/${row.id}`);
      setDetail(d);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载详情失败');
    } finally {
      setDetailLoading(false);
    }
  };

  const modifyProofFromDetail = () => {
    if (!detail) return;
    setDetailOpen(false);
    openProof(detail.info);
  };

  const submitGenerate = async (values: any) => {
    setGenLoading(true);
    try {
      const body: any = {};
      if (values.merchant_profile_id) body.merchant_profile_id = values.merchant_profile_id;
      if (values.period) {
        const p: Dayjs = values.period;
        const start = p.startOf('month').format('YYYY-MM-DD');
        const end = p.endOf('month').format('YYYY-MM-DD');
        body.period_start = start;
        body.period_end = end;
      }
      const res: any = await post('/api/admin/settlements/generate-monthly', body);
      message.success(`已生成 ${res?.created ?? 0} 张对账单`);
      setGenOpen(false);
      genForm.resetFields();
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '生成失败');
    } finally {
      setGenLoading(false);
    }
  };

  const columns: ColumnsType<SettlementRow> = useMemo(() => [
    { title: '对账单ID', dataIndex: 'statement_no', width: 200, fixed: 'left', render: (v) => <Text copyable={{ text: v }}>{v}</Text> },
    {
      title: '机构/门店名称',
      dataIndex: 'display_name',
      width: 220,
      render: (v, row) => v || row.merchant_name || `机构#${row.merchant_profile_id}`,
    },
    { title: '维度', dataIndex: 'dim', width: 100, render: renderDim },
    {
      title: '账单周期',
      dataIndex: 'period_start',
      width: 200,
      sorter: true,
      render: (_, row) => `${fmtDate(row.period_start)} ~ ${fmtDate(row.period_end)}`,
    },
    {
      title: '应结金额（元）',
      dataIndex: 'settlement_amount',
      width: 140,
      align: 'right',
      sorter: true,
      render: (v) => <Text strong>¥{fmtAmount(v)}</Text>,
    },
    { title: '状态', dataIndex: 'status', width: 100, render: renderStatus },
    { title: '生成时间', dataIndex: 'generated_at', width: 160, sorter: true, render: (v) => fmtDateTime(v) },
    { title: '结清时间', dataIndex: 'settled_at', width: 160, sorter: true, render: (v) => fmtDateTime(v) },
    {
      title: '操作',
      key: 'action',
      width: 200,
      fixed: 'right',
      render: (_, row) => {
        const isSettled = row.status === 'settled';
        return (
          <Space size="small">
            {isSettled ? (
              <Tooltip title="该对账单已结清">
                <Button size="small" disabled>上传凭证</Button>
              </Tooltip>
            ) : (
              <Button size="small" type="link" onClick={() => openProof(row)}>上传凭证</Button>
            )}
            <Button size="small" type="link" icon={<EyeOutlined />} onClick={() => openDetail(row)}>查看详情</Button>
          </Space>
        );
      },
    },
  ], []);

  const merchantOptions = merchants.map((m) => ({ label: m.name, value: m.id }));
  const storeOptions = stores.map((s) => ({ label: s.name, value: s.id }));

  return (
    <div>
      <Title level={4} style={{ marginBottom: 8 }}>对账单管理</Title>
      <Paragraph type="secondary" style={{ marginTop: 0 }}>
        系统每月 1 日凌晨自动为「上一自然月」的所有已启用机构生成对账单（机构维度 + 门店维度）。点击右上角「生成对账单」可手动补录。
      </Paragraph>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Form form={filterForm} layout="vertical" onFinish={onQuery} initialValues={{ status: 'all', dim: 'all' }}>
          <Row gutter={[16, 8]}>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="merchant_profile_id" label="机构">
                <Select
                  allowClear
                  showSearch
                  placeholder="请选择机构"
                  options={merchantOptions}
                  filterOption={(input, option) => String(option?.label || '').toLowerCase().includes(input.toLowerCase())}
                  onChange={(v) => {
                    filterForm.setFieldValue('store_id', undefined);
                    loadStores(v);
                  }}
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="period" label="账单周期">
                <DatePicker picker="month" style={{ width: '100%' }} placeholder="选择月份" />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="status" label="状态">
                <Select
                  options={[
                    { label: '全部', value: 'all' },
                    { label: '未结清', value: 'pending' },
                    { label: '已结清', value: 'settled' },
                    { label: '争议中', value: 'dispute' },
                  ]}
                />
              </Form.Item>
            </Col>
            <Col xs={24} sm={12} md={6}>
              <Form.Item name="keyword" label="关键词">
                <Input allowClear placeholder="机构/门店/对账单ID" onPressEnter={onQuery} />
              </Form.Item>
            </Col>
          </Row>
          {showMoreFilters && (
            <Row gutter={[16, 8]}>
              <Col xs={24} sm={12} md={6}>
                <Form.Item name="store_id" label="门店">
                  <Select
                    allowClear
                    showSearch
                    placeholder="请选择门店"
                    options={storeOptions}
                    filterOption={(input, option) => String(option?.label || '').toLowerCase().includes(input.toLowerCase())}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Form.Item name="dim" label="维度">
                  <Select
                    options={[
                      { label: '全部', value: 'all' },
                      { label: '机构维度', value: 'merchant' },
                      { label: '门店维度', value: 'store' },
                    ]}
                  />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Form.Item name="generated_range" label="生成时间">
                  <RangePicker style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Form.Item name="settled_range" label="结清时间">
                  <RangePicker style={{ width: '100%' }} />
                </Form.Item>
              </Col>
              <Col xs={24} sm={12} md={6}>
                <Form.Item label="金额区间（元）">
                  <Space.Compact style={{ width: '100%' }}>
                    <Form.Item name="amount_min" noStyle>
                      <InputNumber style={{ width: '50%' }} placeholder="最小" min={0} />
                    </Form.Item>
                    <Form.Item name="amount_max" noStyle>
                      <InputNumber style={{ width: '50%' }} placeholder="最大" min={0} />
                    </Form.Item>
                  </Space.Compact>
                </Form.Item>
              </Col>
            </Row>
          )}
          <Row justify="space-between" align="middle">
            <Col>
              <Button
                type="link"
                icon={showMoreFilters ? <UpOutlined /> : <DownOutlined />}
                onClick={() => setShowMoreFilters(!showMoreFilters)}
              >
                {showMoreFilters ? '收起筛选' : '更多筛选'}
              </Button>
            </Col>
            <Col>
              <Space>
                <Button onClick={onReset}>重置</Button>
                <Button type="primary" htmlType="submit">查询</Button>
              </Space>
            </Col>
          </Row>
        </Form>
      </Card>

      <Row justify="space-between" align="middle" style={{ marginBottom: 12 }}>
        <Col>
          <Text type="secondary">共 <Text strong>{total}</Text> 条</Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => load()}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setGenOpen(true)}>生成对账单</Button>
          </Space>
        </Col>
      </Row>

      <Table<SettlementRow>
        rowKey="id"
        columns={columns}
        dataSource={rows}
        loading={loading}
        scroll={{ x: 1400 }}
        pagination={{
          current: page,
          pageSize: pageSize,
          total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          pageSizeOptions: [10, 20, 50, 100],
        }}
        onChange={onTableChange}
        locale={{
          emptyText: (
            <div style={{ padding: '40px 0' }}>
              <Paragraph type="secondary" style={{ margin: 0 }}>
                当前暂无对账单，点击右上角「生成对账单」可手动创建。
              </Paragraph>
            </div>
          ),
        }}
      />

      {/* 生成对账单弹窗 */}
      <Modal
        title="手动生成对账单"
        open={genOpen}
        onCancel={() => setGenOpen(false)}
        onOk={() => genForm.submit()}
        confirmLoading={genLoading}
        destroyOnClose
      >
        <Paragraph type="secondary">
          用于定时任务异常、临时新增机构、历史数据补录等场景。若不选机构，将对所有已启用机构批量生成；若不选账期，将使用"上一自然月"。已存在的对账单不会重复生成。
        </Paragraph>
        <Form form={genForm} layout="vertical" onFinish={submitGenerate}>
          <Form.Item name="merchant_profile_id" label="机构（可选，默认全部）">
            <Select
              allowClear
              showSearch
              placeholder="全部机构"
              options={merchantOptions}
              filterOption={(input, option) => String(option?.label || '').toLowerCase().includes(input.toLowerCase())}
            />
          </Form.Item>
          <Form.Item name="period" label="账期月份（可选，默认上月）">
            <DatePicker picker="month" style={{ width: '100%' }} />
          </Form.Item>
        </Form>
      </Modal>

      {/* 上传凭证弹窗 */}
      <Modal
        title={proofTarget ? `上传打款凭证 · ${proofTarget.display_name || proofTarget.statement_no}` : '上传打款凭证'}
        open={proofOpen}
        onCancel={() => setProofOpen(false)}
        onOk={() => proofForm.submit()}
        confirmLoading={proofLoading}
        width={720}
        destroyOnClose={false}
      >
        {proofTarget && (
          <>
            <Descriptions size="small" column={2} style={{ marginBottom: 12 }}>
              <Descriptions.Item label="对账单ID">{proofTarget.statement_no}</Descriptions.Item>
              <Descriptions.Item label="机构/门店">{proofTarget.display_name || proofTarget.merchant_name}</Descriptions.Item>
              <Descriptions.Item label="应结金额">
                <Text strong style={{ color: '#cf1322' }}>¥{fmtAmount(proofTarget.settlement_amount)}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="账单周期">{`${fmtDate(proofTarget.period_start)} ~ ${fmtDate(proofTarget.period_end)}`}</Descriptions.Item>
            </Descriptions>
            <Form form={proofForm} layout="vertical" onFinish={submitProof}>
              <Form.Item label="凭证文件" required extra="图片模式（1~5 张 JPG/PNG，单张≤5MB）或 PDF 模式（单份 PDF，≤10MB），两种模式互斥">
                <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', marginBottom: 8 }}>
                  {voucherType === 'image' && voucherFiles.map((url, idx) => (
                    <div key={url + idx} style={{ position: 'relative', width: 104, height: 104, border: '1px solid #eee', borderRadius: 6, overflow: 'hidden' }}>
                      <AntImage src={url} width={104} height={104} style={{ objectFit: 'cover' }} />
                      <div style={{ position: 'absolute', top: 2, right: 2, display: 'flex', gap: 2 }}>
                        <Button size="small" onClick={() => moveVoucher(idx, -1)} disabled={idx === 0}>↑</Button>
                        <Button size="small" onClick={() => moveVoucher(idx, 1)} disabled={idx === voucherFiles.length - 1}>↓</Button>
                        <Button size="small" danger onClick={() => removeVoucher(idx)}>×</Button>
                      </div>
                    </div>
                  ))}
                  {voucherType === 'pdf' && voucherFiles.map((url, idx) => (
                    <Card key={url + idx} size="small" style={{ minWidth: 280 }}>
                      <Space>
                        <FilePdfOutlined style={{ color: '#d4380d', fontSize: 28 }} />
                        <div>
                          <div style={{ fontWeight: 500 }}>PDF 凭证</div>
                          <a href={url} target="_blank" rel="noreferrer">打开预览</a>
                          <Divider type="vertical" />
                          <Button size="small" danger onClick={() => removeVoucher(idx)}>删除</Button>
                        </div>
                      </Space>
                    </Card>
                  ))}
                </div>
                <Space>
                  <Upload
                    accept="image/jpeg,image/png,image/jpg"
                    beforeUpload={beforeImageUpload}
                    showUploadList={false}
                    maxCount={5}
                    disabled={uploadingFile || (voucherType === 'image' && voucherFiles.length >= 5)}
                  >
                    <Button icon={<CloudUploadOutlined />} disabled={voucherType === 'image' && voucherFiles.length >= 5} loading={uploadingFile && voucherType !== 'pdf'}>
                      {voucherType === 'image' && voucherFiles.length > 0 ? `追加图片（${voucherFiles.length}/5）` : '上传图片（1~5 张）'}
                    </Button>
                  </Upload>
                  <Upload
                    accept="application/pdf"
                    beforeUpload={beforePdfUpload}
                    showUploadList={false}
                    maxCount={1}
                    disabled={uploadingFile || (voucherType === 'pdf' && voucherFiles.length >= 1)}
                  >
                    <Button icon={<FilePdfOutlined />} disabled={voucherType === 'pdf' && voucherFiles.length >= 1} loading={uploadingFile && voucherType === 'pdf'}>
                      {voucherType === 'pdf' && voucherFiles.length > 0 ? '已上传 PDF' : '上传 PDF（1 份）'}
                    </Button>
                  </Upload>
                </Space>
              </Form.Item>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="amount" label="打款金额（元）" rules={[{ required: true, message: '请填写打款金额' }]}>
                    <InputNumber min={0} precision={2} style={{ width: '100%' }} placeholder="请输入实际打款金额" />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="paid_at" label="打款时间" rules={[{ required: true, message: '请选择打款时间' }]}>
                    <DatePicker showTime style={{ width: '100%' }} disabledDate={(d) => d.isAfter(dayjs(), 'day')} />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item
                name="remark"
                label="打款备注"
                extra="如：华夏银行对公转账 / 分两笔支付 / 扣除手续费 XXX"
                rules={[{ max: 500, message: '备注不能超过 500 字' }]}
              >
                <Input.TextArea rows={3} maxLength={500} showCount placeholder="选填，最多 500 字" />
              </Form.Item>
            </Form>
          </>
        )}
      </Modal>

      {/* 详情弹窗 */}
      <Modal
        title={detail ? `对账单详情 · ${detail.info.statement_no}` : '对账单详情'}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={<Button onClick={() => setDetailOpen(false)}>关闭</Button>}
        width={900}
        maskClosable={false}
        destroyOnClose
      >
        {detailLoading && <Paragraph>加载中...</Paragraph>}
        {detail && (
          <>
            <Title level={5}>基本信息</Title>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="对账单ID">{detail.info.statement_no}</Descriptions.Item>
              <Descriptions.Item label="机构/门店">{detail.info.display_name}</Descriptions.Item>
              <Descriptions.Item label="维度">{renderDim(detail.info.dim)}</Descriptions.Item>
              <Descriptions.Item label="账单周期">{`${fmtDate(detail.info.period_start)} ~ ${fmtDate(detail.info.period_end)}`}</Descriptions.Item>
              <Descriptions.Item label="应结金额">
                <Text strong style={{ color: '#cf1322' }}>¥{fmtAmount(detail.info.settlement_amount)}</Text>
              </Descriptions.Item>
              <Descriptions.Item label="状态">{renderStatus(detail.info.status)}</Descriptions.Item>
              <Descriptions.Item label="生成时间">{fmtDateTime(detail.info.generated_at)}</Descriptions.Item>
              <Descriptions.Item label="结清时间">{fmtDateTime(detail.info.settled_at)}</Descriptions.Item>
            </Descriptions>

            <Divider />

            <Title level={5}>结算明细（核销记录）</Title>
            <Table
              size="small"
              rowKey={(r: any, i) => `${r.order_no || ''}_${i}`}
              dataSource={detail.lines}
              pagination={{ pageSize: 10, showSizeChanger: false }}
              columns={[
                { title: '业务单号', dataIndex: 'order_no', width: 180 },
                { title: '业务类型', dataIndex: 'biz_type', width: 200 },
                { title: '发生时间', dataIndex: 'happened_at', width: 160, render: (v) => fmtDateTime(v) },
                { title: '金额（元）', dataIndex: 'amount', width: 120, align: 'right', render: (v) => `¥${fmtAmount(v)}` },
                { title: '备注', dataIndex: 'remark' },
              ]}
              footer={() => (
                <Space>
                  <Text>合计 <Text strong>{detail.lines.length}</Text> 条，</Text>
                  <Text>金额合计 <Text strong style={{ color: '#cf1322' }}>¥{fmtAmount(detail.lines_total_amount)}</Text></Text>
                </Space>
              )}
            />

            <Divider />

            <Title level={5}>打款凭证</Title>
            {!detail.proof && <Paragraph type="secondary">暂无凭证</Paragraph>}
            {detail.proof && (
              <>
                <Descriptions column={2} size="small">
                  <Descriptions.Item label="打款金额">¥{fmtAmount(detail.proof.amount)}</Descriptions.Item>
                  <Descriptions.Item label="打款时间">{fmtDateTime(detail.proof.paid_at)}</Descriptions.Item>
                  <Descriptions.Item label="上传时间">{fmtDateTime(detail.proof.updated_at || detail.proof.created_at)}</Descriptions.Item>
                  <Descriptions.Item label="上传人">{detail.proof.uploaded_by_name || '-'}</Descriptions.Item>
                  <Descriptions.Item label="打款备注" span={2}>{detail.proof.remark || '-'}</Descriptions.Item>
                </Descriptions>
                <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginTop: 8 }}>
                  {detail.proof.voucher_type === 'pdf'
                    ? (
                      detail.proof.voucher_files.map((url) => (
                        <Card key={url} size="small">
                          <Space>
                            <FilePdfOutlined style={{ fontSize: 28, color: '#d4380d' }} />
                            <a href={url} target="_blank" rel="noreferrer">打开 PDF 预览</a>
                          </Space>
                        </Card>
                      ))
                    )
                    : (
                      <AntImage.PreviewGroup>
                        {detail.proof.voucher_files.map((url) => (
                          fileExtOf(url) === 'pdf'
                            ? (
                              <Card key={url} size="small">
                                <a href={url} target="_blank" rel="noreferrer">打开 PDF 预览</a>
                              </Card>
                            )
                            : <AntImage key={url} src={url} width={120} height={120} style={{ objectFit: 'cover', borderRadius: 4 }} />
                        ))}
                      </AntImage.PreviewGroup>
                    )}
                </div>
                <div style={{ marginTop: 16 }}>
                  {detail.info.status !== 'settled' ? (
                    <Button type="primary" onClick={modifyProofFromDetail}>修改凭证</Button>
                  ) : (
                    <Text type="secondary">已结清，凭证只读</Text>
                  )}
                </div>
              </>
            )}
          </>
        )}
      </Modal>
    </div>
  );
}
