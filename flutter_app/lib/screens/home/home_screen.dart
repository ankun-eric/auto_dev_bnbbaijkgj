import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../models/article.dart';
import '../../providers/font_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/article_card.dart';

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
  String _searchPlaceholder = '搜索健康知识、服务、商品';
  int _gridColumns = 3;
  List<Map<String, dynamic>> _banners = [];
  List<Map<String, dynamic>> _menus = [];

  // City location
  String? _cityName;
  String? _cityId;
  bool _cityLocating = false;

  // Today todos
  List<Map<String, dynamic>> _todoGroups = [];
  int _todoTotalCompleted = 0;
  int _todoTotalCount = 0;
  bool _todayTodosLoading = false;

  // Unread messages
  int _unreadCount = 0;

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
    _loadTodayTodos();
    _loadCityInfo();
    _loadUnreadCount();
  }

  Future<void> _loadCityInfo() async {
    final prefs = await SharedPreferences.getInstance();
    final savedName = prefs.getString('selected_city_name');
    final savedId = prefs.getString('selected_city_id');
    if (savedName != null && savedName.isNotEmpty) {
      if (mounted) setState(() { _cityName = savedName; _cityId = savedId; });
      return;
    }

    final locatedName = prefs.getString('located_city_name');
    final locatedTime = prefs.getInt('located_city_time') ?? 0;
    final now = DateTime.now().millisecondsSinceEpoch;
    if (locatedName != null && locatedName.isNotEmpty && (now - locatedTime) < 30 * 60 * 1000) {
      if (mounted) setState(() { _cityName = locatedName; _cityId = prefs.getString('located_city_id'); });
    }
  }

  Future<void> _onCitySelected() async {
    final result = await Navigator.pushNamed(context, '/city-select');
    if (result is Map<String, dynamic> && mounted) {
      setState(() {
        _cityName = result['name']?.toString();
        _cityId = result['id']?.toString();
      });
    }
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

  Future<void> _loadTodayTodos() async {
    setState(() => _todayTodosLoading = true);
    try {
      final response = await _apiService.getTodayTodos();
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map ? response.data as Map<String, dynamic> : <String, dynamic>{};
        setState(() {
          _todoGroups = _parseList(data['groups']);
          _todoTotalCompleted = data['total_completed'] ?? 0;
          _todoTotalCount = data['total_count'] ?? 0;
          _todayTodosLoading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _todayTodosLoading = false);
    }
  }

  Future<void> _loadUnreadCount() async {
    try {
      final response = await _apiService.getUnreadMessageCount();
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map<String, dynamic>
            ? response.data as Map<String, dynamic>
            : <String, dynamic>{};
        setState(() {
          _unreadCount = data['unread_count'] ?? 0;
        });
      }
    } catch (_) {}
  }

  List<Map<String, dynamic>> _parseList(dynamic list) {
    if (list is List) {
      return list.map((e) => Map<String, dynamic>.from(e as Map)).toList();
    }
    return [];
  }

  Future<void> _handleQuickCheckin(Map<String, dynamic> item) async {
    try {
      final id = item['id'] as int;
      final type = item['type']?.toString() ?? '';
      await _apiService.quickCheckin(id, type);
      _loadTodayTodos();
    } catch (_) {}
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

  void _openScanner() {
    Navigator.push(
      context,
      MaterialPageRoute(builder: (context) => _QrScannerPage(
        onResult: (String code) {
          _handleScanResult(code);
        },
      )),
    );
  }

  void _handleScanResult(String code) {
    final uri = Uri.tryParse(code);
    if (uri != null && uri.queryParameters.containsKey('type') && uri.queryParameters.containsKey('code')) {
      final type = uri.queryParameters['type'];
      final inviteCode = uri.queryParameters['code'];
      if (type == 'family_invite' && inviteCode != null && inviteCode.isNotEmpty) {
        Navigator.pushNamed(context, '/family-auth', arguments: inviteCode);
        return;
      }
    }
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('无法识别该二维码'),
        backgroundColor: Colors.orange,
        duration: Duration(seconds: 2),
      ),
    );
  }

  void _goToMessages() async {
    await Navigator.pushNamed(context, '/messages');
    _loadUnreadCount();
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
                      _buildTodayTodos(),
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

  String get _cityDisplayText {
    if (_cityName != null && _cityName!.isNotEmpty) return _cityName!;
    if (_cityLocating) return '定位中...';
    return '定位';
  }

  Widget _buildAppBar() {
    return SliverAppBar(
      expandedHeight: 0,
      floating: true,
      pinned: true,
      backgroundColor: const Color(0xFF52C41A),
      title: _searchVisible
          ? Row(
              children: [
                GestureDetector(
                  onTap: _onCitySelected,
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      ConstrainedBox(
                        constraints: const BoxConstraints(maxWidth: 72),
                        child: Text(
                          _cityDisplayText,
                          style: const TextStyle(color: Colors.white, fontSize: 14, fontWeight: FontWeight.w500),
                          overflow: TextOverflow.ellipsis,
                          maxLines: 1,
                        ),
                      ),
                      const Icon(Icons.arrow_drop_down, color: Colors.white, size: 20),
                    ],
                  ),
                ),
                Container(
                  width: 1,
                  height: 18,
                  margin: const EdgeInsets.symmetric(horizontal: 8),
                  color: Colors.white.withOpacity(0.3),
                ),
                Expanded(
                  child: GestureDetector(
                    onTap: () => Navigator.pushNamed(context, '/search'),
                    child: Container(
                      height: 34,
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(0.2),
                        borderRadius: BorderRadius.circular(17),
                      ),
                      child: Row(
                        children: [
                          const SizedBox(width: 12),
                          Icon(Icons.search, color: Colors.white.withOpacity(0.8), size: 18),
                          const SizedBox(width: 6),
                          Expanded(
                            child: Text(
                              _searchPlaceholder,
                              style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 13),
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          const SizedBox(width: 12),
                        ],
                      ),
                    ),
                  ),
                ),
              ],
            )
          : const Text('宾尼小康', style: TextStyle(color: Colors.white, fontSize: 18)),
      actions: [
        IconButton(
          icon: const Icon(Icons.qr_code_scanner, color: Colors.white),
          onPressed: _openScanner,
        ),
        Stack(
          alignment: Alignment.center,
          children: [
            IconButton(
              icon: const Icon(Icons.notifications_outlined, color: Colors.white),
              onPressed: _goToMessages,
            ),
            if (_unreadCount > 0)
              Positioned(
                right: 8,
                top: 8,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 1),
                  decoration: BoxDecoration(
                    color: const Color(0xFFFF4D4F),
                    borderRadius: BorderRadius.circular(10),
                  ),
                  constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
                  child: Text(
                    _unreadCount > 99 ? '99+' : '$_unreadCount',
                    style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold),
                    textAlign: TextAlign.center,
                  ),
                ),
              ),
          ],
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

  static const _groupTypeConfig = <String, Map<String, dynamic>>{
    'medication': {'icon': Icons.medication, 'color': Color(0xFFFA8C16)},
    'checkin': {'icon': Icons.check_circle_outline, 'color': Color(0xFF52C41A)},
    'custom': {'icon': Icons.flag_outlined, 'color': Color(0xFF1890FF)},
  };

  Widget _buildTodayTodos() {
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
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Row(
                children: [
                  Container(
                    width: 32,
                    height: 32,
                    decoration: BoxDecoration(
                      color: const Color(0xFF52C41A).withOpacity(0.15),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Icon(Icons.today, color: Color(0xFF52C41A), size: 18),
                  ),
                  const SizedBox(width: 8),
                  const Text('今日待办', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF333333))),
                  if (_todoTotalCount > 0) ...[
                    const SizedBox(width: 8),
                    Text('$_todoTotalCompleted/$_todoTotalCount', style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                  ],
                ],
              ),
              GestureDetector(
                onTap: () => Navigator.pushNamed(context, '/health-plan'),
                child: Row(
                  children: [
                    Text('查看全部', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                    Icon(Icons.chevron_right, size: 18, color: Colors.grey[500]),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          if (_todayTodosLoading)
            const Center(child: Padding(
              padding: EdgeInsets.all(12),
              child: SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Color(0xFF52C41A))),
            ))
          else if (_todoTotalCount == 0)
            Center(
              child: Padding(
                padding: const EdgeInsets.symmetric(vertical: 12),
                child: Text('今天暂无待办事项', style: TextStyle(fontSize: 14, color: Colors.grey[400])),
              ),
            )
          else ...[
            for (final group in _todoGroups) ..._buildGroupItems(group),
          ],
        ],
      ),
    );
  }

  List<Widget> _buildGroupItems(Map<String, dynamic> group) {
    final groupType = group['group_type']?.toString() ?? '';
    final config = _groupTypeConfig[groupType] ?? _groupTypeConfig['custom']!;
    final icon = config['icon'] as IconData;
    final color = config['color'] as Color;
    final items = _parseList(group['items']);
    final isEmpty = group['is_empty'] == true || items.isEmpty;
    final groupName = group['group_name']?.toString() ?? '';

    final widgets = <Widget>[];

    if (isEmpty) {
      widgets.add(_buildTodoItem(
        icon: icon,
        color: Colors.grey[300]!,
        title: groupName,
        subtitle: '今日无待办',
        done: false,
        onCheck: null,
        greyed: true,
      ));
    } else {
      for (final item in items.take(3)) {
        String subtitle = '';
        if (groupType == 'medication') {
          final extra = item['extra'] is Map ? item['extra'] as Map : {};
          subtitle = [extra['time_period'] ?? '', item['remind_time'] ?? ''].where((s) => s.toString().isNotEmpty).join(' ');
        } else if (groupType == 'checkin' && item['target_value'] != null) {
          subtitle = '目标: ${item['target_value']} ${item['target_unit'] ?? ''}';
        } else if (item['extra'] is Map && (item['extra'] as Map)['plan_name'] != null) {
          subtitle = (item['extra'] as Map)['plan_name'].toString();
        }
        widgets.add(_buildTodoItem(
          icon: icon,
          color: color,
          title: item['name']?.toString() ?? '',
          subtitle: subtitle,
          done: item['is_completed'] == true,
          onCheck: () => _handleQuickCheckin(item),
        ));
      }
    }
    return widgets;
  }

  Widget _buildTodoItem({
    required IconData icon,
    required Color color,
    required String title,
    required String subtitle,
    required bool done,
    VoidCallback? onCheck,
    bool greyed = false,
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: greyed ? Colors.grey[50] : Colors.white,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          if (!greyed)
            GestureDetector(
              onTap: done ? null : onCheck,
              child: Container(
                width: 22,
                height: 22,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: done ? color : Colors.transparent,
                  border: Border.all(color: done ? color : Colors.grey[300]!, width: 2),
                ),
                child: done ? const Icon(Icons.check, size: 13, color: Colors.white) : null,
              ),
            ),
          if (!greyed) const SizedBox(width: 10),
          Icon(icon, color: greyed ? Colors.grey[300] : color, size: 18),
          const SizedBox(width: 8),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: TextStyle(
                    fontSize: 14,
                    decoration: done ? TextDecoration.lineThrough : null,
                    color: greyed ? Colors.grey[400] : (done ? Colors.grey[400] : const Color(0xFF333333)),
                  ),
                ),
                if (subtitle.isNotEmpty)
                  Text(subtitle, style: TextStyle(fontSize: 11, color: Colors.grey[400])),
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

class _QrScannerPage extends StatefulWidget {
  final ValueChanged<String> onResult;

  const _QrScannerPage({required this.onResult});

  @override
  State<_QrScannerPage> createState() => _QrScannerPageState();
}

class _QrScannerPageState extends State<_QrScannerPage> {
  final MobileScannerController _controller = MobileScannerController();
  bool _handled = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_handled) return;
    final barcodes = capture.barcodes;
    if (barcodes.isEmpty) return;
    final code = barcodes.first.rawValue;
    if (code == null || code.isEmpty) return;
    _handled = true;
    Navigator.pop(context);
    widget.onResult(code);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('扫一扫'),
        backgroundColor: Colors.black,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Stack(
        children: [
          MobileScanner(
            controller: _controller,
            onDetect: _onDetect,
          ),
          Center(
            child: Container(
              width: 250,
              height: 250,
              decoration: BoxDecoration(
                border: Border.all(color: const Color(0xFF52C41A), width: 2),
                borderRadius: BorderRadius.circular(12),
              ),
            ),
          ),
          Positioned(
            bottom: 80,
            left: 0,
            right: 0,
            child: Center(
              child: Text(
                '将二维码放入框内扫描',
                style: TextStyle(color: Colors.white.withOpacity(0.8), fontSize: 14),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
