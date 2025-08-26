import ollama
import re
from typing import Dict, Any, List, Optional
from src.utils.database_query import AnalyticalCompanyDB, PREDEFINED_QUERIES

class SQLAgent:
    def __init__(self, ollama_model: str = "llama3.2"):
        self.ollama_model = ollama_model
        self.db = AnalyticalCompanyDB()
        
    def get_database_schema(self) -> str:
        """Retorna uma descrição do schema do banco de dados"""
        
        schema_description = """
SCHEMA DO BANCO DE DADOS ANALYTICAL COMPANY:

=== TABELAS OLTP (Dados Operacionais) ===

1. oltp_clients - Clientes da empresa
   - id, name, tax_id, industry, size_segment, country, state, city, created_at

2. oltp_employees - Funcionários
   - id, first_name, last_name, email, department, role, manager_id, team_id, hire_date, salary, country, state, city

3. oltp_teams - Times/Equipes
   - id, name, department

4. oltp_projects - Projetos
   - id, client_id, name, start_date, end_date, contract_type, technology_primary, status, team_id, daily_rate, currency

5. oltp_assignments - Alocações de funcionários em projetos
   - id, employee_id, project_id, start_date, end_date, allocation_pct

6. oltp_timesheets - Registro de horas trabalhadas
   - id, employee_id, project_id, work_date, hours, billing_rate, approved

7. oltp_tickets - Tickets de suporte
   - id, project_id, created_at, closed_at, priority, type, status, sla_minutes, assigned_employee_id

8. oltp_invoices - Faturas
   - id, client_id, project_id, issue_date, due_date, amount, currency, status, tax

=== TABELAS DW (Data Warehouse - Dados Analíticos) ===

DIMENSÕES:
- dw_dim_date - Dimensão de datas (date_key, date_iso, day, month, year, quarter, etc.)
- dw_dim_client - Dimensão de clientes (client_key, client_id, client_name, industry, etc.)
- dw_dim_employee - Dimensão de funcionários (employee_key, employee_id, full_name, department, etc.)
- dw_dim_project - Dimensão de projetos (project_key, project_id, project_name, client_key, etc.)
- dw_dim_currency - Dimensão de moedas (currency_key, code, name)
- dw_dim_ticket - Dimensão de tickets (ticket_key, ticket_id, priority, type)

FATOS:
- dw_fact_timesheet - Fatos de horas trabalhadas (date_key, employee_key, project_key, hours, billable)
- dw_fact_billing - Fatos de faturamento (date_key, client_key, project_key, amount, tax, currency_key, status)
- dw_fact_ticket - Fatos de tickets (open_date_key, close_date_key, project_key, ticket_key, time_to_close_min, sla_met)

IMPORTANTE: Use as tabelas DW (Data Warehouse) para análises e relatórios, pois elas são otimizadas para consultas analíticas.
"""
        return schema_description
    
    def check_predefined_queries(self, user_input: str) -> Optional[str]:
        """Verifica se a pergunta corresponde a uma query pré-definida"""
        
        user_lower = user_input.lower()
        
        # Mapeamento de palavras-chave para queries pré-definidas
        query_mappings = {
            'receita_mensal': ['receita mensal', 'faturamento mensal', 'receita por mês'],
            'top_clientes': ['top clientes', 'melhores clientes', 'maiores clientes', 'ranking clientes'],
            'utilizacao_recursos': ['utilização', 'utilização recursos', 'horas trabalhadas', 'capacidade'],
            'sla_tickets': ['sla', 'tickets', 'sla tickets', 'performance tickets']
        }
        
        for query_name, keywords in query_mappings.items():
            if any(keyword in user_lower for keyword in keywords):
                return query_name
        
        return None
    
    def generate_sql_query(self, user_input: str, chat_history: list = None) -> str:
        """Gera uma query SQL baseada na pergunta do usuário"""
        
        schema = self.get_database_schema()
        
        # Construir contexto da conversa
        context = ""
        if chat_history:
            context = "Contexto da conversa anterior:\n"
            for msg in chat_history[-3:]:  # Últimas 3 mensagens
                if msg['role'] == 'user':
                    context += f"Usuário: {msg['content']}\n"
                elif msg.get('sql_query'):
                    context += f"Query anterior: {msg['sql_query']}\n"
            context += "\n"
        
        prompt = f"""Você é um especialista em SQL e análise de dados. Sua tarefa é gerar uma query SQL válida baseada na pergunta do usuário.

{schema}

{context}PERGUNTA DO USUÁRIO: {user_input}

INSTRUÇÕES:
1. Gere APENAS a query SQL, sem explicações adicionais
2. Use as tabelas DW (Data Warehouse) sempre que possível para análises
3. Para dados temporais, use a tabela dw_dim_date com JOINs apropriados
4. Para valores monetários, considere conversões de moeda quando necessário
5. Use agregações (SUM, COUNT, AVG) quando apropriado
6. Limite resultados com LIMIT quando necessário (máximo 100 registros)
7. Use ORDER BY para organizar resultados de forma lógica

QUERY SQL:"""

        try:
            response = ollama.chat(
                model=self.ollama_model,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }]
            )
            
            sql_query = response['message']['content'].strip()
            
            # Limpar a resposta para extrair apenas o SQL
            sql_query = self._clean_sql_response(sql_query)
            
            return sql_query
            
        except Exception as e:
            raise Exception(f"Erro ao gerar query SQL: {str(e)}")
    
    def _clean_sql_response(self, response: str) -> str:
        """Limpa a resposta do modelo para extrair apenas o SQL"""
        
        # Remover blocos de código markdown
        response = re.sub(r'```sql\n?', '', response)
        response = re.sub(r'```\n?', '', response)
        
        # Remover explicações antes e depois do SQL
        lines = response.split('\n')
        sql_lines = []
        in_sql = False
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Detectar início de SQL
            if line.upper().startswith(('SELECT', 'WITH', 'INSERT', 'UPDATE', 'DELETE')):
                in_sql = True
                sql_lines.append(line)
            elif in_sql and (line.endswith(';') or line.upper().startswith(('ORDER BY', 'GROUP BY', 'HAVING', 'LIMIT', 'FROM', 'WHERE', 'JOIN', 'INNER', 'LEFT', 'RIGHT'))):
                sql_lines.append(line)
                if line.endswith(';'):
                    break
            elif in_sql:
                sql_lines.append(line)
        
        if sql_lines:
            return '\n'.join(sql_lines)
        else:
            # Se não conseguiu extrair, retorna a resposta original limpa
            return response.strip()

    def _normalize_table_names(self, sql_query: str) -> str:
        """Garante que as tabelas fact/dim usem o prefixo dw_ e atualiza os aliases."""
        tables = self.db.get_all_tables()
        mapping = {tbl[3:]: tbl for tbl in tables if tbl.startswith('dw_')}

        for base, full in mapping.items():
            # Substituir referência de tabela em FROM/JOIN sem prefixo
            sql_query = re.sub(rf'(?i)(FROM|JOIN)\s+{base}\b', rf'\1 {full}', sql_query)

            # Detectar alias após correção
            alias_match = re.search(rf'(?i)(FROM|JOIN)\s+{full}\s+(?:AS\s+)?(\w+)', sql_query)
            alias = alias_match.group(2) if alias_match else None

            if alias:
                sql_query = re.sub(rf'\b{base}\.', f'{alias}.', sql_query)
            else:
                sql_query = re.sub(rf'\b{base}\.', f'{full}.', sql_query)

            sql_query = re.sub(rf'\b{base}\b', full, sql_query)

        return sql_query

    def _fix_sql_query(self, sql_query: str, error_msg: str) -> Optional[str]:
        """Tenta corrigir uma query SQL com base no schema e na mensagem de erro"""

        schema = self.get_database_schema()
        prompt = f"""A seguinte query SQL apresentou erro:
{sql_query}

ERRO: {error_msg}

Considerando o schema abaixo, corrija a query mantendo o mesmo objetivo.
{schema}

QUERY CORRIGIDA:"""

        try:
            response = ollama.chat(
                model=self.ollama_model,
                messages=[{'role': 'user', 'content': prompt}]
            )
            corrected = self._clean_sql_response(response['message']['content'].strip())
            return corrected
        except Exception:
            return None

    def process_query(self, user_input: str, chat_history: list = None) -> Dict[str, Any]:
        """Processa uma consulta SQL completa"""

        try:
            # Verificar se é uma query pré-definida
            predefined_query = self.check_predefined_queries(user_input)

            if predefined_query and predefined_query in PREDEFINED_QUERIES:
                sql_query = PREDEFINED_QUERIES[predefined_query]
                query_source = 'predefined'
            else:
                # Gerar query usando IA
                sql_query = self.generate_sql_query(user_input, chat_history)
                sql_query = self._normalize_table_names(sql_query)
                query_source = 'generated'

            try:
                # Executar a query
                results, columns = self.db.execute_query(sql_query)
            except Exception as e:
                if 'no such column' in str(e).lower():
                    corrected = self._fix_sql_query(sql_query, str(e))
                    if corrected:
                        sql_query = self._normalize_table_names(corrected)
                        query_source = 'corrected'
                        results, columns = self.db.execute_query(sql_query)
                    else:
                        raise
                else:
                    raise

            # Gerar resposta em linguagem natural
            response_text = self._generate_response_text(user_input, results, columns, sql_query)

            return {
                'response': response_text,
                'sql_query': sql_query,
                'results': results,
                'columns': columns,
                'metadata': {
                    'query_source': query_source,
                    'row_count': len(results)
                }
            }

        except Exception as e:
            return {
                'response': f'Desculpe, ocorreu um erro ao executar a consulta SQL: {str(e)}',
                'sql_query': sql_query if 'sql_query' in locals() else None,
                'results': [],
                'columns': [],
                'metadata': {
                    'error': str(e)
                }
            }
    
    def _generate_response_text(self, user_input: str, results: List[Dict], columns: List[str], sql_query: str) -> str:
        """Gera uma resposta em linguagem natural baseada nos resultados"""
        
        if not results:
            return "Não foram encontrados dados para sua consulta."
        
        # Limitar resultados para resposta textual
        display_results = results[:10]  # Mostrar apenas os primeiros 10 resultados
        
        prompt = f"""Baseado nos resultados da consulta SQL, gere uma resposta clara e informativa em português.

PERGUNTA DO USUÁRIO: {user_input}

QUERY EXECUTADA: {sql_query}

RESULTADOS ({len(results)} registros encontrados):
{display_results}

INSTRUÇÕES:
1. Responda em português brasileiro
2. Seja claro e objetivo
3. Destaque os principais insights dos dados
4. Se houver muitos resultados, mencione que está mostrando apenas os principais
5. Use formatação adequada para números (vírgulas para milhares, etc.)
6. Seja profissional mas acessível

RESPOSTA:"""

        try:
            response = ollama.chat(
                model=self.ollama_model,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }]
            )
            
            return response['message']['content']
            
        except Exception as e:
            # Fallback para resposta simples
            return f"Encontrei {len(results)} registros. Aqui estão os principais resultados: {display_results[:3]}"

