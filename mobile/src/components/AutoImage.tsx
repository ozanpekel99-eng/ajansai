import { Image } from "expo-image";
import { useState } from "react";
import { StyleProp, ViewStyle } from "react-native";

import { colors } from "@/lib/theme";

/** Görseli kendi en-boy oranıyla gösterir (dikey kampanya görselleri kırpılmaz). */
export default function AutoImage({ uri, style, maxRatio = 1.78 }: { uri: string; style?: StyleProp<ViewStyle>; maxRatio?: number }) {
  const [ratio, setRatio] = useState(1);
  return (
    <Image
      source={{ uri }}
      onLoad={(e) => e.source.width && setRatio(e.source.width / e.source.height)}
      style={[{ width: "100%", aspectRatio: Math.max(ratio, 1 / maxRatio), borderRadius: 14, backgroundColor: colors.surface }, style as any]}
      contentFit="contain"
      transition={200}
    />
  );
}
