from dataclasses import dataclass

_DETECTORS = []


@dataclass
class Finding:
    name: str
    category: str
    confidence: int
    evidence: str
    clue: str
    layers: int = 1

    def to_dict(self):
        return {
            "name": self.name,
            "category": self.category,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "clue": self.clue,
            "layers": self.layers,
        }


def register(fn):
    _DETECTORS.append(fn)
    return fn


def all_detectors():
    return list(_DETECTORS)


def clear_registry():
    _DETECTORS.clear()
