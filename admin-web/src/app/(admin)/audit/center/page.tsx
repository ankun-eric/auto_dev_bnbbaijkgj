'use client';

import React, { useEffect, useState } from 'react';
import {
  Table, Button, Tag, Space, Modal, Input, Form, Select, message, Typography, Drawer, Descriptions,
  Row, Col, DatePicker, Tooltip,
} from 'antd';
import { CheckOutlined, CloseOutlined, RollbackOutlined, SendOutlined, EyeOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title, Paragraph } = Typography;

const STATUS_MAP: Record<string, { label: string; color: string }> = {
  pending: { label: '待审核', color: 'orange' },
  approved: { label: '已通过', color: 'green' },
  rejected: { label: '已驳回', color: 'red' },
  returned: { label: '已退回', color: 'gold' },
  resubmitted: { label: '已重新提交', color: 'blue' },
};

const RISK_MAP: Record<string, { label: string; color: string }> = {
  low: { label: '低风险', color: 'green' },
  high: { label: '高风险', color: 'red' },
};

const BIZ_MAP: Record<string, string> = {
  coupon_grant: '券发放',
  coupon_recall: '券回收',
  redeem_batch: '兑换码批次',
};

export default function AuditCenterPage() {
  const [items, setItems] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<any>({});

  const [detail, setDetail] = useState<any>(null);
  const [detailOpen, setDetailOpen] = useState(false);

  const [approveOpen, setApproveOpen] = useState(false);
  const [approveTarget, setApproveTarget] = useState<any>(null);
  const [code, setCode] = useState('');
  const [phone, setPhone] = useState('');
  const [phones, setPhones] = useState<any[]>([]);
  const [sending, setSending] = useState(false);

  const [returnOpen, setReturnOpen] = useState(false);
  const [returnTarget, setReturnTarget] = useState<any>(null);
  const [returnReason, setReturnReason] = useState('');

  const fetchData = async () => {
    setLoading(true);
    try {
      const params: any = { page: 1, page_size: 100 };
      if (filters.status) params.status = filters.status;
      if (filters.risk) params.risk_level = filters.risk;
      if (filters.biz) params.business_type = filters.biz;
      const res: any = await get('/api/admin/audit/requests', params);
      setItems(res?.items || []);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);
  useEffect(() => {
    get('/api/admin/audit/phones').then((r: any) => {
      const enabled = (r?.items || []).filter((p: any) => p.enabled);
      setPhones(enabled);
      if (enabled[0]) setPhone(enabled[0].phone);
    }).catch(() => {});
  }, []);

  const openDetail = async (r: any) => {
    try {
      const d: any = await get(`/api/admin/audit/requests/${r.id}`);
      setDetail(d);
      setDetailOpen(true);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '加载失败');
    }
  };

  const openApprove = (r: any) => {
    setApproveTarget(r);
    setCode('');
    setApproveOpen(true);
  };

  const sendCode = async () => {
    if (!phone) return message.error('请选择审核手机号');
    setSending(true);
    try {
      const res: any = await post('/api/admin/audit/codes/send', { phone, request_id: approveTarget?.id });
      if (res?.dev_code) message.info(`【调试】验证码：${res.dev_code}`);
      else message.success('验证码已发送');
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '发送失败');
    } finally {
      setSending(false);
    }
  };

  const submitApprove = async () => {
    if (!approveTarget) return;
    if (!code || code.length !== 6) return message.error('请输入 6 位验证码');
    try {
      await post('/api/admin/audit/approve', {
        request_id: approveTarget.id, phone, code,
      });
      message.success('审核操作已提交');
      setApproveOpen(false);
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '审核失败');
    }
  };

  const openReturn = (r: any) => {
    setReturnTarget(r);
    setReturnReason('');
    setReturnOpen(true);
  };
  const submitReturn = async () => {
    if (!returnReason.trim()) return message.error('退回原因必填');
    try {
      await post('/api/admin/audit/return', { request_id: returnTarget.id, reason: returnReason });
      message.success('已退回，申请人可修改后重新提交');
      setReturnOpen(false);
      fetchData();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '退回失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 70 },
    { title: '业务类型', dataIndex: 'business_type', width: 130,
      render: (v: string) => BIZ_MAP[v] || v },
    { title: '标题', dataIndex: 'title' },
    { title: '风险', dataIndex: 'risk_level', width: 100,
      render: (v: string) => {
        const r = RISK_MAP[v] || { label: v, color: 'default' };
        return <Tag color={r.color}>{r.label}</Tag>;
      } },
    { title: '审批模式', dataIndex: 'approval_mode', width: 110,
      render: (v: string) => v === 'joint' ? <Tag color="purple">联合审批</Tag> : <Tag>任一审批</Tag> },
    { title: '申请人', dataIndex: 'requester_name', width: 120,
      render: (_: any, r: any) => r.requester_name || `用户#${r.requester_id || '-'}` },
    { title: '状态', dataIndex: 'status', width: 110,
      render: (v: string) => {
        const s = STATUS_MAP[v] || { label: v, color: 'default' };
        return <Tag color={s.color}>{s.label}</Tag>;
      } },
    { title: '已审批', key: 'aps', width: 110,
      render: (_: any, r: any) => `${r.approved_count || 0} / ${r.required_approvals || 1}` },
    { title: '提交时间', dataIndex: 'created_at', width: 160,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm') : '-' },
    {
      title: '操作', key: 'a', width: 280, fixed: 'right' as const,
      render: (_: any, r: any) => (
        <Space size={0}>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => openDetail(r)}>详情</Button>
          {r.status === 'pending' && (
            <>
              <Tooltip title="发送短信验证码后审批通过">
                <Button type="link" size="small" icon={<CheckOutlined />} onClick={() => openApprove(r)}>审批</Button>
              </Tooltip>
              <Button type="link" size="small" danger icon={<RollbackOutlined />} onClick={() => openReturn(r)}>退回</Button>
            </>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4}>审核中心（资金安全）</Title>
      <Paragraph type="secondary">
        风险分级：低风险 (≤10元 且 ≤100张) 任一审核员通过即可；
        高风险 (&gt;50元、&gt;1000张、&gt;500个唯一兑换码或全员发放) 需联合审批。
      </Paragraph>
      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col><Select placeholder="状态" allowClear style={{ width: 120 }}
          options={Object.entries(STATUS_MAP).map(([k, v]) => ({ label: v.label, value: k }))}
          value={filters.status} onChange={v => setFilters((f: any) => ({ ...f, status: v }))} /></Col>
        <Col><Select placeholder="风险等级" allowClear style={{ width: 120 }}
          options={Object.entries(RISK_MAP).map(([k, v]) => ({ label: v.label, value: k }))}
          value={filters.risk} onChange={v => setFilters((f: any) => ({ ...f, risk: v }))} /></Col>
        <Col><Select placeholder="业务类型" allowClear style={{ width: 140 }}
          options={Object.entries(BIZ_MAP).map(([k, v]) => ({ label: v, value: k }))}
          value={filters.biz} onChange={v => setFilters((f: any) => ({ ...f, biz: v }))} /></Col>
        <Col><Button type="primary" onClick={fetchData}>查询</Button></Col>
      </Row>
      <Table rowKey="id" loading={loading} dataSource={items} columns={columns} scroll={{ x: 1500 }} />

      {/* 详情 */}
      <Drawer title={`审核单详情 #${detail?.id || ''}`} width={700}
        open={detailOpen} onClose={() => setDetailOpen(false)}>
        {detail && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="业务类型">{BIZ_MAP[detail.business_type] || detail.business_type}</Descriptions.Item>
            <Descriptions.Item label="标题">{detail.title}</Descriptions.Item>
            <Descriptions.Item label="描述">{detail.description || '-'}</Descriptions.Item>
            <Descriptions.Item label="风险等级">{RISK_MAP[detail.risk_level]?.label}</Descriptions.Item>
            <Descriptions.Item label="审批模式">{detail.approval_mode === 'joint' ? '联合审批（≥2 人）' : '任一审批'}</Descriptions.Item>
            <Descriptions.Item label="估算金额/数量">¥{detail.est_amount || 0} / {detail.est_count || 0} 张</Descriptions.Item>
            <Descriptions.Item label="状态">{STATUS_MAP[detail.status]?.label}</Descriptions.Item>
            <Descriptions.Item label="申请人">{detail.requester_name || `用户#${detail.requester_id || '-'}`}</Descriptions.Item>
            <Descriptions.Item label="提交时间">{detail.created_at && dayjs(detail.created_at).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
            <Descriptions.Item label="审批历史">
              <pre style={{ fontSize: 12 }}>{JSON.stringify(detail.approval_history || [], null, 2)}</pre>
            </Descriptions.Item>
            <Descriptions.Item label="退回原因">{detail.return_reason || '-'}</Descriptions.Item>
            <Descriptions.Item label="提交内容（payload）">
              <pre style={{ fontSize: 12, maxHeight: 320, overflow: 'auto' }}>{JSON.stringify(detail.payload || {}, null, 2)}</pre>
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>

      {/* 审批弹窗 */}
      <Modal title={`审批：${approveTarget?.title || ''}`} open={approveOpen}
        onOk={submitApprove} onCancel={() => setApproveOpen(false)} okText="确认通过" destroyOnClose>
        <Form layout="vertical">
          <Form.Item label="审核手机号" required>
            <Select value={phone} onChange={setPhone}
              options={phones.map(p => ({ label: `${p.phone}（${p.notes || ''}）`, value: p.phone }))} />
          </Form.Item>
          <Form.Item label="6 位短信验证码" required>
            <Space.Compact style={{ width: '100%' }}>
              <Input value={code} onChange={e => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                maxLength={6} placeholder="请输入 6 位数字" />
              <Button type="primary" loading={sending} icon={<SendOutlined />} onClick={sendCode}>发送验证码</Button>
            </Space.Compact>
          </Form.Item>
        </Form>
        <Paragraph type="secondary" style={{ fontSize: 12 }}>
          验证码有效期 5 分钟；连续 3 次错误将锁定该手机号 10 分钟。
        </Paragraph>
      </Modal>

      {/* 退回弹窗 */}
      <Modal title={`退回审核单 #${returnTarget?.id || ''}`} open={returnOpen}
        onOk={submitReturn} onCancel={() => setReturnOpen(false)} okText="确认退回" okButtonProps={{ danger: true }}>
        <Form layout="vertical">
          <Form.Item label="退回原因（必填）" required>
            <Input.TextArea rows={4} value={returnReason} onChange={e => setReturnReason(e.target.value)}
              placeholder="请说明需要修改的内容" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
