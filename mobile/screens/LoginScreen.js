import { useState } from "react";
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from "react-native";

import { api, saveToken } from "../api";

export default function LoginScreen({ onLoggedIn }) {
  const [mode, setMode] = useState("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const submit = async () => {
    setLoading(true);
    setError("");
    try {
      const body = mode === "register" ? { name, email, password } : { email, password };
      const data = await api(`/api/auth/${mode}`, { method: "POST", body: JSON.stringify(body) });
      await saveToken(data.token);
      onLoggedIn();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={styles.container}>
      <Text style={styles.brand}>
        ajans<Text style={styles.brandAccent}>AI</Text>
      </Text>
      <Text style={styles.title}>{mode === "login" ? "Tekrar hoş geldin." : "Hesabını oluştur."}</Text>

      {mode === "register" && (
        <TextInput style={styles.input} placeholder="Ad soyad" placeholderTextColor="rgba(255,255,255,0.4)" value={name} onChangeText={setName} />
      )}
      <TextInput
        style={styles.input}
        placeholder="E-posta"
        placeholderTextColor="rgba(255,255,255,0.4)"
        autoCapitalize="none"
        keyboardType="email-address"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={styles.input}
        placeholder={mode === "register" ? "Şifre (en az 8 karakter)" : "Şifre"}
        placeholderTextColor="rgba(255,255,255,0.4)"
        secureTextEntry
        value={password}
        onChangeText={setPassword}
      />

      <TouchableOpacity style={styles.button} onPress={submit} disabled={loading}>
        {loading ? <ActivityIndicator color="#fff" /> : <Text style={styles.buttonText}>{mode === "login" ? "Giriş yap" : "Hesap oluştur"}</Text>}
      </TouchableOpacity>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <TouchableOpacity
        onPress={() => {
          setMode(mode === "login" ? "register" : "login");
          setError("");
        }}
      >
        <Text style={styles.switch}>{mode === "login" ? "Hesabın yok mu? Kayıt ol" : "Zaten hesabın var mı? Giriş yap"}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, padding: 20, paddingTop: 80, backgroundColor: "#f5f5f7" },
  brand: { fontSize: 20, fontWeight: "700", color: "#0a0a0a" },
  brandAccent: { color: "#413ff5" },
  title: { fontSize: 26, fontWeight: "700", color: "#0a0a0a", marginTop: 8, marginBottom: 24 },
  input: {
    backgroundColor: "#0a0a0a",
    color: "#f5f5f7",
    borderRadius: 6,
    paddingHorizontal: 12,
    paddingVertical: 12,
    fontSize: 14,
    marginBottom: 12,
  },
  button: { backgroundColor: "#413ff5", borderRadius: 999, paddingVertical: 14, alignItems: "center", marginTop: 8 },
  buttonText: { fontWeight: "700", color: "#fff" },
  error: { color: "#d64545", marginTop: 12, fontSize: 13 },
  switch: { color: "#413ff5", marginTop: 20, fontWeight: "600", textAlign: "center" },
});
