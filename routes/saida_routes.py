from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import get_db, formatar_moeda, formatar_data_br

from auth import login_required

bp = Blueprint('saida', __name__)


def _finalizar_entrega(conn, os_row, forma_pagamento):
    """Marca a OS como entregue/paga. Se o cliente já pagou na entrada
    (os_row['forma_pagamento'] já preenchido), o lançamento no caixa já foi
    feito lá - aqui só confirma a retirada, sem duplicar o valor no caixa."""
    cur = conn.cursor()
    hoje = datetime.now().strftime('%Y-%m-%d')

    if os_row['forma_pagamento']:
        cur.execute(
            "UPDATE ordens_servico SET status = 'Pago', data_entrega = %s WHERE id = %s",
            (hoje, os_row['id']),
        )
    else:
        cur.execute(
            "UPDATE ordens_servico SET status = 'Pago', data_entrega = %s, forma_pagamento = %s WHERE id = %s",
            (hoje, forma_pagamento, os_row['id']),
        )
        cur.execute('''
            INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (hoje, 'entrada', f'Pagamento OS {os_row["numero_os"]} - {os_row["cliente_nome"]}',
              'Serviço', os_row['valor_total'], forma_pagamento, os_row['id']))
    conn.commit()
    cur.close()


@bp.route('/saida', methods=['GET', 'POST'])
@login_required
def saida():
    conn = get_db()

    if request.method == 'POST':
        codigo = request.form.get('codigo', '').strip()
        forma_pagamento = request.form.get('forma_pagamento')

        if not codigo:
            flash('Digite o código do cliente!', 'error')
            conn.close()
            return redirect(url_for('saida.saida'))

        cur = conn.cursor()
        cur.execute('''
            SELECT os.*, c.nome as cliente_nome, c.telefone
            FROM ordens_servico os
            JOIN clientes c ON os.cliente_id = c.id
            WHERE os.codigo_seguranca = %s AND os.status IN ('Entrada', 'Pronto')
        ''', (codigo,))
        os_row = cur.fetchone()
        cur.close()

        if not os_row:
            flash('Código não encontrado ou alicate já retirado!', 'error')
            conn.close()
            return redirect(url_for('saida.saida'))

        if not os_row['forma_pagamento'] and not forma_pagamento:
            flash('Selecione a forma de pagamento!', 'error')
            conn.close()
            return redirect(url_for('saida.saida'))

        _finalizar_entrega(conn, os_row, forma_pagamento)
        conn.close()

        flash(f'✅ Pagamento de {formatar_moeda(os_row["valor_total"])} registrado!', 'success')
        return redirect(url_for('saida.saida'))

    busca = request.args.get('busca', '').strip()
    cur = conn.cursor()
    if busca:
        cur.execute('''
            SELECT os.*, c.nome as cliente_nome, c.telefone
            FROM ordens_servico os
            JOIN clientes c ON os.cliente_id = c.id
            WHERE os.status IN ('Entrada', 'Pronto') AND (c.nome ILIKE %s OR c.telefone ILIKE %s)
            ORDER BY os.data_entrada ASC
        ''', (f'%{busca}%', f'%{busca}%'))
    else:
        cur.execute('''
            SELECT os.*, c.nome as cliente_nome, c.telefone
            FROM ordens_servico os
            JOIN clientes c ON os.cliente_id = c.id
            WHERE os.status IN ('Entrada', 'Pronto')
            ORDER BY os.data_entrada ASC
        ''')
    prontos = cur.fetchall()
    cur.close()
    conn.close()

    return render_template('saida.html', prontos=prontos, busca=busca,
                           formatar_moeda=formatar_moeda, formatar_data=formatar_data_br)


@bp.route('/saida/entregar/<int:id>', methods=['POST'])
@login_required
def saida_entregar(id):
    forma_pagamento = request.form.get('forma_pagamento')

    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT os.*, c.nome as cliente_nome, c.telefone
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        WHERE os.id = %s AND os.status IN ('Entrada', 'Pronto')
    ''', (id,))
    os_row = cur.fetchone()
    cur.close()

    if not os_row:
        flash('Ordem não encontrada ou já retirada!', 'error')
        conn.close()
        return redirect(url_for('saida.saida'))

    if not os_row['forma_pagamento'] and not forma_pagamento:
        flash('Selecione a forma de pagamento!', 'error')
        conn.close()
        return redirect(url_for('saida.saida'))

    _finalizar_entrega(conn, os_row, forma_pagamento)
    conn.close()

    flash(f'✅ Entrega de {os_row["cliente_nome"]} registrada! {formatar_moeda(os_row["valor_total"])}', 'success')
    return redirect(url_for('saida.saida'))
