import { ReactNode } from "react";
import { ActivityIndicator, Pressable, StyleProp, StyleSheet, Text, TextInput, TextInputProps, TextStyle, View, ViewStyle } from "react-native";

import { colors, fonts, radius } from "@/lib/theme";

export function T({ children, style, variant = "body", numberOfLines }: { children: ReactNode; style?: StyleProp<TextStyle>; variant?: "h1" | "h2" | "h3" | "body" | "small" | "muted" | "label"; numberOfLines?: number }) {
  return (
    <Text style={[s[variant], style]} numberOfLines={numberOfLines}>
      {children}
    </Text>
  );
}

export function Button({ title, onPress, variant = "primary", loading, disabled, style, icon }: { title: string; onPress: () => void; variant?: "primary" | "ghost" | "light"; loading?: boolean; disabled?: boolean; style?: StyleProp<ViewStyle>; icon?: ReactNode }) {
  const off = disabled || loading;
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      disabled={off}
      style={({ pressed }) => [s.btn, s[`btn_${variant}`], off && { opacity: 0.5 }, pressed && { opacity: 0.8 }, style]}
    >
      {loading ? (
        <ActivityIndicator color={variant === "light" ? colors.bg : colors.white} />
      ) : (
        <View style={s.btnRow}>
          {icon}
          <Text style={[s.btnText, variant === "light" && { color: colors.bg }]}>{title}</Text>
        </View>
      )}
    </Pressable>
  );
}

export function Input(props: TextInputProps & { label?: string }) {
  const { label, style, ...rest } = props;
  return (
    <View style={{ gap: 6 }}>
      {label ? <T variant="label">{label}</T> : null}
      <TextInput placeholderTextColor={colors.faint} style={[s.input, style]} {...rest} />
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[s.card, style]}>{children}</View>;
}

export function ErrorText({ children }: { children: ReactNode }) {
  if (!children) return null;
  return <T style={{ color: colors.danger }}>{children}</T>;
}

const s = StyleSheet.create({
  h1: { fontFamily: fonts.display, fontSize: 32, lineHeight: 36, color: colors.fg, letterSpacing: -0.8 },
  h2: { fontFamily: fonts.display, fontSize: 24, lineHeight: 28, color: colors.fg, letterSpacing: -0.4 },
  h3: { fontFamily: fonts.display, fontSize: 18, lineHeight: 22, color: colors.fg },
  body: { fontFamily: fonts.body, fontSize: 16, lineHeight: 23, color: colors.fg },
  small: { fontFamily: fonts.body, fontSize: 13, lineHeight: 18, color: colors.fg },
  muted: { fontFamily: fonts.body, fontSize: 14, lineHeight: 20, color: colors.muted },
  label: { fontFamily: fonts.bodyMedium, fontSize: 13, color: colors.muted },
  btn: { minHeight: 50, borderRadius: radius.md, paddingHorizontal: 18, alignItems: "center", justifyContent: "center" },
  btn_primary: { backgroundColor: colors.indigo },
  btn_ghost: { backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.line },
  btn_light: { backgroundColor: colors.white },
  btnRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  btnText: { fontFamily: fonts.bodySemi, fontSize: 16, color: colors.white },
  input: { minHeight: 50, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface, color: colors.fg, paddingHorizontal: 14, fontFamily: fonts.body, fontSize: 16 },
  card: { backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.line, padding: 16 },
});
