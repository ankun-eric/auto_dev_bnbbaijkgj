'use client';

import { Suspense, useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { NavBar, Form, Input, Button, Checkbox, Toast, SpinLoading, TextArea } from 'antd-mobile';
import api from '@/lib/api';

const PERIODS = [
  { value: 'morning', label: '早晨', emoji: '🌅', defaultTime: '08:00' },
  { value: 'noon', label: '中午', emoji: '🌞', defaultTime: '12:30' },
  { value: 'evening', label: '晚上', emoji: '🌙', defaultTime: '18:00' },
  { value: 'bedtime', label: '睡前', emoji: '😴', defaultTime: '22:00' },
];

export default function MedicationAddPage() {
  return (
    <Suspense fallback={<div className="min-h-screen bg-gray-50 flex items-center justify-center"><SpinLoading color="primary" /></div>}>
      <MedicationAddContent />
    </Suspense>
  );
}

function MedicationAddContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const editId = searchParams.get('id');
  const isEdit = !!editId;

  const [loading, setLoading] = useState(false);
  const [fetching, setFetching] = useState(isEdit);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState('');
  const [dosage, setDosage] = useState('');
  const [note, setNote] = useState('');
  const [selectedPeriods, setSelectedPeriods] = useState<string[]>([]);
  const [periodTimes, setPeriodTimes] = useState<Record<string, string>>({
    morning: '08:00',
    noon: '12:30',
    evening: '18:00',
    bedtime: '22:00',
  });

  useEffect(() => {
    if (!editId) return;
    const fetchMedication = async () => {
      try {
        const res: any = await api.get(`/api/health-plan/medications/${editId}`);
        const data = res.data || res;
        setName(data.medicine_name || '');
        setDosage(data.dosage || '');
        setNote(data.notes || '');
        if (data.time_period) {
          setSelectedPeriods([data.time_period]);
          if (data.remind_time) {
            setPeriodTimes((prev) => ({ ...prev, [data.time_period]: data.remind_time }));
          }
        }
      } catch {
        Toast.show({ content: '加载失败', icon: 'fail' });
      } finally {
        setFetching(false);
      }
    };
    fetchMedication();
  }, [editId]);

  const togglePeriod = (val: string) => {
    setSelectedPeriods((prev) =>
      prev.includes(val) ? prev.filter((v) => v !== val) : [...prev, val]
    );
  };

  const handleSubmit = async () => {
    if (!name.trim()) {
      Toast.show({ content: '请输入药品名称', icon: 'fail' });
      return;
    }
    if (selectedPeriods.length === 0) {
      Toast.show({ content: '请选择至少一个用药时段', icon: 'fail' });
      return;
    }

    setSubmitting(true);
    try {
      const firstPeriod = selectedPeriods[0] || '';
      const firstTime = periodTimes[firstPeriod] || '';
      const payload = {
        medicine_name: name.trim(),
        dosage: dosage.trim(),
        notes: note.trim(),
        time_period: firstPeriod,
        remind_time: firstTime,
      };

      if (isEdit) {
        await api.put(`/api/health-plan/medications/${editId}`, payload);
        Toast.show({ content: '修改成功', icon: 'success' });
      } else {
        await api.post('/api/health-plan/medications', payload);
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
          {isEdit ? '编辑用药提醒' : '添加用药提醒'}
        </NavBar>
        <div className="flex items-center justify-center" style={{ height: 'calc(100vh - 45px)' }}>
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <NavBar onBack={() => router.back()} style={{ background: '#fff' }}>
        {isEdit ? '编辑用药提醒' : '添加用药提醒'}
      </NavBar>

      <div className="px-4 pt-4">
        <div className="card">
          <div className="section-title">药品信息</div>
          <Form layout="vertical">
            <Form.Item label="药品名称" required>
              <Input
                placeholder="请输入药品名称"
                value={name}
                onChange={setName}
                clearable
              />
            </Form.Item>
            <Form.Item label="用药剂量">
              <Input
                placeholder="如：1片、2粒、5ml"
                value={dosage}
                onChange={setDosage}
                clearable
              />
            </Form.Item>
            <Form.Item label="备注">
              <TextArea
                placeholder="如：饭后服用、需空腹"
                value={note}
                onChange={setNote}
                rows={2}
                maxLength={200}
                showCount
              />
            </Form.Item>
          </Form>
        </div>

        <div className="card">
          <div className="section-title">用药时段</div>
          <div className="text-xs text-gray-400 mb-3">请选择用药时段并设置提醒时间</div>
          {PERIODS.map((p) => {
            const selected = selectedPeriods.includes(p.value);
            return (
              <div key={p.value} className="mb-3">
                <div
                  className="flex items-center py-3 px-3 rounded-xl cursor-pointer"
                  style={{
                    background: selected ? '#fa8c1610' : '#f5f5f5',
                    border: selected ? '1px solid #fa8c1640' : '1px solid transparent',
                  }}
                  onClick={() => togglePeriod(p.value)}
                >
                  <Checkbox
                    checked={selected}
                    style={{ '--icon-size': '20px', '--adm-color-primary': '#fa8c16' } as React.CSSProperties}
                  />
                  <span className="text-lg ml-2 mr-2">{p.emoji}</span>
                  <span className="text-sm font-medium flex-1">{p.label}</span>
                  {selected && (
                    <input
                      type="time"
                      value={periodTimes[p.value] || p.defaultTime}
                      onChange={(e) => {
                        e.stopPropagation();
                        setPeriodTimes((prev) => ({ ...prev, [p.value]: e.target.value }));
                      }}
                      onClick={(e) => e.stopPropagation()}
                      className="text-sm px-2 py-1 rounded-lg border border-gray-200 bg-white"
                      style={{ color: '#fa8c16' }}
                    />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white" style={{ maxWidth: 750, margin: '0 auto', boxShadow: '0 -2px 8px rgba(0,0,0,0.06)', paddingBottom: 'calc(16px + env(safe-area-inset-bottom))' }}>
        <Button
          block
          color="primary"
          size="large"
          loading={submitting}
          style={{ borderRadius: 12, background: 'linear-gradient(135deg, #fa8c16, #f5af19)', border: 'none', height: 48 }}
          onClick={handleSubmit}
        >
          {isEdit ? '保存修改' : '添加用药提醒'}
        </Button>
      </div>
    </div>
  );
}
