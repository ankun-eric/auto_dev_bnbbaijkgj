'use client';

import { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Form, Input, Button, Toast, SpinLoading, Picker } from 'antd-mobile';
import api from '@/lib/api';

const FREQ_OPTIONS = [
  { value: 'daily', label: '每天' },
  { value: 'weekday', label: '工作日' },
  { value: 'custom', label: '自定义' },
];

const WEEKDAYS = [
  { value: 1, label: '一' },
  { value: 2, label: '二' },
  { value: 3, label: '三' },
  { value: 4, label: '四' },
  { value: 5, label: '五' },
  { value: 6, label: '六' },
  { value: 0, label: '日' },
];

const TIME_HOUR_COL = Array.from({ length: 24 }, (_, i) => {
  const v = String(i).padStart(2, '0');
  return { label: v, value: v };
});
const TIME_MINUTE_COL = Array.from({ length: 60 }, (_, i) => {
  const v = String(i).padStart(2, '0');
  return { label: v, value: v };
});
const TIME_PICKER_COLUMNS = [TIME_HOUR_COL, TIME_MINUTE_COL];

export default function CheckinAddPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50 flex items-center justify-center"><SpinLoading color="primary" /></div>}>
      <CheckinAddContent />
    </Suspense>
  );
}

function CheckinAddContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const editId = searchParams.get('id');
  const isEdit = !!editId;

  const [fetching, setFetching] = useState(isEdit);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState('');
  const [remindTime, setRemindTime] = useState('');
  const [frequency, setFrequency] = useState('daily');
  const [customDays, setCustomDays] = useState<number[]>([]);
  const [timePickerVisible, setTimePickerVisible] = useState(false);

  useEffect(() => {
    if (!editId) return;
    const fetchItem = async () => {
      try {
        const res: any = await api.get(`/api/health-plan/checkin-items/${editId}`);
        const data = res.data || res;
        setName(data.name || '');
        const times = Array.isArray(data.remind_times) ? data.remind_times : [];
        setRemindTime(times[0] || data.remind_time || '');
        setFrequency(data.repeat_frequency || data.frequency || 'daily');
        setCustomDays(data.custom_days || []);
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setFetching(false);
      }
    };
    fetchItem();
  }, [editId]);

  const toggleDay = (day: number) => {
    setCustomDays((prev) =>
      prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day]
    );
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      Toast.show({ content: '请输入打卡名称', icon: 'fail' });
      return;
    }
    if (!remindTime) {
      Toast.show({ content: '请选择提醒时间', icon: 'fail' });
      return;
    }
    if (frequency === 'custom' && customDays.length === 0) {
      Toast.show({ content: '请选择重复日期', icon: 'fail' });
      return;
    }

    setSubmitting(true);
    try {
      const payload: any = {
        name: name.trim(),
        remind_times: remindTime ? [remindTime] : null,
        repeat_frequency: frequency,
        custom_days: frequency === 'custom' ? customDays : null,
      };

      if (isEdit) {
        await api.put(`/api/health-plan/checkin-items/${editId}`, payload);
        Toast.show({ content: '修改成功', icon: 'success' });
      } else {
        await api.post('/api/health-plan/checkin-items', payload);
        Toast.show({ content: '添加成功', icon: 'success' });
      }
      router.back();
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    } finally {
      setSubmitting(false);
    }
  };

  if (fetching) {
    return (
      <div className="min-h-screen bg-gray-50">
        <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
          {isEdit ? '编辑打卡项' : '添加打卡项'}
        </NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  const pickerValue = (() => {
    if (!remindTime) return ['08', '00'];
    const [h = '00', m = '00'] = remindTime.split(':');
    return [h.padStart(2, '0'), m.padStart(2, '0')];
  })();

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        {isEdit ? '编辑打卡项' : '添加打卡项'}
      </NavBar>

      <div className="px-4 pt-4">
        <div className="card">
          <div className="section-title">打卡信息</div>
          <Form layout="vertical">
            <Form.Item label={<span><span style={{ color: 'red' }}>*</span> 打卡名称</span>} required>
              <Input
                placeholder="如：喝水、冥想、跑步"
                value={name}
                onChange={setName}
                clearable
              />
            </Form.Item>
            <Form.Item label={<span><span style={{ color: 'red' }}>*</span> 提醒时间</span>} required>
              <div
                className="w-full text-sm px-3 py-2 rounded-lg border border-gray-200 bg-white cursor-pointer"
                onClick={() => setTimePickerVisible(true)}
              >
                {remindTime ? remindTime : <span className="text-gray-400">请选择提醒时间</span>}
              </div>
            </Form.Item>
          </Form>
        </div>

        <div className="card">
          <div className="section-title"><span style={{ color: 'red' }}>*</span> 重复频率</div>
          <div className="flex gap-2 mb-3">
            {FREQ_OPTIONS.map((opt) => (
              <div
                key={opt.value}
                onClick={() => setFrequency(opt.value)}
                className="flex-1 text-center py-2 rounded-lg cursor-pointer text-sm"
                style={{
                  background: frequency === opt.value ? '#52c41a15' : '#f5f5f5',
                  color: frequency === opt.value ? '#52c41a' : '#666',
                  border: frequency === opt.value ? '1px solid #52c41a40' : '1px solid transparent',
                  fontWeight: frequency === opt.value ? 600 : 400,
                }}
              >
                {opt.label}
              </div>
            ))}
          </div>
          {frequency === 'custom' && (
            <div className="flex gap-2 flex-wrap">
              {WEEKDAYS.map((d) => {
                const selected = customDays.includes(d.value);
                return (
                  <div
                    key={d.value}
                    onClick={() => toggleDay(d.value)}
                    className="w-9 h-9 rounded-full flex items-center justify-center text-sm cursor-pointer"
                    style={{
                      background: selected ? '#52c41a' : '#f5f5f5',
                      color: selected ? '#fff' : '#666',
                    }}
                  >
                    {d.label}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <Picker
        columns={TIME_PICKER_COLUMNS}
        visible={timePickerVisible}
        title="选择提醒时间"
        value={pickerValue}
        onClose={() => setTimePickerVisible(false)}
        onCancel={() => setTimePickerVisible(false)}
        onConfirm={(val) => {
          const [h, m] = val as string[];
          setRemindTime(`${h}:${m}`);
          setTimePickerVisible(false);
        }}
      />

      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white" style={{ maxWidth: 750, margin: '0 auto', boxShadow: '0 -2px 8px rgba(0,0,0,0.06)', paddingBottom: 'calc(16px + env(safe-area-inset-bottom))' }}>
        <Button
          block
          color="primary"
          size="large"
          loading={submitting}
          style={{ borderRadius: 12, background: 'linear-gradient(135deg, #52c41a, #73d13d)', border: 'none', height: 48 }}
          onClick={handleSubmit}
        >
          {isEdit ? '保存修改' : '添加打卡项'}
        </Button>
      </div>
    </div>
  );
}
