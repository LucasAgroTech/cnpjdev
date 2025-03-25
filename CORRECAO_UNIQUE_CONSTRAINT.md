# Correção para Violação de Restrição Única (Unique Constraint)

## Problema

O sistema estava enfrentando um problema ao processar CNPJs que já existiam no banco de dados. Quando um CNPJ já existia, o sistema tentava inseri-lo novamente, o que causava um erro de violação de restrição única (`unique constraint violation`). Em vez de reconhecer que o CNPJ já existia e pular para o próximo, o sistema fazia várias tentativas adicionais (até 3 no total, conforme definido em `MAX_RETRY_ATTEMPTS`), resultando em erros repetidos e processamento desnecessário.

Exemplo de erro nos logs:

```
2025-03-25T13:52:24.846493+00:00 app[web.1]: 2025-03-25 13:52:24,846 - app.services.queue - WARNING - Erro ao processar CNPJ 57369027000173 (tentativa 2/3): This Session's transaction has been rolled back due to a previous exception during flush. To begin a new transaction with this Session, first issue Session.rollback(). Original exception was: (psycopg2.errors.UniqueViolation) duplicate key value violates unique constraint "ix_cnpj_data_cnpj"
2025-03-25T13:52:24.846494+00:00 app[web.1]: DETAIL:  Key (cnpj)=(57369027000173) already exists.
```

## Solução

A solução implementada modifica o tratamento de exceções no método `_process_single_cnpj` da classe `CNPJQueue` para detectar especificamente erros de violação de restrição única e tratá-los de forma diferente de outros erros:

1. Quando ocorre um erro, o sistema agora verifica se é uma violação de restrição única (procurando por "duplicate key value violates unique constraint" na mensagem de erro)
2. Se for uma violação de restrição única, o sistema marca o CNPJ como "completed" (já que ele já existe no banco) e pula para o próximo CNPJ sem fazer novas tentativas
3. Para outros tipos de erro, o sistema mantém a lógica de retry existente

## Arquivos Modificados

- `app/services/queue.py`: Modificado o método `_process_single_cnpj` para detectar e tratar erros de violação de restrição única

## Como Implantar

Para implantar esta correção, execute o script `deploy_fix_unique_constraint.sh`:

```bash
./deploy_fix_unique_constraint.sh
```

Este script fará o commit das alterações e as enviará para o Heroku.

## Benefícios

- Redução de erros nos logs
- Processamento mais eficiente de CNPJs
- Menor carga no banco de dados
- Menor tempo de processamento para a fila de CNPJs
