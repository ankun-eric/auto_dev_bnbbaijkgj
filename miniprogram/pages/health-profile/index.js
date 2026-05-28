/**
 * [PRD-健康档案路径统一 2026-05-16] 小程序端 v2 对齐版逻辑
 * 原文件备份为 index.js.bak-2026-05-16
 *
 * 对齐 H5 v2 信息架构：成员条 → Hero卡 → 5 Tab（今日数据/健康信息/用药计划/共管与提醒/健康事件）
 * 接口对齐：/api/family/members、/api/health/profile/member/{id}、
 *           /api/health-profile-v3/{id}/today-metrics、
 *           /api/health-profile-v3/{id}/medication-plan、
 *           /api/prd469/summary/{id}、/api/family/management、/api/disease-presets
 */
const { get, put, post, del } = require('../../utils/request');
// [BUG_FIX_TIMEZONE_GLOBAL_20260517] 统一时间解析/格式化
const { parseServerTime, formatDateTime, formatDate, formatTime, formatRelativeTime, formatFriendlyTime } = require('../../utils/datetime');

const TAB_LIST = [
  { id: 'today-data',     label: '今日数据' },
  { id: 'health-info',    label: '健康信息' },
  { id: 'medication-plan',label: '用药计划' },
  { id: 'care-reminder',  label: '守护与提醒' },
  { id: 'health-events',  label: '健康事件' },
];

const BLOOD_TYPES = ['A', 'B', 'AB', 'O', '未知'];

function calcAge(birthday) {
  if (!birthday) return null;
  try {
    const b = parseServerTime(birthday);
    if (!b) return null;
    const now = new Date();
    let age = now.getFullYear() - b.getFullYear();
    const m = now.getMonth() - b.getMonth();
    if (m < 0 || (m === 0 && now.getDate() < b.getDate())) age--;
    return age >= 0 ? age : null;
  } catch (_) { return null; }
}

function buildBaseLine(p) {
  if (!p) return '';
  const age = calcAge(p.birthday);
  const parts = [
    p.gender || '',
    age != null ? age + ' 岁' : '',
    p.height ? p.height + ' cm' : '',
    p.weight ? p.weight + ' kg' : '',
    p.blood_type ? p.blood_type + '型' : '',
  ].filter(Boolean);
  return parts.join(' · ');
}

function splitPresetAndCustom(list) {
  const presets = [];
  const customs = [];
  (list || []).forEach((it) => {
    if (typeof it === 'string') presets.push({ value: it });
    else if (it && it.type === 'custom') customs.push(it);
    else if (it && it.value) presets.push({ value: it.value });
  });
  return { presets, customs };
}

Page({
  data: {
    members: [],
    selectedMemberId: null,
    selectedMember: null,
    profile: null,
    isLinked: false,
    isManagedByOthers: false,
    managedByList: [],

    tabList: TAB_LIST,
    activeTab: 'today-data',

    todayMetrics: null,
    todayCells: [],
    medCell: { checked: 0, total: 0, has_overdue: false, percent: 0 },

    medications: [],
    events: [],

    heroMetrics: [
      { label: '既往病史', count: 0, unit: '项' },
      { label: '过敏史', count: 0, unit: '项' },
      { label: '家族遗传', count: 0, unit: '项' },
      { label: '长期用药', count: 0, unit: '种' },
    ],
    baseLine: '',

    guardedFlags: {},
    managedUserIdMap: {},
    managedCount: 0,
    myGuardianCount: 0,
    deviceCount: 0,
    medHeroText: '今日用药 · 0',

    chronicPresets: [],
    allergyPresets: [],
    geneticPresets: [],

    chronicCustomItems: [],
    allergyCustomItems: [],
    geneticCustomItems: [],

    showChronicOther: false,
    showAllergyOther: false,
    showGeneticOther: false,

    chronicOtherInput: '',
    allergyOtherInput: '',
    geneticOtherInput: '',

    smokingOptions: ['从不', '偶尔', '经常'],
    drinkingOptions: ['从不', '偶尔', '经常'],

    bloodTypes: BLOOD_TYPES,
    bloodTypeIndex: -1,

    saving: false,
    heroSaving: false,
    showHeroEdit: false,
    heroEditDraft: null,

    // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人资料完善弹窗 + 抽屉
    selfNeedComplete: false,
    selfMissingFields: [],
    showSelfCompleteDialog: false,
    showSelfCompleteDrawer: false,
    selfDialogShownInSession: false,
    selfFormDraft: { name: '', gender: '', birthday: '', height: '', weight: '' },
    selfFormErrs: { name: false, gender: false, birthday: false },
    selfFormCanSubmit: false,
    selfFormSubmitting: false,
    selfDrawerMoreOpen: false,
    todayDateStr: '',
  },

  onLoad() {
    this.loadPresets();
    this.loadMembers();
    this.loadManagedByInfo();
    this.loadGuardedFlags();
    this.loadGuardianSummary();
    this.loadMyGuardianCount();
    this.loadDeviceCount();
    // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 拉本人完善状态
    this.loadSelfNeedComplete();
    // 今日日期字符串（出生日期 picker end 上限）
    const t = new Date();
    const today = `${t.getFullYear()}-${String(t.getMonth() + 1).padStart(2, '0')}-${String(t.getDate()).padStart(2, '0')}`;
    this.setData({ todayDateStr: today });
  },

  onShow() {
    if (this.data.selectedMemberId && this.data.profile && this.data.profile.id) {
      this.loadMedicationPlan(this.data.profile.id);
    }
    this.loadGuardedFlags();
    this.loadGuardianSummary();
    this.loadMyGuardianCount();
    this.loadDeviceCount();
  },

  // [PRD-HEALTH-ARCHIVE-OPTIM-V1 F3] 加载被守护标记
  async loadGuardedFlags() {
    try {
      const res = await get('/api/health-archive/family-members/guarded-flags', {}, { showLoading: false, suppressErrorToast: true });
      const items = (res && (res.items || (res.data && res.data.items))) || [];
      const flags = {};
      const userIdMap = {};
      items.forEach((it) => {
        if (it.guarded) flags[it.member_id] = true;
        if (it.managed_user_id) userIdMap[it.member_id] = it.managed_user_id;
      });
      this.setData({ guardedFlags: flags, managedUserIdMap: userIdMap });
    } catch (_) {}
  },

  // [PRD-HEALTH-ARCHIVE-OPTIM-V1 F5] 已守护 N 人摘要
  async loadGuardianSummary() {
    try {
      const res = await get('/api/health-archive/guardian/summary', {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      this.setData({ managedCount: data.managed_count || 0 });
    } catch (_) {}
  },

  // [PRD-HEALTH-ARCHIVE-OPTIM-V1 F4-3] 今日用药文案
  async loadMedHero(consultantId) {
    try {
      const url = `/api/medication-plans/hero-count?consultant_id=${consultantId}`;
      const res = await get(url, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      this.setData({ medHeroText: data.display_text || '今日用药 · 0' });
    } catch (_) {
      this.setData({ medHeroText: '今日用药 · 0' });
    }
  },

  async loadMyGuardianCount() {
    try {
      const res = await get('/api/reverse-guardian/guardian-count', {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      this.setData({ myGuardianCount: data.count || 0 });
    } catch (_) {}
  },

  async loadDeviceCount() {
    try {
      const res = await get('/api/devices/my', {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const items = Array.isArray(data.items) ? data.items : (Array.isArray(data) ? data : []);
      this.setData({ deviceCount: items.length });
    } catch (_) {}
  },

  onTapTodayMedication() {
    wx.navigateTo({ url: '/pages/health-plan/medication-reminder/index' });
  },

  onTapGuardianList() {
    wx.navigateTo({ url: '/pages/family-guardian-list/index' });
  },

  onTapMyGuardians() {
    wx.navigateTo({ url: '/pages/my-guardians/index' });
  },

  onTapDevices() {
    const memberId = this.data.selectedMemberId;
    const url = memberId ? `/pages/devices/index?member_id=${memberId}` : '/pages/devices/index';
    wx.navigateTo({
      url,
      fail() { wx.showToast({ title: '设备页面开发中', icon: 'none' }); },
    });
  },

  onTapInviteCoManage() {
    const id = this.data.selectedMemberId;
    if (!id) return;
    wx.navigateTo({ url: `/pages/family-invite/index?member_id=${id}` });
  },

  onTapManageGuardian() {
    const memberId = this.data.selectedMemberId;
    const targetUserId = this.data.managedUserIdMap[memberId];
    if (targetUserId) {
      wx.navigateTo({ url: `/pages/family-guardian-list/index?target=${targetUserId}` });
    } else {
      wx.navigateTo({ url: '/pages/family-guardian-list/index' });
    }
  },

  /* ============ 数据加载 ============ */
  async loadPresets() {
    try {
      const opt = { showLoading: false, suppressErrorToast: true };
      const [chronic, allergy, genetic] = await Promise.all([
        get('/api/disease-presets', { category: 'chronic' }, opt),
        get('/api/disease-presets', { category: 'allergy' }, opt),
        get('/api/disease-presets', { category: 'genetic' }, opt),
      ]);
      const pick = (res) => {
        const items = (res && (res.items || res.data || res)) || [];
        if (Array.isArray(items)) return items.map((x) => x.name || x);
        return [];
      };
      this.setData({
        chronicPresets: pick(chronic),
        allergyPresets: pick(allergy),
        geneticPresets: pick(genetic),
      });
    } catch (_) {}
  },

  async loadMembers() {
    try {
      const res = await get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true });
      const items = (res && (res.items || (res.data && res.data.items))) || [];
      if (items.length === 0) {
        this.setData({ members: [] });
        return;
      }
      const self = items.find((m) => m.is_self) || items[0];
      this.setData({ members: items, selectedMemberId: self.id });
      this.onSelectMember({ currentTarget: { dataset: { id: self.id } } });
    } catch (_) {
      this.setData({ members: [] });
    }
  },

  async loadManagedByInfo() {
    try {
      const res = await get('/api/family/managed-by', {}, { showLoading: false, suppressErrorToast: true });
      const list = (res && (res.items || res.data || [])) || [];
      this.setData({
        managedByList: Array.isArray(list) ? list : [],
        isManagedByOthers: Array.isArray(list) && list.length > 0,
      });
    } catch (_) {}
  },

  onSelectMember(e) {
    const id = Number(e.currentTarget.dataset.id);
    const m = (this.data.members || []).find((x) => x.id === id);
    this.setData({ selectedMemberId: id, selectedMember: m || null });
    this.loadProfile(id);
    this.loadLinkStatus(id);
    // [PRD-HEALTH-ARCHIVE-OPTIM-V1 F2] 按选中咨询人加载今日用药数
    const cid = m ? (m.is_self ? 0 : m.id) : -1;
    this.loadMedHero(cid);
    // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人 Tab 激活 + needComplete=true → 延迟 500ms 弹窗
    this.maybeShowSelfCompleteDialog();
  },

  maybeShowSelfCompleteDialog() {
    if (this.data.selfDialogShownInSession) return;
    if (!this.data.selfNeedComplete) return;
    const m = this.data.selectedMember;
    if (!m || !m.is_self) return;
    if (this._selfDialogTimer) clearTimeout(this._selfDialogTimer);
    this._selfDialogTimer = setTimeout(() => {
      this.setData({
        showSelfCompleteDialog: true,
        selfDialogShownInSession: true,
      });
    }, 500);
  },

  async loadSelfNeedComplete() {
    try {
      const res = await get('/api/health-profile/self', {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const need = !!data.needComplete;
      const missing = Array.isArray(data.missingFields) ? data.missingFields : [];
      // 抽屉初始 draft
      const draft = {
        name: (data.name && data.name !== '本人') ? data.name : '',
        gender: (data.gender === 'male' || data.gender === 'M') ? '男'
          : (data.gender === 'female' || data.gender === 'F') ? '女'
          : (data.gender || ''),
        birthday: (data.birthday || '').slice(0, 10),
        height: data.height != null ? String(data.height) : '',
        weight: data.weight != null ? String(data.weight) : '',
      };
      this.setData({
        selfNeedComplete: need,
        selfMissingFields: missing,
        selfFormDraft: draft,
      });
      this.recalcSelfFormCanSubmit();
      // 如果当前已经在本人 Tab，触发弹窗
      this.maybeShowSelfCompleteDialog();
    } catch (_) {
      this.setData({ selfNeedComplete: false, selfMissingFields: [] });
    }
  },

  onSelfCompleteLater() {
    this.setData({ showSelfCompleteDialog: false });
  },

  onSelfCompleteGo() {
    this.setData({ showSelfCompleteDialog: false, showSelfCompleteDrawer: true });
  },

  closeSelfCompleteDrawer() {
    this.setData({ showSelfCompleteDrawer: false });
  },

  toggleSelfDrawerMore() {
    this.setData({ selfDrawerMoreOpen: !this.data.selfDrawerMoreOpen });
  },

  onSelfFormInput(e) {
    const field = e.currentTarget.dataset.field;
    const draft = Object.assign({}, this.data.selfFormDraft, { [field]: e.detail.value });
    const errs = Object.assign({}, this.data.selfFormErrs);
    if (field === 'name') errs.name = false;
    this.setData({ selfFormDraft: draft, selfFormErrs: errs });
    this.recalcSelfFormCanSubmit();
  },

  onSelfGenderPick(e) {
    const value = e.currentTarget.dataset.value;
    const draft = Object.assign({}, this.data.selfFormDraft, { gender: value });
    const errs = Object.assign({}, this.data.selfFormErrs, { gender: false });
    this.setData({ selfFormDraft: draft, selfFormErrs: errs });
    this.recalcSelfFormCanSubmit();
  },

  onSelfBirthdayPick(e) {
    const draft = Object.assign({}, this.data.selfFormDraft, { birthday: e.detail.value });
    const errs = Object.assign({}, this.data.selfFormErrs, { birthday: false });
    this.setData({ selfFormDraft: draft, selfFormErrs: errs });
    this.recalcSelfFormCanSubmit();
  },

  recalcSelfFormCanSubmit() {
    const d = this.data.selfFormDraft || {};
    const name = String(d.name || '').trim();
    const nameOk = !!name && name !== '本人' && name.length <= 20;
    const ok = nameOk && !!d.gender && !!d.birthday;
    this.setData({ selfFormCanSubmit: ok });
  },

  async onSelfFormSubmit() {
    const d = this.data.selfFormDraft || {};
    const name = String(d.name || '').trim();
    const errs = { name: false, gender: false, birthday: false };
    if (!name || name === '本人' || name.length > 20) errs.name = true;
    if (!d.gender) errs.gender = true;
    if (!d.birthday) errs.birthday = true;
    if (errs.name || errs.gender || errs.birthday) {
      this.setData({ selfFormErrs: errs });
      return;
    }
    this.setData({ selfFormSubmitting: true });
    try {
      const body = {
        name,
        gender: d.gender,
        birthday: d.birthday,
      };
      if (d.height) body.height = Number(d.height);
      if (d.weight) body.weight = Number(d.weight);
      await put('/api/health-profile/self', body);
      wx.showToast({ title: '保存成功', icon: 'success' });
      this.setData({
        showSelfCompleteDrawer: false,
        selfNeedComplete: false,
      });
      // 刷新成员列表（本人 Tab 名变更）+ 当前 profile
      this.loadMembers();
      if (this.data.selectedMemberId) this.loadProfile(this.data.selectedMemberId);
    } catch (e) {
      let msg = '保存失败';
      const detail = e && e.data && e.data.detail;
      if (detail && typeof detail === 'object' && detail.field_errors) {
        const fe = detail.field_errors;
        this.setData({
          selfFormErrs: { name: !!fe.name, gender: !!fe.gender, birthday: !!fe.birthday },
        });
        msg = detail.message || '请补全必填字段';
      } else if (typeof detail === 'string') {
        msg = detail;
      }
      wx.showToast({ title: msg, icon: 'none' });
    } finally {
      this.setData({ selfFormSubmitting: false });
    }
  },

  async loadProfile(memberId) {
    try {
      const res = await get(`/api/health/profile/member/${memberId}`, {}, { showLoading: false, suppressErrorToast: true });
      const p = (res && (res.data || res)) || {};
      const chronic = splitPresetAndCustom(p.chronic_diseases);
      const allergy = splitPresetAndCustom(p.allergies);
      const genetic = splitPresetAndCustom(p.genetic_diseases);
      this.setData({
        profile: p,
        baseLine: buildBaseLine(p),
        chronicCustomItems: chronic.customs,
        allergyCustomItems: allergy.customs,
        geneticCustomItems: genetic.customs,
      });
      if (p && p.id) {
        this.loadTodayMetrics(p.id);
        this.loadMedicationPlan(p.id);
        this.loadHeroSummary(p.id);
        this.loadHealthEvents(p.id);
      }
    } catch (_) {
      this.setData({ profile: null });
    }
  },

  async loadTodayMetrics(profileId) {
    try {
      const res = await get(`/api/health-profile-v3/${profileId}/today-metrics`, {}, { showLoading: false, suppressErrorToast: true });
      const tm = (res && (res.data || res)) || null;
      this.setData({ todayMetrics: tm });
      this.rebuildTodayCells(tm);
    } catch (_) {
      this.setData({ todayMetrics: null });
      this.rebuildTodayCells(null);
    }
  },

  rebuildTodayCells(tm) {
    const v = (obj, key, sub) => {
      if (!obj) return '—';
      const x = obj.value;
      if (!x) return '—';
      if (sub) return x[sub] != null ? x[sub] : '—';
      return x[key] != null ? x[key] : '—';
    };
    const bp = tm && tm.blood_pressure;
    const cells = [
      {
        id: 'blood_pressure', label: '血压', unit: 'mmHg', icon: '💓',
        value: (bp && bp.value)
          ? `${bp.value.systolic || '-'}/${bp.value.diastolic || '-'}`
          : '—',
        abnormal: !!(bp && bp.is_abnormal),
      },
      {
        id: 'blood_glucose', label: '血糖', unit: 'mmol/L', icon: '🩸',
        value: v(tm && tm.blood_glucose, 'value'),
        abnormal: !!(tm && tm.blood_glucose && tm.blood_glucose.is_abnormal),
      },
      {
        id: 'heart_rate', label: '心率', unit: 'bpm', icon: '❤️',
        value: v(tm && tm.heart_rate, 'value'),
        abnormal: !!(tm && tm.heart_rate && tm.heart_rate.is_abnormal),
      },
      {
        id: 'sleep', label: '睡眠', unit: 'h', icon: '🌙',
        value: v(tm && tm.sleep, 'duration_h'),
        abnormal: !!(tm && tm.sleep && tm.sleep.is_abnormal),
      },
      {
        id: 'spo2', label: '血氧', unit: '%', icon: '🫁',
        value: v(tm && tm.spo2, 'value'),
        abnormal: !!(tm && tm.spo2 && tm.spo2.is_abnormal),
      },
    ];
    const med = (tm && tm.medication) || { checked: 0, total: 0, has_overdue: false };
    const percent = med.total > 0 ? Math.round((med.checked / med.total) * 100) : 0;
    this.setData({
      todayCells: cells,
      medCell: { checked: med.checked || 0, total: med.total || 0, has_overdue: !!med.has_overdue, percent },
    });
  },

  async loadMedicationPlan(profileId) {
    try {
      const res = await get(`/api/health-profile-v3/${profileId}/medication-plan`, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const items = Array.isArray(data.items) ? data.items : [];
      this.setData({ medications: items });
    } catch (_) {
      this.setData({ medications: [] });
    }
  },

  async loadHeroSummary(profileId) {
    try {
      const res = await get(`/api/prd469/summary/${profileId}`, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const list = Array.isArray(data.hero_metrics) ? data.hero_metrics : [];
      if (list.length > 0) this.setData({ heroMetrics: list });
    } catch (_) {}
  },

  async loadHealthEvents(profileId) {
    try {
      const res = await get(`/api/health-profile-v3/${profileId}/events`, {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const items = Array.isArray(data.items) ? data.items : [];
      this.setData({ events: items });
    } catch (_) {
      this.setData({ events: [] });
    }
  },

  async loadLinkStatus(memberId) {
    try {
      const res = await get('/api/family/management', {}, { showLoading: false, suppressErrorToast: true });
      const data = (res && (res.data || res)) || {};
      const items = Array.isArray(data.items) ? data.items : [];
      const linked = items.some((it) => it.managed_member_id === memberId && it.status === 'active');
      this.setData({ isLinked: linked });
    } catch (_) {
      this.setData({ isLinked: false });
    }
  },

  /* ============ Tab 切换 ============ */
  onTabClick(e) {
    const id = e.currentTarget.dataset.id;
    if (id && id !== this.data.activeTab) {
      this.setData({ activeTab: id });
    }
  },

  /* ============ 今日数据点击 ============ */
  onMetricCardTap(e) {
    const id = e.currentTarget.dataset.id;
    const pid = this.data.profile && this.data.profile.id;
    if (id && pid) {
      wx.navigateTo({
        url: `/pages/health-metric/index?type=${id}&profileId=${pid}`,
        fail() { wx.showToast({ title: '功能开发中', icon: 'none' }); },
      });
    }
  },

  /* ============ 健康信息：标签 ============ */
  togglePreset(e) {
    const { field, name } = e.currentTarget.dataset;
    const profile = this.data.profile || {};
    const list = (profile[field] || []).slice();
    const idx = list.findIndex((it) =>
      (typeof it === 'string' && it === name) || (it && it.value === name)
    );
    if (idx >= 0) list.splice(idx, 1); else list.push(name);
    profile[field] = list;
    this.setData({ profile });
  },

  toggleOther(e) {
    const key = e.currentTarget.dataset.key;
    const map = { chronic: 'showChronicOther', allergy: 'showAllergyOther', genetic: 'showGeneticOther' };
    const f = map[key];
    if (f) this.setData({ [f]: !this.data[f] });
  },

  onOtherInput(e) {
    const key = e.currentTarget.dataset.key;
    const map = { chronic: 'chronicOtherInput', allergy: 'allergyOtherInput', genetic: 'geneticOtherInput' };
    const f = map[key];
    if (f) this.setData({ [f]: e.detail.value });
  },

  confirmOther(e) {
    const key = e.currentTarget.dataset.key;
    const inputMap = { chronic: 'chronicOtherInput', allergy: 'allergyOtherInput', genetic: 'geneticOtherInput' };
    const listMap  = { chronic: 'chronicCustomItems', allergy: 'allergyCustomItems', genetic: 'geneticCustomItems' };
    const fieldMap = { chronic: 'chronic_diseases', allergy: 'allergies', genetic: 'genetic_diseases' };
    const showMap  = { chronic: 'showChronicOther', allergy: 'showAllergyOther', genetic: 'showGeneticOther' };
    const value = (this.data[inputMap[key]] || '').trim();
    if (!value) { wx.showToast({ title: '请输入内容', icon: 'none' }); return; }
    const customs = (this.data[listMap[key]] || []).slice();
    if (customs.some((x) => x.value === value)) {
      wx.showToast({ title: '已存在', icon: 'none' }); return;
    }
    const item = { type: 'custom', value };
    customs.push(item);
    const profile = this.data.profile || {};
    const arr = (profile[fieldMap[key]] || []).slice();
    arr.push(item);
    profile[fieldMap[key]] = arr;
    this.setData({
      [listMap[key]]: customs,
      profile,
      [inputMap[key]]: '',
      [showMap[key]]: false,
    });
  },

  removeCustom(e) {
    const { key, value } = e.currentTarget.dataset;
    const listMap = { chronic: 'chronicCustomItems', allergy: 'allergyCustomItems', genetic: 'geneticCustomItems' };
    const fieldMap = { chronic: 'chronic_diseases', allergy: 'allergies', genetic: 'genetic_diseases' };
    const customs = (this.data[listMap[key]] || []).filter((x) => x.value !== value);
    const profile = this.data.profile || {};
    profile[fieldMap[key]] = (profile[fieldMap[key]] || []).filter((it) =>
      !(it && it.value === value && it.type === 'custom')
    );
    this.setData({ [listMap[key]]: customs, profile });
  },

  setHabit(e) {
    const { field, value } = e.currentTarget.dataset;
    const profile = this.data.profile || {};
    profile[field] = value;
    this.setData({ profile });
  },

  async saveProfile() {
    const p = this.data.profile;
    if (!p) return;
    this.setData({ saving: true });
    try {
      await put(`/api/health/profile/member/${this.data.selectedMemberId}`, {
        name: p.name,
        gender: p.gender,
        birthday: p.birthday,
        height: p.height ? Number(p.height) : null,
        weight: p.weight ? Number(p.weight) : null,
        blood_type: p.blood_type,
        chronic_diseases: p.chronic_diseases || [],
        allergies: p.allergies || [],
        genetic_diseases: p.genetic_diseases || [],
        smoking: p.smoking || null,
        drinking: p.drinking || null,
      });
      wx.showToast({ title: '已保存', icon: 'success' });
      this.loadProfile(this.data.selectedMemberId);
    } catch (_) {
      wx.showToast({ title: '保存失败', icon: 'none' });
    } finally {
      this.setData({ saving: false });
    }
  },

  /* ============ 用药计划 ============ */
  addMedication() {
    wx.navigateTo({
      url: '/pages/medication-add/index?profileId=' + (this.data.profile && this.data.profile.id || ''),
      fail() { wx.showToast({ title: '请前往 APP/H5 添加', icon: 'none' }); },
    });
  },

  /* ============ 成员添加 ============ */
  onAddMemberTap() {
    wx.navigateTo({
      url: '/pages/family-member-add/index',
      fail() { wx.showToast({ title: '请前往 H5 添加', icon: 'none' }); },
    });
  },

  /* ============ 共管 ============ */
  async onInviteLink() {
    const id = this.data.selectedMemberId;
    if (!id) return;
    try {
      const res = await post('/api/family/invite-link', { member_id: id }, { showLoading: true });
      const code = (res && (res.data && res.data.code || res.code)) || '';
      wx.setClipboardData({
        data: code ? `健康档案守护邀请码：${code}` : '邀请已发送',
        success: () => wx.showToast({ title: '邀请码已复制', icon: 'success' }),
      });
    } catch (_) {
      wx.showToast({ title: '邀请失败', icon: 'none' });
    }
  },

  async onUnlink() {
    const id = this.data.selectedMemberId;
    if (!id) return;
    const that = this;
    wx.showModal({
      title: '解除关联',
      content: '解除后对方将无法继续查看此档案，是否继续？',
      async success(r) {
        if (!r.confirm) return;
        try {
          await del('/api/family/management/' + id);
          wx.showToast({ title: '已解除', icon: 'success' });
          that.setData({ isLinked: false });
        } catch (_) {
          wx.showToast({ title: '操作失败', icon: 'none' });
        }
      },
    });
  },

  goBindList() {
    wx.navigateTo({ url: '/pages/family-bindlist/index', fail() {} });
  },

  /* ============ Hero 编辑 ============ */
  onEditHero() {
    const p = this.data.profile || {};
    const draft = {
      name: p.name || '',
      gender: p.gender || '',
      birthday: p.birthday || '',
      height: p.height || '',
      weight: p.weight || '',
      blood_type: p.blood_type || '',
    };
    const idx = BLOOD_TYPES.indexOf(draft.blood_type);
    this.setData({
      showHeroEdit: true,
      heroEditDraft: draft,
      bloodTypeIndex: idx >= 0 ? idx : -1,
    });
  },

  closeHeroEdit() {
    this.setData({ showHeroEdit: false, heroEditDraft: null });
  },

  onHeroInput(e) {
    const f = e.currentTarget.dataset.field;
    const d = this.data.heroEditDraft || {};
    d[f] = e.detail.value;
    this.setData({ heroEditDraft: d });
  },

  onHeroPick(e) {
    const { field, value } = e.currentTarget.dataset;
    const d = this.data.heroEditDraft || {};
    d[field] = value;
    this.setData({ heroEditDraft: d });
  },

  onHeroDate(e) {
    const d = this.data.heroEditDraft || {};
    d.birthday = e.detail.value;
    this.setData({ heroEditDraft: d });
  },

  onHeroBloodType(e) {
    const idx = Number(e.detail.value);
    const d = this.data.heroEditDraft || {};
    d.blood_type = BLOOD_TYPES[idx] || '';
    this.setData({ heroEditDraft: d, bloodTypeIndex: idx });
  },

  async saveHero() {
    const d = this.data.heroEditDraft;
    if (!d) return;
    // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29 §6] Hero 编辑页三项必填
    const nm = String(d.name || '').trim();
    if (!nm || nm === '本人' || nm.length > 20) {
      wx.showToast({ title: '请填写姓名', icon: 'none' });
      return;
    }
    if (!d.gender) {
      wx.showToast({ title: '请选择性别', icon: 'none' });
      return;
    }
    if (!d.birthday) {
      wx.showToast({ title: '请选择出生日期', icon: 'none' });
      return;
    }
    this.setData({ heroSaving: true });
    try {
      await put(`/api/health/profile/member/${this.data.selectedMemberId}`, {
        name: d.name,
        gender: d.gender,
        birthday: d.birthday,
        height: d.height ? Number(d.height) : null,
        weight: d.weight ? Number(d.weight) : null,
        blood_type: d.blood_type,
      });
      wx.showToast({ title: '已保存', icon: 'success' });
      this.closeHeroEdit();
      this.loadProfile(this.data.selectedMemberId);
    } catch (_) {
      wx.showToast({ title: '保存失败', icon: 'none' });
    } finally {
      this.setData({ heroSaving: false });
    }
  },
});
