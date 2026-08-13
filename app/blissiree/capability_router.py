from dataclasses import dataclass

from .schemas import ConversationContext


CAPABILITY_LABELS = {
    "RECEPTION": "Reception",
    "PLATFORM_INFORMATION": "Platform information",
    "DISCUSSION": "Discussion",
    "CONTENT_MATCHING": "Content matching",
    "BOOKING": "Booking",
    "SAFETY": "Safety",
}


@dataclass(frozen=True)
class CapabilityRoute:
    active_agent: str
    previous_agent: str | None
    confidence: float
    reason: str

    @property
    def label(self) -> str:
        return CAPABILITY_LABELS[self.active_agent]


def previous_capability(history: list[dict]) -> str | None:
    for item in reversed(history[-10:]):
        value=str(item.get("active_agent","")).upper()
        if value in CAPABILITY_LABELS:return value
    return None


def route_capability(context:ConversationContext,history:list[dict],*,safety_override:bool=False,terminal:bool=False) -> CapabilityRoute:
    previous=previous_capability(history)
    if safety_override:return CapabilityRoute("SAFETY",previous,1.0,"safety override")
    if terminal:return CapabilityRoute("RECEPTION",previous,1.0,"natural closure or boundary")
    target={
        "PRODUCT_INFORMATION":"PLATFORM_INFORMATION",
        "RESOURCE_GUIDANCE":"CONTENT_MATCHING",
        "CONSULTATION_BOOKING":"BOOKING",
        "COMPANION_SUPPORT":"DISCUSSION",
        "FEEDBACK":"DISCUSSION",
        "REFUSAL":"DISCUSSION",
        "OUT_OF_SCOPE":"RECEPTION",
    }.get(context.intent,"DISCUSSION")
    return CapabilityRoute(target,previous,max(context.confidence,.5),f"resolved intent: {context.intent.lower()}")


def public_agent(route:CapabilityRoute) -> dict:
    return {"id":route.active_agent,"label":route.label,"previous":route.previous_agent}
