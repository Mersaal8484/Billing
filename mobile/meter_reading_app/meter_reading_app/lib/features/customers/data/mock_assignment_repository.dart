import 'dart:async';
import 'dart:math';

import '../domain/entities.dart';

abstract class AssignmentRepository {
  Stream<List<ReadingAssignment>> watchAssignments(
      {String? query, AssignmentStatus? filter});
  Future<ReadingAssignment?> lookupByMeterNumber(String meterNumber);
  Future<ReadingAssignment?> resolveQr(String payload);
  Future<void> markStatus(String assignmentId, AssignmentStatus status);
  void dispose();
}

/// Mock implementation — بيانات تجريبية يمنية واقعية.
/// يستخدم Stream.multi لضمان وصول البيانات فور الاشتراك.
class MockAssignmentRepository implements AssignmentRepository {
  final _changeHub = StreamController<List<ReadingAssignment>>.broadcast();
  late List<ReadingAssignment> _all;

  MockAssignmentRepository() {
    _all = _generateMockAssignments();
  }

  void _notifyListeners() {
    if (!_changeHub.isClosed) _changeHub.add(List.unmodifiable(_all));
  }

  List<ReadingAssignment> _applyFilters(
    List<ReadingAssignment> source, {
    String? query,
    AssignmentStatus? filter,
  }) {
    var result = source;
    if (filter != null) {
      result = result.where((a) => a.status == filter).toList();
    }
    if (query != null && query.trim().isNotEmpty) {
      final q = query.trim().toLowerCase();
      result = result
          .where((a) =>
              a.customer.name.toLowerCase().contains(q) ||
              a.customer.accountNumber.toLowerCase().contains(q) ||
              a.meter.meterNumber.toLowerCase().contains(q))
          .toList();
    }
    return result;
  }

  @override
  Stream<List<ReadingAssignment>> watchAssignments(
      {String? query, AssignmentStatus? filter}) {
    return Stream<List<ReadingAssignment>>.multi((controller) {
      try {
        controller.add(_applyFilters(List.unmodifiable(_all),
            query: query, filter: filter));
      } catch (e, st) {
        controller.addError(e, st);
      }
      final sub = _changeHub.stream.listen(
        (list) {
          try {
            controller
                .add(_applyFilters(list, query: query, filter: filter));
          } catch (e, st) {
            controller.addError(e, st);
          }
        },
        onError: controller.addError,
        onDone: controller.close,
      );
      controller.onCancel = sub.cancel;
    });
  }

  @override
  Future<ReadingAssignment?> lookupByMeterNumber(String meterNumber) async {
    await Future.delayed(const Duration(milliseconds: 150));
    try {
      return _all.firstWhere((a) => a.meter.meterNumber == meterNumber);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<ReadingAssignment?> resolveQr(String payload) async {
    await Future.delayed(const Duration(milliseconds: 300));
    try {
      final clean = payload.replaceAll('UTILITY:', '').trim().toLowerCase();
      return _all.firstWhere(
        (a) =>
            a.customer.accountNumber.toLowerCase() == clean ||
            a.meter.meterNumber.toLowerCase() == clean ||
            'utility:${a.customer.accountNumber.toLowerCase()}' ==
                payload.trim().toLowerCase(),
      );
    } catch (_) {
      return null;
    }
  }

  @override
  Future<void> markStatus(String assignmentId, AssignmentStatus status) async {
    final idx = _all.indexWhere((a) => a.id == assignmentId);
    if (idx == -1) return;
    final a = _all[idx];
    final updated = List<ReadingAssignment>.from(_all);
    updated[idx] = ReadingAssignment(
      id: a.id,
      meter: a.meter,
      customer: a.customer,
      status: status,
      scheduledAt: a.scheduledAt,
      averageConsumption: a.averageConsumption,
    );
    _all = List.unmodifiable(updated);
    _notifyListeners();
  }

  List<ReadingAssignment> _generateMockAssignments() {
    // ── أسماء يمنية واقعية ───────────────────────────────────────────────
    final names = [
      'محمد أحمد علي',
      'عبدالله حسن الشرعبي',
      'خالد عبدالكريم السامعي',
      'يحيى صالح الأنسي',
      'أحمد علي الحميري',
      'عبدالرحمن محمد الذماري',
      'طارق عمر العمراني',
      'إبراهيم يوسف المأربي',
      'حسين علي الصعدي',
      'جمال عبدالملك الحضرمي',
      'ناصر محمد الإبي',
      'سامي عبدالله الحوثي',
    ];

    // ── عناوين يمنية ─────────────────────────────────────────────────────
    final addresses = [
      'حي السنينة، شارع الستين',
      'حي شميلة، شارع جمال',
      'حي الأصبحي، شارع النصر',
      'حي التحرير، شارع الزبيري',
      'حي الجراف، شارع السبعين',
      'حي الروضة، شارع المطار',
      'حي بئر العزب، شارع العيزري',
      'حي القاهرة، تعز',
      'حي الميناء، الحديدة',
      'حي الهوك، الحديدة',
      'حي المظفر، تعز',
      'حي شعوب، صنعاء',
    ];

    final regions = [
      'صنعاء', 'صنعاء', 'صنعاء', 'صنعاء',
      'صنعاء', 'صنعاء', 'صنعاء', 'تعز',
      'الحديدة', 'الحديدة', 'تعز', 'صنعاء',
    ];

    final areas = [
      'معين', 'السبعين', 'الثورة', 'التحرير',
      'آزال', 'الروضة', 'بئر العزب', 'القاهرة',
      'الميناء', 'الهوك', 'المظفر', 'شعوب',
    ];

    final phones = [
      '770123456', '771654321', '733555222', '775888999',
      '777345678', '778901234', '776543210', '771234567',
      '773456789', '770987654', '772345678', '774567890',
    ];

    // متوسط استهلاك كهرباء شهري واقعي بـ kWh
    final avgConsumptions = [
      120.0, 95.0, 210.0, 145.0, 88.0, 175.0,
      130.0, 200.0, 165.0, 110.0, 155.0, 140.0,
    ];

    final rnd = Random(42);
    final now = DateTime.now();
    final list = <ReadingAssignment>[];

    for (var i = 0; i < names.length; i++) {
      final customer = Customer(
        remoteId: 1000 + i,
        customerNumber: 'YEM-${810000 + i}',  // ← required
        accountNumber: 'ACC-${100000 + i}',
        name: names[i],
        mobile: phones[i],
        address: addresses[i],
        regionName: regions[i],
        areaName: areas[i],
        lastReadingDate: now.subtract(Duration(days: 30 + rnd.nextInt(5))),
        lastReadingValue: (500 + rnd.nextInt(4000)).toDouble(),
      );
      final meter = Meter(
        remoteId: 2000 + i,
        meterNumber: '${100001 + i}',        // عدادات يمنية
        serialNumber: 'YE${90000 + i}',
        customerRemoteId: customer.remoteId,
        paymentType: MeterPaymentType.postpaid,
        meterType: i % 5 == 0 ? 'Three Phase' : 'Single Phase',
      );
      list.add(ReadingAssignment(
        id: 'assign-$i',
        meter: meter,
        customer: customer,
        status: i < 3 ? AssignmentStatus.read : AssignmentStatus.pending,
        scheduledAt: now,                     // ← required
        averageConsumption: avgConsumptions[i], // ← required
      ));
    }
    return list;
  }

  @override
  void dispose() {
    if (!_changeHub.isClosed) _changeHub.close();
  }
}
