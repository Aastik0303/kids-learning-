import { Component, type ErrorInfo, type ReactNode } from "react";
import { Pressable, Text, View } from "react-native";

import { captureException } from "@/services/analytics/crash";
import { colors, palette } from "@/theme/colors";

type Props = { children: ReactNode };
type State = { error: Error | null };

/**
 * Global error boundary (spec section 20).
 *
 * Deliberately built from raw RN primitives and static token imports —
 * no theme hook, no design-system components. If the theme provider is
 * what crashed, a fallback that depends on it would crash too.
 *
 * The copy is child-safe: a small child may be the one looking at this.
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    captureException(error, { componentStack: info.componentStack });
  }

  private reset = () => {
    this.setState({ error: null });
  };

  render() {
    if (!this.state.error) return this.props.children;

    return (
      <View
        style={{
          flex: 1,
          alignItems: "center",
          justifyContent: "center",
          gap: 20,
          backgroundColor: palette.paper,
          padding: 32,
        }}
      >
        <Text style={{ fontSize: 64 }}>🐻</Text>
        <Text
          style={{
            fontSize: 26,
            fontWeight: "900",
            color: colors.text,
            textAlign: "center",
          }}
        >
          Oops! Let us start again.
        </Text>
        <Text
          style={{
            fontSize: 16,
            fontWeight: "700",
            color: colors.textSecondary,
            textAlign: "center",
          }}
        >
          Something went wrong. Tap the button to go back.
        </Text>

        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Start again"
          onPress={this.reset}
          style={{
            minHeight: 64,
            justifyContent: "center",
            borderRadius: 32,
            backgroundColor: colors.primary,
            paddingHorizontal: 32,
          }}
        >
          <Text style={{ fontSize: 19, fontWeight: "900", color: colors.primaryOn }}>
            Start again
          </Text>
        </Pressable>

        {__DEV__ ? (
          <Text style={{ fontSize: 11, color: colors.textMuted, textAlign: "center" }}>
            {this.state.error.message}
          </Text>
        ) : null}
      </View>
    );
  }
}
