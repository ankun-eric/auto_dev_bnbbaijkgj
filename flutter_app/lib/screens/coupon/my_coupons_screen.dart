import 'package:flutter/material.dart';
import '../../models/coupon.dart';
import '../../services/api_service.dart';
import '../points/exchange_records_screen.dart' show jumpToUseCoupon;

class MyCouponsScreen extends StatefulWidget {
  /// OPT-1：支持外部传入初始 Tab 与高亮券 id
  /// initialTab: 'available' | 'used' | 'expired'（兼容 'unused'）
  final String? initialTab;
  final int? highlightCouponId;

  const MyCouponsScreen({
    super.key,
    this.initialTab,
    this.highlightCouponId,
  });

  @override
  State<MyCouponsScreen> createState() => _MyCouponsScreenState();
}

class _MyCouponsScreenState extends State<MyCouponsScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiService _api = ApiService();
  final List<Map<String, String>> _tabs = [
    {'label': '可用', 'status': 'unused'},
    {'label': '已使用', 'status': 'used'},
    {'label': '已过期', 'status': 'expired'},
  ];
  int _availableCount = 0;

  String? _routeInitialTab;
  int? _routeHighlightCouponId;
  bool _routeArgsParsed = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
    _loadAvailableCount();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_routeArgsParsed) return;
    _routeArgsParsed = true;
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map) {
      _routeInitialTab = args['tab']?.toString();
      final hid = args['highlightCouponId'];
      if (hid is int) _routeHighlightCouponId = hid;
      else if (hid != null) _routeHighlightCouponId = int.tryParse('$hid');
    }
    final initial = widget.initialTab ?? _routeInitialTab;
    if (initial != null) {
      // 'available' 视为 'unused'
      final norm = initial == 'available' ? 'unused' : initial;
      final idx = _tabs.indexWhere((t) => t['status'] == norm);
      if (idx >= 0 && idx != _tabController.index) {
        _tabController.index = idx;
      }
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadAvailableCount() async {
    try {
      final res = await _api.getMyCoupons(tab: 'unused', excludeExpired: true);
      final data = res.data;
      if (data is Map) {
        final count = data['available_count'] ?? data['available'] ?? data['total'] ??
            ((data['items'] is List) ? (data['items'] as List).length : 0);
        final n = (count is int) ? count : int.tryParse('$count') ?? 0;
        if (mounted) setState(() => _availableCount = n);
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    final highlightId = widget.highlightCouponId ?? _routeHighlightCouponId;
    return Scaffold(
      appBar: AppBar(
        title: const Text('我的优惠券'),
        backgroundColor: const Color(0xFF52C41A),
        actions: [
          TextButton(
            onPressed: () => Navigator.pushNamed(context, '/coupon-center'),
            child: const Text('领券', style: TextStyle(color: Colors.white)),
          ),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(110),
          child: Column(
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(vertical: 14),
                color: const Color(0xFF52C41A),
                child: Column(
                  children: [
                    const Text('合计', style: TextStyle(color: Colors.white70, fontSize: 12)),
                    const SizedBox(height: 2),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.baseline,
                      textBaseline: TextBaseline.alphabetic,
                      children: [
                        Text(
                          '$_availableCount',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        const SizedBox(width: 4),
                        const Text('张可用',
                            style: TextStyle(color: Colors.white70, fontSize: 13)),
                      ],
                    ),
                  ],
                ),
              ),
              TabBar(
                controller: _tabController,
                indicatorColor: Colors.white,
                indicatorWeight: 3,
                tabs: _tabs.map((t) {
                  final label = t['status'] == 'unused'
                      ? '${t['label']}($_availableCount)'
                      : t['label']!;
                  return Tab(text: label);
                }).toList(),
              ),
            ],
          ),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: _tabs
            .map((t) => _CouponTab(
                  status: t['status']!,
                  highlightCouponId: t['status'] == 'unused' ? highlightId : null,
                  onCountChanged: t['status'] == 'unused'
                      ? (n) {
                          if (mounted) setState(() => _availableCount = n);
                        }
                      : null,
                ))
            .toList(),
      ),
    );
  }
}

class _CouponTab extends StatefulWidget {
  final String status;
  final ValueChanged<int>? onCountChanged;
  final int? highlightCouponId;
  const _CouponTab({
    required this.status,
    this.onCountChanged,
    this.highlightCouponId,
  });

  @override
  State<_CouponTab> createState() => _CouponTabState();
}

class _CouponTabState extends State<_CouponTab>
    with AutomaticKeepAliveClientMixin, TickerProviderStateMixin {
  final ApiService _api = ApiService();
  List<UserCoupon> _coupons = [];
  bool _loading = true;
  AnimationController? _highlightCtrl;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    if (widget.highlightCouponId != null) {
      _highlightCtrl = AnimationController(
        vsync: this,
        duration: const Duration(milliseconds: 1500),
      );
    }
    _loadCoupons();
  }

  @override
  void dispose() {
    _highlightCtrl?.dispose();
    super.dispose();
  }

  Future<void> _loadCoupons() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getMyCoupons(
        tab: widget.status,
        excludeExpired: widget.status == 'unused',
      );
      final data = res.data;
      if (data is Map && data['items'] is List) {
        final items = (data['items'] as List)
            .map((e) => UserCoupon.fromJson(e as Map<String, dynamic>))
            .toList();
        if (mounted) {
          setState(() {
            _coupons = items;
          });
        }
        if (widget.status == 'unused' && widget.onCountChanged != null) {
          final count = data['available_count'] ??
              data['available'] ??
              data['total'] ??
              items.length;
          final n = (count is int) ? count : int.tryParse('$count') ?? items.length;
          widget.onCountChanged!(n);
        }
        // OPT-1：列表加载完后启动 1.5s 高亮动画
        if (widget.highlightCouponId != null && _highlightCtrl != null) {
          _highlightCtrl!.forward(from: 0);
        }
      }
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  bool _isExpiringSoon(String? validEnd) {
    if (validEnd == null || validEnd.isEmpty) return false;
    try {
      final t = DateTime.parse(validEnd);
      final diff = t.difference(DateTime.now());
      return !diff.isNegative && diff.inDays <= 7;
    } catch (_) {
      return false;
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    if (_loading) {
      return const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)));
    }
    if (_coupons.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.local_offer_outlined, size: 64, color: Colors.grey[300]),
            const SizedBox(height: 12),
            Text('暂无优惠券', style: TextStyle(color: Colors.grey[500])),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _loadCoupons,
      color: const Color(0xFF52C41A),
      child: ListView.builder(
        padding: const EdgeInsets.all(16),
        itemCount: _coupons.length,
        itemBuilder: (context, index) => _buildCouponCard(_coupons[index]),
      ),
    );
  }

  Widget _buildCouponCard(UserCoupon uc) {
    final coupon = uc.coupon;
    if (coupon == null) return const SizedBox.shrink();
    final disabled = widget.status != 'unused';
    final isLongTerm = coupon.validEnd == null || coupon.validEnd!.isEmpty;
    final isExpiringSoon = !isLongTerm && widget.status == 'unused' && _isExpiringSoon(coupon.validEnd);
    final isHighlightTarget = widget.highlightCouponId != null &&
        widget.highlightCouponId == uc.id;

    final card = Opacity(
      opacity: disabled ? 0.5 : 1.0,
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8)],
        ),
        child: Row(
          children: [
            Container(
              width: 100,
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: disabled ? Colors.grey : const Color(0xFFFF4D4F),
                borderRadius: const BorderRadius.only(
                  topLeft: Radius.circular(12),
                  bottomLeft: Radius.circular(12),
                ),
              ),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  if (coupon.type == 'discount')
                    Text('${(coupon.discountRate * 10).toStringAsFixed(1)}折',
                        style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold))
                  else
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('¥', style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
                        Text('${coupon.discountValue.toInt()}',
                            style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold)),
                      ],
                    ),
                  if (coupon.conditionAmount > 0)
                    Text('满${coupon.conditionAmount.toInt()}可用',
                        style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 11)),
                ],
              ),
            ),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(coupon.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                        if (isLongTerm)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                            decoration: BoxDecoration(
                              color: const Color(0xFF52C41A).withOpacity(0.12),
                              border: Border.all(color: const Color(0xFF52C41A).withOpacity(0.5)),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('长期有效',
                                style: TextStyle(fontSize: 10, color: Color(0xFF52C41A), fontWeight: FontWeight.w500)),
                          )
                        else if (isExpiringSoon)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                            decoration: BoxDecoration(
                              color: const Color(0xFFFF4D4F).withOpacity(0.12),
                              border: Border.all(color: const Color(0xFFFF4D4F).withOpacity(0.5)),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: const Text('即将到期',
                                style: TextStyle(fontSize: 10, color: Color(0xFFFF4D4F), fontWeight: FontWeight.w500)),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(coupon.typeLabel, style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                    const SizedBox(height: 4),
                    if (isLongTerm)
                      const Text('长期有效',
                          style: TextStyle(fontSize: 11, color: Color(0xFF52C41A)))
                    else
                      Text('有效期至 ${coupon.validEnd!.split('T').first}',
                          style: TextStyle(
                            fontSize: 11,
                            color: isExpiringSoon ? const Color(0xFFFF4D4F) : Colors.grey[400],
                            fontWeight: isExpiringSoon ? FontWeight.w600 : FontWeight.normal,
                          )),
                    if (uc.status != 'unused')
                      Padding(
                        padding: const EdgeInsets.only(top: 4),
                        child: Text(uc.statusLabel,
                            style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                      ),
                    // OPT-1：仅"可用"Tab 显示「去使用」按钮
                    if (widget.status == 'unused')
                      Align(
                        alignment: Alignment.centerRight,
                        child: Padding(
                          padding: const EdgeInsets.only(top: 6),
                          child: ElevatedButton(
                            onPressed: () {
                              Navigator.pushNamed(
                                context,
                                '/services',
                                arguments: {'couponId': uc.id},
                              );
                            },
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF52C41A),
                              foregroundColor: Colors.white,
                              minimumSize: const Size(72, 30),
                              padding: const EdgeInsets.symmetric(horizontal: 14),
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(15),
                              ),
                              textStyle: const TextStyle(fontSize: 12),
                            ),
                            child: const Text('去使用'),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );

    if (!isHighlightTarget || _highlightCtrl == null) return card;

    return AnimatedBuilder(
      animation: _highlightCtrl!,
      builder: (ctx, child) {
        // 1.5s 内 0→1 的进度，0.5s 渐入 0.5s 保持 0.5s 渐出
        final v = _highlightCtrl!.value;
        double intensity;
        if (v < 0.33) {
          intensity = v / 0.33;
        } else if (v < 0.66) {
          intensity = 1.0;
        } else {
          intensity = (1.0 - v) / 0.34;
        }
        final color = Color.lerp(
          Colors.transparent,
          const Color(0xFF52C41A).withOpacity(0.18),
          intensity.clamp(0.0, 1.0),
        );
        return Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            color: color,
          ),
          child: child,
        );
      },
      child: card,
    );
  }
}
