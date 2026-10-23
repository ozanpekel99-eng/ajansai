import { useEffect, useState } from "react";
import { StatusBar } from "expo-status-bar";
import { ActivityIndicator, SafeAreaView, StyleSheet } from "react-native";

import { clearToken, loadToken, setLogoutHandler } from "./api";
import IdeasScreen from "./screens/IdeasScreen";
import LoginScreen from "./screens/LoginScreen";

export default function App() {
  const [state, setState] = useState("loading"); // loading | login | app

  useEffect(() => {
    setLogoutHandler(() => setState("login"));
    loadToken().then((token) => setState(token ? "app" : "login"));
  }, []);

  const logout = async () => {
    await clearToken();
    setState("login");
  };

  return (
    <SafeAreaView style={styles.safe}>
      <StatusBar style="dark" />
      {state === "loading" && <ActivityIndicator style={{ marginTop: 80 }} />}
      {state === "login" && <LoginScreen onLoggedIn={() => setState("app")} />}
      {state === "app" && <IdeasScreen onLogout={logout} />}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: "#f5f5f7" },
});
