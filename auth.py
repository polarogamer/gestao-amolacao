"""Autenticação: decorator de login e helpers de senha (com hash, nada de texto puro)."""
from functools import wraps
from flask import session, redirect, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash


def hash_senha(senha_texto_puro):
    return generate_password_hash(senha_texto_puro)


def verificar_senha(senha_hash, senha_texto_puro):
    return check_password_hash(senha_hash, senha_texto_puro)


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario_id' not in session:
            flash('Por favor, faça login para acessar esta página.', 'warning')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated_function
