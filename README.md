# BomFin — Portfolio (finance-bomfin-portfolio)

Versão pública e sanitizada do sistema de planejamento financeiro **BomFin**: API **FastAPI** + interface **React (Vite/TypeScript)**.

Este repositório é destinado a portfólio. Dados pessoais, faturas reais, URLs de produção e segredos foram removidos ou substituídos por fixtures sintéticas.

## Destaques técnicos

- Autenticação JWT, gestão de usuários/admin e troca obrigatória de senha
- Importação de fatura de cartão (CSV/PDF — Nubank, Itaú, Santander) com preview e confirmação
- Rateio de compras entre pessoas (split) e templates de divisão
- Metas com **pool** compartilhado por período
- Notificações (cartões, metas, viagens, devedores)
- Módulo de viagens com settlement entre participantes
- Migrações Alembic + patches de schema para SQLite/Postgres

## Requisitos

- Python 3.11+
- Node.js 18+ (frontend)
- (Opcional) PostgreSQL; o padrão é SQLite para desenvolvimento

## Configuração

1. Ambiente virtual e dependências:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Copie `.env.example` para `.env` e ajuste `DATABASE_URL` e `SECRET_KEY`.

3. Migrações:

```bash
alembic upgrade head
```

4. API:

```bash
uvicorn app.main:app --reload
```

Docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Abra [http://127.0.0.1:5173](http://127.0.0.1:5173) — o Vite faz proxy de `/api` para `http://127.0.0.1:8000`.

## Testes

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Fixtures de fatura nos testes são **sintéticas** (sem dados financeiros pessoais).

## Autenticação (resumo)

- `POST /api/v1/auth/register` — cadastro
- `POST /api/v1/auth/login` — retorna `access_token` (JWT)

Admin local:

```bash
python -m app.cli.manage_user create-admin --email admin@exemplo.com --name "Admin" --password "SenhaSegura"
```

## Seed

```bash
python -m app.seed.run_seed --email seu@email.com
```

## Deploy (opcional)

Arquivos de exemplo: `Dockerfile`, `render.yaml`, `netlify.toml`, `*.env.example`.  
Use URLs placeholder (`your-api.example.com` / `your-frontend.example.com`) — não há endpoints de produção neste repo.

```bash
docker build -t finance-bomfin-portfolio-api .
docker run -p 8000:8000 --env-file .env finance-bomfin-portfolio-api
```

## Estrutura

- `app/` — backend FastAPI (routers, services, repositories, models, schemas)
- `frontend/` — SPA React + Vite + TypeScript
- `tests/` — pytest
- `alembic/` — migrações

## Prefixo da API

Rotas de negócio sob `/api/v1`.
