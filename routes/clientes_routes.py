from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import get_db, formatar_data_br, agora_br, datetime_br
from auth import login_required

bp = Blueprint('clientes', __name__)


@bp.route('/clientes')
@login_required
def clientes():
    """Clientes do dia: pedidos de hoje que ainda não foram pagos/retirados.
    Some da lista sozinho assim que o cliente paga na Saída."""
    hoje = agora_br().strftime('%Y-%m-%d')
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT os.*, c.nome as cliente_nome, c.telefone
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        WHERE os.data_entrada = %s AND os.status != 'Pago'
        ORDER BY os.id ASC
    ''', (hoje,))
    pedidos_hoje = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('clientes.html', pedidos=pedidos_hoje, formatar_data=formatar_data_br, datetime=datetime_br)


@bp.route('/clientes/excluir/<int:id>')
@login_required
def excluir_pedido(id):
    """Exclui um pedido, pago ou não (limpeza manual, ex: cadastro errado).
    Remove também o lançamento correspondente no caixa (se houver) para não
    deixar valor "fantasma" por lá. O histórico em Banco de Clientes não é
    afetado - continua registrado mesmo se o pedido original for excluído."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM movimentacoes_caixa WHERE referencia_os_id = %s", (id,))
    cur.execute("DELETE FROM ordens_servico WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Pedido excluído!', 'success')
    return redirect(request.referrer or url_for('clientes.clientes'))


@bp.route('/clientes/banco')
@login_required
def banco_clientes():
    """Histórico permanente de retiradas: um registro por retirada já paga."""
    busca = request.args.get('busca', '').strip()
    conn = get_db()
    cur = conn.cursor()
    if busca:
        cur.execute("SELECT * FROM banco_clientes WHERE nome ILIKE %s ORDER BY id DESC", (f'%{busca}%',))
    else:
        cur.execute("SELECT * FROM banco_clientes ORDER BY id DESC")
    registros = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('banco_clientes.html', registros=registros, busca=busca, formatar_data=formatar_data_br)


@bp.route('/clientes/banco/excluir/<int:id>')
@login_required
def excluir_banco_cliente(id):
    """Remove um registro do histórico permanente de clientes."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM banco_clientes WHERE id = %s", (id,))
    conn.commit()
    cur.close()
    conn.close()
    flash('Registro excluído do Banco de Clientes!', 'success')
    return redirect(url_for('clientes.banco_clientes'))
