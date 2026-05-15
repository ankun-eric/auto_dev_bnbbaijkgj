// [PRD-HEALTH-SELF-CHECK-V1 2026-05-15] 健康自查抽屉
import 'package:flutter/material.dart';
import '../services/api_service.dart';

class HealthSelfCheckResult {
  final int templateId;
  final int buttonId;
  final int? archiveId;
  final String? archiveName;
  final int? archiveAge;
  final String? archiveGender;
  final Map<String, dynamic> bodyPart; // {id, name, icon}
  final List<String> symptoms;
  final String duration;

  HealthSelfCheckResult({
    required this.templateId,
    required this.buttonId,
    this.archiveId,
    this.archiveName,
    this.archiveAge,
    this.archiveGender,
    required this.bodyPart,
    required this.symptoms,
    required this.duration,
  });

  /// [BUG-FIX 2026-05-16] 后端 HealthSelfCheckStartRequest schema 要求：
  /// button_id / template_id / archive_id / body_part_id（整数）/ symptoms / duration / session_id
  /// 不接受 archive_name / archive_age / archive_gender / body_part 对象，
  /// 因此 toJson 仅输出与后端 schema 严格匹配的字段。
  /// 展示模型（卡片气泡）需要的 archive_name / body_part 对象等请直接使用对象属性，
  /// 不要走 toJson 通道。
  Map<String, dynamic> toJson() {
    final dynamic rawPartId = bodyPart['id'];
    final int bodyPartId = rawPartId is int
        ? rawPartId
        : int.tryParse(rawPartId?.toString() ?? '') ?? 0;
    return {
      'template_id': templateId,
      'button_id': buttonId,
      'archive_id': archiveId,
      'body_part_id': bodyPartId,
      'symptoms': symptoms,
      'duration': duration,
    };
  }
}

class HealthSelfCheckDrawer extends StatefulWidget {
  final int templateId;
  final int buttonId;
  final int? archiveId;
  final String? archiveName;
  final int? archiveAge;
  final String? archiveGender;
  final bool archiveIsDefault;
  final HealthSelfCheckResult? prefill;

  const HealthSelfCheckDrawer({
    super.key,
    required this.templateId,
    required this.buttonId,
    this.archiveId,
    this.archiveName,
    this.archiveAge,
    this.archiveGender,
    this.archiveIsDefault = false,
    this.prefill,
  });

  @override
  State<HealthSelfCheckDrawer> createState() => _HealthSelfCheckDrawerState();
}

class _HealthSelfCheckDrawerState extends State<HealthSelfCheckDrawer> {
  final ApiService _api = ApiService();
  bool _loading = true;
  String? _errorMsg;
  Map<String, dynamic>? _template;
  List<Map<String, dynamic>> _bodyParts = [];
  List<String> _durationOptions = [];
  int? _selectedPartId;
  final Set<String> _selectedSymptoms = <String>{};
  String _selectedDuration = '';
  bool _highlightMissing = false;

  @override
  void initState() {
    super.initState();
    _loadTemplate();
  }

  Future<void> _loadTemplate() async {
    try {
      final resp = await _api.get('/api/health-self-check/template/${widget.templateId}');
      final data = resp.data is Map ? Map<String, dynamic>.from(resp.data as Map) : <String, dynamic>{};
      if (data['enabled'] != true) {
        setState(() {
          _loading = false;
          _errorMsg = '该功能暂不可用，请联系管理员';
        });
        return;
      }
      final partsRaw = data['body_parts_detail'] as List? ?? [];
      final parts = partsRaw
          .whereType<Map>()
          .map((e) => Map<String, dynamic>.from(e))
          .toList();
      final durs = (data['duration_options'] as List? ?? []).map((e) => e.toString()).toList();
      setState(() {
        _template = data;
        _bodyParts = parts;
        _durationOptions = durs;
        _loading = false;
        if (widget.prefill != null) {
          _selectedPartId = widget.prefill!.bodyPart['id'] as int?;
          _selectedSymptoms.addAll(widget.prefill!.symptoms);
          _selectedDuration = widget.prefill!.duration;
        }
      });
    } catch (e) {
      setState(() {
        _loading = false;
        _errorMsg = '模板加载失败，请稍后重试';
      });
    }
  }

  Map<String, dynamic>? get _selectedPart {
    if (_selectedPartId == null) return null;
    for (final p in _bodyParts) {
      if (p['id'] == _selectedPartId) return p;
    }
    return null;
  }

  void _submit() {
    if (_selectedPartId == null ||
        _selectedSymptoms.isEmpty ||
        _selectedDuration.isEmpty) {
      setState(() => _highlightMissing = true);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请完成全部三项后再开始分析'), duration: Duration(seconds: 2)),
      );
      return;
    }
    final part = _selectedPart!;
    final result = HealthSelfCheckResult(
      templateId: widget.templateId,
      buttonId: widget.buttonId,
      archiveId: widget.archiveId,
      archiveName: widget.archiveName,
      archiveAge: widget.archiveAge,
      archiveGender: widget.archiveGender,
      bodyPart: {
        'id': part['id'],
        'name': part['name'],
        'icon': part['icon'] ?? '',
      },
      symptoms: _selectedSymptoms.toList(),
      duration: _selectedDuration,
    );
    Navigator.of(context).pop(result);
  }

  @override
  Widget build(BuildContext context) {
    final size = MediaQuery.of(context).size;
    return Container(
      height: size.height * 0.85,
      decoration: const BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.vertical(top: Radius.circular(16)),
      ),
      child: Column(
        children: [
          // 顶部标题
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
            child: Row(
              children: [
                const Expanded(
                  child: Text('🩺 健康自查',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                ),
                GestureDetector(
                  onTap: () => Navigator.of(context).pop(),
                  child: const Padding(
                    padding: EdgeInsets.all(4),
                    child: Icon(Icons.close, size: 22, color: Colors.grey),
                  ),
                ),
              ],
            ),
          ),
          const Divider(height: 1),
          // 档案
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(16, 10, 16, 10),
            color: const Color(0xFFF7F8FA),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Text('咨询档案：', style: TextStyle(fontSize: 13, color: Color(0xFF666666))),
                    Text(
                      widget.archiveName ?? '未选择',
                      style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF222222)),
                    ),
                    if (widget.archiveIsDefault)
                      Container(
                        margin: const EdgeInsets.only(left: 6),
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                        decoration: BoxDecoration(
                          color: const Color(0xFFE6F4FF),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: const Text('默认档案', style: TextStyle(fontSize: 11, color: Color(0xFF1677FF))),
                      ),
                  ],
                ),
                const SizedBox(height: 4),
                const Text('如需切换档案，请关闭后在顶部切换',
                    style: TextStyle(fontSize: 11, color: Color(0xFF999999))),
              ],
            ),
          ),
          // 内容
          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _errorMsg != null
                    ? Center(
                        child: Text(_errorMsg!,
                            style: const TextStyle(color: Colors.red)))
                    : SingleChildScrollView(
                        padding: const EdgeInsets.all(16),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            _buildStepTitle('步骤 1：选择部位',
                                missing: _highlightMissing && _selectedPartId == null),
                            const SizedBox(height: 8),
                            _buildBodyPartGrid(),
                            const SizedBox(height: 18),
                            _buildStepTitle('步骤 2：选择症状（多选）',
                                missing:
                                    _highlightMissing && _selectedSymptoms.isEmpty),
                            const SizedBox(height: 8),
                            _buildSymptoms(),
                            const SizedBox(height: 18),
                            _buildStepTitle('步骤 3：选择持续时间',
                                missing:
                                    _highlightMissing && _selectedDuration.isEmpty),
                            const SizedBox(height: 8),
                            _buildDurations(),
                          ],
                        ),
                      ),
          ),
          // 底部按钮
          SafeArea(
            top: false,
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: SizedBox(
                width: double.infinity,
                height: 44,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: const Color(0xFF1677FF),
                    foregroundColor: Colors.white,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                  ),
                  onPressed: _loading || _errorMsg != null ? null : _submit,
                  child: const Text('开始 AI 分析',
                      style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStepTitle(String title, {bool missing = false}) {
    return Text(title,
        style: TextStyle(
          fontSize: 14,
          fontWeight: FontWeight.w600,
          color: missing ? Colors.red : const Color(0xFF222222),
        ));
  }

  Widget _buildBodyPartGrid() {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 4,
        crossAxisSpacing: 8,
        mainAxisSpacing: 8,
        childAspectRatio: 1.1,
      ),
      itemCount: _bodyParts.length,
      itemBuilder: (ctx, i) {
        final p = _bodyParts[i];
        final active = _selectedPartId == p['id'];
        return GestureDetector(
          onTap: () {
            setState(() {
              _selectedPartId = p['id'] as int?;
              _selectedSymptoms.clear();
            });
          },
          child: Container(
            padding: const EdgeInsets.all(6),
            decoration: BoxDecoration(
              color: active ? const Color(0xFFE6F4FF) : const Color(0xFFFAFAFA),
              border: Border.all(
                  color: active ? const Color(0xFF1677FF) : const Color(0xFFE8E8E8),
                  width: active ? 2 : 1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text((p['icon'] as String?)?.isNotEmpty == true ? p['icon'] : '🧩',
                    style: const TextStyle(fontSize: 22)),
                const SizedBox(height: 4),
                Text(p['name']?.toString() ?? '',
                    style: TextStyle(
                        fontSize: 12,
                        color: active ? const Color(0xFF1677FF) : const Color(0xFF333333))),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildSymptoms() {
    final part = _selectedPart;
    if (part == null) {
      return const Text('请先选择上方的部位',
          style: TextStyle(fontSize: 12, color: Color(0xFF999999)));
    }
    final symptoms = (part['symptoms'] as List?)?.map((e) => e.toString()).toList() ?? [];
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: symptoms.map((s) {
        final active = _selectedSymptoms.contains(s);
        return GestureDetector(
          onTap: () {
            setState(() {
              if (active) {
                _selectedSymptoms.remove(s);
              } else {
                _selectedSymptoms.add(s);
              }
            });
          },
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
            decoration: BoxDecoration(
              color: active ? const Color(0xFF1677FF) : Colors.white,
              border: Border.all(
                  color: active ? const Color(0xFF1677FF) : const Color(0xFFE8E8E8)),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(s,
                style: TextStyle(
                    fontSize: 13,
                    color: active ? Colors.white : const Color(0xFF333333))),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildDurations() {
    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: _durationOptions.map((d) {
        final active = _selectedDuration == d;
        return GestureDetector(
          onTap: () => setState(() => _selectedDuration = d),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
            decoration: BoxDecoration(
              color: active ? const Color(0xFFE6F4FF) : Colors.white,
              border: Border.all(
                  color: active ? const Color(0xFF1677FF) : const Color(0xFFE8E8E8)),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Text(d,
                style: TextStyle(
                    fontSize: 13,
                    color: active ? const Color(0xFF1677FF) : const Color(0xFF333333))),
          ),
        );
      }).toList(),
    );
  }
}
