# Otimização da Fila de Consulta de CNPJs

Este documento descreve as otimizações implementadas no sistema de consulta de CNPJs para garantir o processamento exato de 11 CNPJs por minuto, maximizando o uso das APIs disponíveis.

## Contexto

O sistema utiliza três APIs diferentes para consulta de CNPJs, cada uma com seu próprio limite de requisições por minuto:

- ReceitaWS: 3 requisições/minuto
- CNPJ.ws: 3 requisições/minuto
- CNPJa Open: 5 requisições/minuto

O limite total combinado é de 11 requisições por minuto.

## Otimizações Implementadas

### 1. Controle Preciso de Taxa de Requisições

No arquivo `app/services/queue.py`, implementamos um controle preciso do intervalo entre requisições para garantir exatamente 11 requisições por minuto:

- Substituímos o cálculo do intervalo mínimo entre requisições, removendo o segundo extra de segurança que estava sendo adicionado
- Definimos uma constante `EXACT_INTERVAL_SECONDS` que calcula o intervalo exato para atingir 11 requisições por minuto (60/11 ≈ 5.45 segundos)
- Ajustamos o limite de processamento simultâneo para exatamente `REQUESTS_PER_MINUTE` (11) em vez de `REQUESTS_PER_MINUTE + 2`

```python
# Constante para o intervalo exato entre requisições para atingir 11 por minuto
EXACT_INTERVAL_SECONDS = 60.0 / REQUESTS_PER_MINUTE

# Calcula o intervalo exato entre requisições para atingir exatamente o limite de requisições por minuto
# Não adiciona tempo extra para maximizar o throughput
min_interval_seconds = EXACT_INTERVAL_SECONDS

# Limita o número de CNPJs em processamento simultâneo
# Mantém exatamente REQUESTS_PER_MINUTE CNPJs em processamento
max_processing = REQUESTS_PER_MINUTE
```

### 2. Distribuição Inteligente entre APIs

No arquivo `app/services/api_manager.py`, implementamos uma estratégia de distribuição inteligente para garantir que cada API seja utilizada até seu limite máximo:

- Adicionamos um sistema de rastreamento de uso para cada API, registrando:
  - O limite de requisições por minuto
  - O timestamp da última requisição
  - O contador de uso

- Implementamos o método `_get_apis_by_availability()` que ordena as APIs por disponibilidade atual, priorizando as que têm mais capacidade disponível no momento:
  - Se uma API não foi usada recentemente (últimos 60 segundos), ela recebe prioridade máxima
  - Caso contrário, calculamos a capacidade disponível com base no tempo decorrido desde o último uso

```python
def _get_apis_by_availability(self) -> List[Tuple[Any, str]]:
    """
    Ordena as APIs por disponibilidade atual, priorizando as que têm mais
    capacidade disponível no momento.
    """
    now = time.time()
    apis_with_scores = []
    
    for api, name in zip(self.apis, self.api_names):
        # Calcula quantas requisições foram feitas no último minuto
        usage_info = self.api_usage[name]
        limit = usage_info["limit"]
        last_used = usage_info["last_used"]
        
        # Se a API não foi usada recentemente, ela tem prioridade máxima
        if last_used == 0 or now - last_used > 60:
            score = limit  # Pontuação máxima
        else:
            # Calcula a capacidade disponível com base no tempo desde o último uso
            time_factor = min(1.0, (now - last_used) / 60.0)
            available_capacity = limit * time_factor
            score = available_capacity
        
        apis_with_scores.append((api, name, score))
    
    # Ordena por pontuação (maior primeiro)
    apis_with_scores.sort(key=lambda x: x[2], reverse=True)
    
    # Retorna apenas a API e o nome, sem a pontuação
    return [(api, name) for api, name, _ in apis_with_scores]
```

- Atualizamos o método `query_cnpj()` para usar esta ordenação inteligente em vez da distribuição aleatória anterior
- Adicionamos atualização do rastreamento de uso após cada consulta bem-sucedida

## Configuração

Para garantir que o sistema processe exatamente 11 CNPJs por minuto, certifique-se de que as seguintes configurações estejam definidas no arquivo `.env`:

```
RECEITAWS_ENABLED=True
CNPJWS_ENABLED=True
CNPJA_OPEN_ENABLED=True
RECEITAWS_REQUESTS_PER_MINUTE=3
CNPJWS_REQUESTS_PER_MINUTE=3
CNPJA_OPEN_REQUESTS_PER_MINUTE=5
REQUESTS_PER_MINUTE=11
```

## Benefícios

Estas otimizações garantem que:

1. O sistema processe consistentemente 11 CNPJs por minuto, maximizando o throughput
2. As APIs sejam utilizadas de forma eficiente, priorizando as que têm maior capacidade disponível
3. O sistema respeite os limites individuais de cada API, evitando erros de limite excedido

## Monitoramento

Para verificar se o sistema está processando exatamente 11 CNPJs por minuto, você pode:

1. Verificar os logs do sistema, que mostrarão mensagens detalhadas sobre o processamento
2. Executar o script `check_queue_status.py` para obter estatísticas sobre a fila
3. Monitorar o banco de dados para verificar a taxa de processamento de CNPJs

## Próximos Passos

Possíveis melhorias futuras incluem:

1. Implementar métricas de desempenho para monitorar a taxa exata de processamento
2. Adicionar um dashboard para visualizar o uso de cada API em tempo real
3. Implementar um sistema de balanceamento dinâmico que ajuste os limites com base no desempenho observado
