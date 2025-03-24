#!/usr/bin/env python3
import os
import sys
import argparse
from datetime import datetime

# Tenta importar psycopg2 e python-dotenv
try:
    import psycopg2
    from psycopg2.extras import DictCursor
except ImportError:
    print("ERRO: O módulo 'psycopg2' não está instalado.")
    print("Instale-o com: pip install psycopg2-binary")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("ERRO: O módulo 'python-dotenv' não está instalado.")
    print("Instale-o com: pip install python-dotenv")
    sys.exit(1)

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Reseta CNPJs com status de erro para "queued" e corrige problemas de sessão')
    parser.add_argument('--db-url', help='URL de conexão com o banco de dados Heroku (ex: postgresql://username:password@hostname:5432/database_name)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Mostrar informações detalhadas')
    parser.add_argument('--fix-sessions', action='store_true', help='Corrigir sessões pendentes (PendingRollbackError)', default=True)
    parser.add_argument('--check-duplicates', action='store_true', help='Verificar CNPJs duplicados na tabela cnpj_data')
    
    return parser.parse_args()

def get_database_url(args):
    """Get database URL from args or environment"""
    # Prioridade: 1. Argumento da linha de comando, 2. Variável de ambiente
    if args.db_url:
        db_url = args.db_url
    else:
        # Tenta carregar do arquivo .env
        load_dotenv()
        db_url = os.environ.get('DATABASE_URL')
    
    if not db_url:
        print("ERRO: URL do banco de dados não fornecida.")
        print("Forneça a URL do banco de dados usando o argumento --db-url ou defina DATABASE_URL no arquivo .env")
        sys.exit(1)
    
    # Verifica se a URL contém placeholders de exemplo
    placeholders = ["usuario", "senha", "host", "porta", "nome_banco"]
    for placeholder in placeholders:
        if placeholder in db_url:
            print(f"ERRO: A URL do banco de dados contém o placeholder '{placeholder}'.")
            print("Substitua todos os placeholders pelos valores reais.")
            print("Exemplo de URL válida: postgresql://username:password@hostname:5432/database_name")
            sys.exit(1)
    
    # Converte postgres:// para postgresql:// se necessário (compatibilidade com Heroku)
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
        print("Nota: Convertendo 'postgres://' para 'postgresql://' para compatibilidade com psycopg2")
    
    return db_url

def connect_to_database(db_url):
    """Connect to the PostgreSQL database"""
    try:
        conn = psycopg2.connect(db_url)
        return conn
    except Exception as e:
        print(f"ERRO: Não foi possível conectar ao banco de dados: {str(e)}")
        sys.exit(1)

def reset_error_cnpjs(conn, verbose=False):
    """Reset CNPJs with error status to queued"""
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # Primeiro, conta quantos CNPJs estão com erro
            cur.execute("SELECT COUNT(*) FROM cnpj_queries WHERE status = 'error'")
            error_count = cur.fetchone()[0]
            
            if error_count == 0:
                print("Nenhum CNPJ com erro encontrado.")
                return 0
            
            # Obtém os CNPJs com erro para exibir detalhes se verbose=True
            if verbose:
                cur.execute("SELECT cnpj, error_message, updated_at FROM cnpj_queries WHERE status = 'error'")
                error_cnpjs = cur.fetchall()
                print(f"\nDetalhes dos {error_count} CNPJs com erro:")
                for i, row in enumerate(error_cnpjs, 1):
                    print(f"{i}. CNPJ: {row['cnpj']}")
                    print(f"   Erro: {row['error_message']}")
                    print(f"   Última atualização: {row['updated_at']}")
                    print()
            
            # Atualiza o status para "queued"
            now = datetime.utcnow()
            cur.execute("""
                UPDATE cnpj_queries 
                SET status = 'queued', 
                    error_message = NULL, 
                    updated_at = %s 
                WHERE status = 'error'
            """, (now,))
            
            # Confirma as alterações
            conn.commit()
            
            print(f"Sucesso! {error_count} CNPJs com erro foram resetados para 'queued'.")
            return error_count
            
    except Exception as e:
        conn.rollback()
        print(f"ERRO: Falha ao resetar CNPJs: {str(e)}")
        return 0

def fix_pending_sessions(conn, verbose=False):
    """Fix pending sessions with PendingRollbackError"""
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            # Verifica CNPJs que estão em processamento
            cur.execute("SELECT COUNT(*) FROM cnpj_queries WHERE status = 'processing'")
            processing_count = cur.fetchone()[0]
            
            if processing_count > 0:
                print(f"Encontrados {processing_count} CNPJs com status 'processing'.")
                
                # Atualiza o status para "queued"
                now = datetime.utcnow()
                cur.execute("""
                    UPDATE cnpj_queries 
                    SET status = 'queued', 
                        error_message = NULL, 
                        updated_at = %s 
                    WHERE status = 'processing'
                """, (now,))
                
                print(f"Resetados {processing_count} CNPJs de 'processing' para 'queued'.")
            else:
                print("Nenhum CNPJ com status 'processing' encontrado.")
            
            # Confirma as alterações
            conn.commit()
            
            return processing_count
            
    except Exception as e:
        conn.rollback()
        print(f"ERRO: Falha ao corrigir sessões pendentes: {str(e)}")
        return 0

def check_duplicate_cnpjs(conn):
    """Check for duplicate CNPJs in cnpj_data table"""
    try:
        with conn.cursor(cursor_factory=DictCursor) as cur:
            print("\nVerificando CNPJs duplicados na tabela cnpj_data...")
            cur.execute("""
                SELECT cnpj, COUNT(*) 
                FROM cnpj_data 
                GROUP BY cnpj 
                HAVING COUNT(*) > 1
            """)
            duplicates = cur.fetchall()
            
            if duplicates:
                print(f"ATENÇÃO: Encontrados {len(duplicates)} CNPJs duplicados na tabela cnpj_data!")
                for dup in duplicates:
                    print(f"CNPJ: {dup['cnpj']} - {dup['count']} ocorrências")
                
                # Pergunta se deseja corrigir os duplicados
                choice = input("\nDeseja remover os registros duplicados? (s/n): ")
                if choice.lower() == 's':
                    fixed_count = 0
                    for dup in duplicates:
                        cnpj = dup['cnpj']
                        # Mantém apenas o registro mais recente
                        cur.execute("""
                            WITH ranked AS (
                                SELECT id, ROW_NUMBER() OVER (PARTITION BY cnpj ORDER BY updated_at DESC) as rn
                                FROM cnpj_data
                                WHERE cnpj = %s
                            )
                            DELETE FROM cnpj_data
                            WHERE id IN (
                                SELECT id FROM ranked WHERE rn > 1
                            )
                        """, (cnpj,))
                        fixed_count += 1
                    
                    conn.commit()
                    print(f"Removidos registros duplicados para {fixed_count} CNPJs.")
            else:
                print("Nenhum CNPJ duplicado encontrado na tabela cnpj_data.")
            
            return len(duplicates)
            
    except Exception as e:
        conn.rollback()
        print(f"ERRO: Falha ao verificar CNPJs duplicados: {str(e)}")
        return 0

def main():
    """Main function"""
    args = parse_args()
    
    # Obtém a URL do banco de dados
    db_url = get_database_url(args)
    
    # Conecta ao banco de dados
    print(f"Conectando ao banco de dados...")
    conn = connect_to_database(db_url)
    
    try:
        # Corrige sessões pendentes se solicitado
        if args.fix_sessions:
            print("Corrigindo sessões pendentes...")
            fix_pending_sessions(conn, args.verbose)
        
        # Reseta CNPJs com erro
        print("Resetando CNPJs com erro para 'queued'...")
        reset_count = reset_error_cnpjs(conn, args.verbose)
        
        # Verifica CNPJs duplicados se solicitado
        if args.check_duplicates:
            check_duplicate_cnpjs(conn)
        
        if reset_count > 0 or args.fix_sessions:
            print("\nPara reiniciar a fila, execute o comando:")
            print("python3 restart_queue.py [URL_BASE]")
    finally:
        # Fecha a conexão com o banco de dados
        conn.close()

if __name__ == "__main__":
    main()
