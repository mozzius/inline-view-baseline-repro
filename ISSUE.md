# iOS: View nested in Text sits below the baseline since 0.82 (placed with 12pt Helvetica's descender)

### Description

On iOS with the New Architecture, a `View` nested in a `Text` (an inline view) is placed below the text baseline instead of on it. Android puts the bottom of the same view exactly on the baseline. This started in 0.82.0 and is still the case on `main`.

The error depends on the text around the view, and follows this formula exactly:

```text
error = |descender of the line's font| + baseline offset - 2.76
```

- **2.76** is the descender of 12pt Helvetica, the font TextKit fills in for the view's own run, because React Native never gives that run a font.
- **The baseline offset** is `(lineHeight - font.lineHeight) / 2` when a `lineHeight` taller than the font's line height is set (`RCTApplyBaselineOffset` raises the glyphs by that much), and 0 otherwise.

For 15pt system text that's 0.86pt without `lineHeight` and 3.91pt with `lineHeight: 24`; for 24pt text with `lineHeight: 36`, 6.71pt. Both terms grow with Dynamic Type: 14.15pt for that last one at the first accessibility size. The formula predicts the logged error of all 20 samples in the repro (10 layouts at two text sizes) to within 0.003pt, and the screenshots match it to the pixel.

Measured from the screenshots, as the view's bottom minus the baseline of its line, in points (positive is below):

| Sample | iOS 0.88.0 | iOS 0.88.0, Accessibility Medium | iOS 0.88.0 with the fix below | iOS 0.81.6 | Android 0.88.0 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 15 / no `lineHeight` | +0.67 | +3.67 | 0 | 0 | 0 |
| 15 / 15 | +1.00 | +3.67 | 0 | -1.00 | 0 |
| 15 / 20 | +2.00 | +5.67 | 0 | 0 | 0 |
| 15 / 24 | +4.00 | +9.00 | 0 | 0 | 0 |
| 24 / no `lineHeight` | +3.00 | +7.67 | 0 | 0 | 0 |
| 24 / 28 | +3.00 | +7.67 | 0 | 0 | 0 |
| 24 / 36 | +6.67 | +14.33 | 0 | 0 | 0 |
| The case from [#53092](https://github.com/react/react-native/issues/53092) | +0.67 | +3.33 | 0 | -4.00 | 0 |
| 15pt text with a nested 24pt word | +3.00 | +7.67 | 0 | 0 | 0 |
| Wrapped 15 / 24, view mid-paragraph | +4.00 | +9.00 | 0 | 0 | 0 |

The letters sit exactly on the baseline `onTextLayout` reports in every row of every screenshot; only the inline view is off. The repro's README has the full formula-vs-measurement tables, the logs, and the scripts that check them.

#### Cause

Links are to `main` at [f754dbd](https://github.com/react/react-native/tree/f754dbd20a8548cddfa548815a6e1f4bb25b6443). `_measureTextStorage:` places each attachment at the bottom of its glyph rect plus the descender of the font on the attachment's own run ([RCTTextLayoutManager.mm#L643-L653](https://github.com/react/react-native/blob/f754dbd20a8548cddfa548815a6e1f4bb25b6443/packages/react-native/ReactCommon/react/renderer/textlayoutmanager/platform/ios/react/renderer/textlayoutmanager/RCTTextLayoutManager.mm#L643-L653)):

```objc
UIFont *font = [[textStorage attributedSubstringFromRange:range] attribute:NSFontAttributeName
                                                                   atIndex:0
                                                            effectiveRange:nil];
frame = {
    .origin =
        {glyphRect.origin.x,
         glyphRect.origin.y + glyphRect.size.height - attachmentSize.height + font.descender},
    .size = attachmentSize};
```

The bottom of the glyph rect is the bottom of the line, so this is the baseline only if `font` is the font that sets the line's descent and the glyphs aren't raised. Neither holds:

1. **The attachment's run has no font.** `RCTNSAttributedStringFragmentFromFragment` gives an attachment fragment only `NSAttachmentAttributeName` and the event emitter ([RCTAttributedTextUtils.mm#L405-L444](https://github.com/react/react-native/blob/f754dbd20a8548cddfa548815a6e1f4bb25b6443/packages/react-native/ReactCommon/react/renderer/textlayoutmanager/platform/ios/react/renderer/textlayoutmanager/RCTAttributedTextUtils.mm#L405-L444)). `NSTextStorage` then fixes the attributes and fills in UIKit's default font (`NSFontAttributeName // UIFont, default Helvetica(Neue) 12` in `NSAttributedString.h`). Logging `font` here prints `Helvetica 12.0 (descender -2.760)` for every attachment, whatever the text's font is.
2. **A tall `lineHeight` raises the glyphs.** `RCTApplyBaselineOffset` ([RCTAttributedTextUtils.mm#L345-L403](https://github.com/react/react-native/blob/f754dbd20a8548cddfa548815a6e1f4bb25b6443/packages/react-native/ReactCommon/react/renderer/textlayoutmanager/platform/ios/react/renderer/textlayoutmanager/RCTAttributedTextUtils.mm#L345-L403)) raises them by `(lineHeight - font.lineHeight) / 2` with `NSBaselineOffsetAttributeName`. The bottom of the line plus a descender doesn't include that.
3. **The line's descent can come from another font.** With mixed font sizes on a line, the baseline sits above the line's bottom by the largest descender on it, not the descender of the view's own text.

#### Regression in 0.82.0

This formula came in with https://github.com/react/react-native/pull/53341 ([6da351a](https://github.com/react/react-native/commit/6da351a5ed80a10138a5558afcb380410c8a93c9), first in v0.82.0-rc.0), to fix https://github.com/react/react-native/issues/53092. Before that, Fabric used `glyphRect.origin.y + [layoutManager locationForGlyphAtIndex:].y` ([0.81.6](https://github.com/react/react-native/blob/cddf8a7536de12db889e35e946281cfaf327197a/packages/react-native/ReactCommon/react/renderer/textlayoutmanager/platform/ios/react/renderer/textlayoutmanager/RCTTextLayoutManager.mm#L412-L417)). The same screen on a fresh 0.81.6 app puts the view on the baseline to the pixel in 8 of the 10 rows, and all 10 at the accessibility size. It's only wrong (too high) when the view is taller than the line's ascent and `lineHeight` keeps the line from growing: the glyph rect then starts at the top of the view instead of the line. That's the case [#53092](https://github.com/react/react-native/issues/53092) reported. [#53341](https://github.com/react/react-native/pull/53341) brought it to within 0.67pt, but moved every other inline view below the baseline.

#### Fix

Place the attachment on the baseline TextKit actually laid its line out with: the line fragment's origin plus the attachment glyph's location within it. That includes the baseline offset, doesn't depend on any font, and is the baseline `onTextLayout` reports for each line. It's the 0.81 placement with the line's top in place of the glyph rect's.

```objc
NSUInteger glyphIndex = attachmentGlyphRange.location;
CGRect lineFragmentRect = [layoutManager lineFragmentRectForGlyphAtIndex:glyphIndex effectiveRange:NULL];
CGFloat baseline = lineFragmentRect.origin.y + [layoutManager locationForGlyphAtIndex:glyphIndex].y;

CGRect frame = {.origin = {glyphRect.origin.x, baseline - attachmentSize.height}, .size = attachmentSize};
```

With this, the bottom of every inline view in the repro sits exactly on the baseline (0px off at both text sizes), including the [#53092](https://github.com/react/react-native/issues/53092) case and the mixed-size line. I'm happy to open a PR with it.

#### Related

- https://github.com/react/react-native/pull/58967 (open) also fixes this, by giving the attachment's run the text's font and subtracting the baseline offset. I applied it to 0.88.0 in the repro: it puts the view on the baseline in every single-font row, but leaves the mixed-size row 2.17pt low (3.88pt at Accessibility Medium), because that line's descent comes from the larger font. Reading the baseline from TextKit avoids that.
- https://github.com/react/react-native/pull/59420 (open, behind `fixTextInlineViewLineHeight`) subtracts the baseline offset but still uses the attachment run's `font.descender`, so going by the diff the `|descender| - 2.76` part would remain (0.86pt for 15pt text).

### Steps to reproduce

1. `git clone https://github.com/mozzius/inline-view-baseline-repro && cd inline-view-baseline-repro/ReproducerApp && yarn install`
2. `cd ios && bundle install && RCT_USE_PREBUILT_RNCORE=0 bundle exec pod install && cd ..` (building the core from source is only needed for the repro's **patched** switch; **stock** is upstream's code)
3. `yarn start`, then `yarn ios`
4. Each row is a `Text` with a blue `View` nested in it. The red hairline is the line's baseline from `onTextLayout`, and the number on the right is the view's bottom minus that baseline. In **stock** mode, every view hangs below the hairline the letters sit on.
5. Tap **patched**: the views move onto the baseline.
6. `yarn android` shows every view on the baseline.

The minimal case:

```tsx
<Text style={{fontSize: 15, lineHeight: 24}}>
  HEXHOLM <View style={{width: 12, height: 12, backgroundColor: 'blue'}} />
</Text>
```

### React Native Version

0.88.0. The code is the same in 0.88.1, on `main` (f754dbd), and in every release since 0.82.0.

### Affected Platforms

Runtime - iOS

### Areas

Fabric - The New Renderer

### Output of `npx @react-native-community/cli info`

```text
System:
  OS: macOS 27.0.1
  CPU: (14) arm64 Apple M4 Pro
  Memory: 202.77 MB / 48.00 GB
  Shell:
    version: 5.3.20
    path: /opt/homebrew/bin/bash
Binaries:
  Node:
    version: 24.22.1
    path: ~/.nvm/versions/node/v24.22.1/bin/node
  Yarn:
    version: 1.22.22
    path: ~/.nvm/versions/node/v24.22.1/bin/yarn
  npm:
    version: 11.19.1
    path: ~/.nvm/versions/node/v24.22.1/bin/npm
  Watchman:
    version: 2026.10.19.00
    path: /opt/homebrew/bin/watchman
Managers:
  CocoaPods:
    version: 1.17.0
    path: ~/.rbenv/shims/pod
SDKs:
  iOS SDK:
    Platforms:
      - DriverKit 27.0
      - iOS 27.1
      - macOS 27.0
      - tvOS 27.0
      - visionOS 27.0
      - watchOS 27.0
  Android SDK:
    API Levels:
      - "35"
      - "36"
      - "37"
IDEs:
  Xcode:
    version: 27.1/27A9275
    path: /usr/bin/xcodebuild
Languages:
  Java:
    version: 17.0.20.1
    path: /usr/bin/javac
  Ruby:
    version: 2.7.6
    path: ~/.rbenv/shims/ruby
npmPackages:
  "@react-native-community/cli":
    installed: 20.2.0
    wanted: 20.2.0
  react:
    installed: 19.3.0
    wanted: 19.3.0
  react-native:
    installed: 0.88.0
    wanted: 0.88.0
  react-native-macos: Not Found
npmGlobalPackages:
  "*react-native*": Not Found
Android:
  hermesEnabled: true
  newArchEnabled: true
iOS:
  hermesEnabled: true
  newArchEnabled: true
```

### Stacktrace or Logs

The repro's patch logs every attachment's placement (iPhone 17 Pro simulator, iOS 26.5, default text size). The first line shows the attributes React Native gives the attachment's run before TextKit sees it; the rest show the text's font, the font the stock code reads (always 12pt Helvetica), and both placements:

```text
[inline-baseline] attachment run attributes from React Native: EventEmitter, NSAttachment
[inline-baseline] stock: view 12.33x12.33 | text font .SFUI-Regular 15.00 (ascender 14.282, descender -3.618, lineHeight 17.900, leading 0.000), paragraph lineHeight 0.00, baseline offset 0.000 | line 0.000..17.900, glyph rect 0.000..17.900, glyph location y 14.282, baseline 14.282 | attachment font Helvetica 12.0 (descender -2.760) | stock bottom 15.141 (+0.858 from baseline), fixed bottom 14.282
[inline-baseline] stock: view 12.33x12.33 | text font .SFUI-Regular 15.00 (ascender 14.282, descender -3.618, lineHeight 17.900, leading 0.000), paragraph lineHeight 24.00, baseline offset 3.050 | line 0.000..24.000, glyph rect 0.000..24.000, glyph location y 17.332, baseline 17.332 | attachment font Helvetica 12.0 (descender -2.760) | stock bottom 21.240 (+3.908 from baseline), fixed bottom 17.332
[inline-baseline] stock: view 16.33x16.33 | text font .SFUI-Regular 24.00 (ascender 22.852, descender -5.789, lineHeight 28.641, leading 0.000), paragraph lineHeight 0.00, baseline offset 0.000 | line 0.000..28.641, glyph rect 0.000..28.641, glyph location y 22.852, baseline 22.852 | attachment font Helvetica 12.0 (descender -2.760) | stock bottom 25.881 (+3.029 from baseline), fixed bottom 22.852
[inline-baseline] stock: view 16.33x16.33 | text font .SFUI-Regular 24.00 (ascender 22.852, descender -5.789, lineHeight 28.641, leading 0.000), paragraph lineHeight 36.00, baseline offset 3.680 | line 0.000..36.000, glyph rect 0.000..36.000, glyph location y 26.531, baseline 26.531 | attachment font Helvetica 12.0 (descender -2.760) | stock bottom 33.240 (+6.709 from baseline), fixed bottom 26.531
[inline-baseline] stock: view 12.33x12.33 | text font .SFUI-Regular 15.00 (ascender 14.282, descender -3.618, lineHeight 17.900, leading 0.000), paragraph lineHeight 0.00, baseline offset 0.000 | line 0.000..28.641, glyph rect 0.000..28.641, glyph location y 22.852, baseline 22.852 | attachment font Helvetica 12.0 (descender -2.760) | stock bottom 25.881 (+3.029 from baseline), fixed bottom 22.852
```

The last line is the mixed-size row: 15pt text, but a 28.64pt line with a 24pt word on it. The full logs are in the repro's [`measurements/logs/`](https://github.com/mozzius/inline-view-baseline-repro/tree/main/measurements/logs).

### MANDATORY Reproducer

https://github.com/mozzius/inline-view-baseline-repro

### Screenshots and Videos

The single-line samples, at the default text size. Red hairline: the line's baseline from `onTextLayout`.

| iOS 0.88.0 | iOS 0.88.0, fixed | iOS 0.81.6 | Android 0.88.0 |
| --- | --- | --- | --- |
| ![iOS 0.88.0: every blue square hangs below the red baseline](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/zoom-ios-0.88-stock.png) | ![iOS 0.88.0 with the fix: every square sits on the baseline](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/zoom-ios-0.88-patched.png) | ![iOS 0.81.6: squares on the baseline, except two taller than the line's ascent, which sit above it](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/zoom-ios-0.81.6.png) | ![Android 0.88.0: every square sits on the baseline](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/zoom-android-0.88.png) |

At Accessibility Medium:

| iOS 0.88.0 | iOS 0.88.0, fixed |
| --- | --- |
| ![iOS 0.88.0 at Accessibility Medium: the squares hang up to 14pt below the baseline](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/ios-0.88-stock-ax-end.png) | ![iOS 0.88.0 at Accessibility Medium with the fix: every square sits on the baseline](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/ios-0.88-patched-ax-end.png) |

Full screens: [iOS 0.88.0](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/ios-0.88-stock.png), [fixed](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/ios-0.88-patched.png), [iOS 0.81.6](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/ios-0.81.6.png), [iOS 0.81.6 at Accessibility Medium](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/ios-0.81.6-ax-end.png), [Android](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/android-0.88.png), [Android at font scale 2](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/android-0.88-scale-2.png).
