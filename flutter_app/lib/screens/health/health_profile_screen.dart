import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/health_provider.dart';
import '../../services/api_service.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/loading_widget.dart';

class HealthProfileScreen extends StatefulWidget {
  const HealthProfileScreen({super.key});

  @override
  State<HealthProfileScreen> createState() => _HealthProfileScreenState();
}

class _HealthProfileScreenState extends State<HealthProfileScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  final ApiService _apiService = ApiService();

  int _selectedMemberIndex = 0;
  List<Map<String, dynamic>> _familyMembers = [
    {'name': '本人', 'relation': '本人', 'is_self': true},
  ];

  static Color _relationColor(String relation) {
    if (relation == '本人') return const Color(0xFF52C41A);
    if (relation == '爸爸' || relation == '妈妈' || relation == '父亲' || relation == '母亲') {
      return const Color(0xFF1890FF);
    }
    if (relation == '儿子' || relation == '女儿' || relation == '子女') {
      return const Color(0xFFEB2F96);
    }
    if (relation == '爷爷' || relation == '奶奶') return const Color(0xFFFA8C16);
    return const Color(0xFF8C8C8C);
  }

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    _loadFamilyMembers();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<HealthProvider>(context, listen: false).loadHealthProfile();
    });
  }

  Future<void> _loadFamilyMembers() async {
    try {
      final response = await _apiService.getFamilyMembers();
      if (response.statusCode == 200 && mounted) {
        final items = response.data['items'] as List? ?? [];
        if (items.isNotEmpty) {
          setState(() {
            _familyMembers = items.map((e) {
              final m = Map<String, dynamic>.from(e as Map);
              return {
                'id': m['id'],
                'name': m['nickname'] ?? m['name'] ?? '',
                'relation': m['relation_type_name'] ?? m['relationship_type'] ?? '本人',
                'is_self': m['is_self'] ?? false,
              };
            }).toList();
          });
        }
      }
    } catch (_) {}
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  void _onMemberTap(int index) {
    setState(() => _selectedMemberIndex = index);
  }

  void _onAddMember() {
    Navigator.pushNamed(context, '/family');
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('健康档案'),
        backgroundColor: const Color(0xFF52C41A),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Column(
        children: [
          _buildMemberTabs(),
          Container(
            color: Colors.white,
            child: TabBar(
              controller: _tabController,
              indicatorColor: const Color(0xFF52C41A),
              indicatorWeight: 3,
              labelColor: const Color(0xFF52C41A),
              unselectedLabelColor: const Color(0xFF999999),
              tabs: const [
                Tab(text: '基础信息'),
                Tab(text: '健康记录'),
                Tab(text: '用药记录'),
              ],
            ),
          ),
          Expanded(
            child: Consumer<HealthProvider>(
              builder: (context, provider, child) {
                if (provider.isLoading) {
                  return const LoadingWidget();
                }

                return TabBarView(
                  controller: _tabController,
                  children: [
                    _buildBasicInfo(provider),
                    _buildHealthRecords(),
                    _buildMedicationRecords(),
                  ],
                );
              },
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildMemberTabs() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: SizedBox(
        height: 72,
        child: ListView.builder(
          scrollDirection: Axis.horizontal,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          itemCount: _familyMembers.length + 1,
          itemBuilder: (context, index) {
            if (index == _familyMembers.length) {
              return _buildAddButton();
            }
            final member = _familyMembers[index];
            final relation = member['relation']?.toString() ?? '本人';
            final isSelected = index == _selectedMemberIndex;
            final color = _relationColor(relation);

            return GestureDetector(
              onTap: () => _onMemberTap(index),
              child: Padding(
                padding: const EdgeInsets.symmetric(horizontal: 6),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Container(
                      width: 44,
                      height: 44,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: isSelected ? color : const Color(0xFFF0F0F0),
                        boxShadow: isSelected
                            ? [BoxShadow(color: color.withOpacity(0.3), blurRadius: 6, offset: const Offset(0, 2))]
                            : null,
                      ),
                      alignment: Alignment.center,
                      child: Text(
                        relation.length > 2 ? relation.substring(0, 2) : relation,
                        style: TextStyle(
                          fontSize: 13,
                          fontWeight: FontWeight.w600,
                          color: isSelected ? Colors.white : const Color(0xFF333333),
                        ),
                      ),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      relation,
                      style: TextStyle(
                        fontSize: 10,
                        color: isSelected ? color : const Color(0xFF999999),
                      ),
                      overflow: TextOverflow.ellipsis,
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildAddButton() {
    return GestureDetector(
      onTap: _onAddMember,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 6),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width: 44,
              height: 44,
              decoration: const BoxDecoration(
                shape: BoxShape.circle,
                color: Color(0xFFF0F0F0),
              ),
              alignment: Alignment.center,
              child: const Icon(Icons.add, color: Color(0xFF999999), size: 22),
            ),
            const SizedBox(height: 4),
            const Text('添加', style: TextStyle(fontSize: 10, color: Color(0xFF999999))),
          ],
        ),
      ),
    );
  }

  Widget _buildBasicInfo(HealthProvider provider) {
    final profile = provider.healthProfile;
    return SingleChildScrollView(
      padding: const EdgeInsets.all(16),
      child: Column(
        children: [
          _buildInfoCard('身高', '${profile?.height ?? "--"} cm', Icons.height),
          _buildInfoCard('体重', '${profile?.weight ?? "--"} kg', Icons.monitor_weight),
          _buildInfoCard('BMI', profile?.bmi?.toStringAsFixed(1) ?? '--', Icons.analytics),
          _buildInfoCard('血型', profile?.bloodType ?? '--', Icons.bloodtype),
          _buildInfoCard('过敏史', profile?.allergies.join(', ') ?? '无', Icons.warning_amber),
          _buildInfoCard('慢性病', profile?.chronicDiseases.join(', ') ?? '无', Icons.medical_information),
          _buildInfoCard('体质类型', profile?.constitution ?? '未测评', Icons.spa),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () {},
              child: const Text('编辑信息'),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoCard(String label, String value, IconData icon) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        children: [
          Container(
            width: 40,
            height: 40,
            decoration: BoxDecoration(
              color: const Color(0xFF52C41A).withOpacity(0.1),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: const Color(0xFF52C41A), size: 20),
          ),
          const SizedBox(width: 14),
          Text(label, style: TextStyle(fontSize: 15, color: Colors.grey[600])),
          const Spacer(),
          Text(value, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
        ],
      ),
    );
  }

  Widget _buildHealthRecords() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.folder_open, size: 60, color: Colors.grey[300]),
          const SizedBox(height: 12),
          Text('暂无健康记录', style: TextStyle(color: Colors.grey[500])),
        ],
      ),
    );
  }

  Widget _buildMedicationRecords() {
    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(Icons.medication_outlined, size: 60, color: Colors.grey[300]),
          const SizedBox(height: 12),
          Text('暂无用药记录', style: TextStyle(color: Colors.grey[500])),
        ],
      ),
    );
  }
}
