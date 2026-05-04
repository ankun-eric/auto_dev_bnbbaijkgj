// [2026-05-05 用户地址改造 PRD v1.0] 小程序 my-addresses v2 改造
const { get, post, put, del, patch } = require('../../utils/request');

const PRESET_TAGS = ['家', '公司'];
const ADDR_LIMIT = 10;
const DETAIL_MAX = 80;

Page({
  data: {
    addresses: [],
    loading: false,
    selectMode: false,
    showForm: false,
    showRegionPicker: false,
    editId: '',
    form: {
      consignee_name: '',
      consignee_phone: '',
      province: '',
      province_code: '',
      city: '',
      city_code: '',
      district: '',
      district_code: '',
      detail: '',
      tag: '',
      is_default: false,
      longitude: null,
      latitude: null,
    },
    regions: null,
    pickerColumns: [[], [], []],     // [provinces[], cities[], districts[]]
    pickerValue: [0, 0, 0],
    addrLimit: ADDR_LIMIT,
    detailMax: DETAIL_MAX,
    presetTags: PRESET_TAGS,
    customTagMode: false,
    customTagValue: '',
    canAdd: true,
  },

  onLoad(options) {
    if (options.select === '1') {
      this.setData({ selectMode: true });
    }
    this._loadRegions();
    this.loadAddresses();
  },

  async _loadRegions() {
    try {
      const fs = wx.getFileSystemManager();
      const text = fs.readFileSync('/data/regions.json', 'utf-8');
      const data = JSON.parse(text);
      this.setData({
        regions: data,
        pickerColumns: [
          data.provinces.map(p => p.name),
          data.provinces[0]?.cities?.map(c => c.name) || [],
          data.provinces[0]?.cities?.[0]?.districts?.map(d => d.name) || [],
        ],
      });
    } catch (e) {
      // 兜底走 API
      try {
        const data = await get('/api/v2/regions', {}, { showLoading: false });
        this.setData({
          regions: data,
          pickerColumns: [
            (data.provinces || []).map(p => p.name),
            data.provinces?.[0]?.cities?.map(c => c.name) || [],
            data.provinces?.[0]?.cities?.[0]?.districts?.map(d => d.name) || [],
          ],
        });
      } catch (err) { console.log('regions fallback failed', err); }
    }
  },

  async loadAddresses() {
    this.setData({ loading: true });
    try {
      const res = await get('/api/v2/user/addresses', {}, { showLoading: false });
      const items = res.items || res || [];
      this.setData({
        addresses: items.map(a => ({
          ...a,
          phone_mask: this._maskPhone(a.consignee_phone || a.phone || ''),
        })),
        canAdd: items.length < ADDR_LIMIT,
      });
    } catch (e) {
      console.log('loadAddresses error', e);
    } finally {
      this.setData({ loading: false });
    }
  },

  _maskPhone(p) {
    if (!p || p.length !== 11) return p;
    return p.slice(0, 3) + '****' + p.slice(7);
  },

  selectAddress(e) {
    if (!this.data.selectMode) return;
    const item = e.currentTarget.dataset.item;
    const eventChannel = this.getOpenerEventChannel();
    if (eventChannel) eventChannel.emit('selectAddress', item);
    wx.navigateBack();
  },

  showAddForm() {
    if (this.data.addresses.length >= ADDR_LIMIT) {
      wx.showToast({ title: '地址已达上限（10 条），请删除后再添加', icon: 'none' });
      return;
    }
    this.setData({
      showForm: true,
      editId: '',
      form: {
        consignee_name: '', consignee_phone: '',
        province: '', province_code: '', city: '', city_code: '',
        district: '', district_code: '', detail: '',
        tag: '', is_default: this.data.addresses.length === 0,
        longitude: null, latitude: null,
      },
      customTagMode: false, customTagValue: '',
    });
  },

  showEditForm(e) {
    const item = e.currentTarget.dataset.item;
    const tag = item.tag || '';
    const isPreset = PRESET_TAGS.includes(tag);
    this.setData({
      showForm: true,
      editId: item.id,
      form: {
        consignee_name: item.consignee_name || item.name || '',
        consignee_phone: item.consignee_phone || item.phone || '',
        province: item.province || '',
        province_code: item.province_code || '',
        city: item.city || '',
        city_code: item.city_code || '',
        district: item.district || '',
        district_code: item.district_code || '',
        detail: item.detail || item.street || '',
        tag: isPreset ? tag : '',
        is_default: !!item.is_default,
        longitude: item.longitude || null,
        latitude: item.latitude || null,
      },
      customTagMode: !isPreset && tag !== '',
      customTagValue: !isPreset ? tag : '',
    });
  },

  hideForm() { this.setData({ showForm: false }); },

  onNameInput(e) { this.setData({ 'form.consignee_name': e.detail.value }); },
  onPhoneInput(e) { this.setData({ 'form.consignee_phone': e.detail.value }); },
  onDetailInput(e) { this.setData({ 'form.detail': e.detail.value }); },

  onCustomTagInput(e) { this.setData({ customTagValue: e.detail.value }); },
  selectPresetTag(e) {
    const t = e.currentTarget.dataset.tag;
    this.setData({ 'form.tag': t, customTagMode: false, customTagValue: '' });
  },
  enterCustomTag() {
    this.setData({ customTagMode: true, 'form.tag': '' });
  },
  exitCustomTag() {
    this.setData({ customTagMode: false, customTagValue: '' });
  },

  toggleDefault() {
    this.setData({ 'form.is_default': !this.data.form.is_default });
  },

  // ─── 三级滚轮 ───
  openRegionPicker() {
    const r = this.data.regions;
    if (!r || !r.provinces) {
      wx.showToast({ title: '行政区划加载中…', icon: 'none' });
      return;
    }
    let pIdx = 0, cIdx = 0, dIdx = 0;
    if (this.data.form.province_code) {
      const i = r.provinces.findIndex(p => p.code === this.data.form.province_code);
      if (i >= 0) pIdx = i;
    }
    const cities = r.provinces[pIdx]?.cities || [];
    if (this.data.form.city_code) {
      const j = cities.findIndex(c => c.code === this.data.form.city_code);
      if (j >= 0) cIdx = j;
    }
    const dists = cities[cIdx]?.districts || [];
    if (this.data.form.district_code) {
      const k = dists.findIndex(d => d.code === this.data.form.district_code);
      if (k >= 0) dIdx = k;
    }
    this.setData({
      showRegionPicker: true,
      pickerValue: [pIdx, cIdx, dIdx],
      pickerColumns: [
        r.provinces.map(p => p.name),
        cities.map(c => c.name),
        dists.map(d => d.name),
      ],
    });
  },

  onPickerChange(e) {
    const val = e.detail.value;
    const r = this.data.regions;
    if (!r) return;
    let [p, c, d] = val;
    p = p || 0; c = c || 0; d = d || 0;
    let columns = this.data.pickerColumns;
    let needUpdate = false;
    const cities = r.provinces[p]?.cities || [];
    const dists = cities[c]?.districts || [];

    // 当省变化，重置市/县
    if (p !== this.data.pickerValue[0]) {
      c = 0; d = 0;
      columns = [
        r.provinces.map(pp => pp.name),
        cities.map(cc => cc.name),
        (cities[0]?.districts || []).map(dd => dd.name),
      ];
      needUpdate = true;
    } else if (c !== this.data.pickerValue[1]) {
      d = 0;
      columns = [
        columns[0],
        cities.map(cc => cc.name),
        dists.map(dd => dd.name),
      ];
      needUpdate = true;
    }
    this.setData({ pickerValue: [p, c, d], pickerColumns: needUpdate ? columns : this.data.pickerColumns });
  },

  cancelRegionPicker() {
    this.setData({ showRegionPicker: false });
  },

  confirmRegionPicker() {
    const [pi, ci, di] = this.data.pickerValue;
    const r = this.data.regions;
    if (!r) return;
    const p = r.provinces[pi];
    const c = p?.cities?.[ci];
    const d = c?.districts?.[di];
    if (!p || !c) {
      wx.showToast({ title: '请选择完整地区', icon: 'none' });
      return;
    }
    this.setData({
      showRegionPicker: false,
      'form.province': p.name, 'form.province_code': p.code,
      'form.city': c.name, 'form.city_code': c.code,
      'form.district': d?.name || '', 'form.district_code': d?.code || '',
    });
  },

  // ─── 微信导入地址（chooseAddress → fallback chooseLocation）───
  importFromWx() {
    const that = this;
    if (typeof wx.chooseAddress === 'function') {
      wx.chooseAddress({
        success(addr) {
          that._fillFromWxAddress(addr);
        },
        fail() { that._fallbackChooseLocation(); },
      });
    } else {
      that._fallbackChooseLocation();
    }
  },

  _fillFromWxAddress(addr) {
    // wx.chooseAddress 返回字段：provinceName/cityName/countyName/detailInfo/userName/telNumber
    this.setData({
      'form.consignee_name': addr.userName || this.data.form.consignee_name,
      'form.consignee_phone': addr.telNumber || this.data.form.consignee_phone,
      'form.province': addr.provinceName || '',
      'form.city': addr.cityName || '',
      'form.district': addr.countyName || '',
      'form.detail': addr.detailInfo || this.data.form.detail,
    });
    // 经纬度交由后端 geocoding 兜底
    wx.showToast({ title: '已导入微信地址', icon: 'success' });
  },

  _fallbackChooseLocation() {
    wx.chooseLocation({
      success: (loc) => {
        this.setData({
          'form.longitude': loc.longitude,
          'form.latitude': loc.latitude,
        });
        // 调后端 reverse-geocode 拆省市县
        post('/api/v2/regions/reverse-geocode', {
          longitude: loc.longitude, latitude: loc.latitude,
        }, { showLoading: false }).then((res) => {
          const r = res.data || res;
          if (r.province) {
            this.setData({
              'form.province': r.province,
              'form.city': r.city || r.province,
              'form.district': r.district || '',
              'form.detail': r.detail || loc.address || this.data.form.detail,
            });
          } else if (loc.address) {
            this.setData({ 'form.detail': loc.address });
          }
          wx.showToast({ title: '已导入位置，请确认地区', icon: 'success' });
        }).catch(() => {
          if (loc.address) this.setData({ 'form.detail': loc.address });
          wx.showToast({ title: '已记录经纬度，请手动选择地区', icon: 'none' });
        });
      },
      fail: () => wx.showToast({ title: '导入失败，请手动选择', icon: 'none' }),
    });
  },

  async saveAddress() {
    const f = this.data.form;
    const phoneRe = /^1[3-9]\d{9}$/;
    if (!f.consignee_name || f.consignee_name.length < 2) { wx.showToast({ title: '请输入姓名（≥2 字）', icon: 'none' }); return; }
    if (!phoneRe.test(f.consignee_phone)) { wx.showToast({ title: '请输入正确的 11 位手机号', icon: 'none' }); return; }
    if (!f.province || !f.city) { wx.showToast({ title: '请选择所在地区', icon: 'none' }); return; }
    if (!f.detail) { wx.showToast({ title: '请输入详细地址', icon: 'none' }); return; }
    if (f.detail.length > DETAIL_MAX) { wx.showToast({ title: `详细地址最多 ${DETAIL_MAX} 字`, icon: 'none' }); return; }

    let finalTag = f.tag;
    if (this.data.customTagMode && this.data.customTagValue) {
      const v = this.data.customTagValue.trim();
      if (v.length > 6) { wx.showToast({ title: '自定义标签最多 6 个汉字', icon: 'none' }); return; }
      finalTag = v;
    }

    const payload = { ...f, tag: finalTag };
    if (payload.longitude == null) delete payload.longitude;
    if (payload.latitude == null) delete payload.latitude;

    try {
      if (this.data.editId) {
        await put(`/api/v2/user/addresses/${this.data.editId}`, payload);
      } else {
        await post('/api/v2/user/addresses', payload);
      }
      wx.showToast({ title: '保存成功', icon: 'success' });
      this.setData({ showForm: false });
      this.loadAddresses();
    } catch (e) {
      const msg = (e && e.data && e.data.detail && e.data.detail.message) || (e && e.errMsg) || '保存失败';
      wx.showToast({ title: msg, icon: 'none' });
    }
  },

  setDefault(e) {
    const id = e.currentTarget.dataset.id;
    patch(`/api/v2/user/addresses/${id}/default`, { is_default: true })
      .then(() => { wx.showToast({ title: '已设为默认', icon: 'success' }); this.loadAddresses(); })
      .catch(() => wx.showToast({ title: '操作失败', icon: 'none' }));
  },

  deleteAddress(e) {
    const id = e.currentTarget.dataset.id;
    wx.showModal({
      title: '删除地址',
      content: '确定要删除此地址吗？',
      success: async (res) => {
        if (!res.confirm) return;
        try {
          await del(`/api/v2/user/addresses/${id}`);
          wx.showToast({ title: '已删除', icon: 'success' });
          this.loadAddresses();
        } catch (err) { console.log('deleteAddress error', err); }
      },
    });
  }
});
