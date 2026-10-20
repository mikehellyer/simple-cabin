import sys
from unittest.mock import patch

from simple_cabin import app


def test_self_test_passes():
    with patch.object(sys, "argv", ["Simple-Cabin", "--self-test"]):
        assert app.main() == 0
