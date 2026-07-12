from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import get_db, formatar_moeda, parse_valor, parse_inteiro
from auth import login_required

bp = Blueprint('consumiveis', __name__)


@bp.route('/consumiveis')
@login_required
def consumiveis():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM consumiveis ORDER BY nome")
    items = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('consumiveis.html', consumiveis=items, formatar_moeda=formatar_moeda)


@bp.route('/consumiveis/adicionar', methods=['POST'])
@login_required
def consumivel_adicionar():
    nome = request.form.get('nome', '').strip()
    if not nome:
        flash('Nome do insumo é obrigatório!', 'error')
        return redirect(url_for('consumiveis.consumiveis'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO consumiveis (nome, quantidade, unidade, estoque_minimo, preco_unitario)
        VALUES (%s, %s, %s, %s, %s)
    ''', (
        nome, parse_inteiro(request.form.get('quantidade'), 0),
        request.form.get('unidade', 'un'), parse_inteiro(request.form.get('estoque_minimo'), 5),
        parse_valor(request.form.get('preco_unitario')),
    ))
    conn.commit()
    cur.close()
    conn.close()
    flash('Insumo adicionado!', 'success')
    return redirect(url_for('consumiveis.consumiveis'))


# NOVO: rota que faltava - o template consumivel_editor.html já existia mas nunca
# tinha uma rota para servi-lo. Agora dá para editar um insumo já cadastrado.
@bp.route('/consumiveis/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def consumivel_editar(id):
    conn = get_db()
    cur = conn.cursor()

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        if not nome:
            flash('Nome do insumo é obrigatório!', 'error')
            cur.close()
            conn.close()
            return redirect(url_for('consumiveis.consumivel_editar', id=id))

        cur.execute('''
            UPDATE consumiveis SET nome = %s, quantidade = %s, unidade = %s,
                                    estoque_minimo = %s, preco_unitario = %s
            WHERE id = %s
        ''', (
            nome, parse_inteiro(request.form.get('quantidade'), 0),
            request.form.get('unidade', 'un'), parse_inteiro(request.form.get('estoque_minimo'), 5),
            parse_valor(request.form.get('preco_unitario')), id,
        ))
        conn.commit()
        cur.close()
        conn.close()
        flash('Insumo atualizado!', 'success')
        return redirect(url_for('consumiveis.consumiveis'))

    cur.execute("SELECT * FROM consumiveis WHERE id = %s", (id,))
    item = cur.fetchone()
    cur.close()
    conn.close()
    if not item:
        flash('Insumo não encontrado!', 'error')
        return redirect(url_for('consumiveis.consumiveis'))
    return render_template('consumivel_editor.html', item=item)


@bp.route('/consumiveis/usar/<int:id>', methods=['POST'])
@login_required
def consumivel_usar(id):
    quantidade = parse_inteiro(request.form.get('quantidade'), 0)
    if quantidade < 1:
        flash('Quantidade inválida!', 'error')
        return redirect(url_for('consumiveis.consumiveis'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE consumiveis SET quantidade = quantidade - %s WHERE id = %s", (quantidade, id))
    conn.commit()
    cur.close()
    conn.close()
    flash('Insumo utilizado!', 'success')
    return redirect(url_for('consumiveis.consumiveis'))


@bp.route('/consumiveis/excluir/<int:id>')
@login_required
def consumivel_excluir(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM consumiveis WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Insumo excluído!', 'success')
    return redirect(url_for('consumiveis.consumiveis'))
