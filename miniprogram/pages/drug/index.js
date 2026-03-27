const { get } = require('../../utils/request');
const { debounce } = require('../../utils/util');

Page({
  data: {
    keyword: '',
    hotKeywords: ['布洛芬', '阿莫西林', '感冒灵', '连花清瘟', '维生素C', '板蓝根', '对乙酰氨基酚', '头孢'],
    searchResults: [],
    showDetail: false,
    currentDrug: null,
    mockDrugs: [
      { id: '1', name: '布洛芬缓释胶囊', generic: '布洛芬', spec: '0.3g×20粒', otc: true, prescription: false, usage: '口服，成人每次1-2粒，每日2次', indication: '用于缓解轻至中度疼痛，如头痛、关节痛、偏头痛、牙痛、肌肉痛、神经痛、痛经等', sideEffects: '可能出现恶心、呕吐、胃痛等消化道反应', contraindication: '对本品过敏者禁用，活动性消化性溃疡禁用', precautions: '不宜长期服用，如需用药3天以上应咨询医生' },
      { id: '2', name: '阿莫西林胶囊', generic: '阿莫西林', spec: '0.5g×24粒', otc: false, prescription: true, usage: '口服，成人每次0.5g，每6-8小时1次', indication: '上呼吸道感染、下呼吸道感染、泌尿生殖道感染、皮肤软组织感染等', sideEffects: '可能出现皮疹、腹泻等过敏反应', contraindication: '对青霉素类药物过敏者禁用', precautions: '使用前需做青霉素皮试，遵医嘱用药' },
      { id: '3', name: '感冒灵颗粒', generic: '复方感冒灵', spec: '10g×10袋', otc: true, prescription: false, usage: '开水冲服，一次1袋，一日3次', indication: '感冒引起的头痛、发热、鼻塞、流涕、咽痛等', sideEffects: '偶见困倦、嗜睡', contraindication: '对本品成分过敏者禁用', precautions: '服药期间不宜驾车或高空作业' }
    ]
  },

  onSearch: function(e) {
    this.setData({ keyword: e.detail.value });
    this._debounceSearch(e.detail.value);
  },

  _debounceSearch: debounce(function(keyword) {
    this.doSearch();
  }, 300),

  doSearch() {
    const keyword = this.data.keyword.trim();
    if (!keyword) {
      this.setData({ searchResults: [] });
      return;
    }

    // Mock local search
    const results = this.data.mockDrugs.filter(d =>
      d.name.includes(keyword) || d.generic.includes(keyword)
    );
    this.setData({ searchResults: results });
  },

  clearSearch() {
    this.setData({ keyword: '', searchResults: [] });
  },

  searchKeyword(e) {
    const keyword = e.currentTarget.dataset.keyword;
    this.setData({ keyword });
    this.doSearch();
  },

  scanDrug() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['camera'],
      success: () => {
        wx.showLoading({ title: 'AI识别中...' });
        setTimeout(() => {
          wx.hideLoading();
          this.setData({
            keyword: '布洛芬',
            searchResults: [this.data.mockDrugs[0]]
          });
          wx.showToast({ title: '识别成功', icon: 'success' });
        }, 2000);
      }
    });
  },

  showDrugDetail(e) {
    const drug = e.currentTarget.dataset.drug;
    this.setData({ showDetail: true, currentDrug: drug });
  },

  closeDetail() {
    this.setData({ showDetail: false });
  },

  askAboutDrug() {
    const name = this.data.currentDrug.name;
    this.setData({ showDetail: false });
    wx.navigateTo({
      url: `/pages/chat/index?type=general&question=${encodeURIComponent('我想了解药物' + name + '的详细信息')}`
    });
  }
});
