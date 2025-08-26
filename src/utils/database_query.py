import sqlite3
import os
from typing import List, Dict, Any, Tuple

class AnalyticalCompanyDB:
    def __init__(self):
        self.db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'analytical_company.db')
    
    def execute_query(self, query: str, params: tuple = ()) -> Tuple[List[Dict[str, Any]], List[str]]:
        """
        Executa uma query SQL e retorna os resultados
        
        Returns:
            Tuple contendo:
            - Lista de dicionários com os resultados
            - Lista com os nomes das colunas
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Para acessar colunas por nome
            cursor = conn.cursor()
            
            cursor.execute(query, params)
            
            if query.strip().upper().startswith('SELECT'):
                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]
                results = [dict(row) for row in rows]
                return results, columns
            else:
                conn.commit()
                return [], []
                
        except Exception as e:
            raise Exception(f"Erro ao executar query: {str(e)}")
        finally:
            if conn:
                conn.close()
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Retorna o schema de uma tabela"""
        query = f"PRAGMA table_info({table_name})"
        results, _ = self.execute_query(query)
        return results
    
    def get_all_tables(self) -> List[str]:
        """Retorna lista de todas as tabelas no banco"""
        query = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        results, _ = self.execute_query(query)
        return [row['name'] for row in results]
    
    def get_sample_data(self, table_name: str, limit: int = 5) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Retorna dados de amostra de uma tabela"""
        query = f"SELECT * FROM {table_name} LIMIT {limit}"
        return self.execute_query(query)
    
    def search_tables_by_keyword(self, keyword: str) -> List[str]:
        """Busca tabelas que contenham uma palavra-chave no nome"""
        tables = self.get_all_tables()
        return [table for table in tables if keyword.lower() in table.lower()]
    
    def get_table_row_count(self, table_name: str) -> int:
        """Retorna o número de linhas de uma tabela"""
        query = f"SELECT COUNT(*) as count FROM {table_name}"
        results, _ = self.execute_query(query)
        return results[0]['count'] if results else 0

# Queries pré-definidas para análises comuns
PREDEFINED_QUERIES = {
    'receita_mensal': """
        SELECT 
            year, month, currency,
            SUM(amount) as amount,
            SUM(tax) as tax,
            SUM(amount_usd) as amount_usd,
            SUM(tax_usd) as tax_usd
        FROM dw_fact_billing fb
        JOIN dw_dim_date dd ON fb.date_key = dd.date_key
        JOIN dw_dim_currency dc ON fb.currency_key = dc.currency_key
        GROUP BY year, month, currency
        ORDER BY year, month, currency
    """,
    
    'top_clientes': """
        SELECT 
            dc.client_name,
            SUM(fb.amount) as amount
        FROM dw_fact_billing fb
        JOIN dw_dim_client dc ON fb.client_key = dc.client_key
        GROUP BY dc.client_name
        ORDER BY amount DESC
        LIMIT 10
    """,
    
    'utilizacao_recursos': """
        SELECT 
            dd.year, dd.month,
            SUM(ft.hours) as horas,
            COUNT(DISTINCT de.employee_id) as empregados_ativos,
            COUNT(DISTINCT de.employee_id) * 168 as capacidade_horas,
            ROUND((SUM(ft.hours) * 100.0) / (COUNT(DISTINCT de.employee_id) * 168), 2) as utilizacao_pct
        FROM dw_fact_timesheet ft
        JOIN dw_dim_date dd ON ft.date_key = dd.date_key
        JOIN dw_dim_employee de ON ft.employee_key = de.employee_key
        GROUP BY dd.year, dd.month
        ORDER BY dd.year, dd.month
    """,
    
    'sla_tickets': """
        SELECT 
            dt.priority,
            COUNT(*) as qtd,
            SUM(CASE WHEN ft.sla_met = 1 THEN 1 ELSE 0 END) as dentro_sla,
            ROUND((SUM(CASE WHEN ft.sla_met = 1 THEN 1 ELSE 0 END) * 100.0) / COUNT(*), 2) as pct_sla
        FROM dw_fact_ticket ft
        JOIN dw_dim_ticket dt ON ft.ticket_key = dt.ticket_key
        GROUP BY dt.priority
        ORDER BY dt.priority
    """
}

