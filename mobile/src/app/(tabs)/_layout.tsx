import Ionicons from "@expo/vector-icons/Ionicons";
import { Tabs } from "expo-router";
import type { ColorValue } from "react-native";

import { colors, fonts } from "@/lib/theme";

type IconName = keyof typeof Ionicons.glyphMap;
const icon = (name: IconName, active: IconName) =>
  function TabIcon({ color, focused, size }: { color: ColorValue; focused: boolean; size: number }) {
    return <Ionicons name={focused ? active : name} color={color as string} size={size} />;
  };

export default function TabsLayout() {
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.fg,
        tabBarInactiveTintColor: colors.faint,
        tabBarStyle: { backgroundColor: colors.bg, borderTopColor: colors.line },
        tabBarLabelStyle: { fontFamily: fonts.bodyMedium, fontSize: 11 },
      }}
    >
      <Tabs.Screen name="index" options={{ title: "Sohbet", tabBarIcon: icon("chatbubble-outline", "chatbubble") }} />
      <Tabs.Screen name="uret" options={{ title: "Üret", tabBarIcon: icon("sparkles-outline", "sparkles") }} />
      <Tabs.Screen name="reklam" options={{ title: "Reklam", tabBarIcon: icon("megaphone-outline", "megaphone") }} />
      <Tabs.Screen name="kutuphane" options={{ title: "Kütüphane", tabBarIcon: icon("images-outline", "images") }} />
      <Tabs.Screen name="hesap" options={{ title: "Hesap", tabBarIcon: icon("person-circle-outline", "person-circle") }} />
    </Tabs>
  );
}
