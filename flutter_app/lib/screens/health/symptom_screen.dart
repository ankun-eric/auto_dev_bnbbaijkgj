import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/disease_tag_selector.dart';

const _kPrimaryGreen = Color(0xFF52C41A);

const _kRelationColors = <String, Color>{
  '本人': Color(0xFF1677FF),
  '爸爸': Color(0xFFFA8C16),
  '父亲': Color(0xFFFA8C16),
  '妈妈': Color(0xFFEB2F96),
  '母亲': Color(0xFFEB2F96),
  '配偶': Color(0xFF722ED1),
  '子女': Color(0xFF13C2C2),
};

Color _getMemberTagColor(String? relation) {
  if (relation == null || relation.isEmpty) return const Color(0xFF1677FF);
  return _kRelationColors[relation] ?? const Color(0xFF8C8C8C);
}

class SymptomScreen extends StatefulWidget {
  const SymptomScreen({super.key});

  @override
  State<SymptomScreen> createState() => _SymptomScreenState();
}

class _SymptomScreenState extends State<SymptomScreen> {
  final ApiService _apiService = ApiService();

  // 3-step flow: 0=选择部位+症状+持续时间, 1=选择咨询人, 2=AI分析
  int _currentStep = 0;

  // Step 0 sub-steps (within the same page)
  int _symptomSubStep = 0; // 0=部位, 1=症状, 2=持续时间

  String? _selectedBodyPart;
  final List<String> _selectedSymptoms = [];
  String? _selectedDuration;

  // Step 1: Member selection
  List<Map<String, dynamic>> _familyMembers = [];
  int? _selectedMemberId;
  String _selectedMemberName = '本人';
  bool _membersLoading = true;

  // Self basic info
  String _selfNickname = '';
  String _selfGender = '';
  String _selfBirthday = '';
  final TextEditingController _nicknameController = TextEditingController();
  Map<String, String> _selfErrors = {};

  // Health profile
  List<String> _chronicPresets = [];
  List<String> _allergyPresets = [];
  List<String> _geneticPresets = [];
  bool _presetsLoading = true;
  List<dynamic> _chronicDiseases = [];
  List<dynamic> _allergies = [];
  List<dynamic> _geneticDiseases = [];

  static const List<String> _durationOptions = [
    '刚刚出现', '几小时内', '1-3天', '3-7天', '1-2周', '2周以上', '1个月以上', '3个月以上',
  ];

  final Map<String, List<String>> _bodyPartSymptoms = {
    '头部': ['头痛', '头晕', '耳鸣', '视力模糊', '鼻塞', '咽喉痛'],
    '胸部': ['胸闷', '胸痛', '心悸', '呼吸困难', '咳嗽', '气短'],
    '腹部': ['胃痛', '腹胀', '腹泻', '便秘', '恶心', '呕吐'],
    '四肢': ['关节痛', '肌肉酸痛', '手脚麻木', '水肿', '抽筋', '无力'],
    '皮肤': ['皮疹', '瘙痒', '红肿', '脱皮', '色素沉着', '溃疡'],
    '全身': ['发热', '疲劳', '失眠', '食欲不振', '体重变化', '多汗'],
  };

  @override
  void initState() {
    super.initState();
    _loadFamilyMembers();
    _loadPresets();
    _loadSelfProfile();
  }

  @override
  void dispose() {
    _nicknameController.dispose();
    super.dispose();
  }

  Future<void> _loadFamilyMembers() async {
    try {
      final response = await _apiService.getFamilyMembers();
      if (response.statusCode == 200 && mounted) {
        final items = response.data['items'] as List? ?? [];
        setState(() {
          _familyMembers = items.map((e) {
            final m = Map<String, dynamic>.from(e as Map);
            return {
              'id': m['id'],
              'name': m['nickname'] ?? m['name'] ?? '',
              'relation': m['relation_type_name'] ?? m['relationship_type'] ?? '本人',
              'is_self': m['is_self'] ?? false,
              'gender': (m['gender'] ?? '').toString(),
              'birthday': (m['birthday'] ?? '').toString(),
            };
          }).toList();
          _membersLoading = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _membersLoading = false);
    }
  }

  Future<void> _loadPresets() async {
    setState(() => _presetsLoading = true);
    try {
      final results = await Future.wait([
        _apiService.getDiseasePresets('chronic'),
        _apiService.getDiseasePresets('allergy'),
        _apiService.getDiseasePresets('genetic'),
      ]);
      if (mounted) {
        setState(() {
          _chronicPresets = _parsePresets(results[0].data);
          _allergyPresets = _parsePresets(results[1].data);
          _geneticPresets = _parsePresets(results[2].data);
        });
      }
    } catch (_) {}
    if (mounted) setState(() => _presetsLoading = false);
  }

  List<String> _parsePresets(dynamic data) {
    if (data is List) {
      return data.map((e) => e is Map ? (e['name'] ?? '').toString() : e.toString()).toList();
    }
    if (data is Map) {
      final items = data['items'] ?? data['data'] ?? data['presets'];
      if (items is List) {
        return items.map((e) => e is Map ? (e['name'] ?? '').toString() : e.toString()).toList();
      }
    }
    return [];
  }

  Future<void> _loadSelfProfile() async {
    try {
      final response = await _apiService.getHealthProfile();
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map ? response.data as Map : {};
        setState(() {
          _selfNickname = (data['nickname'] ?? '').toString();
          _selfGender = (data['gender'] ?? '').toString();
          _selfBirthday = (data['birthday'] ?? '').toString();
          _nicknameController.text = _selfNickname;
          _selfErrors = {};
        });
      }
    } catch (_) {}
  }

  bool _validateSelfInfo() {
    final errors = <String, String>{};
    if (_selfNickname.trim().isEmpty) errors['nickname'] = '请输入姓名';
    if (_selfGender.isEmpty) errors['gender'] = '请选择性别';
    if (_selfBirthday.isEmpty) errors['birthday'] = '请选择出生日期';
    setState(() => _selfErrors = errors);
    if (errors.isNotEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('请填写完整的必填信息'), duration: Duration(seconds: 2)),
      );
      return false;
    }
    return true;
  }

  Future<void> _pickBirthday() async {
    final initial = _selfBirthday.isNotEmpty
        ? (DateTime.tryParse(_selfBirthday) ?? DateTime(2000))
        : DateTime(2000);
    final date = await showDatePicker(
      context: context,
      initialDate: initial,
      firstDate: DateTime(1900),
      lastDate: DateTime.now(),
      builder: (context, child) {
        return Theme(
          data: Theme.of(context).copyWith(colorScheme: const ColorScheme.light(primary: _kPrimaryGreen)),
          child: child!,
        );
      },
    );
    if (date != null) {
      setState(() {
        _selfBirthday = '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
      });
    }
  }

  Future<void> _saveHealthProfile() async {
    final data = <String, dynamic>{
      'chronic_diseases': _chronicDiseases,
      'allergies': _allergies,
      'genetic_diseases': _geneticDiseases,
      'nickname': _selfNickname.trim(),
      'gender': _selfGender,
      'birthday': _selfBirthday,
    };
    try {
      if (_selectedMemberId != null) {
        await _apiService.updateMemberHealthProfile(_selectedMemberId!, data);
      } else {
        await _apiService.updateHealthProfile(data);
      }
    } catch (_) {}
  }

  @override
  Widget build(BuildContext context) {
    if (_currentStep == 1) {
      return _buildMemberSelectionPage();
    }

    return Scaffold(
      appBar: const CustomAppBar(title: '症状自查'),
      body: Column(
        children: [
          _buildStepIndicator(),
          Expanded(child: _buildSymptomContent()),
          _buildBottomButton(),
        ],
      ),
    );
  }

  Widget _buildStepIndicator() {
    const steps = ['选择症状', '选择咨询人', 'AI分析'];
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      color: Colors.white,
      child: Row(
        children: List.generate(steps.length * 2 - 1, (index) {
          if (index.isOdd) {
            final stepIdx = index ~/ 2;
            return Expanded(
              child: Container(
                height: 2,
                color: _currentStep > stepIdx ? _kPrimaryGreen : Colors.grey[300],
              ),
            );
          }
          final stepIdx = index ~/ 2;
          final isActive = _currentStep >= stepIdx;
          final isDone = _currentStep > stepIdx;
          return GestureDetector(
            onTap: stepIdx < _currentStep ? () => setState(() => _currentStep = stepIdx) : null,
            child: Column(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isActive ? _kPrimaryGreen : Colors.grey[300],
                  ),
                  child: Center(
                    child: isDone
                        ? const Icon(Icons.check, size: 16, color: Colors.white)
                        : Text(
                            '${stepIdx + 1}',
                            style: TextStyle(color: isActive ? Colors.white : Colors.grey[600], fontSize: 13),
                          ),
                  ),
                ),
                const SizedBox(height: 4),
                Text(steps[stepIdx], style: TextStyle(fontSize: 11, color: isActive ? _kPrimaryGreen : Colors.grey[500])),
              ],
            ),
          );
        }),
      ),
    );
  }

  Widget _buildSymptomContent() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildBodyPartSection(),
          if (_selectedBodyPart != null) ...[
            const SizedBox(height: 16),
            _buildSymptomSection(),
          ],
          if (_selectedSymptoms.isNotEmpty) ...[
            const SizedBox(height: 16),
            _buildDurationSection(),
          ],
        ],
      ),
    );
  }

  Widget _buildBodyPartSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 24, height: 24,
                decoration: BoxDecoration(color: _kPrimaryGreen, borderRadius: BorderRadius.circular(6)),
                child: const Center(child: Text('1', style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold))),
              ),
              const SizedBox(width: 8),
              const Text('选择不适部位', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 16),
          GridView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3, childAspectRatio: 1.4, crossAxisSpacing: 10, mainAxisSpacing: 10,
            ),
            itemCount: _bodyPartSymptoms.keys.length,
            itemBuilder: (context, index) {
              final part = _bodyPartSymptoms.keys.elementAt(index);
              final isSelected = _selectedBodyPart == part;
              final icons = [Icons.face, Icons.favorite, Icons.restaurant, Icons.accessibility, Icons.brush, Icons.self_improvement];
              return GestureDetector(
                onTap: () => setState(() {
                  _selectedBodyPart = part;
                  _selectedSymptoms.clear();
                }),
                child: Container(
                  decoration: BoxDecoration(
                    color: isSelected ? const Color(0xFFF0F9EB) : const Color(0xFFF5F5F5),
                    borderRadius: BorderRadius.circular(12),
                    border: Border.all(color: isSelected ? _kPrimaryGreen : Colors.transparent, width: isSelected ? 2 : 1),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(icons[index], size: 28, color: isSelected ? _kPrimaryGreen : Colors.grey[600]),
                      const SizedBox(height: 6),
                      Text(part, style: TextStyle(
                        fontSize: 13, fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                        color: isSelected ? _kPrimaryGreen : Colors.grey[800],
                      )),
                    ],
                  ),
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _buildSymptomSection() {
    final symptoms = _bodyPartSymptoms[_selectedBodyPart] ?? [];
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 24, height: 24,
                decoration: BoxDecoration(color: _kPrimaryGreen, borderRadius: BorderRadius.circular(6)),
                child: const Center(child: Text('2', style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold))),
              ),
              const SizedBox(width: 8),
              Text('$_selectedBodyPart - 选择症状', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: symptoms.map((symptom) {
              final isSelected = _selectedSymptoms.contains(symptom);
              return GestureDetector(
                onTap: () {
                  setState(() {
                    if (isSelected) {
                      _selectedSymptoms.remove(symptom);
                    } else {
                      _selectedSymptoms.add(symptom);
                    }
                  });
                },
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                  decoration: BoxDecoration(
                    color: isSelected ? _kPrimaryGreen : const Color(0xFFF5F5F5),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: isSelected ? _kPrimaryGreen : Colors.grey[300]!),
                  ),
                  child: Text(symptom, style: TextStyle(
                    color: isSelected ? Colors.white : Colors.grey[800],
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                  )),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildDurationSection() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                width: 24, height: 24,
                decoration: BoxDecoration(color: _kPrimaryGreen, borderRadius: BorderRadius.circular(6)),
                child: const Center(child: Text('3', style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.bold))),
              ),
              const SizedBox(width: 8),
              const Text('持续时间', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: _durationOptions.map((duration) {
              final isSelected = _selectedDuration == duration;
              return GestureDetector(
                onTap: () => setState(() => _selectedDuration = duration),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
                  decoration: BoxDecoration(
                    color: isSelected ? _kPrimaryGreen : const Color(0xFFF5F5F5),
                    borderRadius: BorderRadius.circular(20),
                    border: Border.all(color: isSelected ? _kPrimaryGreen : Colors.grey[300]!),
                  ),
                  child: Text(duration, style: TextStyle(
                    color: isSelected ? Colors.white : Colors.grey[800],
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                  )),
                ),
              );
            }).toList(),
          ),
        ],
      ),
    );
  }

  Widget _buildMemberSelectionPage() {
    return Scaffold(
      appBar: CustomAppBar(
        title: '选择咨询对象',
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => setState(() => _currentStep = 0),
        ),
      ),
      body: Column(
        children: [
          _buildStepIndicator(),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.people, color: _kPrimaryGreen, size: 20),
                            SizedBox(width: 8),
                            Text('为谁咨询？', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text('选择后将为该成员生成专属健康分析', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                        const SizedBox(height: 16),
                        if (_membersLoading)
                          const Center(
                            child: Padding(
                              padding: EdgeInsets.all(20),
                              child: SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)),
                            ),
                          )
                        else
                          Wrap(
                            spacing: 12,
                            runSpacing: 12,
                            children: [
                              ..._familyMembers.map((member) {
                                final isSelf = member['is_self'] == true;
                                final id = isSelf ? null : member['id'] as int?;
                                final isSelected = _selectedMemberId == id &&
                                    _selectedMemberName == (member['relation']?.toString() ?? '本人');
                                final relation = member['relation']?.toString() ?? '本人';
                                final tagColor = _getMemberTagColor(relation);

                                return GestureDetector(
                                  onTap: () {
                                    setState(() {
                                      _selectedMemberId = id;
                                      _selectedMemberName = relation;
                                      _selfErrors = {};
                                    });
                                    if (isSelf || id == null) {
                                      _loadSelfProfile();
                                    } else {
                                      setState(() {
                                        _selfNickname = (member['name'] ?? '').toString();
                                        _selfGender = (member['gender'] ?? '').toString();
                                        _selfBirthday = (member['birthday'] ?? '').toString();
                                        _nicknameController.text = _selfNickname;
                                      });
                                    }
                                  },
                                  child: Container(
                                    width: 80,
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                    decoration: BoxDecoration(
                                      color: isSelected ? _kPrimaryGreen.withOpacity(0.08) : const Color(0xFFF5F5F5),
                                      borderRadius: BorderRadius.circular(12),
                                      border: Border.all(color: isSelected ? _kPrimaryGreen : Colors.transparent, width: 2),
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
                                        Text(relation, style: TextStyle(
                                          fontSize: 12,
                                          color: isSelected ? _kPrimaryGreen : const Color(0xFF666666),
                                        ), overflow: TextOverflow.ellipsis),
                                      ],
                                    ),
                                  ),
                                );
                              }),
                            ],
                          ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),
                  _buildSelfBasicInfoForm(),
                  const SizedBox(height: 16),
                  if (!_presetsLoading) ...[
                    DiseaseTagSelector(
                      title: '既往病史', presets: _chronicPresets, selectedItems: _chronicDiseases,
                      onChanged: (items) => setState(() => _chronicDiseases = items), color: const Color(0xFFFA8C16),
                    ),
                    DiseaseTagSelector(
                      title: '过敏史', presets: _allergyPresets, selectedItems: _allergies,
                      onChanged: (items) => setState(() => _allergies = items), color: const Color(0xFFEB2F96),
                    ),
                    DiseaseTagSelector(
                      title: '家族遗传病史', presets: _geneticPresets, selectedItems: _geneticDiseases,
                      onChanged: (items) => setState(() => _geneticDiseases = items), color: const Color(0xFF1890FF),
                    ),
                  ],
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF0F9EB),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: _kPrimaryGreen.withOpacity(0.2)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.info_outline, size: 18, color: _kPrimaryGreen),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            '症状：${_selectedSymptoms.join("、")}  持续：${_selectedDuration ?? "未选择"}',
                            style: TextStyle(fontSize: 13, color: Colors.grey[700]),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
          Container(
            padding: EdgeInsets.only(
              left: 16, right: 16, top: 12,
              bottom: MediaQuery.of(context).padding.bottom + 12,
            ),
            color: Colors.white,
            child: Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: () => setState(() => _currentStep = 0),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      side: const BorderSide(color: _kPrimaryGreen),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text('上一步', style: TextStyle(color: _kPrimaryGreen)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: ElevatedButton.icon(
                    onPressed: () {
                      if (!_validateSelfInfo()) return;
                      _saveHealthProfile();
                      setState(() => _currentStep = 2);
                      Navigator.pushNamed(context, '/ai');
                    },
                    icon: const Icon(Icons.auto_awesome, size: 18),
                    label: const Text('确认并AI分析'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: _kPrimaryGreen,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      elevation: 0,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSelfBasicInfoForm() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12)),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.person, color: _kPrimaryGreen, size: 20),
              SizedBox(width: 8),
              Text('基本信息', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 16),
          _buildFormLabel('姓名', true),
          const SizedBox(height: 8),
          TextField(
            controller: _nicknameController,
            onChanged: (v) => setState(() {
              _selfNickname = v;
              _selfErrors.remove('nickname');
            }),
            decoration: InputDecoration(
              hintText: '请输入姓名',
              hintStyle: TextStyle(color: Colors.grey[400], fontSize: 14),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              filled: true, fillColor: const Color(0xFFF5F5F5),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(8), borderSide: BorderSide.none),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: _selfErrors.containsKey('nickname')
                    ? const BorderSide(color: Color(0xFFFF4D4F)) : BorderSide.none,
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: const BorderSide(color: _kPrimaryGreen),
              ),
            ),
          ),
          if (_selfErrors.containsKey('nickname')) _buildErrorText(_selfErrors['nickname']!),
          const SizedBox(height: 16),
          _buildFormLabel('性别', true),
          const SizedBox(height: 8),
          Row(
            children: ['male', 'female'].map((g) {
              final isSelected = _selfGender == g;
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() { _selfGender = g; _selfErrors.remove('gender'); }),
                  child: Container(
                    margin: EdgeInsets.only(right: g == 'male' ? 6 : 0, left: g == 'female' ? 6 : 0),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: isSelected ? const Color(0xFFF0F9EB) : const Color(0xFFF5F5F5),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected ? _kPrimaryGreen : _selfErrors.containsKey('gender') ? const Color(0xFFFF4D4F) : Colors.transparent,
                        width: isSelected ? 2 : 1,
                      ),
                    ),
                    alignment: Alignment.center,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(g == 'male' ? Icons.male : Icons.female, size: 18, color: isSelected ? _kPrimaryGreen : Colors.grey[600]),
                        const SizedBox(width: 4),
                        Text(g == 'male' ? '男' : '女', style: TextStyle(
                          fontSize: 14, fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                          color: isSelected ? _kPrimaryGreen : Colors.grey[800],
                        )),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
          if (_selfErrors.containsKey('gender')) _buildErrorText(_selfErrors['gender']!),
          const SizedBox(height: 16),
          _buildFormLabel('出生日期', true),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: _pickBirthday,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(color: _selfErrors.containsKey('birthday') ? const Color(0xFFFF4D4F) : Colors.transparent),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      _selfBirthday.isNotEmpty ? _selfBirthday : '请选择出生日期',
                      style: TextStyle(fontSize: 14, color: _selfBirthday.isNotEmpty ? Colors.black87 : Colors.grey[400]),
                    ),
                  ),
                  Icon(Icons.calendar_today, size: 18, color: Colors.grey[400]),
                ],
              ),
            ),
          ),
          if (_selfErrors.containsKey('birthday')) _buildErrorText(_selfErrors['birthday']!),
        ],
      ),
    );
  }

  Widget _buildFormLabel(String text, bool required) {
    return RichText(
      text: TextSpan(
        text: text,
        style: TextStyle(fontSize: 13, color: Colors.grey[600]),
        children: required ? const [TextSpan(text: ' *', style: TextStyle(color: Color(0xFFFF4D4F)))] : null,
      ),
    );
  }

  Widget _buildErrorText(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(text, style: const TextStyle(fontSize: 12, color: Color(0xFFFF4D4F))),
    );
  }

  Widget _buildBottomButton() {
    final canProceed = _selectedBodyPart != null && _selectedSymptoms.isNotEmpty && _selectedDuration != null;
    return Container(
      padding: EdgeInsets.only(left: 16, right: 16, top: 12, bottom: MediaQuery.of(context).padding.bottom + 12),
      color: Colors.white,
      child: SizedBox(
        width: double.infinity,
        child: ElevatedButton(
          onPressed: canProceed ? () => setState(() => _currentStep = 1) : null,
          style: ElevatedButton.styleFrom(
            backgroundColor: _kPrimaryGreen,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 14),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            elevation: 0,
          ),
          child: const Text('下一步：选择咨询人'),
        ),
      ),
    );
  }
}
