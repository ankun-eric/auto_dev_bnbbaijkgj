// [PRD-健康档案路径统一 2026-05-16] Flutter 端按 H5 v2 信息架构完整重写
// 原文件备份为 health_profile_screen.dart.bak-2026-05-16，1 个月后清理
//
// 对齐 H5 v2 信息架构：
//   成员条 → Hero 卡 → 粘性 5 Tab → 今日数据 / 健康信息 / 用药计划 / 共管与提醒 / 健康事件
// 接口对齐：
//   /api/family/members、/api/health/profile/member/{id}、
//   /api/health-profile-v3/{id}/today-metrics、
//   /api/health-profile-v3/{id}/medication-plan、
//   /api/prd469/summary/{id}、/api/family/management
// 视觉规范：蓝白渐变主色 + 圆角 12/16 + 病历卡左侧 3px 竖线（对齐 BH_TOKENS）

import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class HealthProfileScreen extends StatefulWidget {
  const HealthProfileScreen({super.key});

  @override
  State<HealthProfileScreen> createState() => _HealthProfileScreenState();
}

class _HealthProfileScreenState extends State<HealthProfileScreen>
    with SingleTickerProviderStateMixin {
  final ApiService _apiService = ApiService();

  // ====== 设计 Token（对齐 H5 v2 BH_TOKENS：蓝白渐变） ======
  static const Color _brand50 = Color(0xFFEFF6FF);
  static const Color _brand100 = Color(0xFFDBEAFE);
  static const Color _brand200 = Color(0xFFBFDBFE);
  static const Color _brand500 = Color(0xFF4A9EE0);
  static const Color _brand600 = Color(0xFF2563EB);
  static const Color _brand700 = Color(0xFF1E40AF);
  static const Color _brand800 = Color(0xFF1E3A8A);
  static const Color _warn = Color(0xFFF59E0B);
  static const Color _cardLine = Color(0xFF22C55E);
  static const Color _cardLineWarn = Color(0xFFF59E0B);
  static const Color _textPrimary = Color(0xFF1F2937);
  static const Color _textSecondary = Color(0xFF6B7280);

  static const List<Map<String, String>> _tabs = [
    {'id': 'today-data', 'label': '今日数据'},
    {'id': 'health-info', 'label': '健康信息'},
    {'id': 'medication-plan', 'label': '用药计划'},
    {'id': 'care-reminder', 'label': '守护与提醒'},
    {'id': 'health-events', 'label': '健康事件'},
  ];

  late TabController _tabController;
  String _activeTab = 'today-data';

  List<Map<String, dynamic>> _members = [];
  int? _selectedMemberId;
  Map<String, dynamic>? _profile;
  Map<String, dynamic>? _todayMetrics;
  List<Map<String, dynamic>> _medications = [];
  List<Map<String, dynamic>> _heroMetrics = [];
  List<Map<String, dynamic>> _events = [];
  bool _isLinked = false;
  bool _loadingProfile = false;

  // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人资料完善弹窗 + 抽屉
  bool _selfNeedComplete = false;
  List<String> _selfMissingFields = [];
  bool _selfDialogShownInSession = false;
  Map<String, dynamic>? _selfInitialForDrawer;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: _tabs.length, vsync: this);
    _tabController.addListener(() {
      if (!_tabController.indexIsChanging) {
        setState(() => _activeTab = _tabs[_tabController.index]['id']!);
      }
    });
    _loadMembers();
    // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 拉本人完善状态
    _loadSelfNeedComplete();
  }

  Future<void> _loadSelfNeedComplete() async {
    try {
      final res = await _apiService.dio.get('/api/health-profile/self');
      if (!mounted) return;
      if (res.statusCode == 200 && res.data is Map) {
        final body = Map<String, dynamic>.from(res.data as Map);
        final data = body['data'] is Map
            ? Map<String, dynamic>.from(body['data'] as Map)
            : body;
        final need = data['needComplete'] == true;
        final missing = (data['missingFields'] as List?)
                ?.map((e) => e.toString())
                .toList() ??
            <String>[];
        setState(() {
          _selfNeedComplete = need;
          _selfMissingFields = missing;
          _selfInitialForDrawer = {
            'name': data['name'],
            'gender': data['gender'],
            'birthday': data['birthday'],
            'height': data['height'],
            'weight': data['weight'],
          };
        });
        _maybeShowSelfCompleteDialog();
      }
    } catch (_) {}
  }

  void _maybeShowSelfCompleteDialog() {
    if (_selfDialogShownInSession) return;
    if (!_selfNeedComplete) return;
    final m = _members.firstWhere(
      (x) => x['id'] == _selectedMemberId,
      orElse: () => <String, dynamic>{},
    );
    if (m['is_self'] != true) return;
    _selfDialogShownInSession = true;
    Future.delayed(const Duration(milliseconds: 500), () {
      if (!mounted) return;
      _showSelfCompleteDialog();
    });
  }

  void _showSelfCompleteDialog() {
    showDialog<void>(
      context: context,
      barrierDismissible: true,
      builder: (ctx) {
        return Dialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          insetPadding: const EdgeInsets.symmetric(horizontal: 32),
          child: Padding(
            padding: const EdgeInsets.fromLTRB(20, 22, 20, 18),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Stack(
                  alignment: Alignment.center,
                  children: [
                    const Text('完善健康档案',
                        style: TextStyle(
                            fontSize: 17, fontWeight: FontWeight.w700, color: _textPrimary)),
                    Positioned(
                      right: -8,
                      top: -10,
                      child: IconButton(
                        icon: const Icon(Icons.close, color: Color(0xFF94A3B8)),
                        onPressed: () => Navigator.pop(ctx),
                        splashRadius: 18,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 10),
                const Text(
                  '为了给您提供更精准的健康服务，请先完善您的基本资料（姓名、性别、出生日期）。',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 13, color: Color(0xFF475569), height: 1.6),
                ),
                const SizedBox(height: 18),
                Row(children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(ctx),
                      style: OutlinedButton.styleFrom(
                        backgroundColor: const Color(0xFFF1F5F9),
                        side: BorderSide.none,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(21)),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                      ),
                      child: const Text('稍后', style: TextStyle(color: _textPrimary)),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.pop(ctx);
                        _showSelfCompleteDrawer();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: _brand500,
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(21)),
                        padding: const EdgeInsets.symmetric(vertical: 10),
                      ),
                      child: const Text('去完善',
                          style: TextStyle(fontWeight: FontWeight.w700)),
                    ),
                  ),
                ]),
              ],
            ),
          ),
        );
      },
    );
  }

  void _showSelfCompleteDrawer() {
    final initial = _selfInitialForDrawer ?? {};
    final nameCtl = TextEditingController(
        text: (initial['name'] != null && initial['name'].toString() != '本人')
            ? initial['name'].toString()
            : '');
    final heightCtl = TextEditingController(
        text: initial['height'] != null ? '${initial['height']}' : '');
    final weightCtl = TextEditingController(
        text: initial['weight'] != null ? '${initial['weight']}' : '');
    String gender = '';
    final gRaw = initial['gender']?.toString() ?? '';
    if (gRaw == '男' || gRaw == 'male' || gRaw == 'M') gender = '男';
    else if (gRaw == '女' || gRaw == 'female' || gRaw == 'F') gender = '女';
    String birthday = (initial['birthday'] ?? '').toString();
    if (birthday.length > 10) birthday = birthday.substring(0, 10);

    bool moreOpen = false;
    bool submitting = false;
    final errs = {'name': false, 'gender': false, 'birthday': false};

    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFFF8FAFC),
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) {
        return StatefulBuilder(builder: (ctx, setS) {
          bool nameOk() {
            final s = nameCtl.text.trim();
            return s.isNotEmpty && s != '本人' && s.length <= 20;
          }

          bool canSubmit() => nameOk() && gender.isNotEmpty && birthday.isNotEmpty && !submitting;

          Future<void> doSubmit() async {
            final s = nameCtl.text.trim();
            final newErrs = <String, bool>{
              'name': !(s.isNotEmpty && s != '本人' && s.length <= 20),
              'gender': gender.isEmpty,
              'birthday': birthday.isEmpty,
            };
            if (newErrs.values.any((v) => v)) {
              setS(() {
                errs.addAll(newErrs);
              });
              return;
            }
            setS(() => submitting = true);
            try {
              final body = <String, dynamic>{
                'name': s,
                'gender': gender,
                'birthday': birthday,
              };
              if (heightCtl.text.isNotEmpty) {
                body['height'] = num.tryParse(heightCtl.text);
              }
              if (weightCtl.text.isNotEmpty) {
                body['weight'] = num.tryParse(weightCtl.text);
              }
              await _apiService.dio.put('/api/health-profile/self', data: body);
              if (mounted) {
                Navigator.pop(ctx);
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('保存成功')),
                );
                setState(() => _selfNeedComplete = false);
                _loadMembers();
                if (_selectedMemberId != null) _loadProfile(_selectedMemberId!);
              }
            } catch (e) {
              if (mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  const SnackBar(content: Text('保存失败')),
                );
              }
            } finally {
              setS(() => submitting = false);
            }
          }

          return Padding(
            padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
            child: Container(
              constraints:
                  BoxConstraints(maxHeight: MediaQuery.of(ctx).size.height * 0.92),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  // Head
                  Container(
                    padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                      border: Border(bottom: BorderSide(color: Color(0xFFE2E8F0))),
                    ),
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        GestureDetector(
                          onTap: () => Navigator.pop(ctx),
                          child: const Text('×',
                              style: TextStyle(fontSize: 22, color: Color(0xFF64748B))),
                        ),
                        const Text('完善健康档案',
                            style: TextStyle(
                                fontSize: 16, fontWeight: FontWeight.w700, color: _textPrimary)),
                        const SizedBox(width: 16),
                      ],
                    ),
                  ),
                  // Body
                  Flexible(
                    child: SingleChildScrollView(
                      padding: const EdgeInsets.fromLTRB(16, 16, 16, 16),
                      child: Column(children: [
                        // Tip
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                          decoration: BoxDecoration(
                            color: const Color(0xFFEFF6FF),
                            border: Border.all(color: const Color(0xFFBFDBFE)),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: const Text(
                            '为了给您提供更精准的健康服务，请先完善您的基本资料（姓名、性别、出生日期）。',
                            style: TextStyle(fontSize: 12, color: Color(0xFF1E40AF), height: 1.6),
                          ),
                        ),
                        const SizedBox(height: 12),
                        // Name
                        _completeSelfField(
                          label: '姓名',
                          required: true,
                          hasError: errs['name'] == true,
                          errMsg: '请填写姓名',
                          child: TextField(
                            controller: nameCtl,
                            maxLength: 20,
                            decoration: const InputDecoration(
                              hintText: '请输入姓名',
                              counterText: '',
                              border: OutlineInputBorder(
                                borderRadius: BorderRadius.all(Radius.circular(10)),
                              ),
                              isDense: true,
                              contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                            ),
                            onChanged: (_) => setS(() {
                              errs['name'] = false;
                            }),
                          ),
                        ),
                        // Gender
                        _completeSelfField(
                          label: '性别',
                          required: true,
                          hasError: errs['gender'] == true,
                          errMsg: '请选择性别',
                          child: Row(
                            children: ['男', '女'].map((g) {
                              final on = gender == g;
                              return Expanded(
                                child: Padding(
                                  padding: EdgeInsets.only(right: g == '男' ? 8 : 0),
                                  child: GestureDetector(
                                    onTap: () => setS(() {
                                      gender = g;
                                      errs['gender'] = false;
                                    }),
                                    child: Container(
                                      alignment: Alignment.center,
                                      padding: const EdgeInsets.symmetric(vertical: 8),
                                      decoration: BoxDecoration(
                                        color: on ? const Color(0xFFDBEAFE) : const Color(0xFFF1F5F9),
                                        borderRadius: BorderRadius.circular(8),
                                        border: Border.all(
                                          color: on ? const Color(0xFF38BDF8) : Colors.transparent,
                                          width: 1.5,
                                        ),
                                      ),
                                      child: Text(g,
                                          style: TextStyle(
                                              fontWeight: FontWeight.w600,
                                              color: on
                                                  ? const Color(0xFF0284C7)
                                                  : _textPrimary)),
                                    ),
                                  ),
                                ),
                              );
                            }).toList(),
                          ),
                        ),
                        // Birthday
                        _completeSelfField(
                          label: '出生日期',
                          required: true,
                          hasError: errs['birthday'] == true,
                          errMsg: '请选择出生日期',
                          child: InkWell(
                            onTap: () async {
                              final initial = DateTime.tryParse(birthday) ?? DateTime(1990, 1, 1);
                              final picked = await showDatePicker(
                                context: ctx,
                                initialDate: initial,
                                firstDate: DateTime(1900),
                                lastDate: DateTime.now(),
                              );
                              if (picked != null) {
                                setS(() {
                                  birthday =
                                      '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}';
                                  errs['birthday'] = false;
                                });
                              }
                            },
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                              decoration: BoxDecoration(
                                color: Colors.white,
                                border: Border.all(color: const Color(0xFFE2E8F0)),
                                borderRadius: BorderRadius.circular(10),
                              ),
                              child: Row(
                                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                children: [
                                  Text(birthday.isEmpty ? '请选择' : birthday,
                                      style: TextStyle(
                                          color: birthday.isEmpty
                                              ? const Color(0xFF94A3B8)
                                              : _textPrimary)),
                                  const Text('›', style: TextStyle(color: Color(0xFF94A3B8))),
                                ],
                              ),
                            ),
                          ),
                        ),
                        // Collapsible
                        Container(
                          margin: const EdgeInsets.only(top: 4),
                          decoration: BoxDecoration(
                            color: Colors.white,
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Column(children: [
                            InkWell(
                              onTap: () => setS(() => moreOpen = !moreOpen),
                              child: Padding(
                                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
                                child: Row(
                                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                                  children: [
                                    const Text('其他（选填）',
                                        style: TextStyle(
                                            fontSize: 14,
                                            fontWeight: FontWeight.w600,
                                            color: Color(0xFF475569))),
                                    Text(moreOpen ? '⌄' : '›',
                                        style: const TextStyle(color: Color(0xFF94A3B8))),
                                  ],
                                ),
                              ),
                            ),
                            if (moreOpen)
                              Padding(
                                padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                                child: Column(children: [
                                  Row(children: [
                                    Expanded(
                                      child: TextField(
                                        controller: heightCtl,
                                        keyboardType: TextInputType.number,
                                        decoration: const InputDecoration(
                                          labelText: '身高(cm)',
                                          isDense: true,
                                          border: OutlineInputBorder(),
                                        ),
                                      ),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(
                                      child: TextField(
                                        controller: weightCtl,
                                        keyboardType: TextInputType.number,
                                        decoration: const InputDecoration(
                                          labelText: '体重(kg)',
                                          isDense: true,
                                          border: OutlineInputBorder(),
                                        ),
                                      ),
                                    ),
                                  ]),
                                ]),
                              ),
                          ]),
                        ),
                      ]),
                    ),
                  ),
                  // Foot
                  Container(
                    padding: const EdgeInsets.fromLTRB(16, 10, 16, 16),
                    decoration: const BoxDecoration(
                      color: Colors.white,
                      border: Border(top: BorderSide(color: Color(0xFFE2E8F0))),
                    ),
                    child: SizedBox(
                      width: double.infinity,
                      height: 46,
                      child: ElevatedButton(
                        onPressed: canSubmit() ? doSubmit : null,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _brand500,
                          disabledBackgroundColor: const Color(0xFFCBD5E1),
                          foregroundColor: Colors.white,
                          disabledForegroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(23)),
                        ),
                        child: Text(submitting ? '保存中...' : '保存',
                            style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15)),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          );
        });
      },
    );
  }

  static Widget _completeSelfField({
    required String label,
    bool required = false,
    required Widget child,
    bool hasError = false,
    String errMsg = '',
  }) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              SizedBox(
                width: 90,
                child: Row(children: [
                  if (required)
                    const Text('*',
                        style: TextStyle(color: Color(0xFFEF4444), fontSize: 14)),
                  Text(label,
                      style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: hasError
                              ? const Color(0xFFEF4444)
                              : const Color(0xFF475569))),
                ]),
              ),
              Expanded(child: child),
            ],
          ),
          if (hasError && errMsg.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(left: 90, top: 4),
              child: Text(errMsg,
                  style: const TextStyle(fontSize: 11, color: Color(0xFFEF4444))),
            ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  // ====== 数据加载 ======
  Future<void> _loadMembers() async {
    try {
      final res = await _apiService.getFamilyMembers();
      if (res.statusCode == 200 && mounted) {
        final raw = res.data is Map ? (res.data['items'] as List? ?? []) : [];
        final items = raw
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        if (items.isNotEmpty) {
          final self = items.firstWhere(
            (m) => m['is_self'] == true,
            orElse: () => items.first,
          );
          setState(() {
            _members = items;
            _selectedMemberId = self['id'] as int?;
          });
          if (_selectedMemberId != null) _loadProfile(_selectedMemberId!);
          // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29] 本人 Tab 激活后尝试弹窗
          _maybeShowSelfCompleteDialog();
        }
      }
    } catch (_) {}
  }

  Future<void> _loadProfile(int memberId) async {
    setState(() => _loadingProfile = true);
    try {
      final res = await _apiService.dio.get('/api/health/profile/member/$memberId');
      if (mounted && res.statusCode == 200) {
        final data = (res.data is Map) ? Map<String, dynamic>.from(res.data) : null;
        setState(() => _profile = data);
        final pid = data?['id'] as int?;
        if (pid != null) {
          _loadTodayMetrics(pid);
          _loadMedicationPlan(pid);
          _loadHeroSummary(pid);
          _loadEvents(pid);
        }
        _loadLinkStatus(memberId);
      }
    } catch (_) {
      if (mounted) setState(() => _profile = null);
    } finally {
      if (mounted) setState(() => _loadingProfile = false);
    }
  }

  Future<void> _loadTodayMetrics(int profileId) async {
    try {
      final res = await _apiService.dio
          .get('/api/health-profile-v3/$profileId/today-metrics');
      if (mounted && res.statusCode == 200 && res.data is Map) {
        setState(() => _todayMetrics = Map<String, dynamic>.from(res.data));
      }
    } catch (_) {}
  }

  Future<void> _loadMedicationPlan(int profileId) async {
    try {
      final res = await _apiService.dio
          .get('/api/health-profile-v3/$profileId/medication-plan');
      if (mounted && res.statusCode == 200 && res.data is Map) {
        final items = (res.data['items'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        setState(() => _medications = items);
      }
    } catch (_) {
      if (mounted) setState(() => _medications = []);
    }
  }

  Future<void> _loadHeroSummary(int profileId) async {
    try {
      final res = await _apiService.dio.get('/api/prd469/summary/$profileId');
      if (mounted && res.statusCode == 200 && res.data is Map) {
        final raw = res.data['hero_metrics'] as List? ?? [];
        setState(() => _heroMetrics =
            raw.map((e) => Map<String, dynamic>.from(e as Map)).toList());
      }
    } catch (_) {}
  }

  Future<void> _loadEvents(int profileId) async {
    try {
      final res = await _apiService.dio
          .get('/api/health-profile-v3/$profileId/events');
      if (mounted && res.statusCode == 200 && res.data is Map) {
        final items = (res.data['items'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        setState(() => _events = items);
      }
    } catch (_) {
      if (mounted) setState(() => _events = []);
    }
  }

  Future<void> _loadLinkStatus(int memberId) async {
    try {
      final res = await _apiService.getFamilyManagementList();
      if (mounted && res.statusCode == 200) {
        List items = [];
        final d = res.data;
        if (d is Map && d['items'] is List) items = d['items'] as List;
        else if (d is List) items = d;
        final linked = items.any((it) =>
            it is Map &&
            it['managed_member_id'] == memberId &&
            it['status'] == 'active');
        setState(() => _isLinked = linked);
      }
    } catch (_) {}
  }

  // ====== UI ======
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF0F7FF),
      appBar: AppBar(
        title: const Text('健康档案', style: TextStyle(color: Colors.white)),
        backgroundColor: _brand600,
        elevation: 0,
        iconTheme: const IconThemeData(color: Colors.white),
        actions: [
          IconButton(
            tooltip: '设备管理',
            icon: const Icon(Icons.watch_outlined, color: Colors.white),
            onPressed: () {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('设备管理入口暂未集成')),
              );
            },
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          children: [
            _buildMemberBar(),
            Expanded(
              child: NestedScrollView(
                headerSliverBuilder: (_, __) => [
                  SliverToBoxAdapter(child: _buildHeroCard()),
                  SliverPersistentHeader(
                    pinned: true,
                    delegate: _StickyTabsDelegate(
                      TabBar(
                        controller: _tabController,
                        isScrollable: true,
                        labelColor: _brand600,
                        unselectedLabelColor: _textSecondary,
                        indicatorColor: _brand600,
                        indicatorWeight: 3,
                        labelStyle: const TextStyle(
                            fontSize: 15, fontWeight: FontWeight.w700),
                        unselectedLabelStyle:
                            const TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
                        tabs: _tabs
                            .map((t) => Tab(text: t['label']))
                            .toList(),
                      ),
                    ),
                  ),
                ],
                body: TabBarView(
                  controller: _tabController,
                  children: [
                    _buildTodayTab(),
                    _buildHealthInfoTab(),
                    _buildMedicationTab(),
                    _buildCareReminderTab(),
                    _buildHealthEventsTab(),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // 成员条
  Widget _buildMemberBar() {
    return Container(
      color: _brand50,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
      height: 88,
      child: ListView(
        scrollDirection: Axis.horizontal,
        children: [
          ..._members.map((m) {
            final active = m['id'] == _selectedMemberId;
            final isSelf = m['is_self'] == true;
            final linked = m['member_user_id'] != null;
            return GestureDetector(
              onTap: () {
                setState(() => _selectedMemberId = m['id'] as int?);
                if (_selectedMemberId != null) _loadProfile(_selectedMemberId!);
              },
              child: Container(
                margin: const EdgeInsets.only(right: 12),
                width: 64,
                child: Column(
                  children: [
                    Stack(
                      clipBehavior: Clip.none,
                      children: [
                        Container(
                          width: 48, height: 48,
                          decoration: BoxDecoration(
                            shape: BoxShape.circle,
                            color: active ? _brand500 : Colors.white,
                            border: Border.all(
                              color: active ? _brand600 : _brand200,
                              width: active ? 2 : 1,
                            ),
                            boxShadow: active
                                ? [BoxShadow(color: _brand500.withOpacity(.25), blurRadius: 12, offset: const Offset(0, 4))]
                                : null,
                          ),
                          alignment: Alignment.center,
                          child: Text(
                            isSelf ? '🙂' : _relationEmoji(m['relation_type_name'] ?? m['relationship_type'] ?? ''),
                            style: const TextStyle(fontSize: 22),
                          ),
                        ),
                        if (linked)
                          Positioned(
                            top: -2, right: -2,
                            child: Container(
                              width: 10, height: 10,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: _cardLine,
                                border: Border.all(color: Colors.white, width: 2),
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      isSelf ? '本人' : (m['relation_type_name'] ?? m['nickname'] ?? '家人').toString(),
                      style: const TextStyle(fontSize: 12, color: _brand800),
                      maxLines: 1, overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            );
          }),
          GestureDetector(
            onTap: _onAddMember,
            child: Column(
              children: [
                Container(
                  width: 48, height: 48,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: Colors.white,
                    border: Border.all(color: _brand500, width: 2, style: BorderStyle.solid),
                  ),
                  alignment: Alignment.center,
                  child: const Text('+', style: TextStyle(fontSize: 24, color: _brand600)),
                ),
                const SizedBox(height: 4),
                const Text('添加', style: TextStyle(fontSize: 12, color: _brand800)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // Hero 卡
  Widget _buildHeroCard() {
    if (_profile == null) {
      return const Padding(
        padding: EdgeInsets.all(16),
        child: SizedBox(height: 100, child: Center(child: CircularProgressIndicator())),
      );
    }
    final p = _profile!;
    final age = _calcAge(p['birthday']);
    final baseLine = [
      p['gender'] ?? '',
      age != null ? '$age 岁' : '',
      p['height'] != null ? '${p['height']} cm' : '',
      p['weight'] != null ? '${p['weight']} kg' : '',
      p['blood_type'] != null && (p['blood_type'] as String).isNotEmpty
          ? '${p['blood_type']}型' : '',
    ].where((s) => (s as String).isNotEmpty).join(' · ');

    final metrics = _heroMetrics.isNotEmpty
        ? _heroMetrics
        : <Map<String, dynamic>>[
            {'label': '既往病史', 'count': 0, 'unit': '项'},
            {'label': '过敏史', 'count': 0, 'unit': '项'},
            {'label': '家族遗传', 'count': 0, 'unit': '项'},
            {'label': '长期用药', 'count': 0, 'unit': '种'},
          ];

    final selectedMember = _members.firstWhere(
      (m) => m['id'] == _selectedMemberId,
      orElse: () => <String, dynamic>{},
    );
    final isSelf = selectedMember['is_self'] == true;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 12),
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            begin: Alignment.topLeft, end: Alignment.bottomRight,
            colors: [_brand500, _brand600],
          ),
          borderRadius: BorderRadius.circular(16),
          boxShadow: [BoxShadow(color: _brand600.withOpacity(.18), blurRadius: 16, offset: const Offset(0, 6))],
        ),
        child: Stack(
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Container(
                      width: 56, height: 56,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.white.withOpacity(.25),
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        isSelf ? '🙂' : _relationEmoji(selectedMember['relation_type_name'] ?? ''),
                        style: const TextStyle(fontSize: 28),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(p['name']?.toString().isNotEmpty == true ? p['name'] : '未填',
                            style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Colors.white)),
                          const SizedBox(height: 4),
                          Row(children: [
                            Text(
                              isSelf ? '本人' : (selectedMember['relation_type_name'] ?? '家庭成员').toString(),
                              style: TextStyle(fontSize: 12, color: Colors.white.withOpacity(.9)),
                            ),
                            if (_isLinked) ...[
                              const SizedBox(width: 8),
                              Container(
                                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                                decoration: BoxDecoration(
                                  color: Colors.white.withOpacity(.3),
                                  borderRadius: BorderRadius.circular(10),
                                ),
                                child: const Text('✓ 已关联', style: TextStyle(fontSize: 10, color: Colors.white, fontWeight: FontWeight.w600)),
                              ),
                            ]
                          ]),
                          const SizedBox(height: 4),
                          Text(baseLine.isEmpty ? '未填基础信息' : baseLine,
                            style: TextStyle(fontSize: 11, color: Colors.white.withOpacity(.75))),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 16),
                Row(
                  children: metrics.take(4).map<Widget>((m) => Expanded(
                    child: Container(
                      margin: const EdgeInsets.symmetric(horizontal: 4),
                      padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 4),
                      decoration: BoxDecoration(
                        color: Colors.white.withOpacity(.18),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Column(
                        children: [
                          Text('${m['count']}', style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w700, color: Colors.white)),
                          const SizedBox(height: 2),
                          Text('${m['label']}', style: TextStyle(fontSize: 10, color: Colors.white.withOpacity(.85))),
                        ],
                      ),
                    ),
                  )).toList(),
                ),
              ],
            ),
            Positioned(
              top: 0, right: 0,
              child: GestureDetector(
                onTap: _onEditHero,
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                    color: Colors.white.withOpacity(.25),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: Colors.white.withOpacity(.4)),
                  ),
                  child: const Text('✏️ 编辑', style: TextStyle(color: Colors.white, fontSize: 12, fontWeight: FontWeight.w500)),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  // Tab 1：今日数据
  Widget _buildTodayTab() {
    final tm = _todayMetrics;
    final med = (tm?['medication'] is Map ? tm!['medication'] : null) as Map?;
    final cells = [
      {
        'id': 'blood_pressure', 'label': '血压', 'unit': 'mmHg', 'icon': '💓',
        'value': () {
          final v = (tm?['blood_pressure'] is Map) ? tm!['blood_pressure']['value'] : null;
          if (v is Map) return '${v['systolic'] ?? '-'}/${v['diastolic'] ?? '-'}';
          return '—';
        }(),
        'abnormal': (tm?['blood_pressure'] is Map) && tm!['blood_pressure']['is_abnormal'] == true,
      },
      {
        'id': 'blood_glucose', 'label': '血糖', 'unit': 'mmol/L', 'icon': '🩸',
        'value': _readMetric(tm, 'blood_glucose'),
        'abnormal': (tm?['blood_glucose'] is Map) && tm!['blood_glucose']['is_abnormal'] == true,
      },
      {
        'id': 'heart_rate', 'label': '心率', 'unit': 'bpm', 'icon': '❤️',
        'value': _readMetric(tm, 'heart_rate'),
        'abnormal': (tm?['heart_rate'] is Map) && tm!['heart_rate']['is_abnormal'] == true,
      },
      // [PRD-SPO2-CARD-V1 2026-06-02] 血氧插在睡眠前面，顺序与关怀模式对齐（血压/血糖/心率/血氧/睡眠）
      () {
        final sp = (tm?['spo2'] is Map) ? tm!['spo2'] as Map : null;
        final raw = (sp != null && sp['value'] is Map) ? sp['value']['value'] : null;
        final spVal = (raw is num) ? raw.toDouble() : (raw is String ? double.tryParse(raw) : null);
        final cap = _spo2Cap(spVal);
        return {
          'id': 'spo2', 'label': '血氧', 'unit': '%', 'icon': '🫁',
          'value': (spVal != null && spVal > 0)
              ? (spVal == spVal.roundToDouble() ? spVal.toInt().toString() : spVal.toString())
              : '—',
          'abnormal': (sp != null) && sp['is_abnormal'] == true,
          'capLabel': cap?['label'] ?? '',
          'capColor': cap?['color'] ?? '',
        };
      }(),
      // [PRD-SLEEP-ALIGN-BP-V1 2026-06-02] 睡眠四档胶囊（充足蓝 / 偏少·偏多黄 / 不足橙）+ 大号时长，对齐血压
      () {
        final sl = (tm?['sleep'] is Map) ? tm!['sleep'] as Map : null;
        final raw = (sl != null && sl['value'] is Map) ? sl['value']['duration_h'] : null;
        final slVal = (raw is num) ? raw.toDouble() : (raw is String ? double.tryParse(raw) : null);
        final cap = _sleepCap(slVal);
        return {
          'id': 'sleep', 'label': '睡眠', 'unit': 'h', 'icon': '🌙',
          'value': (slVal != null && slVal > 0 && slVal <= 24)
              ? (slVal == slVal.roundToDouble() ? slVal.toInt().toString() : slVal.toString())
              : '—',
          // C2 异常竖条：睡眠不正常（偏少/不足/偏多）时显示
          'abnormal': cap != null ? (cap['abnormal'] == true) : ((sl != null) && sl['is_abnormal'] == true),
          'capLabel': cap?['label'] ?? '',
          'capColor': cap?['color'] ?? '',
        };
      }(),
    ];

    final checked = med?['checked'] ?? 0;
    final total = med?['total'] ?? 0;
    final hasOverdue = med?['has_overdue'] == true;
    final percent = (total is int && total > 0)
        ? ((checked as int) / total).clamp(0.0, 1.0)
        : 0.0;

    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Text('今日数据',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600, color: _brand700)),
        ),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          itemCount: cells.length + 1,
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            crossAxisSpacing: 12,
            mainAxisSpacing: 12,
            childAspectRatio: 1.45,
          ),
          itemBuilder: (_, i) {
            if (i < cells.length) {
              final c = cells[i];
              return _v5Card(
                abnormal: c['abnormal'] as bool,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                      Text('${c['icon']} ${c['label']}', style: const TextStyle(fontSize: 13, color: _textSecondary)),
                      // [PRD-SPO2-CARD-V1 2026-06-02] 血氧三档胶囊（正常蓝 / 偏低·偏低明显橙），其余卡片回退「异常」标签
                      if ((c['capLabel'] as String?)?.isNotEmpty == true)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: c['capColor'] == 'orange'
                                ? const Color(0xFFF97316)
                                : (c['capColor'] == 'yellow'
                                    ? const Color(0xFFF5B73D)
                                    : const Color(0xFF3B82F6)),
                            borderRadius: BorderRadius.circular(999),
                          ),
                          child: Text('${c['capLabel']}', style: const TextStyle(fontSize: 10, color: Colors.white, fontWeight: FontWeight.w700)),
                        )
                      else if (c['abnormal'] as bool)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(color: _warn, borderRadius: BorderRadius.circular(6)),
                          child: const Text('异常', style: TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.w600)),
                        ),
                    ]),
                    const SizedBox(height: 8),
                    Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                      Text('${c['value']}', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: _textPrimary)),
                      const SizedBox(width: 4),
                      Padding(
                        padding: const EdgeInsets.only(bottom: 3),
                        child: Text('${c['unit']}', style: const TextStyle(fontSize: 13, color: _textSecondary)),
                      ),
                    ]),
                  ],
                ),
              );
            }
            return GestureDetector(
              onTap: () => _tabController.animateTo(2),
              child: _v5Card(
                abnormal: hasOverdue,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                      const Text('💊 用药提醒', style: TextStyle(fontSize: 13, color: _textSecondary)),
                      if (hasOverdue)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(color: _warn, borderRadius: BorderRadius.circular(6)),
                          child: const Text('待服', style: TextStyle(fontSize: 11, color: Colors.white, fontWeight: FontWeight.w600)),
                        ),
                    ]),
                    const SizedBox(height: 8),
                    Row(crossAxisAlignment: CrossAxisAlignment.end, children: [
                      Text('$checked/$total', style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w700, color: _textPrimary)),
                      const SizedBox(width: 4),
                      const Padding(
                        padding: EdgeInsets.only(bottom: 3),
                        child: Text('已服', style: TextStyle(fontSize: 13, color: _textSecondary)),
                      ),
                    ]),
                    const SizedBox(height: 8),
                    ClipRRect(
                      borderRadius: BorderRadius.circular(3),
                      child: LinearProgressIndicator(
                        value: percent,
                        minHeight: 6,
                        backgroundColor: _brand100,
                        valueColor: const AlwaysStoppedAnimation<Color>(_brand600),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ],
    );
  }

  // Tab 2：健康信息
  Widget _buildHealthInfoTab() {
    final p = _profile ?? {};
    final chronic = _normList(p['chronic_diseases']);
    final allergy = _normList(p['allergies']);
    final genetic = _normList(p['genetic_diseases']);
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        _infoCard('🏥 既往病史', chronic.isEmpty ? '未填写' : chronic.join('、')),
        _infoCard('⚠️ 过敏史', allergy.isEmpty ? '未填写' : allergy.join('、')),
        _infoCard('🧬 家族遗传病史', genetic.isEmpty ? '未填写' : genetic.join('、')),
        _infoCard('🧘 个人习惯',
          '吸烟：${p['smoking'] ?? '未填'}    饮酒：${p['drinking'] ?? '未填'}'),
        const SizedBox(height: 12),
        SizedBox(
          height: 48,
          child: ElevatedButton(
            onPressed: _onEditHero,
            style: ElevatedButton.styleFrom(
              backgroundColor: _brand600, foregroundColor: Colors.white,
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
            ),
            child: const Text('编辑健康信息', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
          ),
        ),
      ],
    );
  }

  // Tab 3：用药计划
  Widget _buildMedicationTab() {
    if (_medications.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(40),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text('💊', style: TextStyle(fontSize: 48)),
              const SizedBox(height: 12),
              const Text('暂无用药计划', style: TextStyle(color: _textSecondary, fontSize: 14)),
              const SizedBox(height: 16),
              OutlinedButton(
                onPressed: _onAddMedication,
                child: const Text('+ 添加用药'),
              ),
            ],
          ),
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _medications.length,
      itemBuilder: (_, i) {
        final m = _medications[i];
        final chips = (m['time_chips'] as List? ?? [])
            .map((e) => Map<String, dynamic>.from(e as Map))
            .toList();
        return Container(
          margin: const EdgeInsets.only(bottom: 12),
          child: _v5Card(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                  Text('${m['drug_name'] ?? '药品'}',
                    style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: _textPrimary)),
                  Text('${m['dosage'] ?? ''}',
                    style: const TextStyle(fontSize: 12, color: _textSecondary)),
                ]),
                const SizedBox(height: 6),
                Text('本周完成率 ${m['weekly_completed'] ?? 0}/${m['weekly_total'] ?? 0}'
                     '（${m['weekly_rate'] ?? 0}%）',
                  style: const TextStyle(fontSize: 12, color: _textSecondary)),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 6, runSpacing: 6,
                  children: chips.map<Widget>((chip) {
                    final checked = chip['checked'] == true;
                    return Container(
                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                      decoration: BoxDecoration(
                        color: checked ? _cardLine : const Color(0xFFF3F4F6),
                        borderRadius: BorderRadius.circular(10),
                      ),
                      child: Text('${chip['scheduled_time'] ?? ''}',
                        style: TextStyle(
                          fontSize: 12,
                          color: checked ? Colors.white : _textSecondary,
                        )),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  // Tab 4：共管与提醒
  Widget _buildCareReminderTab() {
    final selectedMember = _members.firstWhere(
      (m) => m['id'] == _selectedMemberId,
      orElse: () => <String, dynamic>{},
    );
    final isSelf = selectedMember['is_self'] == true;
    final med = (_todayMetrics?['medication'] is Map ? _todayMetrics!['medication'] : null) as Map?;
    return ListView(
      padding: const EdgeInsets.all(12),
      children: [
        _v5Card(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('🔗 家庭守护', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: _textPrimary)),
              const SizedBox(height: 8),
              if (isSelf)
                const Text('本人档案默认不需要守护关系', style: TextStyle(color: _textSecondary, fontSize: 13))
              else if (!_isLinked) ...[
                const Text('邀请本人关联后，对方可同步查看和管理此健康档案',
                    style: TextStyle(color: _textSecondary, fontSize: 13)),
                const SizedBox(height: 12),
                ElevatedButton(
                  onPressed: _onInviteLink,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _brand600, foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
                  ),
                  child: const Text('邀请本人关联'),
                ),
              ] else ...[
                Row(children: [
                  Container(width: 8, height: 8,
                    decoration: const BoxDecoration(shape: BoxShape.circle, color: _cardLine)),
                  const SizedBox(width: 6),
                  const Text('已关联', style: TextStyle(color: Color(0xFF16A34A), fontSize: 13)),
                  const Spacer(),
                  TextButton(
                    onPressed: _onUnlink,
                    child: const Text('解除关联', style: TextStyle(color: Color(0xFFDC2626))),
                  ),
                ]),
              ],
            ],
          ),
        ),
        const SizedBox(height: 12),
        _v5Card(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('⏰ 用药提醒', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: _textPrimary)),
              const SizedBox(height: 8),
              Row(children: [
                Text('今日已完成 ${med?['checked'] ?? 0} / ${med?['total'] ?? 0}',
                    style: const TextStyle(color: _textSecondary, fontSize: 13)),
                if (med?['has_overdue'] == true) ...[
                  const SizedBox(width: 8),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFEF3C7),
                      borderRadius: BorderRadius.circular(8),
                    ),
                    child: const Text('有待服', style: TextStyle(fontSize: 11, color: Color(0xFFB45309))),
                  ),
                ]
              ]),
            ],
          ),
        ),
      ],
    );
  }

  // Tab 5：健康事件
  Widget _buildHealthEventsTab() {
    if (_events.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(40),
          child: Text('暂无健康事件记录', style: TextStyle(color: _textSecondary)),
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(12),
      itemCount: _events.length,
      itemBuilder: (_, i) {
        final e = _events[i];
        return Container(
          margin: const EdgeInsets.only(bottom: 10),
          child: _v5Card(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('${e['occurred_at'] ?? ''}', style: const TextStyle(fontSize: 11, color: _textSecondary)),
                const SizedBox(height: 4),
                Text('${e['title'] ?? ''}', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: _textPrimary)),
                if (e['description'] != null && (e['description'] as String).isNotEmpty) ...[
                  const SizedBox(height: 4),
                  Text('${e['description']}', style: const TextStyle(fontSize: 12, color: Color(0xFF4B5563))),
                ]
              ],
            ),
          ),
        );
      },
    );
  }

  // ====== 通用组件 ======
  Widget _v5Card({required Widget child, bool abnormal = false}) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border(
          left: BorderSide(color: abnormal ? _cardLineWarn : _cardLine, width: 3),
        ),
        boxShadow: [BoxShadow(color: _brand500.withOpacity(.08), blurRadius: 12, offset: const Offset(0, 4))],
      ),
      padding: const EdgeInsets.all(14),
      child: child,
    );
  }

  Widget _infoCard(String title, String content) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: _v5Card(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: _textPrimary)),
            const SizedBox(height: 8),
            Text(content, style: const TextStyle(fontSize: 13, color: Color(0xFF4B5563))),
          ],
        ),
      ),
    );
  }

  // ====== 事件 ======
  void _onAddMember() {
    showDialog(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('添加家庭成员'),
        content: const Text('请前往 H5 端「健康档案 → 添加家庭成员」页面完成添加。'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: const Text('知道了')),
        ],
      ),
    );
  }

  void _onAddMedication() {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('请前往 H5 端「健康档案 → 用药计划 → 添加用药」')),
    );
  }

  Future<void> _onInviteLink() async {
    if (_selectedMemberId == null) return;
    try {
      final res = await _apiService.dio.post(
        '/api/family/invite-link',
        data: {'member_id': _selectedMemberId},
      );
      String code = '';
      if (res.data is Map) {
        code = (res.data['code'] ?? res.data['data']?['code'] ?? '').toString();
      }
      if (mounted) {
        showDialog(
          context: context,
          builder: (_) => AlertDialog(
            title: const Text('邀请已生成'),
            content: SelectableText(code.isEmpty ? '邀请已发送，请前往家庭管理查看' : '邀请码：$code'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('知道了')),
            ],
          ),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('邀请失败，请稍后重试')),
        );
      }
    }
  }

  Future<void> _onUnlink() async {
    if (_selectedMemberId == null) return;
    final ok = await showDialog<bool>(
      context: context,
      builder: (_) => AlertDialog(
        title: const Text('解除关联'),
        content: const Text('解除后对方将无法继续查看此档案，是否继续？'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('取消')),
          TextButton(onPressed: () => Navigator.pop(context, true), child: const Text('确定')),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _apiService.dio.delete('/api/family/management/$_selectedMemberId');
      if (mounted) {
        setState(() => _isLinked = false);
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('已解除')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('操作失败')),
        );
      }
    }
  }

  void _onEditHero() {
    final p = _profile ?? {};
    final nameCtl = TextEditingController(text: '${p['name'] ?? ''}');
    final heightCtl = TextEditingController(text: p['height'] != null ? '${p['height']}' : '');
    final weightCtl = TextEditingController(text: p['weight'] != null ? '${p['weight']}' : '');
    String gender = p['gender'] ?? '';
    String birthday = p['birthday'] ?? '';
    String bloodType = p['blood_type'] ?? '';

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      builder: (ctx) => StatefulBuilder(builder: (ctx, setS) {
        return Padding(
          padding: EdgeInsets.only(bottom: MediaQuery.of(ctx).viewInsets.bottom),
          child: Container(
            constraints: BoxConstraints(maxHeight: MediaQuery.of(ctx).size.height * .85),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
                  decoration: const BoxDecoration(
                    border: Border(bottom: BorderSide(color: _brand100)),
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Text('编辑基本信息', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w700)),
                      GestureDetector(
                        onTap: () => Navigator.pop(ctx),
                        child: const Text('×', style: TextStyle(fontSize: 22, color: Color(0xFF9CA3AF))),
                      ),
                    ],
                  ),
                ),
                Flexible(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(16),
                    child: Column(children: [
                      _row('姓名', TextField(controller: nameCtl, decoration: const InputDecoration(hintText: '请输入姓名'), maxLength: 20), required: true),
                      _row('性别', Wrap(spacing: 8, children: ['男', '女', '其他'].map((g) {
                        final on = gender == g;
                        return GestureDetector(
                          onTap: () => setS(() => gender = g),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                            decoration: BoxDecoration(
                              color: on ? _brand500 : const Color(0xFFF3F4F6),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Text(g, style: TextStyle(color: on ? Colors.white : const Color(0xFF4B5563))),
                          ),
                        );
                      }).toList()), required: true),
                      _row('生日', InkWell(
                        onTap: () async {
                          final initialDate = DateTime.tryParse(birthday) ?? DateTime(1990);
                          final picked = await showDatePicker(
                            context: ctx,
                            initialDate: initialDate,
                            firstDate: DateTime(1900),
                            lastDate: DateTime.now(),
                          );
                          if (picked != null) {
                            setS(() => birthday = '${picked.year}-${picked.month.toString().padLeft(2, '0')}-${picked.day.toString().padLeft(2, '0')}');
                          }
                        },
                        child: Container(
                          padding: const EdgeInsets.symmetric(vertical: 10),
                          alignment: Alignment.centerRight,
                          child: Text(birthday.isEmpty ? '请选择' : birthday,
                            style: TextStyle(color: birthday.isEmpty ? const Color(0xFF9CA3AF) : _textPrimary)),
                        ),
                      ), required: true),
                      _row('身高 (cm)', TextField(controller: heightCtl, keyboardType: TextInputType.number)),
                      _row('体重 (kg)', TextField(controller: weightCtl, keyboardType: TextInputType.number)),
                      _row('血型', Wrap(spacing: 8, children: ['A', 'B', 'AB', 'O', '未知'].map((b) {
                        final on = bloodType == b;
                        return GestureDetector(
                          onTap: () => setS(() => bloodType = b),
                          child: Container(
                            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
                            decoration: BoxDecoration(
                              color: on ? _brand500 : const Color(0xFFF3F4F6),
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: Text(b, style: TextStyle(color: on ? Colors.white : const Color(0xFF4B5563))),
                          ),
                        );
                      }).toList())),
                    ]),
                  ),
                ),
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: const BoxDecoration(
                    border: Border(top: BorderSide(color: _brand100)),
                  ),
                  child: Row(children: [
                    Expanded(
                      child: OutlinedButton(
                        onPressed: () => Navigator.pop(ctx),
                        style: OutlinedButton.styleFrom(
                          side: const BorderSide(color: _brand200),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        child: const Text('取消'),
                      ),
                    ),
                    const SizedBox(width: 12),
                    Expanded(
                      child: ElevatedButton(
                        onPressed: () async {
                          // [PRD-HEALTH-PROFILE-SELF-COMPLETE 2026-05-29 §6] Hero 编辑三项必填
                          final nm = nameCtl.text.trim();
                          if (nm.isEmpty || nm == '本人' || nm.length > 20) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('请填写姓名')),
                            );
                            return;
                          }
                          if (gender.isEmpty) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('请选择性别')),
                            );
                            return;
                          }
                          if (birthday.isEmpty) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(content: Text('请选择出生日期')),
                            );
                            return;
                          }
                          try {
                            await _apiService.dio.put(
                              '/api/health/profile/member/$_selectedMemberId',
                              data: {
                                'name': nameCtl.text,
                                'gender': gender,
                                'birthday': birthday,
                                'height': heightCtl.text.isNotEmpty ? num.tryParse(heightCtl.text) : null,
                                'weight': weightCtl.text.isNotEmpty ? num.tryParse(weightCtl.text) : null,
                                'blood_type': bloodType,
                              },
                            );
                            if (mounted) {
                              Navigator.pop(ctx);
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('已保存')),
                              );
                              if (_selectedMemberId != null) _loadProfile(_selectedMemberId!);
                            }
                          } catch (_) {
                            if (mounted) {
                              ScaffoldMessenger.of(context).showSnackBar(
                                const SnackBar(content: Text('保存失败')),
                              );
                            }
                          }
                        },
                        style: ElevatedButton.styleFrom(
                          backgroundColor: _brand500, foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                          padding: const EdgeInsets.symmetric(vertical: 12),
                        ),
                        child: const Text('保存'),
                      ),
                    ),
                  ]),
                ),
              ],
            ),
          ),
        );
      }),
    );
  }

  Widget _row(String label, Widget control, {bool required = false}) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 8),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: Color(0xFFF3F4F6))),
      ),
      child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
        SizedBox(
          width: 100,
          child: Row(children: [
            if (required)
              const Text('*',
                  style: TextStyle(color: Color(0xFFEF4444), fontWeight: FontWeight.w700)),
            Text(label, style: const TextStyle(color: Color(0xFF4B5563))),
          ]),
        ),
        Expanded(child: control),
      ]),
    );
  }

  // ====== 辅助 ======
  // [PRD-SPO2-CARD-V1 2026-06-02] 血氧档位判定（与 H5 judgeSpo2 对齐）：≥95 正常蓝 / 90–94 偏低橙 / <90 偏低明显橙
  Map<String, String>? _spo2Cap(double? v) {
    if (v == null || v.isNaN || v <= 0) return null;
    if (v >= 95) return {'label': '正常', 'color': 'blue'};
    if (v >= 90) return {'label': '偏低', 'color': 'orange'};
    return {'label': '偏低明显', 'color': 'orange'};
  }

  // [PRD-SLEEP-ALIGN-BP-V1 2026-06-02] 睡眠按总时长定档（与 H5 judgeSleep 对齐）
  //   7~9 充足蓝 / 6~7 偏少黄 / <6 不足橙 / >9 偏多黄；脏数据（<=0/>24）返回 null
  Map<String, dynamic>? _sleepCap(double? v) {
    if (v == null || v.isNaN || v <= 0 || v > 24) return null;
    if (v < 6) return {'label': '睡眠不足', 'color': 'orange', 'abnormal': true};
    if (v < 7) return {'label': '睡眠偏少', 'color': 'yellow', 'abnormal': true};
    if (v <= 9) return {'label': '睡眠充足', 'color': 'blue', 'abnormal': false};
    return {'label': '睡眠偏多', 'color': 'yellow', 'abnormal': true};
  }

  String _readMetric(Map? tm, String key, {String subKey = 'value'}) {
    if (tm == null) return '—';
    final node = tm[key];
    if (node is! Map) return '—';
    final v = node['value'];
    if (v is Map) return v[subKey]?.toString() ?? '—';
    return v?.toString() ?? '—';
  }

  List<String> _normList(dynamic raw) {
    if (raw is! List) return [];
    return raw.map<String>((e) {
      if (e is String) return e;
      if (e is Map && e['value'] != null) return e['value'].toString();
      return '';
    }).where((s) => s.isNotEmpty).toList();
  }

  int? _calcAge(dynamic birthday) {
    if (birthday is! String || birthday.isEmpty) return null;
    final b = DateTime.tryParse(birthday);
    if (b == null) return null;
    final now = DateTime.now();
    int age = now.year - b.year;
    if (now.month < b.month || (now.month == b.month && now.day < b.day)) age--;
    return age >= 0 ? age : null;
  }

  String _relationEmoji(String name) {
    const m = {
      '爸爸': '👨', '父亲': '👨', '老公': '👨', '丈夫': '👨',
      '妈妈': '👩', '母亲': '👩', '老婆': '👩', '妻子': '👩',
      '儿子': '👦', '女儿': '👧',
      '爷爷': '👴', '外公': '👴',
      '奶奶': '👵', '外婆': '👵',
    };
    return m[name] ?? '🙂';
  }
}

class _StickyTabsDelegate extends SliverPersistentHeaderDelegate {
  final TabBar tabBar;
  _StickyTabsDelegate(this.tabBar);

  @override
  double get minExtent => tabBar.preferredSize.height;
  @override
  double get maxExtent => tabBar.preferredSize.height;

  @override
  Widget build(BuildContext context, double shrinkOffset, bool overlapsContent) {
    return Container(
      color: Colors.white,
      child: tabBar,
    );
  }

  @override
  bool shouldRebuild(_StickyTabsDelegate oldDelegate) => false;
}
