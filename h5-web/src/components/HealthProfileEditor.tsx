'use client';

import { useState, useRef, useCallback, useEffect, forwardRef, useImperativeHandle } from 'react';
import { Input, DatePicker } from 'antd-mobile';
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

export interface HealthProfileEditorProps {
  profileEdits: HealthProfile;
  onChange: (profile: HealthProfile) => void;
  profileErrors: { nickname?: string; gender?: string; birthday?: string };
  onErrorsChange: (errors: { nickname?: string; gender?: string; birthday?: string }) => void;
  chronicPresets: DiseasePreset[];
  allergyPresets: DiseasePreset[];
  geneticPresets: DiseasePreset[];
  selectedMemberName?: string;
}

export interface HealthProfileEditorRef {
  resetExpanded: () => void;
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
    },
    ref,
  ) => {
    const [expanded, setExpanded] = useState(false);
    const [birthdayPickerVisible, setBirthdayPickerVisible] = useState(false);
    const expandContentRef = useRef<HTMLDivElement>(null);
    const [contentHeight, setContentHeight] = useState(0);

    useImperativeHandle(ref, () => ({
      resetExpanded: () => setExpanded(false),
    }));

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

    return (
      <div className="mt-4 p-4 rounded-xl" style={{ background: '#f9f9f9', border: '1px solid #e8e8e8' }}>
        <div className="text-sm font-semibold mb-3 text-gray-600">
          {selectedMemberName}健康档案
          <span className="text-xs text-gray-400 ml-2 font-normal">（可修改，点击确认后保存）</span>
        </div>

        {/* Always-visible fields: nickname, birthday, gender */}
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
              style={{ '--font-size': '14px', background: '#fff', borderRadius: 8, padding: '6px 12px', border: '1px solid #d9d9d9' } as React.CSSProperties}
            />
            {profileErrors.nickname && (
              <div style={{ color: '#ff4d4f', fontSize: 12, marginTop: 4 }}>{profileErrors.nickname}</div>
            )}
          </div>

          <div>
            <div className="text-xs text-gray-500 mb-1">出生日期 <span style={{ color: '#ff4d4f' }}>*</span></div>
            <div
              className="bg-white rounded-lg px-3 py-2 text-sm cursor-pointer flex items-center justify-between"
              style={{ border: '1px solid #d9d9d9' }}
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
                    border: `1px solid ${profileEdits.gender === g ? '#52c41a' : '#d9d9d9'}`,
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

        {/* Divider with expand/collapse toggle */}
        <div
          className="flex items-center cursor-pointer py-3 mt-3"
          onClick={() => setExpanded((v) => !v)}
        >
          <div style={{ flex: 1, height: 1, background: '#e0e0e0' }} />
          <div
            className="flex items-center gap-1 px-3"
            style={{ fontSize: 12, color: '#999', whiteSpace: 'nowrap' }}
          >
            <span>{expanded ? '收起信息' : '更多信息'}</span>
            <span>（</span>
            <span style={{ color: statusColor }}>{statusText}</span>
            <span>）</span>
            <span style={{ fontSize: 10, transition: 'transform 250ms ease', display: 'inline-block', transform: expanded ? 'rotate(180deg)' : 'rotate(0deg)' }}>
              ▼
            </span>
          </div>
          <div style={{ flex: 1, height: 1, background: '#e0e0e0' }} />
        </div>

        {/* Expandable content */}
        <div
          style={{
            maxHeight: expanded ? contentHeight : 0,
            opacity: expanded ? 1 : 0,
            overflow: 'hidden',
            transition: 'max-height 250ms ease-in-out, opacity 200ms ease-in-out',
          }}
        >
          <div ref={expandContentRef} className="space-y-3">
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
        </div>

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
