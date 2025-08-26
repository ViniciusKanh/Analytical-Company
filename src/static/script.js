// Estado global da aplicação
const AppState = {
    currentChatId: null,
    chats: [],
    isLoading: false,
    isSidebarOpen: false
};

// Elementos DOM
const elements = {
    sidebar: document.getElementById('sidebar'),
    sidebarToggle: document.getElementById('sidebarToggle'),
    newChatBtn: document.getElementById('newChatBtn'),
    chatItems: document.getElementById('chatItems'),
    chatMessages: document.getElementById('chatMessages'),
    messageInput: document.getElementById('messageInput'),
    sendButton: document.getElementById('sendButton'),
    typingIndicator: document.getElementById('typingIndicator'),
    loadingOverlay: document.getElementById('loadingOverlay'),
    toastContainer: document.getElementById('toastContainer'),
    currentChatTitle: document.getElementById('currentChatTitle'),
    currentChatSubtitle: document.getElementById('currentChatSubtitle'),
    clearChatBtn: document.getElementById('clearChatBtn'),
    aiStatus: document.getElementById('aiStatus')
};

// API Base URL
const API_BASE = '/api';

// Inicialização da aplicação
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
    setupEventListeners();
    loadChats();
});

// Inicializar aplicação
function initializeApp() {
    // Auto-resize do textarea
    autoResizeTextarea();
    
    // Verificar status da IA
    checkAIStatus();
    
    // Criar primeiro chat se não houver nenhum
    setTimeout(() => {
        if (AppState.chats.length === 0) {
            createNewChat();
        }
    }, 1000);
}

// Configurar event listeners
function setupEventListeners() {
    // Sidebar toggle
    elements.sidebarToggle.addEventListener('click', toggleSidebar);
    
    // Novo chat
    elements.newChatBtn.addEventListener('click', createNewChat);
    
    // Input de mensagem
    elements.messageInput.addEventListener('input', handleInputChange);
    elements.messageInput.addEventListener('keydown', handleKeyDown);
    
    // Botão de enviar
    elements.sendButton.addEventListener('click', sendMessage);
    
    // Limpar chat
    elements.clearChatBtn.addEventListener('click', clearCurrentChat);
    
    // Fechar sidebar ao clicar fora (mobile)
    document.addEventListener('click', function(e) {
        if (window.innerWidth <= 768 && 
            AppState.isSidebarOpen && 
            !elements.sidebar.contains(e.target) && 
            !elements.sidebarToggle.contains(e.target)) {
            closeSidebar();
        }
    });
    
    // Responsividade
    window.addEventListener('resize', handleResize);
}

// Toggle sidebar
function toggleSidebar() {
    if (AppState.isSidebarOpen) {
        closeSidebar();
    } else {
        openSidebar();
    }
}

function openSidebar() {
    elements.sidebar.classList.add('open');
    AppState.isSidebarOpen = true;
}

function closeSidebar() {
    elements.sidebar.classList.remove('open');
    AppState.isSidebarOpen = false;
}

// Auto-resize textarea
function autoResizeTextarea() {
    elements.messageInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        
        // Atualizar contador de caracteres
        const charCount = this.value.length;
        const charCountElement = document.querySelector('.char-count');
        if (charCountElement) {
            charCountElement.textContent = `${charCount}/2000`;
        }
    });
}

// Manipular mudanças no input
function handleInputChange() {
    const hasText = elements.messageInput.value.trim().length > 0;
    elements.sendButton.disabled = !hasText || AppState.isLoading;
}

// Manipular teclas
function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        if (!elements.sendButton.disabled) {
            sendMessage();
        }
    }
}

// Verificar status da IA
async function checkAIStatus() {
    try {
        // Simular verificação de status
        elements.aiStatus.innerHTML = '<i class="fas fa-circle status-online"></i> IA Online';
    } catch (error) {
        elements.aiStatus.innerHTML = '<i class="fas fa-circle status-offline"></i> IA Offline';
        elements.aiStatus.style.color = 'var(--accent-red)';
    }
}

// Carregar lista de chats
async function loadChats() {
    try {
        const response = await fetch(`${API_BASE}/chats`);
        const data = await response.json();
        
        if (data.success) {
            AppState.chats = data.chats;
            renderChatList();
            
            // Selecionar primeiro chat se houver
            if (AppState.chats.length > 0 && !AppState.currentChatId) {
                selectChat(AppState.chats[0].id);
            }
        }
    } catch (error) {
        console.error('Erro ao carregar chats:', error);
        showToast('Erro ao carregar conversas', 'error');
    }
}

// Renderizar lista de chats
function renderChatList() {
    elements.chatItems.innerHTML = '';
    
    AppState.chats.forEach(chat => {
        const chatElement = createChatElement(chat);
        elements.chatItems.appendChild(chatElement);
    });
}

// Criar elemento de chat
function createChatElement(chat) {
    const div = document.createElement('div');
    div.className = `chat-item ${chat.id === AppState.currentChatId ? 'active' : ''}`;
    div.onclick = () => selectChat(chat.id);
    
    const createdAt = new Date(chat.created_at);
    const timeString = formatTime(createdAt);
    
    div.innerHTML = `
        <div class="chat-item-title">${chat.title}</div>
        <div class="chat-item-preview">${chat.message_count} mensagens</div>
        <div class="chat-item-time">${timeString}</div>
    `;
    
    return div;
}

// Formatar tempo
function formatTime(date) {
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'Agora';
    if (minutes < 60) return `${minutes}m`;
    if (hours < 24) return `${hours}h`;
    if (days < 7) return `${days}d`;
    
    return date.toLocaleDateString('pt-BR');
}

// Selecionar chat
async function selectChat(chatId) {
    if (AppState.currentChatId === chatId) return;
    
    AppState.currentChatId = chatId;
    
    // Atualizar UI
    updateChatSelection();
    
    // Carregar mensagens
    await loadChatMessages(chatId);
}

// Atualizar seleção de chat
function updateChatSelection() {
    document.querySelectorAll('.chat-item').forEach(item => {
        item.classList.remove('active');
    });
    
    const activeChat = AppState.chats.find(chat => chat.id === AppState.currentChatId);
    if (activeChat) {
        const chatElement = document.querySelector(`[onclick="selectChat(${activeChat.id})"]`);
        if (chatElement) {
            chatElement.classList.add('active');
        }
        
        // Atualizar título
        elements.currentChatTitle.textContent = activeChat.title;
        elements.currentChatSubtitle.textContent = `${activeChat.message_count} mensagens • Criado em ${formatTime(new Date(activeChat.created_at))}`;
    }
}

// Carregar mensagens do chat
async function loadChatMessages(chatId) {
    try {
        showLoading();
        
        const response = await fetch(`${API_BASE}/chats/${chatId}`);
        const data = await response.json();
        
        if (data.success) {
            renderMessages(data.messages);
        } else {
            showToast('Erro ao carregar mensagens', 'error');
        }
    } catch (error) {
        console.error('Erro ao carregar mensagens:', error);
        showToast('Erro ao carregar mensagens', 'error');
    } finally {
        hideLoading();
    }
}

// Renderizar mensagens
function renderMessages(messages) {
    // Limpar mensagens existentes (exceto welcome message)
    const welcomeMessage = elements.chatMessages.querySelector('.welcome-message');
    elements.chatMessages.innerHTML = '';
    
    if (messages.length === 0 && welcomeMessage) {
        elements.chatMessages.appendChild(welcomeMessage);
    } else {
        messages.forEach(message => {
            const messageElement = createMessageElement(message);
            elements.chatMessages.appendChild(messageElement);
        });
    }
    
    scrollToBottom();
}

// Criar elemento de mensagem
function createMessageElement(message) {
    const div = document.createElement('div');
    div.className = `message ${message.role}-message`;
    
    const avatar = message.role === 'user' 
        ? '<i class="fas fa-user"></i>' 
        : '<i class="fas fa-robot"></i>';
    
    div.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="message-text">${formatMessageContent(message.content)}</div>
            ${message.query_type ? `<div class="message-meta">Tipo: ${message.query_type} • ${message.execution_time?.toFixed(2)}s</div>` : ''}
        </div>
    `;
    
    return div;
}

// Formatar conteúdo da mensagem
function formatMessageContent(content) {
    // Converter quebras de linha
    content = content.replace(/\n/g, '<br>');
    
    // Destacar código SQL
    content = content.replace(/```sql\n?([\s\S]*?)```/g, '<pre class="sql-code">$1</pre>');
    
    // Destacar código genérico
    content = content.replace(/```\n?([\s\S]*?)```/g, '<pre class="code-block">$1</pre>');
    
    // Destacar texto em negrito
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    // Destacar texto em itálico
    content = content.replace(/\*(.*?)\*/g, '<em>$1</em>');
    
    return content;
}

// Criar novo chat
async function createNewChat() {
    try {
        showLoading();
        
        const response = await fetch(`${API_BASE}/chats`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                title: 'Nova Conversa'
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            AppState.chats.unshift(data.chat);
            renderChatList();
            selectChat(data.chat.id);
            showToast('Nova conversa criada!', 'success');
        } else {
            showToast('Erro ao criar conversa', 'error');
        }
    } catch (error) {
        console.error('Erro ao criar chat:', error);
        showToast('Erro ao criar conversa', 'error');
    } finally {
        hideLoading();
    }
}

// Enviar mensagem
async function sendMessage() {
    const content = elements.messageInput.value.trim();
    if (!content || AppState.isLoading) return;
    
    // Verificar se há chat selecionado
    if (!AppState.currentChatId) {
        await createNewChat();
        if (!AppState.currentChatId) return;
    }
    
    try {
        AppState.isLoading = true;
        elements.sendButton.disabled = true;
        
        // Adicionar mensagem do usuário à UI
        const userMessage = {
            role: 'user',
            content: content,
            timestamp: new Date().toISOString()
        };
        
        const userMessageElement = createMessageElement(userMessage);
        elements.chatMessages.appendChild(userMessageElement);
        
        // Limpar input
        elements.messageInput.value = '';
        elements.messageInput.style.height = 'auto';
        
        // Mostrar indicador de digitação
        showTypingIndicator();
        
        scrollToBottom();
        
        // Enviar para API
        const response = await fetch(`${API_BASE}/chats/${AppState.currentChatId}/messages`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                content: content
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Remover indicador de digitação
            hideTypingIndicator();
            
            // Adicionar resposta do assistente
            const assistantMessageElement = createMessageElement(data.assistant_message);
            elements.chatMessages.appendChild(assistantMessageElement);
            
            // Atualizar informações do chat
            const chatIndex = AppState.chats.findIndex(chat => chat.id === AppState.currentChatId);
            if (chatIndex !== -1) {
                AppState.chats[chatIndex] = data.chat;
                updateChatSelection();
                renderChatList();
            }
            
            scrollToBottom();
            
        } else {
            hideTypingIndicator();
            
            if (data.limit_reached) {
                showToast('Limite de mensagens atingido. Criando nova conversa...', 'error');
                setTimeout(() => createNewChat(), 2000);
            } else {
                showToast(data.error || 'Erro ao enviar mensagem', 'error');
            }
        }
        
    } catch (error) {
        console.error('Erro ao enviar mensagem:', error);
        hideTypingIndicator();
        showToast('Erro ao enviar mensagem', 'error');
    } finally {
        AppState.isLoading = false;
        elements.sendButton.disabled = false;
        handleInputChange(); // Revalidar estado do botão
    }
}

// Mostrar indicador de digitação
function showTypingIndicator() {
    elements.typingIndicator.style.display = 'block';
    scrollToBottom();
}

// Esconder indicador de digitação
function hideTypingIndicator() {
    elements.typingIndicator.style.display = 'none';
}

// Limpar chat atual
async function clearCurrentChat() {
    if (!AppState.currentChatId) return;
    
    if (!confirm('Tem certeza que deseja excluir esta conversa?')) return;
    
    try {
        showLoading();
        
        const response = await fetch(`${API_BASE}/chats/${AppState.currentChatId}`, {
            method: 'DELETE'
        });
        
        const data = await response.json();
        
        if (data.success) {
            // Remover chat da lista
            AppState.chats = AppState.chats.filter(chat => chat.id !== AppState.currentChatId);
            AppState.currentChatId = null;
            
            renderChatList();
            elements.chatMessages.innerHTML = '';
            
            // Selecionar outro chat ou criar novo
            if (AppState.chats.length > 0) {
                selectChat(AppState.chats[0].id);
            } else {
                createNewChat();
            }
            
            showToast('Conversa excluída', 'success');
        } else {
            showToast('Erro ao excluir conversa', 'error');
        }
    } catch (error) {
        console.error('Erro ao excluir chat:', error);
        showToast('Erro ao excluir conversa', 'error');
    } finally {
        hideLoading();
    }
}

// Scroll para o final
function scrollToBottom() {
    setTimeout(() => {
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }, 100);
}

// Mostrar loading
function showLoading() {
    elements.loadingOverlay.style.display = 'flex';
}

// Esconder loading
function hideLoading() {
    elements.loadingOverlay.style.display = 'none';
}

// Mostrar toast
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    elements.toastContainer.appendChild(toast);
    
    // Remover após 3 segundos
    setTimeout(() => {
        toast.remove();
    }, 3000);
}

// Manipular redimensionamento
function handleResize() {
    if (window.innerWidth > 768) {
        elements.sidebar.classList.remove('open');
        AppState.isSidebarOpen = false;
    }
}

// Utilitários
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Adicionar estilos CSS para elementos criados dinamicamente
const additionalStyles = `
.message-meta {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 8px;
    padding-top: 8px;
    border-top: 1px solid var(--border-color);
}

.sql-code {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    overflow-x: auto;
    color: var(--accent-blue);
}

.code-block {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    padding: 12px;
    margin: 8px 0;
    font-family: 'Courier New', monospace;
    font-size: 13px;
    overflow-x: auto;
}

.status-offline {
    color: var(--accent-red) !important;
}
`;

// Adicionar estilos ao documento
const styleSheet = document.createElement('style');
styleSheet.textContent = additionalStyles;
document.head.appendChild(styleSheet);

