const { get, post } = require('../../utils/request')

Page({
  data: {
    orderInfo: null,
    verifying: false
  },

  onLoad: function () {
    this.startScan()
  },

  startScan: function () {
    var that = this
    this.setData({ orderInfo: null })

    wx.scanCode({
      onlyFromCamera: false,
      scanType: ['qrCode', 'barCode'],
      success: function (res) {
        var code = res.result
        that.queryOrder(code)
      },
      fail: function (err) {
        if (err.errMsg && err.errMsg.indexOf('cancel') === -1) {
          wx.showToast({ title: '扫码失败，请重试', icon: 'none' })
        }
      }
    })
  },

  queryOrder: function (code) {
    var that = this
    wx.showLoading({ title: '查询订单中...' })

    get('/api/orders/verify-code/' + encodeURIComponent(code)).then(function (res) {
      wx.hideLoading()
      var info = res || {}
      if (!info.refund_status) {
        info.refund_status = 'none'
      }
      that.setData({ orderInfo: info })
    }).catch(function (err) {
      wx.hideLoading()
      wx.showToast({ title: (err && err.detail) || '未找到对应订单', icon: 'none' })
    })
  },

  handleVerify: function () {
    var that = this
    var orderInfo = this.data.orderInfo
    if (!orderInfo || !orderInfo.id) return

    var rs = orderInfo.refund_status || 'none'
    if (rs === 'applied' || rs === 'reviewing' || rs === 'approved' || rs === 'returning') {
      wx.showToast({ title: '该订单正在退款处理中，无法核销', icon: 'none' })
      return
    }
    if (rs === 'refund_success') {
      wx.showToast({ title: '该订单已退款，无法核销', icon: 'none' })
      return
    }

    wx.showModal({
      title: '确认核销',
      content: '确定要核销订单 ' + orderInfo.orderNo + ' 吗？',
      confirmColor: '#52c41a',
      success: function (res) {
        if (res.confirm) {
          that.doVerify(orderInfo.id)
        }
      }
    })
  },

  doVerify: function (orderId) {
    var that = this
    this.setData({ verifying: true })

    post('/api/orders/' + orderId + '/verify').then(function (res) {
      wx.navigateTo({
        url: '/pages/result/index?status=success&orderNo=' + (that.data.orderInfo.order_no || '')
      })
    }).catch(function (err) {
      wx.navigateTo({
        url: '/pages/result/index?status=fail&reason=' + encodeURIComponent((err && err.detail) || '核销失败')
      })
    }).finally(function () {
      that.setData({ verifying: false })
    })
  }
})
