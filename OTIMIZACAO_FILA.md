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

### 1. Sistema de Token Bucket Adaptativo

Foi implementado um sistema de Token Bucket adaptativo para cada API, garantindo um controle de taxa preciso e eficiente:

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

Este sistema oferece várias vantagens:

- **Garantia matemática** de não exceder os limites de cada API
- **Distribuição suave** das requisições ao longo do tempo
- **Adaptação dinâmica** às condições de cada API
- **Monitoramento detalhado** do uso de cada API

### 2. Escalonador Central Adaptativo

Um escalonador central gerencia todas as APIs e seleciona a melhor para cada requisição:

```python
def get_best_api(self) -> Optional[str]:
    """
    Seleciona a melhor API para usar no momento, com base na disponibilidade
    e no histórico de uso.
    """
```

O escalonador considera múltiplos fatores para selecionar a API:

- Número de tokens disponíveis
- Tempo desde o último uso
- Histórico de erros
- Fator aleatório para evitar concentração

### 3. Fatores de Segurança Dinâmicos

Os fatores de segurança são ajustados dinamicamente com base no desempenho de cada API:

```python
# Determina o fator de segurança inicial
if initial_safety_factor is None:
    # Se a API tem um limite baixo, usa um fator de segurança mais conservador
    if requests_per_minute <= API_RATE_LIMIT_THRESHOLD:
        safety_factor = API_RATE_LIMIT_SAFETY_FACTOR_LOW
    else:
        safety_factor = API_RATE_LIMIT_SAFETY_FACTOR_HIGH
```

Além disso, o sistema ajusta automaticamente os fatores de segurança:

- **Redução após erros**: Quando uma API retorna erro de limite excedido, seu fator de segurança é reduzido
- **Aumento gradual após sucesso**: Após várias requisições bem-sucedidas, o fator é aumentado gradualmente

### 4. Sistema de Backoff Exponencial para Cooldown

Quando uma API atinge seu limite, é implementado um sistema de backoff exponencial:

```python
# Calcula o tempo de cooldown com base no número de erros
# Usa backoff exponencial com limite máximo
error_count = self.api_info[api_name]["error_count"]
cooldown_time = min(API_COOLDOWN_AFTER_RATE_LIMIT * (2 ** (error_count - 1)), API_COOLDOWN_MAX)
```

Isso significa que:
- Primeiro erro: cooldown de 60 segundos
- Segundo erro: cooldown de 120 segundos
- Terceiro erro: cooldown de 240 segundos
- E assim por diante, até o limite máximo configurado

### 5. Espera Inteligente por API Disponível

O sistema calcula precisamente quanto tempo esperar até que uma API esteja disponível:

```python
async def wait_for_api_availability(self, timeout: float = 30.0) -> Optional[str]:
    """
    Aguarda até que uma API esteja disponível para uso, com timeout.
    """
```

Isso permite:
- Minimizar o tempo de espera
- Evitar verificações desnecessárias
- Garantir que a próxima requisição seja feita exatamente quando uma API estiver disponível

### 6. Monitoramento Detalhado

O sistema mantém estatísticas detalhadas sobre o uso de cada API:

```python
# Estatísticas
self.stats = {
    "requests_allowed": 0,
    "requests_rejected": 0,
    "total_tokens_consumed": 0,
    "last_allowed": 0,
    "last_rejected": 0,
    "error_count": 0
}
```

Estas estatísticas são usadas para:
- Ajustar os fatores de segurança
- Identificar problemas com APIs específicas
- Otimizar a distribuição de requisições

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
MAX_CONCURRENT_PROCESSING=4  # Limita o número de CNPJs em processamento simultâneo
API_COOLDOWN_AFTER_RATE_LIMIT=60  # Tempo base de cooldown em segundos após erro 429
API_COOLDOWN_MAX=300  # Tempo máximo de cooldown em segundos
API_RATE_LIMIT_SAFETY_FACTOR=0.9  # Fator de segurança padrão (mantido para compatibilidade)
API_RATE_LIMIT_SAFETY_FACTOR_LOW=0.7  # Fator de segurança para APIs com limite baixo
API_RATE_LIMIT_SAFETY_FACTOR_HIGH=0.8  # Fator de segurança para APIs com limite alto
API_RATE_LIMIT_THRESHOLD=3  # Limite que define o que é uma API com limite "baixo"
```

## Manutenção

Se for necessário ajustar os limites de requisições por minuto de qualquer API, lembre-se de:

1. Atualizar a variável de ambiente correspondente (ex: `RECEITAWS_REQUESTS_PER_MINUTE`)
2. Atualizar a variável `REQUESTS_PER_MINUTE` para refletir a nova soma total
3. Reiniciar a aplicação para que as alterações tenham efeito
