import 'dart:async';
import '../../../core/network/odoo_api_client.dart';
import '../domain/entities.dart';
import 'mock_assignment_repository.dart' show AssignmentRepository;

class OdooAssignmentRepository implements AssignmentRepository {
  final OdooApiClient _client;
  final _changeHub = StreamController<List<ReadingAssignment>>.broadcast();
  List<ReadingAssignment> _all = [];
  bool _initialized = false;

  OdooAssignmentRepository(this._client);

  String? _lastError;
  String? get lastError => _lastError;

  Future<void> _fetchData() async {
    try {
      final response = await _client.postJson('/api/v1/utility/reader/subscribers', {});
      if (response['success'] == true) {
        final subs = response['subscribers'] as List<dynamic>;
        final list = <ReadingAssignment>[];
        final now = DateTime.now();

        for (int i = 0; i < subs.length; i++) {
          final s = subs[i] as Map<String, dynamic>;
          final cId = s['id'] as int;
          final mId = s['meter_id'] as int?;

          final customer = Customer(
            remoteId: cId,
            customerNumber: s['customer_number']?.toString() ?? '',
            accountNumber: 'ACC-$cId',
            name: s['name']?.toString() ?? '',
            address: s['address']?.toString(),
            regionName: s['route_name']?.toString(),
          );

          final meter = Meter(
            remoteId: mId ?? 0,
            meterNumber: s['meter_number']?.toString() ?? '',
            customerRemoteId: customer.remoteId,
            paymentType: MeterPaymentType.postpaid,
          );

          list.add(ReadingAssignment(
            id: 'assign-$cId',
            meter: meter,
            customer: customer,
            status: _assignmentStatusFromApi(s['reading_status']),
            scheduledAt: now,
            averageConsumption: 0.0,
          ));
        }

        _all = List.unmodifiable(list);
        _lastError = null;
        _notifyListeners();
      } else {
        _lastError = 'API returned success=false';
        _notifyListeners();
      }
    } catch (e) {
      _lastError = e.toString();
      _notifyListeners();
    }
  }

  AssignmentStatus _assignmentStatusFromApi(dynamic value) => switch (value) {
        'read' => AssignmentStatus.read,
        'rejected' => AssignmentStatus.rejected,
        'pending_decision' => AssignmentStatus.pendingDecision,
        'escalated' => AssignmentStatus.escalated,
        'skipped' => AssignmentStatus.skipped,
        _ => AssignmentStatus.pending,
      };

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
  Stream<List<ReadingAssignment>> watchAssignments({String? query, AssignmentStatus? filter}) {
    return Stream<List<ReadingAssignment>>.multi((controller) {
      if (!_initialized) {
        _initialized = true;
        _fetchData();
      }
      try {
        controller.add(_applyFilters(List.unmodifiable(_all), query: query, filter: filter));
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
  Future<ReadingAssignment?> getById(String id) async {
    try {
      return _all.firstWhere((a) => a.id == id);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<ReadingAssignment?> lookupByMeterNumber(String meterNumber) async {
    try {
      return _all.firstWhere((a) => a.meter.meterNumber == meterNumber);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<ReadingAssignment?> resolveQr(String payload) async {
    try {
      final clean = payload.replaceAll('UTILITY:', '').trim().toLowerCase();
      return _all.firstWhere(
        (a) =>
            a.customer.accountNumber.toLowerCase() == clean ||
            a.meter.meterNumber.toLowerCase() == clean ||
            'utility:${a.customer.accountNumber.toLowerCase()}' == payload.trim().toLowerCase(),
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

  @override
  void dispose() {
    if (!_changeHub.isClosed) _changeHub.close();
  }
}
