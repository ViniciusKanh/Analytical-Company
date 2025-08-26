import ollama
import re
from typing import Dict, Any, Tuple, Optional
from src.utils.database_query import AnalyticalCompanyDB, PREDEFINED_QUERIES
from src.ai.sql_agent import SQLAgent
from src.ai.rag_agent import RAGAgent
from src.ai.learning_system import LearningSystem

class AIOrchestrator:
    def __init__(self, ollama_model: str = "llama3.2"):
        self.ollama_model = ollama_model
        self.db = AnalyticalCompanyDB()
        self.sql_agent = SQLAgent(ollama_model)
        self.rag_agent = RAGAgent(ollama_model)
        self.learning_system = LearningSystem()
        
    def classify_query(self, user_input: str) -> str:
        """
        Classifica a pergunta do usuário para determinar o tipo de resposta
        
        Returns:
            'sql' - Para consultas que precisam de dados específicos
            'rag' - Para perguntas conceituais ou explicações
            'general' - Para conversas gerais
        """
        
        # Primeiro, tentar classificação melhorada baseada em aprendizado
        learned_classification = self.learning_system.improve_classification(user_input)
        if learned_classification:
            return learned_classification
        
        # Palavras-chave que indicam necessidade de dados SQL
        sql_keywords = [
            'quantos', 'quanto', 'qual', 'quais', 'total', 'soma', 'média', 'máximo', 'mínimo',
            'receita', 'faturamento', 'vendas', 'clientes', 'projetos', 'funcionários', 'empregados',
            'tickets', 'sla', 'horas', 'utilização', 'performance', 'relatório', 'dados',
            'número', 'valor', 'custo', 'lucro', 'margem', 'crescimento', 'tendência',
            'comparar', 'comparação', 'ranking', 'top', 'melhor', 'pior', 'maior', 'menor'
        ]
        
        # Palavras-chave que indicam busca conceitual (RAG)
        rag_keywords = [
            'como', 'por que', 'porque', 'explique', 'explicar', 'definir', 'definição',
            'conceito', 'significado', 'diferença', 'vantagem', 'desvantagem', 'benefício',
            'processo', 'metodologia', 'estratégia', 'análise', 'interpretação', 'insight'
        ]
        
        user_lower = user_input.lower()
        
        # Contar ocorrências de palavras-chave
        sql_score = sum(1 for keyword in sql_keywords if keyword in user_lower)
        rag_score = sum(1 for keyword in rag_keywords if keyword in user_lower)
        
        # Verificar se menciona tabelas ou campos específicos
        tables = self.db.get_all_tables()
        table_mentions = sum(1 for table in tables if table.lower() in user_lower)
        
        if table_mentions > 0 or sql_score > rag_score:
            return 'sql'
        elif rag_score > 0:
            return 'rag'
        else:
            return 'general'
    
    def process_query(self, user_input: str, chat_history: list = None) -> Dict[str, Any]:
        """
        Processa a consulta do usuário e retorna a resposta apropriada
        
        Args:
            user_input: Pergunta do usuário
            chat_history: Histórico da conversa (lista de mensagens)
            
        Returns:
            Dict com resposta, tipo de query, tempo de execução, etc.
        """
        
        import time
        start_time = time.time()
        
        try:
            # Classificar o tipo de consulta
            query_type = self.classify_query(user_input)
            
            if query_type == 'sql':
                # Processar com agente SQL
                result = self.sql_agent.process_query(user_input, chat_history)
                
            elif query_type == 'rag':
                # Processar com agente RAG
                result = self.rag_agent.process_query(user_input, chat_history)
                
            else:
                # Resposta geral usando Ollama
                result = self._generate_general_response(user_input, chat_history)
            
            execution_time = time.time() - start_time
            
            # Registrar analytics para aprendizado
            self.learning_system.analyze_query_patterns(
                user_input, 
                query_type, 
                result.get('success', True), 
                execution_time,
                result.get('error')
            )
            
            return {
                'response': result.get('response', 'Desculpe, não consegui processar sua solicitação.'),
                'query_type': query_type,
                'sql_query': result.get('sql_query'),
                'execution_time': execution_time,
                'success': True,
                'metadata': result.get('metadata', {})
            }
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            # Registrar erro para aprendizado
            self.learning_system.analyze_query_patterns(
                user_input, 
                query_type if 'query_type' in locals() else 'error', 
                False, 
                execution_time,
                str(e)
            )
            
            return {
                'response': f'Desculpe, ocorreu um erro ao processar sua solicitação: {str(e)}',
                'query_type': 'error',
                'sql_query': None,
                'execution_time': execution_time,
                'success': False,
                'error': str(e)
            }
    
    def _generate_general_response(self, user_input: str, chat_history: list = None) -> Dict[str, Any]:
        """Gera resposta geral usando Ollama"""
        
        # Construir contexto da conversa
        context = ""
        if chat_history:
            context = "Histórico da conversa:\n"
            for msg in chat_history[-5:]:  # Últimas 5 mensagens
                role = "Usuário" if msg['role'] == 'user' else "Assistente"
                context += f"{role}: {msg['content']}\n"
            context += "\n"
        
        prompt = f"""Você é um assistente de IA especializado em análise de dados empresariais.
Você trabalha com dados de uma empresa de consultoria e pode ajudar com análises, relatórios e insights.

{context}Usuário: {user_input}

Responda de forma útil e profissional. Se a pergunta for sobre dados específicos, sugira que o usuário seja mais específico sobre quais dados deseja consultar."""
        
        try:
            response = ollama.chat(
                model=self.ollama_model,
                messages=[{
                    'role': 'user',
                    'content': prompt
                }]
            )
            
            return {
                'response': response['message']['content'],
                'metadata': {
                    'model': self.ollama_model,
                    'type': 'general_chat'
                }
            }
            
        except Exception as e:
            return {
                'response': 'Desculpe, não consegui me conectar ao serviço de IA. Verifique se o Ollama está rodando.',
                'metadata': {
                    'error': str(e)
                }
            }
    
    def process_feedback(self, message_id: int, feedback_type: str, feedback_text: str = None):
        """Processa feedback do usuário"""
        return self.learning_system.process_feedback(message_id, feedback_type, feedback_text)
    
    def get_learning_insights(self):
        """Retorna insights do sistema de aprendizado"""
        return self.learning_system.get_learning_insights()
    
    def optimize_system(self):
        """Otimiza o sistema baseado no aprendizado"""
        return self.learning_system.optimize_responses()

