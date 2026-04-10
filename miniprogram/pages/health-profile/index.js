const { get, post } = require('../../utils/request');

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
      allergies: [],
      diseases: [],
      medications: []
    },
    bloodTypes: ['A型', 'B型', 'AB型', 'O型', '未知'],
    bloodTypeIndex: -1
  },

  onLoad() {
    this.loadFamilyTabs();
  },

  async loadFamilyTabs() {
    try {
      const res = await get('/api/family/members', {}, { showLoading: false, suppressErrorToast: true });
      const items = res && res.items ? res.items : [];
      const tabs = items.map(m => ({
        id: m.id,
        name: m.relation_type_name || m.nickname || '本人',
        color: getRelationColor(m.relation_type_name || ''),
        is_self: m.is_self
      }));
      if (!tabs.some(t => t.is_self)) {
        tabs.unshift({ id: 0, name: '本人', color: '#52c41a', is_self: true });
      }
      this.setData({ familyTabs: tabs, activeTabIndex: 0 });
      this.loadProfile();
    } catch (e) {
      this.setData({
        familyTabs: [{ id: 0, name: '本人', color: '#52c41a', is_self: true }],
        activeTabIndex: 0
      });
      this.loadProfile();
    }
  },

  onTabSelect(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({ activeTabIndex: index });
    this.loadProfile();
  },

  onAddMemberTap() {
    wx.navigateTo({ url: '/pages/family/index' });
  },

  async loadProfile() {
    try {
      const saved = wx.getStorageSync('healthProfile');
      if (saved) {
        this.setData({ profile: saved });
        const idx = this.data.bloodTypes.indexOf(saved.bloodType);
        if (idx >= 0) this.setData({ bloodTypeIndex: idx });
      }
    } catch (e) {
      console.log('loadProfile error', e);
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

  addAllergy() {
    wx.showModal({
      title: '添加过敏信息',
      editable: true,
      placeholderText: '如：青霉素、花粉、海鲜...',
      success: (res) => {
        if (res.confirm && res.content) {
          const allergies = [...this.data.profile.allergies, res.content.trim()];
          this.setData({ 'profile.allergies': allergies });
        }
      }
    });
  },

  removeAllergy(e) {
    const index = e.currentTarget.dataset.index;
    const allergies = this.data.profile.allergies.filter((_, i) => i !== index);
    this.setData({ 'profile.allergies': allergies });
  },

  addDisease() {
    wx.showModal({
      title: '添加既往病史',
      editable: true,
      placeholderText: '如：高血压、糖尿病...',
      success: (res) => {
        if (res.confirm && res.content) {
          const diseases = [...this.data.profile.diseases, res.content.trim()];
          this.setData({ 'profile.diseases': diseases });
        }
      }
    });
  },

  removeDisease(e) {
    const index = e.currentTarget.dataset.index;
    const diseases = this.data.profile.diseases.filter((_, i) => i !== index);
    this.setData({ 'profile.diseases': diseases });
  },

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

  async saveProfile() {
    try {
      wx.setStorageSync('healthProfile', this.data.profile);
      // await post('/api/health/profile', this.data.profile);
      wx.showToast({ title: '保存成功', icon: 'success' });
    } catch (e) {
      wx.showToast({ title: '保存失败', icon: 'none' });
    }
  }
});
