class HealthProfile {
  final String id;
  final String userId;
  final double? height;
  final double? weight;
  final String? bloodType;
  final List<dynamic> allergies;
  final List<dynamic> chronicDiseases;
  final List<String> medications;
  final List<dynamic> geneticDiseases;
  final String? constitution;
  final String? updatedAt;

  HealthProfile({
    required this.id,
    required this.userId,
    this.height,
    this.weight,
    this.bloodType,
    this.allergies = const [],
    this.chronicDiseases = const [],
    this.medications = const [],
    this.geneticDiseases = const [],
    this.constitution,
    this.updatedAt,
  });

  double? get bmi {
    if (height != null && weight != null && height! > 0) {
      final h = height! / 100;
      return weight! / (h * h);
    }
    return null;
  }

  static bool isCustomItem(dynamic item) =>
      item is Map && item['type'] == 'custom';

  static String getItemName(dynamic item) =>
      item is String ? item : (item is Map ? (item['value'] ?? '') : '');

  factory HealthProfile.fromJson(Map<String, dynamic> json) {
    return HealthProfile(
      id: json['id']?.toString() ?? '',
      userId: json['user_id']?.toString() ?? '',
      height: json['height']?.toDouble(),
      weight: json['weight']?.toDouble(),
      bloodType: json['blood_type'],
      allergies: List<dynamic>.from(json['allergies'] ?? []),
      chronicDiseases: List<dynamic>.from(json['chronic_diseases'] ?? []),
      medications: List<String>.from(json['medications'] ?? []),
      geneticDiseases: List<dynamic>.from(json['genetic_diseases'] ?? []),
      constitution: json['constitution'],
      updatedAt: json['updated_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'user_id': userId,
      'height': height,
      'weight': weight,
      'blood_type': bloodType,
      'allergies': allergies,
      'chronic_diseases': chronicDiseases,
      'medications': medications,
      'genetic_diseases': geneticDiseases,
      'constitution': constitution,
      'updated_at': updatedAt,
    };
  }
}
