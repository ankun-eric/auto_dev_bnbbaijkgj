'use client';

/**
 * [PRD-FAMILY-MEMBER-V2 2026-05-18] 新版家庭成员表单
 *
 * 核心特性：
 * - 邀请共管横幅（顶部）
 * - 关系网格 4 列纯文字胶囊（15 个一次性展开）
 * - 必填仅 4 项：成员关系、姓名、性别、出生日期
 * - 性别智能锁定（除"其他"外）
 * - 出生日期智能默认值（基于本人出生年）
 * - 关系唯一性硬约束
 * - 关系合理性硬校验
 * - 本人档案未完善拦截
 * - 折叠区：身高、体重、既往病史、过敏史
 * - 保存后关闭抽屉 + Toast
 * - 不支持删除
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import { Toast, Popup, DatePicker } from 'antd-mobile';
import api from '@/lib/api';
import {
  RELATION_DEFS,
  findRelationDef,
  computeDefaultBirthday,
  validateRelationAge,
  calcAge,
  extractSelfBirthYear,
  FAM_THEME as T,
  CHRONIC_DISEASE_OPTIONS,
} from '@/lib/family-relation';

interface ExistingMember {
  id: number;
  is_self: boolean;
  nickname?: string;
  relationship_type?: string;
  relation_type_name?: string;
  birthday?: string;
  gender?: string;
}

interface Props {
  onClose: () => void;
  onSuccess: () => void;
}

export default function NewFamilyMemberModal({ onClose, onSuccess }: Props) {
  const router = useRouter();

  // 数据
  const [members, setMembers] = useState<ExistingMember[]>([]);
  const [selfBirthYear, setSelfBirthYear] = useState<number | null>(null);
  const [selfBirthday, setSelfBirthday] = useState<string>('');
  const [profileLoaded, setProfileLoaded] = useState(false);
  const [showSelfBlocker, setShowSelfBlocker] = useState(false);

  // 表单
  const [selectedRelation, setSelectedRelation] = useState<string>('');
  const [customRelation, setCustomRelation] = useState<string>('');
  const [name, setName] = useState<string>('');
  const [gender, setGender] = useState<'male' | 'female' | ''>('');
  const [birthday, setBirthday] = useState<string>('');
  const [datePickerVisible, setDatePickerVisible] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);
  const [height, setHeight] = useState<string>('');
  const [weight, setWeight] = useState<string>('');
  const [chronics, setChronics] = useState<string[]>([]);
  const [drugAllergy, setDrugAllergy] = useState<string>('');
  const [foodAllergy, setFoodAllergy] = useState<string>('');
  const [otherAllergy, setOtherAllergy] = useState<string>('');

  // 校验态
  const [errFields, setErrFields] = useState<Set<string>>(new Set());
  const [ageInvalid, setAgeInvalid] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const relationOf = useMemo(() => findRelationDef(selectedRelation), [selectedRelation]);
  const isOther = relationOf?.name === '其他';

  // 初始拉数据：本人档案 + 家庭成员列表
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [hpRes, mbRes] = await Promise.allSettled([
          api.get('/api/health/profile'),
          api.get('/api/family/members'),
        ]);
        if (cancelled) return;
        if (hpRes.status === 'fulfilled') {
          const data: any = (hpRes.value as any)?.data || hpRes.value;
          const bd = data?.birthday || data?.birth_date || null;
          if (bd) {
            setSelfBirthday(String(bd).slice(0, 10));
            setSelfBirthYear(extractSelfBirthYear({ birthday: bd }));
          }
        }
        if (mbRes.status === 'fulfilled') {
          const data: any = (mbRes.value as any)?.data || mbRes.value;
          const items: ExistingMember[] = Array.isArray(data?.items)
            ? data.items
            : Array.isArray(data)
            ? data
            : [];
          setMembers(items);
          // 本人 birthday 也可从家庭成员中取
          const self = items.find((m) => m.is_self);
          if (self?.birthday) {
            const y = extractSelfBirthYear({ birthday: self.birthday });
            if (y && !selfBirthYear) {
              setSelfBirthYear(y);
              setSelfBirthday(String(self.birthday).slice(0, 10));
            }
          }
        }
      } finally {
        if (!cancelled) setProfileLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 加载完毕后判断是否需要拦截
  useEffect(() => {
    if (profileLoaded && !selfBirthYear) {
      setShowSelfBlocker(true);
    }
  }, [profileLoaded, selfBirthYear]);

  // 已存在的唯一关系
  const usedUniqueRelations = useMemo(() => {
    const set = new Set<string>();
    members.forEach((m) => {
      if (m.is_self) return;
      const rn = m.relation_type_name || m.relationship_type;
      const def = findRelationDef(rn || '');
      if (def && def.unique) set.add(def.name);
    });
    return set;
  }, [members]);

  // 当选择关系时：自动锁定性别 + 自动填充默认出生年
  const handleSelectRelation = (rn: string) => {
    if (usedUniqueRelations.has(rn)) {
      Toast.show({ content: '已添加过该关系', icon: 'fail' });
      return;
    }
    setSelectedRelation(rn);
    const def = findRelationDef(rn);
    if (def) {
      if (def.gender === 'M') setGender('male');
      else if (def.gender === 'F') setGender('female');
      else setGender('');
      // 自动填充出生日期默认值
      if (selfBirthYear) {
        const def_bday = computeDefaultBirthday(selfBirthYear, rn);
        setBirthday(def_bday);
      }
    }
    setErrFields((s) => {
      const ns = new Set(s);
      ns.delete('relation');
      ns.delete('birthday');
      return ns;
    });
    setAgeInvalid(false);
  };

  // 表单字段清错
  const clearErr = (field: string) => {
    setErrFields((s) => {
      if (!s.has(field)) return s;
      const ns = new Set(s);
      ns.delete(field);
      return ns;
    });
    if (field === 'birthday' || field === 'relation') setAgeInvalid(false);
  };

  // 校验
  const validate = (): boolean => {
    const errs = new Set<string>();
    if (!selectedRelation) errs.add('relation');
    if (isOther) {
      const tr = customRelation.trim();
      if (!tr || tr.length < 1 || tr.length > 8) errs.add('customRelation');
    }
    const n = name.trim();
    if (!n || n.length < 1 || n.length > 12) errs.add('name');
    if (!gender) errs.add('gender');
    if (!birthday) errs.add('birthday');
    // 出生日期上限：≤ 今天
    if (birthday && birthday > new Date().toISOString().slice(0, 10)) {
      errs.add('birthday');
    }
    // 关系合理性
    let invalidAge = false;
    if (selectedRelation && birthday && selfBirthday) {
      if (!validateRelationAge(selectedRelation, birthday, selfBirthday)) {
        invalidAge = true;
        errs.add('relation');
        errs.add('birthday');
      }
    }
    setErrFields(errs);
    setAgeInvalid(invalidAge);
    return errs.size === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) {
      Toast.show({ content: '请补全或修正标红字段', icon: 'fail' });
      return;
    }
    const def = findRelationDef(selectedRelation)!;
    const relationLabel = isOther ? customRelation.trim() : def.name;
    const nickname = name.trim();
    setSubmitting(true);
    try {
      const body: any = {
        relationship_type: relationLabel,
        nickname,
        name: nickname,
        gender: gender === 'male' ? 'male' : 'female',
        birthday,
      };
      if (height) body.height = Number(height);
      if (weight) body.weight = Number(weight);
      if (chronics.length) body.medical_histories = chronics;
      // 后端 allergies 是 List[str]，前端把三组按 "药物:xxx、食物:xxx" 形态合并为字符串数组
      const allergies: string[] = [];
      const pushParts = (prefix: string, raw: string) => {
        raw.split(/[,，;；\s]+/).filter(Boolean).forEach((s) => allergies.push(`${prefix}:${s}`));
      };
      if (drugAllergy.trim()) pushParts('药物', drugAllergy);
      if (foodAllergy.trim()) pushParts('食物', foodAllergy);
      if (otherAllergy.trim()) pushParts('其他', otherAllergy);
      if (allergies.length) body.allergies = allergies;

      await api.post('/api/family/members', body);
      Toast.show({ content: '添加成功', icon: 'success' });
      onSuccess();
    } catch (e: any) {
      const detail = e?.response?.data?.detail || '保存失败';
      Toast.show({ content: typeof detail === 'string' ? detail : '保存失败', icon: 'fail' });
    } finally {
      setSubmitting(false);
    }
  };

  const goCompleteSelfProfile = () => {
    setShowSelfBlocker(false);
    onClose();
    router.push('/health-profile');
  };

  const cancelBlocker = () => {
    setShowSelfBlocker(false);
    onClose();
  };

  const goInvite = () => {
    // 跳转邀请共管页（复用现有）
    onClose();
    router.push('/family-invite');
  };

  if (showSelfBlocker) {
    return (
      <div
        style={{
          position: 'fixed', inset: 0, zIndex: 3000,
          background: 'rgba(15,23,42,0.55)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}
        data-testid="fm-v2-self-blocker"
      >
        <div
          style={{
            width: '78%', maxWidth: 320, background: '#fff',
            borderRadius: 16, padding: '22px 18px 18px', textAlign: 'center',
            boxShadow: '0 12px 40px rgba(2,132,199,0.25)',
          }}
        >
          <div
            style={{
              width: 44, height: 44, borderRadius: '50%',
              background: T.pillBg, color: T.primary,
              display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 24, fontWeight: 700, marginBottom: 10,
            }}
          >!</div>
          <div style={{ fontSize: 16, fontWeight: 700, color: T.textPrimary, marginBottom: 16 }}>
            请先完善您的个人档案
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button
              onClick={cancelBlocker}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 22,
                background: '#F1F5F9', color: T.textPrimary,
                border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >取消</button>
            <button
              onClick={goCompleteSelfProfile}
              style={{
                flex: 1, padding: '10px 0', borderRadius: 22,
                background: `linear-gradient(135deg, ${T.primaryLight}, ${T.primaryDark})`,
                color: '#fff', border: 'none', fontSize: 14, fontWeight: 600, cursor: 'pointer',
              }}
            >去完善</button>
          </div>
        </div>
      </div>
    );
  }

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
      data-testid="fm-v2-modal"
    >
      {/* 顶部 NavBar */}
      <div
        style={{
          padding: '14px 16px',
          background: '#fff',
          borderRadius: '20px 20px 0 0',
          display: 'flex', alignItems: 'center', justifyContent: 'space-between',
          borderBottom: `1px solid ${T.divider}`,
        }}
      >
        <span onClick={onClose} style={{ fontSize: 20, color: T.textSecondary, cursor: 'pointer', padding: '0 4px' }}>‹</span>
        <span style={{ fontSize: 16, fontWeight: 700, color: T.textPrimary }}>添加家庭成员</span>
        <span style={{ width: 16 }} />
      </div>

      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 16px 16px' }}>
        {/* 邀请横幅 */}
        <div
          onClick={goInvite}
          style={{
            background: `linear-gradient(135deg, ${T.primaryLight}, ${T.primaryDark})`,
            borderRadius: 14, padding: '12px 14px',
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            cursor: 'pointer', boxShadow: '0 4px 12px rgba(2,132,199,0.18)',
            marginBottom: 14,
          }}
          data-testid="fm-v2-invite-banner"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ fontSize: 20 }}>💙</div>
            <div>
              <div style={{ color: '#fff', fontSize: 14, fontWeight: 700 }}>邀请家人加入健康守护计划</div>
              <div style={{ color: 'rgba(255,255,255,0.85)', fontSize: 11, marginTop: 2 }}>共同管理家庭健康档案</div>
            </div>
          </div>
          <div
            style={{
              background: '#fff', color: T.primaryDark,
              fontSize: 12, fontWeight: 600, padding: '6px 12px', borderRadius: 14,
            }}
          >去邀请</div>
        </div>

        {/* 错误顶部条 */}
        {ageInvalid && (
          <div
            style={{
              background: '#FEF2F2', border: `1px solid #FECACA`,
              borderRadius: 10, padding: '8px 12px', color: T.textError,
              fontSize: 12, marginBottom: 12,
            }}
            data-testid="fm-v2-error-banner"
          >
            ⚠️ 关系与出生日期不符，请检查后重新填写
          </div>
        )}

        {/* 关系网格 */}
        <div
          style={{
            background: '#fff', borderRadius: 14, padding: '14px 12px 12px',
            marginBottom: 12, boxShadow: '0 2px 8px rgba(15,23,42,0.05)',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'baseline', marginBottom: 10 }}>
            <span style={{ color: T.textError, fontSize: 14, marginRight: 4 }}>*</span>
            <span style={{ fontSize: 14, color: T.textSecondary, fontWeight: 600 }}>成员关系</span>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 8 }}>
            {RELATION_DEFS.map((def) => {
              const isActive = selectedRelation === def.name;
              const isDisabled = def.unique && usedUniqueRelations.has(def.name);
              const isErr = ageInvalid && isActive;
              return (
                <button
                  key={def.name}
                  data-testid={`fm-v2-relation-${def.name}`}
                  disabled={isDisabled}
                  onClick={() => handleSelectRelation(def.name)}
                  title={isDisabled ? '已添加过该关系' : ''}
                  style={{
                    height: 36, borderRadius: 10, padding: 0,
                    background: isErr
                      ? '#FEE2E2'
                      : isActive
                        ? T.pillBgActive
                        : isDisabled
                          ? T.pillBgDisabled
                          : T.pillBg,
                    color: isErr
                      ? T.textError
                      : isActive
                        ? T.primaryDark
                        : isDisabled
                          ? T.textHint
                          : T.textPrimary,
                    border: isErr
                      ? `1.5px solid ${T.errorBorder}`
                      : isActive
                        ? `1.5px solid ${T.pillBorderActive}`
                        : '1.5px solid transparent',
                    fontSize: 13, fontWeight: isActive ? 600 : 500,
                    cursor: isDisabled ? 'not-allowed' : 'pointer',
                    opacity: isDisabled ? 0.6 : 1,
                  }}
                >{def.name}</button>
              );
            })}
          </div>
          {isOther && (
            <FieldRow label="关系" required hasError={errFields.has('customRelation')}>
              <input
                value={customRelation}
                onChange={(e) => { setCustomRelation(e.target.value); clearErr('customRelation'); }}
                placeholder="如：舅舅、表妹"
                maxLength={8}
                style={inputStyle}
                data-testid="fm-v2-custom-relation"
              />
            </FieldRow>
          )}
        </div>

        {/* 基础字段卡片 */}
        <div
          style={{
            background: '#fff', borderRadius: 14,
            marginBottom: 12, boxShadow: '0 2px 8px rgba(15,23,42,0.05)',
            overflow: 'hidden',
          }}
        >
          <FieldRow label="姓名" required hasError={errFields.has('name')} errMsg={errFields.has('name') ? '请输入姓名（1-12 字）' : ''}>
            <input
              value={name}
              onChange={(e) => { setName(e.target.value); clearErr('name'); }}
              placeholder="请输入"
              maxLength={12}
              style={inputStyle}
              data-testid="fm-v2-name"
            />
          </FieldRow>

          <FieldRow label="性别" required hasError={errFields.has('gender')}>
            {relationOf && relationOf.gender ? (
              <div
                style={{
                  ...inputStyle, color: T.textHint, background: '#F8FAFC',
                  display: 'flex', alignItems: 'center',
                }}
                data-testid="fm-v2-gender-locked"
              >
                {relationOf.gender === 'M' ? '男（自动）' : '女（自动）'}
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 8 }}>
                {(['male', 'female'] as const).map((g) => (
                  <button
                    key={g}
                    onClick={() => { setGender(g); clearErr('gender'); }}
                    data-testid={`fm-v2-gender-${g}`}
                    style={{
                      flex: 1, padding: '8px 0', borderRadius: 8,
                      background: gender === g ? T.pillBgActive : T.pillBg,
                      color: gender === g ? T.primaryDark : T.textPrimary,
                      border: gender === g ? `1.5px solid ${T.pillBorderActive}` : '1.5px solid transparent',
                      fontSize: 14, fontWeight: 600, cursor: 'pointer',
                    }}
                  >{g === 'male' ? '男' : '女'}</button>
                ))}
              </div>
            )}
          </FieldRow>

          <FieldRow
            label="出生日期"
            required
            hasError={errFields.has('birthday') || (ageInvalid && true)}
            isLast
          >
            <div
              onClick={() => { setDatePickerVisible(true); clearErr('birthday'); }}
              style={{
                ...inputStyle, cursor: 'pointer', display: 'flex',
                justifyContent: 'space-between', alignItems: 'center',
                color: ageInvalid ? T.textError : birthday ? T.textPrimary : T.textHint,
              }}
              data-testid="fm-v2-birthday"
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
            data-testid="fm-v2-more-toggle"
          >
            <span>其他（选填）</span>
            <span style={{ color: T.textHint, transition: 'transform .2s', transform: moreOpen ? 'rotate(90deg)' : 'rotate(0)' }}>›</span>
          </div>

          {moreOpen && (
            <div style={{ padding: '0 4px 8px' }}>
              <div style={{ display: 'flex' }}>
                <FieldRow label="身高(cm)" inline>
                  <input
                    type="number" value={height} onChange={(e) => setHeight(e.target.value)}
                    placeholder="0-300" style={inputStyle} data-testid="fm-v2-height"
                  />
                </FieldRow>
                <FieldRow label="体重(kg)" inline>
                  <input
                    type="number" value={weight} onChange={(e) => setWeight(e.target.value)}
                    placeholder="0-300" style={inputStyle} data-testid="fm-v2-weight"
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

      {/* 底部 */}
      <div
        style={{
          padding: '10px 16px 16px',
          background: '#fff',
          borderTop: `1px solid ${T.divider}`,
        }}
      >
        <div style={{ fontSize: 11, color: T.textHint, textAlign: 'center', marginBottom: 8 }}>
          请保证信息真实性，将基于您的档案信息提供个性化健康服务
        </div>
        <button
          onClick={handleSubmit}
          disabled={submitting || ageInvalid}
          data-testid="fm-v2-submit"
          style={{
            width: '100%', height: 46, borderRadius: 23,
            background: (submitting || ageInvalid)
              ? '#CBD5E1'
              : `linear-gradient(135deg, ${T.primaryLight}, ${T.primaryDark})`,
            color: '#fff', border: 'none',
            fontSize: 15, fontWeight: 700,
            cursor: (submitting || ageInvalid) ? 'not-allowed' : 'pointer',
            boxShadow: '0 6px 16px rgba(2,132,199,0.25)',
          }}
        >{submitting ? '保存中...' : '保存'}</button>
      </div>

      {/* 出生日期选择器 */}
      <DatePicker
        visible={datePickerVisible}
        onClose={() => setDatePickerVisible(false)}
        precision="day"
        max={new Date()}
        min={new Date('1900-01-01')}
        value={birthday ? new Date(birthday) : new Date()}
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
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: 6 }}>
        {required && <span style={{ color: T.textError, marginRight: 3 }}>*</span>}
        <span style={{ fontSize: 13, color: hasError ? T.textError : T.textSecondary, fontWeight: 600 }}>{label}</span>
      </div>
      {children}
      {hasError && errMsg && (
        <div style={{ fontSize: 11, color: T.textError, marginTop: 4 }}>{errMsg}</div>
      )}
    </div>
  );
}
