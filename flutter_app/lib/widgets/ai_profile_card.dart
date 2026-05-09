// [PRD-432] AI 回答顶部「咨询对象档案」折叠卡片 - Flutter
import 'package:flutter/material.dart';
import '../services/api_service.dart';

class AiProfileCard extends StatefulWidget {
  final int consultantId;
  final VoidCallback? onGoCompleteProfile;
  final void Function(int consultantId, bool autoCreate)? onGoMedicationManage;

  const AiProfileCard({
    super.key,
    required this.consultantId,
    this.onGoCompleteProfile,
    this.onGoMedicationManage,
  });

  @override
  State<AiProfileCard> createState() => _AiProfileCardState();
}

class _AiProfileCardState extends State<AiProfileCard> {
  bool _expanded = false;
  bool _loading = false;
  bool _error = false;
  Map<String, dynamic>? _data;

  static final Map<int, _CacheEntry> _cache = {};
  static const Duration _cacheTtl = Duration(seconds: 30);

  final ApiService _api = ApiService();

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  @override
  void didUpdateWidget(AiProfileCard old) {
    super.didUpdateWidget(old);
    if (old.consultantId != widget.consultantId) _fetch();
  }

  // [Bug-432-fix 2026-05-09]
  // 原实现：接口失败时直接 _error=true，卡片消失，且**不重试**——
  //   PRD 3.10 要求接口失败保留 1 次自动重试（3 秒后再试），均失败才静默不展示。
  // 修因：除"二次脱壳"外，三端的失败兜底都缺重试。本端 dio 拦截器已脱壳（onResponse 不动 response），
  //   resp.data 才是 JSON 体，所以原来的 `resp.data is Map` 是正确的，无需脱壳层面修复。
  // 修复：抽出 _fetchOnce()，在外层加 1 次重试逻辑；按 PRD 失败时静默隐藏卡片。
  Future<Map<String, dynamic>?> _fetchOnce() async {
    final resp =
        await _api.get('/api/v1/consultant/${widget.consultantId}/profile_card');
    if (resp.data is Map) {
      final m = Map<String, dynamic>.from(resp.data as Map);
      // 强校验：必须含 fields 字段，避免后端 200 但 body 异常时进入"无声成功"
      if (m['fields'] is Map) {
        return m;
      }
    }
    return null;
  }

  Future<void> _fetch() async {
    final cached = _cache[widget.consultantId];
    if (cached != null && DateTime.now().difference(cached.ts) < _cacheTtl) {
      if (mounted) {
        setState(() {
          _data = cached.data;
          _error = false;
          _loading = false;
        });
      }
      return;
    }
    if (mounted) {
      setState(() {
        _loading = true;
        _error = false;
      });
    }
    Map<String, dynamic>? data;
    try {
      data = await _fetchOnce();
    } catch (_) {
      data = null;
    }
    if (data == null) {
      // PRD 3.10：失败保留 1 次自动重试（3 秒后再试一次）
      await Future<void>.delayed(const Duration(seconds: 3));
      if (!mounted) return;
      try {
        data = await _fetchOnce();
      } catch (_) {
        data = null;
      }
    }
    if (!mounted) return;
    if (data != null) {
      _cache[widget.consultantId] =
          _CacheEntry(data: data, ts: DateTime.now());
      setState(() {
        _data = data;
        _error = false;
        _loading = false;
      });
    } else {
      setState(() {
        _error = true;
        _loading = false;
      });
    }
  }

  String _genderIcon(String? g) {
    if (g == '男' || g == 'male') return '♂';
    if (g == '女' || g == 'female') return '♀';
    return '👤';
  }

  Color _genderColor(String? g) {
    if (g == '男' || g == 'male') return const Color(0xFF3B82F6);
    if (g == '女' || g == 'female') return const Color(0xFFEC4899);
    return const Color(0xFF9CA3AF);
  }

  String _formatMd(String? iso) {
    if (iso == null) return '';
    try {
      final d = DateTime.parse(iso);
      final m = d.month.toString().padLeft(2, '0');
      final dd = d.day.toString().padLeft(2, '0');
      return '$m/$dd';
    } catch (_) {
      return '';
    }
  }

  String _renderListField(Map? f) {
    if (f == null) return '未填写';
    if (f['is_none'] == true) return '无';
    final val = f['value'];
    if (val is List && val.isNotEmpty) {
      if (val.length == 1) return val.first.toString();
      return '${val.take(2).join('、')} 等 ${val.length} 项';
    }
    return f['filled'] == true ? '' : '未填写';
  }

  @override
  Widget build(BuildContext context) {
    if (_error || _data == null) {
      if (_error) return const SizedBox.shrink();
      return Container(
        margin: const EdgeInsets.fromLTRB(12, 8, 12, 4),
        padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 12),
        decoration: BoxDecoration(
          color: const Color(0xFFF4F6FA),
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Text('加载档案中...', style: TextStyle(color: Color(0xFF9CA3AF), fontSize: 12)),
      );
    }
    final data = _data!;
    final fields = (data['fields'] ?? {}) as Map;
    final gender = (fields['gender'] ?? {}) as Map;
    final age = (fields['age'] ?? {}) as Map;
    final height = (fields['height'] ?? {}) as Map;
    final weight = (fields['weight'] ?? {}) as Map;
    final past = (fields['past_history'] ?? {}) as Map;
    final allergy = (fields['allergy'] ?? {}) as Map;
    final meds = (fields['long_term_meds'] ?? {}) as Map;
    final completeness = (data['completeness'] ?? {}) as Map;
    final percent = (completeness['percent'] ?? 0) as num;
    final isComplete = percent >= 100;
    final summary = (data['summary_text'] ?? '') as String;
    final nickname = (data['nickname'] ?? '本人') as String;
    final medsClickable = meds['is_none'] != true;

    return Container(
      margin: const EdgeInsets.fromLTRB(12, 8, 12, 4),
      decoration: BoxDecoration(
        color: const Color(0xFFF4F6FA),
        borderRadius: BorderRadius.circular(8),
      ),
      clipBehavior: Clip.hardEdge,
      child: Column(
        children: [
          InkWell(
            onTap: () => setState(() => _expanded = !_expanded),
            child: Container(
              height: 44,
              padding: const EdgeInsets.symmetric(horizontal: 12),
              child: Row(
                children: [
                  Container(
                    width: 24,
                    height: 24,
                    decoration: BoxDecoration(
                      color: _genderColor(gender['value'] as String?),
                      shape: BoxShape.circle,
                    ),
                    alignment: Alignment.center,
                    child: Text(_genderIcon(gender['value'] as String?),
                        style: const TextStyle(color: Colors.white, fontSize: 14)),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      '本次回答结合 $nickname 的档案',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                          fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF1F2937)),
                    ),
                  ),
                  if (summary.isNotEmpty) ...[
                    const SizedBox(width: 8),
                    Flexible(
                      child: Text(
                        summary,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280)),
                      ),
                    ),
                  ],
                  const SizedBox(width: 8),
                  Text(_expanded ? '▴' : '▾',
                      style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
                ],
              ),
            ),
          ),
          if (_expanded)
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    decoration: const BoxDecoration(
                      border: Border(top: BorderSide(color: Color(0xFFE5E7EB))),
                    ),
                    child: Row(
                      children: [
                        Expanded(
                          child: GestureDetector(
                            onTap: isComplete ? null : widget.onGoCompleteProfile,
                            child: Text(
                              isComplete
                                  ? '档案已完整 ✓'
                                  : '档案完整度 $percent%，点击补全 ›',
                              style: TextStyle(
                                fontSize: 12,
                                color: isComplete
                                    ? const Color(0xFF10B981)
                                    : const Color(0xFF2563EB),
                              ),
                            ),
                          ),
                        ),
                        if (data['updated_within_30d'] == true && data['last_updated_at'] != null)
                          Text('档案已于 ${_formatMd(data['last_updated_at'])} 更新',
                              style:
                                  const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
                      ],
                    ),
                  ),
                  _buildRow('性别', _renderField(gender)),
                  _buildRow('年龄', age['filled'] == true ? '${age['value']} 岁' : '未填写',
                      isEmpty: age['filled'] != true),
                  _buildRow('身高', _renderField(height), isEmpty: height['filled'] != true),
                  _buildRow('体重', _renderField(weight), isEmpty: weight['filled'] != true),
                  _buildRow('既往病史', _renderListField(past),
                      isEmpty: past['is_none'] != true && past['filled'] != true),
                  _buildRow('过敏史', _renderListField(allergy),
                      isEmpty: allergy['is_none'] != true && allergy['filled'] != true),
                  _buildMedsRow(meds, medsClickable, data['consultant_id'] as int? ?? 0),
                ],
              ),
            ),
        ],
      ),
    );
  }

  String _renderField(Map f) {
    if (f['filled'] != true) return '未填写';
    return (f['value'] ?? '').toString();
  }

  Widget _buildRow(String label, String value, {bool isEmpty = false}) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 70,
            child: Text(label,
                style: const TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
          ),
          Expanded(
            child: Text(value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: TextStyle(
                    fontSize: 13,
                    color: isEmpty ? const Color(0xFF9CA3AF) : const Color(0xFF111827))),
          ),
        ],
      ),
    );
  }

  Widget _buildMedsRow(Map meds, bool clickable, int consultantId) {
    final isNone = meds['is_none'] == true;
    final count = (meds['count'] ?? 0) as int;
    final brief = (meds['value_brief'] ?? '').toString();
    final value = isNone
        ? '无'
        : (count > 0 ? (brief.isEmpty ? '共 $count 项' : brief) : '未填写');
    return InkWell(
      onTap: clickable ? () => _showMedicationsBottomSheet(consultantId) : null,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 6),
        decoration: BoxDecoration(
          color: clickable ? const Color(0xFFFAFCFF) : Colors.transparent,
          borderRadius: BorderRadius.circular(4),
        ),
        child: Row(
          children: [
            const SizedBox(
              width: 70,
              child: Text('长期用药', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
            ),
            Expanded(
              child: Text(value,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(
                      fontSize: 13,
                      color: isNone ? const Color(0xFF9CA3AF) : const Color(0xFF111827))),
            ),
            if (clickable)
              const Text('›', style: TextStyle(color: Color(0xFF9CA3AF))),
          ],
        ),
      ),
    );
  }

  void _showMedicationsBottomSheet(int consultantId) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.transparent,
      builder: (ctx) {
        return MedicationBottomSheet(
          consultantId: consultantId,
          consultantName: (_data?['nickname'] ?? '本人') as String,
          onGoManage: () {
            Navigator.of(ctx).pop();
            widget.onGoMedicationManage?.call(consultantId, false);
          },
          onGoCreate: () {
            Navigator.of(ctx).pop();
            widget.onGoMedicationManage?.call(consultantId, true);
          },
        );
      },
    );
  }
}

class _CacheEntry {
  final Map<String, dynamic> data;
  final DateTime ts;
  _CacheEntry({required this.data, required this.ts});
}

class MedicationBottomSheet extends StatefulWidget {
  final int consultantId;
  final String consultantName;
  final VoidCallback onGoManage;
  final VoidCallback onGoCreate;
  const MedicationBottomSheet({
    super.key,
    required this.consultantId,
    required this.consultantName,
    required this.onGoManage,
    required this.onGoCreate,
  });

  @override
  State<MedicationBottomSheet> createState() => _MedicationBottomSheetState();
}

class _MedicationBottomSheetState extends State<MedicationBottomSheet> {
  final ApiService _api = ApiService();
  bool _loading = true;
  bool _error = false;
  bool _isNone = false;
  List<Map<String, dynamic>> _items = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() {
      _loading = true;
      _error = false;
    });
    try {
      final resp = await _api.get('/api/v1/consultant/${widget.consultantId}/medications');
      final data = resp.data is Map ? Map<String, dynamic>.from(resp.data as Map) : null;
      if (data != null) {
        final items = (data['items'] as List?) ?? [];
        if (mounted) {
          setState(() {
            _items = items.map((e) => Map<String, dynamic>.from(e as Map)).toList();
            _isNone = data['is_none'] == true;
          });
        }
      } else {
        if (mounted) setState(() => _error = true);
      }
    } catch (_) {
      if (mounted) setState(() => _error = true);
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final h = MediaQuery.of(context).size.height * 0.5;
    return Container(
      height: h,
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: Column(
        children: [
          Container(
            margin: const EdgeInsets.symmetric(vertical: 8),
            width: 36,
            height: 4,
            decoration: BoxDecoration(
              color: const Color(0xFFE5E7EB),
              borderRadius: BorderRadius.circular(2),
            ),
          ),
          Container(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 10),
            decoration: const BoxDecoration(
              border: Border(bottom: BorderSide(color: Color(0xFFF3F4F6))),
            ),
            child: Row(
              children: [
                const Expanded(
                  child: Text('长期用药',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                ),
                GestureDetector(
                  onTap: widget.onGoManage,
                  child: const Text('去管理 ›',
                      style: TextStyle(color: Color(0xFF2563EB), fontSize: 14)),
                ),
              ],
            ),
          ),
          Expanded(child: _buildBody()),
        ],
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) {
      return const Center(child: Padding(padding: EdgeInsets.all(20), child: Text('加载中...')));
    }
    if (_error) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: GestureDetector(
            onTap: () {
              _fetch();
            },
            child: const Text('加载失败，点击重试',
                style: TextStyle(color: Color(0xFF9CA3AF))),
          ),
        ),
      );
    }
    if (_isNone) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(30),
          child: Text('${widget.consultantName} 当前无长期用药',
              style: const TextStyle(color: Color(0xFF6B7280))),
        ),
      );
    }
    if (_items.isEmpty) {
      return Center(
        child: GestureDetector(
          onTap: widget.onGoCreate,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: const [
              Text('💊', style: TextStyle(fontSize: 56)),
              SizedBox(height: 12),
              Text('暂无长期用药，点击添加 ›',
                  style: TextStyle(color: Color(0xFF2563EB), fontSize: 14)),
            ],
          ),
        ),
      );
    }
    return ListView.separated(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      itemCount: _items.length,
      separatorBuilder: (_, __) => const Divider(height: 1, color: Color(0xFFF3F4F6)),
      itemBuilder: (context, idx) {
        final it = _items[idx];
        final dosage = (it['dosage'] ?? '').toString();
        final freq = (it['frequency'] ?? '').toString();
        final days = it['used_days'] ?? 0;
        final parts = <String>[];
        if (dosage.isNotEmpty) parts.add(dosage);
        if (freq.isNotEmpty) parts.add(freq);
        if (days is num && days > 0) parts.add('已服用 $days 天');
        return Padding(
          padding: const EdgeInsets.symmetric(vertical: 10),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('💊 ${it['medicine_name'] ?? ''}',
                  style: const TextStyle(
                      fontSize: 15,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF111827))),
              const SizedBox(height: 4),
              Text(parts.join(' / '),
                  style: const TextStyle(fontSize: 12, color: Color(0xFF6B7280))),
            ],
          ),
        );
      },
    );
  }
}
