# CNPJ Consulta

Sistema automatizado de consulta de CNPJs via múltiplas APIs (ReceitaWS, CNPJ.ws e CNPJa Open), com armazenamento em PostgreSQL.
![Dashboard](dashboard.png)

## Características

- Processamento assíncrono de consultas de CNPJ
- Sistema de rotação entre múltiplas APIs para maximizar o throughput
- Processamento de até 11 CNPJs por minuto (3 + 3 + 5 de cada API)
- Limitação inteligente de requisições por minuto para evitar bloqueios
- Fallback automático entre APIs em caso de falha ou limite de requisições
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

Edite o arquivo `.env` com suas configurações:

```
# Configuração das APIs
RECEITAWS_ENABLED=True
CNPJWS_ENABLED=True
CNPJA_OPEN_ENABLED=True
RECEITAWS_REQUESTS_PER_MINUTE=3
CNPJWS_REQUESTS_PER_MINUTE=3
CNPJA_OPEN_REQUESTS_PER_MINUTE=5

# Banco de dados
DATABASE_URL=postgresql://usuario:senha@host:porta/nome_banco

# Outras configurações
DEBUG=False
AUTO_RESTART_QUEUE=True
MAX_RETRY_ATTEMPTS=3
```

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
heroku config:set RECEITAWS_ENABLED=True
heroku config:set CNPJWS_ENABLED=True
heroku config:set CNPJA_OPEN_ENABLED=True
heroku config:set RECEITAWS_REQUESTS_PER_MINUTE=3
heroku config:set CNPJWS_REQUESTS_PER_MINUTE=3
heroku config:set CNPJA_OPEN_REQUESTS_PER_MINUTE=5
heroku config:set AUTO_RESTART_QUEUE=True
heroku config:set MAX_RETRY_ATTEMPTS=3
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

## Sistema de Múltiplas APIs

O sistema utiliza três APIs diferentes para consulta de CNPJs, aumentando significativamente a capacidade de processamento e adicionando redundância.

### APIs Suportadas

- **ReceitaWS**: 3 requisições por minuto
- **CNPJ.ws**: 3 requisições por minuto
- **CNPJa Open**: 5 requisições por minuto

### Capacidade Total

Com as três APIs habilitadas, o sistema pode processar até **11 CNPJs por minuto**, um aumento significativo em relação ao uso de apenas uma API.

### Como Funciona o Sistema de Rotação

1. Quando uma consulta de CNPJ é solicitada, o sistema seleciona aleatoriamente uma das APIs habilitadas
2. Se a API selecionada estiver no limite de requisições ou falhar, o sistema automaticamente tenta outra API
3. O sistema mantém controle das requisições feitas para cada API, respeitando seus limites individuais
4. Os resultados são normalizados para um formato padrão, independentemente da API utilizada

### Configuração das APIs

Cada API pode ser habilitada ou desabilitada individualmente através das variáveis de ambiente:

- `RECEITAWS_ENABLED`: Habilita/desabilita a API ReceitaWS
- `CNPJWS_ENABLED`: Habilita/desabilita a API CNPJ.ws
- `CNPJA_OPEN_ENABLED`: Habilita/desabilita a API CNPJa Open

Os limites de requisições também podem ser ajustados:

- `RECEITAWS_REQUESTS_PER_MINUTE`: Limite para ReceitaWS (padrão: 3)
- `CNPJWS_REQUESTS_PER_MINUTE`: Limite para CNPJ.ws (padrão: 3)
- `CNPJA_OPEN_REQUESTS_PER_MINUTE`: Limite para CNPJa Open (padrão: 5)

## Algoritmos e Otimizações

O sistema implementa algoritmos sofisticados para gerenciar o processamento de CNPJs e maximizar o throughput, respeitando os limites de cada API.

### Token Bucket

O sistema utiliza o algoritmo Token Bucket para controle preciso da taxa de requisições para cada API:

```python
class TokenBucket:
    """
    Implementação do algoritmo Token Bucket para controle de taxa de requisições.
    
    O Token Bucket é um algoritmo usado para controlar a taxa na qual um processo
    pode consumir recursos. Neste caso, é usado para controlar a taxa de requisições
    para uma API específica.
    
    Cada bucket é preenchido com tokens a uma taxa constante (refill_rate).
    Quando uma requisição é feita, um token é consumido do bucket.
    Se não houver tokens disponíveis, a requisição é rejeitada.
    """
```

#### Como funciona o Token Bucket:

1. Cada API tem seu próprio "bucket" (balde) com capacidade máxima definida pelo limite de requisições por minuto
2. Os tokens são adicionados ao bucket a uma taxa constante (tokens por segundo)
3. Quando uma requisição é feita, um token é consumido do bucket
4. Se não houver tokens disponíveis, a requisição é rejeitada ou colocada em espera
5. Este mecanismo garante matematicamente que o limite de requisições não será excedido

#### Vantagens do Token Bucket:

- **Precisão matemática**: Garante que os limites de cada API sejam respeitados
- **Distribuição suave**: Distribui as requisições uniformemente ao longo do tempo
- **Flexibilidade**: Permite ajustes finos através de fatores de segurança

### Limitador de Taxa Adaptativo

O sistema implementa um limitador de taxa adaptativo que ajusta dinamicamente os fatores de segurança com base no desempenho de cada API:

```python
class AdaptiveRateLimiter:
    """
    Gerenciador adaptativo de limites de taxa para múltiplas APIs.
    
    Implementa um sistema de controle de taxa baseado em Token Bucket
    com ajuste dinâmico de fatores de segurança e distribuição inteligente
    de requisições entre as APIs disponíveis.
    """
```

#### Fatores de Segurança Dinâmicos:

- **Fator de segurança inicial**: Baseado no limite de requisições da API
  - APIs com limite baixo (≤ 3 req/min): Fator mais conservador (0.7)
  - APIs com limite alto (> 3 req/min): Fator menos conservador (0.8)

- **Ajuste automático**:
  - **Redução após erros**: Quando uma API retorna erro de limite excedido, seu fator de segurança é reduzido
  - **Aumento gradual após sucesso**: Após várias requisições bem-sucedidas, o fator é aumentado gradualmente

#### Sistema de Backoff Exponencial:

Quando uma API atinge seu limite, é implementado um sistema de backoff exponencial:

```python
# Calcula o tempo de cooldown com base no número de erros
# Usa backoff exponencial com limite máximo
error_count = self.api_info[api_name]["error_count"]
cooldown_time = min(API_COOLDOWN_AFTER_RATE_LIMIT * (2 ** (error_count - 1)), API_COOLDOWN_MAX)
```

- Primeiro erro: cooldown de 60 segundos
- Segundo erro: cooldown de 120 segundos
- Terceiro erro: cooldown de 240 segundos
- E assim por diante, até o limite máximo configurado (300 segundos)

### Escalonador Central Inteligente

Um escalonador central gerencia todas as APIs e seleciona a melhor para cada requisição:

```python
def get_best_api(self) -> Optional[str]:
    """
    Seleciona a melhor API para usar no momento, com base na disponibilidade
    e no histórico de uso.
    """
```

O escalonador considera múltiplos fatores para selecionar a API:

1. **Número de tokens disponíveis**: Prioriza APIs com mais tokens disponíveis
2. **Tempo desde o último uso**: Prioriza APIs que não foram usadas recentemente
3. **Histórico de erros**: Penaliza APIs com histórico de erros
4. **Fator aleatório**: Adiciona um pequeno fator aleatório para evitar concentração

A pontuação final é calculada como uma combinação ponderada desses fatores:

```python
# Pontuação final: combinação ponderada dos fatores
# Dá mais peso ao número de tokens disponíveis e ao tempo desde o último uso
final_score = (0.4 * token_score) + (0.4 * time_score) + (0.15 * error_factor) + random_factor
```

### Sistema de Fila com Persistência

O sistema implementa uma fila de processamento com persistência, garantindo que o processamento continue mesmo após reinicialização do servidor:

```python
class CNPJQueue:
    """
    Gerenciador de fila para consultas de CNPJ
    
    Status possíveis:
    - queued: CNPJ na fila para processamento
    - processing: CNPJ em processamento
    - completed: CNPJ processado com sucesso
    - error: Erro permanente no processamento (CNPJ não encontrado, etc)
    - rate_limited: Erro temporário por limite de requisições excedido
    """
```

#### Características do sistema de fila:

1. **Persistência**: O estado da fila é armazenado no banco de dados, permitindo que o processamento continue após reinicialização
2. **Processamento assíncrono**: Utiliza asyncio para processamento assíncrono eficiente
3. **Controle de concorrência**: Limita o número de CNPJs em processamento simultâneo
4. **Mecanismo de retry**: Tenta processar novamente CNPJs que falharam devido a erros temporários
5. **Limpeza automática**: Detecta e corrige CNPJs presos em processamento

#### Mecanismo de retry:

O sistema implementa um mecanismo de retry com backoff exponencial:

```python
# Se não for a primeira tentativa, aguarda um pouco mais
if retry_count > 0:
    wait_time = min(2 ** retry_count, 8)  # Backoff exponencial com limite máximo de 8s
    logger.info(f"Tentativa {retry_count+1} para CNPJ {cnpj}, aguardando {wait_time}s")
    await asyncio.sleep(wait_time)
```

- Primeira tentativa: imediata
- Segunda tentativa: espera 2 segundos
- Terceira tentativa: espera 4 segundos
- Quarta tentativa: espera 8 segundos (limite máximo)

## Configuração Detalhada das Variáveis de Ambiente

O sistema oferece diversas variáveis de ambiente para configuração fina do comportamento. Abaixo estão todas as variáveis disponíveis, seus propósitos e valores recomendados:

### Configuração das APIs

| Variável | Descrição | Valor Padrão | Recomendação |
|----------|-----------|--------------|--------------|
| `RECEITAWS_ENABLED` | Habilita/desabilita a API ReceitaWS | `True` | Manter habilitada para maximizar throughput |
| `CNPJWS_ENABLED` | Habilita/desabilita a API CNPJ.ws | `True` | Manter habilitada para maximizar throughput |
| `CNPJA_OPEN_ENABLED` | Habilita/desabilita a API CNPJa Open | `True` | Manter habilitada para maximizar throughput |
| `RECEITAWS_REQUESTS_PER_MINUTE` | Limite de requisições por minuto para ReceitaWS | `3` | Não exceder o limite da API (3) |
| `CNPJWS_REQUESTS_PER_MINUTE` | Limite de requisições por minuto para CNPJ.ws | `3` | Não exceder o limite da API (3) |
| `CNPJA_OPEN_REQUESTS_PER_MINUTE` | Limite de requisições por minuto para CNPJa Open | `5` | Não exceder o limite da API (5) |
| `REQUESTS_PER_MINUTE` | Limite total de requisições por minuto (compatibilidade) | `11` | Deve ser igual à soma das taxas individuais |

### Configuração de Controle de Taxa

| Variável | Descrição | Valor Padrão | Recomendação |
|----------|-----------|--------------|--------------|
| `MAX_CONCURRENT_PROCESSING` | Número máximo de CNPJs em processamento simultâneo | `4` | 4-6 para equilíbrio entre throughput e estabilidade |
| `API_COOLDOWN_AFTER_RATE_LIMIT` | Tempo base de cooldown (segundos) após erro de limite excedido | `60` | 60-120 para evitar bloqueios prolongados |
| `API_COOLDOWN_MAX` | Tempo máximo de cooldown (segundos) | `300` | 300-600 para casos extremos |
| `API_RATE_LIMIT_SAFETY_FACTOR` | Fator de segurança padrão (compatibilidade) | `0.9` | 0.8-0.9 para equilíbrio entre segurança e throughput |
| `API_RATE_LIMIT_SAFETY_FACTOR_LOW` | Fator de segurança para APIs com limite baixo | `0.7` | 0.6-0.7 para APIs com limite ≤ 3 req/min |
| `API_RATE_LIMIT_SAFETY_FACTOR_HIGH` | Fator de segurança para APIs com limite alto | `0.8` | 0.7-0.8 para APIs com limite > 3 req/min |
| `API_RATE_LIMIT_THRESHOLD` | Limite que define o que é uma API com limite "baixo" | `3` | 3 é adequado para o contexto atual |

### Configuração de Persistência

| Variável | Descrição | Valor Padrão | Recomendação |
|----------|-----------|--------------|--------------|
| `AUTO_RESTART_QUEUE` | Reinicia automaticamente o processamento na inicialização | `True` | Manter `True` para garantir continuidade |
| `MAX_RETRY_ATTEMPTS` | Número máximo de tentativas para processar um CNPJ | `3` | 3-5 dependendo da criticidade |

### Configuração da Aplicação

| Variável | Descrição | Valor Padrão | Recomendação |
|----------|-----------|--------------|--------------|
| `DEBUG` | Modo de depuração | `False` | `True` em desenvolvimento, `False` em produção |
| `DATABASE_URL` | URL de conexão com o banco de dados | - | Configurar de acordo com seu ambiente |

### Interdependências entre Variáveis

Algumas variáveis têm interdependências importantes:

1. **Soma das taxas individuais**: A variável `REQUESTS_PER_MINUTE` deve ser igual à soma de `RECEITAWS_REQUESTS_PER_MINUTE`, `CNPJWS_REQUESTS_PER_MINUTE` e `CNPJA_OPEN_REQUESTS_PER_MINUTE` para as APIs habilitadas.

2. **Fatores de segurança**: Os fatores `API_RATE_LIMIT_SAFETY_FACTOR_LOW` e `API_RATE_LIMIT_SAFETY_FACTOR_HIGH` são aplicados com base no valor de `API_RATE_LIMIT_THRESHOLD`.

3. **Concorrência e throughput**: `MAX_CONCURRENT_PROCESSING` deve ser ajustado considerando o throughput total (`REQUESTS_PER_MINUTE`). Um valor muito alto pode causar erros de limite excedido, enquanto um valor muito baixo pode subutilizar as APIs.

## Limitações das APIs

Cada API tem seu próprio limite de requisições por minuto:

- ReceitaWS: 3 requisições por minuto
- CNPJ.ws: 3 requisições por minuto
- CNPJa Open: 5 requisições por minuto

O sistema está configurado para respeitar esses limites e evitar bloqueios, controlando a taxa de requisições para cada API individualmente.

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
