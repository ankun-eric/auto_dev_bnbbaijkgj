'use client';

import { useState, useRef, useCallback, useEffect, forwardRef, useImperativeHandle, useMemo } from 'react';
import { Input, DatePicker, Toast } from 'antd-mobile';
import DiseaseTagSelector, { type DiseaseItem } from '@/components/DiseaseTagSelector';

export interface HealthProfile {
  nickname: string;
  birthday: string;
  gender: string;
  height: string;
  weight: string;
  chronic_diseases: DiseaseItem[];
  allergies: DiseaseItem[];
  genetic_diseases: DiseaseItem[];
}

export interface DiseasePreset {
  id: number;
  name: string;
  category: string;
}

export type HealthProfileMode = 'existing' | 'new';

export interface HealthProfileEditorProps {
  profileEdits: HealthProfile;
  onChange: (profile: HealthProfile) => void;
  profileErrors: { nickname?: string; gender?: string; birthday?: string };
  onErrorsChange: (errors: { nickname?: string; gender?: string; birthday?: string }) => void;
  chronicPresets: DiseasePreset[];
  allergyPresets: DiseasePreset[];
  geneticPresets: DiseasePreset[];
  selectedMemberName?: string;
  /** 新增：模式 existing 默认收起+带独立保存按钮；new 默认展开，无独立保存按钮 */
  mode?: HealthProfileMode;
  /** 新增：初始档案快照，用于判断是否脏 */
  initialProfile?: HealthProfile | null;
  /** 新增：独立保存回调，仅 existing 模式使用 */
  onSaveProfile?: (profile: HealthProfile) => Promise<boolean>;
  /** 新增：收起时卡片显示的 emoji */
  memberEmoji?: string;
}

export interface HealthProfileEditorRef {
  resetExpanded: () => void;
  /** 是否有未保存修改 */
  hasUnsavedChanges: () => boolean;
  /** 触发保存（existing 模式），返回 true 表示已保存 */
  saveProfile: () => Promise<boolean>;
  /** 放弃修改，重置为 initialProfile */
  discardChanges: () => void;
  /** 校验必填项 */
  validate: () => boolean;
  expand: () => void;
  collapse: () => void;
}

function isProfileComplete(p: HealthProfile): boolean {
  return !!(
    p.nickname?.trim() &&
    p.gender &&
    p.birthday &&
    p.height?.trim() &&
    p.weight?.trim()
  );
}

function normalizeDiseaseItems(items: DiseaseItem[] | undefined): string {
  if (!items || !Array.isArray(items)) return '[]';
  const normalized = items.map((it) => {
    if (typeof it === 'string') return { type: 'preset', value: it };
    return { type: it.type || 'preset', value: (it.value || '').toString().trim() };
  }).filter((it) => !!it.value);
  normalized.sort((a, b) => {
    if (a.type !== b.type) return a.type < b.type ? -1 : 1;
    return a.value < b.value ? -1 : a.value > b.value ? 1 : 0;
  });
  return JSON.stringify(normalized);
}

function profilesEqual(a: HealthProfile | null | undefined, b: HealthProfile | null | undefined): boolean {
  if (!a || !b) return a === b;
  if ((a.nickname || '').trim() !== (b.nickname || '').trim()) return false;
  if ((a.gender || '') !== (b.gender || '')) return false;
  if ((a.birthday || '') !== (b.birthday || '')) return false;
  if (String(a.height || '').trim() !== String(b.height || '').trim()) return false;
  if (String(a.weight || '').trim() !== String(b.weight || '').trim()) return false;
  if (normalizeDiseaseItems(a.chronic_diseases) !== normalizeDiseaseItems(b.chronic_diseases)) return false;
  if (normalizeDiseaseItems(a.allergies) !== normalizeDiseaseItems(b.allergies)) return false;
  if (normalizeDiseaseItems(a.genetic_diseases) !== normalizeDiseaseItems(b.genetic_diseases)) return false;
  return true;
}

function calcAge(birthday: string): string {
  if (!birthday) return '';
  const parts = birthday.split('-');
  if (parts.length < 3) return '';
  const y = parseInt(parts[0], 10);
  const m = parseInt(parts[1], 10);
  const d = parseInt(parts[2], 10);
  if (!y || !m || !d) return '';
  const now = new Date();
  let age = now.getFullYear() - y;
  const nm = now.getMonth() + 1;
  const nd = now.getDate();
  if (nm < m || (nm === m && nd < d)) age -= 1;
  if (age < 0) return '';
  return `${age}`;
}

/** 触发未保存修改的三按钮确认弹窗 */
export function showUnsavedChangesModal(
  context: 'analyze' | 'switch',
): Promise<'save' | 'discard' | 'cancel'> {
  return new Promise((resolve) => {
    const title = '档案有未保存的修改';
    const primaryLabel = context === 'analyze' ? '保存并分析' : '保存并切换';
    const discardLabel = context === 'analyze' ? '放弃修改并分析' : '放弃修改并切换';
    const mask = document.createElement('div');
    mask.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.45);z-index:9999;display:flex;align-items:center;justify-content:center;';
    const box = document.createElement('div');
    box.style.cssText = 'background:#fff;border-radius:16px;padding:20px 20px 12px;width:80%;max-width:320px;box-shadow:0 4px 20px rgba(0,0,0,0.15);';
    box.innerHTML = `
      <div style="font-size:17px;font-weight:600;text-align:center;margin-bottom:8px;">${title}</div>
      <div style="font-size:14px;color:#666;text-align:center;margin-bottom:16px;line-height:1.5;">您对档案做了修改但尚未保存，请选择：</div>
      <button data-act="save" style="width:100%;padding:11px 0;background:#52c41a;color:#fff;border:none;border-radius:10px;font-size:15px;margin-bottom:8px;cursor:pointer;">${primaryLabel}</button>
      <button data-act="discard" style="width:100%;padding:11px 0;background:#fff;color:#ff4d4f;border:1px solid #ff4d4f;border-radius:10px;font-size:15px;margin-bottom:8px;cursor:pointer;">${discardLabel}</button>
      <button data-act="cancel" style="width:100%;padding:11px 0;background:#fff;color:#666;border:1px solid #d9d9d9;border-radius:10px;font-size:15px;cursor:pointer;">取消</button>
    `;
    mask.appendChild(box);
    const close = (act: 'save' | 'discard' | 'cancel') => {
      try { document.body.removeChild(mask); } catch {}
      resolve(act);
    };
    box.querySelectorAll('button').forEach((b) => {
      (b as HTMLButtonElement).addEventListener('click', () => {
        const act = (b as HTMLButtonElement).getAttribute('data-act') as 'save' | 'discard' | 'cancel';
        close(act);
      });
    });
    mask.addEventListener('click', (e) => {
      if (e.target === mask) close('cancel');
    });
    document.body.appendChild(mask);
  });
}

const HealthProfileEditor = forwardRef<HealthProfileEditorRef, HealthProfileEditorProps>(
  (
    {
      profileEdits,
      onChange,
      profileErrors,
      onErrorsChange,
      chronicPresets,
      allergyPresets,
      geneticPresets,
      selectedMemberName,
      mode = 'existing',
      initialProfile,
      onSaveProfile,
      memberEmoji,
    },
    ref,
  ) => {
    // existing 模式默认收起，new 模式默认展开
    const [expanded, setExpanded] = useState(mode === 'new');
    const [birthdayPickerVisible, setBirthdayPickerVisible] = useState(false);
    const [saving, setSaving] = useState(false);
    const expandContentRef = useRef<HTMLDivElement>(null);
    const [contentHeight, setContentHeight] = useState(0);

    const isDirty = useMemo(() => {
      if (mode === 'new') return false;
      if (!initialProfile) return false;
      return !profilesEqual(initialProfile, profileEdits);
    }, [initialProfile, profileEdits, mode]);

    const validateInternal = useCallback((): boolean => {
      const errors: { nickname?: string; gender?: string; birthday?: string } = {};
      if (!profileEdits.nickname?.trim()) errors.nickname = '请输入姓名';
      if (!profileEdits.gender) errors.gender = '请选择性别';
      if (!profileEdits.birthday) errors.birthday = '请选择出生日期';
      onErrorsChange(errors);
      return Object.keys(errors).length === 0;
    }, [profileEdits, onErrorsChange]);

    const doSave = useCallback(async (): Promise<boolean> => {
      if (!onSaveProfile) return true;
      if (!validateInternal()) {
        Toast.show({ content: '请填写必填项' });
        return false;
      }
      setSaving(true);
      try {
        const ok = await onSaveProfile(profileEdits);
        return ok;
      } finally {
        setSaving(false);
      }
    }, [onSaveProfile, validateInternal, profileEdits]);

    const doDiscard = useCallback(() => {
      if (initialProfile) {
        onChange({ ...initialProfile });
        onErrorsChange({});
      }
    }, [initialProfile, onChange, onErrorsChange]);

    useImperativeHandle(ref, () => ({
      resetExpanded: () => setExpanded(mode === 'new'),
      hasUnsavedChanges: () => isDirty,
      saveProfile: doSave,
      discardChanges: doDiscard,
      validate: validateInternal,
      expand: () => setExpanded(true),
      collapse: () => setExpanded(false),
    }), [mode, isDirty, doSave, doDiscard, validateInternal]);

    const measureHeight = useCallback(() => {
      if (expandContentRef.current) {
        setContentHeight(expandContentRef.current.scrollHeight);
      }
    }, []);

    useEffect(() => {
      measureHeight();
    }, [profileEdits, chronicPresets, allergyPresets, geneticPresets, measureHeight]);

    useEffect(() => {
      if (expanded) {
        const timer = setTimeout(measureHeight, 50);
        return () => clearTimeout(timer);
      }
    }, [expanded, measureHeight]);

    const complete = isProfileComplete(profileEdits);
    const statusText = complete ? '已完善' : '待完善';
    const statusColor = complete ? '#52c41a' : '#fa8c16';

    const updateField = <K extends keyof HealthProfile>(key: K, value: HealthProfile[K]) => {
      onChange({ ...profileEdits, [key]: value });
    };

    // existing 模式且未展开：显示收起卡片
    if (mode === 'existing' && !expanded) {
      const age = calcAge(profileEdits.birthday);
      const genderText = profileEdits.gender === 'male' ? '男' : profileEdits.gender === 'female' ? '女' : '';
      return (
        <div
          className="mt-4 p-4 rounded-xl flex items-center cursor-pointer"
          style={{ background: '#fff', border: '2px solid #e8f5e9', boxShadow: '0 2px 8px rgba(0,0,0,0.04)' }}
          onClick={() => setExpanded(true)}
        >
          <div
            className="flex items-center justify-center mr-3 flex-shrink-0"
            style={{ width: 48, height: 48, borderRadius: '50%', background: '#f0f9f0', fontSize: 24 }}
          >
            {memberEmoji || '👤'}
          </div>
          <div className="flex-1 min-w-0">
            <div className="font-semibold text-gray-800 truncate" style={{ fontSize: 16, marginBottom: 4 }}>
              {profileEdits.nickname?.trim() || selectedMemberName || '未填写姓名'}
            </div>
            <div style={{ fontSize: 13, color: '#666', display: 'flex', alignItems: 'center', gap: 6 }}>
              {genderText ? (
                <span>{genderText}</span>
              ) : (
                <span style={{ color: '#faad14' }}>性别待完善</span>
              )}
              <span style={{ color: '#ccc' }}>·</span>
              {age ? (
                <span>{age}岁</span>
              ) : (
                <span style={{ color: '#faad14' }}>年龄待完善</span>
              )}
            </div>
          </div>
          <div style={{ fontSize: 13, color: '#52c41a', paddingLeft: 8 }}>编辑 ▼</div>
        </div>
      );
    }

    return (
      <div className="mt-4 p-4 rounded-xl" style={{ background: '#f9f9f9', border: '1px solid #e8e8e8' }}>
        <div className="text-sm font-semibold mb-3 text-gray-600 flex items-center justify-between">
          <span>
            {mode === 'new' ? '健康档案（新建）' : `${selectedMemberName || ''}健康档案`}
          </span>
          {mode === 'existing' && (
            <span
              style={{ color: '#52c41a', fontSize: 13, cursor: 'pointer' }}
              onClick={() => setExpanded(false)}
            >
              收起 ▲
            </span>
          )}
        </div>

        {/* Always-visible fields */}
        <div className="space-y-3">
          <div>
            <div className="text-xs text-gray-500 mb-1">姓名 <span style={{ color: '#ff4d4f' }}>*</span></div>
            <Input
              placeholder="请输入姓名"
              value={profileEdits.nickname}
              onChange={(v) => {
                updateField('nickname', v);
                if (v.trim()) onErrorsChange({ ...profileErrors, nickname: undefined });
              }}
              onBlur={() => {
                if (!profileEdits.nickname?.trim()) {
                  onErrorsChange({ ...profileErrors, nickname: '请输入姓名' });
                }
              }}
              style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: `1px solid ${profileErrors.nickname ? '#ff4d4f' : '#d9d9d9'}` } as React.CSSProperties}
            />
            {profileErrors.nickname && (
              <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>{profileErrors.nickname}</div>
            )}
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">出生日期 <span style={{ color: '#ff4d4f' }}>*</span></div>
            <div
              className="bg-white rounded-lg px-3 py-2 text-sm cursor-pointer flex items-center justify-between"
              style={{ border: `1px solid ${profileErrors.birthday ? '#ff4d4f' : '#d9d9d9'}` }}
              onClick={() => setBirthdayPickerVisible(true)}
            >
              <span style={{ color: profileEdits.birthday ? '#333' : '#bbb' }}>
                {profileEdits.birthday || '请选择出生日期'}
              </span>
              <span className="text-gray-300">📅</span>
            </div>
            {profileErrors.birthday && (
              <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>{profileErrors.birthday}</div>
            )}
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">性别 <span style={{ color: '#ff4d4f' }}>*</span></div>
            <div className="flex gap-3">
              {['male', 'female'].map((g) => (
                <div
                  key={g}
                  className="flex-1 text-center py-2 rounded-lg text-sm cursor-pointer"
                  style={{
                    background: profileEdits.gender === g ? '#52c41a' : '#fff',
                    color: profileEdits.gender === g ? '#fff' : '#666',
                    border: `1px solid ${profileEdits.gender === g ? '#52c41a' : (profileErrors.gender ? '#ff4d4f' : '#d9d9d9')}`,
                  }}
                  onClick={() => {
                    updateField('gender', g);
                    onErrorsChange({ ...profileErrors, gender: undefined });
                  }}
                >
                  {g === 'male' ? '男' : '女'}
                </div>
              ))}
            </div>
            {profileErrors.gender && (
              <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>{profileErrors.gender}</div>
            )}
          </div>
        </div>

        {/* 扩展区域（身高、体重、病史）——始终展开（已合并到主区） */}
        <div className="mt-3 space-y-3">
          <div className="flex gap-3">
            <div className="flex-1">
              <div className="text-xs text-gray-500 mb-1">身高 (cm)</div>
              <Input
                type="number"
                placeholder="如：170"
                value={profileEdits.height}
                onChange={(v) => updateField('height', v)}
                style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' } as React.CSSProperties}
              />
            </div>
            <div className="flex-1">
              <div className="text-xs text-gray-500 mb-1">体重 (kg)</div>
              <Input
                type="number"
                placeholder="如：65"
                value={profileEdits.weight}
                onChange={(v) => updateField('weight', v)}
                style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' } as React.CSSProperties}
              />
            </div>
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">既往病史（慢性病史）</div>
            <DiseaseTagSelector
              items={profileEdits.chronic_diseases}
              presets={chronicPresets}
              onChange={(items) => updateField('chronic_diseases', items)}
              activeColor="linear-gradient(135deg, #fa8c16, #faad14)"
              categoryLabel="慢性病史"
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">过敏史</div>
            <DiseaseTagSelector
              items={profileEdits.allergies}
              presets={allergyPresets}
              onChange={(items) => updateField('allergies', items)}
              activeColor="linear-gradient(135deg, #f5222d, #fa541c)"
              categoryLabel="过敏史"
            />
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">家族遗传病史</div>
            <DiseaseTagSelector
              items={profileEdits.genetic_diseases}
              presets={geneticPresets}
              onChange={(items) => updateField('genetic_diseases', items)}
              activeColor="linear-gradient(135deg, #722ed1, #1890ff)"
              categoryLabel="遗传病史"
            />
          </div>
        </div>

        {/* 完善度提示 */}
        <div className="mt-3 text-xs" style={{ color: '#999', textAlign: 'center' }}>
          档案状态：<span style={{ color: statusColor, fontWeight: 500 }}>{statusText}</span>
        </div>

        {/* existing 模式 + isDirty 时显示独立保存按钮 */}
        {mode === 'existing' && isDirty && (
          <button
            onClick={doSave}
            disabled={saving}
            style={{
              marginTop: 12,
              width: '100%',
              padding: '11px 0',
              background: saving ? '#91d5a4' : '#52c41a',
              color: '#fff',
              border: 'none',
              borderRadius: 10,
              fontSize: 15,
              fontWeight: 500,
              cursor: saving ? 'not-allowed' : 'pointer',
            }}
          >
            {saving ? '保存中...' : '保存档案'}
          </button>
        )}

        <DatePicker
          visible={birthdayPickerVisible}
          onClose={() => setBirthdayPickerVisible(false)}
          precision="day"
          max={new Date()}
          min={new Date('1900-01-01')}
          onConfirm={(val) => {
            const d = val as Date;
            const str = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
            updateField('birthday', str);
            onErrorsChange({ ...profileErrors, birthday: undefined });
            setBirthdayPickerVisible(false);
          }}
          title="选择出生日期"
        />
      </div>
    );
  },
);

HealthProfileEditor.displayName = 'HealthProfileEditor';

export default HealthProfileEditor;
