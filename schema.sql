-- Gestão Amolação - schema para Supabase (Postgres)
-- Cole isso no SQL Editor do Supabase e rode uma vez.
-- (Alternativa a rodar `flask init-db` a partir do seu computador.)

CREATE TABLE IF NOT EXISTS usuarios (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    usuario TEXT UNIQUE NOT NULL,
    senha_hash TEXT NOT NULL,
    data_cadastro DATE DEFAULT CURRENT_DATE
);

CREATE TABLE IF NOT EXISTS clientes (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    telefone TEXT,
    endereco TEXT,
    codigo_seguranca TEXT,
    data_cadastro DATE DEFAULT CURRENT_DATE
);

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
    hora_entrega TEXT
);
ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS hora_entrada TEXT;
ALTER TABLE ordens_servico ADD COLUMN IF NOT EXISTS hora_entrega TEXT;

CREATE TABLE IF NOT EXISTS estoque_alicates (
    id SERIAL PRIMARY KEY,
    sku TEXT UNIQUE NOT NULL,
    descricao TEXT NOT NULL,
    tipo TEXT,
    quantidade INTEGER DEFAULT 0,
    preco_venda NUMERIC(10,2),
    estoque_minimo INTEGER DEFAULT 5
);

CREATE TABLE IF NOT EXISTS movimentacoes_caixa (
    id SERIAL PRIMARY KEY,
    data DATE NOT NULL,
    tipo TEXT,
    descricao TEXT,
    categoria TEXT,
    valor NUMERIC(10,2),
    forma_pagamento TEXT,
    referencia_os_id INTEGER,
    hora TEXT
);
ALTER TABLE movimentacoes_caixa ADD COLUMN IF NOT EXISTS hora TEXT;

CREATE TABLE IF NOT EXISTS consumiveis (
    id SERIAL PRIMARY KEY,
    nome TEXT NOT NULL,
    quantidade INTEGER DEFAULT 0,
    unidade TEXT,
    estoque_minimo INTEGER DEFAULT 5,
    preco_unitario NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS configuracoes (
    chave TEXT PRIMARY KEY,
    valor TEXT
);

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
    data_pagamento DATE
);

CREATE TABLE IF NOT EXISTS fechamentos_diarios (
    id SERIAL PRIMARY KEY,
    data DATE UNIQUE NOT NULL,
    total_entradas INTEGER DEFAULT 0,
    total_saidas INTEGER DEFAULT 0,
    faturamento_dia NUMERIC(10,2) DEFAULT 0,
    pendentes INTEGER DEFAULT 0,
    fechado_em TEXT
);

-- Histórico permanente de retiradas já pagas: um registro por retirada
-- (nome, telefone, serviço/quantidade e observação daquele pedido),
-- para consulta rápida sem depender dos pedidos do dia.
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
);
-- Idempotente: adiciona as colunas em bancos que já tinham a tabela criada
-- antes delas existirem (ex: produção, que não roda init_db automaticamente).
ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS quantidade_total INTEGER DEFAULT 0;
ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS codigo_servico TEXT;
ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS quantidade INTEGER DEFAULT 1;
ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS observacao TEXT;
ALTER TABLE banco_clientes ADD COLUMN IF NOT EXISTS hora TEXT;

-- Dados iniciais
INSERT INTO consumiveis (nome, quantidade, unidade, estoque_minimo, preco_unitario)
SELECT * FROM (VALUES
    ('Lixa d agua 600', 50, 'folha', 20, 2.50),
    ('Mola inox', 30, 'un', 10, 4.90),
    ('Oleo refrigerante', 8, 'litro', 3, 32.50),
    ('Parafuso ajuste', 40, 'un', 15, 1.90)
) AS v(nome, quantidade, unidade, estoque_minimo, preco_unitario)
WHERE NOT EXISTS (SELECT 1 FROM consumiveis);

INSERT INTO estoque_alicates (sku, descricao, tipo, quantidade, preco_venda, estoque_minimo)
SELECT 'ALICATE777', 'Alicate 777', 'Alicate', 0, 25.00, 5
WHERE NOT EXISTS (SELECT 1 FROM estoque_alicates);

INSERT INTO configuracoes (chave, valor)
SELECT 'meta_diaria', '30'
WHERE NOT EXISTS (SELECT 1 FROM configuracoes WHERE chave = 'meta_diaria');

INSERT INTO movimentacoes_caixa (data, tipo, descricao, categoria, valor, forma_pagamento)
SELECT CURRENT_DATE, 'entrada', 'Saldo inicial de caixa', 'Abertura', 120.00, 'Dinheiro'
WHERE NOT EXISTS (SELECT 1 FROM movimentacoes_caixa);
