"""Shared unsupported-feature messages for CVA fail-closed gates."""

MAR50_9_MATERIALITY_POLICY = "MAR50.9_MATERIALITY_THRESHOLD_CCR"
MAR50_9_UNSUPPORTED_MESSAGE = (
    "Materiality-threshold 100% CCR alternative (MAR50.9) is unsupported "
    "because frtb-cva does not own CCR capital inputs or orchestration method election."
)

__all__ = ["MAR50_9_MATERIALITY_POLICY", "MAR50_9_UNSUPPORTED_MESSAGE"]
