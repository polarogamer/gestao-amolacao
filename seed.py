"""
Popula o banco com dados de teste a partir de seed_data.json, usando as
mesmas regras da aplicação (cria cliente se não existir, gera código de
segurança e número de OS, lança no caixa e no banco de clientes quando um
pedido é marcado como pago). Não apaga nada - só adiciona.

Uso:
    DATABASE_URL=... python3 seed.py
    (ou rode com o mesmo .env que a aplicação já usa)
"""
import json
import random
from datetime import timedelta

from db import get_db, agora_br


def gerar_codigo_unico(cur):
    while True:
        codigo = ''.join(random.choices('0123456789', k=6))
        cur.execute("SELECT id FROM ordens_servico WHERE codigo_seguranca = %s", (codigo,))
        if not cur.fetchone():
            return codigo


def gerar_numero_os(cur, ano):
    cur.execute("SELECT COUNT(*) AS c FROM ordens_servico WHERE EXTRACT(YEAR FROM data_entrada) = %s", (ano,))
    total = cur.fetchone()['c']
    return f"{ano}/{total + 1:04d}"


def obter_ou_criar_cliente(cur, nome, telefone, codigo_seguranca):
    cur.execute("SELECT id FROM clientes WHERE nome = %s AND telefone = %s", (nome, telefone))
    row = cur.fetchone()
    if row:
        return row['id']
    cur.execute(
        "INSERT INTO clientes (nome, telefone, codigo_seguranca) VALUES (%s, %s, %s) RETURNING id",
        (nome, telefone, codigo_seguranca),
    )
    return cur.fetchone()['id']


def seed():
    with open('seed_data.json', encoding='utf-8') as f:
        dados = json.load(f)

    conn = get_db()
    cur = conn.cursor()
    agora = agora_br()

    # ---- Estoque de alicates (ON CONFLICT: reforça a quantidade do seed) ----
    for item in dados.get('estoque_alicates', []):
        cur.execute("SELECT id FROM estoque_alicates WHERE sku = %s", (item['sku'],))
        if cur.fetchone():
            cur.execute(
                "UPDATE estoque_alicates SET quantidade = %s WHERE sku = %s",
                (item['quantidade'], item['sku']),
            )
        else:
            cur.execute(
                "INSERT INTO estoque_alicates (sku, descricao, tipo, quantidade, preco_venda, estoque_minimo) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (item['sku'], item['descricao'], item.get('tipo', ''), item['quantidade'],
                 item['preco_venda'], item.get('estoque_minimo', 5)),
            )
    print(f"✔ {len(dados.get('estoque_alicates', []))} produtos de estoque")

    # ---- Consumíveis ----
    novos_consumiveis = 0
    for item in dados.get('consumiveis', []):
        cur.execute("SELECT id FROM consumiveis WHERE nome = %s", (item['nome'],))
        if cur.fetchone():
            continue
        cur.execute(
            "INSERT INTO consumiveis (nome, quantidade, unidade, estoque_minimo, preco_unitario) "
            "VALUES (%s, %s, %s, %s, %s)",
            (item['nome'], item['quantidade'], item.get('unidade', 'un'),
             item.get('estoque_minimo', 5), item['preco_unitario']),
        )
        novos_consumiveis += 1
    print(f"✔ {novos_consumiveis} consumíveis novos")

    # ---- Pedidos (ordens_servico) ----
    total_pedidos = 0
    for cliente in dados.get('clientes', []):
        for pedido in cliente.get('pedidos', []):
            momento = agora - timedelta(days=pedido.get('dias_atras', 0))
            data_entrada = momento.strftime('%Y-%m-%d')
            data_prometida = (momento + timedelta(days=1)).strftime('%Y-%m-%d')
            hora_entrada = pedido.get('hora_entrada', momento.strftime('%H:%M'))

            codigo_seguranca = gerar_codigo_unico(cur)
            cliente_id = obter_ou_criar_cliente(cur, cliente['nome'], cliente.get('telefone', ''), codigo_seguranca)
            numero_os = gerar_numero_os(cur, momento.year)

            quantidade = pedido['quantidade']
            valor_unitario = pedido['valor_unitario']
            valor_total = quantidade * valor_unitario
            pagou_na_entrada = pedido.get('pagou_na_entrada', False)
            forma_pagamento_entrada = pedido.get('forma_pagamento') if pagou_na_entrada else None

            cur.execute('''
                INSERT INTO ordens_servico (
                    cliente_id, numero_os, codigo_seguranca, codigo_servico, tipo_servico,
                    quantidade, valor_unitario, valor_total, data_entrada, data_prometida,
                    status, observacao, forma_pagamento, hora_entrada
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
            ''', (
                cliente_id, numero_os, codigo_seguranca, pedido['codigo_servico'], pedido.get('tipo_servico', 'Amolação'),
                quantidade, valor_unitario, valor_total, data_entrada, data_prometida,
                'Entrada', pedido.get('observacao', ''), forma_pagamento_entrada, hora_entrada,
            ))
            os_id = cur.fetchone()['id']

            if pagou_na_entrada:
                cur.execute('''
                    INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id, hora)
                    VALUES (%s, 'entrada', %s, 'Serviço', %s, %s, %s, %s)
                ''', (data_entrada, f'Pagamento antecipado OS {numero_os} - {cliente["nome"]}',
                      valor_total, forma_pagamento_entrada, os_id, hora_entrada))

            if pedido.get('pago'):
                hora_entrega = pedido.get('hora_entrega', hora_entrada)
                data_entrega = pedido.get('data_entrega', data_entrada)
                forma_pagamento = pedido.get('forma_pagamento', 'Pix')

                cur.execute(
                    "UPDATE ordens_servico SET status = 'Pago', data_entrega = %s, hora_entrega = %s, "
                    "forma_pagamento = %s WHERE id = %s",
                    (data_entrega, hora_entrega, forma_pagamento, os_id),
                )
                if not pagou_na_entrada:
                    cur.execute('''
                        INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id, hora)
                        VALUES (%s, 'entrada', %s, 'Serviço', %s, %s, %s, %s)
                    ''', (data_entrega, f'Pagamento OS {numero_os} - {cliente["nome"]}',
                          valor_total, forma_pagamento, os_id, hora_entrega))

                cur.execute(
                    "INSERT INTO banco_clientes (nome, telefone, codigo_servico, quantidade, observacao, hora, data_registro) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (cliente['nome'], cliente.get('telefone', ''), pedido['codigo_servico'],
                     quantidade, pedido.get('observacao', ''), hora_entrega, data_entrega),
                )

            total_pedidos += 1
    print(f"✔ {total_pedidos} pedidos (ordens de serviço)")

    # ---- Vendas avulsas de estoque ----
    total_vendas = 0
    for venda in dados.get('vendas_avulsas', []):
        cur.execute("SELECT id, descricao FROM estoque_alicates WHERE sku = %s", (venda['produto_sku'],))
        produto = cur.fetchone()
        if not produto:
            print(f"  (pulando venda: produto {venda['produto_sku']} não existe no seed)")
            continue

        momento = agora - timedelta(days=venda.get('dias_atras', 0))
        data_registro = momento.strftime('%Y-%m-%d')
        quantidade = venda['quantidade']
        cur.execute("SELECT preco_venda FROM estoque_alicates WHERE id = %s", (produto['id'],))
        preco_unitario = cur.fetchone()['preco_venda'] or 0
        valor_total = float(preco_unitario) * quantidade
        pago = venda.get('pago', False)
        status = 'pago' if pago else 'reservado'
        forma_pagamento = venda.get('forma_pagamento') if pago else None

        cur.execute('''
            INSERT INTO vendas_alicates (produto_id, produto_descricao, cliente_nome, telefone, quantidade,
                                          valor_unitario, valor_total, forma_pagamento, status, data_registro, data_pagamento)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        ''', (produto['id'], produto['descricao'], venda['cliente_nome'], venda.get('telefone', ''), quantidade,
              preco_unitario, valor_total, forma_pagamento, status, data_registro,
              data_registro if pago else None))
        venda_id = cur.fetchone()['id']

        if pago:
            cur.execute('''
                INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, referencia_os_id, hora)
                VALUES (%s, 'entrada', %s, 'Venda', %s, %s, %s, %s)
            ''', (data_registro, f'Venda {produto["descricao"]} - {venda["cliente_nome"]}',
                  valor_total, forma_pagamento, venda_id, momento.strftime('%H:%M')))
        total_vendas += 1
    print(f"✔ {total_vendas} vendas avulsas de estoque")

    # ---- Lançamentos extras de caixa (despesas, abertura, etc.) ----
    total_caixa = 0
    for lanc in dados.get('caixa_extra', []):
        momento = agora - timedelta(days=lanc.get('dias_atras', 0))
        data = momento.strftime('%Y-%m-%d')
        cur.execute('''
            INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento, hora)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        ''', (data, lanc['tipo'], lanc['descricao'], lanc.get('categoria', 'Outros'),
              lanc['valor'], lanc.get('forma_pagamento', 'Dinheiro'), lanc.get('hora', '12:00')))
        total_caixa += 1
    print(f"✔ {total_caixa} lançamentos extras de caixa")

    conn.commit()
    cur.close()
    conn.close()
    print("\nSeed concluído com sucesso.")


if __name__ == '__main__':
    seed()
