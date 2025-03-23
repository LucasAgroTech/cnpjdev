# Guia de Upload de CNPJs

Este guia explica como fazer upload de planilhas com CNPJs para o sistema após o deploy no Heroku.

## Opções de Upload

Existem duas maneiras principais de enviar CNPJs para processamento:

### 1. Através da Interface Web

1. Acesse a aplicação no navegador: `https://seu-app.herokuapp.com`
2. Na seção "Upload de Arquivo", clique em "Selecionar Arquivo" ou arraste e solte sua planilha
3. Formatos suportados: CSV, XLS, XLSX
4. A planilha deve conter uma coluna com "cnpj" no nome (ou a primeira coluna será usada)
5. Clique em "Enviar Arquivo"
6. Acompanhe o status do processamento na tabela à direita

### 2. Através da API REST

Se preferir automatizar o processo, você pode usar a API diretamente:

#### Upload de arquivo:
```bash
curl -X POST https://seu-app.herokuapp.com/api/upload-file/ \
  -F "file=@caminho/para/sua/planilha.xlsx"
```

#### Envio direto de lista de CNPJs:
```bash
curl -X POST https://seu-app.herokuapp.com/api/upload-cnpjs/ \
  -H "Content-Type: application/json" \
  -d '{"cnpjs": ["00.000.000/0000-00", "11.111.111/1111-11"]}'
```

#### Verificar status:
```bash
curl https://seu-app.herokuapp.com/api/status/
```

## Formato da Planilha

Para melhor compatibilidade, recomendamos:

1. **CSV**: Use ponto-e-vírgula (;) como separador e UTF-8 como codificação
2. **Excel (XLS/XLSX)**: Mantenha a planilha simples, sem fórmulas complexas

A planilha deve ter uma coluna contendo os CNPJs. Idealmente, esta coluna deve ter "cnpj" no nome (ex: "cnpj", "CNPJ", "numero_cnpj"). Se nenhuma coluna tiver "cnpj" no nome, o sistema usará a primeira coluna.

Exemplo de planilha:

| CNPJ               | Nome Empresa      | Observações |
|--------------------|-------------------|-------------|
| 00.000.000/0000-00 | Empresa Exemplo 1 | Teste 1     |
| 11.111.111/1111-11 | Empresa Exemplo 2 | Teste 2     |

## Processamento e Limites

- O processamento é feito de forma assíncrona
- O sistema respeita o limite de requisições da API ReceitaWS (padrão: 3 por minuto)
- Para lotes grandes, o processamento pode levar tempo
- Use a interface de status para acompanhar o progresso

## Visualização dos Resultados

Após o processamento, você pode visualizar os resultados:

1. Na interface web, clique no botão "Ver" ao lado de um CNPJ com status "Concluído"
2. Ou acesse diretamente via API:
   ```bash
   curl https://seu-app.herokuapp.com/api/cnpj/00000000000000
   ```

## Solução de Problemas

Se encontrar problemas ao fazer upload:

1. **Formato de arquivo não suportado**: Certifique-se de usar CSV, XLS ou XLSX
2. **Nenhum CNPJ válido encontrado**: Verifique se os CNPJs na planilha têm 14 dígitos
3. **Erro na API**: Verifique se a API da ReceitaWS está disponível
4. **Limite de requisições**: O sistema pode estar aguardando para respeitar o limite da API

Para verificar os logs e identificar problemas:
```bash
heroku logs --tail --app seu-app
```
