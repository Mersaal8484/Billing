import 'dart:async';
import '../domain/collection_models.dart';
import '../../customers/domain/entities.dart';

class MockCollectionRepository implements CollectionRepository {
  final _ctrl = StreamController<List<CollectionAccount>>.broadcast();
  final List<CollectionReceipt> _receipts = [];
  late List<CollectionAccount> _accounts;

  MockCollectionRepository() {
    _accounts = List.unmodifiable(_mockAccounts());
  }

  @override
  Stream<List<CollectionAccount>> watchAccounts({String? query}) {
    return Stream<List<CollectionAccount>>.multi((controller) {
      controller.add(_filtered(query));
      final sub = _ctrl.stream.listen((_) => controller.add(_filtered(query)));
      controller.onCancel = sub.cancel;
    });
  }

  List<CollectionAccount> _filtered(String? query) {
    if (query == null || query.trim().isEmpty) return _accounts;
    final q = query.trim().toLowerCase();
    return _accounts.where((a) =>
      a.customer.name.toLowerCase().contains(q) ||
      a.customer.accountNumber.toLowerCase().contains(q) ||
      a.meter.meterNumber.toLowerCase().contains(q),
    ).toList();
  }

  @override
  Future<CollectionAccount?> resolveQr(String payload) async {
    await Future.delayed(const Duration(milliseconds: 300));
    try { return _accounts.firstWhere((a) => a.qrPayload == payload); }
    catch (_) { return null; }
  }

  @override
  Future<CollectionAccount?> findById(String id) async {
    try { return _accounts.firstWhere((a) => a.id == id); }
    catch (_) { return null; }
  }

  @override
  Future<CollectionReceipt> collect({
    required String accountId,
    required CollectionInvoice invoice,
    required double amount,
    required PaymentMethod method,
  }) async {
    final account = await findById(accountId);
    if (account == null) throw StateError('الحساب غير موجود');
    await Future.delayed(const Duration(milliseconds: 300));
    final receipt = CollectionReceipt(
      reference: 'RCT-${DateTime.now().millisecondsSinceEpoch.toString().substring(7)}',
      account: account,
      amount: amount,
      method: method,
      paidAt: DateTime.now(),
    );
    _receipts.insert(0, receipt);
    _ctrl.add(_accounts);
    return receipt;
  }

  @override
  CollectorDailySummary dailySummary() {
    final collected = _receipts.fold<double>(0, (t, r) => t + r.amount);
    return CollectorDailySummary(
      collectedAmount: collected + 18400,
      operationCount: _receipts.length + 7,
      pendingAccounts: _accounts.where((a) => a.dueTotal > 0).length,
    );
  }

  @override
  List<CollectionReceipt> receipts() => List.unmodifiable(_receipts);

  @override
  void dispose() => _ctrl.close();

  List<CollectionAccount> _mockAccounts() {
    final names = ['محمد أحمد علي','عبدالله حسن الشرعبي','خالد عبدالكريم السامعي','يحيى صالح الأنسي','أحمد علي الحميري'];
    final areas = ['معين','السبعين','الثورة','التحرير','آزال'];
    return List.generate(names.length, (i) {
      final customer = Customer(
        remoteId: 3000 + i,
        customerNumber: 'YEM-${810000 + i}',
        accountNumber: 'ACC-${200000 + i}',
        name: names[i],
        address: 'حي ${areas[i]}، صنعاء',
        regionName: 'صنعاء',
        areaName: areas[i],
        mobile: '77012345$i',
      );
      final meter = Meter(
        remoteId: 4000 + i,
        meterNumber: '${200000 + i}',
        customerRemoteId: 3000 + i,
        paymentType: MeterPaymentType.postpaid,
      );
      final invoices = [
        CollectionInvoice(
          orderId: 10000 + i,
          invoiceId: 20000 + i,
          id: 'inv-$i-1',
          invoiceNumber: 'INV-${20260700 + i}',
          dueDate: DateTime.now().subtract(Duration(days: 8 + i)),
          amount: (2150 + i * 350).toDouble(),
          status: i == 1 ? InvoiceStatus.paid : InvoiceStatus.overdue,
        ),
        CollectionInvoice(
          orderId: 11000 + i,
          invoiceId: 21000 + i,
          id: 'inv-$i-2',
          invoiceNumber: 'INV-${20260600 + i}',
          dueDate: DateTime.now().add(Duration(days: 5 + i)),
          amount: (1650 + i * 280).toDouble(),
          status: InvoiceStatus.unpaid,
        ),
      ];
      return CollectionAccount(
        id: 'collection-$i',
        customer: customer,
        meter: meter,
        balance: i == 1 ? 420 : -180,
        debtAmount: invoices.where((inv) => inv.status != InvoiceStatus.paid).fold<double>(0, (t, inv) => t + inv.amount),
        qrPayload: 'UTILITY:${customer.accountNumber}',
        invoices: invoices,
      );
    });
  }
}
