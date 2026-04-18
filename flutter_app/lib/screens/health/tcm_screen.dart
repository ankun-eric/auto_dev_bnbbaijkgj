import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';

const _kPrimaryPurple = Color(0xFF722ED1);
const _kPrimaryPink = Color(0xFFEB2F96);

const _kRelationColors = <String, Color>{
  '本人': Color(0xFF1677FF),
  '爸爸': Color(0xFFFA8C16),
  '父亲': Color(0xFFFA8C16),
  '妈妈': Color(0xFFEB2F96),
  '母亲': Color(0xFFEB2F96),
  '配偶': Color(0xFF722ED1),
  '子女': Color(0xFF13C2C2),
};

Color _getMemberColor(String? relation) {
  if (relation == null || relation.isEmpty) return const Color(0xFF1677FF);
  return _kRelationColors[relation] ?? const Color(0xFF8C8C8C);
}

class TcmScreen extends StatefulWidget {
  const TcmScreen({super.key});

  @override
  State<TcmScreen> createState() => _TcmScreenState();
}

class _TcmScreenState extends State<TcmScreen> {
  final ImagePicker _picker = ImagePicker();
  final ApiService _api = ApiService();

  Map<String, dynamic> _config = {};
  bool _configLoading = true;

  List<Map<String, dynamic>> _diagnosisList = [];
  bool _diagnosisLoading = true;

  List<Map<String, dynamic>> _familyMembers = [];
  bool _membersLoading = true;

  final List<Map<String, dynamic>> _allFunctions = [
    {
      'title': '舌诊',
      'desc': '拍摄舌头照片，AI智能分析',
      'icon': Icons.camera_alt,
      'color': const Color(0xFFEB2F96),
      'type': 'tongue',
      'configKey': 'tongue_diagnosis_enabled',
    },
    {
      'title': '面诊',
      'desc': '拍摄面部照片，辨别面色',
      'icon': Icons.face,
      'color': const Color(0xFFFA8C16),
      'type': 'face',
      'configKey': 'face_diagnosis_enabled',
    },
    {
      'title': '体质测评',
      'desc': '回答问卷，了解您的中医体质',
      'icon': Icons.quiz,
      'color': const Color(0xFF722ED1),
      'type': 'constitution',
      'configKey': 'constitution_test_enabled',
    },
  ];

  final List<Map<String, String>> _constitutions = [
    {'name': '平和质', 'desc': '体态适中，面色红润'},
    {'name': '气虚质', 'desc': '容易疲乏、气短'},
    {'name': '阳虚质', 'desc': '手脚发凉、畏寒怕冷'},
    {'name': '阴虚质', 'desc': '手足心热、口燥咽干'},
    {'name': '痰湿质', 'desc': '体形肥胖、腹部肥满'},
    {'name': '湿热质', 'desc': '面垢油光、口苦口干'},
    {'name': '血瘀质', 'desc': '肤色晦暗、色素沉着'},
    {'name': '气郁质', 'desc': '情志抑郁、忧虑脆弱'},
    {'name': '特禀质', 'desc': '过敏体质、易生荨麻疹'},
  ];

  @override
  void initState() {
    super.initState();
    _loadTcmConfig();
    _loadDiagnosisList();
    _loadFamilyMembers();
  }

  Future<void> _loadTcmConfig() async {
    try {
      final response = await _api.getTcmConfig();
      if (response.statusCode == 200 && mounted) {
        final data = response.data;
        setState(() {
          _config = data is Map<String, dynamic> ? data : <String, dynamic>{};
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _configLoading = false);
  }

  Future<void> _loadDiagnosisList() async {
    try {
      final response = await _api.getTcmDiagnosisList();
      if (response.statusCode == 200 && mounted) {
        final data = response.data;
        final rawData = data is Map && data.containsKey('data') ? data['data'] : data;
        final items = rawData is List
            ? rawData
            : (rawData is Map ? (rawData['items'] as List? ?? []) : []);
        setState(() {
          _diagnosisList = items.cast<Map<String, dynamic>>();
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _diagnosisLoading = false);
  }

  Future<void> _loadFamilyMembers() async {
    try {
      final response = await _api.getFamilyMembers();
      if (response.statusCode == 200 && mounted) {
        final items = response.data['items'] as List? ?? [];
        setState(() {
          _familyMembers = items.map((e) {
            final m = Map<String, dynamic>.from(e as Map);
            return {
              'id': m['id'],
              'nickname': m['nickname'] ?? m['name'] ?? '',
              'relationship_type': m['relation_type_name'] ?? m['relationship_type'] ?? '本人',
              'is_self': m['is_self'] ?? false,
            };
          }).toList();
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _membersLoading = false);
  }

  bool _isFunctionEnabled(Map<String, dynamic> func) {
    if (_configLoading) return true;
    final key = func['configKey'] as String?;
    if (key == null) return true;
    final val = _config[key];
    if (val == null) return true;
    return val == true || val == 1 || val == 'true';
  }

  List<Map<String, dynamic>> get _visibleFunctions =>
      _allFunctions.where(_isFunctionEnabled).toList();

  Future<void> _takeDiagnosePhoto(String type) async {
    final image = await _picker.pickImage(source: ImageSource.camera);
    if (image != null && mounted) {
      _showDiagnoseResult(type);
    }
  }

  void _showDiagnoseResult(String type) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: Row(
          children: [
            const Icon(Icons.spa, color: _kPrimaryPurple),
            const SizedBox(width: 8),
            Text(type == 'tongue' ? '舌诊分析' : '面诊分析'),
          ],
        ),
        content: const Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('正在上传图片进行AI分析...', style: TextStyle(fontSize: 14)),
            SizedBox(height: 16),
            Text(
              '分析完成后将为您提供：\n• 体质类型判断\n• 健康状态评估\n• 养生调理建议',
              style: TextStyle(fontSize: 14, height: 1.6, color: Color(0xFF666666)),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('知道了', style: TextStyle(color: Color(0xFF52C41A))),
          ),
        ],
      ),
    );
  }

  void _showConstitutionTest() {
    final answers = <int, int>{};
    final questions = [
      '1. 您是否经常感到疲劳、气短？',
      '2. 您是否手脚发凉、怕冷？',
      '3. 您是否口干舌燥、手足心热？',
      '4. 您是否体形偏胖、腹部肥满？',
      '5. 您是否面部容易出油？',
    ];
    final options = ['没有', '很少', '有时', '经常', '总是'];

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) => StatefulBuilder(
        builder: (ctx, setSheetState) => DraggableScrollableSheet(
          initialChildSize: 0.8,
          maxChildSize: 0.95,
          minChildSize: 0.5,
          expand: false,
          builder: (context, controller) => Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              children: [
                Container(
                  width: 40, height: 4,
                  decoration: BoxDecoration(color: Colors.grey[300], borderRadius: BorderRadius.circular(2)),
                ),
                const SizedBox(height: 20),
                const Text('中医体质测评', style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold)),
                const SizedBox(height: 8),
                Text('回答以下问题，了解您的中医体质类型', style: TextStyle(color: Colors.grey[600])),
                const SizedBox(height: 24),
                Expanded(
                  child: ListView.builder(
                    controller: controller,
                    itemCount: questions.length,
                    itemBuilder: (context, qIdx) {
                      return Container(
                        margin: const EdgeInsets.only(bottom: 16),
                        padding: const EdgeInsets.all(16),
                        decoration: BoxDecoration(
                          color: const Color(0xFFF5F7FA),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(questions[qIdx], style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
                            const SizedBox(height: 12),
                            Row(
                              children: List.generate(options.length, (oIdx) {
                                final isSelected = answers[qIdx] == oIdx;
                                return Expanded(
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(horizontal: 2),
                                    child: OutlinedButton(
                                      onPressed: () => setSheetState(() => answers[qIdx] = oIdx),
                                      style: OutlinedButton.styleFrom(
                                        padding: const EdgeInsets.symmetric(vertical: 8),
                                        backgroundColor: isSelected ? _kPrimaryPurple.withOpacity(0.1) : null,
                                        side: BorderSide(
                                          color: isSelected ? _kPrimaryPurple : Colors.grey[300]!,
                                        ),
                                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                                      ),
                                      child: Text(
                                        options[oIdx],
                                        style: TextStyle(
                                          fontSize: 12,
                                          color: isSelected ? _kPrimaryPurple : const Color(0xFF666666),
                                          fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                                        ),
                                      ),
                                    ),
                                  ),
                                );
                              }),
                            ),
                          ],
                        ),
                      );
                    },
                  ),
                ),
                SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: answers.length == questions.length
                        ? () {
                            Navigator.pop(context);
                            _showConsultMemberPickerBeforeSubmit(answers);
                          }
                        : null,
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _kPrimaryPurple,
                      disabledBackgroundColor: Colors.grey[300],
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: Text(
                      answers.length == questions.length ? '下一步：选择咨询人' : '请回答所有问题 (${answers.length}/${questions.length})',
                      style: const TextStyle(color: Colors.white),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  void _showConsultMemberPickerBeforeSubmit(Map<int, int> answers) async {
    int? selectedMemberId;
    List<dynamic> members = [];
    try {
      final res = await _api.getFamilyMembers();
      if (res.statusCode == 200) {
        final data = res.data;
        members = (data is Map ? (data['items'] ?? data['data'] ?? data) : data) as List;
      }
    } catch (_) {}
    if (members.isEmpty) {
      members = [{'id': 0, 'relation_type_name': '本人', 'is_self': true}];
    }
    if (!mounted) return;
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: EdgeInsets.only(left: 24, right: 24, top: 20, bottom: MediaQuery.of(ctx).viewInsets.bottom + 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('选择本次测评的咨询人', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 8),
              const Text('选定后立即提交测评', style: TextStyle(color: Colors.grey, fontSize: 12)),
              const SizedBox(height: 16),
              ConstrainedBox(
                constraints: const BoxConstraints(maxHeight: 280),
                child: ListView.builder(
                  shrinkWrap: true,
                  itemCount: members.length,
                  itemBuilder: (_, idx) {
                    final m = members[idx] as Map;
                    final id = m['id'] as int?;
                    final name = (m['relation_type_name'] ?? m['nickname'] ?? '本人').toString();
                    final selected = selectedMemberId == id;
                    return ListTile(
                      title: Text(name),
                      trailing: selected ? const Icon(Icons.check_circle, color: _kPrimaryPurple) : const Icon(Icons.radio_button_unchecked, color: Colors.grey),
                      onTap: () => setSheetState(() => selectedMemberId = id),
                    );
                  },
                ),
              ),
              const SizedBox(height: 12),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: selectedMemberId == null ? null : () {
                    Navigator.pop(ctx);
                    _submitConstitutionTest(answers, familyMemberId: selectedMemberId);
                  },
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _kPrimaryPurple,
                    disabledBackgroundColor: Colors.grey[300],
                    padding: const EdgeInsets.symmetric(vertical: 14),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                  ),
                  child: const Text('确认咨询人并提交测评', style: TextStyle(color: Colors.white)),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _submitConstitutionTest(Map<int, int> answers, {int? familyMemberId}) async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (_) => const Center(
        child: Card(
          child: Padding(
            padding: EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                CircularProgressIndicator(color: _kPrimaryPurple),
                SizedBox(height: 16),
                Text('正在分析体质...'),
              ],
            ),
          ),
        ),
      ),
    );

    try {
      final answersList = answers.entries.map((e) => {
        'question_id': e.key,
        'answer_value': e.value.toString(),
      }).toList();
      final payload = <String, dynamic>{
        'answers': answersList,
      };
      if (familyMemberId != null && familyMemberId != 0) {
        payload['family_member_id'] = familyMemberId;
      }
      final response = await _api.postConstitutionTest(payload);

      if (!mounted) return;
      Navigator.of(context).pop();

      if (response.statusCode == 200) {
        final data = response.data is Map ? response.data as Map<String, dynamic> : <String, dynamic>{};
        final resultData = data['data'] ?? data;
        final constitutionType = (resultData is Map ? resultData['constitution_type'] : null)?.toString() ?? '平和质';
        final description = (resultData is Map ? resultData['description'] : null)?.toString() ?? '';
        final diagnosisId = resultData is Map ? resultData['id'] : null;

        _loadDiagnosisList();
        _showConsultMemberPicker(constitutionType, description, diagnosisId);
      } else {
        _showError('分析失败，请重试');
      }
    } catch (_) {
      if (mounted) {
        Navigator.of(context).pop();
        _showError('网络异常，请重试');
      }
    }
  }

  void _showConsultMemberPicker(String constitutionType, String description, dynamic diagnosisId) {
    int? selectedMemberId;
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(20))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setSheetState) => Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 20),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: _kPrimaryPurple.withOpacity(0.06),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    const Icon(Icons.spa, color: _kPrimaryPurple, size: 22),
                    const SizedBox(width: 10),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('测评结果: $constitutionType', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: _kPrimaryPurple)),
                          if (description.isNotEmpty) ...[
                            const SizedBox(height: 4),
                            Text(description, style: TextStyle(fontSize: 13, color: Colors.grey[600]), maxLines: 2, overflow: TextOverflow.ellipsis),
                          ],
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 20),
              const Text('为谁咨询调理方案？', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold)),
              const SizedBox(height: 16),
              if (_membersLoading)
                const Center(child: CircularProgressIndicator(color: _kPrimaryPurple))
              else
                Wrap(
                  spacing: 12,
                  runSpacing: 12,
                  children: _familyMembers.map((member) {
                    final isSelf = member['is_self'] == true;
                    final id = isSelf ? null : member['id'] as int?;
                    final isSelected = selectedMemberId == id;
                    final relation = member['relationship_type']?.toString() ?? '本人';
                    final nickname = member['nickname']?.toString() ?? '';
                    final displayName = nickname.isNotEmpty ? nickname : relation;
                    final tagColor = _getMemberColor(relation);

                    return GestureDetector(
                      onTap: () => setSheetState(() => selectedMemberId = id),
                      child: Container(
                        width: 80,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        decoration: BoxDecoration(
                          color: isSelected ? _kPrimaryPurple.withOpacity(0.08) : const Color(0xFFF5F5F5),
                          borderRadius: BorderRadius.circular(12),
                          border: Border.all(
                            color: isSelected ? _kPrimaryPurple : Colors.transparent,
                            width: 2,
                          ),
                        ),
                        child: Column(
                          children: [
                            Container(
                              width: 40, height: 40,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                color: isSelected ? tagColor : const Color(0xFFE8E8E8),
                              ),
                              alignment: Alignment.center,
                              child: Text(
                                relation.length > 2 ? relation.substring(0, 2) : relation,
                                style: TextStyle(
                                  fontSize: 13, fontWeight: FontWeight.w600,
                                  color: isSelected ? Colors.white : const Color(0xFF666666),
                                ),
                              ),
                            ),
                            const SizedBox(height: 6),
                            Text(displayName, style: TextStyle(fontSize: 12, color: isSelected ? _kPrimaryPurple : const Color(0xFF666666)), overflow: TextOverflow.ellipsis),
                          ],
                        ),
                      ),
                    );
                  }).toList(),
                ),
              const SizedBox(height: 20),
              SizedBox(
                width: double.infinity,
                child: Container(
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [_kPrimaryPurple, _kPrimaryPink]),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: ElevatedButton(
                    onPressed: () {
                      Navigator.pop(ctx);
                      Navigator.pushNamed(context, '/chat', arguments: {
                        'type': 'constitution',
                        'family_member_id': selectedMemberId,
                        'summary': '体质分析: $constitutionType - $description',
                        'initial_message': '我的体质测评结果是$constitutionType，请提供养生调理建议',
                      });
                    },
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent,
                      shadowColor: Colors.transparent,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text('咨询AI调理方案'),
                  ),
                ),
              ),
              const SizedBox(height: 12),
              if (diagnosisId != null)
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () {
                      Navigator.pop(ctx);
                      Navigator.pushNamed(context, '/tcm-diagnosis-detail', arguments: {
                        'id': diagnosisId,
                        'constitution_type': constitutionType,
                        'description': description,
                      });
                    },
                    style: OutlinedButton.styleFrom(
                      foregroundColor: _kPrimaryPurple,
                      side: const BorderSide(color: _kPrimaryPurple),
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text('查看详细分析报告'),
                  ),
                ),
              const SizedBox(height: 8),
            ],
          ),
        ),
      ),
    );
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(msg), backgroundColor: Colors.red[400]),
    );
  }

  String _formatTime(String? timeStr) {
    if (timeStr == null || timeStr.isEmpty) return '';
    try {
      final dt = DateTime.parse(timeStr);
      return '${dt.month.toString().padLeft(2, '0')}-${dt.day.toString().padLeft(2, '0')} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    } catch (_) {
      return timeStr;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '中医辨证'),
      body: RefreshIndicator(
        color: _kPrimaryPurple,
        onRefresh: () => Future.wait([_loadTcmConfig(), _loadDiagnosisList()]),
        child: SingleChildScrollView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildBanner(),
              const SizedBox(height: 24),
              const Text('诊断工具', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              if (_configLoading)
                const Padding(
                  padding: EdgeInsets.all(20),
                  child: Center(child: CircularProgressIndicator(color: _kPrimaryPurple)),
                )
              else
                ..._visibleFunctions.map(_buildFunctionCard),
              const SizedBox(height: 24),
              _buildDiagnosisHistorySection(),
              const SizedBox(height: 24),
              const Text('九种体质', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 12),
              _buildConstitutionGrid(),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildBanner() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        gradient: const LinearGradient(colors: [_kPrimaryPurple, _kPrimaryPink]),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        children: [
          Container(
            width: 56, height: 56,
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.2),
              borderRadius: BorderRadius.circular(14),
            ),
            child: const Icon(Icons.spa, color: Colors.white, size: 30),
          ),
          const SizedBox(width: 16),
          const Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('中医智能辨证', style: TextStyle(color: Colors.white, fontSize: 18, fontWeight: FontWeight.bold)),
                SizedBox(height: 4),
                Text('结合望闻问切，AI辅助辨证施治', style: TextStyle(color: Colors.white70, fontSize: 13)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFunctionCard(Map<String, dynamic> func) {
    return GestureDetector(
      onTap: () {
        if (func['type'] == 'constitution') {
          _showConstitutionTest();
        } else {
          _takeDiagnosePhoto(func['type']);
        }
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 12),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 8, offset: const Offset(0, 2)),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 48, height: 48,
              decoration: BoxDecoration(
                color: (func['color'] as Color).withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(func['icon'], color: func['color'], size: 26),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(func['title'], style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                  const SizedBox(height: 2),
                  Text(func['desc'], style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: Colors.grey[400]),
          ],
        ),
      ),
    );
  }

  Widget _buildDiagnosisHistorySection() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            const Text('历史记录', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            if (_diagnosisList.isNotEmpty)
              Text('共${_diagnosisList.length}条', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
          ],
        ),
        const SizedBox(height: 12),
        if (_diagnosisLoading)
          const Padding(
            padding: EdgeInsets.all(20),
            child: Center(child: CircularProgressIndicator(color: _kPrimaryPurple)),
          )
        else if (_diagnosisList.isEmpty)
          Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                children: [
                  Icon(Icons.spa_outlined, size: 48, color: Colors.grey[300]),
                  const SizedBox(height: 12),
                  Text('暂无诊断记录', style: TextStyle(color: Colors.grey[500])),
                  const SizedBox(height: 6),
                  Text('完成体质测评后记录将显示在这里', style: TextStyle(color: Colors.grey[400], fontSize: 13)),
                ],
              ),
            ),
          )
        else
          ..._diagnosisList.map(_buildDiagnosisCard),
      ],
    );
  }

  Widget _buildDiagnosisCard(Map<String, dynamic> item) {
    final constitutionType = item['constitution_type']?.toString() ?? item['type']?.toString() ?? '未知';
    final description = item['description']?.toString() ?? item['summary']?.toString() ?? '';
    final createdAt = item['created_at']?.toString() ?? '';
    final memberName = item['family_member_name']?.toString() ?? item['member_name']?.toString() ?? '本人';
    final diagnosisId = item['id'];

    final typeColors = <String, Color>{
      '平和质': const Color(0xFF52C41A),
      '气虚质': const Color(0xFF1890FF),
      '阳虚质': const Color(0xFF13C2C2),
      '阴虚质': const Color(0xFFFA8C16),
      '痰湿质': const Color(0xFF722ED1),
      '湿热质': const Color(0xFFEB2F96),
      '血瘀质': const Color(0xFFFF4D4F),
      '气郁质': const Color(0xFF2F54EB),
      '特禀质': const Color(0xFF8C8C8C),
    };
    final typeColor = typeColors[constitutionType] ?? _kPrimaryPurple;

    return GestureDetector(
      onTap: () {
        Navigator.pushNamed(context, '/tcm-diagnosis-detail', arguments: {
          'id': diagnosisId,
          'constitution_type': constitutionType,
          'description': description,
        });
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(color: Colors.black.withOpacity(0.03), blurRadius: 6, offset: const Offset(0, 2)),
          ],
        ),
        child: Row(
          children: [
            Container(
              width: 48, height: 48,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: typeColor.withOpacity(0.1),
              ),
              child: Icon(Icons.spa, color: typeColor, size: 24),
            ),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Text(constitutionType, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: typeColor)),
                      const SizedBox(width: 8),
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: _getMemberColor(memberName).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(memberName, style: TextStyle(fontSize: 10, color: _getMemberColor(memberName), fontWeight: FontWeight.w500)),
                      ),
                    ],
                  ),
                  if (description.isNotEmpty) ...[
                    const SizedBox(height: 4),
                    Text(description, style: TextStyle(fontSize: 13, color: Colors.grey[500]), maxLines: 1, overflow: TextOverflow.ellipsis),
                  ],
                  const SizedBox(height: 4),
                  Text(_formatTime(createdAt), style: TextStyle(fontSize: 12, color: Colors.grey[400])),
                ],
              ),
            ),
            Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
          ],
        ),
      ),
    );
  }

  Widget _buildConstitutionGrid() {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        childAspectRatio: 0.9,
        crossAxisSpacing: 10,
        mainAxisSpacing: 10,
      ),
      itemCount: _constitutions.length,
      itemBuilder: (context, index) {
        final item = _constitutions[index];
        return Container(
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(12),
          ),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.spa, color: _kPrimaryPurple.withOpacity(0.6 + index * 0.04), size: 28),
              const SizedBox(height: 6),
              Text(item['name']!, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
              const SizedBox(height: 2),
              Text(
                item['desc']!,
                style: TextStyle(fontSize: 10, color: Colors.grey[500]),
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        );
      },
    );
  }
}
