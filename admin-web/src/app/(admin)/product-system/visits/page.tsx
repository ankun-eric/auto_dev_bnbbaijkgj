'use client';

import React, { useEffect, useState, useCallback } from 'react';
import {
  Table, Button, Space, Tag, message, Typography, Row, Col,
  DatePicker, Select, Card, Statistic, Form, InputNumber, Modal,
} from 'antd';
import { SettingOutlined } from '@ant-design/icons';
import { get, post } from '@/lib/api';
import dayjs from 'dayjs';

const { Title } = Typography;
const { RangePicker } = DatePicker;

interface CheckinRecord {
  id: number;
  user_id: number;
  store_id: number;
  staff_user_id: number | null;
  points_earned: number;
  checked_in_at: string;
  user_nickname: string | null;
  user_phone: string | null;
  store_name: string | null;
}

interface StoreOption {
  label: string;
  value: number;
}

function mapRecord(raw: Record<string, unknown>): CheckinRecord {
  return {
    id: Number(raw.id),
    user_id: Number(raw.user_id ?? 0),
    store_id: Number(raw.store_id ?? 0),
    staff_user_id: raw.staff_user_id ? Number(raw.staff_user_id) : null,
    points_earned: Number(raw.points_earned ?? 0),
    checked_in_at: String(raw.checked_in_at ?? ''),
    user_nickname: raw.user_nickname ? String(raw.user_nickname) : null,
    user_phone: raw.user_phone ? String(raw.user_phone) : null,
    store_name: raw.store_name ? String(raw.store_name) : null,
  };
}

export default function VisitsPage() {
  const [records, setRecords] = useState<CheckinRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [dateRange, setDateRange] = useState<[dayjs.Dayjs | null, dayjs.Dayjs | null] | null>(null);
  const [storeOptions, setStoreOptions] = useState<StoreOption[]>([]);
  const [filterStore, setFilterStore] = useState<number | undefined>(undefined);
  const [configVisible, setConfigVisible] = useState(false);
  const [configForm] = Form.useForm();
  const [stats, setStats] = useState({ total: 0, today: 0, totalPoints: 0 });

  const fetchStores = useCallback(async () => {
    try {
      const res = await get('/api/admin/merchant/stores');
      if (res) {
        const items = res.items || res.list || res;
        if (Array.isArray(items)) {
          setStoreOptions(items.map((s: any) => ({ label: String(s.store_name || s.name || ''), value: Number(s.id) })));
        }
      }
    } catch {}
  }, []);

  const fetchData = useCallback(async (page = 1, pageSize = 10) => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, page_size: pageSize };
      if (filterStore) params.store_id = filterStore;

      const res = await get('/api/admin/checkin-records', params);
      if (res) {
        const raw = res.items || res.list || res;
        const items = Array.isArray(raw) ? raw.map((r: Record<string, unknown>) => mapRecord(r)) : [];
        setRecords(items);
        setPagination(prev => ({ ...prev, current: page, total: res.total ?? items.length }));

        const today = dayjs().format('YYYY-MM-DD');
        const todayRecords = items.filter(r => r.checked_in_at.startsWith(today));
        const totalPoints = items.reduce((sum, r) => sum + r.points_earned, 0);
        setStats({
          total: res.total ?? items.length,
          today: todayRecords.length,
          totalPoints,
        });
      }
    } catch {
      setRecords([]);
      setPagination(prev => ({ ...prev, current: page, total: 0 }));
    } finally {
      setLoading(false);
    }
  }, [filterStore]);

  useEffect(() => {
    fetchStores();
    fetchData();
  }, []);

  const handleSearch = () => fetchData(1, pagination.pageSize);

  const handleSaveConfig = async () => {
    try {
      const values = await configForm.validateFields();
      await post('/api/admin/checkin-config', {
        points_per_checkin: values.points_per_checkin,
        daily_limit: values.daily_limit,
      });
      message.success('配置已保存');
      setConfigVisible(false);
    } catch (err: any) {
      if (err?.errorFields) return;
      message.error(err?.response?.data?.detail || '保存失败');
    }
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '用户', key: 'user', width: 150,
      render: (_: unknown, record: CheckinRecord) => (
        <div>
          <div>{record.user_nickname || `用户#${record.user_id}`}</div>
          {record.user_phone && <div style={{ color: '#999', fontSize: 12 }}>{record.user_phone}</div>}
        </div>
      ),
    },
    {
      title: '门店', dataIndex: 'store_name', key: 'store_name', width: 150,
      render: (v: string | null, record: CheckinRecord) => v || `门店#${record.store_id}`,
    },
    {
      title: '获得积分', dataIndex: 'points_earned', key: 'points_earned', width: 100,
      render: (v: number) => <span style={{ color: '#faad14', fontWeight: 600 }}>+{v}</span>,
    },
    {
      title: '操作员', dataIndex: 'staff_user_id', key: 'staff_user_id', width: 100,
      render: (v: number | null) => v ? `员工#${v}` : '-',
    },
    {
      title: '签到时间', dataIndex: 'checked_in_at', key: 'checked_in_at', width: 180,
      render: (v: string) => v ? dayjs(v).format('YYYY-MM-DD HH:mm:ss') : '-',
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>进店记录</Title>
        <Button icon={<SettingOutlined />} onClick={() => {
          configForm.setFieldsValue({ points_per_checkin: 5, daily_limit: 1 });
          setConfigVisible(true);
        }}>
          签到积分配置
        </Button>
      </div>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card size="small"><Statistic title="签到总数" value={stats.total} /></Card>
        </Col>
        <Col span={6}>
          <Card size="small"><Statistic title="今日签到" value={stats.today} /></Card>
        </Col>
        <Col span={6}>
          <Card size="small"><Statistic title="发放积分总计" value={stats.totalPoints} suffix="分" /></Card>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col>
          <Select
            placeholder="按门店筛选"
            allowClear
            style={{ width: 180 }}
            options={storeOptions}
            value={filterStore}
            onChange={v => setFilterStore(v)}
          />
        </Col>
        <Col>
          <RangePicker value={dateRange as any} onChange={vals => setDateRange(vals as any)} />
        </Col>
        <Col>
          <Button type="primary" onClick={handleSearch}>搜索</Button>
        </Col>
      </Row>

      <Table
        columns={columns}
        dataSource={records}
        rowKey="id"
        loading={loading}
        pagination={{
          ...pagination,
          showSizeChanger: true,
          showTotal: total => `共 ${total} 条`,
          onChange: (page, pageSize) => fetchData(page, pageSize),
        }}
        scroll={{ x: 800 }}
      />

      {/* 签到积分配置弹窗 */}
      <Modal
        title="签到积分配置"
        open={configVisible}
        onOk={handleSaveConfig}
        onCancel={() => setConfigVisible(false)}
        destroyOnClose
      >
        <Form form={configForm} layout="vertical" style={{ marginTop: 16 }}>
          <Form.Item label="每次签到积分" name="points_per_checkin" rules={[{ required: true, message: '请输入积分值' }]}>
            <InputNumber min={0} style={{ width: '100%' }} placeholder="5" />
          </Form.Item>
          <Form.Item label="每日签到次数限制" name="daily_limit" rules={[{ required: true, message: '请输入限制次数' }]}>
            <InputNumber min={1} style={{ width: '100%' }} placeholder="1" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
}
