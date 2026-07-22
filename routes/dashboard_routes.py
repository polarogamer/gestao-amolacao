import json
from datetime import timedelta
from flask import Blueprint, render_template

from db import get_db, formatar_moeda, agora_br, datetime_br
from auth import login_required

bp = Blueprint('dashboard', __name__)

DIAS_SEMANA = ['Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom']


def contar_entradas_hoje(conn):
    """Soma a quantidade de PEÇAS (não de ordens) recebidas hoje - usado para a meta diária."""
    hoje = agora_br().strftime('%Y-%m-%d')
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


def _dados_por_dia(conn, data_inicio, data_fim):
    """Entradas/saídas/faturamento por dia num intervalo. Usa o snapshot de
    fechamentos_diarios para dias já fechados (a OS crua já foi apagada de
    lá) e calcula ao vivo a partir de ordens_servico/movimentacoes_caixa
    para dias que ainda não foram fechados (inclusive hoje)."""
    cur = conn.cursor()
    dados = {}
    d = data_inicio
    while d <= data_fim:
        dados[d.strftime('%Y-%m-%d')] = {
            'entradas': 0, 'saidas': 0, 'pendentes': 0, 'faturamento': 0.0,
        }
        d += timedelta(days=1)

    cur.execute(
        "SELECT data, total_entradas, total_saidas, faturamento_dia FROM fechamentos_diarios "
        "WHERE data BETWEEN %s AND %s",
        (data_inicio, data_fim),
    )
    fechados = set()
    for row in cur.fetchall():
        key = row['data'].strftime('%Y-%m-%d')
        if key in dados:
            dados[key] = {
                'entradas': row['total_entradas'] or 0,
                'saidas': row['total_saidas'] or 0,
                'pendentes': row['pendentes'] or 0,
                'faturamento': float(row['faturamento_dia'] or 0),
            }
            fechados.add(key)

    cur.execute(
        "SELECT data_entrada, COALESCE(SUM(quantidade), 0) AS c FROM ordens_servico "
        "WHERE data_entrada BETWEEN %s AND %s GROUP BY data_entrada",
        (data_inicio, data_fim),
    )
    for row in cur.fetchall():
        key = row['data_entrada'].strftime('%Y-%m-%d')
        if key in dados and key not in fechados:
            dados[key]['entradas'] = row['c']

    cur.execute(
        "SELECT data_entrega, COALESCE(SUM(quantidade), 0) AS c FROM ordens_servico "
        "WHERE data_entrega BETWEEN %s AND %s AND status = 'Pago' GROUP BY data_entrega",
        (data_inicio, data_fim),
    )
    for row in cur.fetchall():
        key = row['data_entrega'].strftime('%Y-%m-%d')
        if key in dados and key not in fechados:
            dados[key]['saidas'] = row['c']

    cur.execute(
        "SELECT data, COALESCE(SUM(valor), 0) AS s FROM movimentacoes_caixa "
        "WHERE data BETWEEN %s AND %s AND tipo = 'entrada' AND categoria != 'Abertura' "
        "GROUP BY data",
        (data_inicio, data_fim),
    )
    for row in cur.fetchall():
        key = row['data'].strftime('%Y-%m-%d')
        if key in dados and key not in fechados:
            dados[key]['faturamento'] = float(row['s'] or 0)

    cur.execute(
        "SELECT data_entrada, COALESCE(SUM(quantidade), 0) AS c FROM ordens_servico "
        "WHERE data_entrada BETWEEN %s AND %s AND status != 'Pago' GROUP BY data_entrada",
        (data_inicio, data_fim),
    )
    for row in cur.fetchall():
        key = row['data_entrada'].strftime('%Y-%m-%d')
        if key in dados and key not in fechados:
            dados[key]['pendentes'] = row['c']

    cur.close()
    return dados


def _dados_hoje_por_hora(conn, hoje):
    """Entradas/saídas de hoje agrupadas por hora (7h-19h), usando os
    horários gravados na Entrada e na Saída."""
    cur = conn.cursor()
    cur.execute("SELECT hora_entrada FROM ordens_servico WHERE data_entrada = %s AND hora_entrada IS NOT NULL", (hoje,))
    horas_entrada = [r['hora_entrada'] for r in cur.fetchall()]
    cur.execute(
        "SELECT hora_entrega FROM ordens_servico WHERE data_entrega = %s AND status = 'Pago' AND hora_entrega IS NOT NULL",
        (hoje,),
    )
    horas_saida = [r['hora_entrega'] for r in cur.fetchall()]
    cur.close()

    horas = [f"{h:02d}h" for h in range(7, 20)]
    entradas = {h: 0 for h in horas}
    saidas = {h: 0 for h in horas}
    for h in horas_entrada:
        bucket = f"{h[:2]}h"
        if bucket in entradas:
            entradas[bucket] += 1
    for h in horas_saida:
        bucket = f"{h[:2]}h"
        if bucket in saidas:
            saidas[bucket] += 1

    return horas, [entradas[h] for h in horas], [saidas[h] for h in horas]


@bp.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    agora = agora_br()
    hoje_data = agora.date()
    hoje = hoje_data.strftime('%Y-%m-%d')
    cur = conn.cursor()

    # Ordens que entraram hoje (nº de clientes atendidos)
    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE data_entrada = %s", (hoje,))
    entradas_hoje = cur.fetchone()['c'] or 0

    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE data_entrega = %s AND status = 'Pago'", (hoje,))
    saidas_hoje = cur.fetchone()['c'] or 0

    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE status != 'Pago'")
    pendentes = cur.fetchone()['c'] or 0

    mes_atual = agora.strftime('%Y-%m')
    cur.execute(
        "SELECT COALESCE(SUM(valor), 0) AS s FROM movimentacoes_caixa "
        "WHERE tipo='entrada' AND to_char(data, 'YYYY-MM') = %s",
        (mes_atual,),
    )
    faturamento_mes = cur.fetchone()['s'] or 0

    cur.execute(
        "SELECT COALESCE(SUM(valor), 0) AS s FROM movimentacoes_caixa "
        "WHERE tipo='entrada' AND data = %s AND categoria != 'Abertura'",
        (hoje,),
    )
    faturamento_hoje = cur.fetchone()['s'] or 0
    cur.close()

    qtd_hoje = contar_entradas_hoje(conn)
    meta_diaria = int(get_config(conn, 'meta_diaria', '30'))

    # --- Gráfico do dia: entradas x saídas por hora ---
    horas_labels, horas_entradas, horas_saidas = _dados_hoje_por_hora(conn, hoje)

    # --- Gráfico da semana: segunda a domingo da semana atual ---
    inicio_semana = hoje_data - timedelta(days=hoje_data.weekday())
    fim_semana = inicio_semana + timedelta(days=6)
    dados_semana = _dados_por_dia(conn, inicio_semana, fim_semana)
    semana_labels = []
    semana_entradas = []
    semana_saidas = []
    semana_pendentes = []
    semana_faturamento = []
    d = inicio_semana
    while d <= fim_semana:
        key = d.strftime('%Y-%m-%d')
        semana_labels.append(DIAS_SEMANA[d.weekday()])
        semana_entradas.append(dados_semana[key]['entradas'])
        semana_saidas.append(dados_semana[key]['saidas'])
        semana_pendentes.append(dados_semana[key]['pendentes'])
        semana_faturamento.append(dados_semana[key]['faturamento'])
        d += timedelta(days=1)

    # --- Gráfico do mês: dia 1 até hoje do mês atual ---
    inicio_mes = hoje_data.replace(day=1)
    dados_mes = _dados_por_dia(conn, inicio_mes, hoje_data)
    mes_labels = []
    mes_entradas = []
    mes_saidas = []
    mes_pendentes = []
    mes_faturamento = []
    d = inicio_mes
    while d <= hoje_data:
        key = d.strftime('%Y-%m-%d')
        mes_labels.append(str(d.day))
        mes_entradas.append(dados_mes[key]['entradas'])
        mes_saidas.append(dados_mes[key]['saidas'])
        mes_pendentes.append(dados_mes[key]['pendentes'])
        mes_faturamento.append(dados_mes[key]['faturamento'])
        d += timedelta(days=1)

    def resumo_periodo(dados, inicio, fim):
        """Totais dos cards. Pendências são peças do período ainda não retiradas."""
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(SUM(quantidade), 0) AS total FROM ordens_servico "
            "WHERE status != 'Pago' AND data_entrada BETWEEN %s AND %s",
            (inicio, fim),
        )
        pendentes_periodo = cur.fetchone()['total'] or 0
        cur.close()
        return {
            'entradas': sum(item['entradas'] for item in dados.values()),
            'saidas': sum(item['saidas'] for item in dados.values()),
            'pendentes': pendentes_periodo,
            'faturamento': float(sum(item['faturamento'] for item in dados.values())),
        }

    dados_hoje = _dados_por_dia(conn, hoje_data, hoje_data)
    resumos = {
        'dia': resumo_periodo(dados_hoje, hoje_data, hoje_data),
        'semana': resumo_periodo(dados_semana, inicio_semana, fim_semana),
        'mes': resumo_periodo(dados_mes, inicio_mes, hoje_data),
    }

    conn.close()
    return render_template(
        'dashboard.html',
        resumos=json.dumps(resumos),
        entradas_hoje=entradas_hoje,
        saidas_hoje=saidas_hoje,
        pendentes=pendentes,
        faturamento=formatar_moeda(faturamento_mes),
        faturamento_hoje=formatar_moeda(faturamento_hoje),
        qtd_hoje=qtd_hoje,
        meta_diaria=meta_diaria,
        datetime=datetime_br,
        grafico_dia=json.dumps({'labels': horas_labels, 'entradas': horas_entradas, 'saidas': horas_saidas}),
        grafico_semana=json.dumps({
            'labels': semana_labels, 'entradas': semana_entradas,
            'saidas': semana_saidas, 'pendentes': semana_pendentes,
            'faturamento': semana_faturamento,
        }),
        grafico_mes=json.dumps({
            'labels': mes_labels, 'entradas': mes_entradas,
            'saidas': mes_saidas, 'pendentes': mes_pendentes,
            'faturamento': mes_faturamento,
        }),
    )
