// PRD F4：积分商品详情页
// 路由：/points-product-detail  arguments: int id
import 'package:flutter/material.dart';
import '../../services/api_service.dart';

/// 轻量 HTML → 纯文本降级工具：剥离标签并把常见块级标签替换为换行。
/// Flutter 端富文本暂不引入第三方包，先用纯文本显示保证信息可见。
String _htmlToPlainText(String html) {
  var s = html;
  s = s.replaceAll(RegExp(r'</(p|div|h[1-6]|li|br)>', caseSensitive: false), '\n');
  s = s.replaceAll(RegExp(r'<br\s*/?>', caseSensitive: false), '\n');
  s = s.replaceAll(RegExp(r'<[^>]+>'), '');
  s = s.replaceAll('&nbsp;', ' ').replaceAll('&amp;', '&')
       .replaceAll('&lt;', '<').replaceAll('&gt;', '>');
  return s.trim();
}

class PointsProductDetailScreen extends StatefulWidget {
  const PointsProductDetailScreen({super.key});

  @override
  State<PointsProductDetailScreen> createState() => _PointsProductDetailScreenState();
}

class _PointsProductDetailScreenState extends State<PointsProductDetailScreen> {
  final ApiService _api = ApiService();
  int? _id;
  Map<String, dynamic>? _item;
  bool _loading = true;
  bool _exchanging = false;
  final PageController _pageCtrl = PageController();
  int _currentPage = 0;

  static const Map<String, Map<String, dynamic>> _typeMeta = {
    'coupon': {'text': '优惠券', 'color': Color(0xFFFA8C16), 'icon': '🎫'},
    'service': {'text': '体验服务', 'color': Color(0xFF13C2C2), 'icon': '💆'},
    'physical': {'text': '实物', 'color': Color(0xFF722ED1), 'icon': '📦'},
    'virtual': {'text': '虚拟', 'color': Color(0xFFBFBFBF), 'icon': '🎁'},
    'third_party': {'text': '第三方', 'color': Color(0xFFBFBFBF), 'icon': '🛍️'},
  };

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_id == null) {
      final args = ModalRoute.of(context)?.settings.arguments;
      int? id;
      if (args is int) id = args;
      if (args is String) id = int.tryParse(args);
      if (args is Map && args['id'] != null) id = int.tryParse('${args['id']}');
      _id = id;
      if (id != null) _load();
      else setState(() => _loading = false);
    }
  }

  @override
  void dispose() {
    _pageCtrl.dispose();
    super.dispose();
  }

  Future<void> _load() async {
    if (_id == null) return;
    setState(() => _loading = true);
    try {
      final res = await _api.getPointsMallProductDetail(_id!);
      final data = res.data is Map ? Map<String, dynamic>.from(res.data as Map) : <String, dynamic>{};
      setState(() {
        _item = data;
        _loading = false;
      });
    } catch (e) {
      final msg = _extractDetail(e) ?? '加载失败';
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
        setState(() {
          _item = null;
          _loading = false;
        });
      }
    }
  }

  String? _extractDetail(dynamic e) {
    try {
      final s = e.toString();
      final rep = e is dynamic ? (e as dynamic).response : null;
      if (rep != null && rep.data is Map && rep.data['detail'] != null) {
        return '${rep.data['detail']}';
      }
      return s;
    } catch (_) {
      return null;
    }
  }

  Future<void> _handleExchange() async {
    if (_item == null) return;
    final state = '${_item!['button_state'] ?? 'exchangeable'}';
    if (state != 'exchangeable') return;
    final cost = int.tryParse('${_item!['price_points'] ?? 0}') ?? 0;
    final type = '${_item!['type']}';
    final name = '${_item!['name']}';
    final extra = type == 'service' ? '\n\n⚠️ 兑换后 30 天内有效，过期作废，积分不退。' : '';

    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('兑换确认'),
        content: Text('确认用 $cost 积分兑换【$name】吗？$extra'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('取消')),
          ElevatedButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF4CAF50)),
            child: const Text('确认兑换', style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
    if (confirm != true) return;

    setState(() => _exchanging = true);
    try {
      await _api.exchangePointsGoods(goodsId: _id!, quantity: 1);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('兑换成功'), backgroundColor: Color(0xFF4CAF50)),
      );
      Future.delayed(const Duration(milliseconds: 600), () {
        if (mounted) {
          Navigator.pushReplacementNamed(
            context,
            '/points-detail',
            arguments: const {'tab': 'exchange'},
          );
        }
      });
    } catch (e) {
      final msg = _extractDetail(e) ?? '兑换失败';
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(msg)));
    } finally {
      if (mounted) setState(() => _exchanging = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F5),
      appBar: AppBar(
        title: const Text('商品详情'),
        backgroundColor: const Color(0xFF4CAF50),
        foregroundColor: Colors.white,
        iconTheme: const IconThemeData(color: Colors.white),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF4CAF50)))
          : _item == null
              ? const Center(child: Text('商品不存在或已下架', style: TextStyle(color: Colors.grey)))
              : _buildContent(),
      bottomNavigationBar: _item == null ? null : _buildBottomBar(),
    );
  }

  Widget _buildContent() {
    final item = _item!;
    final type = '${item['type']}';
    final meta = _typeMeta[type] ?? _typeMeta['virtual']!;
    final images = item['images'];
    final imgList = <String>[];
    if (images is List) {
      for (final i in images) {
        if (i is String && i.isNotEmpty) imgList.add(i);
      }
    }
    final cost = int.tryParse('${item['price_points'] ?? 0}') ?? 0;
    final stock = int.tryParse('${item['stock'] ?? 0}') ?? 0;
    final limit = int.tryParse('${item['limit_per_user'] ?? 0}') ?? 0;
    final usedCnt = int.tryParse('${item['user_exchanged_count'] ?? 0}') ?? 0;
    final detailHtml = item['detail_html']?.toString() ?? '';
    final desc = item['description']?.toString() ?? '';

    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 图片轮播
          Container(
            height: 280,
            color: Colors.white,
            child: imgList.isEmpty
                ? Center(child: Text('${meta['icon']}', style: const TextStyle(fontSize: 80)))
                : Stack(
                    children: [
                      PageView.builder(
                        controller: _pageCtrl,
                        itemCount: imgList.length,
                        onPageChanged: (i) => setState(() => _currentPage = i),
                        itemBuilder: (_, i) => Container(
                          color: const Color(0xFFF5F5F5),
                          child: Image.network(
                            imgList[i],
                            fit: BoxFit.contain,
                            errorBuilder: (_, __, ___) => Center(
                              child: Text('${meta['icon']}', style: const TextStyle(fontSize: 80)),
                            ),
                          ),
                        ),
                      ),
                      if (imgList.length > 1)
                        Positioned(
                          bottom: 12,
                          left: 0,
                          right: 0,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: List.generate(imgList.length, (i) {
                              final active = i == _currentPage;
                              return Container(
                                margin: const EdgeInsets.symmetric(horizontal: 3),
                                width: active ? 16 : 6,
                                height: 6,
                                decoration: BoxDecoration(
                                  color: active ? const Color(0xFF4CAF50) : Colors.white,
                                  borderRadius: BorderRadius.circular(3),
                                ),
                              );
                            }),
                          ),
                        ),
                    ],
                  ),
          ),
          // 基本信息
          Container(
            width: double.infinity,
            color: Colors.white,
            margin: const EdgeInsets.only(top: 8),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: (meta['color'] as Color).withOpacity(0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        '${meta['text']}',
                        style: TextStyle(color: meta['color'] as Color, fontSize: 11),
                      ),
                    ),
                    if (item['status'] != 'active') ...[
                      const SizedBox(width: 6),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          border: Border.all(color: Colors.grey.shade400),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text('已下架',
                            style: TextStyle(color: Colors.grey, fontSize: 11)),
                      ),
                    ],
                  ],
                ),
                const SizedBox(height: 10),
                Text('${item['name'] ?? ''}',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                const SizedBox(height: 12),
                Row(
                  crossAxisAlignment: CrossAxisAlignment.baseline,
                  textBaseline: TextBaseline.alphabetic,
                  children: [
                    Text('$cost',
                        style: const TextStyle(
                            fontSize: 26,
                            fontWeight: FontWeight.bold,
                            color: Color(0xFF2E7D32))),
                    const SizedBox(width: 4),
                    const Text('积分',
                        style: TextStyle(fontSize: 13, color: Color(0xFF2E7D32))),
                    const Spacer(),
                    Text(
                      type == 'service' ? '服务券' : (stock > 0 ? '剩余库存 $stock' : '已兑完'),
                      style: const TextStyle(fontSize: 12, color: Colors.grey),
                    ),
                  ],
                ),
                if (limit > 0)
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: Text(
                      '每人限兑 $limit 次（已兑 $usedCnt 次）',
                      style: const TextStyle(color: Colors.grey, fontSize: 12),
                    ),
                  ),
              ],
            ),
          ),
          // 详情
          Container(
            width: double.infinity,
            color: Colors.white,
            margin: const EdgeInsets.only(top: 8),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('商品详情',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Text(
                  detailHtml.isNotEmpty
                      ? _htmlToPlainText(detailHtml)
                      : (desc.isEmpty ? '暂无详情' : desc),
                  style: const TextStyle(fontSize: 14, color: Color(0xFF333333), height: 1.7),
                ),
              ],
            ),
          ),
          // 使用须知
          Container(
            width: double.infinity,
            color: Colors.white,
            margin: const EdgeInsets.only(top: 8),
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('使用须知',
                    style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                if (type == 'service')
                  const Text('• 兑换后 30 天内有效，过期作废',
                      style: TextStyle(fontSize: 13, color: Color(0xFF666666), height: 1.8)),
                if (type == 'coupon')
                  const Text('• 券码将发放至「我的卡券」，请在有效期内使用',
                      style: TextStyle(fontSize: 13, color: Color(0xFF666666), height: 1.8)),
                if (type == 'physical')
                  const Text('• 实物商品需填写收货地址，由工作人员安排发货',
                      style: TextStyle(fontSize: 13, color: Color(0xFF666666), height: 1.8)),
                const Text('• 兑换后积分即时扣除，一经兑换不予退还',
                    style: TextStyle(fontSize: 13, color: Color(0xFF666666), height: 1.8)),
                if (limit > 0)
                  Text('• 每人限兑 $limit 次',
                      style: const TextStyle(fontSize: 13, color: Color(0xFF666666), height: 1.8)),
              ],
            ),
          ),
          const SizedBox(height: 80),
        ],
      ),
    );
  }

  Widget _buildBottomBar() {
    final item = _item!;
    final state = '${item['button_state'] ?? 'exchangeable'}';
    final text = '${item['button_text'] ?? '立即兑换'}';
    final disabled = state != 'exchangeable' || _exchanging;

    return SafeArea(
      top: false,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        decoration: const BoxDecoration(
          color: Colors.white,
          border: Border(top: BorderSide(color: Color(0xFFEEEEEE), width: 1)),
        ),
        child: SizedBox(
          height: 48,
          child: ElevatedButton(
            onPressed: disabled ? null : _handleExchange,
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF4CAF50),
              foregroundColor: Colors.white,
              disabledBackgroundColor: const Color(0xFFE0E0E0),
              disabledForegroundColor: const Color(0xFF999999),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
              textStyle: const TextStyle(fontSize: 16),
            ),
            child: _exchanging
                ? const SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white),
                  )
                : Text(text),
          ),
        ),
      ),
    );
  }
}
