import 'package:flutter/material.dart';

import '../../../core/printing/thermal_printer_service.dart';

Future<ThermalPrinterDevice?> showThermalPrinterPickerSheet(
  BuildContext context, {
  required ThermalPrinterService printerService,
  ThermalPrinterDevice? selected,
}) {
  return showModalBottomSheet<ThermalPrinterDevice>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (context) => _ThermalPrinterPickerSheet(
      printerService: printerService,
      selected: selected,
    ),
  );
}

class _ThermalPrinterPickerSheet extends StatefulWidget {
  final ThermalPrinterService printerService;
  final ThermalPrinterDevice? selected;

  const _ThermalPrinterPickerSheet({
    required this.printerService,
    this.selected,
  });

  @override
  State<_ThermalPrinterPickerSheet> createState() =>
      _ThermalPrinterPickerSheetState();
}

class _ThermalPrinterPickerSheetState extends State<_ThermalPrinterPickerSheet> {
  late Future<List<ThermalPrinterDevice>> _devicesFuture;

  @override
  void initState() {
    super.initState();
    _devicesFuture = widget.printerService.pairedDevices();
  }

  void _reload() {
    setState(() {
      _devicesFuture = widget.printerService.pairedDevices();
    });
  }

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('اختر الطابعة الحرارية',
                style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 8),
            Text(
              'اربط الطابعة من إعدادات Bluetooth في الجهاز، ثم اخترها من القائمة.',
              style: Theme.of(context).textTheme.bodySmall,
            ),
            const SizedBox(height: 16),
            Flexible(
              child: FutureBuilder<List<ThermalPrinterDevice>>(
                future: _devicesFuture,
                builder: (context, snapshot) {
                  if (snapshot.connectionState == ConnectionState.waiting) {
                    return const Center(child: CircularProgressIndicator());
                  }
                  if (snapshot.hasError) {
                    return Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Text('${snapshot.error}'),
                        const SizedBox(height: 12),
                        OutlinedButton.icon(
                          onPressed: _reload,
                          icon: const Icon(Icons.refresh_rounded),
                          label: const Text('إعادة المحاولة'),
                        ),
                      ],
                    );
                  }

                  final devices = snapshot.data ?? const [];
                  if (devices.isEmpty) {
                    return Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const Icon(Icons.print_disabled_outlined, size: 48),
                        const SizedBox(height: 12),
                        const Text('لا توجد طابعات Bluetooth مقترنة'),
                        const SizedBox(height: 12),
                        OutlinedButton.icon(
                          onPressed: _reload,
                          icon: const Icon(Icons.refresh_rounded),
                          label: const Text('تحديث القائمة'),
                        ),
                      ],
                    );
                  }

                  return ListView.separated(
                    shrinkWrap: true,
                    itemCount: devices.length,
                    separatorBuilder: (_, __) => const Divider(height: 1),
                    itemBuilder: (context, index) {
                      final device = devices[index];
                      final isSelected = widget.selected?.mac == device.mac;
                      return ListTile(
                        leading: const Icon(Icons.print_outlined),
                        title: Text(device.name),
                        subtitle: Text(device.mac),
                        trailing: isSelected
                            ? Icon(Icons.check_circle,
                                color: Theme.of(context).colorScheme.primary)
                            : null,
                        onTap: () => Navigator.of(context).pop(device),
                      );
                    },
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }
}
