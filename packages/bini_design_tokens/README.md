# bini_design_tokens

PRD-442 全域三端设计 Token 包（Flutter 端）。

## 引用方式（Monorepo path）

```yaml
dependencies:
  bini_design_tokens:
    path: ../packages/bini_design_tokens
```

## 用法

```dart
import 'package:bini_design_tokens/bini_design_tokens.dart';

MaterialApp(
  theme: BhTheme.lightTheme(),
  home: Scaffold(
    body: Container(color: BhTokens.colorBrand400),
  ),
);

// 图标
BhIcon(name: 'health-report', size: 24, color: BhTokens.colorBrand600);
```

## 升级路径（Path → Git）

如需多仓库化，仅需把本目录 `packages/bini_design_tokens` 抽出建立 Git 仓库，把 `pubspec.yaml` 的 `path:` 改为 `git: url:` 即可，改造成本 < 30 分钟。

## 自动生成文件

以下文件由 `scripts/gen-tokens.mjs` / `scripts/gen-icons.mjs` 自动生成，**禁止手动修改**：

- `lib/src/tokens.g.dart`
- `lib/src/icons.g.dart`

执行命令：

```bash
node scripts/gen-tokens.mjs
node scripts/gen-icons.mjs
```
