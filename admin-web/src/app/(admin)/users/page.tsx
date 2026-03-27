'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Input, Space, Tag, Modal, Descriptions, message, Typography, Avatar, Popconfirm } from 'antd';
import { SearchOutlined, UserOutlined, EyeOutlined, StopOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;

interface UserRecord {
  id: number;
  phone: string;
  nickname: string;
  avatar?: string;
  role: string;
  level: string;
  points: number;
  status: number;
  createdAt: string;
}

const mockUsers: UserRecord[] = [
  { id: 1, phone: '138****1234', nickname: '张三', role: 'user', level: '黄金会员', points: 2580, status: 1, createdAt: '2026-01-15 10:30:00' },
  { id: 2, phone: '139****5678', nickname: '李四', role: 'user', level: '白银会员', points: 1200, status: 1, createdAt: '2026-02-20 14:22:00' },
  { id: 3, phone: '137****9012', nickname: '王五', role: 'vip', level: '钻石会员', points: 8900, status: 1, createdAt: '2025-12-05 09:15:00' },
  { id: 4, phone: '136****3456', nickname: '赵六', role: 'user', level: '普通会员', points: 350, status: 0, createdAt: '2026-03-01 16:48:00' },
  { id: 5, phone: '135****7890', nickname: '孙七', role: 'user', level: '黄金会员', points: 3100, status: 1, createdAt: '2026-01-28 11:30:00' },
  { id: 6, phone: '188****2345', nickname: '周八', role: 'vip', level: '钻石会员', points: 12500, status: 1, createdAt: '2025-11-10 08:20:00' },
  { id: 7, phone: '199****6789', nickname: '吴九', role: 'user', level: '白银会员', points: 980, status: 1, createdAt: '2026-03-15 13:45:00' },
  { id: 8, phone: '177****0123', nickname: '郑十', role: 'user', level: '普通会员', points: 150, status: 0, createdAt: '2026-03-20 17:00:00' },
];

export default function UsersPage() {
  const [users, setUsers] = useState<UserRecord[]>(mockUsers);
  const [loading, setLoading] = useState(false);
  const [searchPhone, setSearchPhone] = useState('');
  const [searchNickname, setSearchNickname] = useState('');
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: mockUsers.length });
  const [detailVisible, setDetailVisible] = useState(false);
  const [currentUser, setCurrentUser] = useState<UserRecord | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get('/api/admin/users', { page, pageSize, phone: searchPhone, nickname: searchNickname });
      if (res.code === 0 && res.data) {
        setUsers(res.data.list || res.data);
        setPagination((prev) => ({ ...prev, current: page, total: res.data.total || res.data.length }));
      }
    } catch {
      let filtered = mockUsers;
      if (searchPhone) filtered = filtered.filter((u) => u.phone.includes(searchPhone));
      if (searchNickname) filtered = filtered.filter((u) => u.nickname.includes(searchNickname));
      setUsers(filtered);
      setPagination((prev) => ({ ...prev, current: page, total: filtered.length }));
    } finally {
      setLoading(false);
    }
  };

  const handleToggleStatus = async (record: UserRecord) => {
    try {
      await post(`/api/admin/users/${record.id}/toggle-status`, { status: record.status === 1 ? 0 : 1 });
      message.success(record.status === 1 ? '已封禁' : '已解封');
    } catch {}
    setUsers((prev) =>
      prev.map((u) => (u.id === record.id ? { ...u, status: u.status === 1 ? 0 : 1 } : u))
    );
  };

  const roleMap: Record<string, { color: string; text: string }> = {
    user: { color: 'blue', text: '普通用户' },
    vip: { color: 'gold', text: 'VIP用户' },
    admin: { color: 'red', text: '管理员' },
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 70 },
    { title: '手机号', dataIndex: 'phone', key: 'phone', width: 130 },
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
      render: (v: number) => (
        <Tag color={v === 1 ? 'green' : 'red'}>{v === 1 ? '正常' : '封禁'}</Tag>
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
      width: 160,
      render: (_: any, record: UserRecord) => (
        <Space>
          <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => { setCurrentUser(record); setDetailVisible(true); }}>
            详情
          </Button>
          <Popconfirm
            title={record.status === 1 ? '确定封禁该用户？' : '确定解封该用户？'}
            onConfirm={() => handleToggleStatus(record)}
          >
            <Button
              type="link"
              size="small"
              danger={record.status === 1}
              icon={record.status === 1 ? <StopOutlined /> : <CheckCircleOutlined />}
            >
              {record.status === 1 ? '封禁' : '解封'}
            </Button>
          </Popconfirm>
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
        scroll={{ x: 1100 }}
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
            <Descriptions.Item label="手机号">{currentUser.phone}</Descriptions.Item>
            <Descriptions.Item label="昵称">{currentUser.nickname}</Descriptions.Item>
            <Descriptions.Item label="角色">
              <Tag color={roleMap[currentUser.role]?.color}>{roleMap[currentUser.role]?.text || currentUser.role}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="会员等级">{currentUser.level}</Descriptions.Item>
            <Descriptions.Item label="积分">{currentUser.points}</Descriptions.Item>
            <Descriptions.Item label="状态">
              <Tag color={currentUser.status === 1 ? 'green' : 'red'}>{currentUser.status === 1 ? '正常' : '封禁'}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="注册时间">{dayjs(currentUser.createdAt).format('YYYY-MM-DD HH:mm:ss')}</Descriptions.Item>
          </Descriptions>
        )}
      </Modal>
    </div>
  );
}
