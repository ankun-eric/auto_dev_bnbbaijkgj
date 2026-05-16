const { get, put, del } = require('../../utils/request');

const RELATION_COLORS = {
  '本人': '#52c41a',
  '爸爸': '#1890ff', '妈妈': '#1890ff',
  '儿子': '#eb2f96', '女儿': '#eb2f96',
  '爷爷': '#fa8c16', '奶奶': '#fa8c16',
  '外公': '#fa8c16', '外婆': '#fa8c16'
};
function getRelationColor(name) {
  return RELATION_COLORS[name] || '#8c8c8c';
}

function isPresetSelected(items, name) {
  return (items || []).some(i => typeof i === 'string' && i === name);
}
function getCustomItems(items) {
  return (items || []).filter(i => typeof i === 'object' && i.type === 'custom');
}

Page({
  data: {
    familyTabs: [],
    activeTabIndex: 0,
    profile: {
      name: '',
      gender: '',
      birthday: '',
      height: '',
      weight: '',
      bloodType: '',
      chronic_diseases: [],
      allergies: [],
      genetic_diseases: [],
      medications: []
    },
    bloodTypes: ['A型', 'B型', 'AB型', 'O型', '未知'],
    bloodTypeIndex: -1,

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

    managementList: [],
    isManagedByOthers: false,
    managedByList: [],
    currentMemberLinked: false,
    currentMemberManagementId: null
  },

  onLoad() {
    this.loadFamilyTabs();
    this.loadPresets();
    this.loadManagedByInfo();
  },

  onShow() {
    this.loadProfile();
  },

  async loadPresets() {
    try {
      const [chronicRes, allergyRes, geneticRes] = await Promise.all([
        get('/api/disease-presets', { category: 'chronic' }, { showLoading: false, suppressErrorToast: true }),
        get('/api/disease-presets', { category: 'allergy' }, { showLoading: false, suppressErrorToast: true }),
        get('/api/disease-presets', { category: 'genetic' }, { showLoading: false, suppressErrorToast: true })
      ]);
      this.setData({
        chronicPresets: (chronicRes && chronicRes.items) || [],
        allergyPresets: (allergyRes && allergyRes.items) || [],
        geneticPresets: (geneticRes && geneticRes.items) || []
      });
    } catch (e) {
      console.log('loadPresets error', e);
    }
  },

  async loadFamilyTabs() {
    try {
      const [membersRes, mgmtRes] = await Promise.all([
        get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true }),
        get('/api/family/management', {}, { showLoading: false, suppressErrorToast: true }).catch(() => ({ items: [] }))
      ]);
      const items = membersRes && membersRes.items ? membersRes.items : [];
      const mgmtItems = mgmtRes && mgmtRes.items ? mgmtRes.items : [];
      const mgmtMap = {};
      mgmtItems.forEach(m => { mgmtMap[m.managed_member_id] = m; });

      const tabs = items.map(m => ({
        id: m.id,
        name: m.relation_type_name || m.nickname || '本人',
        color: getRelationColor(m.relation_type_name || ''),
        is_self: m.is_self,
        linked: !!mgmtMap[m.id],
        managementId: mgmtMap[m.id] ? mgmtMap[m.id].id : null
      }));
      if (!tabs.some(t => t.is_self)) {
        tabs.unshift({ id: 0, name: '本人', color: '#52c41a', is_self: true, linked: false, managementId: null });
      }
      this.setData({
        familyTabs: tabs,
        activeTabIndex: 0,
        managementList: mgmtItems
      });
      this.updateCurrentMemberLinkStatus(0);
      this.loadProfile();
    } catch (e) {
      this.setData({
        familyTabs: [{ id: 0, name: '本人', color: '#52c41a', is_self: true, linked: false, managementId: null }],
        activeTabIndex: 0
      });
      this.loadProfile();
    }
  },

  async loadManagedByInfo() {
    try {
      const res = await get('/api/family/managed-by', {}, { showLoading: false, suppressErrorToast: true });
      const items = res && res.items ? res.items : [];
      this.setData({
        isManagedByOthers: items.length > 0,
        managedByList: items
      });
    } catch (e) {
      this.setData({ isManagedByOthers: false, managedByList: [] });
    }
  },

  updateCurrentMemberLinkStatus(index) {
    const tab = this.data.familyTabs[index];
    if (!tab) return;
    this.setData({
      currentMemberLinked: !!tab.linked,
      currentMemberManagementId: tab.managementId || null
    });
  },

  onTabSelect(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ activeTabIndex: index });
    this.updateCurrentMemberLinkStatus(index);
    this.loadProfile();
  },

  onAddMemberTap() {
    wx.navigateTo({ url: '/pages/family/index' });
  },

  async loadProfile() {
    const tab = this.data.familyTabs[this.data.activeTabIndex];
    if (!tab) return;
    try {
      let profile;
      if (tab.is_self) {
        profile = await get('/api/health/profile', {}, { showLoading: false, suppressErrorToast: true });
      } else {
        profile = await get(`/api/health/profile/member/${tab.id}`, {}, { showLoading: false, suppressErrorToast: true });
      }
      if (profile) {
        const p = {
          name: profile.name || '',
          gender: profile.gender || '',
          birthday: profile.birthday || '',
          height: profile.height || '',
          weight: profile.weight || '',
          bloodType: profile.blood_type || '',
          chronic_diseases: profile.chronic_diseases || [],
          allergies: profile.allergies || [],
          genetic_diseases: profile.genetic_diseases || [],
          medications: []
        };
        const idx = this.data.bloodTypes.indexOf(p.bloodType);
        this.setData({
          profile: p,
          bloodTypeIndex: idx >= 0 ? idx : -1,
          chronicCustomItems: getCustomItems(p.chronic_diseases),
          allergyCustomItems: getCustomItems(p.allergies),
          geneticCustomItems: getCustomItems(p.genetic_diseases)
        });
      }
    } catch (e) {
      this.setData({
        profile: {
          name: '', gender: '', birthday: '', height: '', weight: '', bloodType: '',
          chronic_diseases: [], allergies: [], genetic_diseases: [], medications: []
        },
        bloodTypeIndex: -1,
        chronicCustomItems: [],
        allergyCustomItems: [],
        geneticCustomItems: []
      });
    }
  },

  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [`profile.${field}`]: e.detail.value });
  },

  setGender(e) {
    this.setData({ 'profile.gender': e.currentTarget.dataset.gender });
  },

  onDateChange(e) {
    this.setData({ 'profile.birthday': e.detail.value });
  },

  onBloodTypeChange(e) {
    const index = e.detail.value;
    this.setData({
      bloodTypeIndex: index,
      'profile.bloodType': this.data.bloodTypes[index]
    });
  },

  // ── Chronic disease tag handlers ──
  toggleChronicPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...(this.data.profile.chronic_diseases || [])];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) {
      items.splice(idx, 1);
    } else {
      items.push(name);
    }
    this.setData({ 'profile.chronic_diseases': items });
  },

  toggleChronicOther() {
    this.setData({ showChronicOther: !this.data.showChronicOther });
  },

  onChronicOtherInput(e) {
    this.setData({ chronicOtherInput: e.detail.value });
  },

  confirmChronicOther() {
    const val = (this.data.chronicOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) {
      wx.showToast({ title: '最多100个字符', icon: 'none' });
      return;
    }
    const presetNames = this.data.chronicPresets.map(p => p.name);
    if (presetNames.includes(val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' });
      return;
    }
    const items = [...(this.data.profile.chronic_diseases || [])];
    const exists = items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val);
    if (exists) {
      wx.showToast({ title: '已添加该项', icon: 'none' });
      return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({
      'profile.chronic_diseases': items,
      chronicCustomItems: getCustomItems(items),
      chronicOtherInput: ''
    });
  },

  removeChronicCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = (this.data.profile.chronic_diseases || []).filter(
      i => !(typeof i === 'object' && i.type === 'custom' && i.value === val)
    );
    this.setData({
      'profile.chronic_diseases': items,
      chronicCustomItems: getCustomItems(items)
    });
  },

  // ── Allergy tag handlers ──
  toggleAllergyPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...(this.data.profile.allergies || [])];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) {
      items.splice(idx, 1);
    } else {
      items.push(name);
    }
    this.setData({ 'profile.allergies': items });
  },

  toggleAllergyOther() {
    this.setData({ showAllergyOther: !this.data.showAllergyOther });
  },

  onAllergyOtherInput(e) {
    this.setData({ allergyOtherInput: e.detail.value });
  },

  confirmAllergyOther() {
    const val = (this.data.allergyOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) {
      wx.showToast({ title: '最多100个字符', icon: 'none' });
      return;
    }
    const presetNames = this.data.allergyPresets.map(p => p.name);
    if (presetNames.includes(val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' });
      return;
    }
    const items = [...(this.data.profile.allergies || [])];
    const exists = items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val);
    if (exists) {
      wx.showToast({ title: '已添加该项', icon: 'none' });
      return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({
      'profile.allergies': items,
      allergyCustomItems: getCustomItems(items),
      allergyOtherInput: ''
    });
  },

  removeAllergyCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = (this.data.profile.allergies || []).filter(
      i => !(typeof i === 'object' && i.type === 'custom' && i.value === val)
    );
    this.setData({
      'profile.allergies': items,
      allergyCustomItems: getCustomItems(items)
    });
  },

  // ── Genetic disease tag handlers ──
  toggleGeneticPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...(this.data.profile.genetic_diseases || [])];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) {
      items.splice(idx, 1);
    } else {
      items.push(name);
    }
    this.setData({ 'profile.genetic_diseases': items });
  },

  toggleGeneticOther() {
    this.setData({ showGeneticOther: !this.data.showGeneticOther });
  },

  onGeneticOtherInput(e) {
    this.setData({ geneticOtherInput: e.detail.value });
  },

  confirmGeneticOther() {
    const val = (this.data.geneticOtherInput || '').trim();
    if (!val) return;
    if (val.length > 100) {
      wx.showToast({ title: '最多100个字符', icon: 'none' });
      return;
    }
    const presetNames = this.data.geneticPresets.map(p => p.name);
    if (presetNames.includes(val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' });
      return;
    }
    const items = [...(this.data.profile.genetic_diseases || [])];
    const exists = items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val);
    if (exists) {
      wx.showToast({ title: '已添加该项', icon: 'none' });
      return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({
      'profile.genetic_diseases': items,
      geneticCustomItems: getCustomItems(items),
      geneticOtherInput: ''
    });
  },

  removeGeneticCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = (this.data.profile.genetic_diseases || []).filter(
      i => !(typeof i === 'object' && i.type === 'custom' && i.value === val)
    );
    this.setData({
      'profile.genetic_diseases': items,
      geneticCustomItems: getCustomItems(items)
    });
  },

  // ── Medication handlers (kept as-is) ──
  addMedication() {
    wx.showModal({
      title: '添加用药记录',
      editable: true,
      placeholderText: '药品名称，如：降压药',
      success: (res) => {
        if (res.confirm && res.content) {
          const medications = [...this.data.profile.medications, { name: res.content.trim(), dosage: '遵医嘱' }];
          this.setData({ 'profile.medications': medications });
        }
      }
    });
  },

  removeMedication(e) {
    const index = e.currentTarget.dataset.index;
    const medications = this.data.profile.medications.filter((_, i) => i !== index);
    this.setData({ 'profile.medications': medications });
  },

  // ── WXS helper proxies (called from WXML via event data) ──
  _isPresetSelected(items, name) {
    return isPresetSelected(items, name);
  },

  onInviteLink() {
    const tab = this.data.familyTabs[this.data.activeTabIndex];
    if (!tab || tab.is_self) return;
    wx.navigateTo({ url: `/pages/family-invite/index?member_id=${tab.id}` });
  },

  onUnlink() {
    const tab = this.data.familyTabs[this.data.activeTabIndex];
    if (!tab || !tab.managementId) return;
    wx.showModal({
      title: '解除关联',
      content: `确定要解除与「${tab.name}」的关联吗？解除后将无法查看对方健康档案。`,
      confirmColor: '#ff4d4f',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/family/management/${tab.managementId}`);
          wx.showToast({ title: '已解除关联', icon: 'success' });
          this.loadFamilyTabs();
        } catch (e) {
          wx.showToast({ title: '操作失败', icon: 'none' });
        }
      }
    });
  },

  goBindList() {
    wx.navigateTo({ url: '/pages/family-bindlist/index' });
  },

  async saveProfile() {
    const tab = this.data.familyTabs[this.data.activeTabIndex];
    if (!tab) return;

    const p = this.data.profile;
    const payload = {
      name: p.name || undefined,
      gender: p.gender || undefined,
      birthday: p.birthday || undefined,
      height: p.height ? parseFloat(p.height) : undefined,
      weight: p.weight ? parseFloat(p.weight) : undefined,
      blood_type: p.bloodType || undefined,
      chronic_diseases: p.chronic_diseases,
      allergies: p.allergies,
      genetic_diseases: p.genetic_diseases
    };

    try {
      if (tab.is_self) {
        await put('/api/health/profile', payload);
      } else {
        await put(`/api/health/profile/member/${tab.id}`, payload);
      }
      wx.showToast({ title: '保存成功', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: '保存失败', icon: 'none' });
    }
  }
});
