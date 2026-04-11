import 'package:flutter/material.dart';
import '../../services/api_service.dart';
import '../../widgets/disease_tag_selector.dart';

class HealthGuideScreen extends StatefulWidget {
  final int? memberId;
  const HealthGuideScreen({super.key, this.memberId});

  @override
  State<HealthGuideScreen> createState() => _HealthGuideScreenState();
}

class _HealthGuideScreenState extends State<HealthGuideScreen> {
  final ApiService _apiService = ApiService();
  final PageController _pageController = PageController();
  int _currentStep = 0;

  // Step 0 - Basic info
  final TextEditingController _heightController = TextEditingController();
  final TextEditingController _weightController = TextEditingController();
  String? _bloodType;

  // Steps 1/2/3 - Disease tags
  List<String> _chronicPresets = [];
  List<String> _allergyPresets = [];
  List<String> _geneticPresets = [];
  bool _presetsLoading = true;

  List<dynamic> _chronicDiseases = [];
  List<dynamic> _allergies = [];
  List<dynamic> _geneticDiseases = [];

  bool _saving = false;

  static const _steps = ['基本信息', '慢性病史', '过敏史', '遗传病史'];
  static const _bloodTypes = ['A', 'B', 'AB', 'O', 'Rh+', 'Rh-', '不清楚'];

  @override
  void initState() {
    super.initState();
    _loadPresets();
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
            .map((e) => e is Map ? (e['name'] ?? '').toString() : e.toString())
            .toList();
      }
    }
    return [];
  }

  void _nextStep() {
    if (_currentStep < 3) {
      setState(() => _currentStep++);
      _pageController.animateToPage(
        _currentStep,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    } else {
      _finish();
    }
  }

  void _prevStep() {
    if (_currentStep > 0) {
      setState(() => _currentStep--);
      _pageController.animateToPage(
        _currentStep,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeInOut,
      );
    }
  }

  Future<void> _finish() async {
    setState(() => _saving = true);
    final data = <String, dynamic>{
      'chronic_diseases': _chronicDiseases,
      'allergies': _allergies,
      'genetic_diseases': _geneticDiseases,
    };

    final height = double.tryParse(_heightController.text.trim());
    final weight = double.tryParse(_weightController.text.trim());
    if (height != null) data['height'] = height;
    if (weight != null) data['weight'] = weight;
    if (_bloodType != null && _bloodType != '不清楚') {
      data['blood_type'] = _bloodType;
    }

    try {
      if (widget.memberId != null) {
        await _apiService.updateMemberHealthProfile(widget.memberId!, data);
      } else {
        await _apiService.updateHealthProfile(data);
      }
      await _apiService.postGuideStatus();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('健康档案已保存'),
            backgroundColor: Color(0xFF52C41A),
            duration: Duration(seconds: 1),
          ),
        );
        Navigator.pushNamedAndRemoveUntil(context, '/main', (route) => false);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('保存失败，请重试'), backgroundColor: Colors.red),
        );
      }
    }
    if (mounted) setState(() => _saving = false);
  }

  @override
  void dispose() {
    _pageController.dispose();
    _heightController.dispose();
    _weightController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('健康引导'),
        backgroundColor: const Color(0xFF52C41A),
        leading: _currentStep > 0
            ? IconButton(
                icon: const Icon(Icons.arrow_back_ios, size: 20),
                onPressed: _prevStep,
              )
            : null,
        actions: [
          TextButton(
            onPressed: () => Navigator.pushNamedAndRemoveUntil(
                context, '/main', (route) => false),
            child:
                const Text('跳过', style: TextStyle(color: Colors.white70)),
          ),
        ],
      ),
      body: Column(
        children: [
          _buildStepIndicator(),
          Expanded(
            child: PageView(
              controller: _pageController,
              physics: const NeverScrollableScrollPhysics(),
              children: [
                _buildBasicInfoStep(),
                _buildChronicStep(),
                _buildAllergyStep(),
                _buildGeneticStep(),
              ],
            ),
          ),
          _buildBottomButton(),
        ],
      ),
    );
  }

  Widget _buildStepIndicator() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
      color: Colors.white,
      child: Row(
        children: List.generate(_steps.length * 2 - 1, (index) {
          if (index.isOdd) {
            final stepIdx = index ~/ 2;
            return Expanded(
              child: Container(
                height: 2,
                color: _currentStep > stepIdx
                    ? const Color(0xFF52C41A)
                    : const Color(0xFFE8E8E8),
              ),
            );
          }
          final stepIdx = index ~/ 2;
          final isActive = _currentStep >= stepIdx;
          final isDone = _currentStep > stepIdx;
          return Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: isActive
                      ? const Color(0xFF52C41A)
                      : const Color(0xFFE8E8E8),
                ),
                alignment: Alignment.center,
                child: isDone
                    ? const Icon(Icons.check, size: 16, color: Colors.white)
                    : Text(
                        '${stepIdx + 1}',
                        style: TextStyle(
                          fontSize: 13,
                          color:
                              isActive ? Colors.white : const Color(0xFF999999),
                          fontWeight: FontWeight.w600,
                        ),
                      ),
              ),
              const SizedBox(height: 4),
              Text(
                _steps[stepIdx],
                style: TextStyle(
                  fontSize: 11,
                  color: isActive
                      ? const Color(0xFF52C41A)
                      : const Color(0xFF999999),
                ),
              ),
            ],
          );
        }),
      ),
    );
  }

  Widget _buildBasicInfoStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text('请填写基本健康信息',
                    style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF333333))),
                const SizedBox(height: 20),
                _buildTextField('身高 (cm)', _heightController,
                    keyboardType: TextInputType.number, hint: '请输入身高'),
                const SizedBox(height: 16),
                _buildTextField('体重 (kg)', _weightController,
                    keyboardType: TextInputType.number, hint: '请输入体重'),
                const SizedBox(height: 16),
                const Text('血型',
                    style: TextStyle(
                        fontSize: 14,
                        fontWeight: FontWeight.w500,
                        color: Color(0xFF333333))),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: _bloodTypes.map((type) {
                    final selected = _bloodType == type;
                    return ChoiceChip(
                      label: Text(type),
                      selected: selected,
                      onSelected: (_) => setState(() => _bloodType = type),
                      selectedColor:
                          const Color(0xFF52C41A).withOpacity(0.15),
                      labelStyle: TextStyle(
                        color: selected
                            ? const Color(0xFF52C41A)
                            : const Color(0xFF666666),
                        fontWeight:
                            selected ? FontWeight.w600 : FontWeight.normal,
                      ),
                      side: BorderSide(
                        color: selected
                            ? const Color(0xFF52C41A)
                            : const Color(0xFFE8E8E8),
                      ),
                      shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(20)),
                    );
                  }).toList(),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTextField(String label, TextEditingController controller,
      {TextInputType? keyboardType, String? hint}) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: const TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w500,
                color: Color(0xFF333333))),
        const SizedBox(height: 8),
        TextField(
          controller: controller,
          keyboardType: keyboardType,
          decoration: InputDecoration(
            hintText: hint,
            hintStyle:
                const TextStyle(fontSize: 14, color: Color(0xFFBFBFBF)),
            contentPadding:
                const EdgeInsets.symmetric(horizontal: 12, vertical: 12),
            border: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: BorderSide(color: Colors.grey[300]!),
            ),
            focusedBorder: OutlineInputBorder(
              borderRadius: BorderRadius.circular(8),
              borderSide: const BorderSide(color: Color(0xFF52C41A)),
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildChronicStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: _presetsLoading
          ? const Center(
              child: Padding(
                  padding: EdgeInsets.all(40),
                  child: CircularProgressIndicator()))
          : DiseaseTagSelector(
              title: '您是否有以下慢性疾病？',
              presets: _chronicPresets,
              selectedItems: _chronicDiseases,
              onChanged: (items) => setState(() => _chronicDiseases = items),
              color: const Color(0xFFFA8C16),
            ),
    );
  }

  Widget _buildAllergyStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: _presetsLoading
          ? const Center(
              child: Padding(
                  padding: EdgeInsets.all(40),
                  child: CircularProgressIndicator()))
          : DiseaseTagSelector(
              title: '您是否有以下过敏史？',
              presets: _allergyPresets,
              selectedItems: _allergies,
              onChanged: (items) => setState(() => _allergies = items),
              color: const Color(0xFFEB2F96),
            ),
    );
  }

  Widget _buildGeneticStep() {
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: _presetsLoading
          ? const Center(
              child: Padding(
                  padding: EdgeInsets.all(40),
                  child: CircularProgressIndicator()))
          : DiseaseTagSelector(
              title: '您的家族是否有以下遗传病史？',
              presets: _geneticPresets,
              selectedItems: _geneticDiseases,
              onChanged: (items) =>
                  setState(() => _geneticDiseases = items),
              color: const Color(0xFF1890FF),
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
          if (_currentStep > 0) ...[
            Expanded(
              child: OutlinedButton(
                onPressed: _prevStep,
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
            const SizedBox(width: 12),
          ],
          Expanded(
            child: ElevatedButton(
              onPressed: _saving ? null : _nextStep,
              child: _saving
                  ? const SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white),
                    )
                  : Text(_currentStep == 3 ? '完成' : '下一步'),
            ),
          ),
        ],
      ),
    );
  }
}
