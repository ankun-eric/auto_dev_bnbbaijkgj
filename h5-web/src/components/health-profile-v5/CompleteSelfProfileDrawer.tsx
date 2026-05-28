'use client';

/**
 * [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 完善健康档案 抽屉（本人专用）
 *
 * 复用「添加成员」抽屉样式 (NewFamilyMemberModal)，裁剪：
 * - ❌ 去掉「去邀请」横幅
 * - ❌ 去掉「成员关系」字段（本人无需选择）
 *
 * 必填三项默认展开置顶：姓名 * / 性别 * / 出生日期 *
 * 其他字段折叠（默认收起）：身高、体重、既往病史、过敏史
 *
 * 校验：
 * - 姓名：非空、非"本人"占位、长度 1~20
 * - 性别：单选 男/女
 * - 出生日期：≤ 今天，≥ 1900-01-01
 *
 * 保存：调用 PUT /api/health-profile/self；成功后 Toast「保存成功」+ 自动关闭抽屉
 */

import { useEffect, useState } from 'react';
import { Popup, DatePicker } from 'antd-mobile';
import { showToast } from '@/lib/toast-unified';
import api from '@/lib/api';
import { FAM_THEME as T, CHRONIC_DISEASE_OPTIONS } from '@/lib/family-relation';

const PLACEHOLDER_NAMES = new Set(['本人', '我', 'self', 'me']);

interface Props {
  onClose: () => void;
  onSuccess: () => void;
  /** 初始数据：来自 GET /api/health-profile/self */
  initial?: {
    name?: string | null;
    gender?: string | null;
    birthday?: string | null;
    height?: number | null;
    weight?: number | null;
  } | null;
}

export default function CompleteSelfProfileDrawer({ onClose, onSuccess, initial }: Props) {
  // 姓名/性别/生日：必填
  const [name, setName] = useState<string>('');
  const [gender, setGender] = useState<'男' | '女' | ''>('');
  const [birthday, setBirthday] = useState<string>('');
  const [datePickerVisible, setDatePickerVisible] = useState(false);

  // 折叠区选填
  const [moreOpen, setMoreOpen] = useState(false);
  const [height, setHeight] = useState<string>('');
  const [weight, setWeight] = useState<string>('');
  const [chronics, setChronics] = useState<string[]>([]);
  const [drugAllergy, setDrugAllergy] = useState<string>('');
  const [foodAllergy, setFoodAllergy] = useState<string>('');
  const [otherAllergy, setOtherAllergy] = useState<string>('');

  const [errFields, setErrFields] = useState<Set<string>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  // 初始化（如果 GET 已经有部分数据，把非占位项目带入）
  useEffect(() => {
    if (!initial) return;
    if (initial.name && !PLACEHOLDER_NAMES.has(String(initial.name).trim())) {
      setName(String(initial.name));
    }
    if (initial.gender) {
      const g = String(initial.gender).trim();
      if (g === '男' || g === 'male' || g === 'M') setGender('男');
      else if (g === '女' || g === 'female' || g === 'F') setGender('女');
    }
    if (initial.birthday) {
      setBirthday(String(initial.birthday).slice(0, 10));
    }
    if (initial.height != null) setHeight(String(initial.height));
    if (initial.weight != null) setWeight(String(initial.weight));
  }, [initial]);

  const clearErr = (f: string) => {
    setErrFields((s) => {
      if (!s.has(f)) return s;
      const ns = new Set(s);
      ns.delete(f);
      return ns;
    });
  };

  const validate = (): boolean => {
    const errs = new Set<string>();
    const n = name.trim();
    if (!n) errs.add('name');
    else if (PLACEHOLDER_NAMES.has(n)) errs.add('name');
    else if (n.length > 20) errs.add('name');

    if (!gender) errs.add('gender');

    if (!birthday) errs.add('birthday');
    else {
      const today = new Date().toISOString().slice(0, 10);
      if (birthday > today) errs.add('birthday');
      if (birthday < '1900-01-01') errs.add('birthday');
    }

    setErrFields(errs);
    return errs.size === 0;
  };

  const canSubmit = name.trim() && gender && birthday && !submitting;

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    try {
      const body: any = {
        name: name.trim(),
        gender,
        birthday,
      };
      if (height) body.height = Number(height);
      if (weight) body.weight = Number(weight);
      if (chronics.length) body.medical_histories = chronics;
      const allergies: string[] = [];
      const pushParts = (prefix: string, raw: string) => {
        raw.split(/[,，;；\s]+/).filter(Boolean).forEach((s) => allergies.push(`${prefix}:${s}`));
      };
      if (drugAllergy.trim()) pushParts('药物', drugAllergy);
      if (foodAllergy.trim()) pushParts('食物', foodAllergy);
      if (otherAllergy.trim()) pushParts('其他', otherAllergy);
      if (allergies.length) body.allergies = allergies;

      await api.put('/api/health-profile/self', body);
      showToast('保存成功');
      onSuccess();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      let msg = '保存失败';
      if (detail && typeof detail === 'object') {
        if (detail.field_errors) {
          const fe = detail.field_errors;
          const next = new Set<string>();
          if (fe.name) next.add('name');
          if (fe.gender) next.add('gender');
          if (fe.birthday) next.add('birthday');
          setErrFields(next);
          msg = detail.message || '请补全必填字段';
        }
      } else if (typeof detail === 'string') {
        msg = detail;
      }
      showToast(msg, 'fail');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Popup
      visible
      onMaskClick={onClose}
      position="bottom"
      bodyStyle={{
        borderRadius: '20px 20px 0 0',
        height: '92vh',
        background: T.pageBg,
        display: 'flex',
        flexDirection: 'column',
      }}
      data-testid="complete-self-drawer"
    >
      {/* 顶部 NavBar */}
      <div
        style={{
          padding: '14px 16px',
          background: '#fff',
          borderRadius: '20px 20px 0 0',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: `1px solid ${T.divider}`,
        }}
      >
        <span
          onClick={onClose}
          style={{ fontSize: 20, color: T.textSecondary, cursor: 'pointer', padding: '0 4px' }}
          data-testid="complete-self-drawer-close"
        >×</span>
        <span style={{ fontSize: 16, fontWeight: 700, color: T.textPrimary }}>完善健康档案</span>
        <span style={{ width: 16 }} />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px 16px' }}>
        {/* 提示文案 */}
        <div
          style={{
            background: '#EFF6FF',
            border: '1px solid #BFDBFE',
            borderRadius: 10,
            padding: '10px 12px',
            fontSize: 12,
            color: '#1E40AF',
            marginBottom: 12,
          }}
        >
          为了给您提供更精准的健康服务，请先完善您的基本资料（姓名、性别、出生日期）。
        </div>

        {/* 必填三项 */}
        <div
          style={{
            background: '#fff',
            borderRadius: 14,
            marginBottom: 12,
            boxShadow: '0 2px 8px rgba(15,23,42,0.05)',
            overflow: 'hidden',
          }}
        >
          <FieldRow
            label="姓名"
            required
            hasError={errFields.has('name')}
            errMsg={errFields.has('name') ? '请填写姓名' : ''}
          >
            <input
              value={name}
              onChange={(e) => { setName(e.target.value); clearErr('name'); }}
              placeholder="请输入姓名"
              maxLength={20}
              style={inputStyle}
              data-testid="complete-self-name"
            />
          </FieldRow>

          <FieldRow
            label="性别"
            required
            hasError={errFields.has('gender')}
            errMsg={errFields.has('gender') ? '请选择性别' : ''}
          >
            <div style={{ display: 'flex', gap: 8 }}>
              {(['男', '女'] as const).map((g) => (
                <button
                  key={g}
                  onClick={() => { setGender(g); clearErr('gender'); }}
                  data-testid={`complete-self-gender-${g}`}
                  style={{
                    flex: 1, padding: '8px 0', borderRadius: 8,
                    background: gender === g ? T.pillBgActive : T.pillBg,
                    color: gender === g ? T.primaryDark : T.textPrimary,
                    border: gender === g ? `1.5px solid ${T.pillBorderActive}` : '1.5px solid transparent',
                    fontSize: 14, fontWeight: 600, cursor: 'pointer',
                  }}
                >{g}</button>
              ))}
            </div>
          </FieldRow>

          <FieldRow
            label="出生日期"
            required
            hasError={errFields.has('birthday')}
            errMsg={errFields.has('birthday') ? '请选择出生日期' : ''}
            isLast
          >
            <div
              onClick={() => { setDatePickerVisible(true); clearErr('birthday'); }}
              style={{
                ...inputStyle,
                cursor: 'pointer',
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'center',
                color: birthday ? T.textPrimary : T.textHint,
              }}
              data-testid="complete-self-birthday"
            >
              <span>{birthday || '请选择'}</span>
              <span style={{ color: T.textHint }}>›</span>
            </div>
          </FieldRow>
        </div>

        {/* 其他（选填）折叠区 */}
        <div
          style={{
            background: '#fff', borderRadius: 14,
            boxShadow: '0 2px 8px rgba(15,23,42,0.05)',
            overflow: 'hidden',
          }}
        >
          <div
            onClick={() => setMoreOpen((v) => !v)}
            style={{
              padding: '14px 16px', cursor: 'pointer',
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              fontSize: 14, fontWeight: 600, color: T.textSecondary,
            }}
            data-testid="complete-self-more-toggle"
          >
            <span>其他（选填）</span>
            <span style={{ color: T.textHint, transition: 'transform .2s', transform: moreOpen ? 'rotate(90deg)' : 'rotate(0)' }}>›</span>
          </div>

          {moreOpen && (
            <div style={{ padding: '0 4px 8px' }} data-testid="complete-self-more-panel">
              <div style={{ display: 'flex' }}>
                <FieldRow label="身高(cm)" inline>
                  <input
                    type="number" value={height} onChange={(e) => setHeight(e.target.value)}
                    placeholder="0-300" style={inputStyle}
                  />
                </FieldRow>
                <FieldRow label="体重(kg)" inline>
                  <input
                    type="number" value={weight} onChange={(e) => setWeight(e.target.value)}
                    placeholder="0-300" style={inputStyle}
                  />
                </FieldRow>
              </div>
              <div style={{ padding: '8px 12px 4px' }}>
                <div style={{ fontSize: 13, color: T.textSecondary, marginBottom: 6, fontWeight: 600 }}>既往病史</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                  {CHRONIC_DISEASE_OPTIONS.map((d) => {
                    const active = chronics.includes(d);
                    return (
                      <button
                        key={d}
                        onClick={() => setChronics((p) => p.includes(d) ? p.filter((x) => x !== d) : [...p, d])}
                        style={{
                          padding: '4px 10px', borderRadius: 14, fontSize: 12,
                          background: active ? T.pillBgActive : T.pillBg,
                          color: active ? T.primaryDark : T.textPrimary,
                          border: active ? `1px solid ${T.pillBorderActive}` : '1px solid transparent',
                          cursor: 'pointer',
                        }}
                      >{d}</button>
                    );
                  })}
                </div>
              </div>
              <div style={{ padding: '10px 12px 4px' }}>
                <div style={{ fontSize: 13, color: T.textSecondary, marginBottom: 6, fontWeight: 600 }}>过敏史</div>
                <input
                  value={drugAllergy} onChange={(e) => setDrugAllergy(e.target.value)}
                  placeholder="药物过敏（如：青霉素、头孢）" style={{ ...inputStyle, marginBottom: 6 }}
                />
                <input
                  value={foodAllergy} onChange={(e) => setFoodAllergy(e.target.value)}
                  placeholder="食物过敏（如：海鲜、坚果）" style={{ ...inputStyle, marginBottom: 6 }}
                />
                <input
                  value={otherAllergy} onChange={(e) => setOtherAllergy(e.target.value)}
                  placeholder="其他过敏（如：花粉、尘螨）" style={inputStyle}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 底部保存 */}
      <div
        style={{
          padding: '10px 16px 16px',
          background: '#fff',
          borderTop: `1px solid ${T.divider}`,
        }}
      >
        <button
          onClick={handleSubmit}
          disabled={!canSubmit}
          data-testid="complete-self-submit"
          style={{
            width: '100%', height: 46, borderRadius: 23,
            background: !canSubmit
              ? '#CBD5E1'
              : `linear-gradient(135deg, ${T.primaryLight}, ${T.primaryDark})`,
            color: '#fff', border: 'none',
            fontSize: 15, fontWeight: 700,
            cursor: !canSubmit ? 'not-allowed' : 'pointer',
            boxShadow: '0 6px 16px rgba(2,132,199,0.25)',
          }}
        >{submitting ? '保存中...' : '保存'}</button>
      </div>

      <DatePicker
        visible={datePickerVisible}
        onClose={() => setDatePickerVisible(false)}
        precision="day"
        max={new Date()}
        min={new Date('1900-01-01')}
        value={birthday ? new Date(birthday) : new Date(1990, 0, 1)}
        title="选择出生日期"
        onConfirm={(val: Date) => {
          const d = val;
          const str = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
          setBirthday(str);
          setDatePickerVisible(false);
          clearErr('birthday');
        }}
      />
    </Popup>
  );
}

const inputStyle: React.CSSProperties = {
  width: '100%',
  padding: '10px 12px',
  borderRadius: 10,
  border: '1px solid #E2E8F0',
  fontSize: 14,
  boxSizing: 'border-box',
  background: '#fff',
  color: '#0F172A',
};

function FieldRow({
  label,
  required,
  children,
  hasError,
  errMsg,
  isLast,
  inline,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
  hasError?: boolean;
  errMsg?: string;
  isLast?: boolean;
  inline?: boolean;
}) {
  return (
    <div
      style={{
        padding: '12px 16px',
        borderBottom: isLast ? 'none' : `1px solid ${T.divider}`,
        flex: inline ? 1 : undefined,
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'center',
        gap: 12,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', flexShrink: 0 }}>
        {required && <span style={{ color: T.textError, marginRight: 3 }}>*</span>}
        <span style={{ fontSize: 13, color: hasError ? T.textError : T.textSecondary, fontWeight: 600 }}>{label}</span>
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {children}
        {hasError && errMsg && (
          <div
            style={{ fontSize: 11, color: T.textError, marginTop: 4 }}
            data-testid={`complete-self-err-${label}`}
          >{errMsg}</div>
        )}
      </div>
    </div>
  );
}
