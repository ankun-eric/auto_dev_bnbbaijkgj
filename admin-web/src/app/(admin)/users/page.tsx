'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Input, Space, Tag, Modal, Descriptions, message, Typography, Avatar, Popconfirm, Tooltip, Form, Card, InputNumber } from 'antd';
import { SearchOutlined, UserOutlined, EyeOutlined, StopOutlined, CheckCircleOutlined, EditOutlined, CrownOutlined } from '@ant-design/icons';
import { get, post, put } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

type UserStatus = 'active' | 'disabled' | 'banned';

interface UserRecord {
  id: number;
  phone: string;
  nickname: string;
  avatar?: string;
  role: string;
  level: string;
  points: number;
  status: UserStatus;
  createdAt: string;
  userNo: string;
  referrerNo: string;
  referrerNickname: string;
}

function mapApiUser(row: Record<string, unknown>): UserRecord {
  const statusRaw = row.status;
  const status: UserStatus =
    statusRaw === 'active' || statusRaw === 'disabled' || statusRaw === 'banned'
      ? statusRaw
      : 'active';

  return {
    id: Number(row.id),
    phone: String(row.phone ?? ''),
    nickname: String(row.nickname ?? ''),
    avatar: row.avatar != null ? String(row.avatar) : undefined,
    role: String(row.role ?? 'user'),
    level: String(row.member_level ?? ''),
    points: Number(row.points ?? 0),
    status,
    createdAt: String(row.created_at ?? ''),
    userNo: String(row.user_no ?? ''),
    referrerNo: String(row.referrer_no ?? ''),
    referrerNickname: String(row.referrer_nickname ?? ''),
  };
}

function isActiveStatus(s: UserStatus): boolean {
  return s === 'active';
}

export default function UsersPage() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchPhone, setSearchPhone] = useState('');
  const [searchNickname, setSearchNickname] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [detailVisible, setDetailVisible] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserRecord | null>(null);
  // [会员中心 PRD v1.0] 用户详情会员信息卡片
  const [memberInfo, setMemberInfo] = useState<any | null>(null);
  const [memberLoading, setMemberLoading] = useState(false);
  const [extendDays, setExtendDays] = useState<number>(30);
  const [isSuperuser, setIsSuperuser] = useState(false);
  const [referrerModalVisible, setReferrerModalVisible] = useState(false);
  const [referrerTarget, setReferrerTarget] = useState<UserRecord | null>(null);
  const [referrerForm] = Form.useForm();
  const [referrerSaving, setReferrerSaving] = useState(false);

  useEffect(() => {
    fetchData();
    try {
      const stored = localStorage.getItem('admin_user');
      if (stored) {
        const u = JSON.parse(stored);
        setIsSuperuser(!!u.is_superuser);
      }
    } catch {}
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const keyword = [searchPhone, searchNickname].filter(Boolean).join(' ').trim();
      const res = await get<{
        items?: Record<string, unknown>[];
        list?: Record<string, unknown>[];
        total?: number;
        page?: number;
        page_size?: number;
      }>('/api/admin/users', {
        page,
        page_size: pageSize,
        ...(keyword ? { keyword } : {}),
      });

      const rawItems = res.items ?? res.list ?? [];
      const items = Array.isArray(rawItems) ? rawItems.map(mapApiUser) : [];
      setUsers(items);
      setPagination((prev) => ({
        ...prev,
        current: res.page ?? page,
        pageSize: res.page_size ?? pageSize,
        total: res.total ?? items.length,
      }));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string } }; message?: string };
      message.error(err?.response?.data?.message || err?.message || '加载用户列表失败');
      setUsers([]);
      setPagination((prev) => ({ ...prev, current: page, pageSize, total: 0 }));
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (record: UserRecord) => {
    const active = isActiveStatus(record.status);
    const nextStatus: UserStatus = active ? 'banned' : 'active';
    try {
      await put(`/api/admin/users/${record.id}/status`, undefined, { params: { status: nextStatus } });
      message.success(active ? '已封禁' : '已解封');
      setUsers((prev) => prev.map((u) => (u.id === record.id ? { ...u, status: nextStatus } : u)));
      setCurrentUser((prev) => (prev && prev.id === record.id ? { ...prev, status: nextStatus } : prev));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string } }; message?: string };
      message.error(err?.response?.data?.message || err?.message || '操作失败');
    }
  };

  const reloadMember = async (userId: number) => {
    setMemberLoading(true);
    try {
      const info = await get<any>(`/api/admin/users/${userId}/membership`);
      setMemberInfo(info);
    } finally {
      setMemberLoading(false);
    }
  };

  const handleMemberAdjust = async (action: 'extend' | 'downgrade' | 'reset_quota') => {
    if (!currentUser) return;
    try {
      const body: any = { action };
      if (action === 'extend') body.days = extendDays;
      await post(`/api/admin/users/${currentUser.id}/membership/adjust`, body);
      message.success(
        action === 'extend' ? `已延长 ${extendDays} 天` :
        action === 'downgrade' ? '已降级为免费会员' : '已重置额度'
      );
      await reloadMember(currentUser.id);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '操作失败');
    }
  };

  const handleUpdateReferrer = async () => {
    try {
      const values = await referrerForm.validateFields();
      setReferrerSaving(true);
      await put(`/api/admin/users/${referrerTarget!.id}/referrer`, { referrer_no: values.referrer_no });
      message.success('推荐人修改成功');
      setReferrerModalVisible(false);
      referrerForm.resetFields();
      setReferrerTarget(null);
      fetchData(pagination.current, pagination.pageSize);
    } catch (e: unknown) {
      const err = e as { response?: { data?: { message?: string } }; message?: string; errorFields?: unknown };
      if ((err as any).errorFields) return;
      message.error(err?.response?.data?.message || err?.message || '修改推荐人失败');
    } finally {
      setReferrerSaving(false);
    }
  };

  const roleMap: Record<string, { color: string; text: string }> = {
    user: { color: 'blue', text: '普通用户' },
    vip: { color: 'gold', text: 'VIP用户' },
    admin: { color: 'red', text: '管理员' },
  };

  const statusTag = (status: UserStatus) => {
    if (status === 'active') return <Tag color="green">正常</Tag>;
    if (status === 'banned') return <Tag color="red">封禁</Tag>;
    if (status === 'disabled') return <Tag color="orange">禁用</Tag>;
    return <Tag>{status}</Tag>;
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    { title: '手机号', dataIndex: 'phone', key: 'phone', width: 130 },
    { title: '用户编号', dataIndex: 'userNo', key: 'userNo', width: 120 },
    {
      title: '昵称',
      dataIndex: 'nickname',
      key: 'nickname',
      width: 120,
      render: (v: string, r: UserRecord) => (
        <Space>
          <Avatar size="small" icon={<UserOutlined />} src={r.avatar} style={{ backgroundColor: '#52c41a' }} />
          {v}
        </Space>
      ),
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 100,
      render: (v: string) => {
        const r = roleMap[v] || { color: 'default', text: v };
        return <Tag color={r.color}>{r.text}</Tag>;
      },
    },
    { title: '等级', dataIndex: 'level', key: 'level', width: 100 },
    { title: '积分', dataIndex: 'points', key: 'points', width: 80 },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: UserStatus) => statusTag(v),
    },
    {
      title: '推荐人',
      dataIndex: 'referrerNickname',
      key: 'referrerNickname',
      width: 120,
      render: (v: string, r: UserRecord) =>
        v ? (
          <Tooltip title={`推荐人编号: ${r.referrerNo}`}>{v}</Tooltip>
        ) : (
          '—'
        ),
    },
    {
      title: '注册时间',
      dataIndex: 'createdAt',
      key: 'createdAt',
      width: 170,
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '操作',
      key: 'action',
      width: isSuperuser ? 240 : 160,
      render: (_: unknown, record: UserRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={async () => {
            setCurrentUser(record);
            setDetailVisible(true);
            setMemberInfo(null);
            setMemberLoading(true);
            try {
              const info = await get<any>(`/api/admin/users/${record.id}/membership`);
              setMemberInfo(info);
            } catch (e) {
              setMemberInfo({ error: true });
            } finally {
              setMemberLoading(false);
            }
          }}>
            详情
          </Button>
          <Popconfirm
            title={isActiveStatus(record.status) ? '确定封禁该用户？' : '确定解封该用户？'}
            onConfirm={() => handleToggleStatus(record)}
          >
            <Button
              type="link"
              size="small"
              danger={isActiveStatus(record.status)}
              icon={isActiveStatus(record.status) ? <StopOutlined /> : <CheckCircleOutlined />}
            >
              {isActiveStatus(record.status) ? '封禁' : '解封'}
            </Button>
          </Popconfirm>
          {isSuperuser && (
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => {
                setReferrerTarget(record);
                referrerForm.setFieldsValue({ referrer_no: record.referrerNo || '' });
                setReferrerModalVisible(true);
              }}
            >
              推荐人
            </Button>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={4} style={{ marginBottom: 24 }}>用户管理</Title>

      <Space style={{ marginBottom: 16 }} wrap>
        <Input
          placeholder="搜索手机号"
          prefix={<SearchOutlined />}
          value={searchPhone}
          onChange={(e) => setSearchPhone(e.target.value)}
          onPressEnter={() => fetchData(1)}
          style={{ width: 200 }}
          allowClear
        />
        <Input
          placeholder="搜索昵称"
          prefix={<SearchOutlined />}
          value={searchNickname}
          onChange={(e) => setSearchNickname(e.target.value)}
          onPressEnter={() => fetchData(1)}
          style={{ width: 200 }}
          allowClear
        />
        <Button type="primary" onClick={() => fetchData(1)}>搜索</Button>
        <Button onClick={() => { setSearchPhone(''); setSearchNickname(''); setTimeout(() => fetchData(1), 0); }}>重置</Button>
      </Space>

      <Table
        columns={columns}
        dataSource={users}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showQuickJumper: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1400 }}
      />

      <Modal
        title="用户详情"
        open={detailVisible}
        onCancel={() => setDetailVisible(false)}
        footer={null}
        width={720}
      >
        {currentUser && (
          <>
            <Descriptions column={2} bordered size="small">
              <Descriptions.Item label="ID">{currentUser.id}</Descriptions.Item>
              <Descriptions.Item label="用户编号">{currentUser.userNo}</Descriptions.Item>
              <Descriptions.Item label="手机号">{currentUser.phone}</Descriptions.Item>
              <Descriptions.Item label="昵称">{currentUser.nickname}</Descriptions.Item>
              <Descriptions.Item label="角色">
                <Tag color={roleMap[currentUser.role]?.color}>{roleMap[currentUser.role]?.text || currentUser.role}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="会员等级">{currentUser.level}</Descriptions.Item>
              <Descriptions.Item label="积分">{currentUser.points}</Descriptions.Item>
              <Descriptions.Item label="状态">{statusTag(currentUser.status)}</Descriptions.Item>
              <Descriptions.Item label="推荐人">
                {currentUser.referrerNickname ? `${currentUser.referrerNickname} (${currentUser.referrerNo})` : '—'}
              </Descriptions.Item>
              <Descriptions.Item label="注册时间">{dayjs(currentUser.createdAt).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
            </Descriptions>

            {/* [会员中心 PRD v1.0] 会员信息卡片 */}
            <Card
              size="small"
              loading={memberLoading}
              style={{ marginTop: 16, borderColor: memberInfo?.membership_level === 'paid' ? '#D4AF37' : undefined }}
              title={
                <Space>
                  <CrownOutlined style={{ color: memberInfo?.membership_level === 'paid' ? '#D4AF37' : '#999' }} />
                  <span>会员信息</span>
                  {memberInfo?.membership_level === 'paid' && <Tag color="gold">付费会员</Tag>}
                  {memberInfo?.membership_level === 'free' && <Tag>免费会员</Tag>}
                </Space>
              }
            >
              {memberInfo && !memberInfo.error && (
                <>
                  <Descriptions column={2} size="small">
                    <Descriptions.Item label="当前等级">{memberInfo.plan_name || '免费会员'}</Descriptions.Item>
                    <Descriptions.Item label="有效期">
                      {memberInfo.expire_at ? (() => {
                        const days = dayjs(memberInfo.expire_at).diff(dayjs(), 'day');
                        return `${dayjs(memberInfo.expire_at).format('YYYY-MM-DD')}（剩 ${days} 天）`;
                      })() : '长期'}
                    </Descriptions.Item>
                    <Descriptions.Item label="健康档案配额（不含本人）">{memberInfo.max_managed === -1 ? '不限' : memberInfo.max_managed}</Descriptions.Item>
                    <Descriptions.Item label="被守护上限">{memberInfo.max_managed_by === -1 ? '不限' : memberInfo.max_managed_by}</Descriptions.Item>
                    <Descriptions.Item label="AI 外呼提醒上限">{memberInfo.ai_outbound_call_count === -1 ? '不限' : `${memberInfo.ai_outbound_call_count} 次/月`}</Descriptions.Item>
                    <Descriptions.Item label="紧急 AI 呼叫上限">{memberInfo.emergency_ai_call_count === -1 ? '不限' : `${memberInfo.emergency_ai_call_count} 次/月`}</Descriptions.Item>
                  </Descriptions>
                  <Space style={{ marginTop: 12 }} wrap>
                    <Space.Compact>
                      <InputNumber
                        min={1}
                        value={extendDays}
                        onChange={(v) => setExtendDays(Number(v || 30))}
                        style={{ width: 80 }}
                      />
                      <Popconfirm
                        title={`延长 ${extendDays} 天会员期？`}
                        onConfirm={() => handleMemberAdjust('extend')}
                        disabled={memberInfo.membership_level !== 'paid'}
                      >
                        <Button
                          type="primary"
                          disabled={memberInfo.membership_level !== 'paid'}
                        >手动延长会员期</Button>
                      </Popconfirm>
                    </Space.Compact>
                    <Popconfirm title="重置该用户的本月额度？" onConfirm={() => handleMemberAdjust('reset_quota')}>
                      <Button>手动重置额度</Button>
                    </Popconfirm>
                    <Popconfirm
                      title="降级为免费会员？此操作会立即取消该用户的付费订阅。"
                      onConfirm={() => handleMemberAdjust('downgrade')}
                      disabled={memberInfo.membership_level !== 'paid'}
                    >
                      <Button danger disabled={memberInfo.membership_level !== 'paid'}>手动降级</Button>
                    </Popconfirm>
                  </Space>
                </>
              )}
              {memberInfo?.error && <span style={{ color: '#999' }}>加载会员信息失败</span>}
            </Card>
          </>
        )}
      </Modal>

      <Modal
        title={`修改推荐人 - ${referrerTarget?.nickname || ''}`}
        open={referrerModalVisible}
        onCancel={() => { setReferrerModalVisible(false); referrerForm.resetFields(); setReferrerTarget(null); }}
        footer={null}
        destroyOnClose
      >
        <Form form={referrerForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item
            name="referrer_no"
            label="推荐人编号"
            rules={[{ required: true, message: '请输入推荐人编号' }]}
          >
            <Input placeholder="请输入推荐人的用户编号" />
          </Form.Item>
          <Form.Item>
            <Space>
              <Popconfirm
                title="确定修改该用户的推荐人？"
                onConfirm={handleUpdateReferrer}
              >
                <Button type="primary" loading={referrerSaving}>确认修改</Button>
              </Popconfirm>
              <Button onClick={() => { setReferrerModalVisible(false); referrerForm.resetFields(); setReferrerTarget(null); }}>
                取消
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
