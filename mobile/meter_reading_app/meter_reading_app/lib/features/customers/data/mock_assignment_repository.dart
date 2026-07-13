import 'dart:async';
import 'dart:math';

import '../domain/entities.dart';

abstract class AssignmentRepository {
  Stream<List<ReadingAssignment>> watchAssignments(
      {String? query, AssignmentStatus? filter});
  Future<ReadingAssignment?> lookupByMeterNumber(String meterNumber);
  Future<void> markStatus(String assignmentId, AssignmentStatus status);
  void dispose();
}

class MockAssignmentRepository implements AssignmentRepository {
  final _changeHub = StreamController<List<ReadingAssignment>>.broadcast();
  late List<ReadingAssignment> _all;

  MockAssignmentRepository() {
    _all = List.unmodifiable(_generateMockAssignments());
  }

  void _notifyListeners() {
    if (!_changeHub.isClosed) {
      _changeHub.add(List.unmodifiable(_all));
    }
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
          .where(
            (a) =>
                a.customer.name.toLowerCase().contains(q) ||
                a.customer.customerNumber.toLowerCase().contains(q) ||
                a.customer.accountNumber.toLowerCase().contains(q) ||
                a.meter.meterNumber.toLowerCase().contains(q) ||
                (a.meter.serialNumber?.toLowerCase().contains(q) ?? false),
          )
          .toList();
    }
    return result;
  }

  @override
  Stream<List<ReadingAssignment>> watchAssignments({
    String? query,
    AssignmentStatus? filter,
  }) {
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
            controller.add(_applyFilters(list, query: query, filter: filter));
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
      return _all.firstWhere(
        (a) =>
            a.meter.meterNumber.toLowerCase() == meterNumber.toLowerCase() ||
            a.meter.serialNumber?.toLowerCase() == meterNumber.toLowerCase(),
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
    final names = [
      'محمد أحمد الحداد',
      'فاطمة علي النعيمي',
      'خالد سالم القحطاني',
      'ليلى يوسف الشامي',
      'عبدالله حسين الزهراني',
      'مريم عبدالرحمن العمري',
      'سعيد ناصر البلوشي',
      'هدى كريم السلمي',
      'ياسر فهد المطيري',
      'نورة راشد الدوسري',
      'طارق عمر الغامدي',
      'سارة فيصل العتيبي',
    ];
    final rnd = Random(42);
    final list = <ReadingAssignment>[];
    for (var i = 0; i < names.length; i++) {
      final customer = Customer(
        remoteId: 1000 + i,
        customerNumber: 'CUS-${700000 + i}',
        accountNumber: 'ACC-${100000 + i}',
        name: names[i],
        mobile: '05${50000000 + i * 9137}',
        address: 'الحي ${i + 1}، شارع ${10 + i}',
        regionName: 'المنطقة الشمالية',
        areaName: i.isEven ? 'حي النخيل' : 'حي السلام',
        lastReadingDate:
            DateTime.now().subtract(Duration(days: 30 + rnd.nextInt(5))),
        lastReadingValue: (500 + rnd.nextInt(4000)).toDouble(),
      );
      final meter = Meter(
        remoteId: 2000 + i,
        meterNumber: 'MTR-${1000 + i}',
        serialNumber: 'SN${90000 + i}',
        customerRemoteId: customer.remoteId,
        paymentType: MeterPaymentType.postpaid,
        meterType: i % 5 == 0 ? 'Three Phase' : 'Single Phase',
        connectionStatus: i == 8 ? 'disconnected' : 'connected',
      );
      list.add(
        ReadingAssignment(
          id: 'assign-$i',
          meter: meter,
          customer: customer,
          status: switch (i) {
            0 || 1 => AssignmentStatus.read,
            2 => AssignmentStatus.pendingDecision,
            3 => AssignmentStatus.rejected,
            4 => AssignmentStatus.escalated,
            _ => AssignmentStatus.pending,
          },
          scheduledAt: DateTime.now().add(Duration(minutes: (i - 2) * 18)),
          averageConsumption: (260 + rnd.nextInt(220)).toDouble(),
        ),
      );
    }
    return list;
  }

  @override
  void dispose() {
    if (!_changeHub.isClosed) _changeHub.close();
  }
}
