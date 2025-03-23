# Checklist para Deploy no Heroku

Use esta checklist para garantir que tudo está pronto para o deploy da aplicação CNPJ Consulta no Heroku.

## Pré-requisitos

- [ ] Heroku CLI instalado (`brew install heroku/brew/heroku` no macOS)
- [ ] Conta no Heroku criada (https://signup.heroku.com/)
- [ ] Git instalado e configurado

## Arquivos de Configuração

- [x] Procfile configurado corretamente
- [x] runtime.txt com a versão do Python especificada
- [x] requirements.txt com todas as dependências
- [x] .env.example documentando as variáveis de ambiente necessárias

## Preparação para Deploy

- [ ] Todas as alterações foram commitadas no Git
- [ ] Testou a aplicação localmente usando `./run_local.sh`
- [ ] Verificou se a conexão com o banco de dados está funcionando
- [ ] Verificou se a API da CNPJA está respondendo corretamente

## Deploy no Heroku

Para fazer o deploy, você pode usar o script automatizado:

```bash
./deploy_heroku.sh
```

Ou seguir os passos manualmente:

1. [ ] Login no Heroku: `heroku login`
2. [ ] Criar app no Heroku: `heroku create nome-do-app`
3. [ ] Adicionar PostgreSQL: `heroku addons:create heroku-postgresql:mini`
4. [ ] Configurar variáveis de ambiente:
   ```bash
   heroku config:set REQUESTS_PER_MINUTE=3
   heroku config:set DEBUG=False
   ```
5. [ ] Fazer o deploy: `git push heroku main`
6. [ ] Verificar logs: `heroku logs --tail`
7. [ ] Abrir a aplicação: `heroku open`

## Pós-Deploy

- [ ] Verificou se a aplicação está acessível
- [ ] Testou o upload de um arquivo de exemplo (exemplo_cnpjs.csv ou exemplo_cnpjs.xlsx)
- [ ] Verificou se as consultas estão sendo processadas corretamente
- [ ] Verificou se os resultados estão sendo armazenados no banco de dados

## Solução de Problemas

Se encontrar problemas durante o deploy:

1. Verifique os logs: `heroku logs --tail`
2. Verifique as variáveis de ambiente: `heroku config`
3. Verifique o status do banco de dados: `heroku pg:info`
4. Tente reiniciar a aplicação: `heroku restart`

## Recursos Adicionais

- [Documentação do Heroku](https://devcenter.heroku.com/)
- [Guia de Upload de CNPJs](./GUIA_UPLOAD_CNPJ.md)
- [Documentação da API ReceitaWS](https://receitaws.com.br/api)
