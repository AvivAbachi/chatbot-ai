// Adapted from the Astryx ai-chat page template (Meta Platforms, Inc. and affiliates).
import { Sparkle } from "lucide-react";

export function Spark({ large = false }: { large?: boolean }) {
  return (
    <Sparkle
      className={large ? "spark spark-large" : "spark"}
      fill="currentColor"
      strokeWidth={0}
      aria-hidden="true"
    />
  );
}
