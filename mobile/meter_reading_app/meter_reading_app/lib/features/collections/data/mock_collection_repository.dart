import 'dart:async';

import '../../customers/domain/entities.dart';
import '../domain/collection_models.dart';

abstract class CollectionRepository {
  Stream<List<CollectionAccount>> watchAccounts({String? query});
  Future<CollectionAccount?> resolveQr(String payload);
  Future<CollectionAccount?> findById(String id);
  Future<CollectionReceipt> collect({
    required String accountId,
    required double amount,
    required PaymentMethod method,
  });
  CollectorDailySummary dailySummary();
  List<CollectionReceipt> receipts();
  void dispose();
}

class MockCollectionRepository implements CollectionRepository {
  final _accountsController =
      StreamController<List<CollectionAccount>>.broadcast();
  final List<CollectionReceipt> _receipts = [];
  late List<CollectionAccount> _accounts;

  MockCollectionRepository() {
    _accounts = List.unmodifiable(_mockAccounts());
  }

  @override
  Stream<List<CollectionAccount>> watchAccounts({String? query}) {
    return Stream<List<CollectionAccount>>.multi((controller) {
      controller.add(_filtered(query));
      final sub = _accountsController.stream
          .listen((_) => controller.add(_filtered(query)));
      controller.onCancel = sub.cancel;
    });
  }

  List<CollectionAccount> _filtered(String? query) {
    if (query == null || query.trim().isEmpty) return _accounts;
    final q = query.trim().toLowerCase();
    return _accounts
        .where(
          (account) =>
              account.customer.name.toLowerCase().contains(q) ||
              account.customer.customerNumber.toLowerCase().contains(q) ||
              account.customer.accountNumber.toLowerCase().contains(q) ||
              account.meter.meterNumber.toLowerCase().contains(q),
        )
        .toList();
  }

  @override
  Future<CollectionAccount?> resolveQr(String payload) async {
    await Future.delayed(const Duration(milliseconds: 450));
    try {
      return _accounts.firstWhere((account) => account.qrPayload == payload);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<CollectionAccount?> findById(String id) async {
    try {
      return _accounts.firstWhere((account) => account.id == id);
    } catch (_) {
      return null;
    }
  }

  @override
  Future<CollectionReceipt> collect({
    required String accountId,
    required double amount,
    required PaymentMethod method,
  }) async {
    final account = await findById(accountId);
    if (account == null) throw StateError('الحساب غير موجود');
    await Future.delayed(const Duration(milliseconds: 300));
    final receipt = CollectionReceipt(
      reference:
          'RCT-${DateTime.now().millisecondsSinceEpoch.toString().substring(7)}',
      account: account,
      amount: amount,
      method: method,
      paidAt: DateTime.now(),
    );
    _receipts.insert(0, receipt);
    _accountsController.add(_accounts);
    return receipt;
  }

  @override
  CollectorDailySummary dailySummary() {
    final collected =
        _receipts.fold<double>(0, (total, receipt) => total + receipt.amount);
    return CollectorDailySummary(
      collectedAmount: collected + 18400, // مبلغ أساسي بالريال اليمني
      operationCount: _receipts.length + 7,
      pendingAccounts:
          _accounts.where((account) => account.dueTotal > 0).length,
    );
  }

  @override
  List<CollectionReceipt> receipts() => List.unmodifiable(_receipts);

  List<CollectionAccount> _mockAccounts() {
    // ── بيانات تجريبية يمنية ─────────────────────────────────────────────
    final names = [
      'محمد أحمد علي',
      'عبدالله حسن الشرعبي',
      'خالد عبدالكريم السامعي',
      'يحيى صالح الأنسي',
      'أحمد علي الحميري',
    ];
    final addresses = [
      'حي السنينة، شارع الستين',
      'حي شميلة، شارع جمال',
      'حي الأصبحي، شارع النصر',
      'حي التحرير، شارع الزبيري',
      'حي الجراف، شارع السبعين',
    ];
    final regions = ['صنعاء', 'صنعاء', 'صنعاء', 'صنعاء', 'صنعاء'];
    final areas = ['معين', 'السبعين', 'الثورة', 'التحرير', 'آزال'];
    final phones = [
      '770123456', '771654321', '733555222', '775888999', '777345678',
    ];

    return List.generate(names.length, (i) {
      final customer = Customer(
        remoteId: 3000 + i,
        customerNumber: 'YEM-${810000 + i}',   // ← required
        accountNumber: 'ACC-${220000 + i}',
        name: names[i],
        mobile: phones[i],
        address: addresses[i],
        regionName: regions[i],
        areaName: areas[i],
        lastReadingDate: DateTime.now().subtract(Duration(days: 28 + i)),
        lastReadingValue: (1800 + i * 310).toDouble(),
      );
      final meter = Meter(
        remoteId: 4100 + i,
        meterNumber: '${100001 + i}',           // عدادات كهرباء يمنية
        serialNumber: 'YE${77000 + i}',
        customerRemoteId: customer.remoteId,
        paymentType: MeterPaymentType.postpaid,
        meterType: i == 2 ? 'Three Phase' : 'Single Phase',
        connectionStatus: i == 3 ? 'disconnected' : 'connected',
      );
      // فواتير كهرباء بالريال اليمني (YER)
      final invoices = [
        CollectionInvoice(
          id: 'inv-$i-1',
          invoiceNumber: 'INV-${20260700 + i}',
          dueDate: DateTime.now().subtract(Duration(days: 8 + i)),
          amount: (2150 + (i * 350)).toDouble(),
          status: i == 1 ? InvoiceStatus.paid : InvoiceStatus.overdue,
        ),
        CollectionInvoice(
          id: 'inv-$i-2',
          invoiceNumber: 'INV-${20260600 + i}',
          dueDate: DateTime.now().add(Duration(days: 5 + i)),
          amount: (1650 + (i * 280)).toDouble(),
          status: InvoiceStatus.unpaid,
        ),
      ];
      return CollectionAccount(
        id: 'collection-$i',
        customer: customer,
        meter: meter,
        balance: i == 1 ? 420 : -180,
        debtAmount: invoices
            .where((inv) => inv.status != InvoiceStatus.paid)
            .fold<double>(0, (total, inv) => total + inv.amount),
        qrPayload: 'UTILITY:${customer.accountNumber}',
        invoices: invoices,
      );
    });
  }

  @override
  void dispose() {
    _accountsController.close();
  }
}
