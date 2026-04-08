import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../providers/font_provider.dart';
import '../../models/article.dart';
import '../../services/api_service.dart';
import '../../widgets/article_card.dart';
import '../../widgets/font_size_sheet.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final PageController _bannerController = PageController();
  final ApiService _apiService = ApiService();
  int _currentBanner = 0;

  bool _loading = true;

  // Config defaults
  bool _searchVisible = true;
  String _searchPlaceholder = '搜索症状、疾病、药品';
  int _gridColumns = 3;
  bool _fontSwitchEnabled = false;

  List<Map<String, dynamic>> _banners = [];
  List<Map<String, dynamic>> _menus = [];

  final List<Article> _articles = [
    Article(id: '1', title: '春季养生：如何预防过敏性鼻炎', summary: '春季是过敏性鼻炎的高发季节，了解预防措施...', author: '健康专家', viewCount: 2345),
    Article(id: '2', title: '每天走一万步真的健康吗？', summary: '运动量因人而异，科学运动更重要...', author: '运动医学', viewCount: 1892),
    Article(id: '3', title: '中医教你看舌象辨健康', summary: '舌诊是中医四诊之一，通过舌象可以了解...', author: '中医养生', viewCount: 3210),
  ];

  static const List<Map<String, dynamic>> _defaultBanners = [
    {'title': 'AI健康咨询', 'subtitle': '足不出户，在线咨询', 'color': Color(0xFF52C41A)},
    {'title': '中医体质辨识', 'subtitle': '了解体质，养生有方', 'color': Color(0xFF13C2C2)},
    {'title': '家庭健康管理', 'subtitle': '全家健康，一手掌握', 'color': Color(0xFF1890FF)},
  ];

  static const List<Map<String, dynamic>> _defaultMenus = [
    {'icon_type': 'emoji', 'icon_content': '🤖', 'name': 'AI咨询', 'link_type': 'internal', 'link_url': '/ai'},
    {'icon_type': 'emoji', 'icon_content': '📋', 'name': '体检报告', 'link_type': 'internal', 'link_url': '/checkup'},
    {'icon_type': 'emoji', 'icon_content': '🔍', 'name': '症状自查', 'link_type': 'internal', 'link_url': '/symptom'},
    {'icon_type': 'emoji', 'icon_content': '🌿', 'name': '中医辨证', 'link_type': 'internal', 'link_url': '/tcm'},
    {'icon_type': 'emoji', 'icon_content': '💊', 'name': '用药参考', 'link_type': 'internal', 'link_url': '/drug'},
    {'icon_type': 'emoji', 'icon_content': '📅', 'name': '健康计划', 'link_type': 'internal', 'link_url': '/health-plan'},
  ];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    try {
      final results = await Future.wait([
        _apiService.getHomeConfig().catchError((_) => <String, dynamic>{}),
        _apiService.getHomeMenus().catchError((_) => <Map<String, dynamic>>[]),
        _apiService.getHomeBanners().catchError((_) => <Map<String, dynamic>>[]),
      ]);

      final config = results[0] as Map<String, dynamic>;
      final menus = results[1] as List<Map<String, dynamic>>;
      final banners = results[2] as List<Map<String, dynamic>>;

      if (!mounted) return;

      final fontProvider = Provider.of<FontProvider>(context, listen: false);
      if (config.isNotEmpty) {
        fontProvider.applyConfig(config);
      }

      setState(() {
        if (config.isNotEmpty) {
          _searchVisible = config['search_visible'] ?? true;
          _searchPlaceholder = config['search_placeholder'] ?? _searchPlaceholder;
          _gridColumns = config['grid_columns'] ?? _gridColumns;
          _fontSwitchEnabled = config['font_switch_enabled'] ?? false;
        }
        _menus = menus.isNotEmpty ? menus : List<Map<String, dynamic>>.from(_defaultMenus);
        _banners = banners.isNotEmpty ? banners : List<Map<String, dynamic>>.from(_defaultBanners);
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _menus = List<Map<String, dynamic>>.from(_defaultMenus);
        _banners = List<Map<String, dynamic>>.from(_defaultBanners);
        _loading = false;
      });
    }
  }

  @override
  void dispose() {
    _bannerController.dispose();
    super.dispose();
  }

  void _handleBannerTap(Map<String, dynamic> banner) async {
    final linkType = banner['link_type']?.toString() ?? 'none';
    final linkUrl = banner['link_url']?.toString() ?? '';

    switch (linkType) {
      case 'internal':
        if (linkUrl.isNotEmpty) {
          Navigator.pushNamed(context, linkUrl);
        }
        break;
      case 'external':
        if (linkUrl.isNotEmpty) {
          final uri = Uri.tryParse(linkUrl);
          if (uri != null && await canLaunchUrl(uri)) {
            await launchUrl(uri, mode: LaunchMode.externalApplication);
          }
        }
        break;
      default:
        break;
    }
  }

  void _handleMenuTap(Map<String, dynamic> menu) async {
    final linkType = menu['link_type']?.toString() ?? 'none';
    final linkUrl = menu['link_url']?.toString() ?? '';

    switch (linkType) {
      case 'internal':
        if (linkUrl.isNotEmpty) {
          Navigator.pushNamed(context, linkUrl);
        }
        break;
      case 'external':
        if (linkUrl.isNotEmpty) {
          final uri = Uri.tryParse(linkUrl);
          if (uri != null && await canLaunchUrl(uri)) {
            await launchUrl(uri, mode: LaunchMode.externalApplication);
          }
        }
        break;
      default:
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: _loading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF52C41A)))
          : CustomScrollView(
              slivers: [
                _buildAppBar(),
                SliverToBoxAdapter(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      _buildBanner(),
                      const SizedBox(height: 20),
                      _buildFeatureGrid(),
                      const SizedBox(height: 20),
                      _buildHealthTip(),
                      const SizedBox(height: 20),
                      _buildSectionHeader('健康知识', onMore: () => Navigator.pushNamed(context, '/articles')),
                      const SizedBox(height: 8),
                    ],
                  ),
                ),
                SliverList(
                  delegate: SliverChildBuilderDelegate(
                    (context, index) => ArticleCard(
                      article: _articles[index],
                      onTap: () => Navigator.pushNamed(context, '/article-detail', arguments: _articles[index].id),
                    ),
                    childCount: _articles.length,
                  ),
                ),
                const SliverPadding(padding: EdgeInsets.only(bottom: 20)),
              ],
            ),
    );
  }

  Widget _buildAppBar() {
    return SliverAppBar(
      expandedHeight: 0,
      floating: true,
      pinned: true,
      backgroundColor: const Color(0xFF52C41A),
      title: _searchVisible
          ? GestureDetector(
              onTap: () {},
              child: Container(
                height: 38,
                decoration: BoxDecoration(
                  color: Colors.white.withOpacity(0.2),
                  borderRadius: BorderRadius.circular(19),
                ),
                child: Row(
                  children: [
                    const SizedBox(width: 14),
                    Icon(Icons.search, color: Colors.white.withOpacity(0.8), size: 20),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        _searchPlaceholder,
                        style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 14),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    const SizedBox(width: 14),
                  ],
                ),
              ),
            )
          : const Text('宾尼小康', style: TextStyle(color: Colors.white, fontSize: 18)),
      actions: [
        if (_fontSwitchEnabled)
          IconButton(
            icon: const Text(
              'Aa',
              style: TextStyle(color: Colors.white, fontSize: 16, fontWeight: FontWeight.bold),
            ),
            onPressed: () => FontSizeSheet.show(context),
          ),
        IconButton(
          icon: const Icon(Icons.notifications_outlined, color: Colors.white),
          onPressed: () => Navigator.pushNamed(context, '/notifications'),
        ),
      ],
    );
  }

  Widget _buildBanner() {
    final bool isFromApi = _banners.isNotEmpty && _banners.first.containsKey('image_url');

    return Container(
      height: 160,
      margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: Stack(
          children: [
            PageView.builder(
              controller: _bannerController,
              itemCount: _banners.length,
              onPageChanged: (index) => setState(() => _currentBanner = index),
              itemBuilder: (context, index) {
                final banner = _banners[index];
                return GestureDetector(
                  onTap: () => _handleBannerTap(banner),
                  child: _buildBannerItem(banner, isFromApi),
                );
              },
            ),
            Positioned(
              bottom: 12,
              right: 16,
              child: Row(
                children: List.generate(
                  _banners.length,
                  (index) => Container(
                    width: _currentBanner == index ? 18 : 6,
                    height: 6,
                    margin: const EdgeInsets.only(left: 4),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(3),
                      color: _currentBanner == index ? Colors.white : Colors.white.withOpacity(0.5),
                    ),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildBannerItem(Map<String, dynamic> banner, bool isFromApi) {
    if (isFromApi && banner['image_url'] != null && (banner['image_url'] as String).isNotEmpty) {
      return Image.network(
        banner['image_url'],
        fit: BoxFit.cover,
        width: double.infinity,
        errorBuilder: (_, __, ___) => _buildFallbackBanner(banner),
      );
    }
    return _buildFallbackBanner(banner);
  }

  Widget _buildFallbackBanner(Map<String, dynamic> banner) {
    final color = banner['color'] is Color
        ? banner['color'] as Color
        : const Color(0xFF52C41A);
    final title = banner['title']?.toString() ?? banner['name']?.toString() ?? '';
    final subtitle = banner['subtitle']?.toString() ?? '';

    return Container(
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [color, color.withOpacity(0.7)],
        ),
      ),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Text(
              title,
              style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold),
            ),
            if (subtitle.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(subtitle, style: TextStyle(color: Colors.white.withOpacity(0.9), fontSize: 14)),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildFeatureGrid() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: GridView.builder(
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: _gridColumns,
          childAspectRatio: 1.1,
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
        ),
        itemCount: _menus.length,
        itemBuilder: (context, index) {
          final menu = _menus[index];
          return GestureDetector(
            onTap: () => _handleMenuTap(menu),
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
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  _buildMenuIcon(menu),
                  const SizedBox(height: 8),
                  Text(
                    menu['name']?.toString() ?? menu['label']?.toString() ?? '',
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _buildMenuIcon(Map<String, dynamic> menu) {
    final iconType = menu['icon_type']?.toString() ?? 'emoji';
    final iconContent = menu['icon_content']?.toString() ?? '';

    if (iconType == 'image' && iconContent.isNotEmpty) {
      return Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(12)),
        clipBehavior: Clip.antiAlias,
        child: Image.network(
          iconContent,
          fit: BoxFit.cover,
          errorBuilder: (_, __, ___) => Container(
            width: 44,
            height: 44,
            decoration: BoxDecoration(
              color: const Color(0xFF52C41A).withOpacity(0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Icon(Icons.apps, color: Color(0xFF52C41A), size: 24),
          ),
        ),
      );
    }

    if (iconType == 'emoji' && iconContent.isNotEmpty) {
      return Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: const Color(0xFF52C41A).withOpacity(0.1),
          borderRadius: BorderRadius.circular(12),
        ),
        alignment: Alignment.center,
        child: Text(iconContent, style: const TextStyle(fontSize: 24)),
      );
    }

    // Fallback for legacy icon data
    final icon = menu['icon'];
    final color = menu['color'] is Color ? menu['color'] as Color : const Color(0xFF52C41A);
    return Container(
      width: 44,
      height: 44,
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        icon is IconData ? icon : Icons.apps,
        color: color,
        size: 24,
      ),
    );
  }

  Widget _buildHealthTip() {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          colors: [
            const Color(0xFF52C41A).withOpacity(0.08),
            const Color(0xFF13C2C2).withOpacity(0.08),
          ],
        ),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: const Color(0xFF52C41A).withOpacity(0.2)),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: const Color(0xFF52C41A).withOpacity(0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Icon(Icons.lightbulb_outline, color: Color(0xFF52C41A), size: 22),
          ),
          const SizedBox(width: 12),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '今日健康提示',
                  style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
                ),
                SizedBox(height: 4),
                Text(
                  '春季多饮水、早睡早起，适当进行户外运动有助于增强免疫力。',
                  style: TextStyle(fontSize: 13, color: Color(0xFF666666), height: 1.4),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSectionHeader(String title, {VoidCallback? onMore}) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            title,
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
          if (onMore != null)
            GestureDetector(
              onTap: onMore,
              child: Row(
                children: [
                  Text('查看更多', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                  Icon(Icons.chevron_right, size: 18, color: Colors.grey[500]),
                ],
              ),
            ),
        ],
      ),
    );
  }
}
