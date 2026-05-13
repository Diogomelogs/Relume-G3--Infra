import sys
from pathlib import Path
from typing import Literal, Optional

import whisper


ModelName = Literal["tiny", "base", "small", "medium", "large"]


def load_model(name: ModelName = "small"):
    """
    Carrega o modelo Whisper.

    tiny/base: mais rápido, menos qualidade
    small/medium/large: mais lento, bem mais qualidade
    """
    print(f"[whisper] Carregando modelo: {name}")
    model = whisper.load_model(name)
    return model


def transcribe_file(
    model,
    audio_path: Path,
    language: Optional[str] = "pt",
    verbose: bool = False,
):
    """
    Transcreve um arquivo de áudio usando Whisper.

    language="pt" força português; use None para auto-detecção.
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")

    print(f"[whisper] Transcrevendo: {audio_path}")
    result = model.transcribe(
        str(audio_path),
        language=language,  # pode ser None para auto
        verbose=verbose,
    )
    return result


def main():
    if len(sys.argv) < 2:
        print("Uso: python transcribe_audio.py caminho/do/arquivo.m4a [modelo]")
        print("Exemplo: python transcribe_audio.py meu_audio.m4a small")
        sys.exit(1)

    audio_path = Path(sys.argv[1])

    # modelo opcional via CLI, default = small
    model_name: ModelName = "small"
    if len(sys.argv) >= 3:
        model_name_cli = sys.argv[2].lower()
        if model_name_cli in {"tiny", "base", "small", "medium", "large"}:
            model_name = model_name_cli  # type: ignore
        else:
            print(f"[whisper] Modelo desconhecido '{model_name_cli}', usando 'small'.")

    try:
        model = load_model(model_name)
        result = transcribe_file(model, audio_path, language="pt", verbose=False)
    except Exception as e:
        print(f"[whisper] Erro ao transcrever: {e}")
        sys.exit(1)

    text = (result or {}).get("text", "").strip()

    print("\n=== TRANSCRIÇÃO ===\n")
    if not text:
        print("(sem texto retornado)")
        sys.exit(0)

    print(text)

    # Se quiser ver segmentos com timestamps, descomenta abaixo:
    # segments = result.get("segments") or []
    # if segments:
    #     print("\n=== SEGMENTOS ===\n")
    #     for seg in segments:
    #         ini = seg.get("start")
#         fim = seg.get("end")
    #         txt = seg.get("text", "").strip()
    #         print(f"[{ini:6.2f} -> {fim:6.2f}] {txt}")


if __name__ == "__main__":
    main()
