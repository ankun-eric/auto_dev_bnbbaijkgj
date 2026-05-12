'use client';

/**
 * [PRD-469 M6] 健康信息模块 —— 既往病史 / 过敏史 / 家族病史 / 个人习惯
 */

import { useCallback, useEffect, useState } from 'react';
import { Toast, Mask } from 'antd-mobile';
import api from '@/lib/api';

interface HealthInfo {
  chronic_diseases: Array<{ name: string; year?: string }>;
  surgery_history: Array<{ name: string; time?: string; note?: string }>;
  drug_allergies: string[];
  food_allergies: string[];
  other_allergies: string[];
  family_history: Array<{ relation: string; disease: string }>;
  habit_smoking?: string;
  habit_drinking?: string;
  habit_exercise?: string;
  habit_diet?: string;
}

const CHRONIC_PRESETS = ['高血压', '糖尿病', '高血脂', '冠心病', '脑卒中', '慢阻肺', '哮喘', '慢性肾病', '甲状腺', '痛风'];

interface Props {
  profileId?: number;
  token: any;
}

export default function HealthInfoBlock({ profileId, token: T }: Props) {
  const [info, setInfo] = useState<HealthInfo | null>(null);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState<HealthInfo>({
    chronic_diseases: [], surgery_history: [],
    drug_allergies: [], food_allergies: [], other_allergies: [],
    family_history: [],
  });

  const fetchInfo = useCallback(async () => {
    if (!profileId) return;
    try {
      const res: any = await api.get(`/api/prd469/health-info/${profileId}`);
      const data = res.data || res;
      setInfo({
        chronic_diseases: data.chronic_diseases || [],
        surgery_history: data.surgery_history || [],
        drug_allergies: data.drug_allergies || [],
        food_allergies: data.food_allergies || [],
        other_allergies: data.other_allergies || [],
        family_history: data.family_history || [],
        habit_smoking: data.habit_smoking,
        habit_drinking: data.habit_drinking,
        habit_exercise: data.habit_exercise,
        habit_diet: data.habit_diet,
      });
    } catch {
      setInfo(null);
    }
  }, [profileId]);

  useEffect(() => { fetchInfo(); }, [fetchInfo]);

  const openEdit = () => {
    if (info) setDraft(info);
    setEditing(true);
  };

  const handleSave = async () => {
    if (!profileId) return;
    try {
      await api.put(`/api/prd469/health-info/${profileId}`, draft);
      setInfo(draft);
      setEditing(false);
      Toast.show({ content: '已保存', icon: 'success' });
    } catch {
      Toast.show({ content: '保存失败', icon: 'fail' });
    }
  };

  const toggleChronic = (name: string) => {
    setDraft((d) => {
      const exists = d.chronic_diseases.find((c) => c.name === name);
      const next = exists
        ? d.chronic_diseases.filter((c) => c.name !== name)
        : [...d.chronic_diseases, { name }];
      return { ...d, chronic_diseases: next };
    });
  };

  const capsules: { icon: string; label: string }[] = [];
  if (info?.habit_smoking === '无') capsules.push({ icon: '🚭', label: '不吸烟' });
  if (info?.habit_smoking === '有') capsules.push({ icon: '🚬', label: '吸烟' });
  if (info?.habit_drinking === '无') capsules.push({ icon: '🚫', label: '不饮酒' });
  if (info?.habit_drinking === '有') capsules.push({ icon: '🍷', label: '饮酒' });
  for (const c of (info?.chronic_diseases || []).slice(0, 3)) capsules.push({ icon: '🩺', label: c.name });
  for (const d of (info?.drug_allergies || []).slice(0, 2)) capsules.push({ icon: '⚠️', label: `${d}过敏` });

  return (
    <div id="health-info" data-testid="prd469-health-info" style={{ padding: '12px 16px' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', margin: '8px 0 12px' }}>
        <h3 style={{ fontSize: 18, fontWeight: 600, color: T.brand700, margin: 0 }}>健康信息</h3>
        <span
          onClick={openEdit}
          style={{ fontSize: 13, color: T.brand600, cursor: 'pointer' }}
          data-testid="prd469-health-info-edit"
        >编辑 ›</span>
      </div>
      <div
        style={{
          background: '#fff', borderRadius: 12, padding: 16,
          boxShadow: '0 2px 8px rgba(0,0,0,0.06)',
          borderLeft: '3px solid #22c55e',
        }}
      >
        {capsules.length === 0 ? (
          <div style={{ color: '#9ca3af', fontSize: 14, textAlign: 'center', padding: '12px 0' }}>
            暂无健康信息，点击右上角「编辑」补充
          </div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {capsules.map((c, i) => (
              <span
                key={i}
                style={{
                  padding: '4px 10px', borderRadius: 12,
                  background: T.brand100, color: T.brand700,
                  fontSize: 13, fontWeight: 500,
                }}
              >{c.icon} {c.label}</span>
            ))}
          </div>
        )}

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8, marginTop: 14 }}>
          {[
            { label: '既往病史', count: info?.chronic_diseases.length || 0 },
            { label: '过敏史', count: (info?.drug_allergies.length || 0) + (info?.food_allergies.length || 0) + (info?.other_allergies.length || 0) },
            { label: '家族病史', count: info?.family_history.length || 0 },
            { label: '个人习惯', count: [info?.habit_smoking, info?.habit_drinking, info?.habit_exercise, info?.habit_diet].filter(Boolean).length },
          ].map((s) => (
            <div key={s.label} style={{ textAlign: 'center', padding: '8px 0', background: '#f9fafb', borderRadius: 8 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: T.brand700 }}>{s.count}</div>
              <div style={{ fontSize: 11, color: '#6b7280', marginTop: 2 }}>{s.label}</div>
            </div>
          ))}
        </div>
      </div>

      {editing && (
        <Mask visible color="rgba(0,0,0,0.5)">
          <div
            data-testid="prd469-health-info-modal"
            style={{
              position: 'fixed', left: 0, right: 0, bottom: 0,
              background: '#fff', borderTopLeftRadius: 16, borderTopRightRadius: 16,
              maxHeight: '90vh', display: 'flex', flexDirection: 'column',
            }}
          >
            <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.brand100}` }}>
              <span style={{ fontSize: 17, fontWeight: 700 }}>编辑健康信息</span>
              <span onClick={() => setEditing(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
            </div>
            <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
              <Section title="既往病史（慢病）">
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                  {CHRONIC_PRESETS.map((c) => {
                    const active = draft.chronic_diseases.some((x) => x.name === c);
                    return (
                      <button
                        key={c}
                        onClick={() => toggleChronic(c)}
                        style={{
                          padding: '6px 12px', borderRadius: 14,
                          background: active ? T.brand500 : '#f3f4f6',
                          color: active ? '#fff' : '#374151',
                          border: 'none', fontSize: 13, cursor: 'pointer',
                        }}
                      >{c}</button>
                    );
                  })}
                </div>
              </Section>

              <Section title="过敏史">
                <TagsInput
                  label="药物过敏" tags={draft.drug_allergies}
                  onChange={(v) => setDraft({ ...draft, drug_allergies: v })}
                  T={T}
                />
                <TagsInput
                  label="食物过敏" tags={draft.food_allergies}
                  onChange={(v) => setDraft({ ...draft, food_allergies: v })}
                  T={T}
                />
                <TagsInput
                  label="其他过敏（花粉/尘螨等）" tags={draft.other_allergies}
                  onChange={(v) => setDraft({ ...draft, other_allergies: v })}
                  T={T}
                />
              </Section>

              <Section title="个人习惯">
                <HabitRow label="抽烟" value={draft.habit_smoking} options={['有', '无']}
                  onChange={(v) => setDraft({ ...draft, habit_smoking: v })} T={T} />
                <HabitRow label="饮酒" value={draft.habit_drinking} options={['有', '无']}
                  onChange={(v) => setDraft({ ...draft, habit_drinking: v })} T={T} />
                <HabitRow label="运动频率" value={draft.habit_exercise} options={['无', '偶尔', '经常']}
                  onChange={(v) => setDraft({ ...draft, habit_exercise: v })} T={T} />
                <HabitRow label="饮食偏好" value={draft.habit_diet} options={['清淡', '重口味', '素食', '其他']}
                  onChange={(v) => setDraft({ ...draft, habit_diet: v })} T={T} />
              </Section>
            </div>
            <div style={{ padding: 16, borderTop: `1px solid ${T.brand100}`, display: 'flex', gap: 12 }}>
              <button onClick={() => setEditing(false)}
                style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600 }}>取消</button>
              <button onClick={handleSave} data-testid="prd469-health-info-save"
                style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.brand500, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>保存</button>
            </div>
          </div>
        </Mask>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: '#15803d', marginBottom: 10 }}>{title}</div>
      {children}
    </div>
  );
}

function HabitRow({ label, value, options, onChange, T }: {
  label: string; value?: string; options: string[];
  onChange: (v: string) => void; T: any;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #f3f4f6' }}>
      <span style={{ width: 80, fontSize: 14, color: '#374151' }}>{label}</span>
      <div style={{ flex: 1, display: 'flex', gap: 8 }}>
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            style={{
              padding: '4px 10px', borderRadius: 10,
              background: value === opt ? T.brand500 : '#f3f4f6',
              color: value === opt ? '#fff' : '#374151',
              border: 'none', fontSize: 13, cursor: 'pointer',
            }}
          >{opt}</button>
        ))}
      </div>
    </div>
  );
}

function TagsInput({ label, tags, onChange, T }: {
  label: string; tags: string[]; onChange: (v: string[]) => void; T: any;
}) {
  const [val, setVal] = useState('');
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>{label}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
        {tags.map((t, i) => (
          <span
            key={i}
            style={{
              padding: '4px 10px', borderRadius: 12,
              background: T.brand100, color: T.brand700, fontSize: 13,
            }}
          >
            {t}
            <span
              onClick={() => onChange(tags.filter((_, j) => j !== i))}
              style={{ marginLeft: 6, cursor: 'pointer', color: '#9ca3af' }}
            >×</span>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text" value={val} onChange={(e) => setVal(e.target.value)}
          placeholder="输入后点击添加"
          style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: `1px solid ${T.brand200}`, fontSize: 13 }}
        />
        <button
          onClick={() => { if (val.trim()) { onChange([...tags, val.trim()]); setVal(''); } }}
          style={{ padding: '8px 16px', borderRadius: 8, background: T.brand500, color: '#fff', border: 'none', fontSize: 13 }}
        >添加</button>
      </div>
    </div>
  );
}
