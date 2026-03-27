class HealthProfile {
  final String id;
  final String userId;
  final double? height;
  final double? weight;
  final String? bloodType;
  final List<String> allergies;
  final List<String> chronicDiseases;
  final List<String> medications;
  final String? familyHistory;
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
    this.familyHistory,
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

  factory HealthProfile.fromJson(Map<String, dynamic> json) {
    return HealthProfile(
      id: json['id']?.toString() ?? '',
      userId: json['user_id']?.toString() ?? '',
      height: json['height']?.toDouble(),
      weight: json['weight']?.toDouble(),
      bloodType: json['blood_type'],
      allergies: List<String>.from(json['allergies'] ?? []),
      chronicDiseases: List<String>.from(json['chronic_diseases'] ?? []),
      medications: List<String>.from(json['medications'] ?? []),
      familyHistory: json['family_history'],
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
      'family_history': familyHistory,
      'constitution': constitution,
      'updated_at': updatedAt,
    };
  }
}
