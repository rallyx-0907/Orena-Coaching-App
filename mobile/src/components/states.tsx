import {useEffect, useRef} from 'react';
import {Animated, Easing, StyleSheet, Text, View, type StyleProp, type ViewStyle} from 'react-native';
import {useI18n} from '../i18n/I18nProvider';
import {useTheme} from '../theme/ThemeProvider';
function PanelCopy({children}: React.PropsWithChildren) {const {tokens}=useTheme();return <Text style={{color:tokens.colors.mutedText,fontSize:15,lineHeight:24}}>{children}</Text>;}

/**
 * The shared loading / error / empty states, ported from `loadingBlock()` and
 * `errorBlock()` in static/becoming/components/primitives.js.
 *
 * Every screen was hand-rolling these, so a loading state was a bare line of
 * text on one screen and nothing at all on another, and the web's shimmering
 * skeleton had no native equivalent. Sharing them also keeps one distinction the
 * product depends on: signed out, unavailable, and empty are three different
 * facts and each has its own component rather than one grey message.
 */

/** `.loading-line`: a 14px bar with the 1.2s shimmer passing over it. */
function SkeletonLine({width}: {width: number | `${number}%`}) {
  const {tokens} = useTheme();
  const shimmer = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(Animated.timing(shimmer, {toValue: 1, duration: 1200, easing: Easing.linear, useNativeDriver: true}));
    loop.start();
    return () => loop.stop();
  }, [shimmer]);
  return (
    <View style={[styles.line, {width, backgroundColor: tokens.colors.surfaceSunken}]}>
      <Animated.View
        style={[
          styles.shimmer,
          {
            backgroundColor: tokens.scheme === 'dark' ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.7)',
            transform: [{translateX: shimmer.interpolate({inputRange: [0, 1], outputRange: [-160, 160]})}],
          },
        ]}
      />
    </View>
  );
}

/**
 * `loadingBlock(lines)`. The label is what a screen reader announces; the bars
 * are decoration and are hidden from it.
 */
export function LoadingState({lines = 3, style}: {lines?: number; style?: StyleProp<ViewStyle>}) {
  const {t} = useI18n();
  const widths: (number | `${number}%`)[] = ['92%', '78%', '85%', '64%', '88%', '72%'];
  return (
    <View accessibilityRole="progressbar" accessibilityLabel={t('chrome.loading' as never)} style={[styles.block, style]}>
      {Array.from({length: Math.max(1, lines)}, (_, index) => (
        <View key={index} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <SkeletonLine width={widths[index % widths.length]!} />
        </View>
      ))}
    </View>
  );
}

/** `errorBlock(message)`: announced, and never dressed up as ordinary copy. */
export function ErrorState({message, style}: {message: string; style?: StyleProp<ViewStyle>}) {
  const {tokens} = useTheme();
  return (
    <View
      accessibilityRole="alert"
      style={[styles.error, {borderColor: tokens.colors.danger, backgroundColor: tokens.colors.dangerSurface}, style]}
    >
      <Text style={[styles.errorText, {color: tokens.colors.danger}]}>{message}</Text>
    </View>
  );
}

/**
 * Nothing here yet -- which is not a failure, so it is not an alert and does
 * not borrow the error colour.
 */
export function EmptyState({title, body, action, style}: {title: string; body?: string; action?: React.ReactNode; style?: StyleProp<ViewStyle>}) {
  const {tokens} = useTheme();
  return (
    <View style={[styles.block, style]}>
      <Text style={[styles.emptyTitle, {color: tokens.colors.text}]}>{title}</Text>
      {body ? <PanelCopy>{body}</PanelCopy> : null}
      {action}
    </View>
  );
}

/**
 * Signed out is a third fact again: the service is fine and there is nothing
 * wrong with the learner's data, they just are not signed in.
 */
export function SignedOutState({message, action, style}: {message: string; action?: React.ReactNode; style?: StyleProp<ViewStyle>}) {
  return (
    <View style={[styles.block, style]}>
      <PanelCopy>{message}</PanelCopy>
      {action}
    </View>
  );
}

const styles = StyleSheet.create({
  block: {gap: 12},
  line: {height: 14, borderRadius: 6, overflow: 'hidden'},
  shimmer: {position: 'absolute', top: 0, bottom: 0, width: 160},
  error: {borderWidth: 1, borderRadius: 15, padding: 12},
  errorText: {fontSize: 14, lineHeight: 20},
  emptyTitle: {fontSize: 15, fontWeight: '600'},
});
