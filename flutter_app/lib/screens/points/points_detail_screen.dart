// PRD F3：积分明细聚合页 — 合并原"积分详情 + 兑换记录"入口，使用两 Tab
// 默认激活"积分明细"；支持路由参数 tab='exchange' 直接激活"兑换记录"

import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import 'exchange_records_screen.dart' show ExchangeRecord, jumpToUseCoupon;

class PointsDetailScreen extends StatefulWidget {
  const PointsDetailScreen({super.key});

  @override
  State<PointsDetailScreen> createState() => _PointsDetailScreenState();
}

class _PointsDetailScreenState extends State<PointsDetailScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final args = ModalRoute.of(context)?.settings.arguments;
    if (args is Map && args['tab'] == 'exchange') {
      _tabController.index = 1;
    }
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F5),
      appBar: AppBar(
        title: const Text('积分明细'),
        backgroundColor: const Color(0xFF4CAF50),
        foregroundColor: Colors.white,
        iconTheme: const IconThemeData(color: Colors.white),
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          tabs: const [
            Tab(text: '积分明细'),
            Tab(text: '兑换记录'),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: const [
          _PointsRecordsTab(),
          _ExchangeRecordsTab(),
        ],
      ),
    );
  }
}

// ─────── Tab 1：积分明细 ───────
class _PointsRecordsTab extends StatefulWidget {
  const _PointsRecordsTab();

  @override
  State<_PointsRecordsTab> createState() => _PointsRecordsTabState();
}

class _PointsRecordsTabState extends State<_PointsRecordsTab> {
  final ApiService _api = ApiService();
  final ScrollController _scrollCtrl = ScrollController();
  final List<Map<String, dynamic>> _records = [];
  int _page = 1;
  bool _loading = false;
  bool _noMore = false;

  static const _typeLabel = {
    'signin': '每日签到',
    'checkin': '健康打卡',
    'completeProfile': '完善档案',
    'invite': '邀请奖励',
    'firstOrder': '首次下单',
    'reviewService': '订单评价',
    'exchange': '积分兑换',
    'consume': '积分消费',
    'redeem': '积分兑换',
    'task': '任务奖励',
    'purchase': '购物奖励',
  };

  @override
  void initState() {
    super.initState();
    _loadMore();
    _scrollCtrl.addListener(() {
      if (_scrollCtrl.position.pixels >= _scrollCtrl.position.maxScrollExtent - 80) {
        _loadMore();
      }
    });
  }

  @override
  void dispose() {
    _scrollCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadMore() async {
    if (_loading || _noMore) return;
    setState(() => _loading = true);
    try {
      final res = await _api.getPointsRecords(page: _page);
      final data = res.data is Map ? res.data as Map : {};
      final items = (data['items'] ?? data['records'] ?? []) as List;
      setState(() {
        _records.addAll(items.map((e) => Map<String, dynamic>.from(e as Map)));
        _page++;
        _noMore = items.length < 20;
      });
    } catch (_) {
      setState(() => _noMore = true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_records.isEmpty && !_loading) {
      return const Center(child: Text('暂无积分记录', style: TextStyle(color: Colors.grey)));
    }
    return ListView.builder(
      controller: _scrollCtrl,
      itemCount: _records.length + 1,
      itemBuilder: (context, index) {
        if (index == _records.length) {
          if (_loading) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator(color: Color(0xFF4CAF50))),
            );
          }
          if (_noMore && _records.isNotEmpty) {
            return const Padding(
              padding: EdgeInsets.all(16),
              child: Center(
                child: Text('— 没有更多了 —', style: TextStyle(color: Colors.grey, fontSize: 12)),
              ),
            );
          }
          return const SizedBox.shrink();
        }
        final r = _records[index];
        final pts = r['points'] ?? 0;
        final isIncome = pts >= 0;
        final type = r['type']?.toString() ?? '';
        final label = _typeLabel[type] ?? type;
        final time = (r['created_at']?.toString() ?? '').replaceAll('T', ' ');
        return Container(
          margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Row(
            children: [
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(r['description']?.toString() ?? label, style: const TextStyle(fontSize: 14)),
                    const SizedBox(height: 4),
                    Text(
                      time.length >= 19 ? time.substring(0, 19) : time,
                      style: const TextStyle(fontSize: 11, color: Colors.grey),
                    ),
                  ],
                ),
              ),
              Text(
                '${isIncome ? '+' : ''}$pts',
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                  color: isIncome ? const Color(0xFF4CAF50) : const Color(0xFFF44336),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}

// ─────── Tab 2：兑换记录 ───────
class _ExchangeRecordsTab extends StatefulWidget {
  const _ExchangeRecordsTab();

  @override
  State<_ExchangeRecordsTab> createState() => _ExchangeRecordsTabState();
}

class _ExchangeRecordsTabState extends State<_ExchangeRecordsTab> {
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

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () => _load(reset: true),
      child: ListView(
        controller: _scroll,
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          if (_loading && _items.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 60),
              child: Center(child: CircularProgressIndicator(color: Color(0xFF4CAF50))),
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
                child: Text('没有更多了', style: TextStyle(color: Colors.grey, fontSize: 12)),
              ),
            ),
        ],
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
    final refServiceId = r['ref_service_id'];

    Widget? actionBtn;
    if (type == 'service' && status != 'expired' && refServiceId != null) {
      actionBtn = ElevatedButton(
        onPressed: () => Navigator.pushNamed(context, '/product-detail', arguments: refServiceId),
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF4CAF50),
          foregroundColor: Colors.white,
          minimumSize: const Size(64, 28),
          padding: const EdgeInsets.symmetric(horizontal: 10),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
        ),
        child: const Text('去使用', style: TextStyle(fontSize: 12)),
      );
    } else if (type == 'coupon') {
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
                      errorBuilder: (_, __, ___) =>
                          Text('${meta['icon']}', style: const TextStyle(fontSize: 24)),
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
                Text(
                  '${r['goods_name'] ?? ''}',
                  style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
                Text(
                  '兑换时间：${_fmt(r['exchange_time'] as String?)}',
                  style: const TextStyle(fontSize: 12, color: Colors.grey),
                ),
                if (expireStr.isNotEmpty)
                  Text('有效期至：$expireStr',
                      style: const TextStyle(fontSize: 12, color: Color(0xFFFA8C16))),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      '-$cost 积分',
                      style: const TextStyle(color: Color(0xFFF44336), fontWeight: FontWeight.w600),
                    ),
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
