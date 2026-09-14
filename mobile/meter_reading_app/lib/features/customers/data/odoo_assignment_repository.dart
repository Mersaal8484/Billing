import 'dart:async';
import '../../../core/network/odoo_api_client.dart';
import '../domain/entities.dart';
import 'mock_assignment_repository.dart'
    show AssignmentRepository, ReadingAssignmentSyncResult;

class OdooAssignmentRepository implements AssignmentRepository {
  final OdooApiClient _client;
  final _changeHub = StreamController<List<ReadingAssignment>>.broadcast();
  List<ReadingAssignment> _all = [];
  bool _initialized = false;
  Future<ReadingAssignmentSyncResult>? _inFlightFetch;

  OdooAssignmentRepository(this._client);

  String? _lastError;
  String? get lastError => _lastError;

  Future<ReadingAssignmentSyncResult> _fetchData() {
    return _inFlightFetch ??= _fetchDataInternal().whenComplete(() {
      _inFlightFetch = null;
    });
  }

  Future<ReadingAssignmentSyncResult> _fetchDataInternal() async {
    try {
      final response = await _client.postJson('/api/v1/utility/reader/subscribers', {});
      if (response['success'] == true) {
        final subs = response['subscribers'] as List<dynamic>? ?? const [];
        final rawPeriod = response['period'];
        final period = rawPeriod is Map
            ? Map<String, dynamic>.from(rawPeriod)
            : null;
        final list = <ReadingAssignment>[];
        final now = DateTime.now();

        for (int i = 0; i < subs.length; i++) {
          final s = Map<String, dynamic>.from(subs[i] as Map);
          final cId = int.tryParse(s['id']?.toString() ?? '');
          if (cId == null) continue;
          final mId = int.tryParse(s['meter_id']?.toString() ?? '');

          final customer = Customer(
            remoteId: cId,
            customerNumber: s['customer_number']?.toString() ?? '',
            accountNumber: _firstText(
              s,
              ['account_number', 'customer_number', 'subscriber_number'],
              fallback: 'ACC-$cId',
            ),
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
        return ReadingAssignmentSyncResult(
          success: true,
          hasOpenPeriod: period != null,
          periodName: period?['name']?.toString(),
          count: list.length,
          message: response['message']?.toString(),
        );
      } else {
        _lastError = response['error']?.toString() ?? 'API returned success=false';
        _notifyListeners();
        return ReadingAssignmentSyncResult(
          success: false,
          hasOpenPeriod: false,
          count: _all.length,
          message: _lastError,
        );
      }
    } catch (e) {
      _lastError = e.toString();
      _notifyListeners();
      return ReadingAssignmentSyncResult(
        success: false,
        hasOpenPeriod: false,
        count: _all.length,
        message: _lastError,
      );
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

  String _firstText(
    Map<String, dynamic> values,
    List<String> keys, {
    String fallback = '',
  }) {
    for (final key in keys) {
      final value = values[key];
      if (value == null || value == false) continue;
      final text = value.toString().trim();
      if (text.isNotEmpty) return text;
    }
    return fallback;
  }

  String _cleanIdentifier(String value) => value.trim().toLowerCase();

  Set<String> _payloadCandidates(String payload) {
    final raw = payload.trim();
    final values = <String>{};
    void add(String? value) {
      if (value == null) return;
      final clean = _cleanIdentifier(value);
      if (clean.isNotEmpty) values.add(clean);
    }

    add(raw);
    if (raw.toLowerCase().startsWith('utility:')) {
      add(raw.substring('utility:'.length));
    }

    final parts = raw.split('|').map((part) => part.trim()).toList();
    if (parts.isNotEmpty && parts.first.toUpperCase().startsWith('UTILITY')) {
      // Official meter QR shape:
      // UTILITY-METER|company|meter_number|physical_serial|customer_number|...
      if (parts.length > 2) add(parts[2]);
      if (parts.length > 3) add(parts[3]);
      if (parts.length > 4) add(parts[4]);
      if (parts.length > 8) add(parts[8]);
    }
    return values;
  }

  Set<String> _assignmentIdentifiers(ReadingAssignment assignment) {
    final values = <String>{};
    void add(String? value) {
      if (value == null) return;
      final clean = _cleanIdentifier(value);
      if (clean.isNotEmpty) values.add(clean);
    }

    add(assignment.customer.accountNumber);
    add(assignment.customer.customerNumber);
    add(assignment.meter.meterNumber);
    add(assignment.meter.serialNumber);
    add('UTILITY:${assignment.customer.accountNumber}');
    add('UTILITY:${assignment.customer.customerNumber}');
    add('UTILITY:${assignment.meter.meterNumber}');
    return values;
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
              a.customer.customerNumber.toLowerCase().contains(q) ||
              a.customer.accountNumber.toLowerCase().contains(q) ||
              a.meter.meterNumber.toLowerCase().contains(q) ||
              (a.meter.serialNumber?.toLowerCase().contains(q) ?? false))
          .toList();
    }
    return result;
  }

  @override
  Stream<List<ReadingAssignment>> watchAssignments({String? query, AssignmentStatus? filter}) {
    return Stream<List<ReadingAssignment>>.multi((controller) {
      if (!_initialized) {
        _initialized = true;
        unawaited(_fetchData());
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
  Future<ReadingAssignmentSyncResult> syncOpenPeriodAssignments() {
    _initialized = true;
    return _fetchData();
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
      final candidates = _payloadCandidates(payload);
      return _all.firstWhere(
        (a) => _assignmentIdentifiers(a).any(candidates.contains),
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
