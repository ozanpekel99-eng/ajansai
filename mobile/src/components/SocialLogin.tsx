// Apple ile giriş (yalnızca iOS). Hesap yoksa aynı anda oluşturulur — web'deki SocialLogin ile aynı uç: /api/auth/apple.
// Google ile giriş sonraki adımda eklenecek (BACKLOG).
import * as AppleAuthentication from "expo-apple-authentication";
import { useEffect, useState } from "react";
import { ActivityIndicator, Platform, StyleSheet, View } from "react-native";

import { ErrorText, T } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useSession, User } from "@/lib/session";
import { colors, radius } from "@/lib/theme";

/** Apple'ın verdiği ad parçalarından "Ad Soyad" (yalnızca ilk girişte gelir). */
export function appleFullName(n: AppleAuthentication.AppleAuthenticationFullName | null): string {
  if (!n) return "";
  return [n.givenName, n.familyName].filter(Boolean).join(" ").trim();
}

export default function SocialLogin() {
  const { signIn } = useSession();
  const [appleOk, setAppleOk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (Platform.OS !== "ios") return;
    AppleAuthentication.isAvailableAsync()
      .then(setAppleOk)
      .catch(() => setAppleOk(false));
  }, []);

  const apple = async () => {
    setError("");
    let cred: AppleAuthentication.AppleAuthenticationCredential;
    try {
      cred = await AppleAuthentication.signInAsync({
        requestedScopes: [AppleAuthentication.AppleAuthenticationScope.FULL_NAME, AppleAuthentication.AppleAuthenticationScope.EMAIL],
      });
    } catch (e: any) {
      if (e?.code !== "ERR_REQUEST_CANCELED") setError("Apple ile giriş tamamlanamadı.");
      return;
    }
    if (!cred.identityToken) {
      setError("Apple ile giriş tamamlanamadı.");
      return;
    }
    setBusy(true);
    try {
      const res = await api<{ token: string; user: User }>("/api/auth/apple", {
        body: { id_token: cred.identityToken, name: appleFullName(cred.fullName) },
      });
      await signIn(res.token, res.user);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Apple ile giriş tamamlanamadı.");
    } finally {
      setBusy(false);
    }
  };

  if (!appleOk) return null;

  return (
    <View style={{ gap: 14 }}>
      <View>
        <AppleAuthentication.AppleAuthenticationButton
          buttonType={AppleAuthentication.AppleAuthenticationButtonType.CONTINUE}
          buttonStyle={AppleAuthentication.AppleAuthenticationButtonStyle.WHITE}
          cornerRadius={radius.md}
          style={st.apple}
          onPress={busy ? () => {} : apple}
        />
        {busy && (
          <View style={st.busy} pointerEvents="none">
            <ActivityIndicator color={colors.bg} />
          </View>
        )}
      </View>
      <ErrorText>{error}</ErrorText>
      <View style={st.divider}>
        <View style={st.line} />
        <T variant="muted">veya e-postayla</T>
        <View style={st.line} />
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  apple: { width: "100%", height: 50 },
  busy: { position: "absolute", top: 0, left: 0, right: 0, bottom: 0, alignItems: "center", justifyContent: "center", backgroundColor: "rgba(255,255,255,0.7)", borderRadius: radius.md },
  divider: { flexDirection: "row", alignItems: "center", gap: 12 },
  line: { flex: 1, height: StyleSheet.hairlineWidth, backgroundColor: colors.line },
});
