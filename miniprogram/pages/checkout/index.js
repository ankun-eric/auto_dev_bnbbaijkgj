const { get, post } = require('../../utils/request');

Page({
  data: {
    productId: '',
    product: null,
    quantity: 1,
    address: null,
    store: null,
    fulfillmentType: '',
    appointmentDate: '',
    appointmentTime: '',
    appointmentNote: '',
    coupons: [],
    selectedCoupon: null,
    usePoints: false,
    availablePoints: 0,
    pointsDeduction: 0,
    maxPointsDeduction: 0,
    paymentMethod: '',
    paymentMethods: [],
    totalPrice: 0,
    discountPrice: 0,
    finalPrice: 0,
    submitting: false,
    showCouponPicker: false,
    minDate: '',
    endDate: '',
    advanceDaysHint: '',
    timeSlots: ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00'],
    slotAvailability: [],
    disabledSlots: [],
    fullyBookedSlots: [],
    // [PRD v1.0 2026-05-04 用户端下单页时段网格化展示与满额置灰]
    // slotItems：渲染用的时段数组 [{ label, full, disabled, expired }]
    // dateAvailMap：date 模式日历的满额映射 {date_str: {is_available, unavailable_reason}}
    slotItems: [],
    availableDates: [],
    appointmentDateFull: false,
    // [2026-05-02 H5 下单流程优化 PRD v1.0]
    contactPhone: '',
    contactPhoneError: '',
    // [先下单后预约 Bug 修复 v1.0]
    // needAppointment 控制下单页是否展示预约控件：
    //   true  → 商品 appointment_mode != 'none' 且 purchase_appointment_mode 为下单即预约
    //   false → 隐藏预约控件（包含「先下单后预约」场景）
    needAppointment: false,
    // [预约日期模式 Bug 修复 v1.0] 当前商品的 appointment_mode（none/date/time_slot/custom_form）
    // needTimeSlot 仅在 time_slot 模式才为 true，date 模式下绝不渲染时段块
    appointmentMode: 'none',
    needTimeSlot: false,
    // OPT-1 / M3-b：从券进入下单时默认勾选该券
    preselectCouponId: ''
  },

  onLoad(options) {
    const today = this.formatDate(new Date());
    const opts = options || {};
    this.setData({
      productId: opts.product_id,
      minDate: today,
      preselectCouponId: opts.couponId ? String(opts.couponId) : ''
    });
    this.loadProduct();
    this.loadCoupons();
    this.loadAddress();
    this.loadPoints();
    this.loadPaymentMethods();
  },

  loadPaymentMethods() {
    get('/api/pay/available-methods', { platform: 'miniprogram' }, { showLoading: false })
      .then(res => {
        const list = Array.isArray(res) ? res : (Array.isArray(res && res.data) ? res.data : []);
        this.setData({
          paymentMethods: list,
          paymentMethod: list.length > 0 ? list[0].channel_code : '',
        });
      })
      .catch(() => this.setData({ paymentMethods: [] }));
  },

  selectPaymentMethod(e) {
    const channelCode = e.currentTarget.dataset.code;
    this.setData({ paymentMethod: channelCode });
  },

  formatDate(date) {
    const y = date.getFullYear();
    const m = `${date.getMonth() + 1}`.padStart(2, '0');
    const d = `${date.getDate()}`.padStart(2, '0');
    return `${y}-${m}-${d}`;
  },

  async loadProduct() {
    try {
      const res = await get(`/api/products/${this.data.productId}`);
      const product = res.data || res;
      const today = new Date();
      // [先下单后预约 Bug 修复 v1.0]
      // 下单页是否展示预约控件 = 商品需预约 且 商品配置为「下单即预约」
      const purchaseMode = product.purchase_appointment_mode || '';
      const isBookWithOrder =
        !purchaseMode ||
        purchaseMode === 'purchase_with_appointment' ||
        purchaseMode === 'must_appoint';
      const appointmentMode = product.appointment_mode || 'none';
      const needAppointment = appointmentMode !== 'none' && isBookWithOrder;
      // [预约日期模式 Bug 修复 v1.0] 仅 time_slot 模式才需要选时段
      const needTimeSlot = needAppointment && appointmentMode === 'time_slot';
      const updateData = {
        product,
        fulfillmentType: product.fulfillment_type || 'online',
        totalPrice: product.price || 0,
        finalPrice: product.price || 0,
        maxPointsDeduction: Math.floor((product.price || 0) * 0.5 * 100),
        appointmentDate: this.formatDate(today),
        needAppointment,
        appointmentMode,
        needTimeSlot,
      };

      // BUG-PRODUCT-APPT-002：可预约日期范围统一公式
      // include_today=true  → [today, today + N - 1]
      // include_today=false → [today + 1, today + N]
      const advanceDays = product.advance_days || 0;
      const includeToday = product.include_today === false ? false : true;
      if (advanceDays > 0) {
        const startDate = new Date(today);
        if (!includeToday) {
          startDate.setDate(startDate.getDate() + 1);
        }
        const maxDate = new Date(startDate);
        maxDate.setDate(maxDate.getDate() + advanceDays - 1);
        updateData.minDate = this.formatDate(startDate);
        updateData.endDate = this.formatDate(maxDate);
        updateData.appointmentDate = this.formatDate(startDate);
        const incHint = includeToday ? '' : '（不含今天）';
        updateData.advanceDaysHint = `可预约：${startDate.getMonth() + 1}月${startDate.getDate()}日 ~ ${maxDate.getMonth() + 1}月${maxDate.getDate()}日${incHint}`;
      }

      if (product.time_slots && product.time_slots.length > 0) {
        updateData.timeSlots = product.time_slots.map(s => `${s.start}-${s.end}`);
      }

      this.setData(updateData);
      if (updateData.appointmentDate) {
        this.loadSlotAvailability(updateData.appointmentDate);
      }
      // [优惠券下单页 Bug 修复 v2 · B3] product 加载完后用真实 subtotal 重新拉一次"本单可用券"
      this.loadCoupons();
    } catch (e) {
      console.log('loadProduct error', e);
    }
  },

  async loadCoupons() {
    // [优惠券下单页 Bug 修复 v2 · B3] 切换为下单页专用接口（仅返回本单可用的券）
    try {
      const subtotal = this.data.totalPrice || 0;
      const res = await get('/api/coupons/usable-for-order', {
        product_id: this.data.productId,
        subtotal,
      }, { showLoading: false });
      const coupons = (res && res.items) || res || [];
      const update = { coupons };
      // OPT-1 / M3-b：若从我的券/兑换记录跳进来，默认勾选该券
      const pre = String(this.data.preselectCouponId || '');
      if (pre && (!this.data.selectedCoupon || String(this.data.selectedCoupon.id) !== pre)) {
        const matched = (coupons || []).find(c => String(c.id) === pre);
        if (matched) {
          update.selectedCoupon = matched;
        }
      }
      this.setData(update, () => {
        if (update.selectedCoupon) this.calcPrice();
      });
    } catch (e) {
      console.log('loadCoupons error', e);
    }
  },

  async loadAddress() {
    try {
      const res = await get('/api/addresses', {}, { showLoading: false });
      const addresses = res.items || res || [];
      const defaultAddr = addresses.find(a => a.is_default) || addresses[0] || null;
      this.setData({ address: defaultAddr });
    } catch (e) {
      console.log('loadAddress error', e);
    }
  },

  async loadPoints() {
    try {
      const app = getApp();
      const userInfo = app.getUserInfo();
      this.setData({
        availablePoints: (userInfo && userInfo.points) || 0
      });
    } catch (e) {
      console.log('loadPoints error', e);
    }
  },

  chooseAddress() {
    wx.navigateTo({
      url: '/pages/my-addresses/index?select=1',
      events: {
        selectAddress: (data) => {
          this.setData({ address: data });
        }
      }
    });
  },

  chooseStore() {
    wx.navigateTo({
      url: '/pages/store-select/index?select=1',
      events: {
        selectStore: (data) => {
          this.setData({ store: data });
        }
      }
    });
  },

  onDateChange(e) {
    this.setData({ appointmentDate: e.detail.value });
    this.loadSlotAvailability(e.detail.value);
  },

  // [PRD v1.0 2026-05-04 §4.3] 切换日期 / 进入页面时拉取该日期下时段满额状态。
  // 沿用 /api/h5/checkout/info 接口，返回 available_slots 和 available_dates。
  async loadSlotAvailability(dateStr) {
    if (!dateStr || !this.data.productId) return;
    const product = this.data.product;
    try {
      const params = { productId: this.data.productId, date: dateStr };
      if (this.data.store && (this.data.store.id || this.data.store.store_id)) {
        params.storeId = this.data.store.id || this.data.store.store_id;
      }
      const res = await get('/api/h5/checkout/info', params, { showLoading: false });
      const data = (res && res.data) || res || {};
      const availSlots = Array.isArray(data.available_slots) ? data.available_slots : [];
      const availDates = Array.isArray(data.available_dates) ? data.available_dates : [];
      this.setData({ slotAvailability: availSlots, availableDates: availDates });
      this.updateSlotItems(dateStr, availSlots, availDates, product);
    } catch (e) {
      this.setData({
        slotAvailability: [],
        availableDates: [],
        slotItems: [],
        disabledSlots: [],
        fullyBookedSlots: [],
        appointmentDateFull: false,
      });
    }
  },

  // 根据后端返回的 available_slots / available_dates 计算渲染用的 slotItems。
  updateSlotItems(dateStr, availSlots, availDates, productArg) {
    const product = productArg || this.data.product;
    const today = this.formatDate(new Date());
    const isToday = dateStr === today;
    const now = new Date();
    const nowHM = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;

    const productSlots = (product && product.time_slots) || [];
    const slotItems = [];
    const disabled = [];
    const fullyBooked = [];

    const availMap = {};
    availSlots.forEach(s => {
      const k = `${s.start_time}-${s.end_time}`;
      availMap[k] = s;
    });

    productSlots.forEach(slot => {
      const label = `${slot.start}-${slot.end}`;
      const expired = isToday && slot.end <= nowHM;
      const info = availMap[label];
      const full = info && info.is_available === false && info.unavailable_reason === 'occupied';
      if (expired || full) disabled.push(label);
      if (full && !expired) fullyBooked.push(label);
      slotItems.push({
        label,
        start: slot.start,
        end: slot.end,
        full: !!full,
        expired: !!expired,
        disabled: !!(expired || full),
      });
    });

    // 当前选中的日期是否已约满（用于在 picker 旁提示）
    const dateInfo = (availDates || []).find(d => d.date === dateStr);
    const dateFull = dateInfo && dateInfo.is_available === false && dateInfo.unavailable_reason === 'occupied';

    this.setData({
      slotItems,
      disabledSlots: disabled,
      fullyBookedSlots: fullyBooked,
      appointmentDateFull: !!dateFull,
    });
  },

  onTimeSlotTap(e) {
    const label = e.currentTarget.dataset.label;
    // [PRD v1.0 2026-05-04 §4.3] 满额或过期时段完全不响应（不弹 Toast、不变色）
    if (this.data.disabledSlots.includes(label)) return;
    this.setData({ appointmentTime: label });
  },

  onTimeChange(e) {
    this.setData({ appointmentTime: this.data.timeSlots[e.detail.value] });
  },

  onNoteInput(e) {
    let v = e.detail.value || '';
    // [2026-05-02 H5 下单流程优化 PRD v1.0] 备注最多 50 字
    if (v.length > 50) v = v.slice(0, 50);
    this.setData({ appointmentNote: v });
  },

  // [2026-05-02 H5 下单流程优化 PRD v1.0] 联系手机号输入
  onContactPhoneInput(e) {
    const v = e.detail.value || '';
    this.setData({ contactPhone: v, contactPhoneError: '' });
  },

  onContactPhoneBlur() {
    const v = this.data.contactPhone || '';
    const re = /^1[3-9]\d{9}$/;
    if (v && !re.test(v)) {
      this.setData({ contactPhoneError: '请输入正确的手机号' });
    } else {
      this.setData({ contactPhoneError: '' });
    }
  },

  onQuantityMinus() {
    if (this.data.quantity <= 1) return;
    this.setData({ quantity: this.data.quantity - 1 });
    this.calcPrice();
    // [优惠券下单页 Bug 修复 v2 · B3] 数量变化后 subtotal 改变，重新拉"本单可用券"
    this.loadCoupons();
  },

  onQuantityPlus() {
    this.setData({ quantity: this.data.quantity + 1 });
    this.calcPrice();
    this.loadCoupons();
  },

  toggleCouponPicker() {
    this.setData({ showCouponPicker: !this.data.showCouponPicker });
  },

  selectCoupon(e) {
    const coupon = e.currentTarget.dataset.item;
    this.setData({
      selectedCoupon: coupon,
      showCouponPicker: false
    });
    this.calcPrice();
  },

  clearCoupon() {
    this.setData({ selectedCoupon: null, showCouponPicker: false });
    this.calcPrice();
  },

  togglePoints() {
    this.setData({ usePoints: !this.data.usePoints });
    this.calcPrice();
  },

  calcPrice() {
    const r2 = n => Math.round(n * 100) / 100;
    const unitPrice = this.data.product ? this.data.product.price : 0;
    const total = r2(unitPrice * this.data.quantity);
    let discount = 0;

    // [优惠券下单页 Bug 修复 v2 · B1] 适配后端 /usable-for-order 返回的数据结构
    // 新接口 item 字段：{ id, type: 'full_reduction|discount|voucher|free_trial', discount_value, discount_rate, condition_amount, ... }
    if (this.data.selectedCoupon) {
      const c = this.data.selectedCoupon;
      const t = c.type;
      if (t === 'free_trial') {
        // 整单 0 元
        discount = total;
      } else if (t === 'discount') {
        discount = total * (1 - (c.discount_rate || 1));
      } else if (t === 'full_reduction' || t === 'voucher') {
        discount = c.discount_value || 0;
      } else if (t === 'fixed') {
        // 兼容老结构
        discount = c.value || 0;
      } else if (t === 'percent') {
        discount = total * (c.value || 0) / 100;
      }
    }
    discount = r2(Math.min(discount, total));

    let pointsDed = 0;
    if (this.data.usePoints) {
      const maxPoints = Math.min(this.data.availablePoints, this.data.maxPointsDeduction);
      pointsDed = r2(maxPoints / 100);
    }

    const finalPrice = r2(Math.max(0, total - discount - pointsDed));
    this.setData({
      totalPrice: total,
      discountPrice: discount,
      pointsDeduction: pointsDed,
      finalPrice: finalPrice
    });
  },

  async submitOrder() {
    if (this.data.submitting) return;

    const ft = this.data.fulfillmentType;
    if ((ft === 'express' || ft === 'home') && !this.data.address) {
      wx.showToast({ title: '请选择收货地址', icon: 'none' });
      return;
    }
    if (ft === 'store' && !this.data.store) {
      wx.showToast({ title: '请选择门店', icon: 'none' });
      return;
    }
    // [先下单后预约 Bug 修复 v1.0] 仅 needAppointment=true 时强校验预约时间
    if (this.data.needAppointment && (ft === 'store' || ft === 'home') && !this.data.appointmentDate) {
      wx.showToast({ title: '请选择预约日期', icon: 'none' });
      return;
    }
    // [PRD v1.0 2026-05-04 §4.1.2] date 模式下选中已约满日期 → 禁止提交（前端兜底，后端会再次校验）
    if (this.data.needAppointment && this.data.appointmentMode === 'date' && this.data.appointmentDateFull) {
      wx.showToast({ title: '所选日期已约满，请重新选择', icon: 'none' });
      return;
    }
    // [2026-05-02 H5 下单流程优化 PRD v1.0] 联系人手机号必填校验（仅展示预约表单时）
    const phone = (this.data.contactPhone || '').trim();
    const phoneRe = /^1[3-9]\d{9}$/;
    if (this.data.needAppointment && (!phone || !phoneRe.test(phone))) {
      this.setData({ contactPhoneError: '请输入正确的手机号' });
      wx.showToast({ title: '请输入正确的联系手机号', icon: 'none' });
      return;
    }

    this.setData({ submitting: true });
    try {
      const itemData = {
        product_id: parseInt(this.data.productId),
        quantity: this.data.quantity,
      };
      // [先下单后预约 + 预约日期模式 Bug 修复 v1.0]
      // 仅 needAppointment 时携带预约信息；其中 time_slot 模式才传 time_slot，date 模式不传
      if (this.data.needAppointment && this.data.needTimeSlot && this.data.appointmentTime) {
        const startTime = this.data.appointmentTime.split('-')[0];
        itemData.appointment_time = `${this.data.appointmentDate}T${startTime}:00`;
      } else if (this.data.needAppointment && this.data.appointmentDate) {
        itemData.appointment_time = `${this.data.appointmentDate}T00:00:00`;
      }
      if (this.data.needAppointment && this.data.appointmentDate) {
        const apptData = {
          date: this.data.appointmentDate,
          note: this.data.appointmentNote || '',
          contact_phone: phone,
          store_id: this.data.store ? (this.data.store.id || this.data.store.store_id) : undefined,
        };
        if (this.data.needTimeSlot && this.data.appointmentTime) {
          apptData.time_slot = this.data.appointmentTime;
        }
        itemData.appointment_data = apptData;
      }

      // [2026-05-04 支付通道枚举不一致 Bug 修复 v1.0]
      // 创建订单的 payment_method 必须为 provider 级别（wechat / alipay），
      // 而 paymentMethod 当前存的是 channel_code（如 wechat_miniprogram）。
      // 从 paymentMethods 列表中按 channel_code 找到对应的 provider，找不到则按
      // _ 前缀降级提取，确保后端入库的 payment_method 仅为 wechat / alipay。
      const _selectedMethodObj = (this.data.paymentMethods || []).find(m => m && m.channel_code === this.data.paymentMethod);
      const _fallbackProvider = String(this.data.paymentMethod || 'wechat').split('_')[0];
      const _providerForOrder = (_selectedMethodObj && _selectedMethodObj.provider) || _fallbackProvider || 'wechat';

      const orderData = {
        items: [itemData],
        // [2026-05-04 支付通道枚举不一致 Bug 修复 v1.0] 仅传 provider 级别值
        payment_method: _providerForOrder,
        points_deduction: this.data.usePoints ? Math.min(this.data.availablePoints, this.data.maxPointsDeduction) : 0,
        notes: this.data.appointmentNote || undefined,
      };
      if (this.data.address) {
        if (this.data.fulfillmentType === 'on_site') {
          orderData.service_address_id = this.data.address.id;
        } else {
          orderData.shipping_address_id = this.data.address.id;
        }
      }
      if (this.data.selectedCoupon) orderData.coupon_id = this.data.selectedCoupon.id;

      const res = await post('/api/orders/unified', orderData);
      const order = res.data || res;
      const paidAmount = Number(order.paid_amount) || 0;

      if (paidAmount === 0) {
        try {
          await post(`/api/orders/unified/${order.id}/confirm-free`, { channel_code: this.data.paymentMethod || null });
          wx.showToast({ title: '支付成功', icon: 'success' });
          setTimeout(() => wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${order.id}` }), 800);
        } catch (e) {
          wx.showToast({ title: '免单确认失败', icon: 'none' });
        }
        return;
      }

      if (!this.data.paymentMethod) {
        wx.showToast({ title: '请选择支付方式', icon: 'none' });
        return;
      }

      try {
        const payRes = await post(`/api/orders/unified/${order.id}/pay`, { channel_code: this.data.paymentMethod });
        const paymentParams = (payRes && payRes.payment_params) || order.payment_params;
        if (this.data.paymentMethod === 'wechat_miniprogram' && paymentParams) {
          wx.requestPayment({
            ...paymentParams,
            success: () => wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${order.id}` }),
            fail: () => wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${order.id}` }),
          });
        } else {
          wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${order.id}` });
        }
      } catch (e) {
        wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${order.id}` });
      }
    } catch (e) {
      console.log('submitOrder error', e);
    } finally {
      this.setData({ submitting: false });
    }
  }
});
