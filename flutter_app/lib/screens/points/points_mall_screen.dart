import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

class PointsMallScreen extends StatefulWidget {
  const PointsMallScreen({super.key});

  @override
  State<PointsMallScreen> createState() => _PointsMallScreenState();
}

class _PointsMallScreenState extends State<PointsMallScreen> {
  final ApiService _apiService = ApiService();
  int _availablePoints = 0;
  bool _loading = true;
  List<Map<String, dynamic>> _goods = [];
  int? _exchangingId;

  static const Map<String, Map<String, dynamic>> _typeMeta = {
    'coupon': {'text': '优惠券', 'color': Color(0xFFFA8C16), 'icon': '🎫'},
    'service': {'text': '体验服务', 'color': Color(0xFF13C2C2), 'icon': '💆'},
    'physical': {'text': '实物', 'color': Color(0xFF722ED1), 'icon': '📦'},
    'virtual': {'text': '虚拟(开发中)', 'color': Color(0xFFBFBFBF), 'icon': '🎁'},
    'third_party': {'text': '第三方(开发中)', 'color': Color(0xFFBFBFBF), 'icon': '🛍️'},
  };

  static const _devTypes = {'virtual', 'third_party'};

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() => _loading = true);
    await Future.wait([_loadAvailablePoints(), _loadGoods()]);
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _loadAvailablePoints() async {
    try {
      final res = await _apiService.getPointsSummary();
      final summary = res.data is Map ? res.data as Map<String, dynamic> : <String, dynamic>{};
      final total = (summary['total_points'] is int)
          ? summary['total_points'] as int
          : int.tryParse('${summary['total_points'] ?? 0}') ?? 0;
      final avail = summary['available_points'] ?? summary['available'] ?? total;
      final n = (avail is int) ? avail : int.tryParse('$avail') ?? total;
      if (mounted) setState(() => _availablePoints = n);
    } catch (_) {}
  }

  Future<void> _loadGoods() async {
    try {
      final res = await _apiService.getPointsMallGoods(page: 1, pageSize: 50);
      final data = res.data is Map ? res.data as Map<String, dynamic> : <String, dynamic>{};
      final items = data['items'];
      final list = <Map<String, dynamic>>[];
      if (items is List) {
        for (final it in items) {
          if (it is Map) list.add(Map<String, dynamic>.from(it));
        }
      }
      if (mounted) setState(() => _goods = list);
    } catch (_) {
      if (mounted) setState(() => _goods = []);
    }
  }

  String _goodsType(Map<String, dynamic> item) {
    final t = item['type'];
    if (t is String) return t;
    if (t is Map && t['value'] != null) return '${t['value']}';
    return 'virtual';
  }

  Future<void> _doExchange(Map<String, dynamic> item) async {
    final type = _goodsType(item);
    if (_devTypes.contains(type)) {
      _toast('该类型商品正在开发中');
      return;
    }
    final cost = int.tryParse('${item['price_points'] ?? 0}') ?? 0;
    if (_availablePoints < cost) {
      _toast('积分不足');
      return;
    }

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('兑换确认'),
        content: Text(
          '确定使用 $cost 积分兑换「${item['name']}」？'
          '${type == 'service' ? '\n\n兑换后 30 天内有效，过期作废，积分不退。' : ''}',
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          ElevatedButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('确认兑换')),
        ],
      ),
    );
    if (confirm != true) return;

    setState(() => _exchangingId = item['id'] as int?);
    try {
      await _apiService.exchangePointsGoods(goodsId: item['id'] as int, quantity: 1);
      _toast('兑换成功');
      await _load();
    } catch (e) {
      final msg = e.toString().contains('detail') ? e.toString() : '兑换失败';
      _toast(msg);
    } finally {
      if (mounted) setState(() => _exchangingId = null);
    }
  }

  void _toast(String msg) {
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '积分商城'),
      body: Column(
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
            color: const Color(0xFFC8E6C9),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Text('可用积分',
                        style: TextStyle(fontSize: 13, color: Color(0xFF1B5E20))),
                    const SizedBox(height: 2),
                    Text('$_availablePoints',
                        style: const TextStyle(
                            fontSize: 26,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF1B5E20))),
                    const SizedBox(height: 2),
                    const Text('用积分兑换好礼',
                        style: TextStyle(fontSize: 12, color: Color(0xFF2E7D32))),
                  ],
                ),
                OutlinedButton(
                  onPressed: () => Navigator.pushNamed(context, '/points-exchange-records'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: const Color(0xFF1B5E20),
                    side: const BorderSide(color: Color(0x591B5E20)),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(18)),
                  ),
                  child: const Text('兑换记录'),
                ),
              ],
            ),
          ),
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
                : _goods.isEmpty
                    ? const Center(child: Text('暂无商品', style: TextStyle(color: Colors.grey)))
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: GridView.builder(
                          padding: const EdgeInsets.all(16),
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2,
                            childAspectRatio: 0.72,
                            crossAxisSpacing: 12,
                            mainAxisSpacing: 12,
                          ),
                          itemCount: _goods.length,
                          itemBuilder: (context, index) {
                            final item = _goods[index];
                            final type = _goodsType(item);
                            final meta = _typeMeta[type] ?? _typeMeta['virtual']!;
                            final cost = int.tryParse('${item['price_points'] ?? 0}') ?? 0;
                            final stock = int.tryParse('${item['stock'] ?? 0}') ?? 0;
                            final isDev = _devTypes.contains(type);
                            final enough = _availablePoints >= cost;
                            final disabled = isDev || !enough;
                            final images = item['images'];
                            String? img;
                            if (images is List && images.isNotEmpty) {
                              img = '${images.first}';
                            } else if (images is String) {
                              img = images;
                            }
                            return Container(
                              decoration: BoxDecoration(
                                color: Colors.white,
                                borderRadius: BorderRadius.circular(12),
                                boxShadow: [
                                  BoxShadow(
                                    color: Colors.black.withOpacity(0.04),
                                    blurRadius: 8,
                                    offset: const Offset(0, 2),
                                  ),
                                ],
                              ),
                              child: Stack(
                                children: [
                                  Column(
                                    children: [
                                      Expanded(
                                        flex: 3,
                                        child: Container(
                                          width: double.infinity,
                                          decoration: const BoxDecoration(
                                            color: Color(0xFFF0F9EB),
                                            borderRadius:
                                                BorderRadius.vertical(top: Radius.circular(12)),
                                          ),
                                          child: img != null
                                              ? ClipRRect(
                                                  borderRadius:
                                                      const BorderRadius.vertical(top: Radius.circular(12)),
                                                  child: Image.network(img,
                                                      fit: BoxFit.cover, errorBuilder: (_, __, ___) {
                                                    return Center(
                                                        child: Text('${meta['icon']}',
                                                            style: const TextStyle(fontSize: 42)));
                                                  }),
                                                )
                                              : Center(
                                                  child: Text('${meta['icon']}',
                                                      style: const TextStyle(fontSize: 42)),
                                                ),
                                        ),
                                      ),
                                      Expanded(
                                        flex: 3,
                                        child: Padding(
                                          padding: const EdgeInsets.all(10),
                                          child: Column(
                                            crossAxisAlignment: CrossAxisAlignment.start,
                                            children: [
                                              Container(
                                                padding: const EdgeInsets.symmetric(
                                                    horizontal: 6, vertical: 2),
                                                decoration: BoxDecoration(
                                                  color: (meta['color'] as Color).withOpacity(0.12),
                                                  borderRadius: BorderRadius.circular(8),
                                                ),
                                                child: Text(
                                                  '${meta['text']}',
                                                  style: TextStyle(
                                                      color: meta['color'] as Color, fontSize: 10),
                                                ),
                                              ),
                                              const SizedBox(height: 4),
                                              Text('${item['name'] ?? ''}',
                                                  style: const TextStyle(
                                                      fontSize: 13, fontWeight: FontWeight.w600),
                                                  maxLines: 2,
                                                  overflow: TextOverflow.ellipsis),
                                              const Spacer(),
                                              Row(
                                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                                children: [
                                                  Text('$cost积分',
                                                      style: const TextStyle(
                                                          fontSize: 14,
                                                          fontWeight: FontWeight.bold,
                                                          color: Color(0xFFB8860B))),
                                                  Text(type == 'service' ? '服务券' : '库存$stock',
                                                      style: TextStyle(
                                                          fontSize: 11, color: Colors.grey[400])),
                                                ],
                                              ),
                                              const SizedBox(height: 6),
                                              SizedBox(
                                                width: double.infinity,
                                                height: 28,
                                                child: ElevatedButton(
                                                  onPressed: disabled || _exchangingId == item['id']
                                                      ? null
                                                      : () => _doExchange(item),
                                                  style: ElevatedButton.styleFrom(
                                                    backgroundColor: const Color(0xFF52C41A),
                                                    foregroundColor: Colors.white,
                                                    disabledBackgroundColor: const Color(0xFFE8E8E8),
                                                    padding: EdgeInsets.zero,
                                                    textStyle: const TextStyle(fontSize: 12),
                                                    shape: RoundedRectangleBorder(
                                                        borderRadius: BorderRadius.circular(14)),
                                                  ),
                                                  child: Text(
                                                    _exchangingId == item['id']
                                                        ? '...'
                                                        : isDev
                                                            ? '开发中'
                                                            : enough
                                                                ? '立即兑换'
                                                                : '积分不足',
                                                  ),
                                                ),
                                              ),
                                            ],
                                          ),
                                        ),
                                      ),
                                    ],
                                  ),
                                  if (isDev)
                                    Positioned.fill(
                                      child: Container(
                                        decoration: BoxDecoration(
                                          color: Colors.white.withOpacity(0.7),
                                          borderRadius: BorderRadius.circular(12),
                                        ),
                                        alignment: Alignment.center,
                                        child: const Text(
                                          '开发中',
                                          style: TextStyle(
                                              color: Colors.grey, fontWeight: FontWeight.bold),
                                        ),
                                      ),
                                    ),
                                ],
                              ),
                            );
                          },
                        ),
                      ),
          ),
        ],
      ),
    );
  }
}
