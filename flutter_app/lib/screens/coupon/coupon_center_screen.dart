import 'package:flutter/material.dart';
import '../../models/coupon.dart';
import '../../services/api_service.dart';

class CouponCenterScreen extends StatefulWidget {
  const CouponCenterScreen({super.key});

  @override
  State<CouponCenterScreen> createState() => _CouponCenterScreenState();
}

class _CouponCenterScreenState extends State<CouponCenterScreen> {
  final ApiService _api = ApiService();
  List<Coupon> _coupons = [];
  bool _loading = true;
  final Set<int> _claimedIds = {};

  @override
  void initState() {
    super.initState();
    _loadCoupons();
  }

  Future<void> _loadCoupons() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getAvailableCoupons();
      final data = res.data;
      if (data is Map && data['items'] is List) {
        setState(() {
          _coupons = (data['items'] as List)
              .map((e) => Coupon.fromJson(e as Map<String, dynamic>))
              .toList();
        });
      }
    } catch (_) {}
    setState(() => _loading = false);
  }

  Future<void> _claimCoupon(Coupon coupon) async {
    try {
      await _api.claimCoupon(coupon.id);
      setState(() => _claimedIds.add(coupon.id));
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('领取成功')));
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('领取失败')));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('领券中心'),
        backgroundColor: const Color(0xFF52C41A),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : _coupons.isEmpty
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(Icons.local_offer_outlined, size: 64, color: Colors.grey[300]),
                      const SizedBox(height: 12),
                      Text('暂无可领优惠券', style: TextStyle(color: Colors.grey[500])),
                    ],
                  ),
                )
              : RefreshIndicator(
                  onRefresh: _loadCoupons,
                  color: const Color(0xFF52C41A),
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: _coupons.length,
                    itemBuilder: (context, index) => _buildCouponCard(_coupons[index]),
                  ),
                ),
    );
  }

  Widget _buildCouponCard(Coupon coupon) {
    final claimed = _claimedIds.contains(coupon.id);
    return Container(
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
            decoration: const BoxDecoration(
              color: Color(0xFFFF4D4F),
              borderRadius: BorderRadius.only(
                topLeft: Radius.circular(12),
                bottomLeft: Radius.circular(12),
              ),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                if (coupon.type == 'discount')
                  Text(
                    '${(coupon.discountRate * 10).toStringAsFixed(1)}折',
                    style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
                  )
                else
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text('¥', style: TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold)),
                      Text(
                        '${coupon.discountValue.toInt()}',
                        style: const TextStyle(color: Colors.white, fontSize: 28, fontWeight: FontWeight.bold),
                      ),
                    ],
                  ),
                if (coupon.conditionAmount > 0)
                  Text(
                    '满${coupon.conditionAmount.toInt()}可用',
                    style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 11),
                  ),
              ],
            ),
          ),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(coupon.name, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 15)),
                  const SizedBox(height: 4),
                  Text(coupon.typeLabel, style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                  if (coupon.validEnd != null) ...[
                    const SizedBox(height: 4),
                    Text(
                      '有效期至 ${coupon.validEnd!.split('T').first}',
                      style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                    ),
                  ],
                  if (coupon.remaining >= 0) ...[
                    const SizedBox(height: 2),
                    Text(
                      '剩余${coupon.remaining}张',
                      style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                    ),
                  ],
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: claimed
                ? Container(
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    decoration: BoxDecoration(
                      color: Colors.grey[200],
                      borderRadius: BorderRadius.circular(16),
                    ),
                    child: Text('已领取', style: TextStyle(color: Colors.grey[500], fontSize: 13)),
                  )
                : ElevatedButton(
                    onPressed: () => _claimCoupon(coupon),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF52C41A),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    ),
                    child: const Text('领取', style: TextStyle(fontSize: 13)),
                  ),
          ),
        ],
      ),
    );
  }
}
