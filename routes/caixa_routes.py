from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import get_db, formatar_moeda, formatar_data_br, parse_valor, agora_br
from auth import login_required

bp = Blueprint('caixa', __name__)


@bp.route('/caixa')
@login_required
def caixa():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM movimentacoes_caixa ORDER BY data DESC, id DESC LIMIT 100")
    movs = cur.fetchall()
    cur.execute(
        "SELECT COALESCE(SUM(CASE WHEN tipo='entrada' THEN valor ELSE -valor END), 0) AS s "
        "FROM movimentacoes_caixa"
    )
    saldo = cur.fetchone()['s'] or 0
    cur.close()
    conn.close()
    return render_template('caixa.html', movimentacoes=movs, saldo=saldo,
                           formatar_moeda=formatar_moeda, formatar_data=formatar_data_br)


@bp.route('/caixa/lancar', methods=['POST'])
@login_required
def caixa_lancar():
    tipo = request.form.get('tipo')
    descricao = request.form.get('descricao', '').strip()
    valor = parse_valor(request.form.get('valor'))

    if not descricao or valor <= 0:
        flash('Informe uma descrição e um valor válido!', 'error')
        return redirect(url_for('caixa.caixa'))

    agora = agora_br()
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, hora)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (
        agora.strftime('%Y-%m-%d'), tipo, descricao,
        request.form.get('categoria', 'Outros'), valor,
        request.form.get('forma_pagamento', 'Dinheiro'), agora.strftime('%H:%M'),
    ))
    conn.commit()
    cur.close()
    conn.close()
    flash('Movimento lançado!', 'success')
    return redirect(url_for('caixa.caixa'))


@bp.route('/caixa/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def caixa_editar(id):
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        cur.execute('''
            UPDATE movimentacoes_caixa SET
                tipo = %s, descricao = %s, categoria = %s, valor = %s, forma_pagamento = %s
            WHERE id = %s
        ''', (
            request.form.get('tipo'), request.form.get('descricao', '').strip(),
            request.form.get('categoria', 'Outros'), parse_valor(request.form.get('valor')),
            request.form.get('forma_pagamento', 'Dinheiro'), id,
        ))
        conn.commit()
        cur.close()
        conn.close()
        flash('Movimentação atualizada!', 'success')
        return redirect(url_for('caixa.caixa'))

    cur.execute("SELECT * FROM movimentacoes_caixa WHERE id = %s", (id,))
    mov = cur.fetchone()
    cur.close()
    conn.close()
    if not mov:
        flash('Movimentação não encontrada!', 'error')
        return redirect(url_for('caixa.caixa'))
    return render_template('caixa_editor.html', mov=mov)


@bp.route('/caixa/excluir/<int:id>')
@login_required
def caixa_excluir(id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM movimentacoes_caixa WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Movimento excluído!', 'success')
    return redirect(url_for('caixa.caixa'))
