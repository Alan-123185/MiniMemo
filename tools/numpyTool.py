import numpy as np

def cosine_similarity(a: list[float], b: list[float]) -> float:
    a, b = np.asarray(a), np.asarray(b)
    return float(a @ b / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))