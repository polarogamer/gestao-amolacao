import random
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import get_db, parse_valor, parse_inteiro
from auth import login_required
from routes.dashboard_routes import contar_entradas_hoje, get_config, set_config

bp = Blueprint('entrada', __name__)


def gerar_codigo_unico(conn):
    cur = conn.cursor()
    while True:
        codigo = ''.join(random.choices('0123456789', k=6))
        cur.execute("SELECT id FROM ordens_servico WHERE codigo_seguranca = %s", (codigo,))
        if not cur.fetchone():
            cur.close()
            return codigo


def gerar_numero_os(conn):
    ano = datetime.now().year
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) AS c FROM ordens_servico WHERE EXTRACT(YEAR FROM data_entrada) = %s",
        (ano,),
    )
    total = cur.fetchone()['c']
    cur.close()
    return f"{ano}/{total + 1:04d}"


@bp.route('/entrada', methods=['GET', 'POST'])
@login_required
def entrada():
    conn = get_db()
    meta_diaria = int(get_config(conn, 'meta_diaria', '30'))
    qtd_hoje = contar_entradas_hoje(conn)

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        telefone = request.form.get('telefone', '').strip()
        codigo_servico = request.form.get('codigo_servico')
        tipo_servico = request.form.get('tipo_servico')
        quantidade = parse_inteiro(request.form.get('quantidade'), 1)
        valor_unitario = parse_valor(request.form.get('valor_unitario'))
        valor_total = quantidade * valor_unitario
        data_prometida = request.form.get('data_prometida')
        observacao = request.form.get('observacao')

        pagou_agora = request.form.get('pagamento_status') == 'agora'
        forma_pagamento = request.form.get('forma_pagamento') if pagou_agora else None

        if not nome:
            flash('Nome do cliente é obrigatório!', 'error')
            conn.close()
            return redirect(url_for('entrada.entrada'))

        if quantidade < 1:
            flash('Quantidade inválida!', 'error')
            conn.close()
            return redirect(url_for('entrada.entrada'))

        if pagou_agora and not forma_pagamento:
            flash('Selecione a forma de pagamento!', 'error')
            conn.close()
            return redirect(url_for('entrada.entrada'))

        if qtd_hoje + quantidade > meta_diaria:
            flash(f'⛔ Limite do dia atingido! Já temos {qtd_hoje} de {meta_diaria} peças hoje. '
                  f'Não é possível cadastrar mais {quantidade}.', 'error')
            conn.close()
            return redirect(url_for('entrada.entrada'))

        codigo_seguranca = gerar_codigo_unico(conn)
        numero_os = gerar_numero_os(conn)

        cur = conn.cursor()
        cur.execute("SELECT id FROM clientes WHERE nome = %s AND telefone = %s", (nome, telefone))
        cliente = cur.fetchone()
        if not cliente:
            cur.execute(
                "INSERT INTO clientes (nome, telefone, codigo_seguranca) VALUES (%s, %s, %s) RETURNING id",
                (nome, telefone, codigo_seguranca),
            )
            cliente_id = cur.fetchone()['id']
        else:
            cliente_id = cliente['id']

        agora = datetime.now()
        hoje = agora.strftime('%Y-%m-%d')
        hora_entrada = agora.strftime('%H:%M')
        cur.execute('''
            INSERT INTO ordens_servico (
                cliente_id, numero_os, codigo_seguranca, codigo_servico, tipo_servico,
                quantidade, valor_unitario, valor_total, data_entrada, data_prometida,
                status, observacao, forma_pagamento, hora_entrada
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (
            cliente_id, numero_os, codigo_seguranca, codigo_servico, tipo_servico,
            quantidade, valor_unitario, valor_total, hoje,
            data_prometida, 'Entrada', observacao, forma_pagamento, hora_entrada
        ))
        os_id = cur.fetchone()['id']

        if pagou_agora:
            cur.execute('''
                INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (hoje, 'entrada', f'Pagamento antecipado OS {numero_os} - {nome}',
                  'Serviço', valor_total, forma_pagamento, os_id))

        conn.commit()
        cur.close()
        conn.close()

        flash(f'✅ Cliente cadastrado! Código: #{codigo_seguranca}', 'success')
        return redirect(url_for('entrada.entrada'))

    conn.close()
    return render_template('entrada.html', datetime=datetime, timedelta=timedelta,
                           qtd_hoje=qtd_hoje, meta_diaria=meta_diaria)


@bp.route('/entrada/meta', methods=['POST'])
@login_required
def entrada_meta():
    valor = parse_inteiro(request.form.get('meta_diaria'), 30)
    conn = get_db()
    set_config(conn, 'meta_diaria', str(valor))
    conn.close()
    flash(f'Meta diária atualizada para {valor} peças!', 'success')
    return redirect(url_for('entrada.entrada'))
