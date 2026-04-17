import 'package:flutter/material.dart';
import 'package:cached_network_image/cached_network_image.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

const _kPrimaryPurple = Color(0xFF722ED1);
const _kPrimaryPink = Color(0xFFEB2F96);
const _kPrimaryGreen = Color(0xFF52C41A);

class TcmDiagnosisDetailScreen extends StatefulWidget {
  const TcmDiagnosisDetailScreen({super.key});

  @override
  State<TcmDiagnosisDetailScreen> createState() => _TcmDiagnosisDetailScreenState();
}

class _TcmDiagnosisDetailScreenState extends State<TcmDiagnosisDetailScreen> {
  final ApiService _api = ApiService();

  Map<String, dynamic> _detail = {};
  bool _detailLoading = true;

  List<Map<String, dynamic>> _products = [];
  bool _productsLoading = true;
  static const int _maxProducts = 6;

  String _constitutionType = '';
  String _description = '';

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_detailLoading && _detail.isEmpty) {
      final args = ModalRoute.of(context)?.settings.arguments;
      if (args is Map<String, dynamic>) {
        _constitutionType = args['constitution_type']?.toString() ?? '';
        _description = args['description']?.toString() ?? '';
        final id = args['id'];
        if (id != null) {
          _loadDetail(id);
        } else {
          setState(() {
            _detailLoading = false;
            _detail = {
              'constitution_type': _constitutionType,
              'description': _description,
            };
          });
        }
        _loadProducts();
      }
    }
  }

  Future<void> _loadDetail(dynamic id) async {
    try {
      final response = await _api.getTcmDiagnosisList();
      if (response.statusCode == 200 && mounted) {
        final data = response.data;
        final rawData = data is Map && data.containsKey('data') ? data['data'] : data;
        final items = rawData is List
            ? rawData
            : (rawData is Map ? (rawData['items'] as List? ?? []) : []);
        for (final item in items) {
          if (item is Map && item['id']?.toString() == id.toString()) {
            setState(() => _detail = Map<String, dynamic>.from(item));
            break;
          }
        }
      }
    } catch (_) {}
    if (mounted) {
      setState(() {
        _detailLoading = false;
        if (_detail.isEmpty) {
          _detail = {
            'constitution_type': _constitutionType,
            'description': _description,
          };
        }
      });
    }
  }

  Future<void> _loadProducts() async {
    if (_constitutionType.isEmpty) {
      setState(() => _productsLoading = false);
      return;
    }
    try {
      final response = await _api.getProducts(
        keyword: _constitutionType,
        pageSize: _maxProducts,
      );
      if (response.statusCode == 200 && mounted) {
        final data = response.data;
        final items = data is Map
            ? (data['items'] as List? ?? data['data'] as List? ?? [])
            : (data is List ? data : []);
        setState(() {
          _products = items.take(_maxProducts).map((e) => Map<String, dynamic>.from(e as Map)).toList();
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _productsLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(
        title: '体质分析详情',
        backgroundColor: _kPrimaryPurple,
      ),
      body: _detailLoading
          ? const Center(child: CircularProgressIndicator(color: _kPrimaryPurple))
          : Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _buildResultHeader(),
                        _buildDetailSection(),
                        _buildProductsSection(),
                        const SizedBox(height: 80),
                      ],
                    ),
                  ),
                ),
                _buildBottomBar(),
              ],
            ),
    );
  }

  Widget _buildResultHeader() {
    final type = _detail['constitution_type']?.toString() ?? _constitutionType;
    final desc = _detail['description']?.toString() ?? _description;

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          colors: [_kPrimaryPurple, _kPrimaryPink],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
      ),
      child: Column(
        children: [
          Container(
            width: 80, height: 80,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              color: Colors.white.withOpacity(0.2),
            ),
            child: const Icon(Icons.spa, color: Colors.white, size: 40),
          ),
          const SizedBox(height: 16),
          Text(
            type,
            style: const TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white),
          ),
          if (desc.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(
              desc,
              style: const TextStyle(fontSize: 14, color: Colors.white70, height: 1.5),
              textAlign: TextAlign.center,
            ),
          ],
          const SizedBox(height: 8),
        ],
      ),
    );
  }

  Widget _buildDetailSection() {
    final characteristics = _detail['characteristics']?.toString() ?? '';
    final dietAdvice = _detail['diet_advice']?.toString() ?? '';
    final lifestyleAdvice = _detail['lifestyle_advice']?.toString() ?? '';
    final exerciseAdvice = _detail['exercise_advice']?.toString() ?? '';
    final avoidance = _detail['avoidance']?.toString() ?? '';

    final sections = <_DetailItem>[
      if (characteristics.isNotEmpty) _DetailItem('体质特征', characteristics, Icons.psychology, const Color(0xFF1890FF)),
      if (dietAdvice.isNotEmpty) _DetailItem('饮食建议', dietAdvice, Icons.restaurant, const Color(0xFFFA8C16)),
      if (lifestyleAdvice.isNotEmpty) _DetailItem('起居调养', lifestyleAdvice, Icons.bedtime, _kPrimaryPurple),
      if (exerciseAdvice.isNotEmpty) _DetailItem('运动建议', exerciseAdvice, Icons.fitness_center, _kPrimaryGreen),
      if (avoidance.isNotEmpty) _DetailItem('注意事项', avoidance, Icons.warning_amber, const Color(0xFFFF4D4F)),
    ];

    if (sections.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            color: _kPrimaryPurple.withOpacity(0.05),
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            children: [
              const Icon(Icons.spa, color: _kPrimaryPurple, size: 32),
              const SizedBox(height: 12),
              Text(
                '咨询AI获取详细的体质调理方案',
                style: TextStyle(fontSize: 14, color: Colors.grey[600]),
              ),
            ],
          ),
        ),
      );
    }

    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Padding(
            padding: EdgeInsets.symmetric(vertical: 8),
            child: Text('体质分析', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
          ),
          ...sections.map((item) => Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              boxShadow: [
                BoxShadow(color: Colors.black.withOpacity(0.03), blurRadius: 6, offset: const Offset(0, 2)),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 32, height: 32,
                      decoration: BoxDecoration(
                        color: item.color.withOpacity(0.1),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Icon(item.icon, color: item.color, size: 18),
                    ),
                    const SizedBox(width: 10),
                    Text(item.title, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: item.color)),
                  ],
                ),
                const SizedBox(height: 10),
                Text(item.content, style: const TextStyle(fontSize: 14, color: Color(0xFF333333), height: 1.6)),
              ],
            ),
          )),
        ],
      ),
    );
  }

  Widget _buildProductsSection() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('推荐商品', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              if (_products.isNotEmpty)
                GestureDetector(
                  onTap: () {
                    Navigator.pushNamed(context, '/product-list', arguments: {
                      'keyword': _constitutionType,
                    });
                  },
                  child: Row(
                    children: [
                      Text('查看更多', style: TextStyle(fontSize: 13, color: _kPrimaryPurple)),
                      Icon(Icons.chevron_right, size: 16, color: _kPrimaryPurple),
                    ],
                  ),
                ),
            ],
          ),
          const SizedBox(height: 12),
          if (_productsLoading)
            const Padding(
              padding: EdgeInsets.all(20),
              child: Center(child: CircularProgressIndicator(color: _kPrimaryPurple)),
            )
          else if (_products.isEmpty)
            Center(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Text('暂无推荐商品', style: TextStyle(color: Colors.grey[500])),
              ),
            )
          else
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 2,
                childAspectRatio: 0.75,
                crossAxisSpacing: 10,
                mainAxisSpacing: 10,
              ),
              itemCount: _products.length,
              itemBuilder: (context, index) => _buildProductCard(_products[index]),
            ),
        ],
      ),
    );
  }

  Widget _buildProductCard(Map<String, dynamic> product) {
    final name = product['name']?.toString() ?? '';
    final price = product['price']?.toString() ?? '';
    final imageUrl = product['main_image']?.toString() ?? product['image_url']?.toString() ?? '';
    final productId = product['id'];

    return GestureDetector(
      onTap: () {
        if (productId != null) {
          Navigator.pushNamed(context, '/product-detail', arguments: productId);
        }
      },
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 6, offset: const Offset(0, 2)),
          ],
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            ClipRRect(
              borderRadius: const BorderRadius.vertical(top: Radius.circular(12)),
              child: imageUrl.isNotEmpty
                  ? CachedNetworkImage(
                      imageUrl: imageUrl,
                      height: 120,
                      width: double.infinity,
                      fit: BoxFit.cover,
                      errorWidget: (_, __, ___) => _buildProductPlaceholder(),
                    )
                  : _buildProductPlaceholder(),
            ),
            Padding(
              padding: const EdgeInsets.all(10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 6),
                  Text(
                    price.isNotEmpty ? '¥$price' : '',
                    style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFFFF4D4F)),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProductPlaceholder() {
    return Container(
      height: 120,
      width: double.infinity,
      color: _kPrimaryPurple.withOpacity(0.05),
      child: const Icon(Icons.spa, color: _kPrimaryPurple, size: 40),
    );
  }

  Widget _buildBottomBar() {
    return Container(
      padding: EdgeInsets.only(
        left: 16, right: 16, top: 12,
        bottom: MediaQuery.of(context).padding.bottom + 12,
      ),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.05), blurRadius: 8, offset: const Offset(0, -2)),
        ],
      ),
      child: SizedBox(
        width: double.infinity,
        child: Container(
          decoration: BoxDecoration(
            gradient: const LinearGradient(colors: [_kPrimaryPurple, _kPrimaryPink]),
            borderRadius: BorderRadius.circular(12),
          ),
          child: ElevatedButton.icon(
            onPressed: () {
              final type = _detail['constitution_type']?.toString() ?? _constitutionType;
              Navigator.pushNamed(context, '/chat', arguments: {
                'type': 'constitution',
                'summary': '体质分析: $type',
                'initial_message': '我的体质是$type，请提供详细的养生调理方案',
              });
            },
            icon: const Icon(Icons.smart_toy, size: 20),
            label: const Text('咨询 AI 调理方案', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            style: ElevatedButton.styleFrom(
              backgroundColor: Colors.transparent,
              shadowColor: Colors.transparent,
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 16),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            ),
          ),
        ),
      ),
    );
  }
}

class _DetailItem {
  final String title;
  final String content;
  final IconData icon;
  final Color color;

  const _DetailItem(this.title, this.content, this.icon, this.color);
}
