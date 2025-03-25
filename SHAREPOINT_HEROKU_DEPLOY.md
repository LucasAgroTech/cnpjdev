# Configuração do SharePoint no Heroku

Este documento explica como configurar a integração com o SharePoint no Heroku para o sistema CNPJ Checker.

## Alterações Realizadas

1. **Adicionada dependência do Office 365 no `requirements.txt`**:
   - Adicionado o pacote `Office365-REST-Python-Client` para permitir a integração com o SharePoint.

2. **Atualizado o script `deploy_heroku.sh`**:
   - Adicionadas configurações para solicitar e configurar as variáveis de ambiente do SharePoint durante o deploy.

3. **Melhorado o código em `office365_api/sharepoint_upload.py`**:
   - Adicionada verificação para garantir que o diretório de armazenamento temporário exista antes de tentar salvar arquivos.
   - Adicionados logs detalhados para diagnóstico de problemas.
   - Corrigido problema com barras duplas no caminho da pasta.

4. **Corrigido o método `upload_file` em `office365_api/office365_api.py`**:
   - Adicionada lógica para evitar barras duplas no caminho da pasta quando `folder_name` é vazio.
   - Adicionado log para mostrar o URL da pasta de destino.

## Variáveis de Ambiente Necessárias

Para que a integração com o SharePoint funcione corretamente no Heroku, as seguintes variáveis de ambiente devem ser configuradas:

| Variável | Descrição |
|----------|-----------|
| `USERNAME` | Email/usuário para autenticação no SharePoint |
| `PASSWORD` | Senha para autenticação no SharePoint |
| `sharepoint_url_site` | URL do site SharePoint (ex: https://empresa.sharepoint.com/sites/SiteName) |
| `sharepoint_site_name` | Nome do site SharePoint (ex: SiteName) |
| `sharepoint_doc_library` | Caminho da biblioteca de documentos (ex: Documentos Compartilhados) - **Importante: Não inclua a barra final** |
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
heroku config:set sharepoint_doc_library="Documentos Compartilhados"
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

1. **Erro "No module named 'office365'"**: 
   - Verifique se o buildpack Python está configurado corretamente.
   - Certifique-se de que o requirements.txt foi atualizado com `Office365-REST-Python-Client`.
   - Execute `heroku buildpacks:add heroku/python --app seu-app-name` se necessário.

2. **Erro de autenticação**: 
   - Verifique se as credenciais do SharePoint estão corretas.
   - Confirme se o usuário tem permissões para acessar e modificar a biblioteca de documentos.

3. **Erro "404 Client Error: Not Found"**:
   - Verifique se o caminho da biblioteca de documentos está correto.
   - **Importante**: Não inclua a barra final (/) no valor de `sharepoint_doc_library`.
   - Confirme se a biblioteca de documentos realmente existe no SharePoint.
   - Verifique os logs para ver o URL completo que está sendo usado.

4. **Erro ao criar diretório temporário**: 
   - O código foi atualizado para criar o diretório se não existir.
   - Verifique se o app tem permissões para criar diretórios temporários.

5. **Erro "System.IO.DirectoryNotFoundException"**:
   - Este erro geralmente ocorre quando o caminho da pasta no SharePoint está incorreto.
   - Verifique se `sharepoint_site_name` e `sharepoint_doc_library` estão corretos.
   - Remova qualquer barra final (/) do valor de `sharepoint_doc_library`.
