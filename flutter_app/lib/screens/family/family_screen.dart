import 'package:flutter/material.dart';
import '../../widgets/custom_app_bar.dart';

class FamilyScreen extends StatefulWidget {
  const FamilyScreen({super.key});

  @override
  State<FamilyScreen> createState() => _FamilyScreenState();
}

class _FamilyScreenState extends State<FamilyScreen> {
  final List<Map<String, dynamic>> _members = [
    {'name': '我', 'relation': '本人', 'avatar': Icons.person, 'age': 30, 'gender': '男'},
  ];

  void _addMember() {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (context) {
        final nameController = TextEditingController();
        String relation = '配偶';
        return Padding(
          padding: EdgeInsets.only(
            left: 24,
            right: 24,
            top: 24,
            bottom: MediaQuery.of(context).viewInsets.bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('添加家庭成员', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
              const SizedBox(height: 20),
              TextField(
                controller: nameController,
                decoration: InputDecoration(
                  labelText: '姓名',
                  border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
                ),
              ),
              const SizedBox(height: 16),
              const Text('关系', style: TextStyle(fontSize: 15, fontWeight: FontWeight.w500)),
              const SizedBox(height: 8),
              Wrap(
                spacing: 8,
                children: ['配偶', '父亲', '母亲', '子女', '其他'].map((r) {
                  return ChoiceChip(
                    label: Text(r),
                    selected: relation == r,
                    selectedColor: const Color(0xFF52C41A).withOpacity(0.2),
                    onSelected: (selected) {
                      if (selected) relation = r;
                    },
                  );
                }).toList(),
              ),
              const SizedBox(height: 24),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: () {
                    if (nameController.text.isNotEmpty) {
                      setState(() {
                        _members.add({
                          'name': nameController.text,
                          'relation': relation,
                          'avatar': Icons.person_outline,
                          'age': 0,
                          'gender': '未知',
                        });
                      });
                      Navigator.pop(context);
                    }
                  },
                  child: const Text('确认添加'),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  void _showSosDialog() {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
        title: const Row(
          children: [
            Icon(Icons.emergency, color: Colors.red, size: 28),
            SizedBox(width: 8),
            Text('紧急求助', style: TextStyle(color: Colors.red)),
          ],
        ),
        content: const Text('确定发送紧急求助信号吗？\n\n系统将通知所有家庭成员您当前的位置信息。'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('取消'),
          ),
          ElevatedButton(
            onPressed: () => Navigator.pop(context),
            style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('确认求助'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: CustomAppBar(
        title: '家庭成员',
        actions: [
          IconButton(
            icon: const Icon(Icons.person_add, color: Colors.white),
            onPressed: _addMember,
          ),
        ],
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: _members.length,
              itemBuilder: (context, index) {
                final member = _members[index];
                return Container(
                  margin: const EdgeInsets.only(bottom: 10),
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Colors.white,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: [
                      BoxShadow(
                        color: Colors.black.withOpacity(0.04),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 50,
                        height: 50,
                        decoration: BoxDecoration(
                          color: const Color(0xFF52C41A).withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Icon(member['avatar'], color: const Color(0xFF52C41A), size: 28),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              member['name'],
                              style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600),
                            ),
                            const SizedBox(height: 4),
                            Text(
                              '关系: ${member['relation']}',
                              style: TextStyle(fontSize: 13, color: Colors.grey[500]),
                            ),
                          ],
                        ),
                      ),
                      IconButton(
                        icon: const Icon(Icons.assignment, color: Color(0xFF52C41A)),
                        onPressed: () => Navigator.pushNamed(context, '/health-profile'),
                      ),
                    ],
                  ),
                );
              },
            ),
          ),
          Container(
            padding: EdgeInsets.only(
              left: 16,
              right: 16,
              top: 12,
              bottom: MediaQuery.of(context).padding.bottom + 12,
            ),
            child: SizedBox(
              width: double.infinity,
              height: 54,
              child: ElevatedButton.icon(
                onPressed: _showSosDialog,
                icon: const Icon(Icons.emergency, size: 24),
                label: const Text('SOS 紧急求助', style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
                style: ElevatedButton.styleFrom(
                  backgroundColor: Colors.red,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(27)),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
