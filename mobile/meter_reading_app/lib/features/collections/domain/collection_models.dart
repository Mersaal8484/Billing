import '../../customers/domain/entities.dart';

enum InvoiceStatus { unpaid, overdue, paid }
enum PaymentMethod { cash, card, wallet, transfer }

class CollectionInvoice {
  final int orderId;
  final int invoiceId;
  final String id;
  final String invoiceNumber;
  final DateTime dueDate;
  final double amount;
  final double amountResidual;
  final InvoiceStatus status;
  const CollectionInvoice({
    required this.orderId,
    required this.invoiceId,
    required this.id,
    required this.invoiceNumber,
    required this.dueDate,
    required this.amount,
    this.amountResidual = 0,
    required this.status,
  });
}

class CollectionAccount {
  final String id;
  final Customer customer;
  final Meter meter;
  final double balance;
  final double debtAmount;
  final double currentBill;
  final double dueAmount;
  final bool allowPartial;
  final String message;
  final String qrPayload;
  final List<CollectionInvoice> invoices;
  const CollectionAccount({
    required this.id,
    required this.customer,
    required this.meter,
    required this.balance,
    required this.debtAmount,
    this.currentBill = 0,
    this.dueAmount = 0,
    this.allowPartial = true,
    this.message = '',
    required this.qrPayload,
    required this.invoices,
  });
  double get dueTotal => dueAmount > 0
      ? dueAmount
      : invoices
          .where((i) => i.status != InvoiceStatus.paid)
          .fold<double>(0, (t, i) => t + i.amountResidual);
}

class CollectionReceipt {
  final String reference;
  final String displayName;
  final CollectionAccount account;
  final double amount;
  final PaymentMethod method;
  final DateTime paidAt;
  const CollectionReceipt({
    required this.reference,
    this.displayName = '',
    required this.account,
    required this.amount,
    required this.method,
    required this.paidAt,
  });
}

class CollectorDailySummary {
  final double collectedAmount;
  final int operationCount;
  final int pendingAccounts;
  const CollectorDailySummary({
    required this.collectedAmount,
    required this.operationCount,
    required this.pendingAccounts,
  });
}

abstract class CollectionRepository {
  Stream<List<CollectionAccount>> watchAccounts({String? query});
  Future<CollectionAccount?> resolveQr(String payload);
  Future<CollectionAccount?> findById(String id);
  Future<CollectionReceipt> collect({
    required String accountId,
    required CollectionInvoice invoice,
    required double amount,
    required PaymentMethod method,
  });
  CollectorDailySummary dailySummary();
  List<CollectionReceipt> receipts();
  void dispose();
}
