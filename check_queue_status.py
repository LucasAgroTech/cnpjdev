#!/usr/bin/env python
"""
Script para verificar o status da fila de processamento de CNPJs

Este script exibe informações sobre o status atual da fila de processamento,
incluindo CNPJs pendentes, em processamento, concluídos e com erro.
"""

import asyncio
import logging
import sys
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger("check_queue_status")

# Importa as dependências necessárias
try:
    from app.config import DATABASE_URL
    from app.models.database import CNPJQuery, CNPJData
    from app.config import (
        RECEITAWS_ENABLED, CNPJWS_ENABLED, CNPJA_OPEN_ENABLED,
        RECEITAWS_REQUESTS_PER_MINUTE, CNPJWS_REQUESTS_PER_MINUTE, CNPJA_OPEN_REQUESTS_PER_MINUTE
    )
except ImportError as e:
    logger.error(f"Erro ao importar dependências: {e}")
    sys.exit(1)

def format_time_ago(dt):
    """
    Formata o tempo decorrido desde uma data/hora
    
    Args:
        dt: Data/hora a ser formatada
        
    Returns:
        String formatada com o tempo decorrido
    """
    if not dt:
        return "desconhecido"
        
    now = datetime.utcnow()
    diff = now - dt
    
    if diff.days > 0:
        return f"{diff.days} dias atrás"
    elif diff.seconds >= 3600:
        hours = diff.seconds // 3600
        return f"{hours} horas atrás"
    elif diff.seconds >= 60:
        minutes = diff.seconds // 60
        return f"{minutes} minutos atrás"
    else:
        return f"{diff.seconds} segundos atrás"

async def main():
    """
    Função principal para verificar o status da fila
    """
    print("\n===== STATUS DA FILA DE PROCESSAMENTO DE CNPJs =====\n")
    
    try:
        # Cria uma sessão do banco de dados
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        # Exibe informações sobre as APIs configuradas
        total_rpm = (RECEITAWS_REQUESTS_PER_MINUTE + 
                     CNPJWS_REQUESTS_PER_MINUTE + 
                     CNPJA_OPEN_REQUESTS_PER_MINUTE)
        
        print("Configuração das APIs:")
        print(f"- ReceitaWS: {'habilitada' if RECEITAWS_ENABLED else 'desabilitada'} ({RECEITAWS_REQUESTS_PER_MINUTE} req/min)")
        print(f"- CNPJ.ws: {'habilitada' if CNPJWS_ENABLED else 'desabilitada'} ({CNPJWS_REQUESTS_PER_MINUTE} req/min)")
        print(f"- CNPJa Open: {'habilitada' if CNPJA_OPEN_ENABLED else 'desabilitada'} ({CNPJA_OPEN_REQUESTS_PER_MINUTE} req/min)")
        print(f"Total de requisições por minuto: {total_rpm}")
        
        # Exibe informações sobre as configurações de controle de taxa
        from app.config import (
            MAX_CONCURRENT_PROCESSING, API_COOLDOWN_AFTER_RATE_LIMIT, 
            API_RATE_LIMIT_SAFETY_FACTOR, API_COOLDOWN_MAX,
            API_RATE_LIMIT_SAFETY_FACTOR_LOW, API_RATE_LIMIT_SAFETY_FACTOR_HIGH,
            API_RATE_LIMIT_THRESHOLD
        )
        
        print("\nConfiguração de controle de taxa:")
        print(f"- Máximo de CNPJs em processamento simultâneo: {MAX_CONCURRENT_PROCESSING}")
        print(f"- Tempo de cooldown após erro 429: {API_COOLDOWN_AFTER_RATE_LIMIT}s")
        print(f"- Tempo máximo de cooldown: {API_COOLDOWN_MAX}s")
        print(f"- Fator de segurança para limites de API: {API_RATE_LIMIT_SAFETY_FACTOR}")
        print(f"- Fator de segurança baixo (APIs com limite <= {API_RATE_LIMIT_THRESHOLD}): {API_RATE_LIMIT_SAFETY_FACTOR_LOW}")
        print(f"- Fator de segurança alto (APIs com limite > {API_RATE_LIMIT_THRESHOLD}): {API_RATE_LIMIT_SAFETY_FACTOR_HIGH}")
        
        print("\nStatus da fila:")
        
        # Conta CNPJs por status
        total_queued = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "queued").scalar() or 0
        total_processing = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "processing").scalar() or 0
        total_completed = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "completed").scalar() or 0
        total_error = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "error").scalar() or 0
        total_rate_limited = db.query(func.count(CNPJQuery.id)).filter(CNPJQuery.status == "rate_limited").scalar() or 0
        
        total = total_queued + total_processing + total_completed + total_error + total_rate_limited
        
        print(f"- Na fila: {total_queued}")
        print(f"- Em processamento: {total_processing}")
        print(f"- Concluídos: {total_completed}")
        print(f"- Com erro: {total_error}")
        print(f"- Limite de requisições excedido: {total_rate_limited}")
        print(f"- Total: {total}")
        
        # Verifica CNPJs presos em processamento
        stuck_threshold = datetime.utcnow() - timedelta(minutes=3)
        stuck_count = db.query(func.count(CNPJQuery.id)).filter(
            CNPJQuery.status == "processing",
            CNPJQuery.updated_at < stuck_threshold
        ).scalar() or 0
        
        if stuck_count > 0:
            print(f"\nAtenção: {stuck_count} CNPJs estão presos em processamento há mais de 3 minutos.")
        
        # Exibe os 5 CNPJs mais recentes em processamento
        print("\nCNPJs em processamento (5 mais recentes):")
        processing_queries = db.query(CNPJQuery).filter(
            CNPJQuery.status == "processing"
        ).order_by(CNPJQuery.updated_at.desc()).limit(5).all()
        
        if processing_queries:
            for query in processing_queries:
                time_ago = format_time_ago(query.updated_at)
                print(f"- CNPJ: {query.cnpj}, atualizado {time_ago}")
        else:
            print("- Nenhum CNPJ em processamento no momento.")
        
        # Exibe os 5 CNPJs mais recentes na fila
        print("\nCNPJs na fila (5 mais recentes):")
        queued_queries = db.query(CNPJQuery).filter(
            CNPJQuery.status == "queued"
        ).order_by(CNPJQuery.updated_at.desc()).limit(5).all()
        
        if queued_queries:
            for query in queued_queries:
                time_ago = format_time_ago(query.updated_at)
                print(f"- CNPJ: {query.cnpj}, adicionado {time_ago}")
        else:
            print("- Nenhum CNPJ na fila no momento.")
        
        # Exibe os 5 CNPJs mais recentes com erro
        print("\nCNPJs com erro (5 mais recentes):")
        error_queries = db.query(CNPJQuery).filter(
            CNPJQuery.status == "error"
        ).order_by(CNPJQuery.updated_at.desc()).limit(5).all()
        
        if error_queries:
            for query in error_queries:
                time_ago = format_time_ago(query.updated_at)
                print(f"- CNPJ: {query.cnpj}, erro: {query.error_message}, ocorrido {time_ago}")
        else:
            print("- Nenhum CNPJ com erro no momento.")
        
        # Exibe estatísticas de processamento
        print("\nEstatísticas de processamento:")
        
        # Calcula a taxa de processamento nas últimas 24 horas
        yesterday = datetime.utcnow() - timedelta(days=1)
        completed_last_24h = db.query(func.count(CNPJQuery.id)).filter(
            CNPJQuery.status == "completed",
            CNPJQuery.updated_at >= yesterday
        ).scalar() or 0
        
        # Calcula a taxa de processamento na última hora
        last_hour = datetime.utcnow() - timedelta(hours=1)
        completed_last_hour = db.query(func.count(CNPJQuery.id)).filter(
            CNPJQuery.status == "completed",
            CNPJQuery.updated_at >= last_hour
        ).scalar() or 0
        
        print(f"- CNPJs processados nas últimas 24 horas: {completed_last_24h}")
        print(f"- CNPJs processados na última hora: {completed_last_hour}")
        
        if completed_last_hour > 0:
            print(f"- Taxa de processamento atual: {completed_last_hour} CNPJs/hora")
            
            # Estima o tempo para processar a fila atual
            if total_queued > 0:
                estimated_hours = total_queued / completed_last_hour
                if estimated_hours < 1:
                    estimated_minutes = estimated_hours * 60
                    print(f"- Tempo estimado para processar a fila atual: {estimated_minutes:.1f} minutos")
                else:
                    print(f"- Tempo estimado para processar a fila atual: {estimated_hours:.1f} horas")
        
        # Tenta exibir informações sobre o gerenciador de limites de taxa adaptativo
        try:
            # Importa as classes necessárias
            from app.services.api_manager import APIManager
            from app.services.adaptive_rate_limiter import AdaptiveRateLimiter
            
            # Cria uma instância do gerenciador de APIs para obter o status
            api_manager = APIManager(
                receitaws_enabled=RECEITAWS_ENABLED,
                cnpjws_enabled=CNPJWS_ENABLED,
                cnpja_open_enabled=CNPJA_OPEN_ENABLED,
                receitaws_requests_per_minute=RECEITAWS_REQUESTS_PER_MINUTE,
                cnpjws_requests_per_minute=CNPJWS_REQUESTS_PER_MINUTE,
                cnpja_open_requests_per_minute=CNPJA_OPEN_REQUESTS_PER_MINUTE
            )
            
            # Obtém o status do gerenciador de limites de taxa
            rate_limiter_status = api_manager.get_status()
            
            print("\nStatus do gerenciador de limites de taxa adaptativo:")
            print(f"- APIs habilitadas: {', '.join(rate_limiter_status['apis_enabled'])}")
            
            # Exibe informações sobre cada API
            for api_name, api_status in rate_limiter_status['rate_limiter']['apis'].items():
                print(f"\n  {api_name}:")
                print(f"  - Capacidade: {api_status['capacity']} req/min")
                print(f"  - Capacidade efetiva: {api_status['effective_capacity']:.2f} req/min (fator de segurança: {api_status['safety_factor']:.2f})")
                print(f"  - Tokens disponíveis: {api_status['current_tokens']:.2f}/{api_status['effective_capacity']:.2f} ({api_status['fullness_percentage']:.1f}%)")
                
                # Exibe informações sobre cooldown
                cooldown_remaining = api_status['cooldown_remaining']
                if cooldown_remaining > 0:
                    print(f"  - Em cooldown por mais {cooldown_remaining:.1f}s")
                
                # Exibe estatísticas de uso
                print(f"  - Requisições permitidas: {api_status['stats']['requests_allowed']}")
                print(f"  - Requisições rejeitadas: {api_status['stats']['requests_rejected']}")
                print(f"  - Erros de limite de taxa: {api_status['error_count']}")
        except Exception as e:
            print(f"\nNão foi possível obter informações do gerenciador de limites de taxa: {e}")
        
        print("\n===== FIM DO RELATÓRIO =====\n")
        
    except Exception as e:
        logger.error(f"Erro ao verificar status da fila: {e}")
        sys.exit(1)
    finally:
        # Fecha a sessão do banco de dados
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
