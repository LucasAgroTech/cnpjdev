# CNPJ Consulta

Sistema automatizado de consulta de CNPJs via API da ReceitaWS, com armazenamento em PostgreSQL.

## Características

- Processamento assíncrono de consultas de CNPJ
- Limitação inteligente de requisições por minuto para evitar bloqueios
- Importação de planilhas com lista de CNPJs
- Armazenamento dos resultados em PostgreSQL no Heroku
- Interface web para acompanhamento das consultas
- Status detalhado de cada consulta (sucesso/erro)
- **Persistência de processamento**: retoma automaticamente de onde parou após reinicialização
- **Mecanismo de retry**: tenta novamente em caso de falhas temporárias
- **Endpoints de administração**: para monitorar e reiniciar o processamento
- **Exportação para Excel**: permite baixar os resultados em formato Excel

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

## Persistência de Processamento

O sistema implementa um mecanismo de persistência que garante que o processamento de CNPJs continue mesmo após uma reinicialização do servidor (por exemplo, quando o dyno do Heroku é reiniciado).

### Como funciona

1. Quando a aplicação é iniciada, ela verifica no banco de dados se existem CNPJs com status "queued" ou "processing"
2. Esses CNPJs são carregados na fila de processamento e o processamento é retomado automaticamente
3. O sistema implementa um mecanismo de retry que tenta processar novamente CNPJs que falharam devido a erros temporários

### Configurações de Persistência

No arquivo `.env`, você pode configurar:

- `AUTO_RESTART_QUEUE`: Define se o processamento deve ser retomado automaticamente na inicialização (padrão: True)
- `MAX_RETRY_ATTEMPTS`: Número máximo de tentativas para processar um CNPJ em caso de falha (padrão: 3)

### Endpoints de Administração

O sistema oferece endpoints de administração para monitorar e controlar o processamento:

- `GET /api/admin/queue/status`: Retorna o status atual da fila, incluindo contagem de CNPJs por status e lista dos 10 CNPJs pendentes mais recentes
- `POST /api/admin/queue/restart`: Reinicia manualmente o processamento de CNPJs pendentes

Exemplo de uso:

```bash
# Verificar status da fila
curl http://localhost:8000/api/admin/queue/status

# Reiniciar processamento
curl -X POST http://localhost:8000/api/admin/queue/restart
```

## Exportação para Excel

O sistema permite exportar os dados de CNPJs consultados para um arquivo Excel, facilitando a análise e o compartilhamento dos resultados.

### Opções de Exportação

A interface web oferece várias opções para exportação:

- **Exportar Todos**: Exporta todos os CNPJs consultados
- **Apenas Concluídos**: Exporta apenas os CNPJs com status "completed"
- **Selecionados**: Exporta apenas os CNPJs selecionados na tabela

### Endpoint de API

O endpoint de exportação para Excel também pode ser acessado diretamente:

- `GET /api/export-excel/`: Exporta todos os CNPJs
- `GET /api/export-excel/?status=completed`: Exporta apenas CNPJs com status "completed"
- `GET /api/export-excel/?cnpjs=00000000000000&cnpjs=11111111111111`: Exporta CNPJs específicos

O arquivo Excel gerado contém todas as informações disponíveis para cada CNPJ, incluindo:
- Dados cadastrais (Razão Social, Nome Fantasia)
- Endereço completo
- Contatos (Email, Telefone)
- Informações sobre Simples Nacional
- Data da consulta
