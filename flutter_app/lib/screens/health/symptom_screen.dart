import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/disease_tag_selector.dart';

class SymptomScreen extends StatefulWidget {
  const SymptomScreen({super.key});

  @override
  State<SymptomScreen> createState() => _SymptomScreenState();
}

class _SymptomScreenState extends State<SymptomScreen> {
  final ApiService _apiService = ApiService();
  int _currentStep = 0;
  String? _selectedBodyPart;
  final List<String> _selectedSymptoms = [];

  // Member selection
  List<Map<String, dynamic>> _familyMembers = [];
  int? _selectedMemberId;
  String _selectedMemberName = '本人';
  bool _membersLoading = true;

  // Duration selection
  String? _selectedDuration;
  static const List<String> _durationOptions = [
    '刚刚出现',
    '几小时内',
    '1-3天',
    '3-7天',
    '1-2周',
    '2周以上',
    '1个月以上',
    '3个月以上',
  ];

  // Self basic info
  String _selfNickname = '';
  String _selfGender = '';
  String _selfBirthday = '';
  final TextEditingController _nicknameController = TextEditingController();
  Map<String, String> _selfErrors = {};

  // Health profile editing for selected member
  List<String> _chronicPresets = [];
  List<String> _allergyPresets = [];
  List<String> _geneticPresets = [];
  bool _presetsLoading = true;
  List<dynamic> _chronicDiseases = [];
  List<dynamic> _allergies = [];
  List<dynamic> _geneticDiseases = [];

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
              'relation':
                  m['relation_type_name'] ?? m['relationship_type'] ?? '本人',
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
      return data
          .map((e) => e is Map ? (e['name'] ?? '').toString() : e.toString())
          .toList();
    }
    if (data is Map) {
      final items = data['items'] ?? data['data'] ?? data['presets'];
      if (items is List) {
        return items
            .map(
                (e) => e is Map ? (e['name'] ?? '').toString() : e.toString())
            .toList();
      }
    }
    return [];
  }

  bool _isSelfSelected() {
    if (_selectedMemberId == null) return true;
    final member = _familyMembers.firstWhere(
      (m) => m['id'] == _selectedMemberId,
      orElse: () => <String, dynamic>{},
    );
    return member['is_self'] == true;
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
        const SnackBar(
          content: Text('请填写完整的必填信息'),
          duration: Duration(seconds: 2),
        ),
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
          data: Theme.of(context).copyWith(
            colorScheme: const ColorScheme.light(
              primary: Color(0xFF52C41A),
            ),
          ),
          child: child!,
        );
      },
    );
    if (date != null) {
      setState(() {
        _selfBirthday =
            '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')}';
      });
    }
  }

  Widget _buildSelfBasicInfoForm() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.person, color: Color(0xFF52C41A), size: 20),
              SizedBox(width: 8),
              Text('基本信息',
                  style: TextStyle(
                      fontSize: 16, fontWeight: FontWeight.w600)),
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
              contentPadding:
                  const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
              filled: true,
              fillColor: const Color(0xFFF5F5F5),
              border: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: BorderSide.none,
              ),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide: _selfErrors.containsKey('nickname')
                    ? const BorderSide(color: Color(0xFFFF4D4F))
                    : BorderSide.none,
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(8),
                borderSide:
                    const BorderSide(color: Color(0xFF52C41A)),
              ),
            ),
          ),
          if (_selfErrors.containsKey('nickname'))
            _buildErrorText(_selfErrors['nickname']!),
          const SizedBox(height: 16),
          _buildFormLabel('性别', true),
          const SizedBox(height: 8),
          Row(
            children: ['male', 'female'].map((g) {
              final isSelected = _selfGender == g;
              return Expanded(
                child: GestureDetector(
                  onTap: () => setState(() {
                    _selfGender = g;
                    _selfErrors.remove('gender');
                  }),
                  child: Container(
                    margin: EdgeInsets.only(
                        right: g == 'male' ? 6 : 0,
                        left: g == 'female' ? 6 : 0),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: isSelected
                          ? const Color(0xFFF0F9EB)
                          : const Color(0xFFF5F5F5),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(
                        color: isSelected
                            ? const Color(0xFF52C41A)
                            : _selfErrors.containsKey('gender')
                                ? const Color(0xFFFF4D4F)
                                : Colors.transparent,
                        width: isSelected ? 2 : 1,
                      ),
                    ),
                    alignment: Alignment.center,
                    child: Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          g == 'male' ? Icons.male : Icons.female,
                          size: 18,
                          color: isSelected
                              ? const Color(0xFF52C41A)
                              : Colors.grey[600],
                        ),
                        const SizedBox(width: 4),
                        Text(
                          g == 'male' ? '男' : '女',
                          style: TextStyle(
                            fontSize: 14,
                            fontWeight: isSelected
                                ? FontWeight.w600
                                : FontWeight.normal,
                            color: isSelected
                                ? const Color(0xFF52C41A)
                                : Colors.grey[800],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              );
            }).toList(),
          ),
          if (_selfErrors.containsKey('gender'))
            _buildErrorText(_selfErrors['gender']!),
          const SizedBox(height: 16),
          _buildFormLabel('出生日期', true),
          const SizedBox(height: 8),
          GestureDetector(
            onTap: _pickBirthday,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(
                  horizontal: 12, vertical: 12),
              decoration: BoxDecoration(
                color: const Color(0xFFF5F5F5),
                borderRadius: BorderRadius.circular(8),
                border: Border.all(
                  color: _selfErrors.containsKey('birthday')
                      ? const Color(0xFFFF4D4F)
                      : Colors.transparent,
                ),
              ),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      _selfBirthday.isNotEmpty
                          ? _selfBirthday
                          : '请选择出生日期',
                      style: TextStyle(
                        fontSize: 14,
                        color: _selfBirthday.isNotEmpty
                            ? Colors.black87
                            : Colors.grey[400],
                      ),
                    ),
                  ),
                  Icon(Icons.calendar_today,
                      size: 18, color: Colors.grey[400]),
                ],
              ),
            ),
          ),
          if (_selfErrors.containsKey('birthday'))
            _buildErrorText(_selfErrors['birthday']!),
        ],
      ),
    );
  }

  Widget _buildFormLabel(String text, bool required) {
    return RichText(
      text: TextSpan(
        text: text,
        style: TextStyle(fontSize: 13, color: Colors.grey[600]),
        children: required
            ? const [
                TextSpan(
                  text: ' *',
                  style: TextStyle(color: Color(0xFFFF4D4F)),
                ),
              ]
            : null,
      ),
    );
  }

  Widget _buildErrorText(String text) {
    return Padding(
      padding: const EdgeInsets.only(top: 4),
      child: Text(text,
          style: const TextStyle(
              fontSize: 12, color: Color(0xFFFF4D4F))),
    );
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
    return Scaffold(
      appBar: const CustomAppBar(title: '症状自查'),
      body: Column(
        children: [
          _buildStepIndicator(),
          Expanded(
            child: _currentStep == 0
                ? _buildMemberSelector()
                : _currentStep == 1
                    ? _buildBodyPartSelector()
                    : _currentStep == 2
                        ? _buildSymptomSelector()
                        : _currentStep == 3
                            ? _buildDurationSelector()
                            : _buildResultView(),
          ),
          _buildBottomButton(),
        ],
      ),
    );
  }

  Widget _buildStepIndicator() {
    const steps = ['为谁咨询', '选择部位', '选择症状', '持续时间', '查看结果'];
    return Container(
      padding: const EdgeInsets.all(16),
      color: Colors.white,
      child: Row(
        children: List.generate(steps.length * 2 - 1, (index) {
          if (index.isOdd) {
            final stepIdx = index ~/ 2;
            return Expanded(
              child: Container(
                height: 2,
                color: _currentStep > stepIdx
                    ? const Color(0xFF52C41A)
                    : Colors.grey[300],
              ),
            );
          }
          final stepIdx = index ~/ 2;
          final isActive = _currentStep >= stepIdx;
          return Column(
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isActive
                      ? const Color(0xFF52C41A)
                      : Colors.grey[300],
                ),
                child: Center(
                  child: isActive && _currentStep > stepIdx
                      ? const Icon(Icons.check, size: 16, color: Colors.white)
                      : Text(
                          '${stepIdx + 1}',
                          style: TextStyle(
                            color: isActive
                                ? Colors.white
                                : Colors.grey[600],
                            fontSize: 13,
                          ),
                        ),
                ),
              ),
              const SizedBox(height: 4),
              Text(
                steps[stepIdx],
                style: TextStyle(
                  fontSize: 11,
                  color: isActive
                      ? const Color(0xFF52C41A)
                      : Colors.grey[500],
                ),
              ),
            ],
          );
        }),
      ),
    );
  }

  Widget _buildMemberSelector() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.people, color: Color(0xFF52C41A), size: 20),
                    SizedBox(width: 8),
                    Text('为谁咨询？',
                        style: TextStyle(
                            fontSize: 16, fontWeight: FontWeight.w600)),
                  ],
                ),
                const SizedBox(height: 16),
                if (_membersLoading)
                  const Center(
                    child: Padding(
                      padding: EdgeInsets.all(20),
                      child: SizedBox(
                          width: 24,
                          height: 24,
                          child:
                              CircularProgressIndicator(strokeWidth: 2)),
                    ),
                  )
                else
                  Wrap(
                    spacing: 12,
                    runSpacing: 12,
                    children: _familyMembers.map((member) {
                      final isSelf = member['is_self'] == true;
                      final id = isSelf ? null : member['id'] as int?;
                      final isSelected = _selectedMemberId == id &&
                          _selectedMemberName ==
                              (member['relation']?.toString() ?? '本人');
                      final relation =
                          member['relation']?.toString() ?? '本人';

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
                          width: 72,
                          padding: const EdgeInsets.symmetric(vertical: 12),
                          decoration: BoxDecoration(
                            color: isSelected
                                ? const Color(0xFFF0F9EB)
                                : const Color(0xFFF5F5F5),
                            borderRadius: BorderRadius.circular(12),
                            border: Border.all(
                              color: isSelected
                                  ? const Color(0xFF52C41A)
                                  : Colors.transparent,
                              width: 2,
                            ),
                          ),
                          child: Column(
                            children: [
                              Container(
                                width: 36,
                                height: 36,
                                decoration: BoxDecoration(
                                  shape: BoxShape.circle,
                                  color: isSelected
                                      ? const Color(0xFF52C41A)
                                      : const Color(0xFFE8E8E8),
                                ),
                                alignment: Alignment.center,
                                child: Text(
                                  relation.length > 2
                                      ? relation.substring(0, 2)
                                      : relation,
                                  style: TextStyle(
                                    fontSize: 12,
                                    fontWeight: FontWeight.w600,
                                    color: isSelected
                                        ? Colors.white
                                        : const Color(0xFF666666),
                                  ),
                                ),
                              ),
                              const SizedBox(height: 4),
                              Text(
                                relation,
                                style: TextStyle(
                                  fontSize: 11,
                                  color: isSelected
                                      ? const Color(0xFF52C41A)
                                      : const Color(0xFF666666),
                                ),
                                overflow: TextOverflow.ellipsis,
                              ),
                            ],
                          ),
                        ),
                      );
                    }).toList(),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _buildSelfBasicInfoForm(),
          const SizedBox(height: 16),
          if (!_presetsLoading) ...[
            DiseaseTagSelector(
              title: '既往病史',
              presets: _chronicPresets,
              selectedItems: _chronicDiseases,
              onChanged: (items) =>
                  setState(() => _chronicDiseases = items),
              color: const Color(0xFFFA8C16),
            ),
            DiseaseTagSelector(
              title: '过敏史',
              presets: _allergyPresets,
              selectedItems: _allergies,
              onChanged: (items) => setState(() => _allergies = items),
              color: const Color(0xFFEB2F96),
            ),
            DiseaseTagSelector(
              title: '家族遗传病史',
              presets: _geneticPresets,
              selectedItems: _geneticDiseases,
              onChanged: (items) =>
                  setState(() => _geneticDiseases = items),
              color: const Color(0xFF1890FF),
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildBodyPartSelector() {
    return GridView.builder(
      padding: const EdgeInsets.all(16),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 2,
        childAspectRatio: 1.6,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
      ),
      itemCount: _bodyPartSymptoms.keys.length,
      itemBuilder: (context, index) {
        final part = _bodyPartSymptoms.keys.elementAt(index);
        final isSelected = _selectedBodyPart == part;
        final icons = [
          Icons.face,
          Icons.favorite,
          Icons.restaurant,
          Icons.accessibility,
          Icons.brush,
          Icons.self_improvement
        ];
        return GestureDetector(
          onTap: () => setState(() => _selectedBodyPart = part),
          child: Container(
            decoration: BoxDecoration(
              color: isSelected
                  ? const Color(0xFFF0F9EB)
                  : Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isSelected
                    ? const Color(0xFF52C41A)
                    : Colors.grey[200]!,
                width: isSelected ? 2 : 1,
              ),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  icons[index],
                  size: 32,
                  color: isSelected
                      ? const Color(0xFF52C41A)
                      : Colors.grey[600],
                ),
                const SizedBox(height: 8),
                Text(
                  part,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight:
                        isSelected ? FontWeight.w600 : FontWeight.normal,
                    color: isSelected
                        ? const Color(0xFF52C41A)
                        : Colors.grey[800],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }

  Widget _buildSymptomSelector() {
    final symptoms = _bodyPartSymptoms[_selectedBodyPart] ?? [];
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          '$_selectedBodyPart - 请选择相关症状',
          style:
              const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
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
                padding: const EdgeInsets.symmetric(
                    horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: isSelected
                      ? const Color(0xFF52C41A)
                      : Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected
                        ? const Color(0xFF52C41A)
                        : Colors.grey[300]!,
                  ),
                ),
                child: Text(
                  symptom,
                  style: TextStyle(
                    color:
                        isSelected ? Colors.white : Colors.grey[800],
                    fontWeight: isSelected
                        ? FontWeight.w600
                        : FontWeight.normal,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildDurationSelector() {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const Text(
          '症状持续多长时间了？',
          style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: _durationOptions.map((duration) {
            final isSelected = _selectedDuration == duration;
            return GestureDetector(
              onTap: () {
                setState(() {
                  _selectedDuration = duration;
                });
              },
              child: Container(
                padding: const EdgeInsets.symmetric(
                    horizontal: 20, vertical: 10),
                decoration: BoxDecoration(
                  color: isSelected
                      ? const Color(0xFF52C41A)
                      : Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected
                        ? const Color(0xFF52C41A)
                        : Colors.grey[300]!,
                  ),
                ),
                child: Text(
                  duration,
                  style: TextStyle(
                    color: isSelected ? Colors.white : Colors.grey[800],
                    fontWeight: isSelected
                        ? FontWeight.w600
                        : FontWeight.normal,
                  ),
                ),
              ),
            );
          }).toList(),
        ),
      ],
    );
  }

  Widget _buildResultView() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Row(
                  children: [
                    Icon(Icons.medical_information,
                        color: Color(0xFF52C41A)),
                    SizedBox(width: 8),
                    Text('症状分析结果',
                        style: TextStyle(
                            fontSize: 18, fontWeight: FontWeight.bold)),
                  ],
                ),
                const SizedBox(height: 16),
                Text('咨询对象：$_selectedMemberName',
                    style: const TextStyle(fontSize: 15)),
                const SizedBox(height: 8),
                Text('部位：$_selectedBodyPart',
                    style: const TextStyle(fontSize: 15)),
                const SizedBox(height: 8),
                Text('症状：${_selectedSymptoms.join("、")}',
                    style: const TextStyle(fontSize: 15)),
                const SizedBox(height: 8),
                Text('持续时间：${_selectedDuration ?? '未选择'}',
                    style: const TextStyle(fontSize: 15)),
                const Divider(height: 24),
                const Text(
                  '可能原因',
                  style: TextStyle(
                      fontSize: 16, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                const Text(
                  '根据您选择的症状，AI正在进行分析，请稍后查看详细结果。建议您及时就医，以获得准确的诊断和治疗方案。',
                  style: TextStyle(
                      fontSize: 14,
                      height: 1.6,
                      color: Color(0xFF666666)),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFFFFF7E6),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                  color: const Color(0xFFFA8C16).withOpacity(0.3)),
            ),
            child: const Row(
              children: [
                Icon(Icons.warning_amber, color: Color(0xFFFA8C16)),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '以上分析仅供参考，不能替代医生的专业诊断。如症状严重，请立即就医。',
                    style: TextStyle(
                        fontSize: 13,
                        color: Color(0xFF666666),
                        height: 1.4),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: () => Navigator.pushNamed(context, '/ai'),
              icon: const Icon(Icons.smart_toy),
              label: const Text('咨询AI健康顾问'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomButton() {
    return Container(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 12,
        bottom: MediaQuery.of(context).padding.bottom + 12,
      ),
      color: Colors.white,
      child: Row(
        children: [
          if (_currentStep > 0)
            Expanded(
              child: OutlinedButton(
                onPressed: () => setState(() => _currentStep--),
                style: OutlinedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  side: const BorderSide(color: Color(0xFF52C41A)),
                  shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(24)),
                ),
                child: const Text('上一步',
                    style: TextStyle(color: Color(0xFF52C41A))),
              ),
            ),
          if (_currentStep > 0) const SizedBox(width: 12),
          if (_currentStep < 4)
            Expanded(
              child: ElevatedButton(
                onPressed: _canProceed()
                    ? () {
                        if (_currentStep == 0) {
                          if (!_validateSelfInfo()) {
                            return;
                          }
                          _saveHealthProfile();
                        }
                        if (_currentStep == 3 &&
                            _selectedDuration == null) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('请选择症状持续时间'),
                              duration: Duration(seconds: 2),
                            ),
                          );
                          return;
                        }
                        setState(() => _currentStep++);
                      }
                    : null,
                child: Text(_currentStep == 3 ? 'AI智能分析' : '下一步'),
              ),
            ),
        ],
      ),
    );
  }

  bool _canProceed() {
    switch (_currentStep) {
      case 0:
        return true;
      case 1:
        return _selectedBodyPart != null;
      case 2:
        return _selectedSymptoms.isNotEmpty;
      case 3:
        return true;
      default:
        return false;
    }
  }
}
