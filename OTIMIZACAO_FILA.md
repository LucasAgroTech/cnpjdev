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

### 3. Controle Preciso do Número de CNPJs em Processamento

O sistema agora limita o número de CNPJs em processamento simultâneo para exatamente o número total de requisições por minuto que as APIs suportam:

```python
# Limita o número de CNPJs em processamento simultâneo
# Mantém exatamente o número total de requisições por minuto em processamento
# para garantir que estamos processando na taxa máxima permitida
max_processing = TOTAL_REQUESTS_PER_MINUTE
```

### 4. Limpeza de Variáveis de Ambiente

Foram removidas variáveis de ambiente não relacionadas à aplicação que poderiam estar causando confusão.

### 5. Script de Deploy Aprimorado

O script de deploy foi atualizado para:

- Calcular automaticamente a soma das taxas individuais das APIs
- Verificar e configurar corretamente as variáveis de ambiente no Heroku
- Reiniciar a fila de processamento após o deploy

### 6. Scripts de Monitoramento

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
RECEITAWS_ENABLED=True
CNPJWS_ENABLED=True
CNPJA_OPEN_ENABLED=True
RECEITAWS_REQUESTS_PER_MINUTE=3
CNPJWS_REQUESTS_PER_MINUTE=3
CNPJA_OPEN_REQUESTS_PER_MINUTE=5
REQUESTS_PER_MINUTE=11  # Deve ser igual à soma das taxas individuais
```

## Manutenção

Se for necessário ajustar os limites de requisições por minuto de qualquer API, lembre-se de:

1. Atualizar a variável de ambiente correspondente (ex: `RECEITAWS_REQUESTS_PER_MINUTE`)
2. Atualizar a variável `REQUESTS_PER_MINUTE` para refletir a nova soma total
3. Reiniciar a aplicação para que as alterações tenham efeito
