# Gestão Amolação

Sistema de gestão para amolação de alicates: entrada/saída de clientes, estoque,
caixa, consumíveis e mensagens de WhatsApp.

## O que mudou em relação ao código original

**Segurança**
- Senhas agora são salvas com hash (`werkzeug.security`), nunca em texto puro.
- `secret_key` e a conexão do banco vêm de variáveis de ambiente, nada fixo no código.
- `debug=True` removido do modo produção (controlado por `FLASK_DEBUG`).

**Estrutura**
- O `app.py` de 915 linhas virou vários arquivos organizados por assunto:
  - `db.py` — conexão com o banco e funções utilitárias (moeda, data, etc.)
  - `auth.py` — login/senha
  - `routes/` — um blueprint por área: `auth_routes`, `dashboard_routes`,
    `entrada_routes`, `saida_routes`, `relatorio_routes`, `caixa_routes`,
    `estoque_routes`, `consumiveis_routes`, `clientes_routes`, `mensagens_routes`.

**Bugs corrigidos**
- `consumivel_editor.html` existia mas não tinha rota nenhuma — agora
  `/consumiveis/editar/<id>` funciona e tem botão na tela de Consumíveis.
- Conversões de número (`float`/`int` de formulário) agora não quebram a
  página com erro 500 se o usuário digitar algo inválido.
- Validações de quantidade > 0 adicionadas em vendas e uso de consumíveis.
- Banco trocado de SQLite para PostgreSQL (Supabase) — **isso é obrigatório**
  para rodar no Vercel: o Vercel é serverless, o disco é somente leitura
  (exceto `/tmp`, que é apagado a cada execução), então um arquivo `.db`
  local simplesmente não sobrevive entre requisições lá.

**O que ainda vale considerar depois (não foi feito agora):**
- Proteção CSRF nos formulários (`Flask-WTF`).
- Paginação nas tabelas de caixa/clientes se a base crescer muito.
- Rate limiting no login.

---

## 1. Rodando localmente

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edite o .env com sua DATABASE_URL do Supabase e uma SECRET_KEY

export $(cat .env | xargs)   # ou use algo como python-dotenv/direnv
flask init-db                # cria as tabelas e dados iniciais no Supabase
python app.py                # roda em http://localhost:5000
```

Acesse `/cadastrar` para criar o primeiro usuário admin.

---

## 2. Criando o banco no Supabase

1. Crie uma conta em https://supabase.com e um novo projeto.
2. Vá em **Project Settings → Database → Connection string** e escolha o
   modo **"Transaction" (pooler, porta 6543)** — é o recomendado para apps
   serverless (Vercel abre e fecha conexões o tempo todo, e o pooler evita
   estourar o limite de conexões do Postgres). Copie essa URL.
3. Você tem duas opções para criar as tabelas:
   - **Opção A (mais simples):** abra o **SQL Editor** do Supabase, cole o
     conteúdo do arquivo `schema.sql` deste projeto e rode.
   - **Opção B:** rode `flask init-db` localmente (com `DATABASE_URL` já
     configurada no `.env`), que faz a mesma coisa via Python.

---

## 3. Deploy no Vercel

1. Suba este projeto para um repositório no GitHub.
2. Em https://vercel.com, clique em **Add New → Project** e importe o repositório.
3. O Vercel deve detectar o `vercel.json` automaticamente (runtime Python).
   Se pedir um "Framework Preset", pode deixar em "Other".
4. Em **Environment Variables**, adicione:
   - `DATABASE_URL` → a connection string do Supabase (pooler, passo 2 acima)
   - `SECRET_KEY` → uma chave aleatória (gere com
     `python -c "import secrets; print(secrets.token_hex(32))"`)
5. Clique em **Deploy**.
6. Depois do primeiro deploy, acesse `https://seu-projeto.vercel.app/cadastrar`
   para criar o usuário admin (isso grava direto no Supabase, então só
   precisa fazer uma vez).

### Notas importantes sobre Vercel + Flask
- O arquivo `api/index.py` é o que a Vercel realmente executa; ele só
  importa o `app` do `app.py` principal — não precisa mexer nele.
- Funções na Vercel têm timeout curto (10s no plano gratuito). As consultas
  deste sistema são simples, então não deve ser problema.
- Cada requisição pode rodar em uma instância "fria" diferente — por isso
  o código abre e fecha a conexão com o banco a cada requisição (não guarda
  conexão global), o que já é compatível com esse modelo.

---

## Estrutura de arquivos

```
app.py                  # cria o Flask app e registra os blueprints
db.py                   # conexão com Postgres/Supabase + helpers
auth.py                 # login_required, hash de senha
routes/
  auth_routes.py        # login, cadastro, logout
  dashboard_routes.py   # painel inicial
  entrada_routes.py     # entrada de clientes/alicates
  saida_routes.py       # saída/entrega
  relatorio_routes.py   # relatório do dia + fechamento
  caixa_routes.py        # movimentações financeiras
  estoque_routes.py     # estoque de alicates (venda/encomenda)
  consumiveis_routes.py # insumos (lixa, mola, óleo...)
  clientes_routes.py    # listagem de clientes
  mensagens_routes.py   # envio manual via WhatsApp Web
templates/              # os mesmos arquivos .html, com endpoints atualizados
api/index.py            # entrada usada pela Vercel
vercel.json              # config de deploy da Vercel
schema.sql               # DDL para rodar direto no SQL Editor do Supabase
requirements.txt
.env.example
```
