"""
Ponto de entrada usado pela Vercel (Python runtime serverless).
A Vercel procura por uma variável `app` do tipo WSGI aqui dentro.
"""
import sys
import os

# Garante que o diretório raiz do projeto (onde estão app.py, db.py, routes/) está no path.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app  # noqa: E402
