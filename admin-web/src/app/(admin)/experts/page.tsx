'use client';

import React, { useEffect, useState } from 'react';
import { Table, Button, Space, Modal, Form, Input, Select, Switch, Rate, Tag, message, Typography, Avatar } from 'antd';
import { PlusOutlined, EditOutlined, CalendarOutlined, UserOutlined } from '@ant-design/icons';
import { get, post, put } from '@/lib/api';

const { Title } = Typography;
const { TextArea } = Input;

/** 后端 GET /api/admin/experts 单条结构 */
interface ExpertApiItem {
  id: number;
  name: string;
  title: string;
  hospital: string;
  department: string;
  specialties: string;
  avatar: string | null;
  consultation_fee: number;
  rating: number;
  status: 'active' | 'deleted';
  created_at: string;
  introduction?: string;
}

/** 表格与表单使用的归一化结构（由 API 映射而来） */
interface Expert {
  id: number;
  name: string;
  avatar: string | null;
  title: string;
  hospital: string;
  department: string;
  specialty: string;
  rating: number;
  consultation_fee: number;
  status: 'active' | 'deleted';
  intro: string;
  createdAt: string;
}

function mapApiItemToExpert(row: ExpertApiItem): Expert {
  return {
    id: row.id,
    name: row.name,
    avatar: row.avatar,
    title: row.title,
    hospital: row.hospital,
    department: row.department,
    specialty: row.specialties ?? '',
    rating: row.rating,
    consultation_fee: row.consultation_fee,
    status: row.status,
    intro: row.introduction ?? '',
    createdAt: row.created_at ?? '',
  };
}

const departmentOptions = [
  { label: '中医科', value: '中医科' },
  { label: '营养科', value: '营养科' },
  { label: '心理科', value: '心理科' },
  { label: '全科', value: '全科' },
  { label: '内科', value: '内科' },
  { label: '康复科', value: '康复科' },
  { label: '运动医学科', value: '运动医学科' },
];

const titleOptions = [
  { label: '主任医师', value: '主任医师' },
  { label: '副主任医师', value: '副主任医师' },
  { label: '主治医师', value: '主治医师' },
  { label: '住院医师', value: '住院医师' },
  { label: '注册营养师', value: '注册营养师' },
  { label: '心理咨询师', value: '心理咨询师' },
];

export default function ExpertsPage() {
  const [experts, setExperts] = useState<Expert[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [scheduleVisible, setScheduleVisible] = useState(false);
  const [editingRecord, setEditingRecord] = useState<Expert | null>(null);
  const [currentExpert, setCurrentExpert] = useState<Expert | null>(null);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [form] = Form.useForm();

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const res = await get<{ items?: ExpertApiItem[]; list?: ExpertApiItem[]; total?: number; page?: number; page_size?: number }>(
        '/api/admin/experts',
        { page, page_size: pageSize }
      );
      const rawItems = res?.items ?? res?.list ?? [];
      const items = Array.isArray(rawItems) ? rawItems.map((row) => mapApiItemToExpert(row as ExpertApiItem)) : [];
      setExperts(items);
      setPagination((prev) => ({
        ...prev,
        current: page,
        pageSize,
        total: res?.total ?? items.length,
      }));
    } catch (e: unknown) {
      const err = e as { response?: { data?: { detail?: string } }; message?: string };
      message.error(err?.response?.data?.detail || err?.message || '加载专家列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingRecord(null);
    form.resetFields();
    form.setFieldsValue({ status: true, rating: 5 });
    setModalVisible(true);
  };

  const handleEdit = (record: Expert) => {
    setEditingRecord(record);
    form.setFieldsValue({ ...record, status: record.status === 'active' });
    setModalVisible(true);
  };

  const buildApiBody = (values: Record<string, unknown>) => {
    const statusBool = Boolean(values.status);
    return {
      name: values.name,
      title: values.title,
      hospital: values.hospital,
      department: values.department,
      rating: values.rating,
      specialties: values.specialty,
      introduction: values.intro,
      status: statusBool ? 'active' : ('deleted' as const),
    };
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      const apiBody = buildApiBody(values);

      if (editingRecord) {
        try {
          await put(`/api/admin/experts/${editingRecord.id}`, apiBody);
          message.success('编辑成功');
          await fetchData(pagination.current, pagination.pageSize);
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: string } }; message?: string };
          message.error(err?.response?.data?.detail || err?.message || '编辑失败');
          return;
        }
      } else {
        try {
          await post('/api/admin/experts', apiBody);
          message.success('新增成功');
          await fetchData(pagination.current, pagination.pageSize);
        } catch (e: unknown) {
          const err = e as { response?: { data?: { detail?: string } }; message?: string };
          message.error(err?.response?.data?.detail || err?.message || '新增失败');
          return;
        }
      }
      setModalVisible(false);
    } catch {
      /* 表单校验失败，antd 已提示 */
    }
  };

  const weekDays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];
  const timeSlots = ['上午 09:00-12:00', '下午 14:00-17:00', '晚上 19:00-21:00'];

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '姓名',
      dataIndex: 'name',
      key: 'name',
      width: 120,
      render: (v: string, r: Expert) => (
        <Space>
          <Avatar size="small" icon={<UserOutlined />} src={r.avatar || undefined} style={{ backgroundColor: '#52c41a' }} />
          {v}
        </Space>
      ),
    },
    { title: '职称', dataIndex: 'title', key: 'title', width: 110 },
    { title: '医院', dataIndex: 'hospital', key: 'hospital', ellipsis: true },
    { title: '科室', dataIndex: 'department', key: 'department', width: 100 },
    {
      title: '评分',
      dataIndex: 'rating',
      key: 'rating',
      width: 140,
      render: (v: number) => <Rate disabled defaultValue={v} allowHalf style={{ fontSize: 14 }} />,
    },
    { title: '咨询次数', dataIndex: 'consultCount', key: 'consultCount', width: 90, render: () => '-' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (v: Expert['status']) => (
        <Tag color={v === 'active' ? 'green' : 'red'}>{v === 'active' ? '在职' : '停诊'}</Tag>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: unknown, record: Expert) => (
        <Space>
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<CalendarOutlined />} onClick={() => { setCurrentExpert(record); setScheduleVisible(true); }}>排班</Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 24 }}>
        <Title level={4} style={{ margin: 0 }}>专家管理</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增专家</Button>
      </div>

      <Table
        columns={columns}
        dataSource={experts}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 1100 }}
      />

      <Modal
        title={editingRecord ? '编辑专家' : '新增专家'}
        open={modalVisible}
        onOk={handleSubmit}
        onCancel={() => setModalVisible(false)}
        width={640}
        destroyOnClose
      >
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="姓名" name="name" rules={[{ required: true, message: '请输入姓名' }]} style={{ flex: 1 }}>
              <Input placeholder="请输入专家姓名" />
            </Form.Item>
            <Form.Item label="职称" name="title" rules={[{ required: true, message: '请选择职称' }]} style={{ flex: 1 }}>
              <Select options={titleOptions} placeholder="请选择职称" />
            </Form.Item>
          </Space>
          <Form.Item label="所属医院" name="hospital" rules={[{ required: true, message: '请输入医院名称' }]}>
            <Input placeholder="请输入医院名称" />
          </Form.Item>
          <Space style={{ width: '100%' }} size={16}>
            <Form.Item label="科室" name="department" rules={[{ required: true, message: '请选择科室' }]} style={{ flex: 1 }}>
              <Select options={departmentOptions} placeholder="请选择科室" />
            </Form.Item>
            <Form.Item label="评分" name="rating" style={{ flex: 1 }}>
              <Rate allowHalf />
            </Form.Item>
          </Space>
          <Form.Item label="擅长领域" name="specialty">
            <Input placeholder="请输入擅长领域，多个用逗号分隔" />
          </Form.Item>
          <Form.Item label="简介" name="intro">
            <TextArea rows={3} placeholder="请输入专家简介" />
          </Form.Item>
          <Form.Item label="在职" name="status" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={`排班管理 - ${currentExpert?.name || ''}`}
        open={scheduleVisible}
        onCancel={() => setScheduleVisible(false)}
        footer={[
          <Button key="close" onClick={() => setScheduleVisible(false)}>关闭</Button>,
          <Button key="save" type="primary" onClick={() => { message.success('排班保存成功'); setScheduleVisible(false); }}>保存排班</Button>,
        ]}
        width={700}
      >
        <div style={{ marginTop: 16 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr>
                <th style={{ padding: '12px 8px', borderBottom: '2px solid #f0f0f0', textAlign: 'left', color: '#666' }}>时段</th>
                {weekDays.map((day) => (
                  <th key={day} style={{ padding: '12px 8px', borderBottom: '2px solid #f0f0f0', textAlign: 'center', color: '#666' }}>{day}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {timeSlots.map((slot, si) => (
                <tr key={slot}>
                  <td style={{ padding: '12px 8px', borderBottom: '1px solid #f0f0f0', fontSize: 13 }}>{slot}</td>
                  {weekDays.map((day, di) => (
                    <td key={day} style={{ padding: '8px', borderBottom: '1px solid #f0f0f0', textAlign: 'center' }}>
                      <Switch
                        size="small"
                        defaultChecked={di < 5 && si < 2}
                      />
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Modal>
    </div>
  );
}
