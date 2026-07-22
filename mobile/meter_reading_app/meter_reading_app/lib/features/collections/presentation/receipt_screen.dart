import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/providers.dart';
import '../../../core/printing/collection_receipt_builder.dart';
import '../../../core/printing/thermal_printer_service.dart';
import '../domain/collection_models.dart';
import 'thermal_printer_picker_sheet.dart';

class ReceiptScreen extends ConsumerStatefulWidget {
  final CollectionReceipt receipt;

  const ReceiptScreen({super.key, required this.receipt});

  @override
  ConsumerState<ReceiptScreen> createState() => _ReceiptScreenState();
}

class _ReceiptScreenState extends ConsumerState<ReceiptScreen> {
  bool _printing = false;
  ThermalPrinterDevice? _connectedPrinter;

  @override
  void initState() {
    super.initState();
    _loadSavedPrinter();
  }

  Future<void> _loadSavedPrinter() async {
    final saved =
        await ref.read(thermalPrinterServiceProvider).savedDevice();
    if (mounted && saved != null) {
      setState(() => _connectedPrinter = saved);
    }
  }

  Future<void> _printReceipt() async {
    if (_printing) return;

    setState(() => _printing = true);
    final printer = ref.read(thermalPrinterServiceProvider);
    final messenger = ScaffoldMessenger.of(context);

    try {
      var device = await printer.ensureConnected(device: _connectedPrinter);
      device ??= await showThermalPrinterPickerSheet(
        context,
        printerService: printer,
        selected: _connectedPrinter,
      );

      if (device == null) {
        return;
      }

      device = await printer.ensureConnected(device: device);
      if (device == null) {
        throw const ThermalPrinterException('تعذر الاتصال بالطابعة');
      }

      final bytes = await CollectionReceiptBuilder.build(widget.receipt);
      await printer.printBytes(bytes);

      if (mounted) {
        setState(() => _connectedPrinter = device);
        messenger.showSnackBar(
          SnackBar(content: Text('تمت الطباعة على ${device.name}')),
        );
      }
    } on ThermalPrinterException catch (error) {
      messenger.showSnackBar(SnackBar(content: Text(error.message)));
    } catch (error) {
      messenger.showSnackBar(
        SnackBar(content: Text('فشلت الطباعة: $error')),
      );
    } finally {
      if (mounted) {
        setState(() => _printing = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final receipt = widget.receipt;

    return Scaffold(
      appBar: AppBar(title: const Text('إيصال التحصيل')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(Icons.verified_rounded,
                      size: 56, color: Theme.of(context).colorScheme.primary),
                  const SizedBox(height: 12),
                  Text('تم تسجيل التحصيل',
                      textAlign: TextAlign.center,
                      style: Theme.of(context).textTheme.titleLarge),
                  const SizedBox(height: 20),
                  _InfoRow(label: 'المرجع', value: receipt.reference),
                  _InfoRow(
                      label: 'المشترك', value: receipt.account.customer.name),
                  _InfoRow(
                      label: 'رقم الحساب',
                      value: receipt.account.customer.accountNumber),
                  _InfoRow(
                      label: 'رقم العداد',
                      value: receipt.account.meter.meterNumber),
                  _InfoRow(
                      label: 'المبلغ',
                      value: '${receipt.amount.toStringAsFixed(0)} ﷼'),
                  _InfoRow(
                      label: 'طريقة الدفع',
                      value: _methodLabel(receipt.method)),
                  _InfoRow(label: 'التاريخ', value: _dateTime(receipt.paidAt)),
                ],
              ),
            ),
          ),
          if (_connectedPrinter != null) ...[
            const SizedBox(height: 12),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.print_outlined),
              title: const Text('الطابعة المحفوظة'),
              subtitle: Text(_connectedPrinter!.name),
              trailing: TextButton(
                onPressed: _printing
                    ? null
                    : () async {
                        final device = await showThermalPrinterPickerSheet(
                          context,
                          printerService:
                              ref.read(thermalPrinterServiceProvider),
                          selected: _connectedPrinter,
                        );
                        if (device != null && mounted) {
                          setState(() => _connectedPrinter = device);
                          await ref
                              .read(thermalPrinterServiceProvider)
                              .saveDevice(device);
                        }
                      },
                child: const Text('تغيير'),
              ),
            ),
          ],
          const SizedBox(height: 16),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _printing ? null : _printReceipt,
                  icon: _printing
                      ? const SizedBox(
                          width: 18,
                          height: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : const Icon(Icons.print_outlined),
                  label: Text(_printing ? 'جاري الطباعة...' : 'طباعة'),
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: () {},
                  icon: const Icon(Icons.sms_outlined),
                  label: const Text('إرسال'),
                ),
              ),
            ],
          ),
          if (receipt.method == PaymentMethod.cash) ...[
            const SizedBox(height: 8),
            Text(
              'للتحصيل النقدي: اطبع الإيصال على الطابعة الحرارية وسلّمه للمشترك.',
              textAlign: TextAlign.center,
              style: Theme.of(context)
                  .textTheme
                  .bodySmall
                  ?.copyWith(color: Theme.of(context).colorScheme.outline),
            ),
          ],
          const SizedBox(height: 12),
          FilledButton.icon(
            onPressed: () => context.go('/collector'),
            icon: const Icon(Icons.home_outlined),
            label: const Text('العودة للرئيسية'),
          ),
        ],
      ),
    );
  }

  String _methodLabel(PaymentMethod method) => switch (method) {
        PaymentMethod.cash => 'نقدي',
        PaymentMethod.card => 'شبكة',
        PaymentMethod.wallet => 'محفظة',
        PaymentMethod.transfer => 'تحويل',
      };

  String _dateTime(DateTime value) =>
      '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')} '
      '${value.hour.toString().padLeft(2, '0')}:${value.minute.toString().padLeft(2, '0')}';
}

class _InfoRow extends StatelessWidget {
  final String label;
  final String value;

  const _InfoRow({required this.label, required this.value});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label,
              style: TextStyle(color: Theme.of(context).colorScheme.outline)),
          Flexible(
            child: Text(value,
                textAlign: TextAlign.end,
                style: const TextStyle(fontWeight: FontWeight.w800)),
          ),
        ],
      ),
    );
  }
}
