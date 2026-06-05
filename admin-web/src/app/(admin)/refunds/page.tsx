'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Modal, Input, Tag, message,
  Typography, Descriptions, Card, Select, InputNumber,
  Spin, Tabs, Badge,
} from 'antd';
import {
  CheckOutlined, CloseOutlined, UndoOutlined, ExclamationCircleOutlined,
} from '@ant-design/icons';
import { get, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const { TextArea } = Input;

interface RefundItem {
  id: number;
  order_id: number;
  order_item_id: number | null;
  user_id: number;
  reason: string;
  refund_amount: number;
  refund_amount_approved: number | null;
  status: string;
  refund_transaction_id: string | null;
  refund_type: string | null;
  refund_channel: string | null;
  admin_notes: string | null;
  has_redemption: boolean;
  created_at: string;
  updated_at: string;
  order: {
    id: number;
    order_no: string;
    total_amount: number;
    paid_amount: number;
    status: string;
    refund_status: string;
  } | null;
  user: {
    id: number;
    nickname: string;
    phone: string;
  } | null;
}

const statusMap: Record<string, { color: string; text: string }> = {
  pending: { color: 'orange', text: '待审核' },
  reviewing: { color: 'orange', text: '审核中' },
  approved: { color: 'blue', text: '已通过(待退款)' },
  rejected: { color: 'red', text: '已驳回' },
  completed: { color: 'green', text: '退款完成' },
  withdrawn: { color: 'default', text: '已撤回' },
};

const channelMap: Record<string, string> = {
  wechat: '微信支付',
  alipay: '支付宝',
};

export default function RefundsPage() {
  const [refunds, setRefunds] = useState<RefundItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('all');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });

  const [detailVisible, setDetailVisible] = useState(false);
  const [currentRefund, setCurrentRefund] = useState<RefundItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const [approveModalVisible, setApproveModalVisible] = useState(false);
  const [approveLoading, setApproveLoading] = useState(false);
  const [refundType, setRefundType] = useState<'full' | 'partial'>('full');
  const [refundAmount, setRefundAmount] = useState<number>(0);
  const [adminNotes, setAdminNotes] = useState('');

  const [rejectModalVisible, setRejectModalVisible] = useState(false);
  const [rejectLoading, setRejectLoading] = useState(false);
  const [rejectReason, setRejectReason] = useState('');

  const fetchRefunds = useCallback(async (page = 1, size = 20) => {
    setLoading(true);
    try {
      const params: any = { page, page_size: size };
      if (activeTab !== 'all') params.status = activeTab;
      const res: any = await get('/api/admin/refunds', params);
      const items = (res && res.items) || [];
      setRefunds(items);
      setPagination({ current: page, pageSize: size, total: res.total || 0 });
    } catch (e) {
      console.error('fetchRefunds error', e);
    } finally {
      setLoading(false);
    }
  }, [activeTab]);

  useEffect(() => {
    fetchRefunds();
  }, [fetchRefunds]);

  const handleTableChange = (pag: any) => {
    fetchRefunds(pag.current, pag.pageSize);
  };

  const handleApproveClick = async (refund: RefundItem) => {
    setCurrentRefund(refund);
    setRefundType('full');
    const amt = refund.refund_amount_approved || refund.refund_amount || 0;
    setRefundAmount(amt);
    setAdminNotes('');
    setApproveModalVisible(true);
  };

  const handleRejectClick = (refund: RefundItem) => {
    setCurrentRefund(refund);
    setRejectReason('');
    setRejectModalVisible(false);
    setTimeout(() => setRejectModalVisible(true), 0);
  };

  const submitApprove = async () => {
    if (!currentRefund) return;
    setApproveLoading(true);
    try {
      const params: any = {};
      if (refundType === 'partial') {
        params.refund_amount = refundAmount;
      }
      if (adminNotes) params.admin_notes = adminNotes;
      await post(`/api/admin/refunds/${currentRefund.id}/approve`, params);
      message.success('退款审核通过，退款已执行');
      setApproveModalVisible(false);
      fetchRefunds(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.detail || '退款操作失败';
      message.error(typeof detail === 'object' ? detail.message || JSON.stringify(detail) : String(detail));
    } finally {
      setApproveLoading(false);
    }
  };

  const submitReject = async () => {
    if (!currentRefund) return;
    setRejectLoading(true);
    try {
      await post(`/api/admin/refunds/${currentRefund.id}/reject`, { admin_notes: rejectReason });
      message.success('退款申请已驳回');
      setRejectModalVisible(false);
      fetchRefunds(pagination.current, pagination.pageSize);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '驳回失败');
    } finally {
      setRejectLoading(false);
    }
  };

  const handleRetry = async (refund: RefundItem) => {
    Modal.confirm({
      title: '确认重试退款？',
      icon: <ExclamationCircleOutlined />,
      content: '将重新向支付平台发起退款请求',
      onOk: async () => {
        try {
          await post(`/api/admin/refunds/${refund.id}/retry`);
          message.success('退款重试已提交');
          fetchRefunds(pagination.current, pagination.pageSize);
        } catch (e: any) {
          message.error(e?.response?.data?.detail || '重试失败');
        }
      },
    });
  };

  const showDetail = async (refund: RefundItem) => {
    setCurrentRefund(refund);
    setDetailVisible(true);
    setDetailLoading(true);
    try {
      const res: any = await get(`/api/admin/refunds/${refund.id}`);
      setCurrentRefund(res);
    } catch (e) {
      console.error('getRefundDetail error', e);
    } finally {
      setDetailLoading(false);
    }
  };

  const tabItems = [
    { key: 'all', label: '全部' },
    { key: 'pending', label: '待审核' },
    { key: 'approved', label: '待退款' },
    { key: 'completed', label: '已完成' },
    { key: 'rejected', label: '已驳回' },
  ];

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '订单号',
      dataIndex: ['order', 'order_no'],
      key: 'order_no',
      width: 160,
      render: (_: any, record: RefundItem) => record.order?.order_no || '-',
    },
    {
      title: '用户',
      key: 'user',
      width: 130,
      render: (_: any, record: RefundItem) =>
        record.user ? `${record.user.nickname || ''} ${record.user.phone || ''}`.trim() || '-' : '-',
    },
    {
      title: '退款金额',
      key: 'amount',
      width: 100,
      render: (_: any, record: RefundItem) => `¥${(record.refund_amount_approved || record.refund_amount || 0).toFixed(2)}`,
    },
    {
      title: '类型',
      dataIndex: 'refund_type',
      key: 'refund_type',
      width: 80,
      render: (v: string) => v === 'partial' ? <Tag color="orange">部分</Tag> : v === 'full' ? <Tag color="green">全额</Tag> : '-',
    },
    {
      title: '渠道',
      dataIndex: 'refund_channel',
      key: 'refund_channel',
      width: 80,
      render: (v: string) => channelMap[v] || v || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (v: string) => {
        const item = statusMap[v] || { color: 'default', text: v };
        return <Tag color={item.color}>{item.text}</Tag>;
      },
    },
    {
      title: '退款原因',
      dataIndex: 'reason',
      key: 'reason',
      width: 150,
      ellipsis: true,
    },
    {
      title: '申请时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 130,
      render: (v: string) => v ? dayjs(v).format('MM-DD HH:mm') : '-',
    },
    {
      title: '操作',
      key: 'actions',
      width: 240,
      fixed: 'right' as const,
      render: (_: any, record: RefundItem) => (
        <Space size="small">
          <Button size="small" onClick={() => showDetail(record)}>详情</Button>
          {(record.status === 'pending' || record.status === 'reviewing') && (
            <>
              <Button size="small" type="primary" onClick={() => handleApproveClick(record)}>退款</Button>
              <Button size="small" danger onClick={() => handleRejectClick(record)}>驳回</Button>
            </>
          )}
          {record.status === 'approved' && (
            <Button size="small" onClick={() => handleRetry(record)}>重试</Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3} style={{ marginBottom: 16 }}>退款管理</Title>

      <Tabs
        activeKey={activeTab}
        onChange={(key) => { setActiveTab(key); }}
        items={tabItems}
        style={{ marginBottom: 16 }}
      />

      <Table
        columns={columns}
        dataSource={refunds}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: (total: number) => `共 ${total} 条`,
        }}
        onChange={handleTableChange}
        scroll={{ x: 1200 }}
        size="middle"
      />

      {/* 退款详情抽屉 */}
      <Modal
        title="退款详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={700}
        destroyOnClose
      >
        <Spin spinning={detailLoading}>
          {currentRefund && (
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="退款ID">{currentRefund.id}</Descriptions.Item>
              <Descriptions.Item label="订单号">{currentRefund.order?.order_no || '-'}</Descriptions.Item>
              <Descriptions.Item label="用户">
                {currentRefund.user ? `${currentRefund.user.nickname || ''} (${currentRefund.user.phone || ''})` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="退款金额">¥{(currentRefund.refund_amount || 0).toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="批准金额">¥{(currentRefund.refund_amount_approved || 0).toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="退款类型">
                {currentRefund.refund_type ? <Tag>{currentRefund.refund_type === 'full' ? '全额退款' : '部分退款'}</Tag> : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="退款渠道">
                {currentRefund.refund_channel ? channelMap[currentRefund.refund_channel] || currentRefund.refund_channel : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                <Tag color={statusMap[currentRefund.status]?.color}>{statusMap[currentRefund.status]?.text || currentRefund.status}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="退款单号">{currentRefund.refund_transaction_id || '-'}</Descriptions.Item>
              <Descriptions.Item label="有核销记录" span={2}>
                {currentRefund.has_redemption ? <Tag color="orange">是</Tag> : '否'}
              </Descriptions.Item>
              <Descriptions.Item label="退款原因" span={2}>{currentRefund.reason || '-'}</Descriptions.Item>
              <Descriptions.Item label="管理员备注" span={2}>{currentRefund.admin_notes || '-'}</Descriptions.Item>
              <Descriptions.Item label="申请时间">{currentRefund.created_at ? dayjs(currentRefund.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</Descriptions.Item>
              <Descriptions.Item label="更新时间">{currentRefund.updated_at ? dayjs(currentRefund.updated_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</Descriptions.Item>
            </Descriptions>
          )}
        </Spin>
      </Modal>

      {/* 退款审批弹窗 */}
      <Modal
        title="退款审批"
        open={approveModalVisible}
        onOk={submitApprove}
        onCancel={() => setApproveModalVisible(false)}
        confirmLoading={approveLoading}
        okText="确认退款"
        destroyOnClose
      >
        {currentRefund && (
          <>
            <Descriptions column={1} size="small" style={{ marginBottom: 16 }}>
              <Descriptions.Item label="订单号">{currentRefund.order?.order_no || '-'}</Descriptions.Item>
              <Descriptions.Item label="申请金额">¥{(currentRefund.refund_amount || 0).toFixed(2)}</Descriptions.Item>
              <Descriptions.Item label="退款渠道">
                {currentRefund.refund_channel ? channelMap[currentRefund.refund_channel] || currentRefund.refund_channel : '自动识别'}
              </Descriptions.Item>
            </Descriptions>
            <div style={{ marginBottom: 12 }}>
              <Text strong>退款类型：</Text>
              <Select
                value={refundType}
                onChange={(val) => {
                  setRefundType(val);
                  if (val === 'full') setRefundAmount(currentRefund.refund_amount || 0);
                }}
                style={{ width: 120, marginLeft: 8 }}
              >
                <Select.Option value="full">全额退款</Select.Option>
                <Select.Option value="partial">部分退款</Select.Option>
              </Select>
            </div>
            {refundType === 'partial' && (
              <div style={{ marginBottom: 12 }}>
                <Text strong>退款金额（元）：</Text>
                <InputNumber
                  min={0.01}
                  max={currentRefund.refund_amount || 0}
                  value={refundAmount}
                  onChange={(v) => setRefundAmount(v || 0)}
                  precision={2}
                  style={{ width: 150, marginLeft: 8 }}
                />
              </div>
            )}
            <div>
              <Text strong>备注：</Text>
              <TextArea
                rows={2}
                value={adminNotes}
                onChange={(e) => setAdminNotes(e.target.value)}
                placeholder="可选：审批备注"
                style={{ marginTop: 8 }}
              />
            </div>
          </>
        )}
      </Modal>

      {/* 驳回弹窗 */}
      <Modal
        title="驳回退款申请"
        open={rejectModalVisible}
        onOk={submitReject}
        onCancel={() => setRejectModalVisible(false)}
        confirmLoading={rejectLoading}
        okText="确认驳回"
        okButtonProps={{ danger: true }}
        destroyOnClose
      >
        <div>
          <Text strong>驳回理由：</Text>
          <TextArea
            rows={3}
            value={rejectReason}
            onChange={(e) => setRejectReason(e.target.value)}
            placeholder="请填写驳回理由"
            style={{ marginTop: 8 }}
          />
        </div>
      </Modal>
    </div>
  );
}
