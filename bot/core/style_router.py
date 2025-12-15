from dataclasses import dataclass
from typing import Optional

from bot.config import RouterConfig, StyleConfig


@dataclass
class StyleDecision:
    style_id: str
    confidence: float
    reason: str
    manual: bool = False


class StyleRouter:
    def __init__(self, router_config: RouterConfig, styles: dict[str, StyleConfig]):
        self.router_config = router_config
        self.styles = styles

    def decide(
        self,
        content: str,
        manual_style: Optional[str] = None,
    ) -> StyleDecision:
        if manual_style and manual_style in self.styles:
            return StyleDecision(
                style_id=manual_style,
                confidence=1.0,
                reason="manual_override",
                manual=True,
            )

        text = content.lower()
        score = {}
        score["techie"] = sum(
            kw in text
            for kw in ["debug", "代码", "bug", "算法", "deploy", "api", "server"]
        )
        score["warm"] = sum(
            kw in text for kw in ["谢谢", "辛苦", "开心", "抱抱", "love", "困", "emo"]
        )
        score["snark"] = sum(
            kw in text for kw in ["无语", "离谱", "真的假的", "吐槽", "？", "??", "lol"]
        )
        score["formal"] = sum(
            kw in text
            for kw in ["请", "麻烦", "安排", "文档", "确认", "合同", "报告", "通知"]
        )

        best_style = self.router_config.default_style
        best_score = 0
        for style_id, sc in score.items():
            if sc > best_score:
                best_score = sc
                best_style = style_id

        confidence = min(1.0, 0.2 + best_score * 0.2)
        if confidence < self.router_config.confidence_threshold:
            return StyleDecision(
                style_id=self.router_config.fallback_style,
                confidence=confidence,
                reason="low_confidence",
            )

        if best_style not in self.styles:
            best_style = self.router_config.fallback_style
            confidence = 0.2
        return StyleDecision(
            style_id=best_style,
            confidence=confidence,
            reason="rule_match",
        )
