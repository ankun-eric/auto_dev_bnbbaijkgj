'use client';

/**
 * [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 新建/编辑打卡计划页
 *
 * 入参：?id=xxx → 编辑模式（回填数据），无参数 → 新建模式
 *
 * 字段：
 *  - 计划名称
 *  - 打卡频率：每天 / 每周 X 次（不做时间点 / 一天多次）
 *  - 计划起止时间
 */

import { Suspense, useState, useEffect, useCallback } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Form, Input, Button, SpinLoading, Stepper, DatePicker } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import GreenNavBar from '@/components/GreenNavBar';
import api from '@/lib/api';

function fmt(d: Date | null | undefined): string {
  if (!d) return '';
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

export default function EditPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-50 flex items-center justify-center">
          <SpinLoading color="primary" />
        </div>
      }
    >
      <EditContent />
    </Suspense>
  );
}

function EditContent() {
  const router = useRouter();
  const sp = useSearchParams();
  const editId = sp.get('id');
  const isEdit = !!editId;

  const [loading, setLoading] = useState(isEdit);
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState('');
  const [freqType, setFreqType] = useState<'daily' | 'weekly'>('daily');
  const [weeklyCount, setWeeklyCount] = useState<number>(3);
  const [startDate, setStartDate] = useState<Date | null>(new Date());
  const [endDate, setEndDate] = useState<Date | null>(null);

  const [startPickerVisible, setStartPickerVisible] = useState(false);
  const [endPickerVisible, setEndPickerVisible] = useState(false);

  const fetchItem = useCallback(async () => {
    if (!editId) return;
    try {
      const res: any = await api.get(`/api/health-plan/checkin-items/${editId}`);
      const data = res.data || res;
      setName(data.name || '');
      const rf = data.repeat_frequency || 'daily';
      if (rf === 'weekly') {
        setFreqType('weekly');
        setWeeklyCount(data.weekly_target_count || 3);
      } else {
        setFreqType('daily');
      }
      if (data.start_date) setStartDate(new Date(data.start_date));
      else setStartDate(null);
      if (data.end_date) setEndDate(new Date(data.end_date));
      else setEndDate(null);
    } catch {
      showToast('加载失败', 'fail');
    } finally {
      setLoading(false);
    }
  }, [editId]);

  useEffect(() => {
    fetchItem();
  }, [fetchItem]);

  const handleSubmit = async () => {
    if (!name.trim()) {
      showToast('请输入计划名称', 'fail');
      return;
    }
    if (freqType === 'weekly' && (!weeklyCount || weeklyCount < 1 || weeklyCount > 7)) {
      showToast('每周次数应在 1~7 之间', 'fail');
      return;
    }
    if (startDate && endDate && fmt(startDate) > fmt(endDate)) {
      showToast('开始日期不能晚于结束日期', 'fail');
      return;
    }

    setSubmitting(true);
    try {
      const payload: any = {
        name: name.trim(),
        repeat_frequency: freqType,
        weekly_target_count: freqType === 'weekly' ? weeklyCount : null,
        start_date: startDate ? fmt(startDate) : null,
        end_date: endDate ? fmt(endDate) : null,
      };
      if (isEdit) {
        await api.put(`/api/health-plan/checkin-items/${editId}`, payload);
        showToast('修改成功', 'success');
      } else {
        await api.post('/api/health-plan/checkin-items', payload);
        showToast('创建成功', 'success');
      }
      router.replace('/health-plan');
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '保存失败';
      showToast(String(msg), 'fail');
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50">
        <GreenNavBar>{isEdit ? '编辑计划' : '新建计划'}</GreenNavBar>
        <div
          className="flex items-center justify-center"
          style={{ height: 'calc(100vh - 45px)' }}
        >
          <SpinLoading color="primary" />
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-24" data-testid="health-plan-edit-v1">
      <GreenNavBar>{isEdit ? '编辑计划' : '新建计划'}</GreenNavBar>

      <div className="px-4 pt-4">
        <div className="bg-white rounded-xl p-4 mb-4">
          <Form layout="vertical">
            <Form.Item
              label={
                <span>
                  <span style={{ color: 'red' }}>*</span> 计划名称
                </span>
              }
              required
            >
              <Input
                placeholder="如：每天喝 8 杯水"
                value={name}
                onChange={setName}
                maxLength={50}
                clearable
                data-testid="edit-name"
              />
            </Form.Item>
          </Form>
        </div>

        <div className="bg-white rounded-xl p-4 mb-4">
          <div className="text-sm font-bold mb-3">
            <span style={{ color: 'red' }}>*</span> 打卡频率
          </div>
          <div className="flex gap-2 mb-3">
            {(
              [
                { v: 'daily', label: '每天' },
                { v: 'weekly', label: '每周 X 次' },
              ] as const
            ).map((opt) => (
              <div
                key={opt.v}
                onClick={() => setFreqType(opt.v)}
                className="flex-1 text-center py-2 rounded-lg cursor-pointer text-sm"
                style={{
                  background: freqType === opt.v ? '#EEF2FF' : '#F5F5F5',
                  color: freqType === opt.v ? '#6366F1' : '#666',
                  border:
                    freqType === opt.v
                      ? '1px solid #6366F140'
                      : '1px solid transparent',
                  fontWeight: freqType === opt.v ? 600 : 400,
                }}
                data-testid={`freq-${opt.v}`}
              >
                {opt.label}
              </div>
            ))}
          </div>
          {freqType === 'weekly' && (
            <div className="flex items-center justify-between pt-2">
              <span className="text-sm text-gray-600">每周打卡次数</span>
              <Stepper
                min={1}
                max={7}
                value={weeklyCount}
                onChange={(v) => setWeeklyCount(Number(v) || 1)}
                data-testid="weekly-count"
              />
            </div>
          )}
          <div className="text-xs text-gray-400 mt-2">
            说明：仅按「天」打卡，不设置具体时间点（如需准点提醒请使用「用药提醒」）。
          </div>
        </div>

        <div className="bg-white rounded-xl p-4 mb-4">
          <div className="text-sm font-bold mb-3">计划起止时间</div>
          <div
            className="flex items-center justify-between py-2 border-b border-gray-100 cursor-pointer"
            onClick={() => setStartPickerVisible(true)}
            data-testid="start-date-row"
          >
            <span className="text-sm text-gray-600">开始日期</span>
            <span className="text-sm" style={{ color: startDate ? '#1F2937' : '#9CA3AF' }}>
              {startDate ? fmt(startDate) : '请选择（默认今天）'}
            </span>
          </div>
          <div
            className="flex items-center justify-between py-2 cursor-pointer"
            onClick={() => setEndPickerVisible(true)}
            data-testid="end-date-row"
          >
            <span className="text-sm text-gray-600">结束日期</span>
            <div className="flex items-center gap-3">
              <span className="text-sm" style={{ color: endDate ? '#1F2937' : '#9CA3AF' }}>
                {endDate ? fmt(endDate) : '不限期'}
              </span>
              {endDate && (
                <span
                  className="text-xs"
                  style={{ color: '#6366F1' }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setEndDate(null);
                  }}
                >
                  清除
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      <DatePicker
        visible={startPickerVisible}
        title="选择开始日期"
        precision="day"
        min={new Date(2020, 0, 1)}
        max={new Date(2099, 11, 31)}
        value={startDate || new Date()}
        onClose={() => setStartPickerVisible(false)}
        onConfirm={(d) => {
          setStartDate(d);
          setStartPickerVisible(false);
        }}
      />
      <DatePicker
        visible={endPickerVisible}
        title="选择结束日期"
        precision="day"
        min={new Date(2020, 0, 1)}
        max={new Date(2099, 11, 31)}
        value={endDate || startDate || new Date()}
        onClose={() => setEndPickerVisible(false)}
        onConfirm={(d) => {
          setEndDate(d);
          setEndPickerVisible(false);
        }}
      />

      <div
        className="fixed bottom-0 left-0 right-0 p-4 bg-white"
        style={{
          maxWidth: 750,
          margin: '0 auto',
          boxShadow: '0 -2px 8px rgba(0,0,0,0.06)',
          paddingBottom: 'calc(16px + env(safe-area-inset-bottom))',
        }}
      >
        <Button
          block
          color="primary"
          size="large"
          loading={submitting}
          style={{
            borderRadius: 12,
            background: 'linear-gradient(135deg, #6366F1, #8B5CF6)',
            border: 'none',
            height: 48,
          }}
          onClick={handleSubmit}
          data-testid="edit-submit"
        >
          {isEdit ? '保存修改' : '创建计划'}
        </Button>
      </div>
    </div>
  );
}
