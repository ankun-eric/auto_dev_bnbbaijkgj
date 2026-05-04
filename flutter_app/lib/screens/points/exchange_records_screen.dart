import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

/// OPT-4：兑换记录中的优惠券字段（snake_case → camelCase）
class ExchangeRecord {
  final int? couponId;
  final String? couponStatus;
  final String? couponScope;
  final Map<String, dynamic> raw;

  ExchangeRecord({
    this.couponId,
    this.couponStatus,
    this.couponScope,
    required this.raw,
  });

  factory ExchangeRecord.fromJson(Map<String, dynamic> json) {
    int? cid;
    final rawCid = json['coupon_id'];
    if (rawCid is int) {
      cid = rawCid;
    } else if (rawCid != null) {
      cid = int.tryParse('$rawCid');
    }
    return ExchangeRecord(
      couponId: cid,
      couponStatus: json['coupon_status']?.toString(),
      couponScope: json['coupon_scope']?.toString(),
      raw: json,
    );
  }
}

/// OPT-4：优惠券【去使用】统一跳转工具
/// 默认：跳服务列表（带 couponId），由服务列表页弹横幅引导用户挑商品下单。
void jumpToUseCoupon(BuildContext context, int? couponId) {
  if (couponId == null) {
    Navigator.pushNamed(context, '/services');
    return;
  }
  Navigator.pushNamed(
    context,
    '/services',
    arguments: {'couponId': couponId},
  );
}

class PointsExchangeRecordsScreen extends StatefulWidget {
  const PointsExchangeRecordsScreen({super.key});

  @override
  State<PointsExchangeRecordsScreen> createState() => _PointsExchangeRecordsScreenState();
}

class _PointsExchangeRecordsScreenState extends State<PointsExchangeRecordsScreen> {
  final ApiService _api = ApiService();
  final ScrollController _scroll = ScrollController();
  final List<Map<String, dynamic>> _items = [];
  int _page = 1;
  bool _hasMore = true;
  bool _loading = true;

  static const Map<String, Map<String, dynamic>> _typeMeta = {
    'coupon': {'text': '优惠券', 'color': Color(0xFFFA8C16), 'icon': '🎫'},
    'service': {'text': '体验服务', 'color': Color(0xFF13C2C2), 'icon': '💆'},
    'physical': {'text': '实物', 'color': Color(0xFF722ED1), 'icon': '📦'},
    'virtual': {'text': '虚拟', 'color': Color(0xFFBFBFBF), 'icon': '🎁'},
    'third_party': {'text': '第三方', 'color': Color(0xFFBFBFBF), 'icon': '🛍️'},
  };

  static const Map<String, Map<String, dynamic>> _statusMeta = {
    'success': {'text': '兑换成功', 'color': Color(0xFF52C41A)},
    'pending': {'text': '处理中', 'color': Color(0xFF1890FF)},
    'failed': {'text': '失败', 'color': Color(0xFFFF4D4F)},
    'used': {'text': '已使用', 'color': Color(0xFF8C8C8C)},
    'expired': {'text': '已过期', 'color': Color(0xFFBFBFBF)},
    'cancelled': {'text': '已取消', 'color': Color(0xFFBFBFBF)},
  };

  @override
  void initState() {
    super.initState();
    _load(reset: true);
    _scroll.addListener(() {
      if (_scroll.position.pixels >= _scroll.position.maxScrollExtent - 100 &&
          _hasMore && !_loading) {
        _load();
      }
    });
  }

  @override
  void dispose() {
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _load({bool reset = false}) async {
    if (reset) {
      _page = 1;
      _hasMore = true;
    }
    if (!_hasMore) return;
    setState(() => _loading = true);
    try {
      final res = await _api.getPointsExchangeRecords(page: _page, pageSize: 20);
      final data = res.data is Map ? res.data as Map<String, dynamic> : <String, dynamic>{};
      final items = data['items'];
      final list = <Map<String, dynamic>>[];
      if (items is List) {
        for (final e in items) {
          if (e is Map) list.add(Map<String, dynamic>.from(e));
        }
      }
      final total = int.tryParse('${data['total'] ?? 0}') ?? 0;
      setState(() {
        if (reset) _items.clear();
        _items.addAll(list);
        _page += 1;
        _hasMore = _items.length < total && list.isNotEmpty;
        _loading = false;
      });
    } catch (_) {
      setState(() {
        _loading = false;
        _hasMore = false;
      });
    }
  }

  String _fmt(String? iso) {
    if (iso == null || iso.isEmpty) return '';
    try {
      final d = DateTime.parse(iso).toLocal();
      final p = (int n) => n < 10 ? '0$n' : '$n';
      return '${d.year}-${p(d.month)}-${p(d.day)} ${p(d.hour)}:${p(d.minute)}';
    } catch (_) {
      return iso;
    }
  }

  void _goAppointment(Map<String, dynamic> r) {
    final stype = r['ref_service_type'];
    final sid = r['ref_service_id'];
    if (r['status'] == 'expired') {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('该服务券已过期')));
      return;
    }
    if (stype == null || sid == null) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('暂无预约入口')));
      return;
    }
    switch (stype) {
      case 'expert':
        Navigator.pushNamed(context, '/expert-detail', arguments: sid);
        break;
      case 'physical_exam':
      case 'tcm':
        Navigator.pushNamed(context, '/service-detail', arguments: sid);
        break;
      case 'health_plan':
        Navigator.pushNamed(context, '/health-plan');
        break;
      default:
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('暂无预约入口')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7F5),
      appBar: const CustomAppBar(title: '兑换记录'),
      body: RefreshIndicator(
        onRefresh: () => _load(reset: true),
        child: ListView(
          controller: _scroll,
          physics: const AlwaysScrollableScrollPhysics(),
          children: [
            Container(
              color: const Color(0xFFC8E6C9),
              padding: const EdgeInsets.fromLTRB(20, 16, 20, 16),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('我的兑换记录',
                      style: TextStyle(
                          color: Color(0xFF1B5E20),
                          fontSize: 15,
                          fontWeight: FontWeight.bold)),
                  SizedBox(height: 4),
                  Text('优惠券、体验服务、实物兑换均在此查看',
                      style: TextStyle(color: Color(0xFF2E7D32), fontSize: 12)),
                ],
              ),
            ),
            if (_loading && _items.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 60),
                child: Center(child: CircularProgressIndicator(color: Color(0xFF52C41A))),
              )
            else if (_items.isEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 80),
                child: Center(child: Text('暂无兑换记录', style: TextStyle(color: Colors.grey))),
              )
            else
              ..._items.map(_buildRow),
            if (!_hasMore && _items.isNotEmpty)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 24),
                child: Center(
                    child: Text('没有更多了', style: TextStyle(color: Colors.grey, fontSize: 12))),
              ),
          ],
        ),
      ),
    );
  }

  Widget _buildRow(Map<String, dynamic> r) {
    final type = '${r['goods_type'] ?? 'virtual'}';
    final meta = _typeMeta[type] ?? _typeMeta['virtual']!;
    final status = '${r['status'] ?? ''}';
    final sm = _statusMeta[status] ?? {'text': status, 'color': const Color(0xFF666666)};
    final cost = int.tryParse('${r['points_cost'] ?? 0}') ?? 0;
    final expireStr = _fmt(r['expire_at'] as String?);

    Widget? actionBtn;
    if (type == 'service' && status != 'expired') {
      actionBtn = ElevatedButton(
        onPressed: () => _goAppointment(r),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF52C41A),
          foregroundColor: Colors.white,
          minimumSize: const Size(64, 28),
          padding: const EdgeInsets.symmetric(horizontal: 10),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
        child: const Text('去预约', style: TextStyle(fontSize: 12)),
      );
    } else if (type == 'coupon') {
      // OPT-4：优惠券类型 → 拆为「查看券」+「去使用」两个按钮
      final rec = ExchangeRecord.fromJson(r);
      final viewBtn = OutlinedButton(
        onPressed: () => Navigator.pushNamed(
          context,
          '/my-coupons',
          arguments: {
            'tab': 'available',
            if (rec.couponId != null) 'highlightCouponId': rec.couponId,
          },
        ),
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFFFA8C16),
          side: const BorderSide(color: Color(0xFFFA8C16)),
          minimumSize: const Size(64, 28),
          padding: const EdgeInsets.symmetric(horizontal: 10),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
        child: const Text('查看券', style: TextStyle(fontSize: 12)),
      );
      final useBtn = ElevatedButton(
        onPressed: () => jumpToUseCoupon(context, rec.couponId),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFFFA8C16),
          foregroundColor: Colors.white,
          minimumSize: const Size(64, 28),
          padding: const EdgeInsets.symmetric(horizontal: 10),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
        child: const Text('去使用', style: TextStyle(fontSize: 12)),
      );
      actionBtn = Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          viewBtn,
          if (rec.couponStatus == 'available') ...[
            const SizedBox(width: 6),
            useBtn,
          ],
        ],
      );
    } else if (type == 'physical') {
      actionBtn = OutlinedButton(
        onPressed: () => Navigator.pushNamed(context, '/unified-orders'),
        style: OutlinedButton.styleFrom(
          foregroundColor: const Color(0xFF722ED1),
          side: const BorderSide(color: Color(0xFF722ED1)),
          minimumSize: const Size(64, 28),
          padding: const EdgeInsets.symmetric(horizontal: 10),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
        child: const Text('查看订单', style: TextStyle(fontSize: 12)),
      );
    }

    return Container(
      margin: const EdgeInsets.fromLTRB(12, 10, 12, 0),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(10),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            width: 48,
            height: 48,
            decoration: BoxDecoration(
              color: const Color(0xFFF5F5F5),
              borderRadius: BorderRadius.circular(8),
            ),
            alignment: Alignment.center,
            child: (r['goods_image'] is String && (r['goods_image'] as String).isNotEmpty)
                ? ClipRRect(
                    borderRadius: BorderRadius.circular(8),
                    child: Image.network(
                      r['goods_image'] as String,
                      width: 48,
                      height: 48,
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Text('${meta['icon']}',
                          style: const TextStyle(fontSize: 24)),
                    ),
                  )
                : Text('${meta['icon']}', style: const TextStyle(fontSize: 24)),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        color: (meta['color'] as Color).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text('${meta['text']}',
                          style: TextStyle(color: meta['color'] as Color, fontSize: 10)),
                    ),
                    const SizedBox(width: 6),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(
                        border: Border.all(color: sm['color'] as Color),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text('${sm['text']}',
                          style: TextStyle(color: sm['color'] as Color, fontSize: 10)),
                    ),
                  ],
                ),
                const SizedBox(height: 4),
                Text('${r['goods_name'] ?? ''}',
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis),
                Text('兑换时间：${_fmt(r['exchange_time'] as String?)}',
                    style: const TextStyle(fontSize: 12, color: Colors.grey)),
                if (expireStr.isNotEmpty)
                  Text('有效期至：$expireStr',
                      style: const TextStyle(fontSize: 12, color: Color(0xFFFA8C16))),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('-$cost 积分',
                        style: const TextStyle(
                            color: Color(0xFFB8860B), fontWeight: FontWeight.w600)),
                    if (actionBtn != null) actionBtn,
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
