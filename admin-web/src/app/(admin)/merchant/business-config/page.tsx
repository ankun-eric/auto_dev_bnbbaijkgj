'use client';

/**
 * [订单系统增强 PRD v1.0] 商家营业时间 + 同时段并发上限配置页。
 *
 * 路由：/merchant/business-config
 *
 * 功能：
 * 1. 选择门店（下拉选择当前商家所属的门店；admin 可看所有门店）
 * 2. 周一至周日各自一段或多段营业时间窗（按周）
 * 3. 日期例外（具体日期休息或单独时间窗）
 * 4. 门店级同时段并发上限
 * 5. 服务级（按商品）并发上限覆盖（不填即继承门店级）
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Divider,
  Form,
  InputNumber,
  message,
  Row,
  Select,
  Space,
  Spin,
  Switch,
  Table,
  TimePicker,
  Typography,
} from 'antd';
import { DeleteOutlined, PlusOutlined, SaveOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import { get, post } from '@/lib/api';

const { Title, Text } = Typography;

const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

interface BusinessHourEntry {
  weekday: number; // 0~6 / -1
  date_exception?: string | null;
  start_time: string;
  end_time: string;
  is_closed?: boolean;
}

interface ConcurrencyService {
  product_id: number;
  name: string;
  max_concurrent_override: number | null;
  service_duration_minutes: number | null;
  effective_max_concurrent: number;
}

interface StoreOption {
  id: number;
  name: string;
}

export default function BusinessConfigPage() {
  const [storeOptions, setStoreOptions] = useState<StoreOption[]>([]);
  const [storeId, setStoreId] = useState<number | null>(null);

  const [weekly, setWeekly] = useState<Record<number, { start: Dayjs; end: Dayjs }[]>>({});
  const [exceptions, setExceptions] = useState<{ date: Dayjs; start: Dayjs; end: Dayjs; closed: boolean }[]>([]);

  const [storeMaxConcurrent, setStoreMaxConcurrent] = useState<number>(1);
  const [services, setServices] = useState<ConcurrencyService[]>([]);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  // 加载门店列表（复用商家中心已有的接口）
  const loadStores = async () => {
    try {
      const data = await get<any>('/api/merchant/stores');
      const items = (data?.items || data || []) as any[];
      const opts = items.map((s) => ({ id: s.id, name: s.store_name || s.name || `门店 ${s.id}` }));
      setStoreOptions(opts);
      if (opts.length > 0 && !storeId) {
        setStoreId(opts[0].id);
      }
    } catch (e) {
      message.error('门店列表加载失败');
    }
  };

  useEffect(() => {
    loadStores();
  }, []);

  // 加载某门店的配置
  const loadConfig = async (sid: number) => {
    setLoading(true);
    try {
      const [bhData, climitData] = await Promise.all([
        get<any>('/api/merchant/business-hours', { store_id: sid }),
        get<any>('/api/merchant/concurrency-limit', { store_id: sid }),
      ]);

      // 营业时间窗
      const wk: Record<number, { start: Dayjs; end: Dayjs }[]> = {};
      const exc: typeof exceptions = [];
      (bhData?.entries || []).forEach((e: BusinessHourEntry) => {
        if (e.weekday === -1 && e.date_exception) {
          exc.push({
            date: dayjs(e.date_exception),
            start: dayjs(e.start_time, 'HH:mm'),
            end: dayjs(e.end_time, 'HH:mm'),
            closed: !!e.is_closed,
          });
        } else if (e.weekday >= 0 && e.weekday <= 6) {
          if (!wk[e.weekday]) wk[e.weekday] = [];
          wk[e.weekday].push({
            start: dayjs(e.start_time, 'HH:mm'),
            end: dayjs(e.end_time, 'HH:mm'),
          });
        }
      });
      setWeekly(wk);
      setExceptions(exc);

      // 并发上限
      setStoreMaxConcurrent(climitData?.store_max_concurrent || 1);
      setServices(climitData?.services || []);
    } catch (e) {
      message.error('配置加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (storeId) loadConfig(storeId);
  }, [storeId]);

  const addWeekSlot = (wd: number) => {
    setWeekly((prev) => {
      const next = { ...prev };
      next[wd] = [...(next[wd] || []), { start: dayjs('09:00', 'HH:mm'), end: dayjs('18:00', 'HH:mm') }];
      return next;
    });
  };

  const removeWeekSlot = (wd: number, idx: number) => {
    setWeekly((prev) => {
      const next = { ...prev };
      next[wd] = (next[wd] || []).filter((_, i) => i !== idx);
      return next;
    });
  };

  const updateWeekSlot = (wd: number, idx: number, key: 'start' | 'end', val: Dayjs | null) => {
    setWeekly((prev) => {
      const next = { ...prev };
      const arr = [...(next[wd] || [])];
      if (val) arr[idx] = { ...arr[idx], [key]: val };
      next[wd] = arr;
      return next;
    });
  };

  const addException = () => {
    setExceptions((prev) => [
      ...prev,
      {
        date: dayjs().add(1, 'day'),
        start: dayjs('09:00', 'HH:mm'),
        end: dayjs('18:00', 'HH:mm'),
        closed: true,
      },
    ]);
  };

  const removeException = (idx: number) => {
    setExceptions((prev) => prev.filter((_, i) => i !== idx));
  };

  const handleSaveAll = async () => {
    if (!storeId) {
      message.warning('请先选择门店');
      return;
    }
    setSaving(true);
    try {
      // 营业时间窗
      const entries: BusinessHourEntry[] = [];
      for (let wd = 0; wd < 7; wd++) {
        for (const slot of weekly[wd] || []) {
          entries.push({
            weekday: wd,
            start_time: slot.start.format('HH:mm'),
            end_time: slot.end.format('HH:mm'),
          });
        }
      }
      for (const e of exceptions) {
        entries.push({
          weekday: -1,
          date_exception: e.date.format('YYYY-MM-DD'),
          start_time: e.start.format('HH:mm'),
          end_time: e.end.format('HH:mm'),
          is_closed: e.closed,
        });
      }
      await post('/api/merchant/business-hours', { store_id: storeId, entries });

      // 并发上限
      await post('/api/merchant/concurrency-limit', {
        store_id: storeId,
        store_max_concurrent: storeMaxConcurrent,
        service_overrides: services.map((s) => ({
          product_id: s.product_id,
          max_concurrent_override: s.max_concurrent_override,
          service_duration_minutes: s.service_duration_minutes,
        })),
      });
      message.success('保存成功');
      if (storeId) await loadConfig(storeId);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const updateService = (pid: number, key: 'max_concurrent_override' | 'service_duration_minutes', val: number | null) => {
    setServices((prev) =>
      prev.map((s) => (s.product_id === pid ? { ...s, [key]: val } : s))
    );
  };

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>商家营业时间 + 并发上限配置</Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="客户端时段选择器将基于此处的营业时间窗与并发上限自动切片并显示已占用置灰。"
      />
      <Form layout="vertical">
        <Form.Item label="选择门店">
          <Select
            value={storeId || undefined}
            onChange={(v) => setStoreId(v)}
            options={storeOptions.map((s) => ({ value: s.id, label: s.name }))}
            style={{ width: 320 }}
            placeholder="请选择门店"
          />
        </Form.Item>
      </Form>

      <Spin spinning={loading}>
        <Card title="按周营业时间" style={{ marginBottom: 16 }}>
          {WEEKDAY_LABELS.map((label, wd) => (
            <Row key={wd} align="middle" gutter={12} style={{ marginBottom: 8 }}>
              <Col span={2}><Text strong>{label}</Text></Col>
              <Col span={20}>
                <Space wrap>
                  {(weekly[wd] || []).map((slot, idx) => (
                    <Space key={idx}>
                      <TimePicker
                        format="HH:mm"
                        value={slot.start}
                        onChange={(v) => updateWeekSlot(wd, idx, 'start', v)}
                        allowClear={false}
                      />
                      <Text>~</Text>
                      <TimePicker
                        format="HH:mm"
                        value={slot.end}
                        onChange={(v) => updateWeekSlot(wd, idx, 'end', v)}
                        allowClear={false}
                      />
                      <Button
                        size="small"
                        danger
                        icon={<DeleteOutlined />}
                        onClick={() => removeWeekSlot(wd, idx)}
                      />
                    </Space>
                  ))}
                  <Button
                    type="dashed"
                    icon={<PlusOutlined />}
                    onClick={() => addWeekSlot(wd)}
                  >
                    添加时间段
                  </Button>
                </Space>
              </Col>
            </Row>
          ))}
        </Card>

        <Card
          title="日期例外"
          extra={
            <Button icon={<PlusOutlined />} onClick={addException}>
              添加例外
            </Button>
          }
          style={{ marginBottom: 16 }}
        >
          {exceptions.length === 0 && <Text type="secondary">暂无日期例外（如国庆休息、春节调整营业时间）</Text>}
          {exceptions.map((e, idx) => (
            <Row key={idx} align="middle" gutter={12} style={{ marginBottom: 8 }}>
              <Col><DatePicker value={e.date} onChange={(v) => v && setExceptions((p) => p.map((x, i) => i === idx ? { ...x, date: v } : x))} /></Col>
              <Col>
                <Switch
                  checked={e.closed}
                  onChange={(v) => setExceptions((p) => p.map((x, i) => i === idx ? { ...x, closed: v } : x))}
                  checkedChildren="休息"
                  unCheckedChildren="营业"
                />
              </Col>
              {!e.closed && (
                <>
                  <Col>
                    <TimePicker
                      format="HH:mm"
                      value={e.start}
                      onChange={(v) => v && setExceptions((p) => p.map((x, i) => i === idx ? { ...x, start: v } : x))}
                      allowClear={false}
                    />
                  </Col>
                  <Col><Text>~</Text></Col>
                  <Col>
                    <TimePicker
                      format="HH:mm"
                      value={e.end}
                      onChange={(v) => v && setExceptions((p) => p.map((x, i) => i === idx ? { ...x, end: v } : x))}
                      allowClear={false}
                    />
                  </Col>
                </>
              )}
              <Col>
                <Button
                  danger
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={() => removeException(idx)}
                />
              </Col>
            </Row>
          ))}
        </Card>

        <Card title="同时段并发上限（双层）" style={{ marginBottom: 16 }}>
          <Form layout="inline" style={{ marginBottom: 16 }}>
            <Form.Item label="门店级（默认值，所有服务在该门店总和上限）">
              <InputNumber
                min={1}
                max={999}
                value={storeMaxConcurrent}
                onChange={(v) => setStoreMaxConcurrent(v || 1)}
              />
            </Form.Item>
          </Form>

          <Divider plain>服务级覆盖（不填则继承门店级）</Divider>
          <Table
            rowKey="product_id"
            dataSource={services}
            pagination={false}
            size="small"
            columns={[
              { title: '服务名称', dataIndex: 'name' },
              {
                title: '服务级并发上限',
                render: (_, r) => (
                  <InputNumber
                    min={1}
                    max={999}
                    placeholder={`继承门店级 ${storeMaxConcurrent}`}
                    value={r.max_concurrent_override ?? undefined}
                    onChange={(v) => updateService(r.product_id, 'max_concurrent_override', v ?? null)}
                  />
                ),
              },
              {
                title: '服务时长（分钟）',
                render: (_, r) => (
                  <InputNumber
                    min={5}
                    max={720}
                    placeholder="默认 60"
                    value={r.service_duration_minutes ?? undefined}
                    onChange={(v) => updateService(r.product_id, 'service_duration_minutes', v ?? null)}
                  />
                ),
              },
              {
                title: '当前生效',
                render: (_, r) => (
                  <Text type="secondary">
                    并发 {r.max_concurrent_override ?? storeMaxConcurrent} / 时长 {r.service_duration_minutes ?? 60}min
                  </Text>
                ),
              },
            ]}
          />
        </Card>

        <Space>
          <Button
            type="primary"
            icon={<SaveOutlined />}
            loading={saving}
            onClick={handleSaveAll}
          >
            保存全部配置
          </Button>
        </Space>
      </Spin>
    </div>
  );
}
