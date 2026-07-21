from flask import Blueprint, render_template

from db import get_db, formatar_moeda, datetime_br
from auth import login_required

bp = Blueprint('mensagens', __name__)


@bp.route('/mensagens')
@login_required
def mensagens():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''
        SELECT os.*, c.nome as cliente_nome, c.telefone
        FROM ordens_servico os
        JOIN clientes c ON os.cliente_id = c.id
        WHERE os.status IN ('Pronto', 'Entrada')
        ORDER BY c.nome ASC
    ''')
    prontos_hoje = cur.fetchall()
    cur.close()
    conn.close()

    mensagem_padrao = "Olá, aqui é o Amorin Alicates! O seu alicate já está pronto. Ficamos até às 15h. Aguardamos você!"

    return render_template('mensagens.html', prontos=prontos_hoje, mensagem_padrao=mensagem_padrao,
                           formatar_moeda=formatar_moeda, datetime=datetime_br)
