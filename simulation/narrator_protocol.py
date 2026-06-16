"""
Narrator interface — swap Gemini for mocks in tests.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class SceneNarrator(Protocol):
    def generate_scene(self, **kwargs) -> str:
        ...


_default_narrator = None


def get_narrator():
    global _default_narrator
    if _default_narrator is None:
        from simulation.narrator import generate_scene

        class _GeminiNarrator:
            def generate_scene(self, **kwargs):
                return generate_scene(**kwargs)

        _default_narrator = _GeminiNarrator()
    return _default_narrator


def set_narrator(narrator: SceneNarrator):
    global _default_narrator
    _default_narrator = narrator


def reset_narrator():
    global _default_narrator
    _default_narrator = None
