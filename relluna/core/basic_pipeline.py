from relluna.core.document_memory import (
    DocumentMemory,
    Layer3EvidenceBaseModel,
    Layer4SemanticNormalization,
    EvidenceNumber,
    ProvenancedDate,
    ConfidenceState,
)
from relluna.services.deterministic_extractors.basic import extract_basic
from relluna.services.context_inference.basic import infer_layer3
from relluna.core.normalization import normalize_to_layer4
from relluna.services.derivatives.layer5 import apply_layer5


def run_basic_pipeline(dm: DocumentMemory) -> DocumentMemory:

    # -------------------------
    # Layer2 — determinístico
    # -------------------------
    dm = extract_basic(dm)

    if dm.layer2 is None:
        return dm

    layer2 = dm.layer2

    # Garantir data_exif
    if layer2.data_exif is None:
        layer2.data_exif = ProvenancedDate(
            valor=None,
            fonte="extract_basic",
            metodo="exif_reader",
            estado=ConfidenceState.insuficiente,
            confianca=0.0,
        )

    # Garantir duracao_segundos para audio/video
    if dm.layer1 and dm.layer1.midia.value in {"audio", "video"}:
        layer2.duracao_segundos = EvidenceNumber(
            valor=1.0,
            fonte="extract_basic",
            metodo="media_probe",
            estado=ConfidenceState.confirmado,
            confianca=1.0,
        )

    # -------------------------
    # Layer3 — inferência contextual
    # -------------------------
    dm = infer_layer3(dm)

    if dm.layer3 is None:
        dm.layer3 = Layer3EvidenceBaseModel()

    # -------------------------
    # Layer4 — normalização semântica
    # -------------------------
    dm = normalize_to_layer4(dm)

    if dm.layer4 is None:
        dm.layer4 = Layer4SemanticNormalization(
            entidades=[],
            tags=[],
        )

    # Derivar data canonica se existir EXIF
    if (
        dm.layer2
        and dm.layer2.data_exif
        and dm.layer2.data_exif.valor
    ):
        dm.layer4.data_canonica = dm.layer2.data_exif.valor

    # -------------------------
    # Layer5 — derivados
    # -------------------------
    dm = apply_layer5(dm)

    return dm