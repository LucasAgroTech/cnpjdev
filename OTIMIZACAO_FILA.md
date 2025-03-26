# Otimização da Fila de Processamento de CNPJs

Este documento descreve as otimizações implementadas na fila de processamento de CNPJs para garantir o máximo aproveitamento das APIs disponíveis.

## Problema Original

O sistema utiliza três APIs diferentes para consulta de CNPJs:

1. **ReceitaWS**: Limite de 3 requisições por minuto
2. **CNPJ.ws**: Limite de 3 requisições por minuto
3. **CNPJa Open**: Limite de 5 requisições por minuto

Isso totaliza 11 requisições por minuto (3 + 3 + 5 = 11).

No entanto, o sistema não estava distribuindo corretamente as requisições entre as APIs, o que resultava em:

- Subutilização das APIs disponíveis
- Erros de limite de taxa excedido
- Processamento mais lento do que o possível

## Otimizações Implementadas

### 1. Cálculo Correto do Intervalo Entre Requisições

Agora o sistema calcula o intervalo entre requisições com base na soma das taxas individuais das APIs:

```python
# Soma das taxas individuais das APIs para obter a taxa total
TOTAL_REQUESTS_PER_MINUTE = (RECEITAWS_REQUESTS_PER_MINUTE + 
                            CNPJWS_REQUESTS_PER_MINUTE + 
                            CNPJA_OPEN_REQUESTS_PER_MINUTE)

# Intervalo exato entre requisições para atingir a taxa total desejada
EXACT_INTERVAL_SECONDS = 60.0 / TOTAL_REQUESTS_PER_MINUTE
```

### 2. Distribuição Inteligente Entre APIs

O algoritmo de distribuição de requisições entre as APIs foi aprimorado para:

- Priorizar APIs que não foram usadas recentemente
- Considerar o tempo decorrido desde o último uso de cada API
- Adicionar um pequeno fator aleatório para evitar que todas as APIs com o mesmo tempo desde o último uso tenham exatamente a mesma pontuação

```python
# Calcula o tempo desde o último uso em segundos
time_since_last_use = now - last_used if last_used > 0 else float('inf')

# Se a API não foi usada recentemente (mais de 60 segundos), ela tem prioridade máxima
if time_since_last_use > 60:
    score = limit * 2  # Pontuação máxima com bônus para APIs não usadas recentemente
else:
    # Calcula a capacidade disponível com base no tempo desde o último uso
    # Quanto mais tempo passou desde o último uso, maior a capacidade disponível
    time_factor = min(1.0, time_since_last_use / 60.0)
    
    # Adiciona um pequeno fator aleatório para evitar que todas as APIs com o mesmo
    # tempo desde o último uso tenham exatamente a mesma pontuação
    random_factor = 0.1 * random.random()
    
    # Calcula a pontuação final
    available_capacity = limit * time_factor
    score = available_capacity + random_factor
```

### 3. Controle Rigoroso de Taxa por API Individual

Foi implementado um controle de taxa rigoroso para cada API individualmente, garantindo que os limites não sejam excedidos:

```python
# Verifica se uma API pode ser usada no momento
def can_use_api(self, api_name: str) -> bool:
    now = time.time()
    usage_info = self.api_usage[api_name]
    
    # Verifica se a API está em cooldown após erro 429
    if now < usage_info["cooldown_until"]:
        return False
    
    # Remove timestamps mais antigos que 60 segundos
    usage_info["requests"] = [t for t in usage_info["requests"] if now - t < 60]
    
    # Verifica se ainda há capacidade disponível
    adjusted_limit = usage_info["adjusted_limit"]
    current_usage = len(usage_info["requests"])
    
    return current_usage < adjusted_limit
```

### 4. Fator de Segurança para Limites de API

Foi adicionado um fator de segurança para evitar atingir o limite exato das APIs:

```python
# Aplica fator de segurança para evitar atingir o limite exato
adjusted_limit = int(api.requests_per_minute * API_RATE_LIMIT_SAFETY_FACTOR)
```

### 5. Período de Cooldown Após Erro de Limite Excedido

Quando uma API retorna erro de limite excedido (429), ela é colocada em cooldown por um período definido:

```python
# Marca uma API como tendo atingido seu limite de requisições
def mark_api_rate_limited(self, api_name: str) -> None:
    now = time.time()
    self.api_usage[api_name]["cooldown_until"] = now + API_COOLDOWN_AFTER_RATE_LIMIT
```

### 6. Limitação da Concorrência Máxima

O número máximo de CNPJs em processamento simultâneo foi reduzido para evitar picos de requisições:

```python
# Limita o número de CNPJs em processamento simultâneo
# Usa o valor configurado de MAX_CONCURRENT_PROCESSING para evitar sobrecarga
if processing_count >= MAX_CONCURRENT_PROCESSING:
    logger.debug(f"Já existem {processing_count} CNPJs em processamento (limite: {MAX_CONCURRENT_PROCESSING}). Aguardando...")
    await asyncio.sleep(min_interval_seconds)
    continue
```

### 7. Limpeza de Variáveis de Ambiente

Foram removidas variáveis de ambiente não relacionadas à aplicação que poderiam estar causando confusão.

### 8. Script de Deploy Aprimorado

O script de deploy foi atualizado para:

- Calcular automaticamente a soma das taxas individuais das APIs
- Verificar e configurar corretamente as variáveis de ambiente no Heroku
- Reiniciar a fila de processamento após o deploy

### 9. Scripts de Monitoramento

Foram adicionados scripts para:

- Reiniciar a fila otimizada (`restart_optimized_queue.py`)
- Verificar o status da fila (`check_queue_status.py`)

## Resultados Esperados

Com estas otimizações, o sistema agora deve:

1. Processar exatamente 11 CNPJs por minuto (o máximo possível com as APIs disponíveis)
2. Distribuir as requisições de forma inteligente entre as APIs
3. Minimizar erros de limite de taxa excedido
4. Fornecer ferramentas para monitoramento e manutenção da fila

## Como Verificar o Funcionamento

Para verificar se as otimizações estão funcionando corretamente:

1. Execute o script de verificação de status:
   ```
   heroku run python check_queue_status.py
   ```

2. Monitore os logs para verificar se as requisições estão sendo distribuídas corretamente:
   ```
   heroku logs --tail
   ```

3. Verifique a taxa de processamento na última hora no relatório de status. Deve estar próxima de 660 CNPJs/hora (11 por minuto × 60 minutos).

## Configuração das Variáveis de Ambiente

Para garantir o funcionamento correto da fila otimizada, as seguintes variáveis de ambiente devem estar configuradas:

```
# Configuração das APIs
RECEITAWS_ENABLED=True
CNPJWS_ENABLED=True
CNPJA_OPEN_ENABLED=True
RECEITAWS_REQUESTS_PER_MINUTE=3
CNPJWS_REQUESTS_PER_MINUTE=3
CNPJA_OPEN_REQUESTS_PER_MINUTE=5
REQUESTS_PER_MINUTE=11  # Deve ser igual à soma das taxas individuais

# Configuração de controle de taxa
MAX_CONCURRENT_PROCESSING=6  # Limita o número de CNPJs em processamento simultâneo
API_COOLDOWN_AFTER_RATE_LIMIT=30  # Tempo de cooldown em segundos após erro 429
API_RATE_LIMIT_SAFETY_FACTOR=0.9  # Fator de segurança para evitar atingir o limite exato
```

## Manutenção

Se for necessário ajustar os limites de requisições por minuto de qualquer API, lembre-se de:

1. Atualizar a variável de ambiente correspondente (ex: `RECEITAWS_REQUESTS_PER_MINUTE`)
2. Atualizar a variável `REQUESTS_PER_MINUTE` para refletir a nova soma total
3. Reiniciar a aplicação para que as alterações tenham efeito
