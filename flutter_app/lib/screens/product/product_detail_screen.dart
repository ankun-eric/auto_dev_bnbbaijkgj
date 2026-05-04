import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:geolocator/geolocator.dart';
import '../../models/product.dart';
import '../../services/api_service.dart';
import '../../utils/price_formatter.dart';
import '../../utils/map_nav_util.dart';

class ProductDetailScreen extends StatefulWidget {
  const ProductDetailScreen({super.key});

  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  final ApiService _api = ApiService();
  Product? _product;
  bool _loading = true;
  bool _isFavorited = false;
  int _quantity = 1;
  int _currentImageIndex = 0;

  List<Map<String, dynamic>> _slotAvailability = [];
  List<Map<String, dynamic>> _availableStores = [];
  int _selectedStoreIdx = 0;
  String _storesSortBy = 'name';
  bool _loadingStores = false;
  // OPT-1：带券进入详情时透传到下单页的 couponId
  int? _initialCouponId;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_product == null) {
      final args = ModalRoute.of(context)!.settings.arguments;
      int productId;
      if (args is int) {
        productId = args;
      } else if (args is Map) {
        final id = args['id'];
        productId = id is int ? id : int.tryParse('$id') ?? 0;
        final cid = args['couponId'];
        if (cid is int) {
          _initialCouponId = cid;
        } else if (cid != null) {
          _initialCouponId = int.tryParse('$cid');
        }
      } else {
        productId = int.tryParse('$args') ?? 0;
      }
      _loadProduct(productId);
    }
  }

  Future<void> _loadProduct(int id) async {
    try {
      final res = await _api.getProductDetail(id);
      if (res.data is Map) {
        setState(() {
          _product = Product.fromJson(res.data as Map<String, dynamic>);
          _loading = false;
        });
      }
      // 收藏状态回显
      try {
        final favRes = await _api.getFavoriteStatus(id, 'product');
        if (favRes.data is Map && mounted) {
          setState(() => _isFavorited = favRes.data['is_favorited'] == true);
        }
      } catch (_) { /* 未登录或失败时静默 */ }

      if (mounted && _product != null) {
        _loadSlotAvailability();
        _loadAvailableStores();
      }
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('加载失败')));
      }
    }
  }

  String _formatToday() {
    final now = DateTime.now();
    return '${now.year}-${now.month.toString().padLeft(2, '0')}-${now.day.toString().padLeft(2, '0')}';
  }

  Future<void> _loadSlotAvailability() async {
    final p = _product;
    if (p == null) return;
    if (p.appointmentMode == 'none') return;
    if (p.timeSlots == null || p.timeSlots!.isEmpty) return;
    try {
      final today = _formatToday();
      final res = await ApiService().getProductTimeSlotsAvailability(p.id, today);
      if (res.data is Map && res.data['data'] is Map) {
        final slots = res.data['data']['slots'];
        if (slots is List) {
          setState(() {
            _slotAvailability = slots.map((e) => Map<String, dynamic>.from(e as Map)).toList();
          });
        }
      }
    } catch (_) {
      setState(() => _slotAvailability = []);
    }
  }

  bool _isSlotExpired(String slotEnd) {
    final now = DateTime.now();
    final parts = slotEnd.split(':');
    if (parts.length < 2) return false;
    final endH = int.tryParse(parts[0]) ?? 0;
    final endM = int.tryParse(parts[1]) ?? 0;
    return (endH * 60 + endM) <= (now.hour * 60 + now.minute);
  }

  bool _isSlotFullyBooked(String label) {
    final hit = _slotAvailability.where((s) =>
      '${s['start_time']}-${s['end_time']}' == label
    ).toList();
    if (hit.isEmpty) return false;
    return ((hit.first['available'] ?? 1) as num) <= 0;
  }

  Future<void> _loadAvailableStores() async {
    final p = _product;
    if (p == null) return;
    setState(() => _loadingStores = true);

    double? lat;
    double? lng;
    try {
      LocationPermission perm = await Geolocator.checkPermission();
      if (perm == LocationPermission.denied) {
        perm = await Geolocator.requestPermission();
      }
      if (perm == LocationPermission.always || perm == LocationPermission.whileInUse) {
        final pos = await Geolocator.getCurrentPosition(
          desiredAccuracy: LocationAccuracy.medium,
          timeLimit: const Duration(seconds: 6),
        ).timeout(const Duration(seconds: 8), onTimeout: () => throw Exception('timeout'));
        lat = pos.latitude;
        lng = pos.longitude;
      }
    } catch (_) {
      // 定位失败：保持 lat/lng 为 null，后端按字母兜底
    }

    try {
      final res = await ApiService().getProductAvailableStores(p.id, lat: lat, lng: lng);
      if (res.data is Map && res.data['data'] is Map) {
        final data = res.data['data'];
        final stores = data['stores'];
        if (stores is List) {
          setState(() {
            _availableStores = stores.map((e) => Map<String, dynamic>.from(e as Map)).toList();
            _selectedStoreIdx = 0;
            _storesSortBy = (data['sort_by'] ?? 'name').toString();
          });
        }
      }
    } catch (_) {
      setState(() => _availableStores = []);
    } finally {
      if (mounted) setState(() => _loadingStores = false);
    }
  }

  void _showStoreDrawer() {
    if (_availableStores.length <= 1) return;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) {
        return SafeArea(
          child: Container(
            constraints: BoxConstraints(maxHeight: MediaQuery.of(context).size.height * 0.7),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 16),
                  child: Text('选择门店', style: TextStyle(fontWeight: FontWeight.w500, fontSize: 16)),
                ),
                const Divider(height: 1),
                Flexible(
                  child: ListView.separated(
                    shrinkWrap: true,
                    itemCount: _availableStores.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (_, idx) {
                      final s = _availableStores[idx];
                      final dist = s['distance_km'];
                      return ListTile(
                        title: Text(s['name'] ?? ''),
                        subtitle: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            if (s['address'] != null) Text(s['address'].toString(), style: const TextStyle(color: Color(0xFF999999), fontSize: 12)),
                            if (dist != null) Text('距您 $dist km', style: const TextStyle(color: Color(0xFF52C41A), fontSize: 12)),
                          ],
                        ),
                        trailing: idx == _selectedStoreIdx
                            ? const Icon(Icons.check, color: Color(0xFF52C41A))
                            : null,
                        onTap: () {
                          setState(() => _selectedStoreIdx = idx);
                          Navigator.pop(ctx);
                        },
                      );
                    },
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _toggleFavorite() async {
    if (_product == null) return;
    try {
      final res = await _api.toggleFavorite(_product!.id, 'product');
      if (res.data is Map) {
        setState(() => _isFavorited = res.data['is_favorited'] == true);
        if (mounted) {
          final msg = _isFavorited ? '收藏成功，可在「我的-收藏」中查看' : '已取消收藏';
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text(msg), duration: const Duration(seconds: 2)),
          );
        }
      }
    } catch (_) {}
  }

  void _goCheckout() {
    if (_product == null) return;
    Navigator.pushNamed(context, '/checkout', arguments: {
      'product': _product!,
      'quantity': _quantity,
      // OPT-1：带券下单时透传 couponId，下单页默认选中
      if (_initialCouponId != null) 'initialCouponId': _initialCouponId,
    });
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return Scaffold(
        appBar: AppBar(backgroundColor: const Color(0xFF52C41A)),
        body: const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A))),
      );
    }

    if (_product == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('商品详情'), backgroundColor: const Color(0xFF52C41A)),
        body: const Center(child: Text('商品不存在')),
      );
    }

    final p = _product!;
    return Scaffold(
      body: CustomScrollView(
        slivers: [
          SliverAppBar(
            expandedHeight: 300,
            pinned: true,
            backgroundColor: const Color(0xFF52C41A),
            actions: [
              IconButton(
                icon: Icon(_isFavorited ? Icons.favorite : Icons.favorite_border, color: Colors.white),
                onPressed: _toggleFavorite,
              ),
            ],
            flexibleSpace: FlexibleSpaceBar(
              background: p.images.isNotEmpty
                  ? PageView.builder(
                      itemCount: p.images.length,
                      onPageChanged: (i) => setState(() => _currentImageIndex = i),
                      itemBuilder: (_, i) => Image.network(
                        p.images[i],
                        fit: BoxFit.cover,
                        errorBuilder: (_, __, ___) => _buildPlaceholder(),
                      ),
                    )
                  : _buildPlaceholder(),
            ),
          ),
          SliverToBoxAdapter(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                if (p.images.length > 1)
                  Center(
                    child: Padding(
                      padding: const EdgeInsets.only(top: 8),
                      child: Row(
                        mainAxisSize: MainAxisSize.min,
                        children: List.generate(
                          p.images.length,
                          (i) => Container(
                            width: 6,
                            height: 6,
                            margin: const EdgeInsets.symmetric(horizontal: 3),
                            decoration: BoxDecoration(
                              shape: BoxShape.circle,
                              color: i == _currentImageIndex
                                  ? const Color(0xFF52C41A)
                                  : Colors.grey[300],
                            ),
                          ),
                        ),
                      ),
                    ),
                  ),
                // Price & Name
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.white,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        crossAxisAlignment: CrossAxisAlignment.end,
                        children: [
                          Text(
                            '¥${formatPrice(p.salePrice)}',
                            style: const TextStyle(
                              color: Color(0xFFFF4D4F),
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          if (p.originalPrice != null && p.originalPrice! > p.salePrice) ...[
                            const SizedBox(width: 8),
                            Text(
                              '¥${formatPrice(p.originalPrice)}',
                              style: TextStyle(
                                color: Colors.grey[400],
                                fontSize: 14,
                                decoration: TextDecoration.lineThrough,
                              ),
                            ),
                          ],
                          const Spacer(),
                          Text('已售${p.salesCount}', style: TextStyle(color: Colors.grey[500], fontSize: 13)),
                        ],
                      ),
                      const SizedBox(height: 10),
                      Text(p.name, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                      if (p.categoryName != null) ...[
                        const SizedBox(height: 6),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF0F9EB),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(p.categoryName!, style: const TextStyle(color: Color(0xFF52C41A), fontSize: 12)),
                        ),
                      ],
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          _buildTag(p.fulfillmentLabel),
                          if (p.pointsExchangeable) ...[
                            const SizedBox(width: 6),
                            _buildTag('积分可兑'),
                          ],
                          if (p.pointsDeductible) ...[
                            const SizedBox(width: 6),
                            _buildTag('积分可抵'),
                          ],
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 8),
                // Info section
                Container(
                  padding: const EdgeInsets.all(16),
                  color: Colors.white,
                  child: Column(
                    children: [
                      _buildInfoRow('库存', p.stock > 0 ? '有货 (${p.stock})' : '暂无库存'),
                      if (p.reviewCount > 0)
                        _buildInfoRow(
                          '评价',
                          '${p.reviewCount}条评价${p.avgRating != null ? '  ${p.avgRating!.toStringAsFixed(1)}分' : ''}',
                        ),
                    ],
                  ),
                ),
                // [2026-05-02 H5 下单流程优化 PRD v1.0]
                // 详情页删除「可预约时段」「可用门店」选择区，
                // 选择行为整体下沉到下单页（CheckoutScreen）。
                if (false &&
                    p.appointmentMode != 'none' &&
                    p.timeSlots != null && p.timeSlots!.isNotEmpty)
                  Container(
                    color: Colors.white,
                    padding: const EdgeInsets.all(16),
                    margin: const EdgeInsets.only(top: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('可预约时段（今日）', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                        const SizedBox(height: 12),
                        Wrap(
                          spacing: 8,
                          runSpacing: 8,
                          children: p.timeSlots!.map<Widget>((slot) {
                            final label = '${slot['start'] ?? ''}-${slot['end'] ?? ''}';
                            final endTime = (slot['end'] ?? '').toString();
                            final expired = _isSlotExpired(endTime);
                            final fullyBooked = _isSlotFullyBooked(label);
                            final disabled = expired || fullyBooked;
                            final suffix = expired ? ' 已结束' : (fullyBooked ? ' 已约满' : '');
                            return Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              decoration: BoxDecoration(
                                color: disabled ? const Color(0xFFF5F5F5) : Colors.white,
                                border: Border.all(color: const Color(0xFFE5E5E5)),
                                borderRadius: BorderRadius.circular(20),
                              ),
                              child: Text(
                                '$label$suffix',
                                style: TextStyle(
                                  color: disabled ? const Color(0xFF999999) : const Color(0xFF333333),
                                  fontSize: 12,
                                ),
                              ),
                            );
                          }).toList(),
                        ),
                      ],
                    ),
                  ),
                if (false && _availableStores.isNotEmpty)
                  Container(
                    color: Colors.white,
                    padding: const EdgeInsets.all(16),
                    margin: const EdgeInsets.only(top: 8),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('可用门店', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w500)),
                            if (_storesSortBy == 'name')
                              const Text('已按门店名排序', style: TextStyle(color: Color(0xFFBBBBBB), fontSize: 11)),
                          ],
                        ),
                        const SizedBox(height: 12),
                        Builder(builder: (_) {
                          final cur = _availableStores[_selectedStoreIdx.clamp(0, _availableStores.length - 1)];
                          final dist = cur['distance_km'];
                          final hasGeo = cur['lat'] != null && cur['lng'] != null;
                          final fullAddr = '${cur['province'] ?? ''}${cur['city'] ?? ''}${cur['district'] ?? ''}${cur['address'] ?? ''}';
                          final mapUrl = cur['static_map_url']?.toString();
                          final isNearest = cur['is_nearest'] == true;
                          return GestureDetector(
                            // [2026-05-01 门店地图能力 PRD v1.0] 整张卡片可点击 → 唤起地图 App
                            onTap: () async {
                              if (hasGeo) {
                                await MapNavUtil.showMapNavSheet(
                                  context,
                                  name: cur['name']?.toString() ?? '',
                                  address: fullAddr,
                                  lat: (cur['lat'] as num).toDouble(),
                                  lng: (cur['lng'] as num).toDouble(),
                                );
                              } else if (_availableStores.length > 1) {
                                _showStoreDrawer();
                              }
                            },
                            child: Container(
                              padding: const EdgeInsets.all(12),
                              decoration: BoxDecoration(
                                border: Border.all(color: const Color(0xFFF0F0F0)),
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Row(
                                children: [
                                  Expanded(
                                    child: Column(
                                      crossAxisAlignment: CrossAxisAlignment.start,
                                      children: [
                                        Row(
                                          children: [
                                            Flexible(
                                              child: Text(
                                                cur['name']?.toString() ?? '',
                                                style: const TextStyle(fontWeight: FontWeight.w500, fontSize: 14),
                                                overflow: TextOverflow.ellipsis,
                                              ),
                                            ),
                                            if (isNearest)
                                              Container(
                                                margin: const EdgeInsets.only(left: 6),
                                                padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                                                decoration: BoxDecoration(
                                                  color: const Color(0xFF52C41A),
                                                  borderRadius: BorderRadius.circular(3),
                                                ),
                                                child: const Text('最近', style: TextStyle(color: Colors.white, fontSize: 10)),
                                              ),
                                          ],
                                        ),
                                        if (fullAddr.isNotEmpty) ...[
                                          const SizedBox(height: 4),
                                          Text(fullAddr, style: const TextStyle(color: Color(0xFF999999), fontSize: 12), maxLines: 2, overflow: TextOverflow.ellipsis),
                                        ],
                                        if (dist != null && hasGeo) ...[
                                          const SizedBox(height: 4),
                                          Text('距您 $dist km · 点击导航', style: const TextStyle(color: Color(0xFF52C41A), fontSize: 12)),
                                        ],
                                      ],
                                    ),
                                  ),
                                  // [2026-05-01 门店地图能力 PRD v1.0] 静态地图缩略图（仅 hasGeo & mapUrl）
                                  if (hasGeo && mapUrl != null && mapUrl.isNotEmpty) ...[
                                    const SizedBox(width: 8),
                                    Container(
                                      width: 100,
                                      height: 100,
                                      decoration: BoxDecoration(
                                        borderRadius: BorderRadius.circular(6),
                                        border: Border.all(color: const Color(0xFFF0F0F0)),
                                      ),
                                      clipBehavior: Clip.hardEdge,
                                      child: Stack(
                                        alignment: Alignment.bottomCenter,
                                        children: [
                                          CachedNetworkImage(
                                            imageUrl: mapUrl,
                                            fit: BoxFit.cover,
                                            width: 100,
                                            height: 100,
                                            placeholder: (_, __) => Container(color: const Color(0xFFF5F5F5)),
                                            errorWidget: (_, __, ___) => Container(
                                              color: const Color(0xFFF5F5F5),
                                              child: const Center(child: Icon(Icons.map, color: Color(0xFFBBBBBB))),
                                            ),
                                          ),
                                          const Padding(
                                            padding: EdgeInsets.only(bottom: 4),
                                            child: Text('📍', style: TextStyle(fontSize: 18)),
                                          ),
                                        ],
                                      ),
                                    ),
                                  ],
                                  if (_availableStores.length > 1) ...[
                                    const SizedBox(width: 6),
                                    GestureDetector(
                                      onTap: _showStoreDrawer,
                                      child: const Padding(
                                        padding: EdgeInsets.all(4),
                                        child: Text('切换', style: TextStyle(color: Color(0xFF1677FF), fontSize: 12)),
                                      ),
                                    ),
                                  ],
                                ],
                              ),
                            ),
                          );
                        }),
                      ],
                    ),
                  ),
                if (p.description != null && p.description!.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    color: Colors.white,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('商品详情', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        Text(p.description!, style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.6)),
                      ],
                    ),
                  ),
                ],
                if (p.symptomTags.isNotEmpty) ...[
                  const SizedBox(height: 8),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(16),
                    color: Colors.white,
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text('适用症状', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                        const SizedBox(height: 8),
                        Wrap(
                          spacing: 8,
                          runSpacing: 6,
                          children: p.symptomTags.map((tag) => Chip(
                            label: Text(tag, style: const TextStyle(fontSize: 12)),
                            backgroundColor: const Color(0xFFF0F9EB),
                            materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                          )).toList(),
                        ),
                      ],
                    ),
                  ),
                ],
                const SizedBox(height: 80),
              ],
            ),
          ),
        ],
      ),
      bottomNavigationBar: Container(
        padding: EdgeInsets.fromLTRB(16, 8, 16, MediaQuery.of(context).padding.bottom + 8),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.06), blurRadius: 8, offset: const Offset(0, -2))],
        ),
        child: Row(
          children: [
            Container(
              decoration: BoxDecoration(
                border: Border.all(color: Colors.grey[300]!),
                borderRadius: BorderRadius.circular(20),
              ),
              child: Row(
                children: [
                  IconButton(
                    icon: const Icon(Icons.remove, size: 18),
                    onPressed: _quantity > 1 ? () => setState(() => _quantity--) : null,
                    constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                  ),
                  Text('$_quantity', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                  IconButton(
                    icon: const Icon(Icons.add, size: 18),
                    onPressed: _quantity < p.stock ? () => setState(() => _quantity++) : null,
                    constraints: const BoxConstraints(minWidth: 36, minHeight: 36),
                  ),
                ],
              ),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: ElevatedButton(
                onPressed: p.stock > 0 ? _goCheckout : null,
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF52C41A),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                ),
                child: Text(p.stock > 0 ? '立即购买' : '暂时缺货', style: const TextStyle(fontSize: 16)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPlaceholder() {
    return Container(
      color: const Color(0xFFF0F9EB),
      child: const Center(child: Icon(Icons.shopping_bag_outlined, size: 60, color: Color(0xFF52C41A))),
    );
  }

  Widget _buildTag(String text) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        border: Border.all(color: const Color(0xFF52C41A)),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(text, style: const TextStyle(color: Color(0xFF52C41A), fontSize: 11)),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 70,
            child: Text(label, style: TextStyle(color: Colors.grey[500], fontSize: 14)),
          ),
          Expanded(child: Text(value, style: const TextStyle(fontSize: 14))),
        ],
      ),
    );
  }
}
