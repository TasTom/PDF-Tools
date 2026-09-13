"""Rend le paquet `app` importable quel que soit le repertoire d'invocation.

Sans cela, `pytest` insere le dossier `tests/` dans `sys.path` et non `backend/` :
`import app` echouerait selon l'endroit d'ou la commande est lancee.
"""
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
