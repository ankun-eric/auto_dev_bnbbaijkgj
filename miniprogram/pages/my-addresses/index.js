const { get, post, put, del } = require('../../utils/request');

Page({
  data: {
    addresses: [],
    loading: false,
    selectMode: false,
    showForm: false,
    editId: '',
    form: {
      name: '',
      phone: '',
      province: '',
      city: '',
      district: '',
      detail: '',
      is_default: false
    },
    regionValue: []
  },

  onLoad(options) {
    if (options.select === '1') {
      this.setData({ selectMode: true });
    }
    this.loadAddresses();
  },

  async loadAddresses() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/addresses', {}, { showLoading: false });
      this.setData({ addresses: res.items || res || [] });
    } catch (e) {
      console.log('loadAddresses error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  selectAddress(e) {
    if (!this.data.selectMode) return;
    const item = e.currentTarget.dataset.item;
    const eventChannel = this.getOpenerEventChannel();
    if (eventChannel) {
      eventChannel.emit('selectAddress', item);
    }
    wx.navigateBack();
  },

  showAddForm() {
    this.setData({
      showForm: true,
      editId: '',
      form: { name: '', phone: '', province: '', city: '', district: '', detail: '', is_default: false },
      regionValue: []
    });
  },

  showEditForm(e) {
    const item = e.currentTarget.dataset.item;
    this.setData({
      showForm: true,
      editId: item.id,
      form: {
        name: item.name,
        phone: item.phone,
        province: item.province || '',
        city: item.city || '',
        district: item.district || '',
        detail: item.detail || '',
        is_default: item.is_default || false
      },
      regionValue: [item.province || '', item.city || '', item.district || '']
    });
  },

  hideForm() {
    this.setData({ showForm: false });
  },

  onNameInput(e) {
    this.setData({ 'form.name': e.detail.value });
  },

  onPhoneInput(e) {
    this.setData({ 'form.phone': e.detail.value });
  },

  onRegionChange(e) {
    const val = e.detail.value;
    this.setData({
      regionValue: val,
      'form.province': val[0] || '',
      'form.city': val[1] || '',
      'form.district': val[2] || ''
    });
  },

  onDetailInput(e) {
    this.setData({ 'form.detail': e.detail.value });
  },

  toggleDefault() {
    this.setData({ 'form.is_default': !this.data.form.is_default });
  },

  async saveAddress() {
    const f = this.data.form;
    if (!f.name) { wx.showToast({ title: '请输入姓名', icon: 'none' }); return; }
    if (!f.phone) { wx.showToast({ title: '请输入手机号', icon: 'none' }); return; }
    if (!f.province) { wx.showToast({ title: '请选择地区', icon: 'none' }); return; }
    if (!f.detail) { wx.showToast({ title: '请输入详细地址', icon: 'none' }); return; }

    try {
      if (this.data.editId) {
        await put(`/api/addresses/${this.data.editId}`, f);
      } else {
        await post('/api/addresses', f);
      }
      wx.showToast({ title: '保存成功', icon: 'success' });
      this.setData({ showForm: false });
      this.loadAddresses();
    } catch (e) {
      console.log('saveAddress error', e);
    }
  },

  deleteAddress(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '删除地址',
      content: '确定要删除此地址吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/addresses/${id}`);
          wx.showToast({ title: '已删除', icon: 'success' });
          this.loadAddresses();
        } catch (e) {
          console.log('deleteAddress error', e);
        }
      }
    });
  }
});
