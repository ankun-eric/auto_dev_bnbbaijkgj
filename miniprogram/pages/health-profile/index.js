const { get, post } = require('../../utils/request');

Page({
  data: {
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
    this.loadProfile();
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
