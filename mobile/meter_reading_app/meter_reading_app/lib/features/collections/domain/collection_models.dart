import '../../customers/domain/entities.dart';

enum InvoiceStatus { unpaid, overdue, paid }

enum PaymentMethod { cash, card, wallet, transfer }

class CollectionInvoice {
  final String id;
  final String invoiceNumber;
  final DateTime dueDate;
  final double amount;
  final InvoiceStatus status;

  const CollectionInvoice({
    required this.id,
    required this.invoiceNumber,
    required this.dueDate,
    required this.amount,
    required this.status,
  });
}

class CollectionAccount {
  final String id;
  final Customer customer;
  final Meter meter;
  final double balance;
  final double debtAmount;
  final String qrPayload;
  final List<CollectionInvoice> invoices;

  const CollectionAccount({
    required this.id,
    required this.customer,
    required this.meter,
    required this.balance,
    required this.debtAmount,
    required this.qrPayload,
    required this.invoices,
  });

  double get dueTotal => invoices
      .where((invoice) => invoice.status != InvoiceStatus.paid)
      .fold<double>(0, (total, invoice) => total + invoice.amount);
}

class CollectionReceipt {
  final String reference;
  final CollectionAccount account;
  final double amount;
  final PaymentMethod method;
  final DateTime paidAt;

  const CollectionReceipt({
    required this.reference,
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
