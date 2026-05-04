// PRD F4：积分商城列表页 — 卡片整体可点进入详情页，底部"立即兑换"按钮按后端 canRedeem 置灰
import 'package:flutter/material.dart';
import '../../services/api_service.dart';

/// BUG-2：商城列表项 model
/// 后端返回字段为 snake_case：can_redeem / redeem_block_reason / shortage_text
/// 这里在 fromJson 中转换为 camelCase。
class PointsMallItem {
  final int id;
  final String name;
  final String type;
  final int pricePoints;
  final int stock;
  final List<String> images;
  final bool canRedeem;
  final String? redeemBlockReason;
  final String? shortageText;
  final Map<String, dynamic> raw;

  PointsMallItem({
    required this.id,
    required this.name,
    required this.type,
    required this.pricePoints,
    required this.stock,
    required this.images,
    required this.canRedeem,
    this.redeemBlockReason,
    this.shortageText,
    required this.raw,
  });

  factory PointsMallItem.fromJson(Map<String, dynamic> json) {
    final imgs = <String>[];
    final rawImgs = json['images'];
    if (rawImgs is List) {
      for (final i in rawImgs) {
        if (i != null) imgs.add('$i');
      }
    } else if (rawImgs is String && rawImgs.isNotEmpty) {
      imgs.add(rawImgs);
    }
    final t = json['type'];
    final type = (t is String)
        ? t
        : (t is Map && t['value'] != null ? '${t['value']}' : 'virtual');
    // 兼容后端未下发 can_redeem 时，按 stock>0 推断（旧数据兜底）
    final hasFlag = json.containsKey('can_redeem');
    final stock = int.tryParse('${json['stock'] ?? 0}') ?? 0;
    final canRedeem = hasFlag ? (json['can_redeem'] == true) : (stock > 0);
    return PointsMallItem(
      id: json['id'] is int ? json['id'] as int : int.tryParse('${json['id']}') ?? 0,
      name: '${json['name'] ?? ''}',
      type: type,
      pricePoints: int.tryParse('${json['price_points'] ?? 0}') ?? 0,
      stock: stock,
      images: imgs,
      canRedeem: canRedeem,
      redeemBlockReason: json['redeem_block_reason']?.toString(),
      shortageText: json['shortage_text']?.toString(),
      raw: Map<String, dynamic>.from(json),
    );
  }
}

class PointsMallScreen extends StatefulWidget {
  const PointsMallScreen({super.key});

  @override
  State<PointsMallScreen> createState() => _PointsMallScreenState();
}

class _PointsMallScreenState extends State<PointsMallScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();
  int _availablePoints = 0;
  bool _loading = true;
  List<PointsMallItem> _goods = [];
  late TabController _tabController;
  String _currentTab = 'all';

  static const Map<String, Map<String, dynamic>> _typeMeta = {
    'coupon': {'text': '优惠券', 'color': Color(0xFFFA8C16), 'icon': '🎫'},
    'service': {'text': '体验服务', 'color': Color(0xFF13C2C2), 'icon': '💆'},
    'physical': {'text': '实物', 'color': Color(0xFF722ED1), 'icon': '📦'},
    'virtual': {'text': '虚拟', 'color': Color(0xFFBFBFBF), 'icon': '🎁'},
    'third_party': {'text': '第三方', 'color': Color(0xFFBFBFBF), 'icon': '🛍️'},
  };

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _tabController.addListener(_onTabChanged);
    _load();
  }

  @override
  void dispose() {
    _tabController.removeListener(_onTabChanged);
    _tabController.dispose();
    super.dispose();
  }

  void _onTabChanged() {
    if (_tabController.indexIsChanging) return;
    final newTab = _tabController.index == 0 ? 'all' : 'exchangeable';
    if (newTab != _currentTab) {
      setState(() => _currentTab = newTab);
      _loadGoods();
    }
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
      final res = await _apiService.getPointsMallGoods(
        page: 1,
        pageSize: 50,
        tab: _currentTab,
      );
      final data = res.data is Map ? res.data as Map<String, dynamic> : <String, dynamic>{};
      final items = data['items'];
      final list = <PointsMallItem>[];
      if (items is List) {
        for (final it in items) {
          if (it is Map) {
            list.add(PointsMallItem.fromJson(Map<String, dynamic>.from(it)));
          }
        }
      }
      if (mounted) setState(() => _goods = list);
    } catch (_) {
      if (mounted) setState(() => _goods = []);
    }
  }

  void _openDetail(PointsMallItem item) {
    Navigator.pushNamed(context, '/points-product-detail', arguments: item.id);
  }

  /// BUG-2：根据 redeemBlockReason 取按钮文案
  String _blockedButtonText(PointsMallItem item) {
    switch (item.redeemBlockReason) {
      case 'OFF_SHELF':
        return '已下架';
      case 'NOT_STARTED':
        return '未开始';
      case 'ENDED':
        return '已结束';
      case 'SOLD_OUT':
        return '已兑完';
      case 'LIMIT_REACHED':
        return '已达上限';
      case 'INSUFFICIENT_POINTS':
        return (item.shortageText != null && item.shortageText!.isNotEmpty)
            ? item.shortageText!
            : '积分不足';
      default:
        return '不可兑换';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text(
          '积分商城',
          style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.w600),
        ),
        centerTitle: true,
        backgroundColor: const Color(0xFF4CAF50),
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, color: Colors.white, size: 20),
          onPressed: () => Navigator.of(context).pop(),
        ),
        automaticallyImplyLeading: false,
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          labelColor: Colors.white,
          unselectedLabelColor: Colors.white70,
          tabs: const [
            Tab(text: '全部'),
            Tab(text: '可兑换'),
          ],
        ),
      ),
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
                  onPressed: () => Navigator.pushNamed(
                    context,
                    '/points-detail',
                    arguments: const {'tab': 'exchange'},
                  ),
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
                ? const Center(child: CircularProgressIndicator(color: Color(0xFF4CAF50)))
                : _goods.isEmpty
                    ? const Center(child: Text('暂无商品', style: TextStyle(color: Colors.grey)))
                    : RefreshIndicator(
                        onRefresh: _load,
                        child: GridView.builder(
                          padding: const EdgeInsets.all(16),
                          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                            crossAxisCount: 2,
                            childAspectRatio: 0.62,
                            crossAxisSpacing: 12,
                            mainAxisSpacing: 12,
                          ),
                          itemCount: _goods.length,
                          itemBuilder: (context, index) => _buildCard(_goods[index]),
                        ),
                      ),
          ),
        ],
      ),
    );
  }

  Widget _buildCard(PointsMallItem item) {
    final meta = _typeMeta[item.type] ?? _typeMeta['virtual']!;
    final img = item.images.isNotEmpty ? item.images.first : null;

    final btnText = item.canRedeem ? '立即兑换' : _blockedButtonText(item);
    final Widget redeemBtn = SizedBox(
      width: double.infinity,
      height: 32,
      child: item.canRedeem
          ? ElevatedButton(
              onPressed: () => _openDetail(item),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFF52C41A),
                foregroundColor: Colors.white,
                padding: EdgeInsets.zero,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
              child: Text(btnText, style: const TextStyle(fontSize: 12)),
            )
          // BUG-2：灰按钮仍可点击，跳详情页让用户看到完整不可兑换原因
          : ElevatedButton(
              onPressed: () => _openDetail(item),
              style: ElevatedButton.styleFrom(
                backgroundColor: const Color(0xFFE0E0E0),
                foregroundColor: const Color(0xFF999999),
                padding: EdgeInsets.zero,
                elevation: 0,
                shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
              ),
              child: Text(btnText, style: const TextStyle(fontSize: 12)),
            ),
    );

    return InkWell(
      onTap: () => _openDetail(item),
      borderRadius: BorderRadius.circular(12),
      child: Container(
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
        child: Column(
          children: [
            Expanded(
              flex: 4,
              child: Container(
                width: double.infinity,
                decoration: const BoxDecoration(
                  color: Color(0xFFF0F9EB),
                  borderRadius: BorderRadius.vertical(top: Radius.circular(12)),
                ),
                child: img != null
                    ? ClipRRect(
                        borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
                        child: Image.network(
                          img,
                          fit: BoxFit.cover,
                          errorBuilder: (_, __, ___) => Center(
                            child: Text('${meta['icon']}', style: const TextStyle(fontSize: 42)),
                          ),
                        ),
                      )
                    : Center(
                        child: Text('${meta['icon']}', style: const TextStyle(fontSize: 42)),
                      ),
              ),
            ),
            Expanded(
              flex: 5,
              child: Padding(
                padding: const EdgeInsets.all(10),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: (meta['color'] as Color).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        '${meta['text']}',
                        style: TextStyle(color: meta['color'] as Color, fontSize: 10),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      item.name,
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    const Spacer(),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          '${item.pricePoints}积分',
                          style: const TextStyle(
                              fontSize: 14,
                              fontWeight: FontWeight.bold,
                              color: Color(0xFF2E7D32)),
                        ),
                        Text(
                          item.type == 'service' ? '服务券' : '库存${item.stock}',
                          style: TextStyle(fontSize: 11, color: Colors.grey[400]),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    redeemBtn,
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
