from flask import Blueprint, render_template, request, redirect, url_for, flash, session
import psycopg2

from db import get_db
from auth import hash_senha, verificar_senha

bp = Blueprint('auth', __name__)


@bp.route('/')
def index():
    if 'usuario_id' in session:
        return redirect(url_for('dashboard.dashboard'))
    return redirect(url_for('auth.login'))


@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '')

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM usuarios WHERE usuario = %s", (usuario,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user and verificar_senha(user['senha_hash'], senha):
            session['usuario_id'] = user['id']
            session['usuario'] = user['usuario']
            session['nome'] = user['nome']
            flash(f'Bem-vindo, {user["nome"]}!', 'success')
            return redirect(url_for('dashboard.dashboard'))
        else:
            flash('Usuário ou senha incorretos!', 'error')

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM usuarios")
    tem_usuario = cur.fetchone()['c'] > 0
    cur.close()
    conn.close()
    return render_template('login.html', tem_usuario=tem_usuario)


@bp.route('/cadastrar', methods=['GET', 'POST'])
def cadastrar():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM usuarios")
    tem_usuario = cur.fetchone()['c'] > 0
    cur.close()
    conn.close()

    if tem_usuario:
        flash('Já existe um usuário cadastrado!', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        usuario = request.form.get('usuario', '').strip()
        senha = request.form.get('senha', '')
        confirmar = request.form.get('confirmar', '')

        if not nome or not usuario or not senha:
            flash('Preencha todos os campos!', 'error')
            return render_template('cadastrar.html')

        if senha != confirmar:
            flash('As senhas não coincidem!', 'error')
            return render_template('cadastrar.html')

        if len(senha) < 4:
            flash('A senha deve ter pelo menos 4 caracteres!', 'error')
            return render_template('cadastrar.html')

        conn = get_db()
        cur = conn.cursor()
        try:
            cur.execute(
                "INSERT INTO usuarios (nome, usuario, senha_hash) VALUES (%s, %s, %s)",
                (nome, usuario, hash_senha(senha)),
            )
            conn.commit()
            flash('Usuário cadastrado com sucesso! Faça login.', 'success')
            return redirect(url_for('auth.login'))
        except psycopg2.IntegrityError:
            conn.rollback()
            flash('Nome de usuário já existe!', 'error')
        finally:
            cur.close()
            conn.close()

    return render_template('cadastrar.html')


@bp.route('/logout')
def logout():
    session.clear()
    flash('Deslogado com sucesso!', 'success')
    return redirect(url_for('auth.login'))
