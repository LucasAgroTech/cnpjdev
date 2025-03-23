# CNPJ Consulta

Sistema automatizado de consulta de CNPJs via API da ReceitaWS, com armazenamento em PostgreSQL.

## Características

- Processamento assíncrono de consultas de CNPJ
- Limitação inteligente de requisições por minuto para evitar bloqueios
- Importação de planilhas com lista de CNPJs
- Armazenamento dos resultados em PostgreSQL no Heroku
- Interface web para acompanhamento das consultas
- Status detalhado de cada consulta (sucesso/erro)

## Requisitos

- Python 3.11+
- PostgreSQL

## Configuração Local

### 1. Clone o repositório

```bash
git clone https://github.com/seu-usuario/cnpj-consulta.git
cd cnpj-consulta
```

### 2. Crie e ative um ambiente virtual

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Crie um arquivo `.env` baseado no exemplo `.env.example`:

```bash
cp .env.example .env
```

Edite o arquivo `.env` com suas chaves de API e configurações do banco de dados.

### 5. Execute as migrações do banco de dados

```bash
alembic upgrade head
```

### 6. Inicie o servidor de desenvolvimento

```bash
uvicorn app.main:app --reload
```

Acesse a aplicação em http://localhost:8000

## Implantação no Heroku

### 1. Crie um aplicativo no Heroku

```bash
heroku create nome-do-seu-app
```

### 2. Adicione o complemento de PostgreSQL

```bash
heroku addons:create heroku-postgresql:mini
```

### 3. Configure as variáveis de ambiente

```bash
heroku config:set REQUESTS_PER_MINUTE=3
```

### 4. Implante o código

```bash
git push heroku main
```

### 5. Execute as migrações do banco de dados

```bash
heroku run alembic upgrade head
```

### 6. Abra a aplicação

```bash
heroku open
```

## Uso

### Upload de Arquivo

1. Acesse a interface web
2. Clique em "Selecionar Arquivo" e escolha um arquivo CSV ou Excel contendo CNPJs
3. Clique em "Enviar Arquivo"
4. Acompanhe o status das consultas na tabela à direita

### Consulta Manual

1. Acesse a interface web
2. Digite um CNPJ no campo de consulta manual
3. Clique em "Consultar CNPJ"
4. Acompanhe o status da consulta na tabela à direita

## Estrutura do Projeto

```
cnpj-consulta/
│
├── app/                   # Código da aplicação
│   ├── api/               # Endpoints da API
│   ├── models/            # Modelos do banco de dados
│   ├── services/          # Serviços (cliente API, fila)
│   └── utils/             # Utilitários
│
├── alembic/               # Migrações do banco de dados
├── templates/             # Templates HTML
├── .env.example           # Exemplo de variáveis de ambiente
├── Procfile               # Configuração para o Heroku
├── requirements.txt       # Dependências do projeto
└── runtime.txt            # Versão do Python para o Heroku
```

## Limitações da API

A API da ReceitaWS tem limite de 3 requisições por minuto. Este sistema está configurado para respeitar esse limite e evitar bloqueios, controlando a taxa de requisições.
