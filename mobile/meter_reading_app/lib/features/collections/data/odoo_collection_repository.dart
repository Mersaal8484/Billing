import 'dart:async';

import '../../../core/network/billing_api_service.dart';
import '../../customers/domain/entities.dart';
import '../domain/collection_models.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Source of truth for field collections.  It never fabricates an account,
/// payment or receipt: a receipt is kept locally only after Odoo confirms the
/// posted payment, exact allocation and collector custody record.
class OdooCollectionRepository implements CollectionRepository {
  OdooCollectionRepository(this._billing, {FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final BillingApiService _billing;
  final FlutterSecureStorage _storage;
  final List<CollectionReceipt> _receipts = [];
  final Map<String, CollectionAccount> _accounts = {};
  final _changeHub = StreamController<List<CollectionAccount>>.broadcast();
  CollectionPeriod? _currentPeriod;
  String? _periodMessage;

  @override
  CollectionPeriod? get currentPeriod => _currentPeriod;

  @override
  String? get periodMessage => _periodMessage;

  @override
  Stream<List<CollectionAccount>> watchAccounts({String? query}) async* {
    yield _filterAccounts(query);
    yield* _changeHub.stream.map((_) => _filterAccounts(query));
  }

  List<CollectionAccount> _filterAccounts(String? query) {
    final value = query?.trim().toLowerCase() ?? '';
    final unique = <String, CollectionAccount>{};
    for (final account in _accounts.values) {
      unique[account.id] = account;
    }
    var list = unique.values.toList()
      ..sort((a, b) => b.dueTotal.compareTo(a.dueTotal));
    if (value.isEmpty) return List.unmodifiable(list);
    list = list.where((account) {
      return account.customer.name.toLowerCase().contains(value) ||
          account.customer.customerNumber.toLowerCase().contains(value) ||
          account.customer.accountNumber.toLowerCase().contains(value) ||
          account.meter.meterNumber.toLowerCase().contains(value);
    }).toList();
    return List.unmodifiable(list);
  }

  void _cacheAccount(CollectionAccount account) {
    _accounts[account.id] = account;
    _accounts[account.customer.customerNumber] = account;
    _accounts[account.customer.accountNumber] = account;
    _accounts[account.meter.meterNumber] = account;
  }

  void _notify() {
    if (!_changeHub.isClosed) {
      _changeHub.add(_filterAccounts(null));
    }
  }

  @override
  Future<CollectionPeriod?> syncPeriodInvoices() async {
    final result = await _billing.getCollectorPeriodInvoices();
    final rawPeriod = result['period'];
    if (rawPeriod is! Map) {
      _currentPeriod = null;
      _periodMessage = 'لا توجد فترة تحصيل مفتوحة حالياً';
      _accounts.clear();
      _notify();
      return null;
    }
    final periodMap = Map<String, dynamic>.from(rawPeriod);
    _currentPeriod = CollectionPeriod(
      id: (periodMap['id'] as num).toInt(),
      name: periodMap['name']?.toString() ?? '',
      state: periodMap['state']?.toString() ?? '',
    );
    _periodMessage = null;
    final accounts = _mapPeriodInvoiceAccounts(result);
    _accounts.clear();
    for (final account in accounts) {
      _cacheAccount(account);
    }
    _notify();
    return _currentPeriod;
  }

  @override
  Future<CollectionAccount?> resolveQr(String payload) async {
    final account = _mapAccount(await _billing.getCollectorAccount(qrReference: payload));
    if (account != null) {
      _cacheAccount(account);
      _notify();
    }
    return account;
  }

  @override
  Future<CollectionAccount?> findById(String id) async {
    final cached = _accounts[id];
    if (cached != null) return cached;
    final account = _mapAccount(
      await _billing.getCollectorAccount(lookupValue: id),
    );
    if (account != null) {
      _cacheAccount(account);
      _notify();
    }
    return account;
  }

  @override
  Future<CollectionReceipt> collect({
    required String accountId,
    required CollectionInvoice invoice,
    required double amount,
    required PaymentMethod method,
  }) async {
    if (method != PaymentMethod.cash) {
      throw StateError('التحصيل الميداني في هذه المرحلة نقدي فقط.');
    }
    final account = _accounts[accountId] ?? await findById(accountId);
    if (account == null) throw StateError('الحساب غير موجود أو خارج مسارك.');

    final pendingKey = _pendingKey(
      accountId: accountId,
      invoiceId: invoice.invoiceId,
      amount: amount,
    );
    // Persist before sending. If the connection times out after the server
    // posts the payment, the next attempt reuses this exact key and receives
    // the original receipt instead of creating a second collection.
    final requestKey = await _storage.read(key: pendingKey) ??
        'MC-${DateTime.now().microsecondsSinceEpoch}-$accountId';
    await _storage.write(key: pendingKey, value: requestKey);
    final result = await _billing.collectCash(
      orderId: invoice.orderId,
      invoiceId: invoice.invoiceId,
      amount: amount,
      idempotencyKey: requestKey,
    );
    await _storage.delete(key: pendingKey);
    final receipt = CollectionReceipt(
      reference: result['reference'] as String? ?? requestKey,
      displayName: result['payment_reference'] as String? ?? '',
      account: account,
      amount: (result['amount'] as num?)?.toDouble() ?? amount,
      method: PaymentMethod.cash,
      paidAt: DateTime.tryParse(result['paid_at'] as String? ?? '') ??
          DateTime.now(),
    );
    _receipts.insert(0, receipt);
    return receipt;
  }

  String _pendingKey({
    required String accountId,
    required int invoiceId,
    required double amount,
  }) => 'collection.pending.$accountId.$invoiceId.${amount.toStringAsFixed(2)}';

  CollectionAccount? _mapAccount(Map<String, dynamic> result) {
    final raw = result['account'];
    if (raw is! Map) return null;
    final account = Map<String, dynamic>.from(raw);
    final customerId = (account['customer_id'] as num?)?.toInt();
    if (customerId == null) return null;
    final bills = (account['bills'] as List? ?? const [])
        .whereType<Map>()
        .map((value) {
      final bill = Map<String, dynamic>.from(value);
      final residual = (bill['amount_residual'] as num?)?.toDouble() ?? 0;
      final total = (bill['amount'] as num?)?.toDouble() ?? 0;
      final isOverdue = bill['overdue'] == true;
      final InvoiceStatus status;
      if (residual <= 0) {
        status = InvoiceStatus.paid;
      } else if (isOverdue) {
        status = InvoiceStatus.overdue;
      } else if (total > 0 && residual < total) {
        status = InvoiceStatus.partiallyPaid;
      } else {
        status = InvoiceStatus.unpaid;
      }
      return CollectionInvoice(
        orderId: (bill['order_id'] as num).toInt(),
        invoiceId: (bill['invoice_id'] as num).toInt(),
        id: '${bill['invoice_id']}',
        invoiceNumber: bill['invoice_number'] as String? ??
            bill['bill_number'] as String? ??
            '—',
        dueDate: DateTime.tryParse(bill['due_date'] as String? ?? '') ??
            DateTime.now(),
        amount: total,
        amountResidual: residual,
        status: status,
      );

    }).toList(growable: false);
    final customer = Customer(
      remoteId: customerId,
      customerNumber: account['customer_number'] as String? ?? '$customerId',
      accountNumber: account['account_number'] as String? ??
          account['customer_number'] as String? ??
          '$customerId',
      name: account['customer_name'] as String? ?? '—',
    );
    final meter = Meter(
      remoteId: (account['meter_id'] as num?)?.toInt() ?? 0,
      meterNumber: account['meter_number'] as String? ?? '—',
      customerRemoteId: customerId,
      paymentType: MeterPaymentType.postpaid,
      connectionStatus: account['connection_status'] as String? ?? 'connected',
    );
    return CollectionAccount(
      id: customer.customerNumber,
      customer: customer,
      meter: meter,
      balance: (account['accounting_balance'] as num?)?.toDouble() ?? 0,
      debtAmount: (account['debt_amount'] as num?)?.toDouble() ?? 0,
      currentBill: (account['current_bill'] as num?)?.toDouble() ?? 0,
      dueAmount: (account['due_amount'] as num?)?.toDouble() ?? 0,
      allowPartial: account['allow_partial'] != false,
      message: '',
      qrPayload: account['external_qr_reference'] as String? ?? '',
      invoices: bills,
    );
  }

  List<CollectionAccount> _mapPeriodInvoiceAccounts(Map<String, dynamic> result) {
    final rows = (result['invoices'] as List? ?? const []).whereType<Map>();
    final grouped = <String, List<Map<String, dynamic>>>{};
    for (final row in rows) {
      final item = Map<String, dynamic>.from(row);
      final key = item['customer_number']?.toString() ??
          item['customer_id']?.toString() ??
          '';
      if (key.isEmpty) continue;
      grouped.putIfAbsent(key, () => <Map<String, dynamic>>[]).add(item);
    }

    return grouped.entries.map((entry) {
      final first = entry.value.first;
      final customerId = (first['customer_id'] as num?)?.toInt() ?? 0;
      final invoices = entry.value.map((bill) {
        final residual = (bill['amount_residual'] as num?)?.toDouble() ?? 0;
        final total = (bill['amount'] as num?)?.toDouble() ?? 0;
        final isOverdue = bill['overdue'] == true;
        final InvoiceStatus status;
        if (residual <= 0) {
          status = InvoiceStatus.paid;
        } else if (isOverdue) {
          status = InvoiceStatus.overdue;
        } else if (total > 0 && residual < total) {
          status = InvoiceStatus.partiallyPaid;
        } else {
          status = InvoiceStatus.unpaid;
        }
        return CollectionInvoice(
          orderId: (bill['order_id'] as num?)?.toInt() ?? 0,
          invoiceId: (bill['invoice_id'] as num).toInt(),
          id: '${bill['invoice_id']}',
          invoiceNumber: bill['invoice_number']?.toString() ?? '—',
          dueDate: DateTime.tryParse(bill['due_date']?.toString() ?? '') ??
              DateTime.now(),
          amount: total,
          amountResidual: residual,
          status: status,
        );
      }).toList(growable: false);

      final customer = Customer(
        remoteId: customerId,
        customerNumber: first['customer_number']?.toString() ?? '$customerId',
        accountNumber: first['account_number']?.toString() ??
            first['customer_number']?.toString() ??
            '$customerId',
        name: first['customer_name']?.toString() ?? '—',
      );
      final meter = Meter(
        remoteId: (first['meter_id'] as num?)?.toInt() ?? 0,
        meterNumber: first['meter_number']?.toString() ?? '—',
        customerRemoteId: customerId,
        paymentType: MeterPaymentType.postpaid,
        connectionStatus: 'connected',
      );
      final dueAmount = invoices
          .where((item) => item.status != InvoiceStatus.paid)
          .fold<double>(0, (sum, item) => sum + item.amountResidual);
      return CollectionAccount(
        id: customer.customerNumber,
        customer: customer,
        meter: meter,
        balance: 0,
        debtAmount: 0,
        currentBill: invoices.isEmpty ? 0 : invoices.first.amountResidual,
        dueAmount: dueAmount,
        allowPartial: true,
        message: '',
        qrPayload: '',
        invoices: invoices,
      );
    }).toList(growable: false);
  }

  @override
  Future<CollectorReport> collectorReport({
    String? customerName,
    String? customerNumber,
    DateTime? dateFrom,
    DateTime? dateTo,
  }) async {
    final result = await _billing.getCollectorReport(
      customerName: customerName,
      customerNumber: customerNumber,
      dateFrom: dateFrom == null ? null : _dateOnly(dateFrom),
      dateTo: dateTo == null ? null : _dateOnly(dateTo),
    );
    final transactions = (result['transactions'] as List? ?? const [])
        .whereType<Map>()
        .map((row) {
      final item = Map<String, dynamic>.from(row);
      return CollectorReportTransaction(
        receiptNumber: item['receipt_number']?.toString() ?? '',
        customerName: item['customer_name']?.toString() ?? '',
        customerNumber: item['customer_number']?.toString() ?? '',
        amount: (item['amount'] as num?)?.toDouble() ?? 0,
        date: DateTime.tryParse(item['date']?.toString() ?? ''),
      );
    }).toList(growable: false);
    return CollectorReport(
      totalAmount: (result['total_amount'] as num?)?.toDouble() ?? 0,
      totalCount: (result['total_count'] as num?)?.toInt() ??
          transactions.length,
      transactions: transactions,
    );
  }

  String _dateOnly(DateTime date) =>
      '${date.year.toString().padLeft(4, '0')}-'
      '${date.month.toString().padLeft(2, '0')}-'
      '${date.day.toString().padLeft(2, '0')}';

  @override
  CollectorDailySummary dailySummary() => CollectorDailySummary(
        collectedAmount: _receipts.fold(0, (sum, item) => sum + item.amount),
        operationCount: _receipts.length,
        pendingAccounts: 0,
      );

  @override
  List<CollectionReceipt> receipts() => List.unmodifiable(_receipts);

  @override
  void dispose() {
    if (!_changeHub.isClosed) _changeHub.close();
  }
}
