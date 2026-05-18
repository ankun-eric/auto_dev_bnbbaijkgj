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
  },

  onLoad() {
    this.loadPresets();
    this.loadMembers();
    this.loadManagedByInfo();
  },

  onShow() {
    if (this.data.selectedMemberId && this.data.profile && this.data.profile.id) {
      this.loadMedicationPlan(this.data.profile.id);
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
