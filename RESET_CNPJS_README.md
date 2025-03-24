# Reset CNPJs com Erro - Script Direto

Este script foi criado para resolver problemas de `PendingRollbackError` e outros erros relacionados ao processamento de CNPJs no banco de dados PostgreSQL do Heroku.

## O que o script faz

1. **Corrige sessões pendentes**: Altera CNPJs com status 'processing' para 'queued', resolvendo problemas de `PendingRollbackError`
2. **Reseta CNPJs com erro**: Altera CNPJs com status 'error' para 'queued', colocando-os de volta na fila
3. **Verifica CNPJs duplicados** (opcional): Identifica e permite remover registros duplicados na tabela `cnpj_data`

## Pré-requisitos

Antes de executar o script, você precisa instalar as dependências:

```bash
pip install psycopg2-binary python-dotenv
```

## Como usar

### 1. Configuração da URL do banco de dados

Você pode fornecer a URL do banco de dados de duas maneiras:

- **Opção 1**: Adicione a URL no arquivo `.env`:
  ```
  DATABASE_URL=postgresql://username:password@hostname:5432/database_name
  ```

- **Opção 2**: Passe a URL diretamente como argumento:
  ```
  python reset_error_cnpjs_direct.py --db-url "postgresql://username:password@hostname:5432/database_name"
  ```

#### Formato da URL de conexão do Heroku

A URL de conexão do banco de dados PostgreSQL do Heroku geralmente segue este formato:
```
postgresql://username:password@hostname:5432/database_name
```

Onde:
- `username`: Nome de usuário para acessar o banco de dados
- `password`: Senha para acessar o banco de dados
- `hostname`: Nome do host ou endereço IP do servidor PostgreSQL
- `5432`: Porta padrão do PostgreSQL (geralmente 5432)
- `database_name`: Nome do banco de dados

**Nota**: O Heroku pode fornecer URLs que começam com `postgres://` em vez de `postgresql://`. O script automaticamente converte o formato para compatibilidade com psycopg2.

Para obter a URL de conexão do seu banco de dados no Heroku:
1. Acesse o dashboard do Heroku
2. Selecione seu aplicativo
3. Vá para a aba "Resources" e clique no seu banco de dados PostgreSQL
4. Na página de detalhes do banco de dados, clique na aba "Settings"
5. Clique no botão "View Credentials" para ver as credenciais de conexão

### 2. Executando o script

Para executar o script com todas as opções padrão:

```bash
python reset_error_cnpjs_direct.py
```

### Opções adicionais

- `--verbose` ou `-v`: Mostra informações detalhadas sobre os CNPJs com erro
- `--check-duplicates`: Verifica e permite corrigir CNPJs duplicados na tabela `cnpj_data`
- `--fix-sessions`: Corrige sessões pendentes (ativado por padrão)

Exemplo com todas as opções:

```bash
python reset_error_cnpjs_direct.py --verbose --check-duplicates
```

## Após executar o script

Depois de executar o script com sucesso, você pode reiniciar a fila de processamento usando o comando:

```bash
python restart_queue.py [URL_BASE]
```

Onde `[URL_BASE]` é a URL base da sua aplicação (ex: https://seu-app.herokuapp.com).

## Solução de problemas

Se você encontrar erros ao executar o script:

1. Verifique se a URL do banco de dados está correta
   - Certifique-se de que a porta é um número (geralmente 5432) e não a palavra "porta"
   - Verifique se não há placeholders como "usuario", "senha", "host" na URL
   - Confirme que todas as credenciais estão corretas
2. Certifique-se de que as dependências estão instaladas
3. Verifique se você tem permissão para acessar o banco de dados do Heroku
4. Se receber o erro "invalid integer value", verifique se você substituiu todos os placeholders na URL de conexão

### Erros comuns

- **invalid integer value "porta" for connection option "port"**: Este erro ocorre quando você usa o exemplo de URL sem substituir o placeholder "porta" por um número real de porta (geralmente 5432).
- **Connection refused**: Verifique se o hostname está correto e se você tem acesso ao servidor de banco de dados.
- **Authentication failed**: Verifique se o nome de usuário e senha estão corretos.
