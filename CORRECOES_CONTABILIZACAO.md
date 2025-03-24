# Correções na Contabilização de CNPJs

Este documento descreve as correções implementadas para resolver problemas de contabilização de CNPJs e remoção de duplicados na base de dados.

## Problemas Resolvidos

1. **Gargalos na Contabilização**: Corrigidos problemas que afetavam a contagem correta de CNPJs processados, em processamento e em fila.
2. **Duplicação de CNPJs**: Implementada solução para identificar e remover CNPJs duplicados na base de dados.
3. **CNPJs Presos em Processamento**: Melhorado o mecanismo de detecção e recuperação de CNPJs presos em estado "processing".
4. **Configuração Incompleta**: Atualizado o arquivo .env com todas as configurações necessárias.

## Soluções Implementadas

### 1. Prevenção de Duplicados na Fila

O método `add_to_queue` foi modificado para verificar se um CNPJ já existe na fila ou já foi processado recentemente antes de adicioná-lo. Isso evita a criação de registros duplicados e melhora a contabilização.

### 2. Melhoria no Mecanismo de Limpeza de CNPJs Presos

O método `cleanup_stuck_processing` foi aprimorado com as seguintes melhorias:
- Redução do tempo para considerar um CNPJ como "preso" de 5 para 3 minutos
- Implementação de transações para garantir atomicidade nas operações
- Uso de bloqueio de linhas (FOR UPDATE) para evitar condições de corrida

### 3. Script para Limpeza de Duplicados

Foi criado o script `clean_duplicates.py` que identifica e remove CNPJs duplicados nas tabelas:
- `CNPJQuery`: Mantém apenas o registro mais recente de cada CNPJ
- `CNPJData`: Mantém apenas os dados mais recentes de cada CNPJ

### 4. Novo Endpoint Administrativo

Foi adicionado um novo endpoint administrativo `/api/admin/cleanup/duplicates` que permite limpar CNPJs duplicados sob demanda através da API.

### 5. Configuração Completa

O arquivo `.env` foi atualizado com todas as configurações necessárias, incluindo:
- Configurações para cada API (ReceitaWS, CNPJ.ws, CNPJa Open)
- Limites de requisições por minuto para cada API
- Configurações de persistência e retry

## Como Usar as Novas Funcionalidades

### Limpeza de Duplicados via Script

Para limpar CNPJs duplicados usando o script:

```bash
# Executar o script diretamente
python clean_duplicates.py

# Ou usando o script executável
./clean_duplicates.py
```

### Limpeza de Duplicados via API

Para limpar CNPJs duplicados usando a API:

```bash
# Substitua URL_BASE pela URL da sua aplicação
curl -X POST "https://URL_BASE/api/admin/cleanup/duplicates"
```

Ou usando o navegador, acesse:
```
https://URL_BASE/api/admin/cleanup/duplicates
```

## Recomendações para Manutenção

1. **Monitoramento Regular**: Use o script `check_queue_status.py` para monitorar o status da fila regularmente.

2. **Limpeza Periódica de Duplicados**: Execute o script `clean_duplicates.py` periodicamente para manter a base de dados limpa.

3. **Reinicialização da Fila**: Se notar problemas na contabilização, use o script `restart_queue.py` para reiniciar o processamento da fila.

4. **Verificação de Configurações**: Certifique-se de que o arquivo `.env` contém todas as configurações necessárias conforme o `.env.example`.

## Próximos Passos Recomendados

1. **Implementar Job Periódico**: Configurar um job periódico (por exemplo, usando o Heroku Scheduler) para executar a limpeza de duplicados automaticamente.

2. **Melhorar Monitoramento**: Implementar um dashboard para visualizar o status da fila e a contabilização de CNPJs em tempo real.

3. **Otimizar Consultas ao Banco de Dados**: Adicionar índices adicionais para melhorar o desempenho das consultas, especialmente para CNPJs com muitos registros.
