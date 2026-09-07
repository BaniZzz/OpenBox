import 'package:bossip_mobile/features/chat/state/chat_session_controller.dart';
import 'package:bossip_mobile/features/chat/state/config_providers.dart';
import 'package:bossip_mobile/features/chat/utils/reasoning.dart';
import 'package:bossip_mobile/features/chat/widgets/composer/picker_sheets.dart';
import 'package:bossip_mobile/shared/appearance/tokens.dart';
import 'package:bossip_mobile/shared/i18n/i18n.dart';
import 'package:bossip_mobile/shared/models/app_config.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

I18nBundle _bundle() => I18nBundle({
  'en-US': {
    'chat': {
      'model': {'pick': 'Switch model'},
      'reasoning': {
        'default': 'Default',
        'defaultWithLevel': 'Default ({{level}})',
        'level': {'low': 'Low', 'high': 'High'},
      },
    },
  },
});

const _reasoningModelId = 'openai/gpt-5';
const _plainModelId = 'plain';

const _reasoningModel = ModelInfo(
  id: _reasoningModelId,
  name: 'GPT-5',
  provider: 'OpenAI',
  variants: ['low', 'high'],
  defaultVariant: 'low',
);
const _plainModel = ModelInfo(
  id: _plainModelId,
  name: 'Plain',
  provider: 'Local',
);
const _config = AppConfig(
  models: [_reasoningModel, _plainModel],
  defaultModel: _reasoningModelId,
);

Future<ProviderContainer> _open(
  WidgetTester tester, {
  String? currentModel = _reasoningModelId,
  String? currentVariant = 'high',
}) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  late ProviderContainer container;

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        i18nProvider.overrideWith(() => I18nController(_bundle(), prefs)),
        appConfigProvider.overrideWith((ref) => _config),
      ],
      child: MaterialApp(
        theme: ThemeData(
          extensions: [
            BossipTokens.resolve(BossipThemeName.default_, Brightness.light),
          ],
        ),
        home: Consumer(
          builder: (context, ref, _) {
            container = ProviderScope.containerOf(context);
            return Scaffold(
              body: Center(
                child: ElevatedButton(
                  onPressed: () => showModelPicker(
                    context,
                    ref,
                    sessionKey: 's1',
                    currentModel: currentModel,
                    currentVariant: currentVariant,
                  ),
                  child: const Text('open'),
                ),
              ),
            );
          },
        ),
      ),
    ),
  );
  await tester.pumpAndSettle();
  await tester.tap(find.text('open'));
  await tester.pumpAndSettle();
  return container;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('reasoning models advertise their second step and active level', (
    tester,
  ) async {
    await _open(tester);

    final activeRow = find.ancestor(
      of: find.text('GPT-5'),
      matching: find.byType(ListTile),
    );
    expect(
      find.descendant(of: activeRow, matching: find.text('High')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: activeRow, matching: find.byIcon(Icons.check)),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: activeRow,
        matching: find.byIcon(Icons.chevron_right),
      ),
      findsOneWidget,
    );

    final plainRow = find.ancestor(
      of: find.text('Plain'),
      matching: find.byType(ListTile),
    );
    expect(
      find.descendant(of: plainRow, matching: find.byIcon(Icons.chevron_right)),
      findsNothing,
    );
  });

  testWidgets('a reasoning level commits the model and level as a pair', (
    tester,
  ) async {
    final container = await _open(
      tester,
      currentModel: _plainModel.id,
      currentVariant: null,
    );

    await tester.tap(find.text('GPT-5'));
    await tester.pumpAndSettle();

    expect(find.text('Default (Low)'), findsOneWidget);
    expect(find.text('Low'), findsOneWidget);
    expect(find.text('High'), findsOneWidget);
    expect(
      container.read(pickedModelProvider('s1')),
      isNull,
      reason: 'opening the second sheet must not partially change the pair',
    );

    await tester.tap(find.text('High'));
    await tester.pumpAndSettle();

    expect(container.read(pickedModelProvider('s1')), _reasoningModel.id);
    expect(
      container.read(
        pickedVariantProvider(reasoningKey('s1', _reasoningModel.id)),
      ),
      const Variant('high'),
    );
  });

  testWidgets('dismissing the reasoning step changes neither selection', (
    tester,
  ) async {
    final container = await _open(
      tester,
      currentModel: _plainModel.id,
      currentVariant: null,
    );

    await tester.tap(find.text('GPT-5'));
    await tester.pumpAndSettle();
    await tester.tapAt(const Offset(10, 10));
    await tester.pumpAndSettle();

    expect(container.read(pickedModelProvider('s1')), isNull);
    expect(
      container.read(
        pickedVariantProvider(reasoningKey('s1', _reasoningModel.id)),
      ),
      isNull,
    );
  });

  testWidgets('a model without reasoning levels is selected immediately', (
    tester,
  ) async {
    final container = await _open(tester);

    await tester.tap(find.text('Plain'));
    await tester.pumpAndSettle();

    expect(find.text('Plain'), findsNothing, reason: 'the picker closed');
    expect(container.read(pickedModelProvider('s1')), _plainModel.id);
  });
}
