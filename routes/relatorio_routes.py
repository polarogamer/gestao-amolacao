from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import get_db, formatar_moeda, formatar_data_br, agora_br, datetime_br
from auth import login_required

bp = Blueprint('relatorio', __name__)


@bp.route('/relatorio')
@login_required
def relatorio():
    hoje = agora_br().strftime('%Y-%m-%d')
    conn = get_db()
    cur = conn.cursor()

    cur.execute('''
        SELECT os.*, c.nome as cliente_nome
        FROM ordens_servico os JOIN clientes c ON os.cliente_id = c.id
        WHERE os.data_entrada = %s ORDER BY os.id ASC
    ''', (hoje,))
    entradas = cur.fetchall()

    cur.execute('''
        SELECT os.*, c.nome as cliente_nome
        FROM ordens_servico os JOIN clientes c ON os.cliente_id = c.id
        WHERE os.data_entrega = %s AND os.status = 'Pago' ORDER BY os.id ASC
    ''', (hoje,))
    saidas = cur.fetchall()

    cur.execute('''
        SELECT os.*, c.nome as cliente_nome, c.telefone
        FROM ordens_servico os JOIN clientes c ON os.cliente_id = c.id
        WHERE os.status != 'Pago' ORDER BY os.data_entrada ASC
    ''')
    pendentes = cur.fetchall()

    cur.execute(
        "SELECT COALESCE(SUM(valor), 0) AS s FROM movimentacoes_caixa "
        "WHERE tipo='entrada' AND data = %s AND categoria != 'Abertura'",
        (hoje,),
    )
    total_faturado = cur.fetchone()['s'] or 0

    cur.execute("SELECT * FROM vendas_alicates WHERE status = 'pago' AND data_pagamento = %s ORDER BY id DESC", (hoje,))
    vendas_hoje = cur.fetchall()

    cur.execute("SELECT * FROM fechamentos_diarios WHERE data = %s", (hoje,))
    ja_fechado_hoje = cur.fetchone()

    cur.execute("SELECT * FROM fechamentos_diarios ORDER BY data DESC LIMIT 14")
    historico = cur.fetchall()

    cur.close()
    conn.close()
    return render_template(
        'relatorio.html', entradas=entradas, saidas=saidas, pendentes=pendentes,
        total_faturado=total_faturado, vendas_hoje=vendas_hoje, ja_fechado_hoje=ja_fechado_hoje,
        historico=historico, formatar_moeda=formatar_moeda, formatar_data=formatar_data_br, datetime=datetime_br,
    )


@bp.route('/relatorio/fechar', methods=['POST'])
@login_required
def relatorio_fechar():
    hoje = agora_br().strftime('%Y-%m-%d')
    conn = get_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM fechamentos_diarios WHERE data = %s", (hoje,))
    if cur.fetchone():
        flash('O dia de hoje já foi fechado!', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('relatorio.relatorio'))

    cur.execute("SELECT COALESCE(SUM(quantidade), 0) AS c FROM ordens_servico WHERE data_entrada = %s", (hoje,))
    total_entradas = cur.fetchone()['c'] or 0

    cur.execute("SELECT COALESCE(SUM(quantidade), 0) AS c FROM ordens_servico WHERE data_entrega = %s AND status = 'Pago'", (hoje,))
    total_saidas = cur.fetchone()['c'] or 0

    cur.execute(
        "SELECT COALESCE(SUM(valor), 0) AS s FROM movimentacoes_caixa "
        "WHERE tipo='entrada' AND data = %s AND categoria != 'Abertura'",
        (hoje,),
    )
    faturamento_dia = cur.fetchone()['s'] or 0

    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE status != 'Pago'")
    pendentes = cur.fetchone()['c'] or 0

    cur.execute('''
        INSERT INTO fechamentos_diarios (data, total_entradas, total_saidas, faturamento_dia, pendentes, fechado_em)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (hoje, total_entradas, total_saidas, faturamento_dia, pendentes, agora_br().strftime('%Y-%m-%d %H:%M:%S')))

    # Limpa OS já pagas/retiradas e clientes sem pendências (mesmo comportamento do sistema original)
    cur.execute("DELETE FROM ordens_servico WHERE status = 'Pago'")
    cur.execute("DELETE FROM clientes WHERE id NOT IN (SELECT DISTINCT cliente_id FROM ordens_servico WHERE cliente_id IS NOT NULL)")

    conn.commit()
    cur.close()
    conn.close()

    flash(f'✅ Dia fechado! {total_entradas} entradas, {total_saidas} saídas, '
          f'{formatar_moeda(faturamento_dia)} faturados. Clientes já pagos foram removidos do banco.', 'success')
    return redirect(url_for('relatorio.relatorio'))
