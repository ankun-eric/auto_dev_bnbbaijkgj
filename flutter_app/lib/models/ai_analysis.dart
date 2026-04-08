class IndicatorItem {
  final String name;
  final String value;
  final String unit;
  final String reference;
  final String status;
  final String? suggestion;

  IndicatorItem({
    required this.name,
    required this.value,
    required this.unit,
    required this.reference,
    required this.status,
    this.suggestion,
  });

  factory IndicatorItem.fromJson(Map<String, dynamic> json) {
    return IndicatorItem(
      name: json['name']?.toString() ?? '',
      value: json['value']?.toString() ?? '',
      unit: json['unit']?.toString() ?? '',
      reference: json['reference']?.toString() ?? '',
      status: json['status']?.toString() ?? '正常',
      suggestion: json['suggestion']?.toString(),
    );
  }

  bool get isAbnormal => status == '偏高' || status == '偏低';
}

class IndicatorCategory {
  final String name;
  final List<IndicatorItem> items;

  IndicatorCategory({required this.name, required this.items});

  factory IndicatorCategory.fromJson(Map<String, dynamic> json) {
    return IndicatorCategory(
      name: json['name']?.toString() ?? '',
      items: (json['items'] as List<dynamic>?)
              ?.map((e) => IndicatorItem.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}

class ReportAnalysisResult {
  final String summary;
  final List<IndicatorCategory> categories;
  final List<String> abnormalItems;

  ReportAnalysisResult({
    required this.summary,
    required this.categories,
    required this.abnormalItems,
  });

  factory ReportAnalysisResult.fromJson(Map<String, dynamic> json) {
    return ReportAnalysisResult(
      summary: json['summary']?.toString() ?? '',
      categories: (json['categories'] as List<dynamic>?)
              ?.map((e) => IndicatorCategory.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      abnormalItems: (json['abnormal_items'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList() ??
          [],
    );
  }

  List<IndicatorItem> get allAbnormalItems {
    final result = <IndicatorItem>[];
    for (final cat in categories) {
      for (final item in cat.items) {
        if (item.isAbnormal) result.add(item);
      }
    }
    return result;
  }
}

class DrugInfo {
  final String name;
  final String? ingredients;
  final String? specification;
  final String? indications;
  final String? dosage;
  final String? precautions;
  final String? aiSuggestionGeneral;
  final String? aiSuggestionPersonal;

  DrugInfo({
    required this.name,
    this.ingredients,
    this.specification,
    this.indications,
    this.dosage,
    this.precautions,
    this.aiSuggestionGeneral,
    this.aiSuggestionPersonal,
  });

  factory DrugInfo.fromJson(Map<String, dynamic> json) {
    return DrugInfo(
      name: json['name']?.toString() ?? '',
      ingredients: json['ingredients']?.toString(),
      specification: json['specification']?.toString(),
      indications: json['indications']?.toString(),
      dosage: json['dosage']?.toString(),
      precautions: json['precautions']?.toString(),
      aiSuggestionGeneral: json['ai_suggestion_general']?.toString(),
      aiSuggestionPersonal: json['ai_suggestion_personal']?.toString(),
    );
  }

  DrugInfo copyWith({String? aiSuggestionPersonal}) {
    return DrugInfo(
      name: name,
      ingredients: ingredients,
      specification: specification,
      indications: indications,
      dosage: dosage,
      precautions: precautions,
      aiSuggestionGeneral: aiSuggestionGeneral,
      aiSuggestionPersonal: aiSuggestionPersonal ?? this.aiSuggestionPersonal,
    );
  }
}

class DrugInteraction {
  final List<String> drugs;
  final String risk;

  DrugInteraction({required this.drugs, required this.risk});

  factory DrugInteraction.fromJson(Map<String, dynamic> json) {
    return DrugInteraction(
      drugs: (json['drugs'] as List<dynamic>?)?.map((e) => e.toString()).toList() ?? [],
      risk: json['risk']?.toString() ?? '',
    );
  }
}

class DrugAnalysisResult {
  final List<DrugInfo> drugs;
  final List<DrugInteraction> interactions;

  DrugAnalysisResult({required this.drugs, required this.interactions});

  factory DrugAnalysisResult.fromJson(Map<String, dynamic> json) {
    return DrugAnalysisResult(
      drugs: (json['drugs'] as List<dynamic>?)
              ?.map((e) => DrugInfo.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      interactions: (json['interactions'] as List<dynamic>?)
              ?.map((e) => DrugInteraction.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}
