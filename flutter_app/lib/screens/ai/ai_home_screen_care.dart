// [PRD-CARE-AI-HOME 2026-05-27] Flutter 关怀模式 AI 主页 v1
// 完整还原需求清单设计图：欢迎区 / 快捷胶囊 / 健康简评卡 / 用药提醒卡 / SOS 关怀卡 /
// 底部"咨询 AI"悬浮球（3/4 屏抽屉）/ 右下角 SOS 占位悬浮球。
import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../services/api_service.dart';

class AiHomeScreenCare extends StatefulWidget {
  const AiHomeScreenCare({super.key});

  @override
  State<AiHomeScreenCare> createState() => _AiHomeScreenCareState();
}

class _AiHomeScreenCareState extends State<AiHomeScreenCare> {
  Map<String, dynamic>? summary;
  List<Map<String, dynamic>> metrics = [];
  List<Map<String, dynamic>> alerts = [];
  Map<String, dynamic>? medication;
  bool loading = true;

  @override
  void initState() {
    super.initState();
    _loadAll();
  }

  String _greeting() {
    final h = DateTime.now().hour;
    if (h >= 5 && h < 11) return '早上好 ☀️';
    if (h >= 11 && h < 18) return '中午好 ☀️';
    return '晚上好 🌙';
  }

  Color _statusColor(String status) {
    if (status == '偏高') return const Color(0xFFE53935);
    if (status == '偏低') return const Color(0xFFFB8C00);
    return const Color(0xFF43A047);
  }

  Future<void> _loadAll() async {
    setState(() => loading = true);
    final dio = ApiService().dio;
    final futures = await Future.wait([
      dio.get('/api/care/daily-summary').then((r) => r.data).catchError((_) => null),
      dio.get('/api/care/alerts/active').then((r) => r.data).catchError((_) => null),
      dio.get('/api/medication-reminder/today').then((r) => r.data).catchError((_) => null),
    ]);

    final sum = futures[0]?['data'];
    final alertsResp = futures[1]?['data']?['alerts'];
    final medResp = futures[2]?['data']?['items'] ?? futures[2]?['items'];

    Map<String, dynamic>? nextMed;
    if (medResp is List) {
      for (final it in medResp) {
        if (it is Map && it['done'] != true) {
          nextMed = Map<String, dynamic>.from(it);
          break;
        }
      }
    }

    setState(() {
      summary = sum is Map ? Map<String, dynamic>.from(sum) : null;
      metrics = (sum?['metrics'] is List)
          ? List<Map<String, dynamic>>.from(
              (sum['metrics'] as List).map((e) => Map<String, dynamic>.from(e)))
          : [];
      alerts = (alertsResp is List)
          ? List<Map<String, dynamic>>.from(
              alertsResp.map((e) => Map<String, dynamic>.from(e)))
          : [];
      medication = nextMed;
      loading = false;
    });
  }

  Future<void> _dismissAlert(int id) async {
    try {
      await ApiService().dio.post('/api/care/alerts/$id/dismiss');
    } catch (_) {}
    setState(() {
      alerts.removeWhere((a) => a['id'] == id);
    });
  }

  Future<void> _callFamily() async {
    final uri = Uri.parse('tel:120');
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    }
  }

  void _showToast(String msg) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(msg), duration: const Duration(seconds: 2)));
  }

  void _openDrawer() {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (context) {
        final h = MediaQuery.of(context).size.height;
        return SizedBox(
          height: h * 0.75,
          child: Container(
            decoration: const BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
            ),
            child: Column(
              children: [
                const SizedBox(height: 8),
                Container(
                  width: 40,
                  height: 4,
                  decoration: BoxDecoration(
                    color: const Color(0xFFE0E0E0),
                    borderRadius: BorderRadius.circular(2),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('咨询小康',
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                      IconButton(
                        icon: const Icon(Icons.close),
                        onPressed: () => Navigator.of(context).pop(),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Container(
                    margin: const EdgeInsets.symmetric(horizontal: 16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF5F7FA),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Center(
                      child: Padding(
                        padding: EdgeInsets.all(16),
                        child: Text(
                          '小康为您服务中…\n\n本期复用标准模式 AI 对话页面，\n您可在此处与 AI 自由对话或切换咨询人。',
                          textAlign: TextAlign.center,
                          style: TextStyle(fontSize: 16, color: Color(0xFF666666), height: 1.6),
                        ),
                      ),
                    ),
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                        decoration: BoxDecoration(
                          color: const Color(0xFFE8F5E9),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        child: const Text('咨询人：本人',
                            style: TextStyle(fontSize: 13, color: Color(0xFF1976D2))),
                      ),
                      const Spacer(),
                      Expanded(
                        child: Container(
                          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                          decoration: BoxDecoration(
                            color: const Color(0xFFF0F2F5),
                            borderRadius: BorderRadius.circular(24),
                          ),
                          child: const Text('请输入想问的问题…',
                              style: TextStyle(color: Color(0xFF999999))),
                        ),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F7FA),
      body: SafeArea(
        child: Stack(
          children: [
            ListView(
              padding: const EdgeInsets.only(bottom: 140),
              children: [
                _buildTopBar(),
                _buildWelcome(),
                _buildQuickGrid(),
                const SizedBox(height: 8),
                _buildHealthSummaryCard(),
                _buildMedicationCard(),
                ...alerts.map(_buildSosAlertCard),
                const SizedBox(height: 16),
              ],
            ),
            // 底部 咨询 AI 悬浮球
            Positioned(
              left: 0,
              right: 0,
              bottom: 24,
              child: Center(
                child: ElevatedButton.icon(
                  onPressed: _openDrawer,
                  icon: const Text('💬', style: TextStyle(fontSize: 20)),
                  label: const Text('咨询 AI',
                      style: TextStyle(fontSize: 17, fontWeight: FontWeight.w600)),
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1976D2),
                    foregroundColor: Colors.white,
                    padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 14),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(32),
                    ),
                    elevation: 6,
                  ),
                ),
              ),
            ),
            // 右下角 SOS 占位悬浮球
            Positioned(
              right: 20,
              bottom: 24,
              child: GestureDetector(
                onTap: () => _showToast('SOS 功能即将上线'),
                child: Container(
                  width: 56,
                  height: 56,
                  decoration: BoxDecoration(
                    color: const Color(0xFFE53935),
                    shape: BoxShape.circle,
                    boxShadow: [
                      BoxShadow(
                        color: const Color(0xFFE53935).withOpacity(0.5),
                        blurRadius: 16,
                        spreadRadius: 2,
                      ),
                    ],
                  ),
                  alignment: Alignment.center,
                  child: const Text(
                    'SOS',
                    style: TextStyle(
                        color: Colors.white, fontSize: 14, fontWeight: FontWeight.bold),
                  ),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTopBar() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      child: Row(
        children: [
          IconButton(
              icon: const Icon(Icons.menu, size: 26),
              onPressed: () {},
              tooltip: '菜单'),
          const Spacer(),
          Row(
            children: [
              const Text('小康', style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              const SizedBox(width: 6),
              Container(
                width: 8,
                height: 8,
                decoration: const BoxDecoration(color: Color(0xFF43A047), shape: BoxShape.circle),
              ),
              const SizedBox(width: 4),
              const Text('在线', style: TextStyle(fontSize: 14, color: Color(0xFF666666))),
            ],
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: const Color(0xFFE8F5E9),
              borderRadius: BorderRadius.circular(12),
            ),
            child: const Text('关怀模式',
                style: TextStyle(
                    fontSize: 12, color: Color(0xFF1976D2), fontWeight: FontWeight.w600)),
          ),
          const SizedBox(width: 8),
          TextButton(
            onPressed: () {
              Navigator.of(context).pushNamed('/welcome-mode');
            },
            style: TextButton.styleFrom(
              backgroundColor: const Color(0xFF1976D2),
              foregroundColor: Colors.white,
              minimumSize: const Size(0, 32),
              padding: const EdgeInsets.symmetric(horizontal: 12),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
            ),
            child: const Text('切换模式', style: TextStyle(fontSize: 13)),
          ),
        ],
      ),
    );
  }

  Widget _buildWelcome() {
    // [PRD-AIHOME-WELCOME-UNIFY-V1 2026-06-02] 两模式仅靠背景底色区分：关怀模式欢迎区改为暖橙渐变，其余不动
    return Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [Color(0xFFFF8A3D), Color(0xFFFB6E2E)],
        ),
        borderRadius: BorderRadius.vertical(bottom: Radius.circular(24)),
      ),
      padding: const EdgeInsets.fromLTRB(20, 28, 20, 28),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(_greeting(),
              style: const TextStyle(
                  fontSize: 28, fontWeight: FontWeight.bold, color: Colors.white)),
          const SizedBox(height: 8),
          const Text('我是小康，有事儿随时问我~',
              style: TextStyle(fontSize: 17, color: Colors.white)),
        ],
      ),
    );
  }

  Widget _buildQuickGrid() {
    final items = [
      {'icon': '📋', 'label': '健康档案', 'route': '/health-profile'},
      {'icon': '💊', 'label': '用药提醒', 'route': '/medication-reminder'},
      {'icon': '📷', 'label': '拍照问AI', 'route': '/ai-chat?action=photo'},
      {'icon': '🏥', 'label': '健康服务', 'route': '/services'},
    ];
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: items
            .map((it) => Expanded(
                  child: Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 4),
                    child: InkWell(
                      onTap: () {
                        try {
                          Navigator.of(context).pushNamed(it['route']!);
                        } catch (_) {
                          _showToast('${it['label']} 即将打开');
                        }
                      },
                      borderRadius: BorderRadius.circular(16),
                      child: Container(
                        height: 80,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          border: Border.all(color: const Color(0xFFE0E0E0)),
                          borderRadius: BorderRadius.circular(16),
                        ),
                        alignment: Alignment.center,
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(it['icon']!, style: const TextStyle(fontSize: 24)),
                            const SizedBox(height: 4),
                            Text(it['label']!,
                                style: const TextStyle(
                                    fontSize: 14, fontWeight: FontWeight.w500)),
                          ],
                        ),
                      ),
                    ),
                  ),
                ))
            .toList(),
      ),
    );
  }

  Widget _buildHealthSummaryCard() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: InkWell(
        onTap: () {
          try {
            Navigator.of(context).pushNamed('/health-dashboard');
          } catch (_) {}
        },
        borderRadius: BorderRadius.circular(16),
        child: Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
            boxShadow: [
              BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2)),
            ],
          ),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: const [
                  Text('📊', style: TextStyle(fontSize: 22)),
                  SizedBox(width: 8),
                  Text('健康简评',
                      style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
                ],
              ),
              const SizedBox(height: 10),
              Text(
                loading ? '加载中…' : (summary?['summary_text'] ?? '今日数据尚未生成，请稍后查看 ~'),
                style: const TextStyle(fontSize: 16, color: Color(0xFF424242)),
              ),
              const SizedBox(height: 12),
              if (metrics.isNotEmpty)
                Row(
                  children: metrics
                      .map((m) => Expanded(
                            child: Padding(
                              padding: const EdgeInsets.symmetric(horizontal: 4),
                              child: Container(
                                padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 8),
                                decoration: BoxDecoration(
                                  color: const Color(0xFFF5F7FA),
                                  borderRadius: BorderRadius.circular(12),
                                ),
                                child: Column(
                                  children: [
                                    Text(m['label'] ?? '',
                                        style: const TextStyle(fontSize: 13, color: Color(0xFF666666))),
                                    const SizedBox(height: 4),
                                    RichText(
                                      text: TextSpan(
                                        text: '${m['value']}',
                                        style: const TextStyle(
                                            fontSize: 18,
                                            fontWeight: FontWeight.bold,
                                            color: Color(0xFF212121)),
                                        children: [
                                          TextSpan(
                                            text: ' ${m['unit']}',
                                            style: const TextStyle(
                                                fontSize: 12, color: Color(0xFF999999), fontWeight: FontWeight.normal),
                                          ),
                                        ],
                                      ),
                                    ),
                                    const SizedBox(height: 4),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                      decoration: BoxDecoration(
                                        color: _statusColor(m['status'] ?? '').withOpacity(0.1),
                                        borderRadius: BorderRadius.circular(8),
                                      ),
                                      child: Text(m['status'] ?? '',
                                          style: TextStyle(
                                              fontSize: 12, color: _statusColor(m['status'] ?? ''))),
                                    ),
                                  ],
                                ),
                              ),
                            ),
                          ))
                      .toList(),
                ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildMedicationCard() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Container(
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(16),
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text('💊', style: TextStyle(fontSize: 22)),
                const SizedBox(width: 8),
                Text(medication != null ? '该吃药啦' : '今日用药已全部完成 ✅',
                    style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600)),
              ],
            ),
            const SizedBox(height: 10),
            if (medication != null) ...[
              Text(
                '${medication!['drug_name'] ?? medication!['name'] ?? '药品'} · '
                '${medication!['remind_time'] ?? medication!['schedule'] ?? ''} · '
                '${medication!['dose'] ?? medication!['dosage'] ?? ''}',
                style: const TextStyle(fontSize: 16, color: Color(0xFF424242)),
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        setState(() => medication = null);
                        _showToast('已记录');
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF43A047),
                        foregroundColor: Colors.white,
                        minimumSize: const Size(0, 44),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: const Text('已吃 ✓', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: PopupMenuButton<int>(
                      onSelected: (v) => _showToast('已推迟 $v 分钟'),
                      itemBuilder: (_) => const [
                        PopupMenuItem(value: 15, child: Text('推迟 15 分钟')),
                        PopupMenuItem(value: 30, child: Text('推迟 30 分钟')),
                        PopupMenuItem(value: 60, child: Text('推迟 60 分钟')),
                      ],
                      child: Container(
                        height: 44,
                        decoration: BoxDecoration(
                          color: Colors.white,
                          border: Border.all(color: const Color(0xFF1976D2)),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        alignment: Alignment.center,
                        child: const Text('推迟',
                            style: TextStyle(fontSize: 16, color: Color(0xFF1976D2))),
                      ),
                    ),
                  ),
                ],
              ),
            ] else
              const Text('继续保持，按时服药有助于健康哦 ~',
                  style: TextStyle(fontSize: 14, color: Color(0xFF666666))),
          ],
        ),
      ),
    );
  }

  Widget _buildSosAlertCard(Map<String, dynamic> alert) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Container(
        decoration: BoxDecoration(
          color: const Color(0xFFFFF5F5),
          border: Border.all(color: const Color(0xFFFFCDD2)),
          borderRadius: BorderRadius.circular(16),
        ),
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Text('🚨', style: TextStyle(fontSize: 22)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(alert['title'] ?? '',
                      style: const TextStyle(
                          fontSize: 18, fontWeight: FontWeight.w600, color: Color(0xFFC62828))),
                ),
              ],
            ),
            const SizedBox(height: 10),
            Text(alert['content'] ?? '',
                style: const TextStyle(fontSize: 15, color: Color(0xFF424242))),
            if ((alert['suggestion'] ?? '').toString().isNotEmpty) ...[
              const SizedBox(height: 8),
              Text('建议：${alert['suggestion']}',
                  style: const TextStyle(fontSize: 14, color: Color(0xFF666666))),
            ],
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: ElevatedButton(
                    onPressed: _callFamily,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFFE53935),
                      foregroundColor: Colors.white,
                      minimumSize: const Size(0, 44),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text('📞 呼叫家人',
                        style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  ),
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => _dismissAlert(alert['id']),
                    style: OutlinedButton.styleFrom(
                      foregroundColor: const Color(0xFF666666),
                      minimumSize: const Size(0, 44),
                      side: const BorderSide(color: Color(0xFFE0E0E0)),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text('我没事', style: TextStyle(fontSize: 16)),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
