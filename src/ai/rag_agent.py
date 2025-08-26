import ollama
import chromadb
import os
from typing import Dict, Any, List
from sentence_transformers import SentenceTransformer

class RAGAgent:
    def __init__(self, ollama_model: str = "llama3.2"):
        self.ollama_model = ollama_model
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        
        # Inicializar ChromaDB
        self.chroma_client = chromadb.PersistentClient(
            path=os.path.join(os.path.dirname(__file__), '..', 'database', 'chroma_db')
        )
        
        # Criar ou obter coleção
        self.collection = self.chroma_client.get_or_create_collection(
            name="analytical_company_knowledge",
            metadata={"description": "Base de conhecimento da Analytical Company"}
        )
        
        # Inicializar base de conhecimento se estiver vazia
        if self.collection.count() == 0:
            self._initialize_knowledge_base()
    
    def _initialize_knowledge_base(self):
        """Inicializa a base de conhecimento com informações sobre a empresa"""
        
        knowledge_documents = [
            {
                "id": "company_overview",
                "content": """A Analytical Company é uma empresa de consultoria especializada em análise de dados e business intelligence. 
                Oferecemos serviços de desenvolvimento de projetos, análise de dados, implementação de soluções tecnológicas e consultoria estratégica. 
                Nossa equipe é composta por profissionais especializados em diversas tecnologias e metodologias de análise.""",
                "metadata": {"category": "empresa", "type": "overview"}
            },
            {
                "id": "services",
                "content": """Nossos principais serviços incluem: Desenvolvimento de projetos customizados, Análise de dados e Business Intelligence, 
                Consultoria em tecnologia, Implementação de soluções de Data Warehouse, Desenvolvimento de dashboards e relatórios, 
                Treinamento em ferramentas de análise, Suporte técnico especializado.""",
                "metadata": {"category": "servicos", "type": "lista"}
            },
            {
                "id": "data_warehouse",
                "content": """Nosso Data Warehouse é estruturado seguindo metodologias de modelagem dimensional. 
                Utilizamos tabelas de fatos e dimensões para otimizar consultas analíticas. As tabelas de fatos armazenam métricas quantitativas 
                como receita, horas trabalhadas e tickets, enquanto as dimensões fornecem contexto como clientes, funcionários, projetos e datas.""",
                "metadata": {"category": "tecnologia", "type": "data_warehouse"}
            },
            {
                "id": "kpis",
                "content": """Os principais KPIs que monitoramos incluem: Receita mensal e anual por cliente e projeto, 
                Utilização de recursos humanos (horas trabalhadas vs capacidade), Performance de SLA em tickets de suporte, 
                Margem de lucro por projeto, Taxa de crescimento de clientes, Produtividade por funcionário, 
                Tempo médio de resolução de tickets.""",
                "metadata": {"category": "metricas", "type": "kpis"}
            },
            {
                "id": "currencies",
                "content": """Trabalhamos com múltiplas moedas: BRL (Real Brasileiro), USD (Dólar Americano), EUR (Euro). 
                Todas as análises financeiras consideram conversões para USD como moeda base para comparações. 
                As taxas de câmbio são atualizadas regularmente para garantir precisão nas análises.""",
                "metadata": {"category": "financeiro", "type": "moedas"}
            },
            {
                "id": "projects",
                "content": """Nossos projetos são categorizados por tipo de contrato (fixo, por hora, retainer), 
                tecnologia principal utilizada, status (ativo, concluído, pausado) e cliente. 
                Cada projeto tem uma equipe dedicada e métricas de acompanhamento específicas.""",
                "metadata": {"category": "projetos", "type": "gestao"}
            },
            {
                "id": "teams",
                "content": """Nossa estrutura organizacional é dividida em departamentos especializados: 
                Desenvolvimento, Análise de Dados, Consultoria, Suporte, Vendas e Marketing. 
                Cada departamento tem equipes específicas com líderes e especialistas em diferentes tecnologias.""",
                "metadata": {"category": "organizacao", "type": "estrutura"}
            },
            {
                "id": "technologies",
                "content": """Utilizamos diversas tecnologias em nossos projetos: Python, SQL, JavaScript, React, Flask, 
                Power BI, Tableau, Apache Spark, Hadoop, AWS, Azure, Google Cloud, Docker, Kubernetes, 
                Machine Learning, Deep Learning, Natural Language Processing.""",
                "metadata": {"category": "tecnologia", "type": "stack"}
            }
        ]
        
        # Adicionar documentos à coleção
        for doc in knowledge_documents:
            embedding = self.embedding_model.encode(doc["content"]).tolist()
            
            self.collection.add(
                ids=[doc["id"]],
                embeddings=[embedding],
                documents=[doc["content"]],
                metadatas=[doc["metadata"]]
            )
    
    def search_knowledge(self, query: str, n_results: int = 3) -> List[Dict[str, Any]]:
        """Busca documentos relevantes na base de conhecimento"""
        
        # Gerar embedding da consulta
        query_embedding = self.embedding_model.encode(query).tolist()
        
        # Buscar documentos similares
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results
        )
        
        # Formatar resultados
        documents = []
        if results['documents'] and results['documents'][0]:
            for i, doc in enumerate(results['documents'][0]):
                documents.append({
                    'content': doc,
                    'metadata': results['metadatas'][0][i] if results['metadatas'] else {},
                    'distance': results['distances'][0][i] if results['distances'] else 0
                })
        
        return documents
    
    def process_query(self, user_input: str, chat_history: list = None) -> Dict[str, Any]:
        """Processa uma consulta usando RAG"""
        
        try:
            # Buscar documentos relevantes
            relevant_docs = self.search_knowledge(user_input, n_results=3)
            
            # Construir contexto
            context = ""
            if relevant_docs:
                context = "Informações relevantes da base de conhecimento:\n\n"
                for i, doc in enumerate(relevant_docs, 1):
                    context += f"{i}. {doc['content']}\n\n"
            
            # Construir histórico da conversa
            conversation_context = ""
            if chat_history:
                conversation_context = "Contexto da conversa:\n"
                for msg in chat_history[-3:]:  # Últimas 3 mensagens
                    role = "Usuário" if msg['role'] == 'user' else "Assistente"
                    conversation_context += f"{role}: {msg['content']}\n"
                conversation_context += "\n"
            
            # Gerar resposta
            response = self._generate_rag_response(user_input, context, conversation_context)
            
            return {
                'response': response,
                'metadata': {
                    'relevant_docs': len(relevant_docs),
                    'sources': [doc['metadata'] for doc in relevant_docs]
                }
            }
            
        except Exception as e:
            return {
                'response': f'Desculpe, ocorreu um erro ao buscar informações: {str(e)}',
                'metadata': {
                    'error': str(e)
                }
            }
    
    def _generate_rag_response(self, user_input: str, context: str, conversation_context: str) -> str:
        """Gera resposta usando RAG com Ollama"""
        
        prompt = f"""Você é um assistente especializado da Analytical Company. Use as informações fornecidas para responder à pergunta do usuário de forma precisa e útil.

{context}

{conversation_context}

PERGUNTA DO USUÁRIO: {user_input}

INSTRUÇÕES:
1. Responda em português brasileiro
2. Use apenas as informações fornecidas no contexto
3. Se não houver informações suficientes, seja honesto sobre isso
4. Seja claro, objetivo e profissional
5. Forneça exemplos quando apropriado
6. Se a pergunta for sobre dados específicos, sugira que o usuário faça uma consulta mais específica

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
            return f"Desculpe, não consegui me conectar ao serviço de IA. Erro: {str(e)}"
    
    def add_knowledge(self, content: str, metadata: Dict[str, Any] = None) -> bool:
        """Adiciona novo conhecimento à base"""
        
        try:
            # Gerar ID único
            import uuid
            doc_id = str(uuid.uuid4())
            
            # Gerar embedding
            embedding = self.embedding_model.encode(content).tolist()
            
            # Adicionar à coleção
            self.collection.add(
                ids=[doc_id],
                embeddings=[embedding],
                documents=[content],
                metadatas=[metadata or {}]
            )
            
            return True
            
        except Exception as e:
            print(f"Erro ao adicionar conhecimento: {str(e)}")
            return False
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas da base de conhecimento"""
        
        try:
            count = self.collection.count()
            return {
                'total_documents': count,
                'collection_name': self.collection.name
            }
        except Exception as e:
            return {
                'error': str(e)
            }

