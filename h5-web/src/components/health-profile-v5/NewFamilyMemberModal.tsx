'use client';

/**
 * [PRD-469 M3] 新建家庭成员弹层（v5 同款）
 *
 * - 关系网格（16 项预置 + 「其他」自定义）
 * - 关系绑定头像（emoji，与 AI 对话页一致）
 * - 7 字段表单
 * - 「其他」自定义关系名重复校验
 */

import { useEffect, useState } from 'react';
import { Toast, Mask, Picker } from 'antd-mobile';
import api from '@/lib/api';

interface RelationOption {
  key: string;
  name: string;
  avatar: string;
  is_other: boolean;
}

const T = {
  brand500: '#22c55e',
  brand600: '#16a34a',
  brand700: '#15803d',
  brand100: '#dcfce7',
  brand200: '#bbf7d0',
  textPrimary: '#1f2937',
  textSecondary: '#6b7280',
};

const BLOOD_TYPES = [
  { label: 'A', value: 'A' },
  { label: 'B', value: 'B' },
  { label: 'AB', value: 'AB' },
  { label: 'O', value: 'O' },
  { label: '不详', value: '不详' },
];

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export default function NewFamilyMemberModal({ onClose, onSuccess }: Props) {
  const [step, setStep] = useState<'relation' | 'form'>('relation');
  const [options, setOptions] = useState<RelationOption[]>([]);
  const [selectedKey, setSelectedKey] = useState<string>('');
  const [customName, setCustomName] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const [name, setName] = useState('');
  const [gender, setGender] = useState<'男' | '女' | ''>('');
  const [birthday, setBirthday] = useState<string>('');
  const [height, setHeight] = useState<string>('');
  const [weight, setWeight] = useState<string>('');
  const [bloodType, setBloodType] = useState<string>('');
  const [bloodPickerVisible, setBloodPickerVisible] = useState(false);
  const [phone, setPhone] = useState('');

  useEffect(() => {
    (async () => {
      try {
        const res: any = await api.get('/api/prd469/family-member/relation-options');
        const data = res.data || res;
        setOptions(Array.isArray(data.items) ? data.items : []);
      } catch {
        setOptions([]);
      }
    })();
  }, []);

  const selectedOption = options.find((o) => o.key === selectedKey);

  const handleSelectRelation = (key: string) => {
    setSelectedKey(key);
    setCustomName('');
  };

  const handleNext = async () => {
    if (!selectedKey) {
      Toast.show({ content: '请选择关系', icon: 'fail' });
      return;
    }
    if (selectedOption?.is_other) {
      const trimmed = customName.trim();
      if (!trimmed) {
        Toast.show({ content: '请填写自定义关系名', icon: 'fail' });
        return;
      }
      try {
        const res: any = await api.post('/api/prd469/family-member/relation-custom/check', { name: trimmed });
        const data = res.data || res;
        if (!data.valid) {
          Toast.show({ content: data.reason || '关系名重复', icon: 'fail' });
          return;
        }
      } catch {
        Toast.show({ content: '校验失败，请重试', icon: 'fail' });
        return;
      }
    }
    setStep('form');
  };

  const handleSubmit = async () => {
    const nameTrimmed = name.trim();
    if (!nameTrimmed || nameTrimmed.length < 2 || nameTrimmed.length > 20) {
      Toast.show({ content: '姓名需为 2–20 个字', icon: 'fail' });
      return;
    }
    if (!gender) {
      Toast.show({ content: '请选择性别', icon: 'fail' });
      return;
    }
    if (!birthday) {
      Toast.show({ content: '请选择出生日期', icon: 'fail' });
      return;
    }

    const relationLabel = selectedOption?.is_other ? customName.trim() : (selectedOption?.name || '');
    setSubmitting(true);
    try {
      await api.post('/api/family/members', {
        relationship_type: relationLabel,
        nickname: nameTrimmed,
        name: nameTrimmed,
        gender,
        birthday,
        height: height ? Number(height) : undefined,
        weight: weight ? Number(weight) : undefined,
        blood_type: bloodType || undefined,
        phone: phone || undefined,
      });
      onSuccess();
    } catch (e: any) {
      const detail = e?.response?.data?.detail || '保存失败';
      Toast.show({ content: detail, icon: 'fail' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Mask visible color="rgba(0,0,0,0.5)">
      <div
        data-testid="prd469-new-member-modal"
        style={{
          position: 'fixed', left: 0, right: 0, bottom: 0,
          background: '#fff', borderTopLeftRadius: 16, borderTopRightRadius: 16,
          maxHeight: '90vh', display: 'flex', flexDirection: 'column',
        }}
      >
        <div
          style={{
            padding: '14px 16px', display: 'flex', justifyContent: 'space-between',
            alignItems: 'center', borderBottom: `1px solid ${T.brand100}`,
          }}
        >
          <span style={{ fontSize: 17, fontWeight: 700, color: T.textPrimary }}>新建家庭成员</span>
          <span onClick={onClose} style={{ fontSize: 22, color: T.textSecondary, cursor: 'pointer' }}>×</span>
        </div>

        <div style={{ flex: 1, overflowY: 'auto', padding: 16 }}>
          {step === 'relation' && (
            <>
              <div style={{ fontSize: 14, color: T.textSecondary, marginBottom: 12 }}>① 选择与本人的关系</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 12 }}>
                {options.map((o) => {
                  const active = selectedKey === o.key;
                  return (
                    <div
                      key={o.key}
                      onClick={() => handleSelectRelation(o.key)}
                      data-testid={`prd469-relation-${o.key}`}
                      style={{
                        display: 'flex', flexDirection: 'column', alignItems: 'center',
                        gap: 6, padding: '10px 4px', borderRadius: 12,
                        background: active ? T.brand100 : '#f9fafb',
                        border: active ? `2px solid ${T.brand500}` : '2px solid transparent',
                        cursor: 'pointer',
                      }}
                    >
                      <div
                        style={{
                          width: 40, height: 40, borderRadius: '50%',
                          background: '#fff',
                          display: 'flex', alignItems: 'center', justifyContent: 'center',
                          fontSize: 24, fontWeight: 600,
                        }}
                      >{o.avatar}</div>
                      <span style={{ fontSize: 13, color: T.textPrimary }}>{o.name}</span>
                    </div>
                  );
                })}
              </div>

              {selectedOption?.is_other && (
                <div style={{ marginTop: 16 }}>
                  <div style={{ fontSize: 13, color: T.textSecondary, marginBottom: 6 }}>请填写自定义关系名（如「大儿子」「二儿子」）</div>
                  <input
                    type="text"
                    value={customName}
                    onChange={(e) => setCustomName(e.target.value)}
                    placeholder="自定义关系名"
                    maxLength={16}
                    style={{
                      width: '100%', padding: '10px 12px', borderRadius: 8,
                      border: `1px solid ${T.brand200}`, fontSize: 14,
                      boxSizing: 'border-box',
                    }}
                  />
                </div>
              )}
            </>
          )}

          {step === 'form' && (
            <>
              <div style={{ fontSize: 14, color: T.textSecondary, marginBottom: 12 }}>② 填写基础信息</div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '12px 0', borderBottom: `1px solid ${T.brand100}` }}>
                <div
                  style={{
                    width: 48, height: 48, borderRadius: '50%', background: T.brand100,
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 28,
                  }}
                >{selectedOption?.avatar || '🧑'}</div>
                <div>
                  <div style={{ fontSize: 16, fontWeight: 600, color: T.textPrimary }}>
                    {selectedOption?.is_other ? customName : selectedOption?.name}
                  </div>
                  <div style={{ fontSize: 12, color: T.textSecondary, marginTop: 2 }}>关系头像（自动绑定）</div>
                </div>
              </div>

              <FormRow label="姓名" required>
                <input
                  type="text" value={name} onChange={(e) => setName(e.target.value)}
                  placeholder="请输入姓名（2-20 字）" maxLength={20}
                  style={inputStyle}
                />
              </FormRow>
              <FormRow label="性别" required>
                <div style={{ display: 'flex', gap: 12 }}>
                  {['男', '女'].map((g) => (
                    <button
                      key={g}
                      onClick={() => setGender(g as '男' | '女')}
                      style={{
                        flex: 1, padding: '8px 0', borderRadius: 8,
                        border: gender === g ? `2px solid ${T.brand500}` : `1px solid ${T.brand200}`,
                        background: gender === g ? T.brand100 : '#fff',
                        color: gender === g ? T.brand700 : T.textPrimary,
                        fontSize: 14, fontWeight: 600, cursor: 'pointer',
                      }}
                    >{g}</button>
                  ))}
                </div>
              </FormRow>
              <FormRow label="出生日期" required>
                <input
                  type="date" value={birthday} onChange={(e) => setBirthday(e.target.value)}
                  style={inputStyle}
                />
              </FormRow>
              <FormRow label="身高 (cm)">
                <input
                  type="number" value={height} onChange={(e) => setHeight(e.target.value)}
                  placeholder="如 170" style={inputStyle}
                />
              </FormRow>
              <FormRow label="体重 (kg)">
                <input
                  type="number" value={weight} onChange={(e) => setWeight(e.target.value)}
                  placeholder="如 65" style={inputStyle}
                />
              </FormRow>
              <FormRow label="血型">
                <div
                  onClick={() => setBloodPickerVisible(true)}
                  style={{ ...inputStyle, cursor: 'pointer', color: bloodType ? T.textPrimary : '#9ca3af' }}
                >
                  {bloodType || '请选择血型'}
                </div>
              </FormRow>
              <FormRow label="手机号">
                <input
                  type="tel" value={phone} onChange={(e) => setPhone(e.target.value)}
                  placeholder="用于共管邀请（选填）" maxLength={11} style={inputStyle}
                />
              </FormRow>
            </>
          )}
        </div>

        <div style={{ padding: 16, borderTop: `1px solid ${T.brand100}`, display: 'flex', gap: 12 }}>
          {step === 'relation' ? (
            <>
              <button onClick={onClose} style={btnGhost}>取消</button>
              <button onClick={handleNext} style={btnPrimary} data-testid="prd469-relation-next-btn">下一步</button>
            </>
          ) : (
            <>
              <button onClick={() => setStep('relation')} style={btnGhost}>上一步</button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                style={{ ...btnPrimary, opacity: submitting ? 0.6 : 1 }}
                data-testid="prd469-member-submit-btn"
              >{submitting ? '保存中…' : '保存'}</button>
            </>
          )}
        </div>
      </div>

      <Picker
        columns={[BLOOD_TYPES]}
        visible={bloodPickerVisible}
        onClose={() => setBloodPickerVisible(false)}
        onConfirm={(val) => { setBloodType(String(val[0] || '')); setBloodPickerVisible(false); }}
      />
    </Mask>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '10px 12px', borderRadius: 8,
  border: `1px solid ${T.brand200}`, fontSize: 14, boxSizing: 'border-box',
};

const btnGhost: React.CSSProperties = {
  flex: 1, padding: '12px 0', borderRadius: 24,
  background: '#fff', color: T.textPrimary,
  border: `1px solid ${T.brand200}`, fontSize: 15, fontWeight: 600, cursor: 'pointer',
};

const btnPrimary: React.CSSProperties = {
  flex: 1, padding: '12px 0', borderRadius: 24,
  background: T.brand500, color: '#fff',
  border: 'none', fontSize: 15, fontWeight: 600, cursor: 'pointer',
};

function FormRow({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ padding: '12px 0', borderBottom: `1px solid ${T.brand100}` }}>
      <div style={{ fontSize: 13, color: T.textSecondary, marginBottom: 6 }}>
        {required && <span style={{ color: '#ef4444', marginRight: 4 }}>*</span>}
        {label}
      </div>
      {children}
    </div>
  );
}
