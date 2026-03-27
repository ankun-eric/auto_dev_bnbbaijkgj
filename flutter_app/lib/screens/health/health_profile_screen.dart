import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../providers/health_provider.dart';
import '../../widgets/custom_app_bar.dart';
import '../../widgets/loading_widget.dart';

class HealthProfileScreen extends StatefulWidget {
  const HealthProfileScreen({super.key});

  @override
  State<HealthProfileScreen> createState() => _HealthProfileScreenState();
}

class _HealthProfileScreenState extends State<HealthProfileScreen> with SingleTickerProviderStateMixin {
  late TabController _tabController;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) {
      Provider.of<HealthProvider>(context, listen: false).loadHealthProfile();
    });
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
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
        bottom: TabBar(
          controller: _tabController,
          indicatorColor: Colors.white,
          indicatorWeight: 3,
          tabs: const [
            Tab(text: '基础信息'),
            Tab(text: '健康记录'),
            Tab(text: '用药记录'),
          ],
        ),
      ),
      body: Consumer<HealthProvider>(
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
