'use client';

import { Suspense, useCallback, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import api from '@/lib/api';
import { showToast } from '@/lib/toast-unified';

// ─── Types ───────────────────────────────────────────────────────

interface Reminder {
  id: number;
  user_id: number;
  member_id?: number | null;
  reminder_type: 'followup' | 'checkup' | 'recheck';
  title: string;
  hospital?: string | null;
  department?: string | null;
  scheduled_date: string;
  recurrence?: string | null;
  notes?: string | null;
  status: string;
  source: string;
  related_metric?: string | null;
  created_by: number;
  completed_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface Recommendation {
  recommended_frequency: string;
  recommended_interval_months: number;
  last_checkup_date?: string | null;
  days_since_last_checkup?: number | null;
  next_recommended_date?: string | null;
  age_group: string;
  suggestions: string[];
}

type TabKey = 'followup' | 'checkup' | 'recheck';

const TAB_DEFS: { key: TabKey; label: string; icon: string }[] = [
  { key: 'followup', label: '复诊提醒', icon: '🏥' },
  { key: 'checkup', label: '体检提醒', icon: '🔬' },
  { key: 'recheck', label: '复查提醒', icon: '📋' },
];

// ─── Form Modal ──────────────────────────────────────────────────

function ReminderFormModal({
  visible,
  mode,
  initial,
  onClose,
  onSave,
}: {
  visible: boolean;
  mode: 'followup' | 'checkup';
  initial?: Partial<Reminder>;
  onClose: () => void;
  onSave: (data: any) => void;
}) {
  const [title, setTitle] = useState(initial?.title || '');
  const [date, setDate] = useState(initial?.scheduled_date || '');
  const [hospital, setHospital] = useState(initial?.hospital || '');
  const [department, setDepartment] = useState(initial?.department || '');
  const [notes, setNotes] = useState(initial?.notes || '');
  const [recurrence, setRecurrence] = useState<string | null>(initial?.recurrence ?? null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (visible) {
      setTitle(initial?.title || '');
      setDate(initial?.scheduled_date || '');
      setHospital(initial?.hospital || '');
      setDepartment(initial?.department || '');
      setNotes(initial?.notes || '');
      setRecurrence(initial?.recurrence ?? null);
    }
  }, [visible, initial]);

  if (!visible) return null;

  const handleSubmit = async () => {
    if (!date) {
      showToast('请选择日期', 'fail');
      return;
    }
    const autoTitle = title.trim() || (mode === 'followup' ? `${department || ''}复诊`.trim() : '定期体检');
    setSaving(true);
    try {
      await onSave({
        reminder_type: mode,
        title: autoTitle,
        scheduled_date: date,
        hospital: hospital || undefined,
        department: department || undefined,
        notes: notes || undefined,
        recurrence: recurrence || undefined,
      });
    } finally {
      setSaving(false);
    }
  };

  const isFollowup = mode === 'followup';

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      zIndex: 100, display: 'flex', alignItems: 'flex-end',
    }}>
      <div style={{
        background: '#fff', width: '100%',
        borderTopLeftRadius: 16, borderTopRightRadius: 16,
        maxHeight: '85vh', display: 'flex', flexDirection: 'column',
      }}>
        {/* Header */}
        <div style={{
          padding: '14px 16px',
          borderBottom: '1px solid #F1F5F9',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        }}>
          <span style={{ fontSize: 17, fontWeight: 700, color: '#1E293B' }}>
            {initial?.id ? '编辑' : '新建'}{isFollowup ? '复诊' : '体检'}提醒
          </span>
          <span onClick={onClose} style={{ fontSize: 22, color: '#9CA3AF', cursor: 'pointer' }}>×</span>
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 6 }}>
              {isFollowup ? '复诊日期' : '体检日期'} *
            </div>
            <input
              type="date" value={date}
              onChange={e => setDate(e.target.value)}
              style={{
                width: '100%', padding: '12px 14px', borderRadius: 10,
                border: '1px solid #E5E7EB', fontSize: 15, boxSizing: 'border-box',
              }}
            />
          </div>

          {isFollowup && (
            <>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 6 }}>科室</div>
                <input
                  type="text" value={department}
                  onChange={e => setDepartment(e.target.value)}
                  placeholder="如：心内科"
                  style={{
                    width: '100%', padding: '12px 14px', borderRadius: 10,
                    border: '1px solid #E5E7EB', fontSize: 15, boxSizing: 'border-box',
                  }}
                />
              </div>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 6 }}>医院</div>
                <input
                  type="text" value={hospital}
                  onChange={e => setHospital(e.target.value)}
                  placeholder="如：北京协和医院"
                  style={{
                    width: '100%', padding: '12px 14px', borderRadius: 10,
                    border: '1px solid #E5E7EB', fontSize: 15, boxSizing: 'border-box',
                  }}
                />
              </div>
            </>
          )}

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 6 }}>标题</div>
            <input
              type="text" value={title}
              onChange={e => setTitle(e.target.value)}
              placeholder={mode === 'followup' ? '如：心内科复诊' : '如：年度体检'}
              style={{
                width: '100%', padding: '12px 14px', borderRadius: 10,
                border: '1px solid #E5E7EB', fontSize: 15, boxSizing: 'border-box',
              }}
            />
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 6 }}>周期设置</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              {[
                { label: '不重复', value: null as string | null },
                { label: '每3个月', value: '3months' },
                { label: '每6个月', value: '6months' },
                { label: '每12个月', value: '12months' },
              ].map(opt => (
                <button
                  key={String(opt.value)}
                  onClick={() => setRecurrence(opt.value)}
                  style={{
                    padding: '8px 16px', borderRadius: 16, border: 'none',
                    background: recurrence === opt.value ? '#0EA5E9' : '#F1F5F9',
                    color: recurrence === opt.value ? '#fff' : '#374151',
                    fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  }}
                >{opt.label}</button>
              ))}
            </div>
          </div>

          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 14, fontWeight: 600, color: '#374151', marginBottom: 6 }}>备注</div>
            <textarea
              value={notes}
              onChange={e => setNotes(e.target.value)}
              placeholder="可填写注意事项..."
              rows={3}
              style={{
                width: '100%', padding: '12px 14px', borderRadius: 10,
                border: '1px solid #E5E7EB', fontSize: 15, boxSizing: 'border-box',
                resize: 'none', fontFamily: 'inherit',
              }}
            />
          </div>
        </div>

        {/* Footer */}
        <div style={{ padding: 16, borderTop: '1px solid #F1F5F9', display: 'flex', gap: 12 }}>
          <button onClick={onClose} style={{
            flex: 1, padding: '14px 0', borderRadius: 22,
            background: '#fff', border: '1px solid #E5E7EB',
            fontSize: 15, fontWeight: 600, color: '#374151', cursor: 'pointer',
          }}>取消</button>
          <button onClick={handleSubmit} disabled={saving} style={{
            flex: 1, padding: '14px 0', borderRadius: 22,
            background: saving ? '#94A3B8' : '#0EA5E9',
            border: 'none', color: '#fff',
            fontSize: 15, fontWeight: 600, cursor: saving ? 'default' : 'pointer',
          }}>{saving ? '保存中...' : '保存'}</button>
        </div>
      </div>
    </div>
  );
}

// ─── Main Inner ──────────────────────────────────────────────────

function HealthRemindersInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const memberId = searchParams?.get('member_id') || '';

  const [activeTab, setActiveTab] = useState<TabKey>('followup');
  const [reminders, setReminders] = useState<Reminder[]>([]);
  const [loading, setLoading] = useState(true);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingReminder, setEditingReminder] = useState<Partial<Reminder> | undefined>(undefined);

  const fetchReminders = useCallback(async (type: TabKey) => {
    setLoading(true);
    try {
      const qs = memberId ? `?member_id=${memberId}&reminder_type=${type}` : `?reminder_type=${type}`;
      const res: any = await api.get(`/api/health-reminders${qs}`);
      const data = res?.data || res;
      setReminders(Array.isArray(data.items) ? data.items : Array.isArray(data) ? data : []);
    } catch {
      setReminders([]);
    } finally {
      setLoading(false);
    }
  }, [memberId]);

  const fetchRecommendation = useCallback(async () => {
    try {
      const qs = memberId ? `?member_id=${memberId}` : '';
      const res: any = await api.get(`/api/health-reminders/recommendations${qs}`);
      const data = res?.data || res;
      setRecommendation(data);
    } catch {
      setRecommendation(null);
    }
  }, [memberId]);

  useEffect(() => {
    fetchReminders(activeTab);
    if (activeTab === 'checkup') {
      fetchRecommendation();
    }
  }, [activeTab, fetchReminders, fetchRecommendation]);

  const handleSave = async (formData: any) => {
    try {
      if (editingReminder?.id) {
        await api.put(`/api/health-reminders/${editingReminder.id}`, {
          ...formData,
          member_id: memberId ? Number(memberId) : undefined,
        });
        showToast('更新成功');
      } else {
        await api.post('/api/health-reminders', {
          ...formData,
          member_id: memberId ? Number(memberId) : undefined,
        });
        showToast('创建成功');
      }
      setShowForm(false);
      setEditingReminder(undefined);
      fetchReminders(activeTab);
    } catch {
      showToast('操作失败', 'fail');
    }
  };

  const handleComplete = async (id: number) => {
    try {
      await api.put(`/api/health-reminders/${id}`, { status: 'completed' });
      showToast('已标记完成');
      fetchReminders(activeTab);
    } catch {
      showToast('操作失败', 'fail');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/api/health-reminders/${id}`);
      showToast('已删除');
      fetchReminders(activeTab);
    } catch {
      showToast('删除失败', 'fail');
    }
  };

  const daysUntil = (dateStr: string) => {
    const target = new Date(dateStr);
    const now = new Date();
    const diff = Math.ceil((target.getTime() - now.getTime()) / (1000 * 60 * 60 * 24));
    return diff;
  };

  const renderFollowupList = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {reminders.length === 0 && !loading ? (
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🏥</div>
          <div style={{ fontSize: 15, color: '#9CA3AF', marginBottom: 16 }}>暂无复诊提醒</div>
          <button
            onClick={() => { setEditingReminder(undefined); setShowForm(true); }}
            style={{
              padding: '12px 28px', borderRadius: 22,
              background: '#0EA5E9', color: '#fff', border: 'none',
              fontSize: 15, fontWeight: 600, cursor: 'pointer',
            }}
          >+ 新建复诊提醒</button>
        </div>
      ) : (
        reminders.map(r => {
          const days = daysUntil(r.scheduled_date);
          const isOverdue = days < 0;
          const isUrgent = days >= 0 && days <= 3;
          return (
            <div key={r.id} style={{
              background: '#fff', borderRadius: 14, padding: '14px 16px',
              boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
              borderLeft: `4px solid ${r.status === 'completed' ? '#10B981' : isOverdue ? '#EF4444' : isUrgent ? '#F59E0B' : '#0EA5E9'}`,
              opacity: r.status === 'completed' ? 0.7 : 1,
            }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start' }}>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: 15, fontWeight: 700, color: '#1E293B' }}>
                      {r.title || `${r.department || ''}复诊`}
                    </span>
                    {r.status === 'completed' && (
                      <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 8, background: '#D1FAE5', color: '#10B981', fontWeight: 600 }}>已完成</span>
                    )}
                    {r.status !== 'completed' && isOverdue && (
                      <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 8, background: '#FEE2E2', color: '#EF4444', fontWeight: 600 }}>已过期</span>
                    )}
                    {r.status !== 'completed' && isUrgent && !isOverdue && (
                      <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 8, background: '#FEF3C7', color: '#D97706', fontWeight: 600 }}>即将到期</span>
                    )}
                  </div>
                  <div style={{ fontSize: 13, color: '#6B7280' }}>
                    📅 {r.scheduled_date}
                    {r.hospital && <span> · {r.hospital}</span>}
                    {r.department && <span> · {r.department}</span>}
                  </div>
                  {r.recurrence && (
                    <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>🔄 {r.recurrence === '3months' ? '每3个月' : r.recurrence === '6months' ? '每6个月' : r.recurrence === '12months' ? '每12个月' : r.recurrence}</div>
                  )}
                  {r.notes && (
                    <div style={{ fontSize: 13, color: '#6B7280', marginTop: 4, padding: '6px 10px', background: '#F8FAFC', borderRadius: 8 }}>📝 {r.notes}</div>
                  )}
                </div>
                <div style={{
                  textAlign: 'center', padding: '6px 10px', borderRadius: 10, marginLeft: 10,
                  background: isOverdue ? '#FEE2E2' : isUrgent ? '#FEF3C7' : '#F0F9FF',
                }}>
                  <div style={{
                    fontSize: 22, fontWeight: 800,
                    color: isOverdue ? '#EF4444' : isUrgent ? '#D97706' : '#0EA5E9',
                  }}>{Math.abs(days)}</div>
                  <div style={{ fontSize: 11, color: '#6B7280' }}>{isOverdue ? '天前' : '天后'}</div>
                </div>
              </div>
              {r.status !== 'completed' && (
                <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                  <button onClick={() => handleComplete(r.id)} style={{
                    flex: 1, padding: '8px 0', borderRadius: 16, background: '#10B981', color: '#fff',
                    border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  }}>✅ 标记完成</button>
                  <button onClick={() => { setEditingReminder(r); setShowForm(true); }} style={{
                    padding: '8px 14px', borderRadius: 16, background: '#F1F5F9', color: '#374151',
                    border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  }}>编辑</button>
                  <button onClick={() => handleDelete(r.id)} style={{
                    padding: '8px 14px', borderRadius: 16, background: '#FEE2E2', color: '#EF4444',
                    border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  }}>删除</button>
                </div>
              )}
            </div>
          );
        })
      )}
    </div>
  );

  const renderCheckupList = () => (
    <div>
      {recommendation && (
        <div style={{
          background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
          borderRadius: 14, padding: '14px 16px', marginBottom: 12, color: '#fff',
        }}>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>💡 系统建议</div>
          <div style={{ fontSize: 13, opacity: 0.95 }}>
            建议体检频率：{recommendation.recommended_frequency}
            {recommendation.next_recommended_date && `，下次建议日期：${recommendation.next_recommended_date}`}
          </div>
          <div style={{ fontSize: 12, opacity: 0.8, marginTop: 4 }}>
            年龄段：{recommendation.age_group}
            {recommendation.days_since_last_checkup != null && ` · 距上次体检 ${recommendation.days_since_last_checkup} 天`}
          </div>
          {recommendation.suggestions.length > 0 && (
            <div style={{ fontSize: 12, opacity: 0.85, marginTop: 6 }}>
              推荐项目：{recommendation.suggestions.join('、')}
            </div>
          )}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
        {reminders.length === 0 && !loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center' }}>
            <div style={{ fontSize: 40, marginBottom: 12 }}>🔬</div>
            <div style={{ fontSize: 15, color: '#9CA3AF', marginBottom: 16 }}>暂无体检提醒</div>
            <button
              onClick={() => { setEditingReminder(undefined); setShowForm(true); }}
              style={{
                padding: '12px 28px', borderRadius: 22,
                background: '#0EA5E9', color: '#fff', border: 'none',
                fontSize: 15, fontWeight: 600, cursor: 'pointer',
              }}
            >+ 设置体检提醒</button>
          </div>
        ) : (
          reminders.map(r => {
            const days = daysUntil(r.scheduled_date);
            const isOverdue = days < 0;
            return (
              <div key={r.id} style={{
                background: '#fff', borderRadius: 14, padding: '14px 16px',
                boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
                borderLeft: `4px solid ${r.status === 'completed' ? '#10B981' : isOverdue ? '#EF4444' : '#0EA5E9'}`,
                opacity: r.status === 'completed' ? 0.7 : 1,
              }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 700, color: '#1E293B' }}>
                      {r.title || '定期体检'}
                      {r.status === 'completed' && (
                        <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 8, background: '#D1FAE5', color: '#10B981', fontWeight: 600, marginLeft: 8 }}>已完成</span>
                      )}
                    </div>
                    <div style={{ fontSize: 13, color: '#6B7280', marginTop: 2 }}>📅 {r.scheduled_date}</div>
                    {r.recurrence && (
                      <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 2 }}>🔄 {r.recurrence === '3months' ? '每3个月' : r.recurrence === '6months' ? '每6个月' : r.recurrence === '12months' ? '每12个月' : r.recurrence}</div>
                    )}
                  </div>
                  <div style={{
                    textAlign: 'center', padding: '6px 10px', borderRadius: 10,
                    background: isOverdue ? '#FEE2E2' : '#F0F9FF',
                  }}>
                    <div style={{ fontSize: 22, fontWeight: 800, color: isOverdue ? '#EF4444' : '#0EA5E9' }}>{Math.abs(days)}</div>
                    <div style={{ fontSize: 11, color: '#6B7280' }}>{isOverdue ? '天前' : '天后'}</div>
                  </div>
                </div>
                {r.status !== 'completed' && (
                  <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                    <button onClick={() => handleComplete(r.id)} style={{
                      flex: 1, padding: '8px 0', borderRadius: 16, background: '#10B981', color: '#fff',
                      border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    }}>✅ 标记完成</button>
                    <button onClick={() => handleDelete(r.id)} style={{
                      padding: '8px 14px', borderRadius: 16, background: '#FEE2E2', color: '#EF4444',
                      border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    }}>删除</button>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );

  const renderRecheckList = () => (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      {reminders.length === 0 && !loading ? (
        <div style={{ padding: '40px 0', textAlign: 'center' }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
          <div style={{ fontSize: 15, color: '#9CA3AF' }}>暂无复查提醒</div>
          <div style={{ fontSize: 13, color: '#C4C4C4', marginTop: 8 }}>系统会根据健康数据自动生成复查建议</div>
        </div>
      ) : (
        reminders.map(r => (
          <div key={r.id} style={{
            background: '#fff', borderRadius: 14, padding: '14px 16px',
            boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
            borderLeft: `4px solid ${r.status === 'completed' ? '#10B981' : r.status === 'cancelled' ? '#9CA3AF' : '#F59E0B'}`,
            opacity: r.status === 'cancelled' ? 0.6 : 1,
          }}>
            <div style={{ display: 'flex', alignItems: 'start', gap: 10 }}>
              <span style={{ fontSize: 20, flexShrink: 0, marginTop: 2 }}>
                {r.status === 'completed' ? '✅' : r.status === 'cancelled' ? '🚫' : '⚠️'}
              </span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 15, fontWeight: 700, color: '#1E293B' }}>
                    {r.title || '复查建议'}
                  </span>
                  {r.source === 'system_recheck' && (
                    <span style={{ fontSize: 11, padding: '1px 8px', borderRadius: 8, background: '#FEF3C7', color: '#D97706', fontWeight: 600 }}>系统生成</span>
                  )}
                </div>
                {r.related_metric && (
                  <div style={{ fontSize: 13, color: '#6B7280', marginTop: 4 }}>
                    相关指标：{r.related_metric === 'blood_pressure' ? '血压' : r.related_metric === 'blood_glucose' ? '血糖' : r.related_metric === 'heart_rate' ? '心率' : r.related_metric}
                  </div>
                )}
                {r.notes && (
                  <div style={{
                    fontSize: 14, color: '#374151', marginTop: 4,
                    padding: '8px 12px', background: '#FFFBEB', borderRadius: 10,
                    lineHeight: 1.5,
                  }}>
                    {r.notes}
                  </div>
                )}
                <div style={{ fontSize: 12, color: '#9CA3AF', marginTop: 4 }}>
                  📅 建议日期：{r.scheduled_date}
                </div>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  );

  return (
    <div style={{ background: '#F0F5FF', minHeight: '100vh', paddingBottom: 80 }}>
      {/* Header */}
      <div style={{
        position: 'sticky', top: 0, zIndex: 50,
        background: 'linear-gradient(135deg, #F59E0B, #FBBF24)',
        padding: '12px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
        color: '#fff',
        boxShadow: '0 2px 8px rgba(245,158,11,0.3)',
      }}>
        <button
          onClick={() => router.back()}
          style={{
            background: 'rgba(255,255,255,0.2)', border: 'none', borderRadius: '50%',
            width: 36, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: 'pointer', color: '#fff', fontSize: 18,
          }}
        >←</button>
        <span style={{ flex: 1, fontSize: 18, fontWeight: 700 }}>🔔 提醒管理</span>
      </div>

      {/* Tabs */}
      <div style={{
        background: '#fff',
        padding: '8px 16px',
        display: 'flex', gap: 0,
        boxShadow: '0 1px 4px rgba(0,0,0,0.04)',
      }}>
        {TAB_DEFS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            style={{
              flex: 1, padding: '10px 0', border: 'none',
              background: activeTab === tab.key ? '#0EA5E9' : 'transparent',
              color: activeTab === tab.key ? '#fff' : '#64748B',
              borderRadius: 14,
              fontSize: 14, fontWeight: 600, cursor: 'pointer',
              transition: 'all 200ms ease',
            }}
          >{tab.icon} {tab.label}</button>
        ))}
      </div>

      {/* Content */}
      <div style={{ padding: '12px 16px' }}>
        {loading ? (
          <div style={{ padding: '40px 0', textAlign: 'center', color: '#9CA3AF' }}>加载中…</div>
        ) : (
          <>
            {activeTab === 'followup' && renderFollowupList()}
            {activeTab === 'checkup' && renderCheckupList()}
            {activeTab === 'recheck' && renderRecheckList()}
          </>
        )}
      </div>

      {/* FAB for followup/checkup */}
      {(activeTab === 'followup' || activeTab === 'checkup') && reminders.length > 0 && (
        <div style={{
          position: 'fixed', bottom: 24, right: 16, zIndex: 60,
        }}>
          <button
            onClick={() => { setEditingReminder(undefined); setShowForm(true); }}
            style={{
              width: 56, height: 56, borderRadius: '50%',
              background: 'linear-gradient(135deg, #0EA5E9, #38BDF8)',
              border: 'none', color: '#fff', fontSize: 28, fontWeight: 700,
              cursor: 'pointer',
              boxShadow: '0 4px 16px rgba(14,165,233,0.4)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}
          >+</button>
        </div>
      )}

      {/* Form Modal */}
      <ReminderFormModal
        visible={showForm}
        mode={activeTab === 'checkup' ? 'checkup' : 'followup'}
        initial={editingReminder}
        onClose={() => { setShowForm(false); setEditingReminder(undefined); }}
        onSave={handleSave}
      />
    </div>
  );
}

// ─── Default Export ──────────────────────────────────────────────

export default function HealthRemindersPage() {
  return (
    <Suspense fallback={<div style={{ minHeight: '100vh', background: '#F0F5FF', display: 'flex', alignItems: 'center', justifyContent: 'center' }}><span style={{ color: '#9CA3AF' }}>加载中…</span></div>}>
      <HealthRemindersInner />
    </Suspense>
  );
}
