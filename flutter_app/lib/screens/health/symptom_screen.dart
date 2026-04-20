import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/health_profile_editor.dart';

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
  final GlobalKey<HealthProfileEditorState> _profileEditorKey = GlobalKey();

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
  String _selfHeight = '';
  String _selfWeight = '';
  Map<String, String> _selfErrors = {};

  // Health profile
  List<String> _chronicPresets = [];
  List<String> _allergyPresets = [];
  List<String> _geneticPresets = [];
  bool _presetsLoading = true;
  List<dynamic> _chronicDiseases = [];
  List<dynamic> _allergies = [];
  List<dynamic> _geneticDiseases = [];

  /// 初始档案快照（用于 dirty 判定）
  HealthProfileSnapshot? _initialProfile;

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
          _selfHeight = (data['height'] ?? '').toString();
          _selfWeight = (data['weight'] ?? '').toString();
          if (_selfHeight == '0' || _selfHeight == '0.0') _selfHeight = '';
          if (_selfWeight == '0' || _selfWeight == '0.0') _selfWeight = '';
          _chronicDiseases = List<dynamic>.from(data['chronic_diseases'] ?? []);
          _allergies = List<dynamic>.from(data['allergies'] ?? []);
          _geneticDiseases = List<dynamic>.from(data['genetic_diseases'] ?? []);
          _selfErrors = {};
          _initialProfile = _snapshotOfCurrent();
        });
      }
    } catch (_) {}
  }

  Future<void> _loadMemberProfile(int memberId, Map<String, dynamic> member) async {
    try {
      final response = await _apiService.getMemberHealthProfile(memberId);
      if (response.statusCode == 200 && mounted) {
        final data = response.data is Map ? response.data as Map : {};
        setState(() {
          _selfNickname = (data['nickname'] ?? member['name'] ?? '').toString();
          _selfGender = (data['gender'] ?? member['gender'] ?? '').toString();
          _selfBirthday = (data['birthday'] ?? member['birthday'] ?? '').toString();
          _selfHeight = (data['height'] ?? '').toString();
          _selfWeight = (data['weight'] ?? '').toString();
          if (_selfHeight == '0' || _selfHeight == '0.0') _selfHeight = '';
          if (_selfWeight == '0' || _selfWeight == '0.0') _selfWeight = '';
          _chronicDiseases = List<dynamic>.from(data['chronic_diseases'] ?? []);
          _allergies = List<dynamic>.from(data['allergies'] ?? []);
          _geneticDiseases = List<dynamic>.from(data['genetic_diseases'] ?? []);
          _selfErrors = {};
          _initialProfile = _snapshotOfCurrent();
        });
      }
    } catch (_) {
      if (mounted) {
        setState(() {
          _selfNickname = (member['name'] ?? '').toString();
          _selfGender = (member['gender'] ?? '').toString();
          _selfBirthday = (member['birthday'] ?? '').toString();
          _selfHeight = '';
          _selfWeight = '';
          _chronicDiseases = [];
          _allergies = [];
          _geneticDiseases = [];
          _selfErrors = {};
          _initialProfile = _snapshotOfCurrent();
        });
      }
    }
  }

  HealthProfileSnapshot _snapshotOfCurrent() => HealthProfileSnapshot(
        nickname: _selfNickname,
        birthday: _selfBirthday,
        gender: _selfGender,
        height: _selfHeight,
        weight: _selfWeight,
        chronicDiseases: List<dynamic>.from(_chronicDiseases),
        allergies: List<dynamic>.from(_allergies),
        geneticDiseases: List<dynamic>.from(_geneticDiseases),
      );

  void _discardProfileChanges() {
    final init = _initialProfile;
    if (init == null) return;
    setState(() {
      _selfNickname = init.nickname;
      _selfGender = init.gender;
      _selfBirthday = init.birthday;
      _selfHeight = init.height;
      _selfWeight = init.weight;
      _chronicDiseases = List<dynamic>.from(init.chronicDiseases);
      _allergies = List<dynamic>.from(init.allergies);
      _geneticDiseases = List<dynamic>.from(init.geneticDiseases);
      _selfErrors = {};
    });
  }

  Future<bool> _handleSaveProfileCallback(HealthProfileSnapshot profile) async {
    if (!_validateSelfInfo()) return false;
    final data = <String, dynamic>{
      'chronic_diseases': profile.chronicDiseases,
      'allergies': profile.allergies,
      'genetic_diseases': profile.geneticDiseases,
      'nickname': profile.nickname.trim(),
      'gender': profile.gender,
      'birthday': profile.birthday,
    };
    if (profile.height.trim().isNotEmpty) {
      data['height'] = double.tryParse(profile.height.trim());
    }
    if (profile.weight.trim().isNotEmpty) {
      data['weight'] = double.tryParse(profile.weight.trim());
    }
    try {
      if (_selectedMemberId != null) {
        await _apiService.updateMemberHealthProfile(_selectedMemberId!, data);
      } else {
        await _apiService.updateHealthProfile(data);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('保存成功'), duration: Duration(seconds: 2)),
        );
        setState(() => _initialProfile = _snapshotOfCurrent());
      }
      return true;
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('保存失败，请稍后重试'), duration: Duration(seconds: 2)),
        );
      }
      return false;
    }
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

  Future<void> _saveHealthProfile() async {
    final data = <String, dynamic>{
      'chronic_diseases': _chronicDiseases,
      'allergies': _allergies,
      'genetic_diseases': _geneticDiseases,
      'nickname': _selfNickname.trim(),
      'gender': _selfGender,
      'birthday': _selfBirthday,
    };
    if (_selfHeight.trim().isNotEmpty) {
      data['height'] = double.tryParse(_selfHeight.trim());
    }
    if (_selfWeight.trim().isNotEmpty) {
      data['weight'] = double.tryParse(_selfWeight.trim());
    }
    try {
      if (_selectedMemberId != null) {
        await _apiService.updateMemberHealthProfile(_selectedMemberId!, data);
      } else {
        await _apiService.updateHealthProfile(data);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('健康档案信息已同步更新'),
            duration: Duration(seconds: 2),
          ),
        );
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
                                  onTap: () async {
                                    // 已选同一个成员直接忽略
                                    if (_selectedMemberId == id && _selectedMemberName == relation) return;
                                    // 拦截未保存修改
                                    if (_profileEditorKey.currentState?.hasUnsavedChanges() ?? false) {
                                      final choice = await showUnsavedChangesDialog(context, scene: 'switch');
                                      if (choice == 'cancel') return;
                                      if (choice == 'save') {
                                        final ok = await _profileEditorKey.currentState?.saveProfile() ?? false;
                                        if (!ok) return;
                                      } else if (choice == 'discard') {
                                        _discardProfileChanges();
                                      }
                                    }
                                    setState(() {
                                      _selectedMemberId = id;
                                      _selectedMemberName = relation;
                                      _selfErrors = {};
                                    });
                                    _profileEditorKey.currentState?.resetExpanded();
                                    if (isSelf || id == null) {
                                      _loadSelfProfile();
                                    } else {
                                      _loadMemberProfile(id, member);
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
                  if (!_presetsLoading)
                    HealthProfileEditor(
                      key: _profileEditorKey,
                      nickname: _selfNickname,
                      birthday: _selfBirthday,
                      gender: _selfGender,
                      height: _selfHeight,
                      weight: _selfWeight,
                      chronicDiseases: _chronicDiseases,
                      allergies: _allergies,
                      geneticDiseases: _geneticDiseases,
                      chronicPresets: _chronicPresets,
                      allergyPresets: _allergyPresets,
                      geneticPresets: _geneticPresets,
                      memberName: _selectedMemberName,
                      errors: _selfErrors.map((k, v) => MapEntry(k, v)),
                      mode: HealthProfileMode.existing,
                      initialProfile: _initialProfile,
                      onSaveProfile: _handleSaveProfileCallback,
                      memberEmoji: _selectedMemberName == '本人' ? '👤' : '👨‍👩‍👧',
                      onDiscardChanges: _discardProfileChanges,
                      onChanged: (changes) {
                        setState(() {
                          if (changes.containsKey('nickname')) {
                            _selfNickname = changes['nickname'];
                            _selfErrors.remove('nickname');
                          }
                          if (changes.containsKey('gender')) {
                            _selfGender = changes['gender'];
                            _selfErrors.remove('gender');
                          }
                          if (changes.containsKey('birthday')) {
                            _selfBirthday = changes['birthday'];
                            _selfErrors.remove('birthday');
                          }
                          if (changes.containsKey('height')) {
                            _selfHeight = changes['height'];
                          }
                          if (changes.containsKey('weight')) {
                            _selfWeight = changes['weight'];
                          }
                          if (changes.containsKey('chronic_diseases')) {
                            _chronicDiseases = changes['chronic_diseases'];
                          }
                          if (changes.containsKey('allergies')) {
                            _allergies = changes['allergies'];
                          }
                          if (changes.containsKey('genetic_diseases')) {
                            _geneticDiseases = changes['genetic_diseases'];
                          }
                          // editor 校验触发的错误回传
                          if (changes.containsKey('__errors')) {
                            final errs = changes['__errors'] as Map<String, String?>?;
                            if (errs != null) {
                              _selfErrors = {
                                for (final e in errs.entries)
                                  if (e.value != null) e.key: e.value!,
                              };
                            }
                          }
                        });
                      },
                    ),
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
                    onPressed: () async {
                      // 拦截未保存修改
                      if (_profileEditorKey.currentState?.hasUnsavedChanges() ?? false) {
                        final choice = await showUnsavedChangesDialog(context, scene: 'analyze');
                        if (choice == 'cancel') return;
                        if (choice == 'save') {
                          final ok = await _profileEditorKey.currentState?.saveProfile() ?? false;
                          if (!ok) return;
                        } else if (choice == 'discard') {
                          _discardProfileChanges();
                        }
                      }
                      if (!_validateSelfInfo()) return;
                      setState(() => _currentStep = 2);
                      Navigator.pushNamed(context, '/ai');
                    },
                    icon: const Icon(Icons.auto_awesome, size: 18),
                    label: const Text('开始AI分析'),
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
