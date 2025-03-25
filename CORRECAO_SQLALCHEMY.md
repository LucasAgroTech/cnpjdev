# Correção do Problema de SQLAlchemy e Transações no Banco de Dados

## Problemas Identificados

O sistema está enfrentando três problemas principais:

1. **Erro de SQLAlchemy**: O método `get_table_names()` está sendo chamado sem o parâmetro `schema`, o que causa o erro:
   ```
   TypeError: get_table_names() missing 1 required positional argument: 'self'
   ```

2. **Erro de SQL Literal**: Expressões SQL literais não estão sendo declaradas corretamente:
   ```
   Erro ao limpar CNPJs presos: Textual SQL expression 'SELECT 1' should be explicitly declared as text('SELECT 1')
   ```

3. **Conflito de Transações**: Há um conflito de transações no banco de dados que impede a atualização do contador de CNPJs concluídos:
   ```
   Erro na transação ao limpar CNPJs presos: A transaction is already begun on this Session.
   ```

4. **Problema com URL no script de reinício da fila**: O script `restart_queue.py` está usando a URL do banco de dados em vez da URL da API:
   ```
   Erro ao fazer requisição: No connection adapters were found for 'postgresql://...'
   ```

## Soluções Implementadas

Para resolver esses problemas, implementamos as seguintes alterações:

1. **Correção do método `get_table_names()`**:
   - Modificamos os scripts `fix_incomplete_status.py` e `check_db_status.py` para usar uma consulta SQL direta em vez do método `get_table_names()`:
   ```python
   from sqlalchemy import text
   tables = [t[0] for t in engine.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()]
   ```

2. **Correção de expressões SQL literais**:
   - Modificamos o método `cleanup_stuck_processing()` em `app/services/queue.py` para usar `text()` para expressões SQL literais:
   ```python
   from sqlalchemy import text
   self.db.execute(text("SELECT 1"))
   ```

3. **Correção do conflito de transações**:
   - Adicionamos verificação para determinar se já existe uma transação em andamento
   - Adicionamos tratamento de erro e rollback explícito para lidar com transações pendentes
   - Melhoramos o tratamento de CNPJs duplicados

4. **Correção do script de reinício da fila**:
   - Modificamos o script `restart_queue.py` para detectar automaticamente a URL correta da API quando executado no Heroku
   - Adicionamos uma URL padrão como fallback

## Como Aplicar a Correção

### Passo 1: Implantar as Alterações de Código

1. Execute o script `deploy_fix_sqlalchemy.sh` para implantar as alterações no Heroku:
   ```bash
   ./deploy_fix_sqlalchemy.sh
   ```

2. O script irá:
   - Fazer commit das alterações
   - Fazer push para o Heroku
   - Executar o diagnóstico inicial
   - Executar a correção de status incompletos
   - Reiniciar o processamento da fila
   - Executar o diagnóstico final

### Passo 2: Monitorar os Logs

Após aplicar a correção, monitore os logs para verificar se o problema foi resolvido:

```bash
heroku logs --tail --app seu-app-heroku
```

Procure por mensagens como:
- `CNPJ X processado com sucesso`
- `Status atualizado de 'Y' para 'completed'`
- `Commit realizado com sucesso. Z CNPJs atualizados.`

### Passo 3: Verificar a Interface

Acesse a interface do sistema e verifique se os CNPJs estão sendo marcados como "concluído" corretamente.

## Prevenção de Problemas Futuros

Para evitar problemas semelhantes no futuro, recomendamos:

1. **Verificação de Transações**: Sempre verifique se já existe uma transação em andamento antes de iniciar uma nova.
2. **Compatibilidade de SQLAlchemy**: Ao usar métodos do SQLAlchemy, verifique a documentação para garantir que está usando a API corretamente, especialmente ao fazer deploy para ambientes diferentes.
3. **Uso de `text()` para SQL Literal**: Sempre use `text()` para expressões SQL literais.
4. **Tratamento de Erros Robusto**: Adicione tratamento de erros e rollback explícito para lidar com transações pendentes.
5. **Monitoramento Regular**: Execute o script `check_db_status.py` regularmente para identificar inconsistências.
6. **Testes em Ambiente de Produção**: Teste as alterações em um ambiente semelhante ao de produção antes de fazer o deploy final.

## Contato

Se você encontrar algum problema ao aplicar a correção ou tiver dúvidas, entre em contato com a equipe de desenvolvimento.
