import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict
from src.models.chat import ChatFeedback, Message
from src.models.user import db
from src.ai.rag_agent import RAGAgent

class LearningSystem:
    def __init__(self):
        self.rag_agent = RAGAgent()
        self.learning_db_path = os.path.join(os.path.dirname(__file__), '..', 'database', 'learning.db')
        self.init_learning_database()
    
    def init_learning_database(self):
        """Inicializa banco de dados para aprendizado"""
        conn = sqlite3.connect(self.learning_db_path)
        cursor = conn.cursor()
        
        cursor.executescript("""
        CREATE TABLE IF NOT EXISTS query_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,
            query_type TEXT NOT NULL,
            success_rate REAL DEFAULT 0.0,
            usage_count INTEGER DEFAULT 0,
            last_used TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS response_improvements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_query TEXT NOT NULL,
            original_response TEXT NOT NULL,
            improved_response TEXT NOT NULL,
            feedback_score REAL NOT NULL,
            improvement_reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preference_type TEXT NOT NULL,
            preference_value TEXT NOT NULL,
            frequency INTEGER DEFAULT 1,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE TABLE IF NOT EXISTS query_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_text TEXT NOT NULL,
            query_type TEXT NOT NULL,
            execution_time REAL,
            success BOOLEAN,
            error_message TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        
        CREATE INDEX IF NOT EXISTS idx_patterns_type ON query_patterns(query_type);
        CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON query_analytics(timestamp);
        """)
        
        conn.commit()
        conn.close()
    
    def analyze_query_patterns(self, query: str, query_type: str, success: bool, execution_time: float = None, error: str = None):
        """Analisa padrões de consultas para melhorar classificação"""
        
        # Registrar analytics
        self._record_query_analytics(query, query_type, execution_time, success, error)
        
        # Extrair padrões da consulta
        patterns = self._extract_query_patterns(query)
        
        # Atualizar padrões no banco
        conn = sqlite3.connect(self.learning_db_path)
        cursor = conn.cursor()
        
        for pattern in patterns:
            # Verificar se padrão já existe
            cursor.execute("""
                SELECT id, usage_count, success_rate FROM query_patterns 
                WHERE pattern = ? AND query_type = ?
            """, (pattern, query_type))
            
            result = cursor.fetchone()
            
            if result:
                # Atualizar padrão existente
                pattern_id, usage_count, current_success_rate = result
                new_usage_count = usage_count + 1
                
                # Calcular nova taxa de sucesso
                if success:
                    new_success_rate = ((current_success_rate * usage_count) + 1) / new_usage_count
                else:
                    new_success_rate = (current_success_rate * usage_count) / new_usage_count
                
                cursor.execute("""
                    UPDATE query_patterns 
                    SET usage_count = ?, success_rate = ?, last_used = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (new_usage_count, new_success_rate, pattern_id))
            else:
                # Criar novo padrão
                initial_success_rate = 1.0 if success else 0.0
                cursor.execute("""
                    INSERT INTO query_patterns (pattern, query_type, success_rate, usage_count)
                    VALUES (?, ?, ?, 1)
                """, (pattern, query_type, initial_success_rate))
        
        conn.commit()
        conn.close()
    
    def _extract_query_patterns(self, query: str) -> List[str]:
        """Extrai padrões úteis de uma consulta"""
        patterns = []
        query_lower = query.lower()
        
        # Padrões de palavras-chave
        keywords = [
            'receita', 'faturamento', 'vendas', 'clientes', 'projetos', 
            'funcionários', 'empregados', 'tickets', 'sla', 'horas',
            'total', 'soma', 'média', 'máximo', 'mínimo', 'quantos',
            'qual', 'quais', 'como', 'por que', 'explique'
        ]
        
        for keyword in keywords:
            if keyword in query_lower:
                patterns.append(f"keyword_{keyword}")
        
        # Padrões de estrutura
        if '?' in query:
            patterns.append("question_mark")
        
        if any(word in query_lower for word in ['último', 'última', 'recente']):
            patterns.append("temporal_recent")
        
        if any(word in query_lower for word in ['comparar', 'diferença', 'vs']):
            patterns.append("comparison")
        
        if any(word in query_lower for word in ['top', 'melhor', 'maior', 'ranking']):
            patterns.append("ranking")
        
        # Padrão de tamanho da consulta
        word_count = len(query.split())
        if word_count <= 3:
            patterns.append("short_query")
        elif word_count <= 10:
            patterns.append("medium_query")
        else:
            patterns.append("long_query")
        
        return patterns
    
    def _record_query_analytics(self, query: str, query_type: str, execution_time: float, success: bool, error: str):
        """Registra analytics da consulta"""
        conn = sqlite3.connect(self.learning_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO query_analytics (query_text, query_type, execution_time, success, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (query, query_type, execution_time, success, error))
        
        conn.commit()
        conn.close()
    
    def improve_classification(self, query: str) -> str:
        """Melhora classificação baseada em padrões aprendidos"""
        patterns = self._extract_query_patterns(query)
        
        conn = sqlite3.connect(self.learning_db_path)
        cursor = conn.cursor()
        
        # Buscar padrões com maior taxa de sucesso
        type_scores = defaultdict(float)
        
        for pattern in patterns:
            cursor.execute("""
                SELECT query_type, success_rate, usage_count 
                FROM query_patterns 
                WHERE pattern = ? AND usage_count >= 3
                ORDER BY success_rate DESC
            """, (pattern,))
            
            results = cursor.fetchall()
            for query_type, success_rate, usage_count in results:
                # Peso baseado na taxa de sucesso e frequência de uso
                weight = success_rate * min(usage_count / 10, 1.0)
                type_scores[query_type] += weight
        
        conn.close()
        
        # Retornar tipo com maior score
        if type_scores:
            best_type = max(type_scores.items(), key=lambda x: x[1])
            if best_type[1] > 0.5:  # Threshold mínimo
                return best_type[0]
        
        return None  # Usar classificação padrão
    
    def process_feedback(self, message_id: int, feedback_type: str, feedback_text: str = None):
        """Processa feedback do usuário para melhorar respostas"""
        
        # Buscar mensagem original
        message = Message.query.get(message_id)
        if not message or message.role != 'assistant':
            return
        
        # Buscar mensagem do usuário correspondente
        user_message = Message.query.filter_by(
            chat_id=message.chat_id,
            role='user'
        ).filter(Message.timestamp < message.timestamp).order_by(Message.timestamp.desc()).first()
        
        if not user_message:
            return
        
        # Registrar feedback
        feedback_score = 1.0 if feedback_type == 'positive' else -1.0
        
        conn = sqlite3.connect(self.learning_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO response_improvements 
            (original_query, original_response, improved_response, feedback_score, improvement_reason)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_message.content,
            message.content,
            feedback_text or message.content,
            feedback_score,
            feedback_text
        ))
        
        conn.commit()
        conn.close()
        
        # Se feedback negativo, tentar melhorar resposta
        if feedback_type == 'negative':
            self._learn_from_negative_feedback(user_message.content, message.content, feedback_text)
    
    def _learn_from_negative_feedback(self, query: str, response: str, feedback: str):
        """Aprende com feedback negativo para melhorar futuras respostas"""
        
        # Adicionar conhecimento baseado no feedback
        if feedback:
            improvement_knowledge = f"""
            Consulta: {query}
            Resposta original: {response}
            Feedback do usuário: {feedback}
            
            Esta interação indica que a resposta pode ser melhorada considerando o feedback fornecido.
            """
            
            self.rag_agent.add_knowledge(
                improvement_knowledge,
                {
                    'category': 'feedback',
                    'type': 'improvement',
                    'query_type': 'learning'
                }
            )
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Retorna insights do sistema de aprendizado"""
        conn = sqlite3.connect(self.learning_db_path)
        cursor = conn.cursor()
        
        # Estatísticas gerais
        cursor.execute("SELECT COUNT(*) FROM query_analytics")
        total_queries = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM query_analytics WHERE success = 1")
        successful_queries = cursor.fetchone()[0]
        
        cursor.execute("SELECT AVG(execution_time) FROM query_analytics WHERE execution_time IS NOT NULL")
        avg_execution_time = cursor.fetchone()[0] or 0
        
        # Padrões mais comuns
        cursor.execute("""
            SELECT pattern, query_type, success_rate, usage_count 
            FROM query_patterns 
            ORDER BY usage_count DESC 
            LIMIT 10
        """)
        top_patterns = cursor.fetchall()
        
        # Tipos de consulta mais comuns
        cursor.execute("""
            SELECT query_type, COUNT(*) as count 
            FROM query_analytics 
            GROUP BY query_type 
            ORDER BY count DESC
        """)
        query_types = cursor.fetchall()
        
        # Feedback recente
        cursor.execute("""
            SELECT feedback_score, COUNT(*) as count 
            FROM response_improvements 
            WHERE created_at >= datetime('now', '-7 days')
            GROUP BY feedback_score
        """)
        recent_feedback = cursor.fetchall()
        
        conn.close()
        
        success_rate = (successful_queries / total_queries * 100) if total_queries > 0 else 0
        
        return {
            'total_queries': total_queries,
            'success_rate': round(success_rate, 2),
            'avg_execution_time': round(avg_execution_time, 3),
            'top_patterns': [
                {
                    'pattern': pattern,
                    'query_type': query_type,
                    'success_rate': round(success_rate, 2),
                    'usage_count': usage_count
                }
                for pattern, query_type, success_rate, usage_count in top_patterns
            ],
            'query_types': [
                {'type': query_type, 'count': count}
                for query_type, count in query_types
            ],
            'recent_feedback': [
                {'score': score, 'count': count}
                for score, count in recent_feedback
            ]
        }
    
    def optimize_responses(self):
        """Otimiza respostas baseado no aprendizado acumulado"""
        
        conn = sqlite3.connect(self.learning_db_path)
        cursor = conn.cursor()
        
        # Buscar padrões com baixa taxa de sucesso
        cursor.execute("""
            SELECT pattern, query_type, success_rate 
            FROM query_patterns 
            WHERE success_rate < 0.7 AND usage_count >= 5
        """)
        
        problematic_patterns = cursor.fetchall()
        
        # Buscar melhorias baseadas em feedback
        cursor.execute("""
            SELECT original_query, improved_response, feedback_score
            FROM response_improvements 
            WHERE feedback_score > 0
            ORDER BY created_at DESC
            LIMIT 50
        """)
        
        improvements = cursor.fetchall()
        
        conn.close()
        
        # Adicionar melhorias à base de conhecimento
        for query, improved_response, score in improvements:
            if score > 0:
                knowledge_content = f"""
                Consulta melhorada: {query}
                Resposta otimizada: {improved_response}
                
                Esta é uma resposta que recebeu feedback positivo e deve ser considerada como referência para consultas similares.
                """
                
                self.rag_agent.add_knowledge(
                    knowledge_content,
                    {
                        'category': 'optimization',
                        'type': 'improved_response',
                        'score': score
                    }
                )
        
        return {
            'problematic_patterns': len(problematic_patterns),
            'improvements_added': len(improvements)
        }
    
    def cleanup_old_data(self, days: int = 90):
        """Remove dados antigos para manter performance"""
        
        conn = sqlite3.connect(self.learning_db_path)
        cursor = conn.cursor()
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Remover analytics antigas
        cursor.execute("""
            DELETE FROM query_analytics 
            WHERE timestamp < ?
        """, (cutoff_date,))
        
        # Remover padrões não utilizados
        cursor.execute("""
            DELETE FROM query_patterns 
            WHERE last_used < ? AND usage_count < 3
        """, (cutoff_date,))
        
        deleted_analytics = cursor.rowcount
        
        cursor.execute("""
            DELETE FROM response_improvements 
            WHERE created_at < ?
        """, (cutoff_date,))
        
        deleted_improvements = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        return {
            'deleted_analytics': deleted_analytics,
            'deleted_improvements': deleted_improvements
        }

