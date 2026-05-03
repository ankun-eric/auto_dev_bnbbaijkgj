/**
 * 卡核销页（v2.0 第 3 期）
 * - 接收 code（数字 / token）
 * - 选择 product_id / store_id
 * - 调用 POST /api/staff/cards/redeem
 */
const { post } = require('../../utils/request')

Page({
  data: {
    code: '',
    isToken: false,
    productIdInput: '',
    storeIdInput: '',
    submitting: false,
  },

  onLoad: function (options) {
    var code = options && options.code ? decodeURIComponent(options.code) : ''
    this.setData({
      code: code,
      isToken: code.length >= 16,
    })
  },

  onProductInput: function (e) {
    this.setData({ productIdInput: e.detail.value })
  },

  onStoreInput: function (e) {
    this.setData({ storeIdInput: e.detail.value })
  },

  handleRedeem: function () {
    var that = this
    var pid = parseInt(this.data.productIdInput, 10)
    if (!pid) {
      wx.showToast({ title: '请填写项目 ID', icon: 'none' })
      return
    }
    this.setData({ submitting: true })
    var body = {
      product_id: pid,
    }
    if (this.data.isToken) {
      body.code_token = this.data.code
    } else {
      body.code_digits = this.data.code
    }
    if (this.data.storeIdInput) {
      body.store_id = parseInt(this.data.storeIdInput, 10)
    }
    post('/api/staff/cards/redeem', body).then(function (res) {
      wx.navigateTo({
        url: '/pages/result/index?status=success&orderNo=card_log_' + (res.log_id || '')
      })
    }).catch(function (err) {
      wx.navigateTo({
        url: '/pages/result/index?status=fail&reason=' + encodeURIComponent((err && err.detail) || '核销失败')
      })
    }).finally(function () {
      that.setData({ submitting: false })
    })
  },
})
