import 'dart:io';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:flutter/material.dart';
import 'package:fluttertoast/fluttertoast.dart';
import 'package:image_picker/image_picker.dart';
import 'package:provider/provider.dart';
import '../../providers/health_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/health_profile_editor.dart';

const _kPrimaryPink = Color(0xFFEB2F96);
const _kPrimaryPurple = Color(0xFF722ED1);
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

class DrugScreen extends StatefulWidget {
  const DrugScreen({super.key});

  @override
  State<DrugScreen> createState() => _DrugScreenState();
}

class _DrugScreenState extends State<DrugScreen> {
  final ImagePicker _picker = ImagePicker();
  final ApiService _api = ApiService();
  final GlobalKey<HealthProfileEditorState> _profileEditorKey = GlobalKey();

  List<XFile> _selectedImages = [];
  final int _maxImages = 5;
  bool _isRecognizing = false;
  String _progressText = '';

  // 3-step flow: 0=拍照, 1=选择咨询人, 2=AI识别中
  int _uploadStep = 0;

  // Family member selection
  List<Map<String, dynamic>> _familyMembers = [];
  int? _selectedFamilyMemberId;
  bool _membersLoading = true;

  // Health profile fields
  String _selfNickname = '';
  String _selfGender = '';
  String _selfBirthday = '';
  String _selfHeight = '';
  String _selfWeight = '';
  Map<String, String> _selfErrors = {};
  List<String> _chronicPresets = [];
  List<String> _allergyPresets = [];
  List<String> _geneticPresets = [];
  bool _presetsLoading = true;
  List<dynamic> _chronicDiseases = [];
  List<dynamic> _allergies = [];
  List<dynamic> _geneticDiseases = [];

  List<Map<String, dynamic>> _historyList = [];
  bool _isLoadingHistory = true;

  @override
  void initState() {
    super.initState();
    _loadHistory();
    _loadFamilyMembers();
    _loadPresets();
    _loadSelfProfile();
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
              'gender': (m['gender'] ?? '').toString(),
            };
          }).toList();
          if (_familyMembers.isNotEmpty) {
            final selfMember = _familyMembers.firstWhere(
              (m) => m['is_self'] == true,
              orElse: () => _familyMembers.first,
            );
            _selectedFamilyMemberId = selfMember['is_self'] == true ? null : selfMember['id'];
          }
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
        _api.getDiseasePresets('chronic'),
        _api.getDiseasePresets('allergy'),
        _api.getDiseasePresets('genetic'),
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
      final response = await _api.getHealthProfile();
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
      if (_selectedFamilyMemberId != null) {
        await _api.updateMemberHealthProfile(_selectedFamilyMemberId!, data);
      } else {
        await _api.updateHealthProfile(data);
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

  Future<void> _loadHistory() async {
    setState(() => _isLoadingHistory = true);
    try {
      final response = await _api.getDrugIdentifyHistory();
      if (response.statusCode == 200) {
        final data = response.data;
        final rawData = data is Map && data.containsKey('data') ? data['data'] : data;
        final items = rawData is List
            ? rawData
            : (rawData is Map ? (rawData['items'] as List? ?? []) : []);
        setState(() {
          _historyList = items.cast<Map<String, dynamic>>();
        });
      }
    } catch (_) {}
    setState(() => _isLoadingHistory = false);
  }

  Future<void> _pickFromGallery() async {
    // v1.2 硬性：用药参考相册单选，严禁 pickMultiImage
    final XFile? pic = await _picker.pickImage(source: ImageSource.gallery);
    if (pic != null) {
      setState(() {
        _selectedImages
          ..clear()
          ..add(pic);
      });
    }
  }

  Future<void> _pickFromCamera() async {
    if (_selectedImages.length >= _maxImages) {
      _showError('最多只能选择 $_maxImages 张图片');
      return;
    }
    final image = await _picker.pickImage(source: ImageSource.camera);
    if (image != null) {
      setState(() {
        _selectedImages.add(image);
      });
    }
  }

  void _removeImage(int index) {
    setState(() {
      _selectedImages.removeAt(index);
    });
  }

  void _goToSelectMember() {
    if (_selectedImages.isEmpty) return;
    setState(() => _uploadStep = 1);
  }

  Future<void> _confirmAndRecognize() async {
    if (_selectedImages.isEmpty || !mounted) return;

    setState(() {
      _isRecognizing = true;
      _progressText = '正在识别 1/${_selectedImages.length} 张...';
      _uploadStep = 2;
    });

    final provider = Provider.of<HealthProvider>(context, listen: false);
    final filePaths = _selectedImages.map((e) => e.path).toList();

    final result = await provider.recognizeMultipleDrugs(
      filePaths,
      onProgress: (current, total) {
        if (mounted) {
          setState(() {
            _progressText = '正在识别 $current/$total 张...';
          });
        }
      },
    );

    if (!mounted) return;
    setState(() {
      _isRecognizing = false;
      _progressText = '';
      _uploadStep = 0;
    });

    if (result != null) {
      final sessionId = result['session_id']?.toString() ?? '';
      final drugName = result['drug_name']?.toString() ?? '药品识别';
      if (sessionId.isNotEmpty) {
        setState(() => _selectedImages.clear());
        // 相册单选提示（后端 single_select_notice=true 时）
        if (result['single_select_notice'] == true) {
          final msg = (result['notice_message'] as String?)?.isNotEmpty == true
              ? result['notice_message'] as String
              : '已自动选取第一张图片';
          Fluttertoast.showToast(msg: msg);
        }
        Navigator.pushNamed(context, '/drug-chat', arguments: {
          'sessionId': sessionId,
          'drugName': drugName,
          'familyMemberId': _selectedFamilyMemberId,
        });
        _loadHistory();
      } else {
        _showError('识别成功但未获取到会话信息');
      }
    } else {
      _showError('识别失败，请重试');
    }
  }

  void _showError(String msg) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(msg),
        backgroundColor: Colors.red[400],
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
      ),
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
    if (_uploadStep == 1) {
      return _buildMemberSelectionPage();
    }

    return Scaffold(
      appBar: const CustomAppBar(title: '拍照识药'),
      body: Stack(
        children: [
          RefreshIndicator(
            color: _kPrimaryPink,
            onRefresh: _loadHistory,
            child: CustomScrollView(
              slivers: [
                if (_selectedImages.isNotEmpty)
                  SliverToBoxAdapter(child: _buildStepIndicator()),
                SliverToBoxAdapter(child: _buildCameraSection()),
                if (_selectedImages.isNotEmpty)
                  SliverToBoxAdapter(child: _buildSelectedImagesSection()),
                SliverToBoxAdapter(child: _buildHistoryHeader()),
                if (_isLoadingHistory)
                  const SliverFillRemaining(
                    child: Center(child: CircularProgressIndicator(color: _kPrimaryPink)),
                  )
                else if (_historyList.isEmpty)
                  SliverFillRemaining(
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.medication_outlined, size: 60, color: Colors.grey[300]),
                          const SizedBox(height: 12),
                          Text('暂无识别记录', style: TextStyle(color: Colors.grey[500], fontSize: 15)),
                          const SizedBox(height: 6),
                          Text('拍照识别药品后记录将显示在这里', style: TextStyle(color: Colors.grey[400], fontSize: 13)),
                        ],
                      ),
                    ),
                  )
                else
                  SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, index) => _buildHistoryCard(_historyList[index]),
                      childCount: _historyList.length,
                    ),
                  ),
                const SliverToBoxAdapter(child: SizedBox(height: 80)),
              ],
            ),
          ),
          if (_isRecognizing) _buildLoadingOverlay(),
        ],
      ),
    );
  }

  Widget _buildStepIndicator() {
    const steps = ['拍照/选图', '选择咨询人', 'AI识别'];
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
                color: _uploadStep > stepIdx ? _kPrimaryPink : Colors.grey[300],
              ),
            );
          }
          final stepIdx = index ~/ 2;
          final isActive = _uploadStep >= stepIdx;
          final isDone = _uploadStep > stepIdx;
          return GestureDetector(
            onTap: stepIdx < _uploadStep ? () => setState(() => _uploadStep = stepIdx) : null,
            child: Column(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: isActive ? _kPrimaryPink : Colors.grey[300],
                  ),
                  child: Center(
                    child: isDone
                        ? const Icon(Icons.check, size: 16, color: Colors.white)
                        : Text(
                            '${stepIdx + 1}',
                            style: TextStyle(
                              color: isActive ? Colors.white : Colors.grey[600],
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
                    color: isActive ? _kPrimaryPink : Colors.grey[500],
                  ),
                ),
              ],
            ),
          );
        }),
      ),
    );
  }

  Widget _buildMemberSelectionPage() {
    return Scaffold(
      appBar: CustomAppBar(
        title: '选择咨询对象',
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.white),
          onPressed: () => setState(() => _uploadStep = 0),
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
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Row(
                          children: [
                            Icon(Icons.people, color: _kPrimaryPink, size: 20),
                            SizedBox(width: 8),
                            Text(
                              '为谁识别药品？',
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '选择后将为该成员提供个性化用药建议',
                          style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                        ),
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
                                final isSelected = _selectedFamilyMemberId == id;
                                final relation = member['relationship_type']?.toString() ?? '本人';
                                final nickname = member['nickname']?.toString() ?? '';
                                final displayName = nickname.isNotEmpty ? nickname : relation;
                                final tagColor = _getMemberTagColor(relation);

                                return GestureDetector(
                                  onTap: () {
                                    setState(() {
                                      _selectedFamilyMemberId = id;
                                      _selfErrors = {};
                                    });
                                    _profileEditorKey.currentState?.resetExpanded();
                                    if (isSelf || id == null) {
                                      _loadSelfProfile();
                                    } else {
                                      setState(() {
                                        _selfNickname = nickname;
                                        _selfGender = (member['gender'] ?? '').toString();
                                        _selfBirthday = '';
                                        _selfHeight = '';
                                        _selfWeight = '';
                                        _chronicDiseases = [];
                                        _allergies = [];
                                        _geneticDiseases = [];
                                      });
                                    }
                                  },
                                  child: Container(
                                    width: 80,
                                    padding: const EdgeInsets.symmetric(vertical: 14),
                                    decoration: BoxDecoration(
                                      color: isSelected
                                          ? _kPrimaryPink.withOpacity(0.08)
                                          : const Color(0xFFF5F5F5),
                                      borderRadius: BorderRadius.circular(12),
                                      border: Border.all(
                                        color: isSelected ? _kPrimaryPink : Colors.transparent,
                                        width: 2,
                                      ),
                                    ),
                                    child: Column(
                                      children: [
                                        Container(
                                          width: 40,
                                          height: 40,
                                          decoration: BoxDecoration(
                                            shape: BoxShape.circle,
                                            color: isSelected ? tagColor : const Color(0xFFE8E8E8),
                                          ),
                                          alignment: Alignment.center,
                                          child: Text(
                                            relation.length > 2 ? relation.substring(0, 2) : relation,
                                            style: TextStyle(
                                              fontSize: 13,
                                              fontWeight: FontWeight.w600,
                                              color: isSelected ? Colors.white : const Color(0xFF666666),
                                            ),
                                          ),
                                        ),
                                        const SizedBox(height: 6),
                                        Text(
                                          displayName,
                                          style: TextStyle(
                                            fontSize: 12,
                                            color: isSelected ? _kPrimaryPink : const Color(0xFF666666),
                                          ),
                                          overflow: TextOverflow.ellipsis,
                                        ),
                                      ],
                                    ),
                                  ),
                                );
                              }),
                              GestureDetector(
                                onTap: () => Navigator.pushNamed(context, '/family').then((_) => _loadFamilyMembers()),
                                child: Container(
                                  width: 80,
                                  padding: const EdgeInsets.symmetric(vertical: 14),
                                  decoration: BoxDecoration(
                                    color: const Color(0xFFF5F5F5),
                                    borderRadius: BorderRadius.circular(12),
                                    border: Border.all(color: Colors.grey[300]!),
                                  ),
                                  child: Column(
                                    children: [
                                      Container(
                                        width: 40,
                                        height: 40,
                                        decoration: BoxDecoration(
                                          shape: BoxShape.circle,
                                          border: Border.all(color: Colors.grey[400]!, width: 1.5),
                                        ),
                                        child: Icon(Icons.add, color: Colors.grey[500], size: 22),
                                      ),
                                      const SizedBox(height: 6),
                                      Text('添加成员', style: TextStyle(fontSize: 12, color: Colors.grey[500])),
                                    ],
                                  ),
                                ),
                              ),
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
                      memberName: _selectedFamilyMemberId == null ? '本人' : '',
                      errors: _selfErrors.map((k, v) => MapEntry(k, v)),
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
                        });
                      },
                    ),
                  const SizedBox(height: 16),
                  Container(
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: const Color(0xFFFFF0F6),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(color: _kPrimaryPink.withOpacity(0.2)),
                    ),
                    child: Row(
                      children: [
                        const Icon(Icons.info_outline, size: 18, color: _kPrimaryPink),
                        const SizedBox(width: 10),
                        Expanded(
                          child: Text(
                            '已选择 ${_selectedImages.length} 张图片，确认对象后将开始AI识别',
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
                    onPressed: () => setState(() => _uploadStep = 0),
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      side: const BorderSide(color: _kPrimaryPink),
                      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                    ),
                    child: const Text('上一步', style: TextStyle(color: _kPrimaryPink)),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  flex: 2,
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: const LinearGradient(colors: [_kPrimaryPink, _kPrimaryPurple]),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: ElevatedButton.icon(
                      onPressed: () {
                        if (!_validateSelfInfo()) return;
                        _saveHealthProfile();
                        _confirmAndRecognize();
                      },
                      icon: const Icon(Icons.auto_awesome, size: 18),
                      label: const Text('确认并开始识别'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.transparent,
                        shadowColor: Colors.transparent,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                      ),
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

  Widget _buildCameraSection() {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 24),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [
          BoxShadow(color: Colors.black.withOpacity(0.04), blurRadius: 12, offset: const Offset(0, 4)),
        ],
      ),
      child: Column(
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: BoxDecoration(
              gradient: LinearGradient(colors: [_kPrimaryPink.withOpacity(0.15), _kPrimaryPurple.withOpacity(0.15)]),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Icon(Icons.camera_alt, size: 64, color: _kPrimaryPink),
          ),
          const SizedBox(height: 16),
          const Text(
            '拍摄药品包装，AI帮您解读用药信息',
            style: TextStyle(fontSize: 14, color: Color(0xFF666666), height: 1.5),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          // v1.2：单个大按钮 "📷 拍照识别药品"
          SizedBox(
            width: double.infinity,
            height: 56,
            child: Container(
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [_kPrimaryPink, _kPrimaryPurple]),
                borderRadius: BorderRadius.circular(28),
              ),
              child: ElevatedButton(
                onPressed: _isRecognizing ? null : _pickFromCamera,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.transparent,
                  shadowColor: Colors.transparent,
                  foregroundColor: Colors.white,
                  padding: EdgeInsets.zero,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28)),
                ),
                child: const Text(
                  '📷 拍照识别药品',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
              ),
            ),
          ),
          const SizedBox(height: 10),
          // 下方小字链接按钮 "🖼️ 从相册选择（单张）"
          TextButton(
            onPressed: _isRecognizing ? null : _pickFromGallery,
            style: TextButton.styleFrom(
              foregroundColor: _kPrimaryPink,
              minimumSize: const Size(0, 40),
            ),
            child: const Text(
              '🖼️ 从相册选择（单张）',
              style: TextStyle(fontSize: 14),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSelectedImagesSection() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '已选 ${_selectedImages.length}/$_maxImages 张',
                style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF333333)),
              ),
              const Spacer(),
              GestureDetector(
                onTap: () => setState(() => _selectedImages.clear()),
                child: Text('清空', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [for (int i = 0; i < _selectedImages.length; i++) _buildImageThumb(i)],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: Container(
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [_kPrimaryPink, _kPrimaryPurple]),
                borderRadius: BorderRadius.circular(12),
              ),
              child: ElevatedButton.icon(
                onPressed: _goToSelectMember,
                icon: const Icon(Icons.arrow_forward, size: 18),
                label: const Text('下一步：选择咨询人'),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.transparent,
                  shadowColor: Colors.transparent,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildImageThumb(int index) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Image.file(File(_selectedImages[index].path), width: 80, height: 80, fit: BoxFit.cover),
        ),
        Positioned(
          top: -6,
          right: -6,
          child: GestureDetector(
            onTap: () => _removeImage(index),
            child: Container(
              width: 22,
              height: 22,
              decoration: const BoxDecoration(color: Color(0xFFFF4D4F), shape: BoxShape.circle),
              child: const Icon(Icons.close, color: Colors.white, size: 14),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildHistoryHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Row(
        children: [
          const Text('识别记录', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
          const Spacer(),
          if (_historyList.isNotEmpty)
            GestureDetector(
              onTap: _loadHistory,
              child: Row(
                children: [
                  Icon(Icons.refresh, size: 16, color: Colors.grey[500]),
                  const SizedBox(width: 4),
                  Text('刷新', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
                ],
              ),
            ),
          if (_historyList.isNotEmpty) ...[
            const SizedBox(width: 12),
            Text('共${_historyList.length}条', style: TextStyle(fontSize: 13, color: Colors.grey[500])),
          ],
        ],
      ),
    );
  }

  Widget _buildHistoryCard(Map<String, dynamic> item) {
    final drugName = item['drug_name']?.toString() ?? item['title']?.toString() ?? '未知药品';
    // v1.2：优先 first_image_url，回退 original_image_url
    final thumbUrl = item['first_image_url']?.toString().isNotEmpty == true
        ? item['first_image_url']?.toString()
        : (item['original_image_url']?.toString() ??
            item['thumbnail']?.toString() ??
            item['image_url']?.toString());
    // image_status: normal | uploading | failed | legacy
    final imageStatus = item['image_status']?.toString() ?? 'normal';
    final createdAt = item['created_at']?.toString() ?? item['time']?.toString();
    final status = item['status']?.toString();
    final sessionId = item['session_id']?.toString() ?? '';

    final statusMap = {
      'completed': {'label': '已完成', 'color': _kPrimaryGreen},
      'processing': {'label': '处理中', 'color': const Color(0xFF1890FF)},
      'failed': {'label': '失败', 'color': const Color(0xFFFF4D4F)},
    };
    final statusInfo = statusMap[status] ?? {'label': status ?? '未知', 'color': const Color(0xFFFA8C16)};

    return GestureDetector(
      onTap: () {
        if (sessionId.isNotEmpty) {
          Navigator.pushNamed(context, '/drug-chat', arguments: {
            'sessionId': sessionId,
            'drugName': drugName,
            'recordId': item['id'] is int
                ? item['id']
                : int.tryParse(item['id']?.toString() ?? ''),
          });
        }
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          boxShadow: [
            BoxShadow(color: Colors.black.withOpacity(0.03), blurRadius: 8, offset: const Offset(0, 2)),
          ],
        ),
        child: Row(
          children: [
            _buildHistoryThumb(thumbUrl, imageStatus, drugName),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    drugName,
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w500,
                      color: Colors.grey.shade800,
                    ),
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 8),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                        decoration: BoxDecoration(
                          color: (statusInfo['color'] as Color).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(4),
                        ),
                        child: Text(
                          statusInfo['label'] as String,
                          style: TextStyle(
                            fontSize: 11,
                            color: statusInfo['color'] as Color,
                            fontWeight: FontWeight.w500,
                          ),
                        ),
                      ),
                      const Spacer(),
                      Text(
                        _formatTime(createdAt),
                        style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(width: 4),
            const Icon(Icons.chevron_right, color: Colors.grey, size: 22),
          ],
        ),
      ),
    );
  }

  /// v1.2 识别记录缩略图：72×72 圆角 12，支持 4 态
  Widget _buildHistoryThumb(String? url, String status, String drugName) {
    const double size = 72;
    final radius = BorderRadius.circular(12);

    Widget inner;
    switch (status) {
      case 'uploading':
        inner = Container(
          color: const Color(0xFFF5F5F5),
          alignment: Alignment.center,
          child: const SizedBox(
            width: 24,
            height: 24,
            child: CircularProgressIndicator(strokeWidth: 2, color: _kPrimaryPink),
          ),
        );
        break;
      case 'failed':
        inner = Container(
          decoration: BoxDecoration(
            color: const Color(0xFFFAFAFA),
            border: Border.all(color: Colors.grey.shade400, width: 1),
            borderRadius: radius,
          ),
          alignment: Alignment.center,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.warning_amber_rounded, color: Colors.grey.shade500, size: 24),
              const SizedBox(height: 2),
              Text(
                '识别失败',
                style: TextStyle(fontSize: 10, color: Colors.grey.shade600),
              ),
            ],
          ),
        );
        break;
      case 'legacy':
        final firstChar = drugName.isNotEmpty && drugName != '未知药品'
            ? drugName.characters.first
            : '💊';
        inner = Container(
          color: const Color(0xFFEEEEEE),
          alignment: Alignment.center,
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.medication_outlined, color: Colors.grey.shade500, size: 22),
              const SizedBox(height: 2),
              Text(
                firstChar,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Colors.grey.shade700,
                ),
              ),
            ],
          ),
        );
        break;
      case 'normal':
      default:
        if (url != null && url.isNotEmpty) {
          inner = CachedNetworkImage(
            imageUrl: url,
            width: size,
            height: size,
            fit: BoxFit.cover,
            placeholder: (_, __) => Container(
              color: const Color(0xFFF5F5F5),
              alignment: Alignment.center,
              child: const SizedBox(
                width: 20,
                height: 20,
                child: CircularProgressIndicator(strokeWidth: 2),
              ),
            ),
            errorWidget: (_, __, ___) => _legacyPlaceholder(drugName),
          );
        } else {
          inner = _legacyPlaceholder(drugName);
        }
    }

    return ClipRRect(
      borderRadius: radius,
      child: SizedBox(width: size, height: size, child: inner),
    );
  }

  Widget _legacyPlaceholder(String drugName) {
    final firstChar = drugName.isNotEmpty && drugName != '未知药品'
        ? drugName.characters.first
        : '💊';
    return Container(
      color: const Color(0xFFEEEEEE),
      alignment: Alignment.center,
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.medication_outlined, color: Colors.grey.shade500, size: 22),
          const SizedBox(height: 2),
          Text(
            firstChar,
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: Colors.grey.shade700,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingOverlay() {
    return Container(
      color: Colors.black.withOpacity(0.4),
      child: Center(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 32, vertical: 24),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const CircularProgressIndicator(color: _kPrimaryPink),
              const SizedBox(height: 16),
              const Text('正在识别药品...', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600)),
              const SizedBox(height: 6),
              Text(
                _progressText.isNotEmpty ? _progressText : 'AI正在分析图片，请稍候',
                style: TextStyle(fontSize: 13, color: Colors.grey[500]),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
