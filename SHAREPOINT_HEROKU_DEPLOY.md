# Configuração do SharePoint no Heroku

Este documento explica como configurar a integração com o SharePoint no Heroku para o sistema CNPJ Checker.

## Alterações Realizadas

1. **Adicionada dependência do Office 365 no `requirements.txt`**:
   - Adicionado o pacote `Office365-REST-Python-Client` para permitir a integração com o SharePoint.

2. **Atualizado o script `deploy_heroku.sh`**:
   - Adicionadas configurações para solicitar e configurar as variáveis de ambiente do SharePoint durante o deploy.

3. **Melhorado o código em `office365_api/sharepoint_upload.py`**:
   - Adicionada verificação para garantir que o diretório de armazenamento temporário exista antes de tentar salvar arquivos.

## Variáveis de Ambiente Necessárias

Para que a integração com o SharePoint funcione corretamente no Heroku, as seguintes variáveis de ambiente devem ser configuradas:

| Variável | Descrição |
|----------|-----------|
| `USERNAME` | Email/usuário para autenticação no SharePoint |
| `PASSWORD` | Senha para autenticação no SharePoint |
| `sharepoint_url_site` | URL do site SharePoint (ex: https://empresa.sharepoint.com/sites/SiteName) |
| `sharepoint_site_name` | Nome do site SharePoint (ex: SiteName) |
| `sharepoint_doc_library` | Caminho da biblioteca de documentos (ex: Documentos Compartilhados/) |
| `ROOT` | Caminho raiz da aplicação no Heroku (deve ser "/app") |

## Como Fazer o Deploy

### Usando o Script Atualizado

O script `deploy_heroku.sh` foi atualizado para solicitar todas as informações necessárias durante o processo de deploy:

1. Execute o script:
   ```bash
   ./deploy_heroku.sh
   ```

2. Siga as instruções para fornecer:
   - Nome do app no Heroku
   - Configurações gerais da aplicação
   - Credenciais e configurações do SharePoint

### Configuração Manual

Se preferir configurar manualmente, você pode usar os seguintes comandos:

```bash
# Configurações gerais
heroku config:set REQUESTS_PER_MINUTE=3
heroku config:set DEBUG=false
heroku config:set AUTO_RESTART_QUEUE=true
heroku config:set MAX_RETRY_ATTEMPTS=3

# Configurações do SharePoint
heroku config:set USERNAME="seu_email@empresa.com"
heroku config:set PASSWORD="sua_senha"
heroku config:set sharepoint_url_site="https://empresa.sharepoint.com/sites/SiteName"
heroku config:set sharepoint_site_name="SiteName"
heroku config:set sharepoint_doc_library="Documentos Compartilhados/"
heroku config:set ROOT="/app"
```

## Verificação da Configuração

Após o deploy, você pode verificar se as variáveis de ambiente foram configuradas corretamente:

```bash
heroku config --app seu-app-name
```

## Solução de Problemas

Se encontrar problemas com a integração do SharePoint, verifique os logs do Heroku:

```bash
heroku logs --tail --app seu-app-name
```

Problemas comuns:

1. **Erro "No module named 'office365'"**: Verifique se o buildpack Python está configurado corretamente e se o requirements.txt foi atualizado.

2. **Erro de autenticação**: Verifique se as credenciais do SharePoint estão corretas.

3. **Erro ao criar diretório temporário**: O código foi atualizado para criar o diretório se não existir, mas verifique os logs para confirmar.

4. **Erro ao acessar o site ou biblioteca do SharePoint**: Verifique se os nomes do site e da biblioteca estão corretos e se o usuário tem permissões adequadas.
