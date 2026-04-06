import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class SymptomScreen extends StatefulWidget {
  const SymptomScreen({super.key});

  @override
  State<SymptomScreen> createState() => _SymptomScreenState();
}

class _SymptomScreenState extends State<SymptomScreen> {
  int _currentStep = 0;
  String? _selectedBodyPart;
  final List<String> _selectedSymptoms = [];

  final Map<String, List<String>> _bodyPartSymptoms = {
    '头部': ['头痛', '头晕', '耳鸣', '视力模糊', '鼻塞', '咽喉痛'],
    '胸部': ['胸闷', '胸痛', '心悸', '呼吸困难', '咳嗽', '气短'],
    '腹部': ['胃痛', '腹胀', '腹泻', '便秘', '恶心', '呕吐'],
    '四肢': ['关节痛', '肌肉酸痛', '手脚麻木', '水肿', '抽筋', '无力'],
    '皮肤': ['皮疹', '瘙痒', '红肿', '脱皮', '色素沉着', '溃疡'],
    '全身': ['发热', '疲劳', '失眠', '食欲不振', '体重变化', '多汗'],
  };

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: const CustomAppBar(title: '症状自查'),
      body: Column(
        children: [
          _buildStepIndicator(),
          Expanded(
            child: _currentStep == 0
                ? _buildBodyPartSelector()
                : _currentStep == 1
                    ? _buildSymptomSelector()
                    : _buildResultView(),
          ),
          _buildBottomButton(),
        ],
      ),
    );
  }

  Widget _buildStepIndicator() {
    return Container(
      padding: const EdgeInsets.all(16),
      color: Colors.white,
      child: Row(
        children: [
          _buildStep(0, '选择部位'),
          _buildStepLine(0),
          _buildStep(1, '选择症状'),
          _buildStepLine(1),
          _buildStep(2, '查看结果'),
        ],
      ),
    );
  }

  Widget _buildStep(int step, String label) {
    final isActive = _currentStep >= step;
    return Column(
      children: [
        Container(
          width: 28,
          height: 28,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: isActive ? const Color(0xFF52C41A) : Colors.grey[300],
          ),
          child: Center(
            child: isActive && _currentStep > step
                ? const Icon(Icons.check, size: 16, color: Colors.white)
                : Text(
                    '${step + 1}',
                    style: TextStyle(color: isActive ? Colors.white : Colors.grey[600], fontSize: 13),
                  ),
          ),
        ),
        const SizedBox(height: 4),
        Text(label, style: TextStyle(fontSize: 12, color: isActive ? const Color(0xFF52C41A) : Colors.grey[500])),
      ],
    );
  }

  Widget _buildStepLine(int step) {
    return Expanded(
      child: Container(
        height: 2,
        margin: const EdgeInsets.only(bottom: 18),
        color: _currentStep > step ? const Color(0xFF52C41A) : Colors.grey[300],
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
        final icons = [Icons.face, Icons.favorite, Icons.restaurant, Icons.accessibility, Icons.brush, Icons.self_improvement];
        return GestureDetector(
          onTap: () => setState(() => _selectedBodyPart = part),
          child: Container(
            decoration: BoxDecoration(
              color: isSelected ? const Color(0xFFF0F9EB) : Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isSelected ? const Color(0xFF52C41A) : Colors.grey[200]!,
                width: isSelected ? 2 : 1,
              ),
            ),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Icon(
                  icons[index],
                  size: 32,
                  color: isSelected ? const Color(0xFF52C41A) : Colors.grey[600],
                ),
                const SizedBox(height: 8),
                Text(
                  part,
                  style: TextStyle(
                    fontSize: 15,
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
                    color: isSelected ? const Color(0xFF52C41A) : Colors.grey[800],
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
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
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
                  color: isSelected ? const Color(0xFF52C41A) : Colors.white,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(
                    color: isSelected ? const Color(0xFF52C41A) : Colors.grey[300]!,
                  ),
                ),
                child: Text(
                  symptom,
                  style: TextStyle(
                    color: isSelected ? Colors.white : Colors.grey[800],
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.normal,
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
                    Icon(Icons.medical_information, color: Color(0xFF52C41A)),
                    SizedBox(width: 8),
                    Text('症状分析结果', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                  ],
                ),
                const SizedBox(height: 16),
                Text('部位：$_selectedBodyPart', style: const TextStyle(fontSize: 15)),
                const SizedBox(height: 8),
                Text('症状：${_selectedSymptoms.join("、")}', style: const TextStyle(fontSize: 15)),
                const Divider(height: 24),
                const Text(
                  '可能原因',
                  style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                const Text(
                  '根据您选择的症状，AI正在进行分析，请稍后查看详细结果。建议您及时就医，以获得准确的诊断和治疗方案。',
                  style: TextStyle(fontSize: 14, height: 1.6, color: Color(0xFF666666)),
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
              border: Border.all(color: const Color(0xFFFA8C16).withOpacity(0.3)),
            ),
            child: const Row(
              children: [
                Icon(Icons.warning_amber, color: Color(0xFFFA8C16)),
                SizedBox(width: 12),
                Expanded(
                  child: Text(
                    '以上分析仅供参考，不能替代医生的专业诊断。如症状严重，请立即就医。',
                    style: TextStyle(fontSize: 13, color: Color(0xFF666666), height: 1.4),
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
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(24)),
                ),
                child: const Text('上一步', style: TextStyle(color: Color(0xFF52C41A))),
              ),
            ),
          if (_currentStep > 0) const SizedBox(width: 12),
          if (_currentStep < 2)
            Expanded(
              child: ElevatedButton(
                onPressed: (_currentStep == 0 && _selectedBodyPart == null) ||
                        (_currentStep == 1 && _selectedSymptoms.isEmpty)
                    ? null
                    : () => setState(() => _currentStep++),
                child: Text(_currentStep == 1 ? '查看结果' : '下一步'),
              ),
            ),
        ],
      ),
    );
  }
}
