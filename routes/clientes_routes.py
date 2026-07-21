from datetime import datetime
from flask import Blueprint, render_template

from db import get_db, formatar_data_br
from auth import login_required

bp = Blueprint('clientes', __name__)


@bp.route('/clientes')
@login_required
def clientes():
    """Clientes do dia: pedidos de hoje que ainda não foram pagos/retirados.
    Some da lista sozinho assim que o cliente paga na Saída."""
    hoje = datetime.now().strftime('%Y-%m-%d')
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
    return render_template('clientes.html', pedidos=pedidos_hoje, formatar_data=formatar_data_br, datetime=datetime)


@bp.route('/clientes/banco')
@login_required
def banco_clientes():
    """Registro permanente (nome + telefone) de clientes que já pagaram alguma vez."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM banco_clientes ORDER BY nome")
    registros = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('banco_clientes.html', registros=registros, formatar_data=formatar_data_br)
