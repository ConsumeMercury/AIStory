"""Mock narrator for offline tests."""

from simulation import narrator_protocol


class MockNarrator:
    def __init__(self, text="[scene ok]"):
        self.text = text
        self.calls = []

    def generate_scene(self, **kwargs):
        self.calls.append(kwargs)
        return self.text


def mock_narrator(text="[scene ok]"):
    """Install a mock narrator; returns the mock instance."""
    mock = MockNarrator(text)
    narrator_protocol.set_narrator(mock)
    return mock


def reset_narrator():
    narrator_protocol.reset_narrator()
