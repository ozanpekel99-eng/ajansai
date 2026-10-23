import { router } from "expo-router";
import { ScrollView } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Button, Card, T } from "@/components/ui";
import { colors } from "@/lib/theme";

// Meta reklam verme ekranı bir sonraki adımda (Meta uygulama onayıyla birlikte) tamamlanacak.
export default function Reklam() {
  return (
    <SafeAreaView style={{ flex: 1, backgroundColor: colors.bg }} edges={["top"]}>
      <ScrollView contentContainerStyle={{ padding: 18, gap: 16 }}>
        <T variant="h2">Reklam</T>
        <Card style={{ gap: 12 }}>
          <T variant="h3">Tek tıkla Instagram reklamı</T>
          <T variant="muted">Ürettiğin görsel ya da videoyu seç, bütçeni ve bölgeni belirle; reklamın Instagram'da yayına girsin.</T>
          <Button title="Önce bir görsel ya da video üret" onPress={() => router.push("/uret")} />
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}
