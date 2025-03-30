# Implantação da Correção no Endpoint de Status

Este documento descreve as alterações feitas no endpoint de status para garantir que a aplicação mostre corretamente os valores na tela index, considerando todos os CNPJs no banco de dados, sem a limitação de 24 horas.

## Problema Identificado

A aplicação não estava mostrando corretamente os valores de CNPJs concluídos na interface principal. Isso ocorria porque:

1. O endpoint `/api/status/` estava consultando apenas os CNPJs das últimas 24 horas
2. A função `get_batch_status()` não estava otimizada para grandes volumes de dados
3. Não havia consistência entre os dados mostrados e o estado real do banco de dados

## Alterações Realizadas

### 1. Modificação no Endpoint `/api/status/`

Removemos a limitação de 24 horas no endpoint `/api/status/` para que ele retorne todos os CNPJs do banco de dados. Agora, o endpoint usa consultas SQL otimizadas para contar registros por status, garantindo que as contagens reflitam o estado real do banco de dados.

```python
@router.get("/status/", response_model=schemas.CNPJBatchStatus)
def get_status(
    cnpjs: List[str] = Query(None),
    db: Session = Depends(get_db)
):
    """
    Obtém o status do processamento de CNPJs
    """
    if cnpjs:
        logger.info(f"Consultando status de {len(cnpjs)} CNPJs específicos")
        # Limpa CNPJs
        clean_cnpjs = [''.join(filter(str.isdigit, cnpj)) for cnpj in cnpjs]
        return get_batch_status(db, clean_cnpjs)
    else:
        # Obtém TODOS os CNPJs sem limitação de tempo
        logger.info("Consultando status de todos os CNPJs no banco de dados")
        
        # Usar consultas SQL otimizadas para contagem
        total_count = db.query(func.count(CNPJQuery.id)).scalar()
        completed_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "completed").scalar()
        processing_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "processing").scalar()
        error_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "error").scalar()
        queued_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "queued").scalar()
        rate_limited_count = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "rate_limited").scalar()
        
        # Obter apenas os CNPJs mais recentes para exibição na tabela (limitado a 100 para performance)
        recent_queries = db.query(CNPJQuery).order_by(CNPJQuery.updated_at.desc()).limit(100).all()
        cnpjs = [query.cnpj for query in recent_queries]
        
        # Criar o objeto de resposta com contagens precisas
        statuses = []
        for cnpj in cnpjs:
            query = db.query(CNPJQuery).filter(CNPJQuery.cnpj == cnpj).order_by(CNPJQuery.created_at.desc()).first()
            
            if query:
                statuses.append(schemas.CNPJStatus(
                    cnpj=cnpj,
                    status=query.status,
                    error_message=query.error_message
                ))
        
        return schemas.CNPJBatchStatus(
            total=total_count,
            completed=completed_count,
            processing=processing_count,
            error=error_count,
            queued=queued_count,
            rate_limited=rate_limited_count,
            results=statuses
        )
```

### 2. Otimização da Função `get_batch_status()`

Otimizamos a função `get_batch_status()` para usar consultas SQL mais eficientes, evitando processamento individual de cada CNPJ quando possível:

```python
def get_batch_status(db: Session, cnpjs: List[str]) -> schemas.CNPJBatchStatus:
    """
    Obtém status de lote para uma lista de CNPJs
    Versão otimizada para consultas mais eficientes
    """
    if not cnpjs:
        return schemas.CNPJBatchStatus(
            total=0,
            completed=0,
            processing=0,
            error=0,
            queued=0,
            rate_limited=0,
            results=[]
        )
    
    # Consulta otimizada para obter todos os CNPJs de uma vez
    # Usamos a subconsulta para pegar apenas o registro mais recente de cada CNPJ
    subquery = db.query(
        CNPJQuery.cnpj,
        CNPJQuery.status,
        CNPJQuery.error_message,
        func.row_number().over(
            partition_by=CNPJQuery.cnpj,
            order_by=CNPJQuery.created_at.desc()
        ).label('rn')
    ).filter(CNPJQuery.cnpj.in_(cnpjs)).subquery()
    
    # Seleciona apenas as linhas com row_number = 1 (mais recentes)
    query_results = db.query(subquery).filter(subquery.c.rn == 1).all()
    
    # Mapeia os resultados para um dicionário para acesso rápido
    cnpj_status_map = {result.cnpj: (result.status, result.error_message) for result in query_results}
    
    # Inicializa contadores
    completed = 0
    processing = 0
    error = 0
    queued = 0
    rate_limited = 0
    
    # Prepara a lista de status
    statuses = []
    for cnpj in cnpjs:
        if cnpj in cnpj_status_map:
            status, error_message = cnpj_status_map[cnpj]
            
            if status == "completed":
                completed += 1
            elif status == "processing":
                processing += 1
            elif status == "error":
                error += 1
            elif status == "queued":
                queued += 1
            elif status == "rate_limited":
                rate_limited += 1
        else:
            status = "unknown"
            error_message = None
        
        statuses.append(schemas.CNPJStatus(
            cnpj=cnpj,
            status=status,
            error_message=error_message
        ))
    
    return schemas.CNPJBatchStatus(
        total=len(cnpjs),
        completed=completed,
        processing=processing,
        error=error,
        queued=queued,
        rate_limited=rate_limited,
        results=statuses
    )
```

## Benefícios das Alterações

1. **Precisão dos dados**: Os contadores agora mostram o número exato de CNPJs em cada status
2. **Visibilidade completa**: Todos os CNPJs processados são considerados, não apenas os das últimas 24 horas
3. **Performance**: As consultas otimizadas garantem que a aplicação continue funcionando bem mesmo com um grande volume de dados
4. **Consistência**: Os dados mostrados na interface refletem o estado real do banco de dados

## Como Implantar

Para implantar essas alterações em produção, execute o script `deploy_status_fix.sh`:

```bash
./deploy_status_fix.sh
```

Este script irá:

1. Adicionar as alterações ao git
2. Realizar commit das alterações
3. Implantar as alterações no Heroku
4. Reiniciar a aplicação

## Verificação

Após a implantação, verifique se a aplicação está mostrando corretamente os valores na tela index:

1. Acesse a aplicação no navegador
2. Verifique se os contadores de CNPJs estão mostrando valores corretos
3. Verifique se a tabela de CNPJs está mostrando os registros mais recentes

## Monitoramento

Para monitorar a aplicação após a implantação, execute:

```bash
heroku logs --tail
```

Isso permitirá que você veja os logs em tempo real e verifique se há algum erro ou problema.

## Rollback

Se for necessário reverter as alterações, você pode usar o comando:

```bash
git revert HEAD
git push heroku main:master
heroku restart
```

Isso irá reverter o último commit e implantar a versão anterior da aplicação.
