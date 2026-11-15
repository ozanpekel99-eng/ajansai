import { ActivityIndicator, Pressable, StyleSheet, View } from "react-native";

import { T } from "@/components/ui";
import { usePricing } from "@/lib/plans";
import { colors, fonts, radius } from "@/lib/theme";
import { FEATURED_PLAN, LIMIT_TITLE, LimitReason, money, orderedPlans, planMeta } from "@/lib/upgrade";

/**
 * Ücretsiz hak dolunca sohbette paketleri gösterir (web `UpgradeCard` karşılığı).
 * onPick: paket seçilince çağrılır (uygulama içi satın alma gelene kadar bilgi mesajı gösterilir).
 */
export default function UpgradeCard({ reason, onPick }: { reason: LimitReason; onPick: (planId: string) => void }) {
  const pricing = usePricing();
  const plans = orderedPlans(pricing);
  const free = pricing?.free;

  return (
    <View style={st.card} accessibilityLabel="Paketler">
      <View style={{ gap: 4 }}>
        <T style={{ fontFamily: fonts.bodySemi }}>{LIMIT_TITLE[reason]}</T>
        <T variant="muted">Paketle kaldığın yerden devam et: aynı kalitede görsel, sınırsız sohbet, video ve Instagram reklamı.</T>
      </View>
      {!pricing ? (
        <ActivityIndicator color={colors.indigoSoft} style={{ paddingVertical: 12 }} />
      ) : (
        plans.map((p) => {
          const featured = p.id === FEATURED_PLAN;
          return (
            <View key={p.id} style={[st.plan, featured && st.featured]}>
              {featured ? <T variant="small" style={st.tag}>En çok tercih edilen</T> : null}
              <View style={st.planHead}>
                <T variant="h3">{p.name}</T>
                <T style={{ fontFamily: fonts.bodySemi }}>
                  {money(p.price, p.currency)} <T variant="small" style={{ color: colors.muted }}>/ ay + KDV</T>
                </T>
              </View>
              <T variant="small" style={{ color: colors.muted }}>{planMeta(p)}</T>
              <Pressable
                accessibilityRole="button"
                onPress={() => onPick(p.id)}
                style={({ pressed }) => [st.btn, featured ? st.btnPrimary : st.btnLight, pressed && { opacity: 0.8 }]}
              >
                <T style={[st.btnText, !featured && { color: colors.bg }]}>{p.name} paketini al</T>
              </Pressable>
            </View>
          );
        })
      )}
      {reason === "chat" && free ? (
        <T variant="small" style={{ color: colors.faint }}>
          Paket almadan da yarın devam edebilirsin: günde {free.chat_per_day} mesaj, ayda {free.images_per_month} görsel ücretsiz.
        </T>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  card: { gap: 12, padding: 14, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  plan: { gap: 6, padding: 12, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface2 },
  featured: { borderColor: colors.indigo },
  tag: { alignSelf: "flex-start", color: colors.indigoSoft, fontFamily: fonts.bodySemi },
  planHead: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline", gap: 8 },
  btn: { marginTop: 4, minHeight: 42, borderRadius: radius.md, alignItems: "center", justifyContent: "center", paddingHorizontal: 14 },
  btnPrimary: { backgroundColor: colors.indigo },
  btnLight: { backgroundColor: colors.white },
  btnText: { fontFamily: fonts.bodySemi, fontSize: 15, color: colors.white },
});
