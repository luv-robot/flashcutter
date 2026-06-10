from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from template_element_miner.utils.image_io import read_image


def phash_image(image: np.ndarray, hash_size: int = 8, highfreq_factor: int = 4) -> str:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    size = hash_size * highfreq_factor
    resized = cv2.resize(gray, (size, size), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    low_freq = dct[:hash_size, :hash_size]
    flattened = low_freq.flatten()
    median = np.median(flattened[1:]) if len(flattened) > 1 else np.median(flattened)
    bits = flattened > median
    value = 0
    for bit in bits:
        value = (value << 1) | int(bool(bit))
    return f"{value:0{hash_size * hash_size // 4}x}"


def phash_path(path: Path) -> str:
    return phash_image(read_image(path))


def hamming_distance(hash_a: Optional[str], hash_b: Optional[str]) -> int:
    if not hash_a or not hash_b:
        return 64
    return (int(hash_a, 16) ^ int(hash_b, 16)).bit_count()
