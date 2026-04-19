import 'package:flutter/material.dart';
import '../../models/coupon.dart';
import '../../services/api_service.dart';

class MyCouponsScreen extends StatefulWidget {
  const MyCouponsScreen({super.key});

  @override
  State<MyCouponsScreen> createState() => _MyCouponsScreenState();
}

class _MyCouponsScreenState extends State<MyCouponsScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final List<Map<String, String>> _tabs = [
    {'label': '未使用', 'status': 'unused'},
    {'label': '已使用', 'status': 'used'},
    {'label': '已过期', 'status': 'expired'},
  ];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          tabs: _tabs.map((t) => Tab(text: t['label'])).toList(),
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: _tabs.map((t) => _CouponTab(status: t['status']!)).toList(),
      ),
    );
  }
}

class _CouponTab extends StatefulWidget {
  final String status;
  const _CouponTab({required this.status});

  @override
  State<_CouponTab> createState() => _CouponTabState();
}

class _CouponTabState extends State<_CouponTab> with AutomaticKeepAliveClientMixin {
  final ApiService _api = ApiService();
  List<UserCoupon> _coupons = [];
  bool _loading = true;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    _loadCoupons();
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
        setState(() {
          _coupons = (data['items'] as List)
              .map((e) => UserCoupon.fromJson(e as Map<String, dynamic>))
              .toList();
        });
      }
    } catch (_) {}
    setState(() => _loading = false);
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

    return Opacity(
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
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
