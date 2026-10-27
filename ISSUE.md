# iOS: a View nested in Text sits below the text baseline

### Description

On iOS with the New Architecture, a `View` nested in a `Text` (an inline view) is placed below the text baseline instead of on it. Android and web put the bottom of the view on the baseline.

The error depends on the text, not on the view:

- Without `lineHeight`, the view is `|descender of the text's font| - 2.76` points low: 0.86pt for 15pt system text, 3.03pt for 24pt.
- With a `lineHeight` taller than the font's line height, it's another `(lineHeight - font.lineHeight) / 2` lower: 3.91pt in total for 15pt text with `lineHeight: 24`, 6.71pt for 24pt text with `lineHeight: 36`.
- Both grow with Dynamic Type. At the first accessibility size, 15pt text with `lineHeight: 20` puts the view 5.58pt low, and 24pt text with `lineHeight: 36` 14.15pt.

Measured in the repro (iPhone 17 Pro simulator, iOS 26.5, system font), as the view's bottom minus the baseline of its line:

| fontSize / lineHeight | Default text size | Accessibility Medium |
| --- | ---: | ---: |
| 15 / none | +0.86 | +3.70 |
| 15 / 15 | +0.86 | +3.70 |
| 15 / 20 | +1.91 | +5.58 |
| 15 / 24 | +3.91 | +9.15 |
| 24 / none | +3.03 | +7.58 |
| 24 / 28 | +3.03 | +7.58 |
| 24 / 36 | +6.71 | +14.15 |

The glyphs themselves sit on the baseline `onTextLayout` reports (checked against the screenshots' pixels); only the inline view is off.

#### Cause

`_measureTextStorage:` places each attachment at the bottom of its glyph rect plus the descender of the font on the attachment's own run ([RCTTextLayoutManager.mm#L645-L653](https://github.com/react/react-native/blob/0941e95391d23cb2e0490d9c5a5b13886da424f2/packages/react-native/ReactCommon/react/renderer/textlayoutmanager/platform/ios/react/renderer/textlayoutmanager/RCTTextLayoutManager.mm#L645-L653)):

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

That's only the baseline if that font is the text's font and the line has no extra height. Neither holds on Fabric:

1. The attachment's run has no font. `RCTNSAttributedStringFragmentFromFragment` only sets `NSAttachmentAttributeName` on it ([RCTAttributedTextUtils.mm#L412-L423](https://github.com/react/react-native/blob/0941e95391d23cb2e0490d9c5a5b13886da424f2/packages/react-native/ReactCommon/react/renderer/textlayoutmanager/platform/ios/react/renderer/textlayoutmanager/RCTAttributedTextUtils.mm#L412-L423)), so `NSTextStorage` fills in its default, 12pt Helvetica (descender -2.76), whatever the surrounding text is. Logging `font` here prints `Helvetica 12.0` for every attachment.
2. With a `lineHeight` taller than the font's, `RCTApplyBaselineOffset` raises the glyphs by `(lineHeight - font.lineHeight) / 2` with `NSBaselineOffsetAttributeName` ([RCTAttributedTextUtils.mm#L378-L384](https://github.com/react/react-native/blob/0941e95391d23cb2e0490d9c5a5b13886da424f2/packages/react-native/ReactCommon/react/renderer/textlayoutmanager/platform/ios/react/renderer/textlayoutmanager/RCTAttributedTextUtils.mm#L378-L384)). The bottom of the line plus a descender doesn't include that offset.

This formula was introduced by https://github.com/react/react-native/pull/53341 (first released in 0.82), which brought over Paper's calculation to fix https://github.com/react/react-native/issues/53092. [`react-native-nano-icons`](https://github.com/software-mansion-labs/react-native-nano-icons) already works around it on 0.82 and later (`ios/NanoIconInlineBaseline.mm`), with the same layout as the fix below.

#### Fix

Place the attachment on the baseline TextKit actually used for its line: the line fragment's origin plus the attachment glyph's location within it. That includes the baseline offset and doesn't depend on any font. It's the same baseline `onTextLayout` reports for each line.

```objc
NSUInteger glyphIndex = attachmentGlyphRange.location;
CGRect lineFragmentRect = [layoutManager lineFragmentRectForGlyphAtIndex:glyphIndex effectiveRange:NULL];
CGFloat baseline = lineFragmentRect.origin.y + [layoutManager locationForGlyphAtIndex:glyphIndex].y;

CGRect frame = {.origin = {glyphRect.origin.x, baseline - attachmentSize.height}, .size = attachmentSize};
```

With this, the bottom of every inline view in the repro sits exactly on the baseline (0 px off, at both text sizes). I'm happy to open a PR with it.

### Steps to reproduce

1. `git clone https://github.com/mozzius/inline-view-baseline-repro && cd inline-view-baseline-repro/ReproducerApp && yarn install`
2. `cd ios && bundle install && RCT_USE_PREBUILT_RNCORE=0 bundle exec pod install && cd ..` (building the core from source is only needed for the repro's **patched** switch; **stock** is upstream's code)
3. `yarn start`, then `yarn ios`
4. Each row is a `Text` with a blue square `View` nested in it. The red hairline is the line's baseline from `onTextLayout`, and the number on the right is the square's bottom minus that baseline. In **stock** mode, every square hangs below the hairline that the letters sit on.
5. Tap **patched**: the squares move up onto the baseline.

The minimal case:

```tsx
<Text style={{fontSize: 15, lineHeight: 24}}>
  HEXHOLM <View style={{width: 12, height: 12, backgroundColor: 'blue'}} />
</Text>
```

### React Native Version

0.88.0. The code is the same on `main` (0941e95391d).

### Affected Platforms

Runtime - iOS

### Areas

Fabric - The New Renderer

### Output of `npx @react-native-community/cli info`

```text
System:
  OS: macOS 27.0.1
  CPU: (14) arm64 Apple M4 Pro
IDEs:
  Xcode:
    version: 27.1/27A9275
npmPackages:
  "@react-native-community/cli":
    installed: 20.2.0
  react:
    installed: 19.3.0
  react-native:
    installed: 0.88.0
iOS:
  hermesEnabled: true
  newArchEnabled: true
```

### Stacktrace or Logs

The repro's patch logs both placements for every attachment (default text size):

```text
[inline-baseline] stock: 12x12 view, line 0.00..17.90, baseline 14.28, attachment font Helvetica 12.0 (descender -2.76): stock bottom 15.14 (+0.86 from baseline), fixed bottom 14.28
[inline-baseline] stock: 12x12 view, line 0.00..20.00, baseline 15.33, attachment font Helvetica 12.0 (descender -2.76): stock bottom 17.24 (+1.91 from baseline), fixed bottom 15.33
[inline-baseline] stock: 12x12 view, line 0.00..24.00, baseline 17.33, attachment font Helvetica 12.0 (descender -2.76): stock bottom 21.24 (+3.91 from baseline), fixed bottom 17.33
[inline-baseline] stock: 16x16 view, line 0.00..28.64, baseline 22.85, attachment font Helvetica 12.0 (descender -2.76): stock bottom 25.88 (+3.03 from baseline), fixed bottom 22.85
[inline-baseline] stock: 16x16 view, line 0.00..36.00, baseline 26.53, attachment font Helvetica 12.0 (descender -2.76): stock bottom 33.24 (+6.71 from baseline), fixed bottom 26.53
```

### MANDATORY Reproducer

https://github.com/mozzius/inline-view-baseline-repro

### Screenshots and Videos

| Stock | Patched |
| --- | --- |
| ![Stock: the blue squares hang below the red baseline in every row](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/zoom-stock.png) | ![Patched: every blue square sits on the red baseline, like the letters](https://raw.githubusercontent.com/mozzius/inline-view-baseline-repro/main/screenshots/zoom-patched.png) |

Full screens: [stock](https://github.com/mozzius/inline-view-baseline-repro/blob/main/screenshots/stock.png), [patched](https://github.com/mozzius/inline-view-baseline-repro/blob/main/screenshots/patched.png), [stock at Accessibility Medium](https://github.com/mozzius/inline-view-baseline-repro/blob/main/screenshots/stock-ax.png), [patched at Accessibility Medium](https://github.com/mozzius/inline-view-baseline-repro/blob/main/screenshots/patched-ax.png).
