# IA-Assistente | Analytical Company

## 🚀 Visão Geral do Projeto

Este projeto apresenta um chatbot de Inteligência Artificial Generativa avançado, desenvolvido para interagir com um banco de dados SQLite (`analytical_company.db`). O objetivo principal é fornecer respostas acionáveis e insights a partir de dados empresariais, utilizando uma arquitetura híbrida que combina consultas SQL diretas, recuperação aumentada de geração (RAG) e um sistema de aprendizado contínuo. A interface do usuário é moderna, intuitiva e responsiva, garantindo uma experiência fluida em diferentes dispositivos.

## ✨ Características Principais

### 🧠 Sistema de IA Híbrido e Orquestrado
- **Orquestrador Inteligente**: Um agente central que entende a solicitação do usuário e decide qual caminho seguir: consultas SQL, busca em banco vetorial (RAG) ou respostas gerais.
- **Agente SQL**: Capaz de gerar e executar queries SQL complexas a partir de linguagem natural, trazendo números, métricas e relatórios diretamente do banco de dados.
- **Agente RAG (Retrieval Augmented Generation)**: Utiliza um banco vetorial (ChromaDB) para resgatar informações semânticas, textos, insights ou documentos completos, enriquecendo as respostas da IA.
- **Integração Ollama**: Permite a utilização de modelos de linguagem grandes (LLMs) de forma local, garantindo privacidade e controle sobre os dados.

### 💾 Banco de Dados Analytical Company
- **Dados OLTP**: Estrutura de tabelas para operações do dia a dia (clientes, funcionários, projetos, timesheets, tickets, faturas).
- **Data Warehouse**: Estrutura dimensional otimizada para análises e relatórios complexos.
- **Queries Pré-definidas**: Um conjunto de consultas SQL otimizadas para métricas comuns (receita mensal, top clientes, utilização de recursos, SLA de tickets).

### 🎨 Interface Moderna e Intuitiva
- **Design Elegante**: Interface com tema escuro, tipografia clara e elementos visuais que proporcionam uma experiência agradável.
- **Animações Suaves**: Transições e microinterações que tornam a experiência do usuário mais dinâmica e responsiva.
- **Responsividade Total**: O layout se adapta perfeitamente a diferentes tamanhos de tela, de desktops a dispositivos móveis.
- **Sidebar Dinâmica**: Gerencia múltiplas conversas, permitindo busca e organização fácil do histórico.
- **Indicadores Visuais**: Feedback em tempo real sobre o status da IA, indicador de digitação e notificações.

### 📚 Sistema de Aprendizado Contínuo
- **Análise de Padrões**: O sistema aprende com cada interação, identificando padrões nas consultas dos usuários para melhorar a precisão da classificação (SQL vs. RAG vs. Geral).
- **Feedback do Usuário**: Mecanismo para coletar feedback positivo e negativo sobre as respostas da IA, permitindo ajustes e melhorias.
- **Otimização Contínua**: Com base no feedback e na análise de padrões, a IA otimiza suas estratégias de resposta ao longo do tempo.
- **Analytics Detalhados**: Métricas de performance, taxa de sucesso das consultas e insights sobre o uso do sistema.

### 💬 Gestão Inteligente de Conversas
- **Histórico Persistente**: Todas as interações são salvas no banco de dados, permitindo que a IA mantenha o contexto da conversa.
- **Limite Inteligente de Interações**: Cada chat tem um limite de 10 interações. Ao atingir o limite, um novo chat é criado automaticamente, mantendo a performance e a relevância do contexto.
- **Busca e Organização**: Facilita a localização de conversas antigas e a retomada de tópicos.

## 🛠️ Tecnologias Utilizadas

### Backend (Python)
- **Flask**: Microframework web para a construção da API.
- **SQLAlchemy**: ORM (Object-Relational Mapper) para interação com o banco de dados SQLite.
- **SQLite**: Banco de dados leve e eficiente para armazenamento de dados da aplicação e do histórico de conversas.
- **ChromaDB**: Banco de dados vetorial para armazenamento e busca de embeddings, essencial para o Agente RAG.
- **Sentence Transformers**: Biblioteca para gerar embeddings semânticos de texto, utilizada na busca RAG.
- **Ollama**: Ferramenta para rodar modelos de linguagem grandes (LLMs) localmente, garantindo flexibilidade e controle.

### Frontend (Web)
- **HTML5/CSS3**: Estrutura e estilização da interface do usuário, com foco em design moderno e responsividade.
- **JavaScript ES6+**: Lógica de interação dinâmica, comunicação com a API e manipulação do DOM.
- **Font Awesome**: Biblioteca de ícones para elementos visuais.
- **Google Fonts (Inter)**: Tipografia moderna e legível para toda a interface.

### IA e Machine Learning
- **Ollama**: Utilizado para inferência dos modelos de linguagem (LLMs) que alimentam o orquestrador e os agentes de IA.
- **ChromaDB**: Base de conhecimento vetorial para o Agente RAG, armazenando embeddings de documentos e informações relevantes.
- **Sentence-BERT**: Modelo de embedding para transformar texto em vetores numéricos, permitindo a busca semântica.
- **Algoritmo Híbrido de Classificação**: Desenvolvido para rotear as consultas do usuário para o agente mais apropriado (SQL, RAG ou Geral).

## 📋 Pré-requisitos

Para rodar este projeto, você precisará:

### Sistema
- **Python 3.11+**
- **Ollama** instalado e configurado (versão 0.11.6 ou superior)
- **4GB+ de RAM** (recomendado 8GB para melhor performance do Ollama)
- **2GB de espaço em disco** disponível

### Ollama (Instalação e Configuração)

Se você ainda não tem o Ollama instalado, siga as instruções oficiais em [ollama.ai](https://ollama.ai/).

```bash
# Exemplo de instalação para Linux/WSL:
curl -fsSL https://ollama.ai/install.sh | sh

# Para Windows, baixe o instalador em: https://ollama.ai/download/windows
# Seu Ollama está instalado em: C:\Users\vinny\AppData\Local\Programs\Ollama\ollama.exe

# Após a instalação, baixe o modelo de linguagem recomendado (llama3.2):
ollama pull llama3.2

# Verifique se o Ollama está rodando (deve mostrar os modelos baixados):
ollama list
```

## 🚀 Instalação e Configuração do Projeto

Siga estes passos para configurar e rodar o projeto em sua máquina:

### 1. Clone o Repositório (ou navegue até a pasta do projeto)

```bash
# Se você ainda não tem o projeto, clone-o:
git clone <URL_DO_SEU_REPOSITORIO>
cd analytical_chatbot # Ou o nome da sua pasta
```

### 2. Ajuste da Estrutura de Pastas (IMPORTANTE!)

Certifique-se de que seus arquivos estão na estrutura correta. Se você seguiu as instruções anteriores, seus arquivos já devem estar organizados. Caso contrário, execute os comandos abaixo na raiz do seu projeto (`Analytical Company/`):

```bash
# Mover chat.py para src/routes/
mv chat.py src/routes/

# Criar pasta src/utils/ se não existir
mkdir -p src/utils/

# Mover database_query.py para src/utils/
mv database_query.py src/utils/

# Mover index.html para src/static/
mv index.html src/static/

# Mover script.js para src/static/
mv script.js src/static/

# Mover styles.css para src/static/
mv styles.css src/static/

# Mover analytical_company.db para src/database/ (se ainda não estiver lá)
mv analytical_company.db src/database/

# Mover schema.py para src/ (se ainda não estiver lá)
mv schema.py src/
```

### 3. Ativar Ambiente Virtual e Instalar Dependências

```bash
# Navegue para a raiz do projeto (se ainda não estiver lá)
cd "C:\Users\vinny\OneDrive - PENSO TECNOLOGIA DA INFORMACAO\Documentos\Analytical Company"

# Ativar ambiente virtual (Windows)
.venv\Scripts\activate

# Ou para Linux/macOS:
source venv/bin/activate

# Instalar dependências listadas no requirements.txt
pip install -r requirements.txt
```

### 4. Configuração do Banco de Dados

O projeto já inclui o banco de dados `analytical_company.db` e o `schema.py` com a estrutura das tabelas OLTP e DW. Os modelos SQLAlchemy estão configurados para interagir com esses bancos. O banco de dados da aplicação (`app.db`) e o banco de aprendizado (`learning.db`) serão criados automaticamente na primeira execução.

### 5. Inicialização do Servidor

Certifique-se de que o Ollama está rodando em segundo plano (`ollama serve`). Em seguida, inicie o servidor Flask:

```bash
# Certifique-se de que o ambiente virtual está ativado
python src/main.py
```

O servidor estará disponível em: `http://localhost:5000`.

## 📁 Estrutura do Projeto

```
analytical_chatbot/
├── src/                     # Código fonte da aplicação
│   ├── ai/                  # Módulos de Inteligência Artificial
│   │   ├── orchestrator.py  # Orquestrador principal da IA
│   │   ├── sql_agent.py     # Agente para consultas SQL
│   │   ├── rag_agent.py     # Agente para Recuperação Aumentada de Geração (RAG)
│   │   └── learning_system.py # Sistema de aprendizado contínuo
│   ├── models/              # Modelos de dados (SQLAlchemy)
│   │   ├── user.py          # Modelo de usuário
│   │   └── chat.py          # Modelos de chat e mensagens
│   ├── routes/              # Definições de rotas da API Flask
│   │   ├── user.py          # Rotas relacionadas a usuários
│   │   └── chat.py          # Rotas para o chatbot (mensagens, chats, feedback)
│   ├── utils/               # Funções utilitárias
│   │   └── database_query.py # Funções para consultas ao banco de dados
│   ├── static/              # Arquivos estáticos do Frontend
│   │   ├── index.html       # Interface principal do chatbot
│   │   ├── styles.css       # Estilos CSS da interface
│   │   └── script.js        # Lógica JavaScript do frontend
│   ├── database/            # Bancos de dados SQLite
│   │   ├── analytical_company.db  # Banco de dados principal da empresa
│   │   ├── app.db           # Banco de dados da aplicação (usuários, chats)
│   │   ├── learning.db      # Banco de dados para o sistema de aprendizado
│   │   └── chroma_db/       # Diretório do banco vetorial ChromaDB
│   ├── schema.py            # Definição do esquema do banco de dados
│   └── main.py              # Ponto de entrada da aplicação Flask
├── venv/                    # Ambiente virtual Python
├── requirements.txt         # Lista de dependências Python
├── todo.md                  # Lista de tarefas e progresso do projeto
├── INSTALL.md               # Guia de instalação simplificado
└── ENTREGA_FINAL.md         # Documento de entrega final
```

## 🎯 Como Usar o Chatbot

### 1. Interface Principal
- **Nova Conversa**: Clique no botão "Nova Conversa" na sidebar para iniciar um novo tópico.
- **Enviar Mensagem**: Digite sua pergunta no campo de entrada e pressione `Enter` ou clique no botão de envio.
- **Navegar Conversas**: Clique em qualquer item na sidebar para alternar entre conversas anteriores.

### 2. Tipos de Consultas e Exemplos

O orquestrador de IA classifica automaticamente suas perguntas para direcioná-las ao agente mais adequado:

#### 📊 Consultas SQL (Para Dados Específicos e Relatórios)
Use para perguntas que exigem números, métricas, agregações ou dados tabulares.
```
"Qual foi a receita total do último trimestre?"
"Quantos funcionários temos por departamento?"
"Mostre os top 10 clientes por faturamento no ano passado"
"Qual a utilização de recursos em 2024?"
"Como está o SLA dos tickets abertos?"
```

#### 🧠 Consultas RAG (Para Informações Conceituais e Insights)
Use para perguntas que buscam explicações, resumos, insights ou informações textuais de documentos.
```
"Como funciona nosso Data Warehouse?"
"Explique a estrutura organizacional da empresa"
"Quais tecnologias utilizamos nos projetos de IA?"
"O que são os KPIs que monitoramos e por que são importantes?"
"Descreva o processo de onboarding de novos clientes."
```

#### 💬 Conversas Gerais
Para interações casuais ou perguntas que não se encaixam nas categorias acima.
```
"Olá, como você pode me ajudar hoje?"
"Obrigado pela informação!"
"Pode me dar mais detalhes sobre isso?"
"Qual é a sua função principal?"
```

### 3. Sistema de Feedback

Ajude a IA a aprender e melhorar:
- **Feedback Positivo (👍)**: Clique para indicar que a resposta foi útil e precisa.
- **Feedback Negativo (👎)**: Clique para indicar que a resposta precisa ser melhorada. Você pode adicionar um comentário explicando o motivo.
- **Comentários**: Forneça texto explicativo para que o sistema possa entender o que deu errado e como melhorar.

## 📈 Metodologia e Execução

### Metodologia

O desenvolvimento seguiu uma abordagem ágil e iterativa, focando na construção de um MVP (Produto Mínimo Viável) funcional e escalável. A arquitetura foi projetada para ser modular, permitindo a fácil adição de novos agentes de IA, fontes de dados e funcionalidades. A prioridade foi dada à experiência do usuário e à capacidade de aprendizado do sistema.

### Execução

1.  **Análise e Planejamento**: Início com a análise dos requisitos do projeto, incluindo a integração com o banco de dados SQLite existente (`analytical_company.db`) e a necessidade de um chatbot com capacidades de SQL e RAG. Definição da arquitetura de microsserviços com Flask para o backend e uma interface web moderna.
2.  **Configuração do Ambiente**: Criação de um ambiente de desenvolvimento isolado com Python e instalação das dependências essenciais (Flask, SQLAlchemy, ChromaDB, Ollama, etc.).
3.  **Desenvolvimento do Backend**: Implementação das rotas da API com Flask, modelos de dados com SQLAlchemy para gerenciar chats e mensagens, e integração com o banco de dados `analytical_company.db` para consultas de dados.
4.  **Implementação da IA**: Desenvolvimento do `AIOrchestrator` para classificar as intenções do usuário. Criação do `SQLAgent` para traduzir linguagem natural em SQL e executar consultas, e do `RAGAgent` para buscar informações contextuais em uma base de conhecimento vetorial (ChromaDB) alimentada por embeddings.
5.  **Construção do Frontend**: Desenvolvimento da interface do usuário com HTML, CSS e JavaScript. Foco em um design elegante, responsivo e com animações para uma experiência de usuário fluida. Implementação da lógica de interação, exibição de mensagens e gerenciamento de chats.
6.  **Sistema de Aprendizado Contínuo**: Integração de um módulo de aprendizado (`LearningSystem`) para analisar padrões de consulta, processar feedback do usuário e otimizar as respostas da IA ao longo do tempo. Isso inclui o registro de analytics e a capacidade de melhorar a classificação das perguntas.
7.  **Testes e Refinamento**: Testes exaustivos de todas as funcionalidades, incluindo a integração entre frontend e backend, a precisão das respostas da IA (SQL e RAG), a persistência do histórico de conversas e a responsividade da interface. Ajustes finos de performance e usabilidade.

## 📊 Resultados e Discussão

### Resultados Alcançados

O projeto resultou em um chatbot de IA generativa robusto e funcional, capaz de:

-   **Interpretar e Responder a Consultas Complexas**: A IA consegue entender perguntas em linguagem natural e fornecer respostas precisas, seja através de dados SQL ou informações contextuais do RAG.
-   **Experiência de Usuário Aprimorada**: A interface moderna e responsiva, combinada com animações e feedback visual, oferece uma experiência de usuário intuitiva e agradável.
-   **Sistema de Aprendizado Efetivo**: O módulo de aprendizado contínuo permite que a IA se adapte e melhore suas respostas com base nas interações e no feedback dos usuários, tornando-a mais inteligente ao longo do tempo.
-   **Modularidade e Escalabilidade**: A arquitetura do projeto facilita a adição de novas funcionalidades, agentes de IA ou fontes de dados no futuro.
-   **Integração com Ollama**: A capacidade de usar LLMs locais oferece flexibilidade e controle sobre os modelos de IA, ideal para ambientes corporativos com requisitos de privacidade.

### Discussão e Próximos Passos

Este projeto demonstra o potencial da IA generativa para transformar a interação com dados empresariais. A combinação de SQL e RAG, orquestrada por um sistema inteligente, abre portas para automação e insights em larga escala. Embora o projeto seja funcional, há sempre espaço para melhorias:

-   **Expansão da Base de Conhecimento**: Adicionar mais documentos e informações ao banco vetorial para enriquecer as respostas RAG.
-   **Otimização de Modelos Ollama**: Experimentar diferentes modelos Ollama e ajustar seus parâmetros para otimizar a performance e a precisão.
-   **Integração com Outras Fontes de Dados**: Conectar o chatbot a outras fontes de dados (APIs, Data Lakes, ERPs) para expandir suas capacidades.
-   **Recursos de Visualização**: Implementar a capacidade de gerar gráficos e visualizações diretamente no chat para dados SQL.
-   **Aprimoramento do Aprendizado**: Desenvolver algoritmos de aprendizado mais sofisticados para um refinamento ainda maior das respostas.

## 🚀 Deploy e Produção

Para preparar a aplicação para um ambiente de produção, siga estas diretrizes:

### Preparação para Deploy
```bash
# Atualizar dependências (garante que todas as libs estão no requirements.txt)
pip freeze > requirements.txt

# Verificar a estrutura da aplicação Flask
python -c "from src.main import app; print(\'App OK\')"
```

### Variáveis de Ambiente
Defina as variáveis de ambiente necessárias para o Flask e o Ollama:
```bash
export FLASK_ENV=production
export OLLAMA_HOST=localhost:11434 # Ou o endereço do seu servidor Ollama
```

### Deploy com Gunicorn (Recomendado para Produção)
Para um deploy robusto, utilize um servidor WSGI como Gunicorn:
```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 src.main:app
```

## 🔍 Troubleshooting (Solução de Problemas Comuns)

### Ollama não conecta
```bash
# Verificar se Ollama está rodando
ollama list

# Iniciar Ollama se necessário
ollama serve
```

### Erro de dependências
```bash
# Reinstalar dependências (pode resolver problemas de versão)
pip install -r requirements.txt --force-reinstall
```

### Banco de dados corrompido
```bash
# Recriar banco da aplicação (apenas para app.db e learning.db)
# Isso apagará o histórico de conversas e aprendizado!
rm src/database/app.db
rm src/database/learning.db
python src/main.py  # Recria automaticamente na inicialização
```

### Performance lenta
- **Verificar RAM disponível**: Mínimo de 4GB, mas 8GB+ é altamente recomendado para LLMs.
- **Usar modelo Ollama menor**: Modelos como `llama3.2:1b` são mais leves.
- **Limpar dados antigos**: Use a API `POST /api/optimize` para limpar dados de aprendizado antigos.

### Logs e Debug
```bash
# Executar em modo debug (para desenvolvimento)
export FLASK_DEBUG=1
python src/main.py
```

## 🤝 Contribuição

Sinta-se à vontade para contribuir com este projeto! As principais áreas de desenvolvimento incluem:
1.  **Backend (`src/ai/`, `src/routes/`, `src/models/`)**: Adicionar novas funcionalidades de IA, otimizar agentes, expandir a API.
2.  **Frontend (`src/static/`)**: Melhorar a interface do usuário, adicionar novos componentes, otimizar a experiência.
3.  **Dados (`src/utils/database_query.py`, `src/database/`)**: Expandir as queries pré-definidas, integrar novas fontes de dados.
4.  **Aprendizado (`src/ai/learning_system.py`)**: Otimizar algoritmos de aprendizado, adicionar novas métricas.

### Boas Práticas
-   Siga os padrões de código PEP 8 para Python.
-   Documente novas funções e classes.
-   Realize testes locais antes de submeter alterações.
-   Mantenha a compatibilidade com as versões mais recentes do Ollama.

## 📄 Licença

Este projeto foi desenvolvido por Vinicius Santos para fins de demonstração e aplicação prática de conceitos de IA Generativa. É um trabalho de código aberto e pode ser utilizado e modificado livremente, desde que a atribuição original seja mantida.

## 📞 Contato e Sobre o Autor

**Desenvolvido por:**

**Vinicius Santos**

-   **Email**: vinicius.santos@ifsp.edu.br

---

**Obrigado por explorar o IA-Assistente!**

*Seu assistente de IA está pronto para revolucionar sua análise de dados!* 🚀

