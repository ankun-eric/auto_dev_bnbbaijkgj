'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Input, Space, Tag, Modal, Descriptions, message, Typography, Avatar, Popconfirm, Tooltip, Form } from 'antd';
import { SearchOutlined, UserOutlined, EyeOutlined, StopOutlined, CheckCircleOutlined, EditOutlined } from '@ant-design/icons';
import { get, put } from '@/lib/api';
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
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => { setCurrentUser(record); setDetailVisible(true); }}>
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
        width={600}
      >
        {currentUser && (
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
