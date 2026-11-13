import numpy as np

def cosine_similarity(a: list[float]|bytes , b: list[float]|bytes) -> float:
    if isinstance(a, bytes):
        a = np.frombuffer(a, dtype=np.float32)
    if isinstance(b, bytes):
        b = np.frombuffer(b, dtype=np.float32)
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))