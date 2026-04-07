from dataclasses import dataclass
from typing import Literal, List

ProcessingMode = Literal["fast", "standard", "forensic"]


@dataclass
class ProcessingDecision:
    mode: ProcessingMode
    reasons: List[str]


def decide_processing_mode(sig) -> ProcessingDecision:
    reasons = []

    if sig.media_type != "documento":
        return ProcessingDecision("standard", ["non_document"])

    if (
        sig.page_count <= 2
        and sig.has_native_text
        and (sig.rotation == 0)
    ):
        return ProcessingDecision("fast", ["simple_pdf"])

    if sig.rotation and abs(sig.rotation) > 0:
        return ProcessingDecision("forensic", ["rotated_doc"])

    return ProcessingDecision("standard", ["default"])