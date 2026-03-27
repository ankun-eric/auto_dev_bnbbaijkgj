const { get } = require('../../utils/request')

Page({
  data: {
    records: [],
    loading: false,
    noMore: false,
    page: 1,
    pageSize: 20,
    totalCount: 0,
    startDate: '',
    endDate: '',
    activeQuick: 'today'
  },

  onLoad: function () {
    this.initDates()
    this.filterToday()
  },

  onPullDownRefresh: function () {
    this.setData({ page: 1, records: [], noMore: false })
    this.loadRecords().then(function () {
      wx.stopPullDownRefresh()
    })
  },

  onReachBottom: function () {
    if (!this.data.noMore && !this.data.loading) {
      this.loadRecords()
    }
  },

  initDates: function () {
    var today = this.formatDate(new Date())
    this.setData({
      startDate: today,
      endDate: today
    })
  },

  formatDate: function (date) {
    var y = date.getFullYear()
    var m = (date.getMonth() + 1).toString().padStart(2, '0')
    var d = date.getDate().toString().padStart(2, '0')
    return y + '-' + m + '-' + d
  },

  onStartDateChange: function (e) {
    this.setData({
      startDate: e.detail.value,
      activeQuick: '',
      page: 1,
      records: [],
      noMore: false
    })
    this.loadRecords()
  },

  onEndDateChange: function (e) {
    this.setData({
      endDate: e.detail.value,
      activeQuick: '',
      page: 1,
      records: [],
      noMore: false
    })
    this.loadRecords()
  },

  filterToday: function () {
    var today = this.formatDate(new Date())
    this.setData({
      startDate: today,
      endDate: today,
      activeQuick: 'today',
      page: 1,
      records: [],
      noMore: false
    })
    this.loadRecords()
  },

  filterWeek: function () {
    var now = new Date()
    var day = now.getDay() || 7
    var monday = new Date(now)
    monday.setDate(now.getDate() - day + 1)
    this.setData({
      startDate: this.formatDate(monday),
      endDate: this.formatDate(now),
      activeQuick: 'week',
      page: 1,
      records: [],
      noMore: false
    })
    this.loadRecords()
  },

  filterMonth: function () {
    var now = new Date()
    var firstDay = new Date(now.getFullYear(), now.getMonth(), 1)
    this.setData({
      startDate: this.formatDate(firstDay),
      endDate: this.formatDate(now),
      activeQuick: 'month',
      page: 1,
      records: [],
      noMore: false
    })
    this.loadRecords()
  },

  filterAll: function () {
    this.setData({
      startDate: '',
      endDate: '',
      activeQuick: 'all',
      page: 1,
      records: [],
      noMore: false
    })
    this.loadRecords()
  },

  loadRecords: function () {
    var that = this
    if (this.data.loading) return Promise.resolve()

    this.setData({ loading: true })

    var params = {
      page: this.data.page,
      pageSize: this.data.pageSize
    }
    if (this.data.startDate) params.startDate = this.data.startDate
    if (this.data.endDate) params.endDate = this.data.endDate

    return get('/api/orders', params).then(function (res) {
      var list = res.items || []
      var total = res.total || 0
      var newRecords = that.data.records.concat(list)

      that.setData({
        records: newRecords,
        totalCount: total,
        page: that.data.page + 1,
        noMore: newRecords.length >= total || list.length < that.data.pageSize
      })
    }).catch(function () {
      wx.showToast({ title: '加载失败', icon: 'none' })
    }).finally(function () {
      that.setData({ loading: false })
    })
  }
})
