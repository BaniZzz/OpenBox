import 'package:flutter/material.dart';

import '../../../shared/appearance/tokens.dart';
import '../../../shared/appearance/type_scale.dart';
import '../../../shared/models/billing.dart';
import '../../../shared/utils/format.dart';
import 'billing_widgets.dart';

class BillingProviderPicker extends StatelessWidget {
  const BillingProviderPicker({
    super.key,
    required this.providers,
    required this.value,
    required this.onChanged,
  });

  final List<PaymentProviderInfo> providers;
  final String? value;
  final ValueChanged<String?>? onChanged;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Container(
      height: 38,
      padding: const EdgeInsets.symmetric(horizontal: 12),
      decoration: BoxDecoration(
        color: tokens.card,
        borderRadius: BorderRadius.circular(Radii.full),
        border: Border.all(color: tokens.hair),
      ),
      child: DropdownButtonHideUnderline(
        child: DropdownButton<String>(
          value: value,
          borderRadius: BorderRadius.circular(Radii.lg),
          style: TextStyle(fontSize: FontSizes.xs, color: tokens.ink),
          items: [
            for (final provider in providers)
              DropdownMenuItem(value: provider.id, child: Text(provider.name)),
          ],
          onChanged: onChanged,
        ),
      ),
    );
  }
}

class BillingTopupCard extends StatelessWidget {
  const BillingTopupCard({
    super.key,
    required this.controller,
    required this.rules,
    required this.allowed,
    required this.canManage,
    required this.providers,
    required this.providerId,
    required this.busy,
    required this.onProviderChanged,
    required this.onPreset,
    required this.onSubmit,
  });

  final TextEditingController controller;
  final TopupRules rules;
  final bool allowed;
  final bool canManage;
  final List<PaymentProviderInfo> providers;
  final String? providerId;
  final bool busy;
  final ValueChanged<String?> onProviderChanged;
  final ValueChanged<int> onPreset;
  final VoidCallback? onSubmit;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = I18nScope.of(context);
    return BillingCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  i18n.t('billing:plans.extraCredits'),
                  style: TextStyle(
                    fontSize: FontSizes.base,
                    fontWeight: FontWeight.w500,
                    color: tokens.ink,
                  ),
                ),
              ),
              Text(
                i18n.t('billing:plans.topupRate'),
                style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
              ),
            ],
          ),
          const SizedBox(height: 14),
          if (!allowed || !canManage)
            Text(
              i18n.t(
                !canManage
                    ? 'billing:plans.managerOnly'
                    : 'billing:plans.topupRequiresPaid',
              ),
              style: TextStyle(fontSize: FontSizes.sm, color: tokens.n600),
            )
          else ...[
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final preset in rules.presetsFen)
                  ActionChip(
                    label: Text(
                      i18n.t(
                        'billing:usage.points',
                        vars: {'value': formatFen(preset)},
                      ),
                    ),
                    onPressed: busy ? null : () => onPreset(preset),
                    backgroundColor: tokens.bg,
                    side: BorderSide(color: tokens.hair),
                    shape: const StadiumBorder(),
                  ),
              ],
            ),
            const SizedBox(height: 12),
            TextField(
              controller: controller,
              enabled: !busy,
              keyboardType: const TextInputType.numberWithOptions(
                decimal: true,
              ),
              decoration: InputDecoration(
                labelText: i18n.t('billing:usage.topUpPoints'),
                prefixText: '¥ ',
              ),
            ),
            const SizedBox(height: 10),
            if (providers.isNotEmpty)
              BillingProviderPicker(
                providers: providers,
                value: providerId,
                onChanged: busy ? null : onProviderChanged,
              ),
            const SizedBox(height: 12),
            FilledButton(
              onPressed: busy ? null : onSubmit,
              style: billingPrimaryButton(tokens),
              child: Text(
                i18n.t(
                  busy ? 'billing:usage.creatingOrder' : 'billing:usage.topUp',
                ),
              ),
            ),
          ],
        ],
      ),
    );
  }
}
