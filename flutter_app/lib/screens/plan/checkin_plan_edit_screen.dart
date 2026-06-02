// [PRD-HEALTH-PLAN-CHECKIN-V1 2026-06-02] 新建/编辑打卡计划页
import 'package:flutter/material.dart';
import '../../services/api_service.dart';

class CheckinPlanEditScreen extends StatefulWidget {
  const CheckinPlanEditScreen({super.key});

  @override
  State<CheckinPlanEditScreen> createState() => _CheckinPlanEditScreenState();
}

class _CheckinPlanEditScreenState extends State<CheckinPlanEditScreen> {
  final ApiService _api = ApiService();
  final _nameCtrl = TextEditingController();
  int? _editId;
  bool _loading = false;
  bool _submitting = false;
  String _freqType = 'daily';
  int _weeklyCount = 3;
  DateTime _startDate = DateTime.now();
  DateTime? _endDate;
  bool _argsLoaded = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_argsLoaded) return;
    _argsLoaded = true;
    final arg = ModalRoute.of(context)?.settings.arguments;
    if (arg is int) {
      _editId = arg;
      _fetch();
    }
  }

  Future<void> _fetch() async {
    setState(() => _loading = true);
    try {
      final res = await _api.getCheckinItemDetail(_editId!);
      final d = res.data as Map<String, dynamic>;
      _nameCtrl.text = (d['name'] ?? '').toString();
      _freqType = d['repeat_frequency'] == 'weekly' ? 'weekly' : 'daily';
      _weeklyCount = (d['weekly_target_count'] as int?) ?? 3;
      if (d['start_date'] != null) _startDate = DateTime.parse(d['start_date'] as String);
      if (d['end_date'] != null) _endDate = DateTime.parse(d['end_date'] as String);
    } catch (_) {}
    if (mounted) setState(() => _loading = false);
  }

  String _fmt(DateTime d) =>
      '${d.year}-${d.month.toString().padLeft(2, '0')}-${d.day.toString().padLeft(2, '0')}';

  Future<void> _submit() async {
    final name = _nameCtrl.text.trim();
    if (name.isEmpty) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('请输入计划名称')));
      return;
    }
    if (_freqType == 'weekly' && (_weeklyCount < 1 || _weeklyCount > 7)) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('每周次数应在 1~7 之间')));
      return;
    }
    if (_endDate != null && _endDate!.isBefore(_startDate)) {
      ScaffoldMessenger.of(context)
          .showSnackBar(const SnackBar(content: Text('开始日期不能晚于结束日期')));
      return;
    }
    setState(() => _submitting = true);
    final payload = {
      'name': name,
      'repeat_frequency': _freqType,
      'weekly_target_count': _freqType == 'weekly' ? _weeklyCount : null,
      'start_date': _fmt(_startDate),
      'end_date': _endDate != null ? _fmt(_endDate!) : null,
    };
    try {
      if (_editId != null) {
        await _api.updateCheckinItem(_editId!, payload);
      } else {
        await _api.createCheckinItem(payload);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(_editId != null ? '保存成功' : '创建成功'),
            backgroundColor: const Color(0xFF6366F1)));
        Navigator.pop(context);
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('保存失败'), backgroundColor: Colors.red));
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  Future<void> _pickStart() async {
    final d = await showDatePicker(
      context: context,
      initialDate: _startDate,
      firstDate: DateTime(2020),
      lastDate: DateTime(2099),
    );
    if (d != null) setState(() => _startDate = d);
  }

  Future<void> _pickEnd() async {
    final d = await showDatePicker(
      context: context,
      initialDate: _endDate ?? _startDate,
      firstDate: DateTime(2020),
      lastDate: DateTime(2099),
    );
    if (d != null) setState(() => _endDate = d);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF5F5F7),
      appBar: AppBar(
        title: Text(_editId != null ? '编辑计划' : '新建计划'),
        backgroundColor: const Color(0xFF52C41A),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  _card(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _LabelText('* 计划名称'),
                      const SizedBox(height: 8),
                      TextField(
                        controller: _nameCtrl,
                        maxLength: 50,
                        decoration: const InputDecoration(
                          hintText: '如：每天喝 8 杯水',
                          border: OutlineInputBorder(),
                          contentPadding: EdgeInsets.symmetric(horizontal: 12, vertical: 12),
                        ),
                      ),
                    ],
                  )),
                  _card(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _LabelText('* 打卡频率'),
                      const SizedBox(height: 12),
                      Row(children: [
                        _freqBtn('daily', '每天'),
                        const SizedBox(width: 12),
                        _freqBtn('weekly', '每周 X 次'),
                      ]),
                      if (_freqType == 'weekly') ...[
                        const SizedBox(height: 16),
                        Row(
                          mainAxisAlignment: MainAxisAlignment.spaceBetween,
                          children: [
                            const Text('每周打卡次数', style: TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
                            Row(children: [
                              IconButton(
                                icon: const Icon(Icons.remove_circle_outline),
                                onPressed: _weeklyCount > 1
                                    ? () => setState(() => _weeklyCount--)
                                    : null,
                              ),
                              Text('$_weeklyCount', style: const TextStyle(fontSize: 16)),
                              IconButton(
                                icon: const Icon(Icons.add_circle_outline),
                                onPressed: _weeklyCount < 7
                                    ? () => setState(() => _weeklyCount++)
                                    : null,
                              ),
                            ]),
                          ],
                        ),
                      ],
                      const SizedBox(height: 8),
                      const Text('仅按「天」打卡，不设置具体时间点。',
                          style: TextStyle(fontSize: 11, color: Color(0xFF9CA3AF))),
                    ],
                  )),
                  _card(child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const _LabelText('计划起止时间'),
                      const SizedBox(height: 8),
                      InkWell(
                        onTap: _pickStart,
                        child: _dateRow('开始日期', _fmt(_startDate)),
                      ),
                      const Divider(height: 1),
                      InkWell(
                        onTap: _pickEnd,
                        child: _dateRow(
                          '结束日期',
                          _endDate != null ? _fmt(_endDate!) : '不限期',
                          trailing: _endDate != null
                              ? GestureDetector(
                                  onTap: () => setState(() => _endDate = null),
                                  child: const Text('清除',
                                      style: TextStyle(color: Color(0xFF6366F1), fontSize: 12)),
                                )
                              : null,
                        ),
                      ),
                    ],
                  )),
                  const SizedBox(height: 24),
                  SizedBox(
                    height: 48,
                    child: ElevatedButton(
                      onPressed: _submitting ? null : _submit,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFF6366F1),
                        foregroundColor: Colors.white,
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
                      child: _submitting
                          ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                          : Text(_editId != null ? '保存修改' : '创建计划',
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
                    ),
                  ),
                ],
              ),
            ),
    );
  }

  Widget _card({required Widget child}) => Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
        child: child,
      );

  Widget _freqBtn(String v, String label) {
    final selected = _freqType == v;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _freqType = v),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10),
          alignment: Alignment.center,
          decoration: BoxDecoration(
            color: selected ? const Color(0xFFEEF2FF) : const Color(0xFFF5F5F5),
            borderRadius: BorderRadius.circular(8),
            border: Border.all(color: selected ? const Color(0xFF6366F1).withOpacity(0.25) : Colors.transparent),
          ),
          child: Text(label,
              style: TextStyle(
                fontSize: 13,
                color: selected ? const Color(0xFF6366F1) : const Color(0xFF666666),
                fontWeight: selected ? FontWeight.bold : FontWeight.normal,
              )),
        ),
      ),
    );
  }

  Widget _dateRow(String left, String right, {Widget? trailing}) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 14),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(left, style: const TextStyle(fontSize: 13, color: Color(0xFF6B7280))),
          Row(
            children: [
              Text(right, style: const TextStyle(fontSize: 13)),
              if (trailing != null) ...[const SizedBox(width: 12), trailing],
            ],
          ),
        ],
      ),
    );
  }
}

class _LabelText extends StatelessWidget {
  final String text;
  const _LabelText(this.text);
  @override
  Widget build(BuildContext context) {
    return Text(text, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.bold));
  }
}
