"""
Camada de acesso ao banco de dados.
Usa PostgreSQL (Supabase) via psycopg2, com cursor que devolve dicts
(equivalente ao sqlite3.Row que o projeto usava antes).
"""
import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL não configurada. Defina a connection string do Supabase "
        "na variável de ambiente DATABASE_URL (veja .env.example)."
    )


def get_db():
    """Abre uma conexão nova. Uma por requisição - importante em ambiente serverless."""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return conn


def init_db():
    """Cria as tabelas se não existirem e insere dados iniciais. Rodar uma vez (ou a cada deploy, é idempotente)."""
    conn = get_db()
    cur = conn.cursor()

    cur.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            usuario TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL,
            data_cadastro DATE DEFAULT CURRENT_DATE
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS clientes (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            telefone TEXT,
            endereco TEXT,
            codigo_seguranca TEXT,
            data_cadastro DATE DEFAULT CURRENT_DATE,
            is_seed BOOLEAN DEFAULT FALSE
        )
    ''')
    cur.execute("ALTER TABLE clientes ADD COLUMN IF NOT EXISTS is_seed BOOLEAN DEFAULT FALSE")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS ordens_servico (
            id SERIAL PRIMARY KEY,
            cliente_id INTEGER REFERENCES clientes(id),
            numero_os TEXT UNIQUE NOT NULL,
            codigo_seguranca TEXT UNIQUE NOT NULL,
            codigo_servico TEXT,
            tipo_servico TEXT,
            quantidade INTEGER DEFAULT 1,
            valor_unitario NUMERIC(10,2),
            valor_total NUMERIC(10,2),
            data_entrada DATE NOT NULL,
            data_prometida DATE,
            data_entrega DATE,
            status TEXT DEFAULT 'Entrada',
            forma_pagamento TEXT,
            observacao TEXT,
            hora_entrada TEXT,
            hora_entrega TEXT,
            is_seed BOOLEAN DEFAULT FALSE
        )
    ''')
    cur.execute("ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS hora_entrada TEXT")
    cur.execute("ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS hora_entrega TEXT")
    cur.execute("ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS is_seed BOOLEAN DEFAULT FALSE")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS estoque_alicates (
            id SERIAL PRIMARY KEY,
            sku TEXT UNIQUE NOT NULL,
            descricao TEXT NOT NULL,
            tipo TEXT,
            quantidade INTEGER DEFAULT 0,
            preco_venda NUMERIC(10,2),
            estoque_minimo INTEGER DEFAULT 5,
            is_seed BOOLEAN DEFAULT FALSE
        )
    ''')
    cur.execute("ALTER TABLE estoque_alicates ADD COLUMN IF NOT EXISTS is_seed BOOLEAN DEFAULT FALSE")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS movimentacoes_caixa (
            id SERIAL PRIMARY KEY,
            data DATE NOT NULL,
            tipo TEXT,
            descricao TEXT,
            categoria TEXT,
            valor NUMERIC(10,2),
            forma_pagamento TEXT,
            referencia_os_id INTEGER,
            hora TEXT,
            is_seed BOOLEAN DEFAULT FALSE
        )
    ''')
    cur.execute("ALTER TABLE movimentacoes_caixa ADD COLUMN IF NOT EXISTS hora TEXT")
    cur.execute("ALTER TABLE movimentacoes_caixa ADD COLUMN IF NOT EXISTS is_seed BOOLEAN DEFAULT FALSE")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS consumiveis (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            quantidade INTEGER DEFAULT 0,
            unidade TEXT,
            estoque_minimo INTEGER DEFAULT 5,
            preco_unitario NUMERIC(10,2),
            is_seed BOOLEAN DEFAULT FALSE
        )
    ''')
    cur.execute("ALTER TABLE consumiveis ADD COLUMN IF NOT EXISTS is_seed BOOLEAN DEFAULT FALSE")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS configuracoes (
            chave TEXT PRIMARY KEY,
            valor TEXT
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS vendas_alicates (
            id SERIAL PRIMARY KEY,
            produto_id INTEGER REFERENCES estoque_alicates(id),
            produto_descricao TEXT,
            cliente_nome TEXT NOT NULL,
            telefone TEXT,
            quantidade INTEGER DEFAULT 1,
            valor_unitario NUMERIC(10,2),
            valor_total NUMERIC(10,2),
            forma_pagamento TEXT,
            status TEXT DEFAULT 'reservado',
            data_registro DATE,
            data_pagamento DATE,
            is_seed BOOLEAN DEFAULT FALSE
        )
    ''')
    cur.execute("ALTER TABLE vendas_alicates ADD COLUMN IF NOT EXISTS is_seed BOOLEAN DEFAULT FALSE")

    cur.execute('''
        CREATE TABLE IF NOT EXISTS fechamentos_diarios (
            id SERIAL PRIMARY KEY,
            data DATE UNIQUE NOT NULL,
            total_entradas INTEGER DEFAULT 0,
            total_saidas INTEGER DEFAULT 0,
            faturamento_dia NUMERIC(10,2) DEFAULT 0,
            pendentes INTEGER DEFAULT 0,
            fechado_em TEXT
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS banco_clientes (
            id SERIAL PRIMARY KEY,
            nome TEXT NOT NULL,
            telefone TEXT,
            codigo_servico TEXT,
            quantidade INTEGER DEFAULT 1,
            observacao TEXT,
            data_registro DATE DEFAULT CURRENT_DATE,
            quantidade_total INTEGER DEFAULT 0,
            hora TEXT
        )
    ''')
    cur.execute("ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS quantidade_total INTEGER DEFAULT 0")
    cur.execute("ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS codigo_servico TEXT")
    cur.execute("ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS quantidade INTEGER DEFAULT 1")
    cur.execute("ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS observacao TEXT")
    cur.execute("ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS hora TEXT")
    cur.execute("ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS is_seed BOOLEAN DEFAULT FALSE")

    # Dados iniciais - consumíveis
    cur.execute("SELECT COUNT(*) AS c FROM consumiveis")
    if cur.fetchone()["c"] == 0:
        consumiveis = [
            ('Lixa d agua 600', 50, 'folha', 20, 2.50),
            ('Mola inox', 30, 'un', 10, 4.90),
            ('Oleo refrigerante', 8, 'litro', 3, 32.50),
            ('Parafuso ajuste', 40, 'un', 15, 1.90),
        ]
        for item in consumiveis:
            cur.execute(
                "INSERT INTO consumiveis (nome, quantidade, unidade, estoque_minimo, preco_unitario) VALUES (%s, %s, %s, %s, %s)",
                item,
            )

    cur.execute("SELECT COUNT(*) AS c FROM estoque_alicates")
    if cur.fetchone()["c"] == 0:
        cur.execute('''
            INSERT INTO estoque_alicates (sku, descricao, tipo, quantidade, preco_venda, estoque_minimo)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', ('ALICATE777', 'Alicate 777', 'Alicate', 0, 25.00, 5))

    cur.execute("SELECT COUNT(*) AS c FROM configuracoes WHERE chave = 'meta_diaria'")
    if cur.fetchone()["c"] == 0:
        cur.execute("INSERT INTO configuracoes (chave, valor) VALUES ('meta_diaria', '30')")

    cur.execute("SELECT COUNT(*) AS c FROM movimentacoes_caixa")
    if cur.fetchone()["c"] == 0:
        cur.execute('''
            INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento)
            VALUES (%s, 'entrada', 'Saldo inicial de caixa', 'Abertura', 120.00, 'Dinheiro')
        ''', (agora_br().strftime('%Y-%m-%d'),))

    conn.commit()
    cur.close()
    conn.close()


# ==================== FUNÇÕES UTILITÁRIAS COMPARTILHADAS ====================

def agora_br():
    """Hora atual no fuso de Brasília (UTC-3, sem horário de verão desde 2019).
    O servidor (Vercel) roda em UTC, então sem esse ajuste data e hora
    registradas ficam à frente do horário real de quem usa o sistema."""
    return datetime.now() - timedelta(hours=3)


class _RelogioBR:
    """Substitui o módulo `datetime` passado para os templates, para que
    `datetime.now()` usado direto no Jinja também já venha ajustado."""
    @staticmethod
    def now():
        return agora_br()


datetime_br = _RelogioBR()


def formatar_moeda(valor):
    if not valor:
        return "R$ 0,00"
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def formatar_data_br(data):
    if not data:
        return ""
    try:
        s = data.strftime('%Y-%m-%d') if hasattr(data, 'strftime') else str(data)
        if '-' in s:
            partes = s.split('-')
            return f"{partes[2]}/{partes[1]}/{partes[0]}"
        return s
    except Exception:
        return str(data)


def parse_valor(texto, padrao=0.0):
    """Converte '15,50' ou '15.50' em float com segurança. Nunca lança exceção."""
    if texto is None or str(texto).strip() == "":
        return padrao
    try:
        return float(str(texto).replace(',', '.').strip())
    except ValueError:
        return padrao


def parse_inteiro(texto, padrao=0):
    try:
        return int(texto)
    except (ValueError, TypeError):
        return padrao
