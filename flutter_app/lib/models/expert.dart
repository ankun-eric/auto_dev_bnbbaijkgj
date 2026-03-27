class Expert {
  final String id;
  final String name;
  final String? avatar;
  final String? title;
  final String? hospital;
  final String? department;
  final String? specialty;
  final String? introduction;
  final double rating;
  final int consultCount;
  final double price;
  final bool isAvailable;
  final List<String> tags;
  final List<ExpertSchedule> schedules;

  Expert({
    required this.id,
    required this.name,
    this.avatar,
    this.title,
    this.hospital,
    this.department,
    this.specialty,
    this.introduction,
    this.rating = 5.0,
    this.consultCount = 0,
    required this.price,
    this.isAvailable = true,
    this.tags = const [],
    this.schedules = const [],
  });

  factory Expert.fromJson(Map<String, dynamic> json) {
    return Expert(
      id: json['id']?.toString() ?? '',
      name: json['name'] ?? '',
      avatar: json['avatar'],
      title: json['title'],
      hospital: json['hospital'],
      department: json['department'],
      specialty: json['specialty'],
      introduction: json['introduction'],
      rating: (json['rating'] ?? 5.0).toDouble(),
      consultCount: json['consult_count'] ?? 0,
      price: (json['price'] ?? 0).toDouble(),
      isAvailable: json['is_available'] ?? true,
      tags: List<String>.from(json['tags'] ?? []),
      schedules: (json['schedules'] as List?)
              ?.map((e) => ExpertSchedule.fromJson(e))
              .toList() ??
          [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      'avatar': avatar,
      'title': title,
      'hospital': hospital,
      'department': department,
      'specialty': specialty,
      'introduction': introduction,
      'rating': rating,
      'consult_count': consultCount,
      'price': price,
      'is_available': isAvailable,
      'tags': tags,
      'schedules': schedules.map((e) => e.toJson()).toList(),
    };
  }
}

class ExpertSchedule {
  final String date;
  final List<String> timeSlots;
  final int remainSlots;

  ExpertSchedule({
    required this.date,
    required this.timeSlots,
    this.remainSlots = 0,
  });

  factory ExpertSchedule.fromJson(Map<String, dynamic> json) {
    return ExpertSchedule(
      date: json['date'] ?? '',
      timeSlots: List<String>.from(json['time_slots'] ?? []),
      remainSlots: json['remain_slots'] ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'date': date,
      'time_slots': timeSlots,
      'remain_slots': remainSlots,
    };
  }
}
