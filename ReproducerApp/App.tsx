/**
 * A View nested in a Text should sit with its bottom on the text baseline, like
 * the letters do. On iOS (Fabric, React Native 0.82 and later) it sits below it.
 *
 * Each sample is a `Text` with a blue `View` nested in it. The red hairline is
 * the baseline of each line, taken from `onTextLayout`
 * (line.y + line.ascender). The number on the right is the view's bottom minus
 * the baseline of its line, in points, from the view's `measureLayout`:
 * positive means below the baseline.
 *
 * Only the samples follow the system text size, so that the rest of the
 * screen stays legible at the accessibility sizes.
 *
 * The stock/patched switch only does anything on iOS, with the patch in
 * patches/ compiled in (see the README).
 *
 * @format
 */

import React, { useEffect, useRef, useState } from 'react';
import {
  type LayoutRectangle,
  PixelRatio,
  Platform,
  Pressable,
  ScrollView,
  Settings,
  StatusBar,
  StyleSheet,
  Text,
  type TextLayoutEvent,
  View,
} from 'react-native';
import {
  SafeAreaProvider,
  useSafeAreaInsets,
} from 'react-native-safe-area-context';

type Mode = 'stock' | 'patched';

type TextLayoutLine = TextLayoutEvent['nativeEvent']['lines'][number];

type Sample = {
  fontSize: number;
  lineHeight?: number;
  fontWeight?: 'bold';
  /** Height of the inline view, and its width unless `width` is set. */
  size: number;
  width?: number;
  /**
   * Font size of a nested `Text` before the view, so that the line mixes two
   * font sizes.
   */
  nestedFontSize?: number;
  /** Row label, if not `fontSize / lineHeight`. */
  label?: string;
};

const IS_IOS = Platform.OS === 'ios';
const RN_VERSION = (() => {
  const { major, minor, patch } = Platform.constants.reactNativeVersion;
  return `${major}.${minor}.${patch}`;
})();

const WORD = 'HEXHOLM';

const SAMPLES: Sample[] = [
  { fontSize: 15, size: 12 },
  { fontSize: 15, lineHeight: 15, size: 12 },
  { fontSize: 15, lineHeight: 20, size: 12 },
  { fontSize: 15, lineHeight: 24, size: 12 },
  { fontSize: 24, size: 16 },
  { fontSize: 24, lineHeight: 28, size: 16 },
  { fontSize: 24, lineHeight: 36, size: 16 },
];

/*
 * The case from react/react-native#53092: bold 14pt text with
 * `lineHeight: 14 * 1.2`, and a 54x20 view, taller than the line.
 */
const ISSUE_53092: Sample = {
  fontSize: 14,
  lineHeight: 14 * 1.2,
  fontWeight: 'bold',
  size: 20,
  width: 54,
  label: '#53092',
};

/*
 * 15pt text with a nested 24pt word before the view. The line's descent, and
 * so its baseline, comes from the 24pt font, not the view's own text.
 */
const MIXED: Sample = {
  fontSize: 15,
  size: 12,
  nestedFontSize: 24,
  label: '15 + 24',
};

const PARAGRAPH: Sample = { fontSize: 15, lineHeight: 24, size: 12 };

/*
 * The patch reads `ReproInlineBaselineFix` from NSUserDefaults each time it
 * places an inline view, and writes the mode it used to
 * `ReproInlineBaselineMeasured`. Every launch starts in stock mode.
 */
if (IS_IOS) {
  Settings.set({
    ReproInlineBaselineFix: false,
    ReproInlineBaselineMeasured: null,
  });
}

function App() {
  return (
    <SafeAreaProvider>
      <StatusBar barStyle="dark-content" />
      <Screen />
    </SafeAreaProvider>
  );
}

function Screen() {
  const insets = useSafeAreaInsets();
  const [mode, setMode] = useState<Mode>('stock');
  const [ready, setReady] = useState(false);
  const [pending, setPending] = useState(false);
  const [measured, setMeasured] = useState<string | null>(null);

  useEffect(() => {
    if (!IS_IOS) {
      return;
    }
    const id = Settings.watchKeys(['ReproInlineBaselineMeasured'], () => {
      const value = Settings.get('ReproInlineBaselineMeasured');
      setMeasured(typeof value === 'string' ? value : null);
    });
    return () => Settings.clearWatch(id);
  }, []);

  /*
   * Settings.set is asynchronous, so give each write a moment to land before
   * any text is laid out with the new mode. That includes the reset to stock
   * at launch.
   */
  useEffect(() => {
    const timer = setTimeout(() => setReady(true), 300);
    return () => clearTimeout(timer);
  }, []);

  const select = (next: Mode) => {
    if (next === mode || pending || !ready) {
      return;
    }
    if (IS_IOS) {
      Settings.set({ ReproInlineBaselineFix: next === 'patched' });
    }
    setPending(true);
    setTimeout(() => {
      setMode(next);
      setPending(false);
    }, 300);
  };

  return (
    <ScrollView
      style={styles.screen}
      contentContainerStyle={[
        styles.content,
        { paddingTop: insets.top + 8, paddingBottom: insets.bottom + 16 },
      ]}
    >
      <Text allowFontScaling={false} style={styles.title}>
        Inline View baseline
      </Text>
      <Text allowFontScaling={false} style={styles.meta}>
        react-native {RN_VERSION} · {Platform.OS} {String(Platform.Version)} ·
        font scale {PixelRatio.getFontScale().toFixed(2)}
      </Text>
      {IS_IOS ? (
        <Text allowFontScaling={false} style={styles.meta}>
          Patch:{' '}
          {measured ? (
            <Text style={styles.ok}>
              compiled in, last layout used {measured}
            </Text>
          ) : (
            <Text style={styles.warn}>
              not seen (core not built from source?)
            </Text>
          )}
        </Text>
      ) : null}

      {!IS_IOS ? null : (
        <View style={styles.toggle}>
          {(['stock', 'patched'] as const).map(option => (
            <Pressable
              key={option}
              accessibilityRole="button"
              accessibilityState={{ selected: mode === option }}
              onPress={() => select(option)}
              style={[
                styles.toggleOption,
                mode === option && styles.toggleOptionSelected,
              ]}
            >
              <Text
                allowFontScaling={false}
                style={[
                  styles.toggleText,
                  mode === option && styles.toggleTextSelected,
                ]}
              >
                {option}
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      <View style={styles.header}>
        <Text
          allowFontScaling={false}
          style={[styles.headerText, styles.labelColumn]}
        >
          fontSize / lineHeight
        </Text>
        <View style={styles.sampleColumn} />
        <Text
          allowFontScaling={false}
          style={[styles.headerText, styles.offsetHeader]}
        >
          bottom − baseline
        </Text>
      </View>

      {!ready ? null : (
        <>
          {[...SAMPLES, ISSUE_53092, MIXED].map(sample => {
            const label =
              sample.label ??
              `${sample.fontSize} / ${sample.lineHeight ?? '–'}`;
            return (
              <SampleRow
                key={label}
                label={label}
                sample={sample}
                mode={mode}
                before={
                  sample.nestedFontSize ? (
                    <>
                      {'HEX '}
                      <Text style={{ fontSize: sample.nestedFontSize }}>
                        HOLM
                      </Text>{' '}
                    </>
                  ) : (
                    `${WORD} `
                  )
                }
              />
            );
          })}

          <Text allowFontScaling={false} style={styles.sectionTitle}>
            Wrapped, 15 / 24, with the square mid-paragraph.
          </Text>
          <SampleRow
            sample={PARAGRAPH}
            mode={mode}
            before={`${WORD} `.repeat(7)}
            after={` ${WORD}`.repeat(4)}
            wide
          />
        </>
      )}
    </ScrollView>
  );
}

function SampleRow({
  label,
  sample,
  mode,
  before,
  after,
  wide = false,
}: {
  label?: string;
  sample: Sample;
  mode: Mode;
  /** Text before the inline square. */
  before: React.ReactNode;
  /** Text after the inline square. */
  after?: string;
  /** Lay the sample out full width, with the readout under it. */
  wide?: boolean;
}) {
  const [lines, setLines] = useState<TextLayoutLine[]>([]);
  const [square, setSquare] = useState<LayoutRectangle | null>(null);
  const textRef = useRef<React.ComponentRef<typeof Text>>(null);
  const squareRef = useRef<React.ComponentRef<typeof View>>(null);

  /*
   * onLayout doesn't fire for a View nested in a Text, so read the square's
   * frame from the committed layout instead, each time the text is laid out.
   */
  useEffect(() => {
    const textNode = textRef.current;
    const squareNode = squareRef.current;
    if (!textNode || !squareNode) {
      return;
    }
    squareNode.measureLayout(textNode, (x, y, width, height) =>
      setSquare({ x, y, width, height }),
    );
  }, [mode, lines]);

  const squareLine = square
    ? lineAt(lines, square.y + square.height / 2)
    : null;
  const offset =
    square && squareLine
      ? square.y + square.height - (squareLine.y + squareLine.ascender)
      : null;

  const text = (
    <View style={styles.textBox}>
      <Text
        ref={textRef}
        style={[
          styles.sampleText,
          {
            fontSize: sample.fontSize,
            lineHeight: sample.lineHeight,
            fontWeight: sample.fontWeight,
          },
        ]}
        /*
         * React Native caches text measurements by the layout-relevant text
         * attributes, so flipping the switch alone would not lay out text it
         * has already measured again. A maxFontSizeMultiplier that never
         * applies gives the patched mode its own cache entries.
         */
        maxFontSizeMultiplier={mode === 'patched' ? 1000 : undefined}
        onTextLayout={event => setLines(event.nativeEvent.lines)}
      >
        {before}
        <View
          ref={squareRef}
          style={[
            styles.square,
            { width: sample.width ?? sample.size, height: sample.size },
          ]}
        />
        {after}
      </Text>
      {lines.map((line, index) => (
        <View
          key={index}
          pointerEvents="none"
          style={[styles.baseline, { top: line.y + line.ascender }]}
        />
      ))}
    </View>
  );

  const readout = (
    <Text
      allowFontScaling={false}
      style={[
        styles.offset,
        offset !== null && Math.abs(offset) >= 0.25 && styles.offsetBad,
      ]}
    >
      {offset === null ? '…' : formatOffset(offset)}
    </Text>
  );

  if (wide) {
    return (
      <View style={styles.wideRow}>
        {text}
        <View style={styles.wideReadout}>
          <Text allowFontScaling={false} style={styles.headerText}>
            bottom − baseline{' '}
          </Text>
          {readout}
        </View>
      </View>
    );
  }

  return (
    <View style={styles.row}>
      <Text allowFontScaling={false} style={[styles.label, styles.labelColumn]}>
        {label}
      </Text>
      <View style={styles.sampleColumn}>{text}</View>
      <View style={styles.offsetColumn}>{readout}</View>
    </View>
  );
}

function lineAt(lines: TextLayoutLine[], y: number) {
  return (
    lines.find(line => y >= line.y && y < line.y + line.height) ??
    lines[lines.length - 1] ??
    null
  );
}

function formatOffset(offset: number) {
  const rounded = Math.round(offset * 100) / 100;
  if (rounded === 0) {
    return '0.00';
  }
  return `${rounded > 0 ? '+' : ''}${rounded.toFixed(2)}`;
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
    backgroundColor: '#ffffff',
  },
  content: {
    paddingHorizontal: 16,
  },
  title: {
    fontSize: 20,
    fontWeight: '700',
    color: '#000000',
  },
  meta: {
    marginTop: 4,
    fontSize: 12,
    color: '#555555',
  },
  ok: {
    color: '#1a7f37',
    fontWeight: '600',
  },
  warn: {
    color: '#bc4c00',
    fontWeight: '600',
  },
  toggle: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    marginTop: 12,
    marginBottom: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#999999',
    overflow: 'hidden',
  },
  toggleOption: {
    paddingHorizontal: 20,
    paddingVertical: 8,
  },
  toggleOptionSelected: {
    backgroundColor: '#222222',
  },
  toggleText: {
    fontSize: 15,
    color: '#222222',
  },
  toggleTextSelected: {
    color: '#ffffff',
    fontWeight: '600',
  },
  header: {
    flexDirection: 'row',
    marginBottom: 8,
  },
  headerText: {
    fontSize: 11,
    color: '#777777',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 18,
  },
  labelColumn: {
    width: 64,
  },
  sampleColumn: {
    flex: 1,
    alignItems: 'flex-start',
  },
  offsetColumn: {
    width: 60,
    alignItems: 'flex-end',
  },
  offsetHeader: {
    width: 60,
    textAlign: 'right',
  },
  label: {
    fontSize: 13,
    color: '#333333',
    fontVariant: ['tabular-nums'],
  },
  textBox: {
    backgroundColor: '#e8ecf2',
  },
  sampleText: {
    color: '#000000',
  },
  square: {
    backgroundColor: '#0000ff',
  },
  baseline: {
    position: 'absolute',
    left: -8,
    right: -8,
    height: StyleSheet.hairlineWidth,
    backgroundColor: '#ff0000',
  },
  offset: {
    fontSize: 15,
    fontWeight: '600',
    color: '#1a7f37',
    fontVariant: ['tabular-nums'],
  },
  offsetBad: {
    color: '#cf222e',
  },
  sectionTitle: {
    marginTop: 4,
    marginBottom: 8,
    fontSize: 11,
    color: '#777777',
  },
  wideRow: {
    marginBottom: 18,
  },
  wideReadout: {
    flexDirection: 'row',
    alignItems: 'baseline',
    justifyContent: 'flex-end',
    marginTop: 6,
  },
});

export default App;
