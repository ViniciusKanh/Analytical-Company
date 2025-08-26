from flask import Blueprint, request, jsonify
from src.models.user import db
from src.models.chat import Chat, Message, ChatFeedback
from src.ai.orchestrator import AIOrchestrator
from datetime import datetime
import time

chat_bp = Blueprint('chat', __name__)

# Inicializar orquestrador de IA
ai_orchestrator = AIOrchestrator()

@chat_bp.route('/chats', methods=['GET'])
def get_chats():
    """Listar todos os chats"""
    try:
        chats = Chat.query.order_by(Chat.updated_at.desc()).all()
        return jsonify({
            'success': True,
            'chats': [chat.to_dict() for chat in chats]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/chats', methods=['POST'])
def create_chat():
    """Criar um novo chat"""
    try:
        data = request.get_json()
        title = data.get('title', 'Nova Conversa')
        
        chat = Chat(title=title)
        db.session.add(chat)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'chat': chat.to_dict()
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/chats/<int:chat_id>', methods=['GET'])
def get_chat(chat_id):
    """Obter um chat específico com suas mensagens"""
    try:
        chat = Chat.query.get_or_404(chat_id)
        messages = Message.query.filter_by(chat_id=chat_id).order_by(Message.timestamp.asc()).all()
        
        return jsonify({
            'success': True,
            'chat': chat.to_dict(),
            'messages': [message.to_dict() for message in messages]
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/chats/<int:chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """Deletar um chat"""
    try:
        chat = Chat.query.get_or_404(chat_id)
        db.session.delete(chat)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Chat deletado com sucesso'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/chats/<int:chat_id>/messages', methods=['POST'])
def send_message(chat_id):
    """Enviar uma mensagem para o chat"""
    try:
        data = request.get_json()
        content = data.get('content', '').strip()
        
        if not content:
            return jsonify({
                'success': False,
                'error': 'Conteúdo da mensagem é obrigatório'
            }), 400
        
        chat = Chat.query.get_or_404(chat_id)
        
        # Verificar limite de 10 mensagens por chat
        if chat.message_count >= 20:  # 10 do usuário + 10 do assistente
            return jsonify({
                'success': False,
                'error': 'Limite de mensagens atingido. Crie um novo chat.',
                'limit_reached': True
            }), 400
        
        # Salvar mensagem do usuário
        user_message = Message(
            chat_id=chat_id,
            content=content,
            role='user'
        )
        db.session.add(user_message)
        
        # Atualizar contador de mensagens e timestamp do chat
        chat.message_count += 1
        chat.updated_at = datetime.utcnow()
        
        # Obter histórico da conversa para contexto
        chat_history = Message.query.filter_by(chat_id=chat_id).order_by(Message.timestamp.asc()).all()
        history_list = [msg.to_dict() for msg in chat_history]
        
        # Processar com IA
        start_time = time.time()
        
        try:
            ai_result = ai_orchestrator.process_query(content, history_list)
            ai_response = ai_result['response']
            query_type = ai_result['query_type']
            sql_query = ai_result.get('sql_query')
            execution_time = ai_result['execution_time']
        except Exception as e:
            ai_response = f"Desculpe, ocorreu um erro ao processar sua solicitação: {str(e)}"
            query_type = 'error'
            sql_query = None
            execution_time = time.time() - start_time
        
        # Salvar resposta do assistente
        assistant_message = Message(
            chat_id=chat_id,
            content=ai_response,
            role='assistant',
            query_type=query_type,
            sql_query=sql_query,
            execution_time=execution_time
        )
        db.session.add(assistant_message)
        
        chat.message_count += 1
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'user_message': user_message.to_dict(),
            'assistant_message': assistant_message.to_dict(),
            'chat': chat.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/messages/<int:message_id>/feedback', methods=['POST'])
def add_feedback(message_id):
    """Adicionar feedback a uma mensagem"""
    try:
        data = request.get_json()
        feedback_type = data.get('feedback_type')  # 'positive' ou 'negative'
        feedback_text = data.get('feedback_text', '')
        
        if feedback_type not in ['positive', 'negative']:
            return jsonify({
                'success': False,
                'error': 'Tipo de feedback inválido'
            }), 400
        
        message = Message.query.get_or_404(message_id)
        
        feedback = ChatFeedback(
            message_id=message_id,
            feedback_type=feedback_type,
            feedback_text=feedback_text
        )
        db.session.add(feedback)
        db.session.commit()
        
        # Processar feedback no sistema de aprendizado
        ai_orchestrator.process_feedback(message_id, feedback_type, feedback_text)
        
        return jsonify({
            'success': True,
            'feedback': feedback.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500



@chat_bp.route('/insights', methods=['GET'])
def get_learning_insights():
    """Obter insights do sistema de aprendizado"""
    try:
        insights = ai_orchestrator.get_learning_insights()
        return jsonify({
            'success': True,
            'insights': insights
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@chat_bp.route('/optimize', methods=['POST'])
def optimize_system():
    """Otimizar sistema baseado no aprendizado"""
    try:
        result = ai_orchestrator.optimize_system()
        return jsonify({
            'success': True,
            'optimization_result': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
