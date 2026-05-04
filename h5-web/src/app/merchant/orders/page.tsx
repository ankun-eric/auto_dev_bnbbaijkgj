'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Input, Space, Button, DatePicker, Tag, Typography, Modal, Upload, Form, InputNumber, message, Popconfirm, Select,
  Drawer, Descriptions, Divider, List as AntList, Image as AntImage,
} from 'antd';
import type { UploadFile, UploadProps } from 'antd';
import {
  SearchOutlined, PaperClipOutlined, DownloadOutlined, UploadOutlined,
  CheckCircleOutlined, ClockCircleOutlined, FormOutlined, EyeOutlined, FilePdfOutlined, DeleteOutlined,
} from '@ant-design/icons';
import api from '@/lib/api';
import dayjs from 'dayjs';
import { getCurrentStoreId } from '../lib';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface OrderRow {
  order_id: number;
  order_no: string;
  user_display: string;
  user_nickname?: string;
  user_phone?: string;
  product_name: string;
  total_quantity?: number;
  created_at: string;
  appointment_time?: string;
  store_id?: number;
  store_name?: string;
  status: string;
  amount: number;
  payment_method?: string;
  attachment_count: number;
  payment_method_text?: string;
  redemption_code?: string;
}

// PRD「商家 PC 后台优化 v1.1」F1+F2：与用户端 unified-orders 完全一致的 14 态映射
// 历史遗留 redeemed/paid 仅作为防御性降级映射，筛选器不暴露
const statusMap: Record<string, { text: string; color: string }> = {
  pending_payment: { text: '待付款', color: '#fa8c16' },
  pending_shipment: { text: '待发货', color: '#1890ff' },
  pending_receipt: { text: '待收货', color: '#13c2c2' },
  pending_appointment: { text: '待预约', color: '#722ed1' },
  appointed: { text: '待核销', color: '#13c2c2' },
  pending_use: { text: '待核销', color: '#13c2c2' },
  partial_used: { text: '部分核销', color: '#faad14' },
  pending_review: { text: '待评价', color: '#eb2f96' },
  completed: { text: '已完成', color: '#52c41a' },
  expired: { text: '已过期', color: '#8c8c8c' },
  refunding: { text: '退款中', color: '#f5222d' },
  refunded: { text: '已退款', color: '#8c8c8c' },
  cancelled: { text: '已取消', color: '#8c8c8c' },
  // 历史遗留兼容映射（不在筛选器中暴露）
  redeemed: { text: '已完成', color: '#52c41a' },
  paid: { text: '待核销', color: '#1677ff' },
};

// 筛选器可选项（商家常用 6 个 Tab，不暴露 redeemed/paid）
const FILTER_STATUS_OPTIONS: { value: string; label: string }[] = [
  { value: 'pending_payment', label: '待付款' },
  { value: 'pending_shipment', label: '待发货' },
  { value: 'pending_use', label: '待核销' },
  { value: 'completed', label: '已完成' },
  { value: 'refunded', label: '已退款' },
  { value: 'cancelled', label: '已取消' },
];

// PRD F4：附件上传约束
const ATTACHMENT_MAX_SIZE = 5 * 1024 * 1024; // 5 MB
const ATTACHMENT_MAX_COUNT = 9;
const IMAGE_MIME = ['image/jpeg', 'image/jpg', 'image/png'];
const PDF_MIME = ['application/pdf'];

export default function OrdersPage() {
  const [rows, setRows] = useState<OrderRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [keyword, setKeyword] = useState('');
  const [status, setStatus] = useState<string | undefined>();
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs, dayjs.Dayjs] | null>(null);

  const [attachOpen, setAttachOpen] = useState(false);
  const [currentOrder, setCurrentOrder] = useState<OrderRow | null>(null);
  const [attachments, setAttachments] = useState<any[]>([]);
  const [uploadForm] = Form.useForm();

  // Order detail drawer state
  const [detailOpen, setDetailOpen] = useState(false);
  const [detailOrder, setDetailOrder] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [orderNotes, setOrderNotes] = useState<any[]>([]);
  const [noteText, setNoteText] = useState('');
  const [submittingNote, setSubmittingNote] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const [adjustForm] = Form.useForm();

  const load = useCallback(async (p: number = page) => {
    setLoading(true);
    try {
      const storeId = getCurrentStoreId();
      const params: any = {
        page: p,
        page_size: 20,
        keyword: keyword || undefined,
        status: status || undefined,
      };
      if (storeId) params.store_id = storeId;
      if (dateRange) {
        params.start_date = dateRange[0].format('YYYY-MM-DD');
        params.end_date = dateRange[1].format('YYYY-MM-DD');
      }
      const res: any = await api.get('/api/merchant/orders', { params });
      setRows(res.items || []);
      setTotal(res.total || 0);
      setPage(p);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [keyword, status, dateRange, page]);

  useEffect(() => { load(1); }, []); // eslint-disable-line

  const openAttach = async (row: OrderRow) => {
    setCurrentOrder(row);
    setAttachOpen(true);
    try {
      const res: any = await api.get(`/api/merchant/orders/${row.order_id}/attachments`);
      setAttachments(res || []);
    } catch { setAttachments([]); }
  };

  // PRD F4：Antd Upload 改造，前端拦截 jpg/png/pdf + 5MB + 9 个上限
  const beforeUpload: UploadProps['beforeUpload'] = (file) => {
    const isImage = IMAGE_MIME.includes(file.type);
    const isPdf = PDF_MIME.includes(file.type);
    if (!isImage && !isPdf) {
      message.error('仅支持 jpg/png 图片或 pdf 文档');
      return Upload.LIST_IGNORE;
    }
    if (file.size > ATTACHMENT_MAX_SIZE) {
      message.error('单个附件不得超过 5MB');
      return Upload.LIST_IGNORE;
    }
    if (attachments.length >= ATTACHMENT_MAX_COUNT) {
      message.error(`单订单最多 ${ATTACHMENT_MAX_COUNT} 个附件`);
      return Upload.LIST_IGNORE;
    }
    return true;
  };

  const customUpload: UploadProps['customRequest'] = async (options) => {
    const { file, onSuccess, onError } = options;
    if (!currentOrder) return;
    try {
      const fd = new FormData();
      fd.append('file', file as Blob);
      const res: any = await api.post(
        `/api/merchant/orders/${currentOrder.order_id}/attachments/upload`,
        fd,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      message.success('附件已上传');
      onSuccess?.(res, new XMLHttpRequest());
      openAttach(currentOrder);
      load(page);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || '上传失败';
      message.error(msg);
      onError?.(new Error(msg));
    }
  };

  const deleteAttach = async (attId: number) => {
    if (!currentOrder) return;
    try {
      await api.delete(`/api/merchant/orders/${currentOrder.order_id}/attachments/${attId}`);
      message.success('已删除');
      openAttach(currentOrder);
      load(page);
    } catch (e: any) { message.error(e?.response?.data?.detail || '删除失败'); }
  };

  const openDetail = async (row: OrderRow) => {
    setDetailOpen(true);
    setDetailLoading(true);
    setDetailOrder(null);
    setOrderNotes([]);
    try {
      const storeId = getCurrentStoreId();
      const params: any = {};
      if (storeId) params.store_id = storeId;
      const res: any = await api.get(`/api/merchant/orders/${row.order_id}/detail`, { params });
      setDetailOrder(res);
    } catch { setDetailOrder(row); }
    try {
      const noteStoreId = getCurrentStoreId();
      const noteP: any = {};
      if (noteStoreId) noteP.store_id = noteStoreId;
      const notesRes: any = await api.get(`/api/merchant/orders/${row.order_id}/notes`, { params: noteP });
      setOrderNotes(notesRes?.items || notesRes || []);
    } catch { setOrderNotes([]); }
    setDetailLoading(false);
  };

  const handleConfirmOrder = async () => {
    if (!detailOrder) return;
    setConfirming(true);
    try {
      const sid = getCurrentStoreId();
      const cp: any = {};
      if (sid) cp.store_id = sid;
      await api.post(`/api/merchant/orders/${detailOrder.order_id}/confirm`, null, { params: cp });
      message.success('已确认接单');
      openDetail(detailOrder);
      load(page);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '确认失败');
    } finally { setConfirming(false); }
  };

  const handleAdjustTime = async (values: any) => {
    if (!detailOrder) return;
    try {
      const dateStr = values.date.format('YYYY-MM-DD');
      const slotTimeMap: Record<string, string> = { morning: '09:00', afternoon: '13:00', evening: '18:00' };
      const sid = getCurrentStoreId();
      const ap: any = {};
      if (sid) ap.store_id = sid;
      await api.put(`/api/merchant/orders/${detailOrder.order_id}/appointment-time`, {
        new_date: dateStr,
        new_time_slot: slotTimeMap[values.time_slot] || '09:00',
      }, { params: ap });
      message.success('预约时间已调整');
      setAdjustOpen(false);
      adjustForm.resetFields();
      openDetail(detailOrder);
      load(page);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '调整失败');
    }
  };

  const handleSubmitNote = async () => {
    if (!detailOrder || !noteText.trim()) {
      message.warning('请输入备注内容');
      return;
    }
    setSubmittingNote(true);
    try {
      const sid = getCurrentStoreId();
      const np: any = {};
      if (sid) np.store_id = sid;
      await api.post(`/api/merchant/orders/${detailOrder.order_id}/notes`, { content: noteText.trim() }, { params: np });
      message.success('备注已添加');
      setNoteText('');
      const notesRes: any = await api.get(`/api/merchant/orders/${detailOrder.order_id}/notes`, { params: np });
      setOrderNotes(notesRes?.items || notesRes || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '添加备注失败');
    } finally { setSubmittingNote(false); }
  };

  // PRD「订单列表固定列与列宽优化 v1.0」：
  // - 左侧 3 列（订单号 / 下单时间 / 商品名称）取消固定，全部跟随横滚
  // - 右侧仅固定 "状态" + "操作"
  // - 商家 PC 端列顺序：订单号 → 下单时间 → 商品名称 → 用户 → 手机 → 数量 → 金额 → 支付方式
  //   → 商家专属（核销码 / 门店 / 预约时间 / 附件）→ 状态 → 操作
  // - 列宽按 PRD 规范，截断列鼠标悬停 tooltip 显示完整内容
  const PAYMENT_METHOD_LABEL: Record<string, string> = {
    wechat: '微信',
    alipay: '支付宝',
    balance: '余额',
    points: '积分',
  };
  const columns = [
    {
      title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 160, ellipsis: true,
      render: (v: string) => (
        <Typography.Text
          ellipsis={{ tooltip: v }}
          copyable={{ text: v, tooltips: ['复制订单号', '已复制'] }}
          style={{ maxWidth: 130 }}
        >
          {v}
        </Typography.Text>
      ),
    },
    {
      title: '下单时间', dataIndex: 'created_at', key: 'created_at', width: 140,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-',
    },
    {
      title: '商品名称', dataIndex: 'product_name', key: 'product_name', width: 220,
      render: (v: string) => (
        <Typography.Paragraph ellipsis={{ rows: 2, tooltip: v }} style={{ marginBottom: 0 }}>
          {v || '-'}
        </Typography.Paragraph>
      ),
    },
    {
      title: '用户', key: 'user_display', width: 140,
      render: (_: any, row: OrderRow) => {
        const nickname = row.user_nickname || row.user_display || '用户';
        const tail = row.user_phone ? row.user_phone.slice(-4) : '';
        const display = tail ? `${nickname}(${tail})` : nickname;
        return (
          <Typography.Text ellipsis={{ tooltip: display }} style={{ maxWidth: 120 }}>
            {display}
          </Typography.Text>
        );
      },
    },
    {
      title: '手机', dataIndex: 'user_phone', key: 'user_phone', width: 120,
      render: (v: string) => v || '-',
    },
    {
      title: '数量', dataIndex: 'total_quantity', key: 'total_quantity', width: 60,
      align: 'right' as const,
      render: (v: number) => <span>{v ?? 0}</span>,
    },
    {
      title: '金额', dataIndex: 'amount', key: 'amount', width: 100,
      align: 'right' as const,
      render: (v: number) => (
        <span style={{ color: '#fa541c', fontWeight: 600 }}>¥{Number(v || 0).toFixed(2)}</span>
      ),
    },
    {
      title: '支付方式', key: 'payment_method', width: 110,
      render: (_: any, row: OrderRow) => {
        if (row.payment_method) return PAYMENT_METHOD_LABEL[row.payment_method] || row.payment_method;
        return row.payment_method_text || '-';
      },
    },
    // ── 以下为商家 PC 端专属字段，本次保留现有顺序与宽度，仅取消左固定 ──
    { title: '核销码', dataIndex: 'redemption_code', key: 'redemption_code', width: 140, render: (v: string) => v ? <code style={{ fontSize: 12 }}>{v}</code> : '-' },
    { title: '门店', dataIndex: 'store_name', key: 'store_name', width: 140, ellipsis: true },
    { title: '预约时间', dataIndex: 'appointment_time', key: 'appointment_time', width: 160, render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
    { title: '附件', dataIndex: 'attachment_count', key: 'attachment_count', width: 70, align: 'center' as const, render: (n: number) => <span>{n || 0}</span> },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      fixed: 'right' as const,
      render: (s: string) => {
        const meta = statusMap[s] || { text: s, color: '#8c8c8c' };
        return <Tag color={meta.color} style={{ borderColor: 'transparent' }}>{meta.text}</Tag>;
      },
    },
    {
      title: '操作', key: 'ops', width: 160,
      fixed: 'right' as const,
      render: (_: any, row: OrderRow) => (
        <Space size={0} wrap>
          <Button size="small" type="link" onClick={() => openDetail(row)}>详情</Button>
          <Button size="small" type="link" icon={<PaperClipOutlined />} onClick={() => openAttach(row)}>附件</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>订单管理</Title>
      <Space wrap style={{ marginBottom: 16 }}>
        <Input
          placeholder="订单号/商品名"
          prefix={<SearchOutlined />}
          value={keyword}
          onChange={e => setKeyword(e.target.value)}
          style={{ width: 200 }}
          allowClear
        />
        <Select
          placeholder="状态"
          value={status}
          onChange={setStatus}
          style={{ width: 140 }}
          allowClear
          options={FILTER_STATUS_OPTIONS}
        />
        <RangePicker value={dateRange as any} onChange={v => setDateRange(v as any)} />
        <Button type="primary" onClick={() => load(1)}>查询</Button>
      </Space>
      <Table
        rowKey="order_id"
        loading={loading}
        dataSource={rows}
        columns={columns as any}
        scroll={{ x: 1820 }}
        size="middle"
        rowClassName={() => 'merchant-orders-row'}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: p => load(p),
          showSizeChanger: false,
        }}
      />
      <style jsx global>{`
        /* PRD F3：行高加高 8px，避免字段拥挤 */
        .merchant-orders-row > td {
          padding-top: 16px !important;
          padding-bottom: 16px !important;
        }
      `}</style>

      <Modal
        title={`订单附件 - ${currentOrder?.order_no || ''}`}
        open={attachOpen}
        onCancel={() => setAttachOpen(false)}
        footer={null}
        width={760}
      >
        {/* PRD F4：附件列表 — 图片可预览，PDF 可下载 */}
        <AntList
          dataSource={attachments}
          locale={{ emptyText: '暂无附件' }}
          renderItem={(att: any) => {
            const isImage = att.file_type === 'image';
            return (
              <AntList.Item
                actions={[
                  isImage ? (
                    <a key="preview" href={att.file_url} target="_blank" rel="noreferrer">
                      <EyeOutlined /> 预览
                    </a>
                  ) : (
                    <a key="download" href={att.file_url} target="_blank" rel="noreferrer" download>
                      <DownloadOutlined /> 下载
                    </a>
                  ),
                  <Popconfirm key="delete" title="确定删除该附件?" onConfirm={() => deleteAttach(att.id)}>
                    <a style={{ color: '#ff4d4f' }}><DeleteOutlined /> 删除</a>
                  </Popconfirm>,
                ]}
              >
                <AntList.Item.Meta
                  avatar={
                    isImage ? (
                      <AntImage
                        src={att.file_url}
                        width={56}
                        height={56}
                        style={{ objectFit: 'cover', borderRadius: 4 }}
                        preview={{ mask: <EyeOutlined /> }}
                      />
                    ) : (
                      <div style={{ width: 56, height: 56, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff1f0', borderRadius: 4 }}>
                        <FilePdfOutlined style={{ fontSize: 28, color: '#cf1322' }} />
                      </div>
                    )
                  }
                  title={att.file_name || (isImage ? '图片' : 'PDF文件')}
                  description={
                    <Space size={16} style={{ fontSize: 12, color: '#8c8c8c' }}>
                      <span>{isImage ? '图片' : 'PDF'}</span>
                      <span>{att.file_size ? `${(att.file_size / 1024).toFixed(1)} KB` : '-'}</span>
                      <span>{att.created_at ? dayjs(att.created_at).format('YYYY-MM-DD HH:mm') : '-'}</span>
                    </Space>
                  }
                />
              </AntList.Item>
            );
          }}
        />
        <Divider />
        {/* PRD F4：Antd Upload 组件，jpg/png/pdf，单文件 ≤5MB，最多 9 个 */}
        <div style={{ padding: 16, background: '#fafafa', borderRadius: 8 }}>
          <Typography.Text strong>上传附件</Typography.Text>
          <div style={{ fontSize: 12, color: '#8c8c8c', margin: '6px 0 12px' }}>
            支持 jpg / png 图片、pdf 文档；单个附件不得超过 5MB；单订单最多 {ATTACHMENT_MAX_COUNT} 个附件
          </div>
          <Upload
            accept=".jpg,.jpeg,.png,.pdf,image/jpeg,image/png,application/pdf"
            beforeUpload={beforeUpload}
            customRequest={customUpload}
            showUploadList={false}
            multiple={false}
            disabled={attachments.length >= ATTACHMENT_MAX_COUNT}
          >
            <Button
              type="primary"
              icon={<UploadOutlined />}
              disabled={attachments.length >= ATTACHMENT_MAX_COUNT}
            >
              选择文件上传
            </Button>
          </Upload>
          <span style={{ marginLeft: 12, fontSize: 12, color: '#1677ff' }}>
            已上传：{attachments.length} / {ATTACHMENT_MAX_COUNT}
          </span>
        </div>
      </Modal>

      {/* Order detail drawer */}
      <Drawer
        title={`订单详情 - ${detailOrder?.order_no || ''}`}
        open={detailOpen}
        onClose={() => { setDetailOpen(false); setDetailOrder(null); }}
        width={560}
      >
        {detailLoading ? (
          <div style={{ textAlign: 'center', padding: 48 }}><Typography.Text type="secondary">加载中...</Typography.Text></div>
        ) : detailOrder && (
          <>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="订单号">{detailOrder.order_no}</Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusMap[detailOrder.status]?.color || 'default'}>{statusMap[detailOrder.status]?.text || detailOrder.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="客户">{detailOrder.user_display || '—'}</Descriptions.Item>
              <Descriptions.Item label="商品">{detailOrder.product_name || '—'}</Descriptions.Item>
              <Descriptions.Item label="金额"><span style={{ color: '#fa541c', fontWeight: 600 }}>¥{detailOrder.amount || 0}</span></Descriptions.Item>
              <Descriptions.Item label="门店">{detailOrder.store_name || '—'}</Descriptions.Item>
              <Descriptions.Item label="下单时间" span={2}>{detailOrder.created_at ? dayjs(detailOrder.created_at).format('YYYY-MM-DD HH:mm') : '—'}</Descriptions.Item>
              {detailOrder.appointment_time && (
                <Descriptions.Item label="预约时间" span={2}>
                  <span style={{ color: '#1677ff', fontWeight: 500 }}>{dayjs(detailOrder.appointment_time).format('YYYY-MM-DD HH:mm')}</span>
                </Descriptions.Item>
              )}
            </Descriptions>

            {/* Action buttons */}
            <div style={{ margin: '16px 0' }}>
              <Space>
                {detailOrder.is_appointment && ['pending', 'paid'].includes(detailOrder.status) && (
                  <Button type="primary" icon={<CheckCircleOutlined />} loading={confirming} onClick={handleConfirmOrder}>
                    确认接单
                  </Button>
                )}
                {detailOrder.is_appointment && !['cancelled', 'refunded', 'completed'].includes(detailOrder.status) && (
                  <Button icon={<ClockCircleOutlined />} onClick={() => setAdjustOpen(true)}>
                    调整预约时间
                  </Button>
                )}
              </Space>
            </div>

            <Divider>门店备注</Divider>

            <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
              <Input.TextArea
                placeholder="输入备注内容..."
                value={noteText}
                onChange={(e) => setNoteText(e.target.value)}
                rows={2}
                style={{ flex: 1 }}
              />
              <Button type="primary" icon={<FormOutlined />} loading={submittingNote} onClick={handleSubmitNote} style={{ alignSelf: 'flex-end' }}>
                提交
              </Button>
            </div>

            {orderNotes.length === 0 ? (
              <Typography.Text type="secondary">暂无备注</Typography.Text>
            ) : (
              <AntList
                size="small"
                dataSource={orderNotes}
                renderItem={(n: any) => (
                  <AntList.Item>
                    <div style={{ width: '100%' }}>
                      <div>{n.content}</div>
                      <div style={{ fontSize: 12, color: '#999', marginTop: 4, display: 'flex', justifyContent: 'space-between' }}>
                        <span>{n.staff_name || ''}</span>
                        <span>{n.created_at ? dayjs(n.created_at).format('YYYY-MM-DD HH:mm') : ''}</span>
                      </div>
                    </div>
                  </AntList.Item>
                )}
              />
            )}
          </>
        )}
      </Drawer>

      {/* Adjust appointment time modal */}
      <Modal
        title="调整预约时间"
        open={adjustOpen}
        onCancel={() => { setAdjustOpen(false); adjustForm.resetFields(); }}
        onOk={() => adjustForm.submit()}
      >
        <Form form={adjustForm} layout="vertical" onFinish={handleAdjustTime}>
          <Form.Item name="date" label="预约日期" rules={[{ required: true, message: '请选择日期' }]}>
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="time_slot" label="预约时段" rules={[{ required: true, message: '请选择时段' }]}>
            <Select
              options={[
                { value: 'morning', label: '上午 (9:00-12:00)' },
                { value: 'afternoon', label: '下午 (13:00-17:00)' },
                { value: 'evening', label: '晚间 (18:00-21:00)' },
              ]}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
