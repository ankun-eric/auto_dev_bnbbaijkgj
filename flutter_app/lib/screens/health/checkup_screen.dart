import 'dart:io';
import 'dart:math' as math;
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:image_picker/image_picker.dart';
import 'package:file_picker/file_picker.dart';
import '../../providers/health_provider.dart';
import '../../models/checkup_report.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/empty_widget.dart';
import '../../widgets/loading_widget.dart';
import '../../widgets/health_profile_editor.dart';
import 'report_detail_screen.dart';
import 'report_compare_screen.dart';

const _kPrimaryGreen = Color(0xFF52C41A);

const _kRelationColors = <String, Color>{
  '本人': Color(0xFF1677FF),
  '爸爸': Color(0xFFFA8C16),
  '父亲': Color(0xFFFA8C16),
  '妈妈': Color(0xFFEB2F96),
  '母亲': Color(0xFFEB2F96),
  '配偶': Color(0xFF722ED1),
  '丈夫': Color(0xFF722ED1),
  '妻子': Color(0xFF722ED1),
  '子女': Color(0xFF13C2C2),
  '儿子': Color(0xFF13C2C2),
  '女儿': Color(0xFF13C2C2),
};

Color _scoreColor(double score) {
  if (score >= 90) return const Color(0xFF1B8C3D);
  if (score >= 75) return const Color(0xFF4CAF50);
  if (score >= 60) return const Color(0xFFFFC107);
  if (score >= 40) return const Color(0xFFFF9800);
  return const Color(0xFFF44336);
}

class CheckupScreen extends StatefulWidget {
  const CheckupScreen({super.key});

  @override
  State<CheckupScreen> createState() => _CheckupScreenState();
}

class _CheckupScreenState extends State<CheckupScreen> {
  final ImagePicker _picker = ImagePicker();
  final ApiService _apiService = ApiService();
  final GlobalKey<HealthProfileEditorState> _profileEditorKey = GlobalKey();

  List<XFile> _selectedImages = [];
  final int _maxImages = 5;
  bool _isRecognizing = false;
  String _progressText = '';

  // Upload step flow: 0=upload, 1=select member, 2=AI analyzing (navigated away)
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

  // Selection mode
  bool _selectionMode = false;
  final Set<int> _selectedReportIds = {};

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final provider = Provider.of<HealthProvider>(context, listen: false);
      provider.loadReportList();
      provider.loadAlerts();
      _loadFamilyMembers();
      _loadPresets();
      _loadSelfProfile();
    });
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
        await _apiService.updateMemberHealthProfile(_selectedFamilyMemberId!, data);
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

  Future<void> _refresh() async {
    final provider = Provider.of<HealthProvider>(context, listen: false);
    await Future.wait([
      provider.loadReportList(),
      provider.loadAlerts(),
    ]);
  }

  Future<void> _pickFromGallery() async {
    final images = await _picker.pickMultiImage();
    if (images.isNotEmpty) {
      setState(() {
        final remaining = _maxImages - _selectedImages.length;
        if (remaining > 0) {
          _selectedImages.addAll(images.take(remaining));
        }
      });
    }
  }

  Future<void> _pickFromCamera() async {
    if (_selectedImages.length >= _maxImages) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('最多只能选择 $_maxImages 张图片')),
      );
      return;
    }
    final image = await _picker.pickImage(source: ImageSource.camera);
    if (image != null) {
      setState(() {
        _selectedImages.add(image);
      });
    }
  }

  Future<void> _pickPdf() async {
    final result = await FilePicker.platform.pickFiles(
      type: FileType.custom,
      allowedExtensions: ['pdf'],
    );
    if (result != null && result.files.single.path != null) {
      _handleSingleUpload(result.files.single.path!, fileType: 'pdf');
    }
  }

  void _removeImage(int index) {
    setState(() {
      _selectedImages.removeAt(index);
    });
  }

  Future<void> _handleSingleUpload(String filePath, {String fileType = 'image'}) async {
    if (!mounted) return;
    final provider = Provider.of<HealthProvider>(context, listen: false);
    final report = await provider.uploadAndAnalyzeReport(filePath, fileType: fileType);
    if (report != null && mounted) {
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ReportDetailScreen(reportId: report.id),
        ),
      );
    } else if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('上传或分析失败，请重试')),
      );
    }
  }

  void _startRecognize() {
    if (_selectedImages.isEmpty) return;
    setState(() => _uploadStep = 1);
  }

  Future<void> _confirmAndUpload() async {
    if (_selectedImages.isEmpty) return;
    if (!mounted) return;

    setState(() {
      _isRecognizing = true;
      _progressText = '正在上传 1/${_selectedImages.length} 张...';
      _uploadStep = 2;
    });

    final provider = Provider.of<HealthProvider>(context, listen: false);
    final filePaths = _selectedImages.map((e) => e.path).toList();

    final report = await provider.uploadAndAnalyzeMultipleReports(
      filePaths,
      familyMemberId: _selectedFamilyMemberId,
      onProgress: (current, total) {
        if (mounted) {
          setState(() {
            _progressText = '正在上传 $current/$total 张...';
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

    if (report != null) {
      setState(() {
        _selectedImages.clear();
      });
      Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => ReportDetailScreen(reportId: report.id),
        ),
      );
    } else {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('上传或分析失败，请重试')),
      );
    }
  }

  void _navigateToDetail(int reportId) {
    if (_selectionMode) {
      _toggleSelection(reportId);
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReportDetailScreen(reportId: reportId),
      ),
    );
  }

  void _enterSelectionMode(int reportId) {
    setState(() {
      _selectionMode = true;
      _selectedReportIds.clear();
      _selectedReportIds.add(reportId);
    });
  }

  void _toggleSelection(int reportId) {
    setState(() {
      if (_selectedReportIds.contains(reportId)) {
        _selectedReportIds.remove(reportId);
        if (_selectedReportIds.isEmpty) {
          _selectionMode = false;
        }
      } else {
        if (_selectedReportIds.length < 2) {
          _selectedReportIds.add(reportId);
        } else {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('最多选择两份报告进行对比')),
          );
        }
      }
    });
  }

  void _exitSelectionMode() {
    setState(() {
      _selectionMode = false;
      _selectedReportIds.clear();
    });
  }

  void _navigateToCompare() {
    if (_selectedReportIds.length != 2) return;
    final ids = _selectedReportIds.toList();
    _exitSelectionMode();
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ReportCompareScreen(
          reportId1: ids[0],
          reportId2: ids[1],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    if (_uploadStep == 1) {
      return _buildMemberSelectionPage();
    }

    return Scaffold(
      appBar: CustomAppBar(
        title: _selectionMode ? '选择报告对比' : '体检报告',
        actions: _selectionMode
            ? [
                TextButton(
                  onPressed: _exitSelectionMode,
                  child: const Text('取消', style: TextStyle(color: Colors.white, fontSize: 15)),
                ),
              ]
            : null,
      ),
      body: Consumer<HealthProvider>(
        builder: (context, provider, child) {
          if (provider.isUploading || _isRecognizing) {
            return LoadingWidget(
              message: _isRecognizing && _progressText.isNotEmpty
                  ? _progressText
                  : '正在上传并分析报告...',
            );
          }

          return RefreshIndicator(
            onRefresh: _refresh,
            color: _kPrimaryGreen,
            child: CustomScrollView(
              slivers: [
                if (_selectedImages.isNotEmpty)
                  SliverToBoxAdapter(child: _buildUploadStepIndicator()),
                if (provider.unreadAlertCount > 0)
                  SliverToBoxAdapter(child: _buildAlertBanner(provider)),
                SliverToBoxAdapter(child: _buildUploadSection()),
                if (_selectedImages.isNotEmpty)
                  SliverToBoxAdapter(child: _buildSelectedImagesSection()),
                SliverToBoxAdapter(child: _buildHistoryHeader(provider)),
                if (provider.isLoading)
                  const SliverFillRemaining(
                    child: LoadingWidget(message: '加载中...'),
                  )
                else if (provider.reportList.isEmpty)
                  const SliverFillRemaining(
                    child: EmptyWidget(message: '暂无体检报告', icon: Icons.assignment_outlined),
                  )
                else
                  SliverList(
                    delegate: SliverChildBuilderDelegate(
                      (context, index) => _buildReportItem(provider.reportList[index]),
                      childCount: provider.reportList.length,
                    ),
                  ),
                const SliverToBoxAdapter(child: SizedBox(height: 80)),
              ],
            ),
          );
        },
      ),
      bottomSheet: _selectionMode && _selectedReportIds.length == 2
          ? _buildCompareBottomBar()
          : null,
    );
  }

  Widget _buildUploadStepIndicator() {
    const steps = ['上传报告', '选择对象', 'AI 解读'];
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
                color: _uploadStep > stepIdx
                    ? _kPrimaryGreen
                    : Colors.grey[300],
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
                    color: isActive ? _kPrimaryGreen : Colors.grey[300],
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
                    color: isActive ? _kPrimaryGreen : Colors.grey[500],
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
          _buildUploadStepIndicator(),
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
                            Icon(Icons.people, color: _kPrimaryGreen, size: 20),
                            SizedBox(width: 8),
                            Text(
                              '这份报告属于谁？',
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                            ),
                          ],
                        ),
                        const SizedBox(height: 6),
                        Text(
                          '选择后将为该成员生成专属健康分析',
                          style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                        ),
                        const SizedBox(height: 16),
                        if (_membersLoading)
                          const Center(
                            child: Padding(
                              padding: EdgeInsets.all(20),
                              child: SizedBox(
                                width: 24,
                                height: 24,
                                child: CircularProgressIndicator(strokeWidth: 2),
                              ),
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
                                          ? _kPrimaryGreen.withOpacity(0.08)
                                          : const Color(0xFFF5F5F5),
                                      borderRadius: BorderRadius.circular(12),
                                      border: Border.all(
                                        color: isSelected ? _kPrimaryGreen : Colors.transparent,
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
                                            color: isSelected ? _kPrimaryGreen : const Color(0xFF666666),
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
                                    border: Border.all(color: Colors.grey[300]!, style: BorderStyle.solid),
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
                                      Text(
                                        '添加成员',
                                        style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                                      ),
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
                            '已选择 ${_selectedImages.length} 张图片，确认对象后将开始上传识别',
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
                      _confirmAndUpload();
                    },
                    icon: const Icon(Icons.auto_awesome, size: 18),
                    label: const Text('确认并开始识别'),
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

  Widget _buildCompareBottomBar() {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.08), blurRadius: 8, offset: const Offset(0, -2))],
      ),
      child: SafeArea(
        child: SizedBox(
          width: double.infinity,
          child: ElevatedButton.icon(
            onPressed: _navigateToCompare,
            icon: const Icon(Icons.compare_arrows, size: 20),
            label: const Text('对比分析'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF1890FF),
              foregroundColor: Colors.white,
              padding: const EdgeInsets.symmetric(vertical: 14),
              shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
              elevation: 0,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildAlertBanner(HealthProvider provider) {
    return GestureDetector(
      onTap: () => _showAlertsDialog(provider),
      child: Container(
        margin: const EdgeInsets.fromLTRB(16, 12, 16, 0),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          gradient: const LinearGradient(
            colors: [Color(0xFFFFF7E6), Color(0xFFFFECD1)],
          ),
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFFFD591)),
        ),
        child: Row(
          children: [
            const Icon(Icons.warning_amber_rounded, color: Color(0xFFFA8C16), size: 22),
            const SizedBox(width: 10),
            Expanded(
              child: Text(
                '您有 ${provider.unreadAlertCount} 条健康预警未读',
                style: const TextStyle(
                  fontSize: 14,
                  color: Color(0xFFD46B08),
                  fontWeight: FontWeight.w500,
                ),
              ),
            ),
            const Icon(Icons.chevron_right, color: Color(0xFFFA8C16), size: 20),
          ],
        ),
      ),
    );
  }

  void _showAlertsDialog(HealthProvider provider) {
    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => DraggableScrollableSheet(
        initialChildSize: 0.6,
        maxChildSize: 0.85,
        minChildSize: 0.4,
        expand: false,
        builder: (ctx, scrollController) => Column(
          children: [
            const SizedBox(height: 12),
            Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: Colors.grey[300],
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            const Padding(
              padding: EdgeInsets.all(16),
              child: Text('健康预警', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            ),
            Expanded(
              child: ListView.builder(
                controller: scrollController,
                padding: const EdgeInsets.symmetric(horizontal: 16),
                itemCount: provider.alerts.length,
                itemBuilder: (ctx, index) {
                  final alert = provider.alerts[index];
                  return Container(
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: alert.isRead ? Colors.grey[50] : const Color(0xFFFFF7E6),
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: alert.isRead ? Colors.grey[200]! : const Color(0xFFFFD591),
                      ),
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Icon(
                              Icons.circle,
                              size: 8,
                              color: alert.isRead ? Colors.grey : const Color(0xFFFA8C16),
                            ),
                            const SizedBox(width: 8),
                            Expanded(
                              child: Text(
                                alert.indicatorName,
                                style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600),
                              ),
                            ),
                            Text(
                              alert.createdAt.length >= 10
                                  ? alert.createdAt.substring(0, 10)
                                  : alert.createdAt,
                              style: TextStyle(fontSize: 12, color: Colors.grey[500]),
                            ),
                          ],
                        ),
                        const SizedBox(height: 8),
                        Text(
                          alert.alertMessage,
                          style: TextStyle(fontSize: 14, color: Colors.grey[700], height: 1.4),
                        ),
                        if (!alert.isRead) ...[
                          const SizedBox(height: 8),
                          Align(
                            alignment: Alignment.centerRight,
                            child: GestureDetector(
                              onTap: () => provider.markAlertRead(alert.id),
                              child: const Text(
                                '标为已读',
                                style: TextStyle(
                                  fontSize: 13,
                                  color: _kPrimaryGreen,
                                  fontWeight: FontWeight.w500,
                                ),
                              ),
                            ),
                          ),
                        ],
                      ],
                    ),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildUploadSection() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            '上传体检报告',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold, color: Color(0xFF333333)),
          ),
          const SizedBox(height: 4),
          Text(
            'AI智能解读，助您了解健康状况（最多可选 $_maxImages 张）',
            style: TextStyle(fontSize: 13, color: Colors.grey[500]),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Expanded(child: _buildUploadCard(
                icon: Icons.photo_library_outlined,
                label: '从相册选择',
                subtitle: '支持多选',
                color: _kPrimaryGreen,
                onTap: _pickFromGallery,
              )),
              const SizedBox(width: 10),
              Expanded(child: _buildUploadCard(
                icon: Icons.camera_alt_outlined,
                label: '拍照上传',
                subtitle: '实时拍摄',
                color: const Color(0xFF1890FF),
                onTap: _pickFromCamera,
              )),
              const SizedBox(width: 10),
              Expanded(child: _buildUploadCard(
                icon: Icons.picture_as_pdf_outlined,
                label: 'PDF文件',
                subtitle: '选取文件',
                color: const Color(0xFFFA541C),
                onTap: _pickPdf,
              )),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildUploadCard({
    required IconData icon,
    required String label,
    required String subtitle,
    required Color color,
    required VoidCallback onTap,
  }) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 18, horizontal: 8),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: color.withOpacity(0.2)),
          boxShadow: [
            BoxShadow(
              color: color.withOpacity(0.06),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Column(
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: BoxDecoration(
                color: color.withOpacity(0.1),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Icon(icon, color: color, size: 24),
            ),
            const SizedBox(height: 10),
            Text(
              label,
              style: TextStyle(
                fontSize: 13,
                fontWeight: FontWeight.w600,
                color: Colors.grey[800],
              ),
            ),
            const SizedBox(height: 2),
            Text(
              subtitle,
              style: TextStyle(fontSize: 11, color: Colors.grey[400]),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSelectedImagesSection() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                '已选 ${_selectedImages.length}/$_maxImages 张',
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  color: Color(0xFF333333),
                ),
              ),
              const Spacer(),
              GestureDetector(
                onTap: () => setState(() => _selectedImages.clear()),
                child: Text(
                  '清空',
                  style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 10,
            runSpacing: 10,
            children: [
              for (int i = 0; i < _selectedImages.length; i++)
                _buildImageThumb(i),
            ],
          ),
          const SizedBox(height: 14),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton.icon(
              onPressed: _startRecognize,
              icon: const Icon(Icons.auto_awesome, size: 18),
              label: const Text('开始识别'),
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
    );
  }

  Widget _buildImageThumb(int index) {
    return Stack(
      clipBehavior: Clip.none,
      children: [
        ClipRRect(
          borderRadius: BorderRadius.circular(10),
          child: Image.file(
            File(_selectedImages[index].path),
            width: 80,
            height: 80,
            fit: BoxFit.cover,
          ),
        ),
        Positioned(
          top: -6,
          right: -6,
          child: GestureDetector(
            onTap: () => _removeImage(index),
            child: Container(
              width: 22,
              height: 22,
              decoration: const BoxDecoration(
                color: Color(0xFFFF4D4F),
                shape: BoxShape.circle,
              ),
              child: const Icon(Icons.close, color: Colors.white, size: 14),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildHistoryHeader(HealthProvider provider) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 8),
      child: Row(
        children: [
          const Text(
            '历史报告',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold),
          ),
          const Spacer(),
          if (!_selectionMode && provider.reportList.length >= 2)
            GestureDetector(
              onTap: () {
                setState(() {
                  _selectionMode = true;
                  _selectedReportIds.clear();
                });
              },
              child: const Text(
                '对比报告',
                style: TextStyle(fontSize: 13, color: Color(0xFF1890FF), fontWeight: FontWeight.w500),
              ),
            ),
          if (!_selectionMode) ...[
            const SizedBox(width: 12),
            Text(
              '共${provider.reportList.length}份',
              style: TextStyle(fontSize: 13, color: Colors.grey[500]),
            ),
          ],
          if (_selectionMode)
            Text(
              '已选 ${_selectedReportIds.length}/2',
              style: const TextStyle(fontSize: 13, color: Color(0xFF1890FF), fontWeight: FontWeight.w500),
            ),
        ],
      ),
    );
  }

  static Color _getMemberTagColor(String? relation) {
    if (relation == null || relation.isEmpty) return const Color(0xFF1677FF);
    final color = _kRelationColors[relation];
    if (color != null) return color;
    if (relation.contains('父') || relation.contains('爸')) return const Color(0xFFFA8C16);
    if (relation.contains('母') || relation.contains('妈')) return const Color(0xFFEB2F96);
    if (relation.contains('配偶') || relation.contains('丈夫') || relation.contains('妻')) return const Color(0xFF722ED1);
    if (relation.contains('子') || relation.contains('女儿') || relation.contains('儿子')) return const Color(0xFF13C2C2);
    return const Color(0xFF8C8C8C);
  }

  Widget _buildFamilyMemberTag(CheckupReport report) {
    final fm = report.familyMember;
    String label;
    String? relation;

    if (fm != null) {
      final nickname = (fm['nickname'] ?? '').toString();
      relation = (fm['relationship_type'] ?? fm['relation_type_name'] ?? '').toString();
      label = nickname.isNotEmpty ? nickname : (relation.isNotEmpty ? relation : '本人');
    } else {
      label = '本人';
      relation = '本人';
    }

    final color = _getMemberTagColor(relation);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: color.withOpacity(0.1),
        borderRadius: BorderRadius.circular(4),
      ),
      child: Text(
        label,
        style: TextStyle(
          fontSize: 11,
          color: color,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _buildReportItem(CheckupReport report) {
    final statusMap = {
      'pending': {'label': '待分析', 'color': const Color(0xFFFA8C16)},
      'analyzing': {'label': '分析中', 'color': const Color(0xFF1890FF)},
      'completed': {'label': '已完成', 'color': _kPrimaryGreen},
      'failed': {'label': '分析失败', 'color': const Color(0xFFFF4D4F)},
    };
    final statusInfo = statusMap[report.status] ?? statusMap['pending']!;
    final isSelected = _selectedReportIds.contains(report.id);

    return GestureDetector(
      onTap: () => _navigateToDetail(report.id),
      onLongPress: () {
        if (!_selectionMode) {
          _enterSelectionMode(report.id);
        }
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 5),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFFE6F7FF) : Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: isSelected ? Border.all(color: const Color(0xFF1890FF), width: 1.5) : null,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.03),
              blurRadius: 8,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        child: Row(
          children: [
            if (_selectionMode)
              Padding(
                padding: const EdgeInsets.only(right: 12),
                child: Icon(
                  isSelected ? Icons.check_circle : Icons.radio_button_unchecked,
                  color: isSelected ? const Color(0xFF1890FF) : Colors.grey[400],
                  size: 24,
                ),
              ),
            _buildReportLeadingWidget(report),
            const SizedBox(width: 14),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          report.reportDate != null
                              ? '体检报告 ${report.reportDate}'
                              : '体检报告',
                          style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500),
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                        ),
                      ),
                      const SizedBox(width: 8),
                      _buildFamilyMemberTag(report),
                    ],
                  ),
                  const SizedBox(height: 6),
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
                      if (report.abnormalCount > 0) ...[
                        const SizedBox(width: 8),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                          decoration: BoxDecoration(
                            color: const Color(0xFFFF4D4F).withOpacity(0.1),
                            borderRadius: BorderRadius.circular(4),
                          ),
                          child: Text(
                            '${report.abnormalCount}项异常',
                            style: const TextStyle(
                              fontSize: 11,
                              color: Color(0xFFFF4D4F),
                              fontWeight: FontWeight.w500,
                            ),
                          ),
                        ),
                      ],
                      const Spacer(),
                      Text(
                        report.createdAt.length >= 10
                            ? report.createdAt.substring(0, 10)
                            : report.createdAt,
                        style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            if (!_selectionMode) ...[
              const SizedBox(width: 8),
              const Icon(Icons.chevron_right, color: Colors.grey, size: 22),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildReportLeadingWidget(CheckupReport report) {
    if (report.healthScore != null && report.healthScore! > 0) {
      final score = report.healthScore!;
      final color = _scoreColor(score);
      return SizedBox(
        width: 50,
        height: 50,
        child: CustomPaint(
          painter: _MiniScoreRingPainter(score: score, color: color),
          child: Center(
            child: Text(
              score.toInt().toString(),
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.bold,
                color: color,
              ),
            ),
          ),
        ),
      );
    }

    return Container(
      width: 50,
      height: 50,
      decoration: BoxDecoration(
        color: _kPrimaryGreen.withOpacity(0.1),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Icon(
        report.fileType == 'pdf' ? Icons.picture_as_pdf : Icons.description,
        color: _kPrimaryGreen,
        size: 26,
      ),
    );
  }
}

class _MiniScoreRingPainter extends CustomPainter {
  final double score;
  final Color color;

  _MiniScoreRingPainter({required this.score, required this.color});

  @override
  void paint(Canvas canvas, Size size) {
    final center = Offset(size.width / 2, size.height / 2);
    final radius = math.min(size.width, size.height) / 2 - 4;

    final bgPaint = Paint()
      ..color = Colors.grey[200]!
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    const startAngle = -math.pi / 2;
    const fullSweep = 2 * math.pi;

    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      fullSweep,
      false,
      bgPaint,
    );

    final scorePaint = Paint()
      ..color = color
      ..style = PaintingStyle.stroke
      ..strokeWidth = 5
      ..strokeCap = StrokeCap.round;

    final scoreSweep = fullSweep * (score / 100).clamp(0.0, 1.0);
    canvas.drawArc(
      Rect.fromCircle(center: center, radius: radius),
      startAngle,
      scoreSweep,
      false,
      scorePaint,
    );
  }

  @override
  bool shouldRepaint(covariant _MiniScoreRingPainter oldDelegate) {
    return oldDelegate.score != score || oldDelegate.color != color;
  }
}
