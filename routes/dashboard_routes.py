from datetime import datetime
from flask import Blueprint, render_template

from db import get_db, formatar_moeda
from auth import login_required

bp = Blueprint('dashboard', __name__)


def contar_entradas_hoje(conn):
    """Soma a quantidade de PEÇAS (não de ordens) recebidas hoje - usado para a meta diária."""
    hoje = datetime.now().strftime('%Y-%m-%d')
    cur = conn.cursor()
    cur.execute("SELECT COALESCE(SUM(quantidade), 0) AS total FROM ordens_servico WHERE data_entrada = %s", (hoje,))
    total = cur.fetchone()['total'] or 0
    cur.close()
    return total


def get_config(conn, chave, padrao=None):
    cur = conn.cursor()
    cur.execute("SELECT valor FROM configuracoes WHERE chave = %s", (chave,))
    row = cur.fetchone()
    cur.close()
    return row['valor'] if row else padrao


def set_config(conn, chave, valor):
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO configuracoes (chave, valor) VALUES (%s, %s) "
        "ON CONFLICT (chave) DO UPDATE SET valor = EXCLUDED.valor",
        (chave, valor),
    )
    conn.commit()
    cur.close()


@bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    hoje = datetime.now().strftime('%Y-%m-%d')
    cur = conn.cursor()

    # Ordens que entraram hoje (nº de clientes atendidos)
    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE data_entrada = %s", (hoje,))
    entradas_hoje = cur.fetchone()['c'] or 0

    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE data_entrega = %s AND status = 'Pago'", (hoje,))
    saidas_hoje = cur.fetchone()['c'] or 0

    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE status != 'Pago'")
    pendentes = cur.fetchone()['c'] or 0

    mes_atual = datetime.now().strftime('%Y-%m')
    cur.execute(
        "SELECT COALESCE(SUM(valor), 0) AS s FROM movimentacoes_caixa "
        "WHERE tipo='entrada' AND to_char(data, 'YYYY-MM') = %s",
        (mes_atual,),
    )
    faturamento = cur.fetchone()['s'] or 0
    cur.close()

    qtd_hoje = contar_entradas_hoje(conn)
    meta_diaria = int(get_config(conn, 'meta_diaria', '30'))

    conn.close()
    return render_template(
        'dashboard.html',
        entradas_hoje=entradas_hoje,
        saidas_hoje=saidas_hoje,
        pendentes=pendentes,
        faturamento=formatar_moeda(faturamento),
        qtd_hoje=qtd_hoje,
        meta_diaria=meta_diaria,
        datetime=datetime,
    )
