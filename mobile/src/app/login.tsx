import { Image } from "expo-image";
import * as WebBrowser from "expo-web-browser";
import { useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import SocialLogin from "@/components/SocialLogin";
import { Button, ErrorText, Input, T } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useSession, User } from "@/lib/session";
import { colors, fonts } from "@/lib/theme";

type Mode = "login" | "register";

export default function Login() {
  const { signIn } = useSession();
  const [mode, setMode] = useState<Mode>("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setError("");
    if (!email.trim() || !password || (mode === "register" && !name.trim())) {
      setError("Lütfen tüm alanları doldur.");
      return;
    }
    setBusy(true);
    try {
      const body = mode === "register" ? { name: name.trim(), email: email.trim(), password } : { email: email.trim(), password };
      const res = await api<{ token: string; user: User }>(`/api/auth/${mode}`, { body });
      await signIn(res.token, res.user);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Giriş yapılamadı, tekrar dene.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }}>
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === "ios" ? "padding" : undefined}>
        <ScrollView contentContainerStyle={st.wrap} keyboardShouldPersistTaps="handled">
          <Image source={require("@/assets/images/logo.png")} style={st.logo} contentFit="contain" />
          <View style={{ gap: 8 }}>
            <T variant="h1">
              <T variant="h1" style={{ color: colors.indigo }}>
                5 dakikada
              </T>{" "}
              reklamın yayında.
            </T>
            <T variant="muted">Fikrini üret, görselini ya da videonu üret, tek tıkla reklamını ver.</T>
          </View>

          <View style={st.switch}>
            {(["login", "register"] as Mode[]).map((m) => (
              <Pressable key={m} onPress={() => setMode(m)} style={[st.switchBtn, mode === m && st.switchOn]} accessibilityRole="tab" accessibilityState={{ selected: mode === m }}>
                <T style={[st.switchText, mode === m && { color: colors.fg }]}>{m === "login" ? "Giriş yap" : "Hesap oluştur"}</T>
              </Pressable>
            ))}
          </View>

          <SocialLogin />

          <View style={{ gap: 14 }}>
            {mode === "register" && <Input label="Ad soyad" value={name} onChangeText={setName} autoComplete="name" textContentType="name" />}
            <Input label="E-posta" value={email} onChangeText={setEmail} autoCapitalize="none" keyboardType="email-address" autoComplete="email" textContentType="emailAddress" />
            <Input label="Şifre" value={password} onChangeText={setPassword} secureTextEntry autoComplete={mode === "login" ? "current-password" : "new-password"} textContentType={mode === "login" ? "password" : "newPassword"} onSubmitEditing={submit} />
            <ErrorText>{error}</ErrorText>
            <Button title={mode === "login" ? "Giriş yap" : "Ücretsiz başla"} onPress={submit} loading={busy} />
          </View>

          <T variant="muted" style={{ textAlign: "center" }}>
            Devam ederek kullanım koşullarını ve gizlilik politikasını kabul etmiş olursun.
          </T>
          <View style={st.legal}>
            <Pressable onPress={() => WebBrowser.openBrowserAsync("https://www.ajansai.tr/kosullar")}>
              <T variant="label" style={st.link}>Kullanım Koşulları</T>
            </Pressable>
            <Pressable onPress={() => WebBrowser.openBrowserAsync("https://www.ajansai.tr/gizlilik")}>
              <T variant="label" style={st.link}>Gizlilik Politikası</T>
            </Pressable>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const st = StyleSheet.create({
  wrap: { padding: 24, gap: 28, flexGrow: 1, justifyContent: "center" },
  logo: { width: 150, height: 44 },
  switch: { flexDirection: "row", backgroundColor: colors.surface, borderRadius: 12, padding: 4, borderWidth: 1, borderColor: colors.line },
  switchBtn: { flex: 1, paddingVertical: 10, borderRadius: 9, alignItems: "center" },
  switchOn: { backgroundColor: colors.surface2 },
  switchText: { fontFamily: fonts.bodyMedium, color: colors.muted },
  link: { color: colors.indigoSoft },
  legal: { flexDirection: "row", justifyContent: "center", gap: 20 },
});
