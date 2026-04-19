import 'package:flutter/material.dart';
import '../../models/product.dart';
import '../../services/api_service.dart';

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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_product == null) {
      final productId = ModalRoute.of(context)!.settings.arguments as int;
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
    } catch (e) {
      setState(() => _loading = false);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('加载失败')));
      }
    }
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
                            '¥${p.salePrice.toStringAsFixed(2)}',
                            style: const TextStyle(
                              color: Color(0xFFFF4D4F),
                              fontSize: 24,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                          if (p.originalPrice > p.salePrice) ...[
                            const SizedBox(width: 8),
                            Text(
                              '¥${p.originalPrice.toStringAsFixed(2)}',
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
                      if (p.stores.isNotEmpty)
                        _buildInfoRow('适用门店', p.stores.map((s) => s.storeName ?? '门店${s.storeId}').join('、')),
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
