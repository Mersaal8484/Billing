import '../../../core/network/billing_api_service.dart';
import '../../customers/domain/entities.dart';
import '../domain/collection_models.dart';

/// Source of truth for field collections.  It never fabricates an account,
/// payment or receipt: a receipt is kept locally only after Odoo confirms the
/// posted payment, exact allocation and collector custody record.
class OdooCollectionRepository implements CollectionRepository {
  OdooCollectionRepository(this._billing);

  final BillingApiService _billing;
  final List<CollectionReceipt> _receipts = [];
  final Map<String, CollectionAccount> _accounts = {};

  @override
  Stream<List<CollectionAccount>> watchAccounts({String? query}) async* {
    final value = query?.trim() ?? '';
    if (value.isEmpty) {
      yield const [];
      return;
    }
    final account = await findById(value);
    yield account == null ? const [] : [account];
  }

  @override
  Future<CollectionAccount?> resolveQr(String payload) async {
    return _mapAccount(await _billing.getCollectorAccount(qrReference: payload));
  }

  @override
  Future<CollectionAccount?> findById(String id) async {
    final account = _mapAccount(
      await _billing.getCollectorAccount(customerNumber: id),
    );
    if (account != null) {
      _accounts[id] = account;
      _accounts[account.id] = account;
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

    final requestKey = 'MC-${DateTime.now().microsecondsSinceEpoch}-$accountId';
    final result = await _billing.collectCash(
      orderId: invoice.orderId,
      invoiceId: invoice.invoiceId,
      amount: amount,
      idempotencyKey: requestKey,
    );
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
      return CollectionInvoice(
        orderId: (bill['order_id'] as num).toInt(),
        invoiceId: (bill['invoice_id'] as num).toInt(),
        id: '${bill['invoice_id']}',
        invoiceNumber: bill['invoice_number'] as String? ??
            bill['bill_number'] as String? ??
            '—',
        dueDate: DateTime.tryParse(bill['due_date'] as String? ?? '') ??
            DateTime.now(),
        amount: (bill['amount'] as num?)?.toDouble() ?? 0,
        amountResidual: (bill['amount_residual'] as num?)?.toDouble() ?? 0,
        status: bill['overdue'] == true
            ? InvoiceStatus.overdue
            : InvoiceStatus.unpaid,
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

  @override
  CollectorDailySummary dailySummary() => CollectorDailySummary(
        collectedAmount: _receipts.fold(0, (sum, item) => sum + item.amount),
        operationCount: _receipts.length,
        pendingAccounts: 0,
      );

  @override
  List<CollectionReceipt> receipts() => List.unmodifiable(_receipts);

  @override
  void dispose() {}
}
