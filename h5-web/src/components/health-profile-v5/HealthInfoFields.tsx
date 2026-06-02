'use client';

/**
 * [PRD-HEALTH-INFO-SHARED 2026-06-02] 公共「健康信息填写区」子组件
 *
 * 把 既往病史 / 过敏史 / 手术史 / 家族病史 / 个人习惯 抽成一份代码，
 * 供「编辑健康档案」抽屉 与「添加/邀请家庭成员」抽屉 两处共用。
 *
 * 设计原则：
 * - 受控组件：所有数据来自 props.value，所有变更通过 props.onChange 回写。
 * - 自带 手术史 / 家族病史 的「＋添加 / 编辑 / 删除」子弹窗，调用方无需关心。
 * - 主题色通过 props.theme 注入，兼容档案页（绿色 brand）与成员表单（蓝色）。
 */

import { useState } from 'react';

export interface HealthInfoValue {
  chronic_diseases: Array<{ name: string; year?: string }>;
  surgery_history: Array<{ name: string; time?: string; note?: string }>;
  drug_allergies: string[];
  food_allergies: string[];
  other_allergies: string[];
  family_history: Array<{ relation: string; disease: string; note?: string }>;
  habit_smoking?: string;
  habit_drinking?: string;
  habit_exercise?: string;
  habit_diet?: string;
}

export interface HealthInfoTheme {
  /** 主按钮 / 选中态底色 */
  primary: string;
  /** 浅底色（胶囊背景） */
  pillBg: string;
  /** 主文字色（标题） */
  titleColor: string;
  /** 边框色 */
  border: string;
  /** Section 标题色 */
  sectionTitle: string;
}

export const GREEN_THEME: HealthInfoTheme = {
  primary: '#22c55e',
  pillBg: '#dcfce7',
  titleColor: '#15803d',
  border: '#bbf7d0',
  sectionTitle: '#15803d',
};

export const BLUE_THEME: HealthInfoTheme = {
  primary: '#0EA5E9',
  pillBg: '#E0F2FE',
  titleColor: '#0369A1',
  border: '#BAE6FD',
  sectionTitle: '#0369A1',
};

const CHRONIC_PRESETS = ['高血压', '糖尿病', '高血脂', '冠心病', '脑卒中', '慢阻肺', '哮喘', '慢性肾病', '甲状腺', '痛风'];
const FAMILY_RELATIONS = ['爸爸', '妈妈', '爷爷', '奶奶', '外公', '外婆', '兄弟', '姐妹', '其他'];

interface Props {
  value: HealthInfoValue;
  onChange: (v: HealthInfoValue) => void;
  theme?: HealthInfoTheme;
  /** 是否展示「既往病史（慢病）」区块，默认展示 */
  showChronic?: boolean;
}

export default function HealthInfoFields({ value, onChange, theme = GREEN_THEME, showChronic = true }: Props) {
  const T = theme;

  const [showAddFamily, setShowAddFamily] = useState(false);
  const [showAddSurgery, setShowAddSurgery] = useState(false);
  const [familyForm, setFamilyForm] = useState({ relation: '爸爸', disease: '', note: '' });
  const [surgeryForm, setSurgeryForm] = useState({ name: '', time: '', note: '' });
  const [editingFamilyIdx, setEditingFamilyIdx] = useState<number | null>(null);
  const [editingSurgeryIdx, setEditingSurgeryIdx] = useState<number | null>(null);

  const patch = (p: Partial<HealthInfoValue>) => onChange({ ...value, ...p });

  const toggleChronic = (name: string) => {
    const exists = (value.chronic_diseases || []).find((c) => c.name === name);
    const next = exists
      ? value.chronic_diseases.filter((c) => c.name !== name)
      : [...(value.chronic_diseases || []), { name }];
    patch({ chronic_diseases: next });
  };

  // ── 家族病史 ──
  const saveFamily = () => {
    if (!familyForm.disease.trim()) return;
    const item = { relation: familyForm.relation, disease: familyForm.disease.trim(), note: familyForm.note.trim() || undefined };
    let list: HealthInfoValue['family_history'];
    if (editingFamilyIdx !== null) {
      list = [...(value.family_history || [])];
      list[editingFamilyIdx] = item;
    } else {
      list = [...(value.family_history || []), item];
    }
    patch({ family_history: list });
    setEditingFamilyIdx(null);
    setFamilyForm({ relation: '爸爸', disease: '', note: '' });
    setShowAddFamily(false);
  };
  const removeFamily = (idx: number) => patch({ family_history: (value.family_history || []).filter((_, i) => i !== idx) });
  const editFamily = (idx: number) => {
    const it = (value.family_history || [])[idx];
    if (!it) return;
    setFamilyForm({ relation: it.relation || '爸爸', disease: it.disease || '', note: it.note || '' });
    setEditingFamilyIdx(idx);
    setShowAddFamily(true);
  };

  // ── 手术史 ──
  const saveSurgery = () => {
    if (!surgeryForm.name.trim()) return;
    const item = { name: surgeryForm.name.trim(), time: surgeryForm.time || undefined, note: surgeryForm.note.trim() || undefined };
    let list: HealthInfoValue['surgery_history'];
    if (editingSurgeryIdx !== null) {
      list = [...(value.surgery_history || [])];
      list[editingSurgeryIdx] = item;
    } else {
      list = [...(value.surgery_history || []), item];
    }
    patch({ surgery_history: list });
    setEditingSurgeryIdx(null);
    setSurgeryForm({ name: '', time: '', note: '' });
    setShowAddSurgery(false);
  };
  const removeSurgery = (idx: number) => patch({ surgery_history: (value.surgery_history || []).filter((_, i) => i !== idx) });
  const editSurgery = (idx: number) => {
    const it = (value.surgery_history || [])[idx];
    if (!it) return;
    setSurgeryForm({ name: it.name || '', time: it.time || '', note: it.note || '' });
    setEditingSurgeryIdx(idx);
    setShowAddSurgery(true);
  };

  const overlayInput: React.CSSProperties = {
    width: '100%', padding: '10px 12px', borderRadius: 8,
    border: '1px solid #e5e7eb', fontSize: 14, boxSizing: 'border-box',
  };

  return (
    <div data-testid="health-info-fields">
      {showChronic && (
        <Section title="既往病史（慢病）" T={T}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {CHRONIC_PRESETS.map((c) => {
              const active = (value.chronic_diseases || []).some((x) => x.name === c);
              return (
                <button
                  key={c}
                  onClick={() => toggleChronic(c)}
                  style={{
                    padding: '6px 12px', borderRadius: 14,
                    background: active ? T.primary : '#f3f4f6',
                    color: active ? '#fff' : '#374151',
                    border: 'none', fontSize: 13, cursor: 'pointer',
                  }}
                >{c}</button>
              );
            })}
          </div>
        </Section>
      )}

      <Section title="过敏史" T={T}>
        <TagsInput label="药物过敏" tags={value.drug_allergies || []} onChange={(v) => patch({ drug_allergies: v })} T={T} />
        <TagsInput label="食物过敏" tags={value.food_allergies || []} onChange={(v) => patch({ food_allergies: v })} T={T} />
        <TagsInput label="其他过敏（花粉/尘螨等）" tags={value.other_allergies || []} onChange={(v) => patch({ other_allergies: v })} T={T} />
      </Section>

      {/* 手术史 */}
      <Section title="手术史" T={T}>
        {(value.surgery_history || []).map((s, idx) => (
          <div key={idx} data-testid={`hif-surgery-${idx}`}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f3f4f6' }}>
            <span style={{ fontSize: 13, color: '#374151' }}>
              🏥 {s.name}{s.time ? ` (${s.time})` : ''}{s.note ? ` — ${s.note}` : ''}
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button onClick={() => editSurgery(idx)} style={{ padding: '4px 8px', border: 'none', background: 'none', color: T.primary, fontSize: 12, cursor: 'pointer' }}>编辑</button>
              <button onClick={() => removeSurgery(idx)} style={{ padding: '4px 8px', border: 'none', background: 'none', color: '#ef4444', fontSize: 12, cursor: 'pointer' }}>删除</button>
            </div>
          </div>
        ))}
        <button
          onClick={() => { setSurgeryForm({ name: '', time: '', note: '' }); setEditingSurgeryIdx(null); setShowAddSurgery(true); }}
          data-testid="hif-add-surgery-btn"
          style={{ marginTop: 8, padding: '8px 16px', borderRadius: 16, background: T.pillBg, color: T.titleColor, border: 'none', fontSize: 13, cursor: 'pointer' }}>
          + 添加手术史
        </button>
      </Section>

      {/* 家族病史 */}
      <Section title="家族病史" T={T}>
        {(value.family_history || []).map((fh, idx) => (
          <div key={idx} data-testid={`hif-family-${idx}`}
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 0', borderBottom: '1px solid #f3f4f6' }}>
            <span style={{ fontSize: 13, color: '#374151' }}>
              👤 {fh.relation}：{fh.disease}{fh.note ? ` (${fh.note})` : ''}
            </span>
            <div style={{ display: 'flex', gap: 6 }}>
              <button onClick={() => editFamily(idx)} style={{ padding: '4px 8px', border: 'none', background: 'none', color: T.primary, fontSize: 12, cursor: 'pointer' }}>编辑</button>
              <button onClick={() => removeFamily(idx)} style={{ padding: '4px 8px', border: 'none', background: 'none', color: '#ef4444', fontSize: 12, cursor: 'pointer' }}>删除</button>
            </div>
          </div>
        ))}
        <button
          onClick={() => { setFamilyForm({ relation: '爸爸', disease: '', note: '' }); setEditingFamilyIdx(null); setShowAddFamily(true); }}
          data-testid="hif-add-family-btn"
          style={{ marginTop: 8, padding: '8px 16px', borderRadius: 16, background: T.pillBg, color: T.titleColor, border: 'none', fontSize: 13, cursor: 'pointer' }}>
          + 添加家族病史
        </button>
      </Section>

      {/* 个人习惯 */}
      <Section title="个人习惯" T={T}>
        <HabitRow label="抽烟" value={value.habit_smoking} options={['有', '无']} onChange={(v) => patch({ habit_smoking: v })} T={T} />
        <HabitRow label="饮酒" value={value.habit_drinking} options={['有', '无']} onChange={(v) => patch({ habit_drinking: v })} T={T} />
        <HabitRow label="运动频率" value={value.habit_exercise} options={['无', '偶尔', '经常']} onChange={(v) => patch({ habit_exercise: v })} T={T} />
        <HabitRow label="饮食偏好" value={value.habit_diet} options={['清淡', '重口味', '素食', '其他']} onChange={(v) => patch({ habit_diet: v })} T={T} />
      </Section>

      {/* 添加/编辑 家族病史 子弹窗 */}
      {showAddFamily && (
        <div data-testid="hif-family-form-modal"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 200, display: 'flex', alignItems: 'flex-end' }}>
          <div style={{ background: '#fff', width: '100%', borderTopLeftRadius: 16, borderTopRightRadius: 16 }}>
            <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontSize: 17, fontWeight: 700 }}>{editingFamilyIdx !== null ? '编辑家族病史' : '添加家族病史'}</span>
              <span onClick={() => setShowAddFamily(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
            </div>
            <div style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>与您的关系</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {FAMILY_RELATIONS.map((r) => (
                    <button key={r} onClick={() => setFamilyForm({ ...familyForm, relation: r })}
                      style={{ padding: '6px 12px', borderRadius: 14, background: familyForm.relation === r ? T.primary : '#f3f4f6', color: familyForm.relation === r ? '#fff' : '#374151', border: 'none', fontSize: 13, cursor: 'pointer' }}>{r}</button>
                  ))}
                </div>
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>疾病名称</div>
                <input type="text" value={familyForm.disease} onChange={(e) => setFamilyForm({ ...familyForm, disease: e.target.value })} placeholder="如：高血压" style={overlayInput} />
              </div>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>备注（可选）</div>
                <input type="text" value={familyForm.note} onChange={(e) => setFamilyForm({ ...familyForm, note: e.target.value })} placeholder="如：确诊于2020年" style={overlayInput} />
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <button onClick={() => setShowAddFamily(false)} style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.border}`, fontSize: 15, fontWeight: 600 }}>取消</button>
                <button onClick={saveFamily} data-testid="hif-save-family" style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.primary, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>保存</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 添加/编辑 手术史 子弹窗 */}
      {showAddSurgery && (
        <div data-testid="hif-surgery-form-modal"
          style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', zIndex: 200, display: 'flex', alignItems: 'flex-end' }}>
          <div style={{ background: '#fff', width: '100%', borderTopLeftRadius: 16, borderTopRightRadius: 16 }}>
            <div style={{ padding: '14px 16px', display: 'flex', justifyContent: 'space-between', borderBottom: `1px solid ${T.border}` }}>
              <span style={{ fontSize: 17, fontWeight: 700 }}>{editingSurgeryIdx !== null ? '编辑手术史' : '添加手术史'}</span>
              <span onClick={() => setShowAddSurgery(false)} style={{ fontSize: 22, color: '#9ca3af', cursor: 'pointer' }}>×</span>
            </div>
            <div style={{ padding: 16 }}>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>手术名称</div>
                <input type="text" value={surgeryForm.name} onChange={(e) => setSurgeryForm({ ...surgeryForm, name: e.target.value })} placeholder="如：阑尾切除术" style={overlayInput} />
              </div>
              <div style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>手术时间</div>
                <input type="date" value={surgeryForm.time} onChange={(e) => setSurgeryForm({ ...surgeryForm, time: e.target.value })} style={overlayInput} />
              </div>
              <div style={{ marginBottom: 16 }}>
                <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>备注（可选）</div>
                <input type="text" value={surgeryForm.note} onChange={(e) => setSurgeryForm({ ...surgeryForm, note: e.target.value })} placeholder="如：恢复良好" style={overlayInput} />
              </div>
              <div style={{ display: 'flex', gap: 12 }}>
                <button onClick={() => setShowAddSurgery(false)} style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: '#fff', border: `1px solid ${T.border}`, fontSize: 15, fontWeight: 600 }}>取消</button>
                <button onClick={saveSurgery} data-testid="hif-save-surgery" style={{ flex: 1, padding: '12px 0', borderRadius: 24, background: T.primary, color: '#fff', border: 'none', fontSize: 15, fontWeight: 600 }}>保存</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Section({ title, children, T }: { title: string; children: React.ReactNode; T: HealthInfoTheme }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 14, fontWeight: 600, color: T.sectionTitle, marginBottom: 10 }}>{title}</div>
      {children}
    </div>
  );
}

function HabitRow({ label, value, options, onChange, T }: {
  label: string; value?: string; options: string[]; onChange: (v: string) => void; T: HealthInfoTheme;
}) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', padding: '10px 0', borderBottom: '1px solid #f3f4f6' }}>
      <span style={{ width: 80, fontSize: 14, color: '#374151', flexShrink: 0 }}>{label}</span>
      <div style={{ flex: 1, display: 'flex', flexWrap: 'wrap', gap: 8 }}>
        {options.map((opt) => (
          <button
            key={opt}
            onClick={() => onChange(opt)}
            style={{
              padding: '4px 10px', borderRadius: 10,
              background: value === opt ? T.primary : '#f3f4f6',
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
  label: string; tags: string[]; onChange: (v: string[]) => void; T: HealthInfoTheme;
}) {
  const [val, setVal] = useState('');
  return (
    <div style={{ marginBottom: 12 }}>
      <div style={{ fontSize: 13, color: '#6b7280', marginBottom: 6 }}>{label}</div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 6 }}>
        {tags.map((t, i) => (
          <span key={i} style={{ padding: '4px 10px', borderRadius: 12, background: T.pillBg, color: T.titleColor, fontSize: 13 }}>
            {t}
            <span onClick={() => onChange(tags.filter((_, j) => j !== i))} style={{ marginLeft: 6, cursor: 'pointer', color: '#9ca3af' }}>×</span>
          </span>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8 }}>
        <input
          type="text" value={val} onChange={(e) => setVal(e.target.value)}
          placeholder="输入后点击添加"
          style={{ flex: 1, padding: '8px 10px', borderRadius: 8, border: `1px solid ${T.border}`, fontSize: 13, minWidth: 0, boxSizing: 'border-box' }}
        />
        <button
          onClick={() => { if (val.trim()) { onChange([...tags, val.trim()]); setVal(''); } }}
          style={{ padding: '8px 16px', borderRadius: 8, background: T.primary, color: '#fff', border: 'none', fontSize: 13, flexShrink: 0 }}
        >添加</button>
      </div>
    </div>
  );
}
