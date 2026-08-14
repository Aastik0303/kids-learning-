import { useCallback } from "react";
import { View } from "react-native";
import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";

import { AvatarFace } from "@/components/avatar/AvatarFace";
import { Button } from "@/components/common/Button";
import { Card } from "@/components/common/Card";
import { FeatureCard } from "@/components/cards/FeatureCard";
import { ResponsiveGrid } from "@/components/responsive/ResponsiveGrid";
import { Screen } from "@/components/common/Screen";
import { Text } from "@/components/common/Text";
import { useTheme } from "@/app/providers/ThemeProvider";
import { useResponsive } from "@/components/responsive/useResponsive";
import { AGE_GROUPS, FEATURES, HOW_IT_WORKS, PARENT_BENEFITS } from "@/features/catalog";
import { track } from "@/services/analytics/analytics";
import { useAuthStore } from "@/store/authStore";
import type { GuestStackParamList, RootStackParamList } from "@/navigation/routes";

type Navigation = NativeStackNavigationProp<GuestStackParamList> &
  NativeStackNavigationProp<RootStackParamList>;

/**
 * The common public home (spec section 2). Identical for everyone, and
 * shows the whole product before asking for anything.
 *
 * Feature taps run the intent-preservation flow: record where the visitor
 * wanted to go, send them through auth and child setup, then land them on
 * that exact destination rather than a generic home.
 */
export function GuestHomeScreen() {
  const theme = useTheme();
  const navigation = useNavigation<Navigation>();
  const { isTablet } = useResponsive();
  const setPendingIntent = useAuthStore((state) => state.setPendingIntent);
  const status = useAuthStore((state) => state.status);

  const openFeature = useCallback(
    (featureId: string, title: string) => {
      track("feature_card_tapped", {
        feature: featureId,
        authenticated: status === "authenticated",
      });

      // Remember the destination before the auth detour.
      setPendingIntent({
        screen: "Classes",
        params: { featureId },
        label: title,
      });

      navigation.navigate("Auth", { screen: "Login" });
    },
    [navigation, setPendingIntent, status],
  );

  const startLearning = useCallback(() => {
    setPendingIntent({ screen: "ChildHome", label: "Start learning" });
    navigation.navigate("Auth", { screen: "SignUp" });
  }, [navigation, setPendingIntent]);

  return (
    <Screen>
      <View style={{ gap: theme.space[8] }}>
        {/* ── Hero ───────────────────────────────────────────────────── */}
        <Card variant="panel" style={{ gap: theme.space[4] }}>
          <View
            style={{
              flexDirection: isTablet ? "row" : "column",
              alignItems: "center",
              gap: theme.space[5],
            }}
          >
            <AvatarFace state="waving" size={isTablet ? 140 : 110} />
            <View style={{ flex: 1, gap: theme.space[3] }}>
              <Text variant="display" align={isTablet ? "left" : "center"}>
                Learn Kids
              </Text>
              <Text variant="bodyLarge" align={isTablet ? "left" : "center"} muted>
                A friendly AI teacher that talks, shows and plays with your child —
                letters, numbers, colours, shapes and more.
              </Text>
            </View>
          </View>

          <View style={{ gap: theme.space[3] }}>
            <Button label="Start learning" icon="🚀" tone="primary" onPress={startLearning} />
            <Button
              label="Explore features"
              icon="✨"
              tone="quiet"
              onPress={() => navigation.navigate("FeatureDemo", { featureId: "alphabets" })}
            />
          </View>
        </Card>

        {/* ── Featured classes ───────────────────────────────────────── */}
        <Section title="What your child will learn" subtitle="Tap any card to see it in action.">
          <ResponsiveGrid columns={{ smallPhone: 1, phone: 2, tablet: 3, largeTablet: 4 }}>
            {FEATURES.map((feature) => (
              <FeatureCard
                key={feature.id}
                featureId={feature.id}
                title={feature.title}
                description={feature.description}
                aiHint={feature.aiHint}
                onPress={() => openFeature(feature.id, feature.title)}
              />
            ))}
          </ResponsiveGrid>
        </Section>

        {/* ── How it works ───────────────────────────────────────────── */}
        <Section title="How it works">
          <ResponsiveGrid columns={{ smallPhone: 1, tablet: 3 }}>
            {HOW_IT_WORKS.map((step) => (
              <Card key={step.title} variant="lift" style={{ gap: theme.space[2], minHeight: 150 }}>
                <Text style={{ fontSize: 38 }}>{step.icon}</Text>
                <Text variant="subheading">{step.title}</Text>
                <Text variant="body" muted>
                  {step.body}
                </Text>
              </Card>
            ))}
          </ResponsiveGrid>
        </Section>

        {/* ── Age groups ─────────────────────────────────────────────── */}
        <Section title="Made for their age" subtitle="The app changes to fit how old your child is.">
          <ResponsiveGrid columns={{ smallPhone: 1, largePhone: 2 }}>
            {AGE_GROUPS.map((group) => (
              <Card
                key={group.id}
                variant="tinted"
                tint={group.id === "toddler" ? theme.palette.sunLight : theme.palette.leafLight}
                style={{ gap: theme.space[2], minHeight: 160 }}
              >
                <Text style={{ fontSize: 36 }}>{group.icon}</Text>
                <Text variant="overline" muted>
                  {group.label}
                </Text>
                <Text variant="subheading">{group.title}</Text>
                <Text variant="body" muted>
                  {group.body}
                </Text>
              </Card>
            ))}
          </ResponsiveGrid>
        </Section>

        {/* ── Parent benefits ────────────────────────────────────────── */}
        <Section title="For grown-ups">
          <ResponsiveGrid columns={{ smallPhone: 1, largePhone: 2, tablet: 4 }}>
            {PARENT_BENEFITS.map((benefit) => (
              <Card key={benefit.title} variant="lift" style={{ gap: theme.space[1], minHeight: 140 }}>
                <Text style={{ fontSize: 30 }}>{benefit.icon}</Text>
                <Text variant="subheading">{benefit.title}</Text>
                <Text variant="body" muted>
                  {benefit.body}
                </Text>
              </Card>
            ))}
          </ResponsiveGrid>
        </Section>

        {/* ── Closing CTA ────────────────────────────────────────────── */}
        <Card variant="panel" style={{ gap: theme.space[4], alignItems: "center" }}>
          <Text style={{ fontSize: 44 }}>🎈</Text>
          <Text variant="heading" align="center">
            Ready to start?
          </Text>
          <Text variant="body" align="center" muted>
            Set up a profile in under a minute.
          </Text>
          <Button label="Start learning" icon="🚀" tone="primary" onPress={startLearning} />
          <Button
            label="I already have an account"
            tone="quiet"
            onPress={() => navigation.navigate("Auth", { screen: "Login" })}
          />
        </Card>
      </View>
    </Screen>
  );
}

function Section({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  const theme = useTheme();
  return (
    <View style={{ gap: theme.space[4] }}>
      <View style={{ gap: theme.space[1] }}>
        <Text variant="title">{title}</Text>
        {subtitle ? (
          <Text variant="body" muted>
            {subtitle}
          </Text>
        ) : null}
      </View>
      {children}
    </View>
  );
}
