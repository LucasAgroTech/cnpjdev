# Gerenciamento da Fila de CNPJs

Este documento descreve as melhorias implementadas no sistema de fila para processamento de CNPJs e como utilizar as ferramentas de gerenciamento.

## Problema Resolvido

O sistema estava acumulando muitos CNPJs com status "Em Processo", o que dificultava o acompanhamento e causava problemas de processamento. As melhorias implementadas garantem que:

1. O número de CNPJs em processamento simultâneo seja limitado de acordo com a capacidade da API (3 requisições por minuto)
2. CNPJs presos em processamento sejam identificados e liberados mais rapidamente
3. O sistema respeite o intervalo mínimo entre requisições para evitar erros de limite de taxa

## Principais Alterações

### 1. Limitação de Processamento Ativo

- O sistema agora limita o número de CNPJs em processamento simultâneo para `REQUESTS_PER_MINUTE + 2` (5 CNPJs)
- Isso garante que sempre haja CNPJs prontos para serem processados, mas sem acumular muitos em estado "Em Processo"

### 2. Melhoria no Mecanismo de Limpeza

- O intervalo de verificação de CNPJs presos foi reduzido de 5 minutos para 1 minuto
- O tempo para considerar um CNPJ como "preso" foi reduzido de 10 para 5 minutos
- Isso permite que CNPJs travados sejam liberados mais rapidamente

### 3. Controle de Fluxo na Fila

- Implementado um mecanismo que respeita o intervalo mínimo entre requisições (20 segundos para 3 req/min)
- O sistema verifica quantos CNPJs já estão em processamento antes de iniciar novos
- Isso garante que o sistema não tente processar mais CNPJs do que a API permite

### 4. Tratamento de Erros Aprimorado

- Melhor tratamento de erros para falhar mais rapidamente em casos específicos
- Implementado tratamento de erros global para garantir que CNPJs não fiquem presos em processamento

## Ferramentas de Gerenciamento

Foram criadas quatro ferramentas para ajudar no gerenciamento da fila:

### 1. Script de Reinício da Fila (`restart_queue.py`)

Este script permite reiniciar o processamento da fila de CNPJs pendentes.

**Uso:**
```
python restart_queue.py [URL_BASE]
```

**Exemplo:**
```
python restart_queue.py https://seu-app.herokuapp.com
```

### 2. Script de Verificação de Status (`check_queue_status.py`)

Este script permite verificar o status atual da fila, mostrando quantos CNPJs estão em cada estado.

**Uso:**
```
python check_queue_status.py [URL_BASE] [INTERVALO] [CONTAGEM]
```

- **URL_BASE**: URL base da API (ex: https://seu-app.herokuapp.com)
- **INTERVALO**: Intervalo em segundos entre verificações (padrão: 10)
- **CONTAGEM**: Número de verificações a realizar (padrão: 1, 0 para contínuo)

**Exemplos:**
```
# Verificação única
python check_queue_status.py https://seu-app.herokuapp.com

# Verificação a cada 5 segundos, 10 vezes
python check_queue_status.py https://seu-app.herokuapp.com 5 10

# Verificação contínua a cada 30 segundos (até Ctrl+C)
python check_queue_status.py https://seu-app.herokuapp.com 30 0
```

### 3. Script para Resetar CNPJs com Erro (`fix_error_cnpjs.py`)

Este script conecta-se diretamente ao banco de dados para resetar CNPJs com status de erro para "queued" e recolocá-los na fila de processamento. Ele é mais robusto e não depende de endpoints da API.

**Uso:**
```
python3 fix_error_cnpjs.py [opções]
```

**Opções:**
- `--db-url URL` - URL de conexão com o banco de dados (ex: postgresql://usuario:senha@host:porta/nome_banco)
- `--api-url URL` - URL base da API para reiniciar a fila (ex: https://seu-app.herokuapp.com)
- `--no-restart` - Não reiniciar a fila após resetar os CNPJs
- `--verbose` ou `-v` - Mostrar informações detalhadas sobre os CNPJs com erro

**Exemplos:**
```
# Usando a URL do banco de dados do arquivo .env e reiniciando a fila
python3 fix_error_cnpjs.py --api-url https://seu-app.herokuapp.com

# Especificando a URL do banco de dados diretamente
python3 fix_error_cnpjs.py --db-url postgresql://usuario:senha@host:porta/nome_banco

# Mostrando detalhes dos CNPJs com erro
python3 fix_error_cnpjs.py --verbose

# Apenas resetando os CNPJs sem reiniciar a fila
python3 fix_error_cnpjs.py --no-restart
```

**Exemplo para o Heroku:**
```
# Para o banco de dados do Heroku
python3 fix_error_cnpjs.py --db-url postgres://usuario:senha@host:porta/nome_banco --api-url https://seu-app.herokuapp.com
```

Este script é a maneira recomendada para lidar com CNPJs que falharam durante o processamento, pois conecta-se diretamente ao banco de dados e não depende de endpoints da API.

### 4. Script de Atualização (`deploy_update.sh`)

Este script facilita o deploy das alterações no Heroku.

**Uso:**
```
./deploy_update.sh
```

O script irá solicitar o nome do seu app no Heroku e cuidará do processo de deploy.

## Recomendações de Uso

1. Após o deploy das alterações, use o script `restart_queue.py` para reiniciar o processamento da fila
2. Use o script `check_queue_status.py` para monitorar o status da fila e verificar se as alterações estão funcionando corretamente
3. Se houver CNPJs com erro, use o script `fix_error_cnpjs.py` para recolocá-los na fila
4. Se ainda houver problemas, verifique os logs do Heroku para identificar possíveis erros

## Configurações Recomendadas

As configurações atuais são otimizadas para o limite de 3 requisições por minuto da API ReceitaWS. Se necessário, você pode ajustar os seguintes parâmetros no arquivo `.env`:

```
# Limite de requisições por minuto da API
REQUESTS_PER_MINUTE=3

# Número máximo de tentativas para processar um CNPJ
MAX_RETRY_ATTEMPTS=3

# Reiniciar automaticamente a fila na inicialização
AUTO_RESTART_QUEUE=True
```
