'use client';

/**
 * [2026-05-05 营业管理入口收敛 PRD v1.0] 门店「营业管理」页（按门店锁定 store_id）
 *
 * 路由：/merchant/stores/{store_id}/business-config
 *
 * 内容：
 *   1. 按周营业时间（沿用 /api/merchant/business-hours）
 *   2. 日期例外（沿用 /api/merchant/business-hours）
 *   3. 门店总接待名额（搬自「编辑门店」页，落库到 merchant_stores.slot_capacity）
 *   4. 服务级并发上限表（沿用 /api/merchant/concurrency-limit；空表给引导）
 *   5. 预约提前 N 天（门店级，merchant_stores.advance_days）
 *   6. 当日截止 N 分钟（门店级，merchant_stores.booking_cutoff_minutes，下拉枚举）
 */

import React, { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Card,
  Col,
  DatePicker,
  Divider,
  Empty,
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
import { ArrowLeftOutlined, DeleteOutlined, PlusOutlined, SaveOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import { useParams, useRouter } from 'next/navigation';
import { get, post, put } from '@/lib/api';

const { Title, Text } = Typography;

const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

interface BusinessHourEntry {
  weekday: number;
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

// [2026-05-05 N-06] 当日截止枚举（PRD §3.2 / N-06）
const CUTOFF_OPTIONS: { label: string; value: number | null }[] = [
  { label: '不限制', value: 0 },
  { label: '15 分钟', value: 15 },
  { label: '30 分钟', value: 30 },
  { label: '1 小时', value: 60 },
  { label: '2 小时', value: 120 },
  { label: '半天（720）', value: 720 },
  { label: '1 天（1440）', value: 1440 },
];

export default function StoreBusinessConfigPage() {
  const params = useParams();
  const router = useRouter();
  const storeId = Number(params?.id);

  const [storeName, setStoreName] = useState<string>('');
  const [weekly, setWeekly] = useState<Record<number, { start: Dayjs; end: Dayjs }[]>>({});
  const [exceptions, setExceptions] = useState<{ date: Dayjs; start: Dayjs; end: Dayjs; closed: boolean }[]>([]);

  const [slotCapacity, setSlotCapacity] = useState<number>(10);
  const [advanceDays, setAdvanceDays] = useState<number | null>(null);
  const [bookingCutoffMinutes, setBookingCutoffMinutes] = useState<number | null>(null);

  const [services, setServices] = useState<ConcurrencyService[]>([]);

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);

  const loadStoreName = async () => {
    try {
      const detail = await get<any>(`/api/admin/merchant/stores/${storeId}`);
      setStoreName(detail?.store_name || `门店 ${storeId}`);
    } catch {
      // 静默：如果用 admin 接口失败，名字保持空
    }
  };

  const loadConfig = async () => {
    if (!storeId) return;
    setLoading(true);
    try {
      const [bhData, climitData, bookingData] = await Promise.all([
        get<any>('/api/merchant/business-hours', { store_id: storeId }),
        get<any>('/api/merchant/concurrency-limit', { store_id: storeId }),
        get<any>(`/api/merchant/stores/${storeId}/booking-config`).catch(() => null),
      ]);

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

      setServices(climitData?.services || []);

      if (bookingData) {
        setSlotCapacity(Number(bookingData.slot_capacity ?? 10));
        setAdvanceDays(
          bookingData.advance_days === null || bookingData.advance_days === undefined
            ? null
            : Number(bookingData.advance_days),
        );
        setBookingCutoffMinutes(
          bookingData.booking_cutoff_minutes === null || bookingData.booking_cutoff_minutes === undefined
            ? null
            : Number(bookingData.booking_cutoff_minutes),
        );
      }
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '配置加载失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (storeId) {
      loadStoreName();
      loadConfig();
    }
  }, [storeId]);

  const addWeekSlot = (wd: number) => {
    setWeekly((prev) => ({
      ...prev,
      [wd]: [...(prev[wd] || []), { start: dayjs('09:00', 'HH:mm'), end: dayjs('18:00', 'HH:mm') }],
    }));
  };

  const removeWeekSlot = (wd: number, idx: number) => {
    setWeekly((prev) => ({ ...prev, [wd]: (prev[wd] || []).filter((_, i) => i !== idx) }));
  };

  const updateWeekSlot = (wd: number, idx: number, key: 'start' | 'end', val: Dayjs | null) => {
    setWeekly((prev) => {
      const arr = [...(prev[wd] || [])];
      if (val) arr[idx] = { ...arr[idx], [key]: val };
      return { ...prev, [wd]: arr };
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

  const updateService = (
    pid: number,
    key: 'max_concurrent_override' | 'service_duration_minutes',
    val: number | null,
  ) => {
    setServices((prev) => prev.map((s) => (s.product_id === pid ? { ...s, [key]: val } : s)));
  };

  const handleSaveAll = async () => {
    if (!storeId) return;
    setSaving(true);
    try {
      // 1) 营业时间
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

      // 2) 服务级并发上限（不再下发 store_max_concurrent，按 PRD N-03 后端会忽略）
      await post('/api/merchant/concurrency-limit', {
        store_id: storeId,
        service_overrides: services.map((s) => ({
          product_id: s.product_id,
          max_concurrent_override: s.max_concurrent_override,
          service_duration_minutes: s.service_duration_minutes,
        })),
      });

      // 3) 门店级 booking-config（slot_capacity / advance_days / booking_cutoff_minutes）
      await put(`/api/merchant/stores/${storeId}/booking-config`, {
        slot_capacity: Number(slotCapacity ?? 0),
        advance_days: advanceDays === null || advanceDays === undefined ? null : Number(advanceDays),
        booking_cutoff_minutes:
          bookingCutoffMinutes === null || bookingCutoffMinutes === undefined
            ? null
            : Number(bookingCutoffMinutes),
      });

      message.success('保存成功');
      await loadConfig();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: 24 }}>
      <Space style={{ marginBottom: 12 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => router.push('/merchant/stores')}>
          返回门店列表
        </Button>
      </Space>
      <Title level={3} style={{ marginTop: 0 }}>
        营业管理 {storeName ? `· ${storeName}` : ''}
      </Title>
      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="本页面只针对当前门店生效；编辑门店页只维护门店资料，营业相关配置统一在此处管理。"
      />

      <Spin spinning={loading}>
        <Card title="按周营业时间" style={{ marginBottom: 16 }}>
          {WEEKDAY_LABELS.map((label, wd) => (
            <Row key={wd} align="middle" gutter={12} style={{ marginBottom: 8 }}>
              <Col span={2}>
                <Text strong>{label}</Text>
              </Col>
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
                  <Button type="dashed" icon={<PlusOutlined />} onClick={() => addWeekSlot(wd)}>
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
          {exceptions.length === 0 && (
            <Text type="secondary">暂无日期例外（如国庆休息、春节调整营业时间）</Text>
          )}
          {exceptions.map((e, idx) => (
            <Row key={idx} align="middle" gutter={12} style={{ marginBottom: 8 }}>
              <Col>
                <DatePicker
                  value={e.date}
                  onChange={(v) =>
                    v && setExceptions((p) => p.map((x, i) => (i === idx ? { ...x, date: v } : x)))
                  }
                />
              </Col>
              <Col>
                <Switch
                  checked={e.closed}
                  onChange={(v) => setExceptions((p) => p.map((x, i) => (i === idx ? { ...x, closed: v } : x)))}
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
                      onChange={(v) =>
                        v && setExceptions((p) => p.map((x, i) => (i === idx ? { ...x, start: v } : x)))
                      }
                      allowClear={false}
                    />
                  </Col>
                  <Col>
                    <Text>~</Text>
                  </Col>
                  <Col>
                    <TimePicker
                      format="HH:mm"
                      value={e.end}
                      onChange={(v) =>
                        v && setExceptions((p) => p.map((x, i) => (i === idx ? { ...x, end: v } : x)))
                      }
                      allowClear={false}
                    />
                  </Col>
                </>
              )}
              <Col>
                <Button danger size="small" icon={<DeleteOutlined />} onClick={() => removeException(idx)} />
              </Col>
            </Row>
          ))}
        </Card>

        {/* [2026-05-05 N-02 + N-03] 门店总接待名额 + 服务级覆盖 */}
        <Card title="同时段并发上限（双层）" style={{ marginBottom: 16 }}>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="服务级未填写时，自动继承本页『门店总接待名额』。"
          />
          <Form layout="inline" style={{ marginBottom: 16 }}>
            <Form.Item label="门店总接待名额" tooltip="0 表示不限制；与服务级覆盖共同决定该门店每个时段的可接待量。">
              <InputNumber
                min={0}
                max={9999}
                value={slotCapacity}
                onChange={(v) => setSlotCapacity(Number(v ?? 0))}
                style={{ width: 200 }}
                placeholder="默认 10，0 表示不限制"
                addonAfter="单/时段"
              />
            </Form.Item>
          </Form>

          <Divider plain>服务级覆盖（不填则继承门店总接待名额）</Divider>

          {services.length === 0 ? (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description={
                <span>
                  <div style={{ fontWeight: 500, fontSize: 15, marginBottom: 4 }}>该门店暂无可配置的服务</div>
                  <div style={{ color: '#666', fontSize: 13, maxWidth: 480, margin: '0 auto' }}>
                    服务级并发上限需先把商品关联到本门店。请前往「商品管理」选择商品并将其上架到本门店后，再回到此处配置。
                  </div>
                </span>
              }
            >
              <Button type="primary" onClick={() => router.push('/product-system/products')}>
                前往商品管理 →
              </Button>
            </Empty>
          ) : (
            <Table
              rowKey="product_id"
              dataSource={services}
              pagination={false}
              size="small"
              columns={[
                { title: '服务名称', dataIndex: 'name' },
                {
                  title: '服务级并发上限',
                  render: (_: any, r: ConcurrencyService) => (
                    <InputNumber
                      min={1}
                      max={999}
                      placeholder={`继承 ${slotCapacity || '门店总名额'}`}
                      value={r.max_concurrent_override ?? undefined}
                      onChange={(v) => updateService(r.product_id, 'max_concurrent_override', v ?? null)}
                    />
                  ),
                },
                {
                  title: '服务时长（分钟）',
                  render: (_: any, r: ConcurrencyService) => (
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
                  render: (_: any, r: ConcurrencyService) => (
                    <Text type="secondary">
                      并发 {r.max_concurrent_override ?? slotCapacity || '不限'} / 时长{' '}
                      {r.service_duration_minutes ?? 60}min
                    </Text>
                  ),
                },
              ]}
            />
          )}
        </Card>

        {/* [2026-05-05 N-05 + N-06] 预约提前规则（门店级） */}
        <Card title="预约提前规则（门店级）" style={{ marginBottom: 16 }}>
          <Alert
            type="info"
            showIcon
            style={{ marginBottom: 12 }}
            message="商品如已单独配置，则以商品级为准；门店级仅作为兜底。"
          />
          <Form layout="vertical">
            <Row gutter={24}>
              <Col span={12}>
                <Form.Item
                  label="最早可提前 N 天"
                  tooltip="留空 = 不限制；商品如已单独配置则以商品级为准。"
                >
                  <InputNumber
                    min={0}
                    max={365}
                    style={{ width: '100%' }}
                    value={advanceDays ?? undefined}
                    onChange={(v) => setAdvanceDays(v === null || v === undefined ? null : Number(v))}
                    placeholder="留空表示不限制"
                  />
                </Form.Item>
              </Col>
              <Col span={12}>
                <Form.Item
                  label="当日最晚提前 N 分钟截止"
                  tooltip="下拉选择；留空 = 系统默认 30 分钟；选「不限制」表示无截止；商品如已单独配置则以商品级为准。"
                >
                  <Select
                    style={{ width: '100%' }}
                    allowClear
                    placeholder="留空 = 系统默认 30 分钟"
                    value={bookingCutoffMinutes ?? undefined}
                    onChange={(v) =>
                      setBookingCutoffMinutes(v === null || v === undefined ? null : Number(v))
                    }
                    options={CUTOFF_OPTIONS.map((o) => ({ label: o.label, value: o.value as number }))}
                  />
                </Form.Item>
              </Col>
            </Row>
          </Form>
        </Card>

        <Space>
          <Button type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSaveAll}>
            保存全部配置
          </Button>
        </Space>
      </Spin>
    </div>
  );
}
