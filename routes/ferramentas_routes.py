"""
Gera e apaga dados fictícios para testar a aplicação. Tudo que é criado aqui
é marcado com is_seed = true, então "Apagar dados de teste" só remove o que
foi gerado por este botão - nunca toca em clientes, pedidos ou vendas reais.
"""
import random
from datetime import timedelta
from flask import Blueprint, render_template, redirect, url_for, flash

from db import get_db, agora_br
from auth import login_required

bp = Blueprint('ferramentas', __name__)

# nome, telefone, dias_atras, hora_entrada, codigo_servico, tipo_servico, quantidade,
# valor_unitario, observacao, pago, pagou_na_entrada, hora_entrega, forma_pagamento
CLIENTES_TESTE = [
    ('Maria Souza (teste)', '11988880001', 0, '08:15', 'AT', 'Amolação', 2, 20.00, 'Cabo azul', True, False, '11:40', 'Pix'),
    ('João Pereira (teste)', '11988880002', 0, '08:40', 'T', 'Amolação', 1, 15.00, '', False, False, None, None),
    ('Ana Beatriz Lima (teste)', '11988880003', 0, '09:05', 'TP', 'Amolação', 3, 5.00, 'Tesourinha de unha do salão', False, False, None, None),
    ('Carlos Eduardo Santos (teste)', '11988880004', 0, '10:20', 'TM', 'Troca de Mola', 1, 15.00, '', True, True, '10:45', 'Espécie'),
    ('Fernanda Alves (teste)', '11988880005', 0, '13:10', 'AT', 'Amolação', 4, 20.00, 'Buscar até 18h', False, False, None, None),
    ('Roberto Nunes (teste)', '11988880006', 0, '14:05', 'TG', 'Amolação', 1, 20.00, '', True, False, '16:30', 'Pix'),
    ('Patrícia Gomes (teste)', '11988880007', 1, '09:00', 'AT', 'Amolação', 2, 20.00, '', True, False, '15:00', 'Pix'),
    ('Bruno Cavalcanti (teste)', '11988880008', 1, '11:30', 'M', 'Troca de Mola', 1, 20.00, '', True, False, '17:45', 'Espécie'),
    ('Juliana Ribeiro (teste)', '11988880009', 2, '08:50', 'AT', 'Amolação', 6, 20.00, 'Cliente do salão Beleza Pura', True, False, '14:00', 'Pix'),
    ('Diego Martins (teste)', '11988880010', 3, '10:00', 'T', 'Amolação', 1, 15.00, '', True, True, '10:20', 'Pix'),
    ('Larissa Freitas (teste)', '11988880011', 5, '09:40', 'TP', 'Amolação', 2, 5.00, '', True, False, '13:00', 'Espécie'),
    ('Eduardo Barros (teste)', '11988880012', 6, '15:00', 'AT', 'Amolação', 3, 20.00, '', True, False, '17:00', 'Pix'),
    ('Camila Rocha (teste)', '11988880013', 9, '08:30', 'TG', 'Amolação', 1, 20.00, '', True, False, '12:00', 'Pix'),
    ('Marcelo Teixeira (teste)', '11988880014', 14, '09:15', 'AT', 'Amolação', 5, 20.00, '', True, False, '16:00', 'Espécie'),
    ('Beatriz Andrade (teste)', '11988880015', 19, '10:45', 'M', 'Troca de Mola', 2, 20.00, '', True, False, '14:30', 'Pix'),
]

# sku (fictício, não usa os SKUs reais da loja), descricao, tipo, quantidade, preco_venda, estoque_minimo
ESTOQUE_TESTE = [
    ('TESTE-AL888', 'Alicate 888 Inox (teste)', 'Alicate', 14, 35.00, 5),
    ('TESTE-TPP', 'Tesoura de Poda Pequena (teste)', 'Tesoura', 1, 18.00, 4),
    ('TESTE-TPG', 'Tesoura de Poda Grande (teste)', 'Tesoura', 9, 32.00, 3),
]

CONSUMIVEIS_TESTE = [
    ("Lixa d'agua 600 (teste)", 6, 'folha', 20, 2.50),
    ('Mola inox (teste)', 25, 'un', 10, 4.90),
    ('Óleo refrigerante (teste)', 2, 'litro', 3, 32.50),
    ('Parafuso de ajuste (teste)', 38, 'un', 15, 1.90),
]

# sku, cliente_nome, telefone, quantidade, dias_atras, pago, forma_pagamento, hora
VENDAS_TESTE = [
    ('TESTE-AL888', 'Renato Cardoso (teste)', '11976543210', 1, 0, True, 'Pix', '09:20'),
    ('TESTE-AL888', 'Simone Ferraz (teste)', '11976541111', 2, 2, True, 'Espécie', '15:10'),
    ('TESTE-TPG', 'Vinícius Nogueira (teste)', '11976542222', 1, 0, False, None, '16:00'),
]

# dias_atras, hora, tipo, descricao, categoria, valor, forma_pagamento
CAIXA_TESTE = [
    (0, '07:30', 'entrada', 'Saldo inicial de caixa (teste)', 'Abertura', 150.00, 'Dinheiro'),
    (0, '12:10', 'saida', 'Compra de lixas e óleo (teste)', 'Insumos', 45.00, 'Dinheiro'),
    (1, '18:00', 'saida', 'Almoço da equipe (teste)', 'Outros', 32.00, 'Dinheiro'),
    (4, '09:00', 'saida', 'Manutenção da esmeril (teste)', 'Equipamento', 80.00, 'Pix'),
]


def _gerar_codigo_unico(cur):
    while True:
        codigo = ''.join(random.choices('0123456789', k=6))
        cur.execute("SELECT id FROM ordens_servico WHERE codigo_seguranca = %s", (codigo,))
        if not cur.fetchone():
            return codigo


def _gerar_numero_os(cur, ano):
    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE EXTRACT(YEAR FROM data_entrada) = %s", (ano,))
    total = cur.fetchone()['c']
    return f"{ano}/{total + 1:04d}"


@bp.route('/ferramentas')
@login_required
def ferramentas():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE is_seed = true")
    total_pedidos = cur.fetchone()['c']
    cur.execute("SELECT COUNT(*) AS c FROM clientes WHERE is_seed = true")
    total_clientes = cur.fetchone()['c']
    cur.close()
    conn.close()
    return render_template('ferramentas.html', total_pedidos=total_pedidos, total_clientes=total_clientes)


@bp.route('/ferramentas/gerar', methods=['POST'])
@login_required
def gerar_dados():
    conn = get_db()
    cur = conn.cursor()
    agora = agora_br()

    for sku, descricao, tipo, quantidade, preco, minimo in ESTOQUE_TESTE:
        cur.execute("SELECT id FROM estoque_alicates WHERE sku = %s", (sku,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO estoque_alicates (sku, descricao, tipo, quantidade, preco_venda, estoque_minimo, is_seed) "
                "VALUES (%s, %s, %s, %s, %s, %s, true)",
                (sku, descricao, tipo, quantidade, preco, minimo),
            )

    for nome, quantidade, unidade, minimo, preco in CONSUMIVEIS_TESTE:
        cur.execute("SELECT id FROM consumiveis WHERE nome = %s", (nome,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO consumiveis (nome, quantidade, unidade, estoque_minimo, preco_unitario, is_seed) "
                "VALUES (%s, %s, %s, %s, %s, true)",
                (nome, quantidade, unidade, minimo, preco),
            )

    for (nome, telefone, dias_atras, hora_entrada, codigo_servico, tipo_servico, quantidade,
         valor_unitario, observacao, pago, pagou_na_entrada, hora_entrega, forma_pagamento) in CLIENTES_TESTE:
        momento = agora - timedelta(days=dias_atras)
        data_entrada = momento.strftime('%Y-%m-%d')

        cur.execute("SELECT id FROM clientes WHERE nome = %s AND telefone = %s", (nome, telefone))
        row = cur.fetchone()
        if row:
            cliente_id = row['id']
        else:
            codigo = _gerar_codigo_unico(cur)
            cur.execute(
                "INSERT INTO clientes (nome, telefone, codigo_seguranca, is_seed) VALUES (%s, %s, %s, true) RETURNING id",
                (nome, telefone, codigo),
            )
            cliente_id = cur.fetchone()['id']

        codigo_seguranca = _gerar_codigo_unico(cur)
        numero_os = _gerar_numero_os(cur, momento.year)
        valor_total = quantidade * valor_unitario
        forma_pagamento_entrada = forma_pagamento if pagou_na_entrada else None

        cur.execute('''
            INSERT INTO ordens_servico (
                cliente_id, numero_os, codigo_seguranca, codigo_servico, tipo_servico,
                quantidade, valor_unitario, valor_total, data_entrada, data_prometida,
                status, observacao, forma_pagamento, hora_entrada, is_seed
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true) RETURNING id
        ''', (
            cliente_id, numero_os, codigo_seguranca, codigo_servico, tipo_servico,
            quantidade, valor_unitario, valor_total, data_entrada, (momento + timedelta(days=1)).strftime('%Y-%m-%d'),
            'Entrada', observacao, forma_pagamento_entrada, hora_entrada,
        ))
        os_id = cur.fetchone()['id']

        if pagou_na_entrada:
            cur.execute('''
                INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id, hora, is_seed)
                VALUES (%s, 'entrada', %s, 'Serviço', %s, %s, %s, %s, true)
            ''', (data_entrada, f'Pagamento antecipado OS {numero_os} - {nome}', valor_total, forma_pagamento_entrada, os_id, hora_entrada))

        if pago:
            cur.execute(
                "UPDATE ordens_servico SET status = 'Pago', data_entrega = %s, hora_entrega = %s, forma_pagamento = %s WHERE id = %s",
                (data_entrada, hora_entrega, forma_pagamento, os_id),
            )
            if not pagou_na_entrada:
                cur.execute('''
                    INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id, hora, is_seed)
                    VALUES (%s, 'entrada', %s, 'Serviço', %s, %s, %s, %s, true)
                ''', (data_entrada, f'Pagamento OS {numero_os} - {nome}', valor_total, forma_pagamento, os_id, hora_entrega))
            cur.execute(
                "INSERT INTO banco_clientes (nome, telefone, codigo_servico, quantidade, observacao, hora, data_registro, is_seed) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, true)",
                (nome, telefone, codigo_servico, quantidade, observacao, hora_entrega, data_entrada),
            )

    for sku, cliente_nome, telefone, quantidade, dias_atras, pago, forma_pagamento, hora in VENDAS_TESTE:
        cur.execute("SELECT id, descricao, preco_venda FROM estoque_alicates WHERE sku = %s", (sku,))
        produto = cur.fetchone()
        if not produto:
            continue
        momento = agora - timedelta(days=dias_atras)
        data_registro = momento.strftime('%Y-%m-%d')
        preco_unitario = produto['preco_venda'] or 0
        valor_total = float(preco_unitario) * quantidade
        status = 'pago' if pago else 'reservado'

        cur.execute('''
            INSERT INTO vendas_alicates (produto_id, produto_descricao, cliente_nome, telefone, quantidade,
                                          valor_unitario, valor_total, forma_pagamento, status, data_registro, data_pagamento, is_seed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, true) RETURNING id
        ''', (produto['id'], produto['descricao'], cliente_nome, telefone, quantidade,
              preco_unitario, valor_total, forma_pagamento, status, data_registro, data_registro if pago else None))
        venda_id = cur.fetchone()['id']

        if pago:
            cur.execute('''
                INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id, hora, is_seed)
                VALUES (%s, 'entrada', %s, 'Venda', %s, %s, %s, %s, true)
            ''', (data_registro, f'Venda {produto["descricao"]} - {cliente_nome}', valor_total, forma_pagamento, venda_id, hora))

    for dias_atras, hora, tipo, descricao, categoria, valor, forma_pagamento in CAIXA_TESTE:
        data = (agora - timedelta(days=dias_atras)).strftime('%Y-%m-%d')
        cur.execute('''
            INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, hora, is_seed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, true)
        ''', (data, tipo, descricao, categoria, valor, forma_pagamento, hora))

    conn.commit()
    cur.close()
    conn.close()
    flash('✅ Dados fictícios gerados! Já aparecem em Entrada, Saída, Relatório, Clientes, Caixa, Estoque e no Dashboard.', 'success')
    return redirect(url_for('ferramentas.ferramentas'))


@bp.route('/ferramentas/apagar', methods=['POST'])
@login_required
def apagar_dados():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM vendas_alicates WHERE is_seed = true")
    cur.execute("DELETE FROM estoque_alicates WHERE is_seed = true")
    cur.execute("DELETE FROM movimentacoes_caixa WHERE is_seed = true")
    cur.execute("DELETE FROM banco_clientes WHERE is_seed = true")
    cur.execute("DELETE FROM ordens_servico WHERE is_seed = true")
    cur.execute("DELETE FROM clientes WHERE is_seed = true")
    cur.execute("DELETE FROM consumiveis WHERE is_seed = true")
    conn.commit()
    cur.close()
    conn.close()
    flash('🗑️ Dados fictícios apagados. Os dados reais não foram tocados.', 'success')
    return redirect(url_for('ferramentas.ferramentas'))
