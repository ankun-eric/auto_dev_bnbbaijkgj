class User {
  final String id;
  final String phone;
  final String? nickname;
  final String? avatar;
  final String? gender;
  final String? birthday;
  final int? age;
  final String? memberLevel;
  final int points;
  final String? createdAt;

  User({
    required this.id,
    required this.phone,
    this.nickname,
    this.avatar,
    this.gender,
    this.birthday,
    this.age,
    this.memberLevel,
    this.points = 0,
    this.createdAt,
  });

  factory User.fromJson(Map<String, dynamic> json) {
    return User(
      id: json['id']?.toString() ?? '',
      phone: json['phone'] ?? '',
      nickname: json['nickname'],
      avatar: json['avatar'],
      gender: json['gender'],
      birthday: json['birthday'],
      age: json['age'],
      memberLevel: json['member_level'],
      points: json['points'] ?? 0,
      createdAt: json['created_at'],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'phone': phone,
      'nickname': nickname,
      'avatar': avatar,
      'gender': gender,
      'birthday': birthday,
      'age': age,
      'member_level': memberLevel,
      'points': points,
      'created_at': createdAt,
    };
  }

  User copyWith({
    String? nickname,
    String? avatar,
    String? gender,
    String? birthday,
    int? age,
    String? memberLevel,
    int? points,
  }) {
    return User(
      id: id,
      phone: phone,
      nickname: nickname ?? this.nickname,
      avatar: avatar ?? this.avatar,
      gender: gender ?? this.gender,
      birthday: birthday ?? this.birthday,
      age: age ?? this.age,
      memberLevel: memberLevel ?? this.memberLevel,
      points: points ?? this.points,
      createdAt: createdAt,
    );
  }
}
