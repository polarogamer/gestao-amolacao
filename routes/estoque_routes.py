import psycopg2
from flask import Blueprint, render_template, request, redirect, url_for, flash

from db import get_db, formatar_moeda, formatar_data_br, parse_valor, parse_inteiro, agora_br
from auth import login_required

bp = Blueprint('estoque', __name__)


@bp.route('/estoque')
@login_required
def estoque():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM estoque_alicates ORDER BY descricao")
    produtos = cur.fetchall()
    cur.execute("SELECT * FROM vendas_alicates WHERE status = 'reservado' ORDER BY id DESC")
    reservas = cur.fetchall()
    cur.execute("SELECT * FROM vendas_alicates WHERE status = 'pago' ORDER BY id DESC LIMIT 20")
    vendas_recentes = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('estoque.html', produtos=produtos, reservas=reservas,
                           vendas_recentes=vendas_recentes, formatar_moeda=formatar_moeda,
                           formatar_data=formatar_data_br)


@bp.route('/estoque/adicionar', methods=['POST'])
@login_required
def estoque_adicionar():
    sku = request.form.get('sku', '').strip()
    descricao = request.form.get('descricao', '').strip()
    if not sku or not descricao:
        flash('SKU e descrição são obrigatórios!', 'error')
        return redirect(url_for('estoque.estoque'))

    quantidade_nova = parse_inteiro(request.form.get('quantidade'), 0)

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM estoque_alicates WHERE sku = %s", (sku,))
    existente = cur.fetchone()

    if existente:
        cur.execute("UPDATE estoque_alicates SET quantidade = quantidade + %s WHERE sku = %s",
                    (quantidade_nova, sku))
        flash(f'📦 Estoque reabastecido! +{quantidade_nova} unidades de {existente["descricao"]}.', 'success')
    else:
        cur.execute('''
            INSERT INTO estoque_alicates (sku, descricao, tipo, quantidade, preco_venda)
            VALUES (%s, %s, %s, %s, %s)
        ''', (sku, descricao, request.form.get('tipo', ''), quantidade_nova,
              parse_valor(request.form.get('preco_venda'))))
        flash('Produto adicionado!', 'success')

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('estoque.estoque'))


@bp.route('/estoque/excluir/<int:id>')
@login_required
def estoque_excluir(id):
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM estoque_alicates WHERE id = %s", (id,))
        conn.commit()
        flash('Produto excluído!', 'success')
    except psycopg2.IntegrityError:
        conn.rollback()
        flash('Não é possível excluir: este produto já tem vendas registradas no histórico.', 'error')
    finally:
        cur.close()
        conn.close()
    return redirect(url_for('estoque.estoque'))


@bp.route('/estoque/vender', methods=['POST'])
@login_required
def estoque_vender():
    conn = get_db()
    cur = conn.cursor()

    produto_id = parse_inteiro(request.form.get('produto_id'))
    cliente_nome = request.form.get('cliente_nome', '').strip()
    telefone = request.form.get('telefone', '').strip()
    quantidade = parse_inteiro(request.form.get('quantidade'), 1)
    forma_pagamento = request.form.get('forma_pagamento', '').strip()

    cur.execute("SELECT * FROM estoque_alicates WHERE id = %s", (produto_id,))
    produto = cur.fetchone()
    if not produto:
        flash('Produto não encontrado!', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('estoque.estoque'))

    if not cliente_nome:
        flash('Informe o nome do cliente!', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('estoque.estoque'))

    if quantidade < 1:
        flash('Quantidade inválida!', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('estoque.estoque'))

    if produto['quantidade'] < quantidade:
        flash(f'⛔ Estoque insuficiente! Só temos {produto["quantidade"]} unidade(s) de {produto["descricao"]}.', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('estoque.estoque'))

    valor_unitario = produto['preco_venda'] or 0
    valor_total = float(valor_unitario) * quantidade
    hoje = agora_br().strftime('%Y-%m-%d')

    cur.execute("UPDATE estoque_alicates SET quantidade = quantidade - %s WHERE id = %s", (quantidade, produto_id))

    if forma_pagamento:
        status = 'pago'
        data_pagamento = hoje
    else:
        status = 'reservado'
        data_pagamento = None

    cur.execute('''
        INSERT INTO vendas_alicates (produto_id, produto_descricao, cliente_nome, telefone, quantidade,
                                      valor_unitario, valor_total, forma_pagamento, status, data_registro, data_pagamento)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    ''', (produto_id, produto['descricao'], cliente_nome, telefone, quantidade,
          valor_unitario, valor_total, forma_pagamento or None, status, hoje, data_pagamento))
    venda_id = cur.fetchone()['id']

    if status == 'pago':
        cur.execute('''
            INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id)
            VALUES (%s, 'entrada', %s, 'Venda', %s, %s, %s)
        ''', (hoje, f'Venda {produto["descricao"]} - {cliente_nome}', valor_total, forma_pagamento, venda_id))
        flash(f'✅ Venda registrada! {formatar_moeda(valor_total)} ({forma_pagamento})', 'success')
    else:
        flash(f'📌 Encomenda separada no estoque para {cliente_nome}. Confirme o pagamento quando ela vier buscar.', 'success')

    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('estoque.estoque'))


@bp.route('/estoque/confirmar_pagamento/<int:id>', methods=['POST'])
@login_required
def estoque_confirmar_pagamento(id):
    forma_pagamento = request.form.get('forma_pagamento')
    if not forma_pagamento:
        flash('Selecione a forma de pagamento (Pix ou Espécie)!', 'error')
        return redirect(url_for('estoque.estoque'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT * FROM vendas_alicates WHERE id = %s AND status = 'reservado'", (id,))
    venda = cur.fetchone()
    if not venda:
        flash('Encomenda não encontrada ou já paga!', 'error')
        cur.close()
        conn.close()
        return redirect(url_for('estoque.estoque'))

    hoje = agora_br().strftime('%Y-%m-%d')
    cur.execute("UPDATE vendas_alicates SET status = 'pago', forma_pagamento = %s, data_pagamento = %s WHERE id = %s",
                (forma_pagamento, hoje, id))

    cur.execute('''
        INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id)
        VALUES (%s, 'entrada', %s, 'Venda', %s, %s, %s)
    ''', (hoje, f'Venda {venda["produto_descricao"]} - {venda["cliente_nome"]}', venda['valor_total'], forma_pagamento, id))

    conn.commit()
    cur.close()
    conn.close()
    flash(f'✅ Pagamento de {venda["cliente_nome"]} confirmado! {formatar_moeda(venda["valor_total"])} ({forma_pagamento})', 'success')
    return redirect(url_for('estoque.estoque'))
