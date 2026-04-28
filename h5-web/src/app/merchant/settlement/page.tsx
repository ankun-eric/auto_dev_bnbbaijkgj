'use client';

import React, { useEffect, useState } from 'react';
import { Table, Typography, Tag, Space, Button, Modal, Input, message } from 'antd';
import api from '@/lib/api';
import dayjs from 'dayjs';
import Link from 'next/link';

const { Title } = Typography;

const statusMap: Record<string, { text: string; color: string }> = {
  pending: { text: '待确认', color: 'orange' },
  confirmed: { text: '已确认', color: 'blue' },
  dispute: { text: '异议中', color: 'red' },
  paid: { text: '已结清', color: 'green' },
};

export default function SettlementPage() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [disputeOpen, setDisputeOpen] = useState(false);
  const [currentId, setCurrentId] = useState<number | null>(null);
  const [reason, setReason] = useState('');

  const load = async () => {
    setLoading(true);
    try {
      const res: any = await api.get('/api/merchant/v1/settlements');
      setRows(res || []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '加载失败');
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const confirm = async (id: number) => {
    try {
      await api.post(`/api/merchant/v1/settlements/${id}/confirm`);
      message.success('已确认');
      load();
    } catch (e: any) { message.error(e?.response?.data?.detail || '操作失败'); }
  };

  const submitDispute = async () => {
    if (!currentId) return;
    try {
      await api.post(`/api/merchant/v1/settlements/${currentId}/dispute`, { reason });
      message.success('已发起异议');
      setDisputeOpen(false);
      setReason('');
      load();
    } catch (e: any) { message.error(e?.response?.data?.detail || '操作失败'); }
  };

  return (
    <div>
      <Title level={4}>对账结算</Title>
      <Table
        rowKey="id"
        dataSource={rows}
        loading={loading}
        pagination={{ pageSize: 20 }}
        columns={[
          { title: '账单号', dataIndex: 'statement_no' },
          { title: '账单周期', render: (_: any, r: any) => `${r.period_start || '-'} ~ ${r.period_end || '-'}` },
          { title: '维度', dataIndex: 'dim', render: (v: string) => v === 'merchant' ? '机构合并' : '门店' },
          { title: '门店ID', dataIndex: 'store_id' },
          { title: '订单数', dataIndex: 'order_count' },
          { title: '应结金额', dataIndex: 'settlement_amount', render: (v: number) => `¥${v || 0}` },
          { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={statusMap[s]?.color || 'default'}>{statusMap[s]?.text || s}</Tag> },
          { title: '确认时间', dataIndex: 'confirmed_at', render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
          {
            title: '操作', render: (_: any, row: any) => (
              <Space>
                {row.status === 'pending' && <Button size="small" type="link" onClick={() => confirm(row.id)}>确认</Button>}
                {row.status === 'pending' && (
                  <Button size="small" type="link" danger onClick={() => { setCurrentId(row.id); setDisputeOpen(true); }}>异议</Button>
                )}
                <Link href={`/merchant/settlement/${row.id}`}>详情</Link>
              </Space>
            ),
          },
        ] as any}
      />

      <Modal
        title="发起异议"
        open={disputeOpen}
        onCancel={() => setDisputeOpen(false)}
        onOk={submitDispute}
      >
        <Input.TextArea rows={4} placeholder="请描述异议原因，平台客服将跟进处理" value={reason} onChange={e => setReason(e.target.value)} />
      </Modal>
    </div>
  );
}
