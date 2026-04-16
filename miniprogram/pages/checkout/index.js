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
    paymentMethod: 'wechat',
    totalPrice: 0,
    discountPrice: 0,
    finalPrice: 0,
    submitting: false,
    showCouponPicker: false,
    minDate: '',
    timeSlots: ['09:00', '10:00', '11:00', '12:00', '13:00', '14:00', '15:00', '16:00', '17:00']
  },

  onLoad(options) {
    const today = this.formatDate(new Date());
    this.setData({
      productId: options.product_id,
      minDate: today
    });
    this.loadProduct();
    this.loadCoupons();
    this.loadAddress();
    this.loadPoints();
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
      this.setData({
        product,
        fulfillmentType: product.fulfillment_type || 'online',
        totalPrice: product.price || 0,
        finalPrice: product.price || 0,
        maxPointsDeduction: Math.floor((product.price || 0) * 0.5 * 100)
      });
    } catch (e) {
      console.log('loadProduct error', e);
    }
  },

  async loadCoupons() {
    try {
      const res = await get('/api/coupons/available', {
        product_id: this.data.productId
      }, { showLoading: false });
      this.setData({ coupons: res.items || res || [] });
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
  },

  onTimeChange(e) {
    this.setData({ appointmentTime: this.data.timeSlots[e.detail.value] });
  },

  onNoteInput(e) {
    this.setData({ appointmentNote: e.detail.value });
  },

  onQuantityMinus() {
    if (this.data.quantity <= 1) return;
    this.setData({ quantity: this.data.quantity - 1 });
    this.calcPrice();
  },

  onQuantityPlus() {
    this.setData({ quantity: this.data.quantity + 1 });
    this.calcPrice();
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
    const unitPrice = this.data.product ? this.data.product.price : 0;
    const total = unitPrice * this.data.quantity;
    let discount = 0;

    if (this.data.selectedCoupon) {
      const c = this.data.selectedCoupon;
      if (c.type === 'fixed') {
        discount += c.value || 0;
      } else if (c.type === 'percent') {
        discount += total * (c.value || 0) / 100;
      }
    }

    let pointsDed = 0;
    if (this.data.usePoints) {
      const maxPoints = Math.min(this.data.availablePoints, this.data.maxPointsDeduction);
      pointsDed = maxPoints / 100;
    }

    const finalPrice = Math.max(0, total - discount - pointsDed);
    this.setData({
      totalPrice: total.toFixed(2),
      discountPrice: discount.toFixed(2),
      pointsDeduction: pointsDed.toFixed(2),
      finalPrice: finalPrice.toFixed(2)
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

    this.setData({ submitting: true });
    try {
      const itemData = {
        product_id: parseInt(this.data.productId),
        quantity: this.data.quantity,
      };
      if (this.data.appointmentTime) {
        itemData.appointment_time = `${this.data.appointmentDate}T${this.data.appointmentTime}:00`;
      }
      if (this.data.appointmentDate && this.data.appointmentNote) {
        itemData.appointment_data = { date: this.data.appointmentDate, note: this.data.appointmentNote };
      }

      const orderData = {
        items: [itemData],
        payment_method: this.data.paymentMethod,
        points_deduction: this.data.usePoints ? Math.min(this.data.availablePoints, this.data.maxPointsDeduction) : 0,
        notes: this.data.appointmentNote || undefined,
      };
      if (this.data.address) orderData.shipping_address_id = this.data.address.id;
      if (this.data.selectedCoupon) orderData.coupon_id = this.data.selectedCoupon.id;

      const res = await post('/api/orders/unified', orderData);
      const order = res.data || res;

      if (this.data.paymentMethod === 'wechat' && order.payment_params) {
        wx.requestPayment({
          ...order.payment_params,
          success: () => {
            wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${order.id}` });
          },
          fail: () => {
            wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${order.id}` });
          }
        });
      } else {
        wx.redirectTo({ url: `/pages/unified-order-detail/index?id=${order.id}` });
      }
    } catch (e) {
      console.log('submitOrder error', e);
    } finally {
      this.setData({ submitting: false });
    }
  }
});
