import 'package:flutter/material.dart';

import '../../../shared/appearance/tokens.dart';
import '../../../shared/appearance/type_scale.dart';
import '../../../shared/i18n/i18n.dart';
import '../../../shared/utils/format.dart';

class BillingCard extends StatelessWidget {
  const BillingCard({
    super.key,
    required this.child,
    this.padding = const EdgeInsets.all(18),
    this.highlighted = false,
  });

  final Widget child;
  final EdgeInsets padding;
  final bool highlighted;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    return Container(
      padding: padding,
      decoration: BoxDecoration(
        color: tokens.card,
        borderRadius: BorderRadius.circular(Radii.xl),
        border: Border.all(color: highlighted ? tokens.ink : tokens.hair),
      ),
      child: child,
    );
  }
}

class CreditBalanceCard extends StatelessWidget {
  const CreditBalanceCard({super.key, this.balance, this.footer});

  final String? balance;
  final Widget? footer;

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
              Icon(Icons.toll_outlined, size: 17, color: tokens.n600),
              const SizedBox(width: 7),
              Expanded(
                child: Text(
                  i18n.t('billing:usage.balance'),
                  style: TextStyle(fontSize: FontSizes.sm, color: tokens.n600),
                ),
              ),
              Text(
                i18n.t(
                  'billing:usage.points',
                  vars: {'value': formatCredits(balance)},
                ),
                style: TextStyle(
                  fontSize: FontSizes.xl,
                  fontWeight: FontWeight.w500,
                  color: tokens.ink,
                ),
              ),
            ],
          ),
          if (footer != null) ...[
            const SizedBox(height: 15),
            Divider(height: 1, color: tokens.hair),
            const SizedBox(height: 13),
            footer!,
          ],
        ],
      ),
    );
  }
}

/// Access to the already-watched i18n state without turning every small leaf
/// widget into a ConsumerWidget.
class I18nScope extends InheritedWidget {
  const I18nScope({super.key, required this.state, required super.child});

  final I18nState state;

  static I18nState of(BuildContext context) {
    final scope = context.dependOnInheritedWidgetOfExactType<I18nScope>();
    assert(scope != null, 'Billing widget requires I18nScope');
    return scope!.state;
  }

  @override
  bool updateShouldNotify(I18nScope oldWidget) => oldWidget.state != state;
}

class BillingErrorBar extends StatelessWidget {
  const BillingErrorBar({
    super.key,
    required this.label,
    required this.onRetry,
  });

  final String label;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = I18nScope.of(context);
    return Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: TextStyle(fontSize: FontSizes.sm, color: tokens.danger),
          ),
        ),
        TextButton(
          onPressed: onRetry,
          child: Text(i18n.t('billing:usage.retry')),
        ),
      ],
    );
  }
}

class BillingPager extends StatelessWidget {
  const BillingPager({
    super.key,
    required this.page,
    required this.pages,
    required this.onPrevious,
    required this.onNext,
    this.busy = false,
  });

  final int page;
  final int pages;
  final VoidCallback onPrevious;
  final VoidCallback onNext;
  final bool busy;

  @override
  Widget build(BuildContext context) {
    final tokens = context.tokens;
    final i18n = I18nScope.of(context);
    final buttonStyle = OutlinedButton.styleFrom(
      foregroundColor: tokens.ink,
      side: BorderSide(color: tokens.hair),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(Radii.full),
      ),
    );
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        OutlinedButton(
          onPressed: page > 1 && !busy ? onPrevious : null,
          style: buttonStyle,
          child: Text(i18n.t('billing:usage.previous')),
        ),
        Text(
          i18n.t('billing:usage.page', vars: {'page': page, 'pages': pages}),
          style: TextStyle(fontSize: FontSizes.xs, color: tokens.n600),
        ),
        OutlinedButton(
          onPressed: page < pages && !busy ? onNext : null,
          style: buttonStyle,
          child: Text(i18n.t('billing:usage.next')),
        ),
      ],
    );
  }
}

ButtonStyle billingPrimaryButton(BossipTokens tokens) => FilledButton.styleFrom(
  backgroundColor: tokens.ink,
  foregroundColor: tokens.bg,
  minimumSize: const Size(0, 44),
  shape: RoundedRectangleBorder(
    borderRadius: BorderRadius.circular(Radii.full),
  ),
);

ButtonStyle billingSecondaryButton(BossipTokens tokens) =>
    OutlinedButton.styleFrom(
      foregroundColor: tokens.ink,
      minimumSize: const Size(0, 44),
      side: BorderSide(color: tokens.hair),
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(Radii.full),
      ),
    );
