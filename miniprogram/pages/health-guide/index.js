const { get, put, post } = require('../../utils/request');

function getCustomItems(items) {
  return (items || []).filter(i => typeof i === 'object' && i.type === 'custom');
}

Page({
  data: {
    currentStep: 0,
    steps: ['基本信息', '慢性病史', '过敏史', '遗传病史'],

    // Step 1: basic info
    name: '',
    gender: '',
    birthday: '',
    height: '',
    weight: '',
    bloodType: '',
    bloodTypes: ['A型', 'B型', 'AB型', 'O型', '未知'],
    bloodTypeIndex: -1,

    // Step 2: chronic diseases
    chronicPresets: [],
    chronic_diseases: [],
    chronicCustomItems: [],
    showChronicOther: false,
    chronicOtherInput: '',

    // Step 3: allergies
    allergyPresets: [],
    allergies: [],
    allergyCustomItems: [],
    showAllergyOther: false,
    allergyOtherInput: '',

    // Step 4: genetic diseases
    geneticPresets: [],
    genetic_diseases: [],
    geneticCustomItems: [],
    showGeneticOther: false,
    geneticOtherInput: ''
  },

  onLoad() {
    this.loadPresets();
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

  // ── Step 1: basic info ──
  onInput(e) {
    const field = e.currentTarget.dataset.field;
    this.setData({ [field]: e.detail.value });
  },

  setGender(e) {
    this.setData({ gender: e.currentTarget.dataset.gender });
  },

  onDateChange(e) {
    this.setData({ birthday: e.detail.value });
  },

  onBloodTypeChange(e) {
    const index = e.detail.value;
    this.setData({
      bloodTypeIndex: index,
      bloodType: this.data.bloodTypes[index]
    });
  },

  // ── Step 2: chronic diseases ──
  toggleChronicPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.chronic_diseases];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ chronic_diseases: items });
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
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.chronicPresets.some(p => p.name === val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return;
    }
    const items = [...this.data.chronic_diseases];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) {
      wx.showToast({ title: '已添加该项', icon: 'none' }); return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({ chronic_diseases: items, chronicCustomItems: getCustomItems(items), chronicOtherInput: '' });
  },

  removeChronicCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.chronic_diseases.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ chronic_diseases: items, chronicCustomItems: getCustomItems(items) });
  },

  // ── Step 3: allergies ──
  toggleAllergyPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.allergies];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ allergies: items });
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
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.allergyPresets.some(p => p.name === val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return;
    }
    const items = [...this.data.allergies];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) {
      wx.showToast({ title: '已添加该项', icon: 'none' }); return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({ allergies: items, allergyCustomItems: getCustomItems(items), allergyOtherInput: '' });
  },

  removeAllergyCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.allergies.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ allergies: items, allergyCustomItems: getCustomItems(items) });
  },

  // ── Step 4: genetic diseases ──
  toggleGeneticPreset(e) {
    const name = e.currentTarget.dataset.name;
    let items = [...this.data.genetic_diseases];
    const idx = items.findIndex(i => typeof i === 'string' && i === name);
    if (idx >= 0) { items.splice(idx, 1); } else { items.push(name); }
    this.setData({ genetic_diseases: items });
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
    if (val.length > 100) { wx.showToast({ title: '最多100个字符', icon: 'none' }); return; }
    if (this.data.geneticPresets.some(p => p.name === val)) {
      wx.showToast({ title: '与预设标签重复，请直接选择', icon: 'none' }); return;
    }
    const items = [...this.data.genetic_diseases];
    if (items.some(i => typeof i === 'object' && i.type === 'custom' && i.value === val)) {
      wx.showToast({ title: '已添加该项', icon: 'none' }); return;
    }
    items.push({ type: 'custom', value: val });
    this.setData({ genetic_diseases: items, geneticCustomItems: getCustomItems(items), geneticOtherInput: '' });
  },

  removeGeneticCustom(e) {
    const val = e.currentTarget.dataset.value;
    const items = this.data.genetic_diseases.filter(i => !(typeof i === 'object' && i.type === 'custom' && i.value === val));
    this.setData({ genetic_diseases: items, geneticCustomItems: getCustomItems(items) });
  },

  // ── Navigation ──
  prevStep() {
    if (this.data.currentStep > 0) {
      this.setData({ currentStep: this.data.currentStep - 1 });
    }
  },

  nextStep() {
    const { currentStep } = this.data;
    if (currentStep === 0) {
      if (!this.data.name) {
        wx.showToast({ title: '请输入姓名', icon: 'none' }); return;
      }
      if (!this.data.gender) {
        wx.showToast({ title: '请选择性别', icon: 'none' }); return;
      }
    }
    if (currentStep < 3) {
      this.setData({ currentStep: currentStep + 1 });
    }
  },

  async finishGuide() {
    const payload = {
      name: this.data.name || undefined,
      gender: this.data.gender || undefined,
      birthday: this.data.birthday || undefined,
      height: this.data.height ? parseFloat(this.data.height) : undefined,
      weight: this.data.weight ? parseFloat(this.data.weight) : undefined,
      blood_type: this.data.bloodType || undefined,
      chronic_diseases: this.data.chronic_diseases,
      allergies: this.data.allergies,
      genetic_diseases: this.data.genetic_diseases
    };

    try {
      await put('/api/health/profile', payload);
      await post('/api/health/guide-status', { action: 'complete' }, { showLoading: false, suppressErrorToast: true });
      wx.showToast({ title: '档案创建成功', icon: 'success' });
      setTimeout(() => {
        wx.switchTab({ url: '/pages/home/index' });
      }, 1500);
    } catch (e) {
      wx.showToast({ title: '保存失败，请重试', icon: 'none' });
    }
  },

  skipGuide() {
    post('/api/health/guide-status', { action: 'skip' }, { showLoading: false, suppressErrorToast: true }).catch(() => {});
    wx.switchTab({ url: '/pages/home/index' });
  }
});
