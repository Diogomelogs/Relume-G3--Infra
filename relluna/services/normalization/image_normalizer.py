from pathlib import Path
from PIL import Image
import pillow_heif
import uuid

pillow_heif.register_heif_opener()

def normalize_image(input_path: Path) -> Path:
    img = Image.open(input_path)

    # Converter para RGB sempre
    if img.mode != "RGB":
        img = img.convert("RGB")

    output_path = input_path.parent / f"{uuid.uuid4()}_normalized.png"
    img.save(output_path, format="PNG", optimize=True)

    return output_path