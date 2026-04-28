'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Input, Space, Button, DatePicker, Tag, Typography, Modal, Upload, Form, InputNumber, message, Popconfirm, Select,
  Drawer, Descriptions, Divider, List as AntList,
} from 'antd';
import {
  SearchOutlined, PaperClipOutlined, DownloadOutlined, UploadOutlined,
  CheckCircleOutlined, ClockCircleOutlined, FormOutlined,
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
  product_name: string;
  created_at: string;
  appointment_time?: string;
  store_id?: number;
  store_name?: string;
  status: string;
  amount: number;
  attachment_count: number;
}

const statusMap: Record<string, { text: string; color: string }> = {
  pending_payment: { text: '待支付', color: 'orange' },
  paid: { text: '已支付', color: 'blue' },
  redeemed: { text: '已核销', color: 'green' },
  cancelled: { text: '已取消', color: 'default' },
  refunded: { text: '已退款', color: 'red' },
  completed: { text: '已完成', color: 'green' },
};

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

  const doUpload = async (values: any) => {
    if (!currentOrder) return;
    try {
      await api.post(`/api/merchant/orders/${currentOrder.order_id}/attachments`, {
        file_url: values.file_url,
        file_name: values.file_name,
        file_type: values.file_type,
        file_size: values.file_size || 0,
      });
      message.success('附件已上传');
      uploadForm.resetFields();
      openAttach(currentOrder);
      load(page);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '上传失败');
    }
  };

  const deleteAttach = async (attId: number) => {
    if (!currentOrder) return;
    try {
      await api.delete(`/api/merchant/orders/${currentOrder.order_id}/attachments/${attId}`);
      message.success('已删除');
      openAttach(currentOrder);
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

  const columns = [
    { title: '订单号', dataIndex: 'order_no', key: 'order_no', width: 180 },
    { title: '用户', dataIndex: 'user_display', key: 'user_display', width: 130 },
    { title: '商品', dataIndex: 'product_name', key: 'product_name' },
    { title: '下单时间', dataIndex: 'created_at', key: 'created_at', width: 160, render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
    { title: '门店', dataIndex: 'store_name', key: 'store_name', width: 140 },
    {
      title: '状态', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => <Tag color={statusMap[s]?.color || 'default'}>{statusMap[s]?.text || s}</Tag>,
    },
    { title: '金额', dataIndex: 'amount', key: 'amount', width: 90, render: (v: number) => `¥${v || 0}` },
    { title: '附件', dataIndex: 'attachment_count', key: 'attachment_count', width: 70 },
    {
      title: '操作', key: 'ops', width: 200,
      render: (_: any, row: OrderRow) => (
        <Space>
          <Button size="small" type="link" onClick={() => openDetail(row)}>详情</Button>
          <Button size="small" icon={<PaperClipOutlined />} onClick={() => openAttach(row)}>附件</Button>
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
          style={{ width: 120 }}
          allowClear
          options={Object.entries(statusMap).map(([k, v]) => ({ value: k, label: v.text }))}
        />
        <RangePicker value={dateRange as any} onChange={v => setDateRange(v as any)} />
        <Button type="primary" onClick={() => load(1)}>查询</Button>
      </Space>
      <Table
        rowKey="order_id"
        loading={loading}
        dataSource={rows}
        columns={columns as any}
        pagination={{
          current: page,
          total,
          pageSize: 20,
          onChange: p => load(p),
          showSizeChanger: false,
        }}
      />

      <Modal
        title={`订单附件 - ${currentOrder?.order_no || ''}`}
        open={attachOpen}
        onCancel={() => setAttachOpen(false)}
        footer={null}
        width={720}
      >
        <Table
          size="small"
          rowKey="id"
          dataSource={attachments}
          pagination={false}
          columns={[
            { title: '文件名', dataIndex: 'file_name' },
            { title: '类型', dataIndex: 'file_type', width: 80 },
            { title: '大小', dataIndex: 'file_size', width: 100, render: (v: number) => v ? `${(v / 1024).toFixed(1)}KB` : '-' },
            { title: '上传时间', dataIndex: 'created_at', width: 160, render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
            {
              title: '操作', width: 160, render: (_: any, att: any) => (
                <Space>
                  <a href={att.file_url} target="_blank" rel="noreferrer"><DownloadOutlined /> 下载</a>
                  <Popconfirm title="确定删除?" onConfirm={() => deleteAttach(att.id)}>
                    <a>删除</a>
                  </Popconfirm>
                </Space>
              ),
            },
          ]}
        />
        <div style={{ marginTop: 16, padding: 16, background: '#fafafa', borderRadius: 8 }}>
          <Typography.Text strong>上传附件（单文件≤20MB，最多 5 个）</Typography.Text>
          <Form form={uploadForm} layout="vertical" onFinish={doUpload} style={{ marginTop: 12 }}>
            <Form.Item name="file_url" label="文件URL" rules={[{ required: true, message: '请输入文件URL' }]}>
              <Input placeholder="上传到OSS后粘贴URL，或使用对接的上传组件" />
            </Form.Item>
            <Space>
              <Form.Item name="file_name" label="文件名" rules={[{ required: true }]}>
                <Input placeholder="report.pdf" />
              </Form.Item>
              <Form.Item name="file_type" label="类型" rules={[{ required: true }]} initialValue="pdf">
                <Select style={{ width: 120 }} options={[{ value: 'image', label: '图片' }, { value: 'pdf', label: 'PDF' }]} />
              </Form.Item>
              <Form.Item name="file_size" label="大小(字节)">
                <InputNumber min={0} max={20 * 1024 * 1024} />
              </Form.Item>
            </Space>
            <Button type="primary" htmlType="submit" icon={<UploadOutlined />}>提交附件</Button>
          </Form>
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
