from flask import Blueprint, render_template

from db import get_db, formatar_data_br
from auth import login_required

bp = Blueprint('clientes', __name__)


@bp.route('/clientes')
@login_required
def clientes():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM clientes ORDER BY nome")
    clientes_rows = cur.fetchall()

    resultado = []
    for c in clientes_rows:
        cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE cliente_id = %s AND status != 'Pago'", (c['id'],))
        pendentes = cur.fetchone()['c']
        resultado.append({**dict(c), 'pendentes': pendentes})

    cur.close()
    conn.close()
    return render_template('clientes.html', clientes=resultado, formatar_data=formatar_data_br)
