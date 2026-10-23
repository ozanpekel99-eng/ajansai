import { Text, View } from "react-native";

import { colors, fonts } from "@/lib/theme";

// Sohbet yanıtları için hafif markdown: başlık, madde, numaralı liste, **kalın**, `kod`.
function inline(text: string, key: string) {
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g).filter(Boolean);
  return parts.map((p, i) => {
    if (p.startsWith("**") && p.endsWith("**")) return <Text key={`${key}-${i}`} style={{ fontFamily: fonts.bodySemi }}>{p.slice(2, -2)}</Text>;
    if (p.startsWith("`") && p.endsWith("`")) return <Text key={`${key}-${i}`} style={{ fontFamily: fonts.bodyMedium, color: colors.indigoSoft }}>{p.slice(1, -1)}</Text>;
    return p;
  });
}

export default function Markdown({ text }: { text: string }) {
  const lines = text.replace(/\r/g, "").split("\n");
  return (
    <View style={{ gap: 6 }}>
      {lines.map((raw, i) => {
        const line = raw.trimEnd();
        if (!line.trim()) return <View key={i} style={{ height: 2 }} />;
        const h = line.match(/^(#{1,4})\s+(.*)/);
        if (h) return <Text key={i} style={{ fontFamily: fonts.display, fontSize: h[1].length <= 2 ? 19 : 17, color: colors.fg, marginTop: 4 }}>{inline(h[2], `${i}`)}</Text>;
        const b = line.match(/^\s*[-*•]\s+(.*)/);
        const n = line.match(/^\s*(\d+)[.)]\s+(.*)/);
        if (b || n) {
          return (
            <View key={i} style={{ flexDirection: "row", gap: 8, paddingLeft: 2 }}>
              <Text style={{ color: colors.indigoSoft, fontFamily: fonts.bodySemi, fontSize: 16, lineHeight: 23, minWidth: n ? 20 : 10 }}>{n ? `${n[1]}.` : "•"}</Text>
              <Text style={{ flex: 1, color: colors.fg, fontFamily: fonts.body, fontSize: 16, lineHeight: 23 }}>{inline(n ? n[2] : b![1], `${i}`)}</Text>
            </View>
          );
        }
        return <Text key={i} style={{ color: colors.fg, fontFamily: fonts.body, fontSize: 16, lineHeight: 23 }}>{inline(line, `${i}`)}</Text>;
      })}
    </View>
  );
}
