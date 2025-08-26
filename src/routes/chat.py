# src/routes/chat.py
from flask import Blueprint, request, jsonify
from datetime import datetime
import time

from src.models.user import db
from src.models.chat import Chat, Message, ChatFeedback
from src.ai.orchestrator import AIOrchestrator

chat_bp = Blueprint("chat", __name__)
# Dica: no app principal, registre com url_prefix="/api"
# app.register_blueprint(chat_bp, url_prefix="/api")

# Inicializa o orquestrador (ajuste debug conforme seu ambiente)
ai_orchestrator = AIOrchestrator()


# ---------------------------
# Helpers de serialização
# ---------------------------
def _message_public_dict(m: Message) -> dict:
    """
    Converte uma Message para um dicionário "público",
    ocultando SQL/tempo/tipo para o frontend.
    """
    return {
        "id": m.id,
        "chat_id": m.chat_id,
        "role": m.role,
        "content": m.content,
        "timestamp": m.timestamp.isoformat() if hasattr(m, "timestamp") and m.timestamp else None,
    }


def _messages_public_list(messages) -> list:
    return [_message_public_dict(m) for m in messages]


# ---------------------------
# Rotas de Chat
# ---------------------------
@chat_bp.route("/chats", methods=["GET"])
def get_chats():
    """Listar todos os chats (somente cabeçalho do chat)."""
    try:
        chats = Chat.query.order_by(Chat.updated_at.desc()).all()
        return jsonify({"success": True, "chats": [chat.to_dict() for chat in chats]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/chats", methods=["POST"])
def create_chat():
    """Criar um novo chat."""
    try:
        data = request.get_json(silent=True) or {}
        title = (data.get("title") or "Nova Conversa").strip()

        chat = Chat(title=title)
        db.session.add(chat)
        db.session.commit()

        return jsonify({"success": True, "chat": chat.to_dict()}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/chats/<int:chat_id>", methods=["GET"])
def get_chat(chat_id: int):
    """Obter um chat específico com suas mensagens (sanitizadas)."""
    try:
        chat = Chat.query.get_or_404(chat_id)
        messages = (
            Message.query.filter_by(chat_id=chat_id)
            .order_by(Message.timestamp.asc())
            .all()
        )

        return jsonify(
            {
                "success": True,
                "chat": chat.to_dict(),
                # <<< IMPORTANTE: mensagens sem sql_query/query_type/execution_time >>>
                "messages": _messages_public_list(messages),
            }
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/chats/<int:chat_id>", methods=["DELETE"])
def delete_chat(chat_id: int):
    """Deletar um chat."""
    try:
        chat = Chat.query.get_or_404(chat_id)
        db.session.delete(chat)
        db.session.commit()
        return jsonify({"success": True, "message": "Chat deletado com sucesso"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/chats/<int:chat_id>/messages", methods=["POST"])
def send_message(chat_id: int):
    """
    Enviar uma mensagem para o chat.
    - Salva a mensagem do usuário e a resposta do assistente.
    - Chama o orquestrador.
    - Retorna SOMENTE conteúdo público (sem SQL).
    """
    try:
        data = request.get_json(force=True) or {}
        content = (data.get("content") or "").strip()

        if not content:
            return (
                jsonify({"success": False, "error": "Conteúdo da mensagem é obrigatório"}),
                400,
            )

        chat = Chat.query.get_or_404(chat_id)

        # Limite de mensagens por chat (2*10 = 20: usuário + assistente)
        if (chat.message_count or 0) >= 20:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "Limite de mensagens atingido. Crie um novo chat.",
                        "limit_reached": True,
                    }
                ),
                400,
            )

        # 1) Salvar mensagem do usuário
        user_message = Message(chat_id=chat_id, content=content, role="user")
        db.session.add(user_message)
        chat.message_count = (chat.message_count or 0) + 1
        chat.updated_at = datetime.utcnow()

        # 2) Montar histórico para contexto do orquestrador
        chat_history = (
            Message.query.filter_by(chat_id=chat_id)
            .order_by(Message.timestamp.asc())
            .all()
        )
        history_list = [m.to_dict() for m in chat_history]  # mantém contexto completo para a IA

        # 3) Processar com IA
        start_time = time.time()
        try:
            result = ai_orchestrator.process_query(content, history_list)
        except Exception as e:
            # Fallback simples de erro
            result = {
                "response": f"Desculpe, ocorreu um erro ao processar sua solicitação: {str(e)}"
            }

        # Compatibilidade com diferentes formatos de retorno do orquestrador
        ai_response = (
            result.get("response")
            or result.get("answer")
            or result.get("content")
            or "Não consegui gerar uma resposta no momento."
        )
        metadata = result.get("metadata") or {}
        query_type = result.get("query_type") or metadata.get("query_source") or None
        sql_query = result.get("sql_query")
        exec_time = result.get("execution_time") or (time.time() - start_time)

        # 4) Salvar resposta do assistente (armazenamos SQL/tempo/tipo NO BANCO, mas não expomos)
        assistant_message = Message(
            chat_id=chat_id,
            content=ai_response,
            role="assistant",
            query_type=query_type,
            sql_query=sql_query,
            execution_time=exec_time,
        )
        db.session.add(assistant_message)
        chat.message_count = (chat.message_count or 0) + 1
        db.session.commit()

        # 5) Responder ao frontend com payload "limpo"
        return jsonify(
            {
                "success": True,
                "user_message": _message_public_dict(user_message),
                "assistant_message": _message_public_dict(assistant_message),
                "chat": chat.to_dict(),
            }
        )

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


# ---------------------------
# Feedback e Insights
# ---------------------------
@chat_bp.route("/messages/<int:message_id>/feedback", methods=["POST"])
def add_feedback(message_id: int):
    """Adicionar feedback a uma mensagem (positivo/negativo)."""
    try:
        data = request.get_json(force=True) or {}
        feedback_type = data.get("feedback_type")
        feedback_text = data.get("feedback_text", "")

        if feedback_type not in {"positive", "negative"}:
            return jsonify({"success": False, "error": "Tipo de feedback inválido"}), 400

        message = Message.query.get_or_404(message_id)
        feedback = ChatFeedback(
            message_id=message_id, feedback_type=feedback_type, feedback_text=feedback_text
        )
        db.session.add(feedback)
        db.session.commit()

        # Envia ao sistema de aprendizado (não bloqueante/rápido no seu orquestrador)
        try:
            ai_orchestrator.process_feedback(message_id, feedback_type, feedback_text)
        except Exception:
            pass

        return jsonify({"success": True, "feedback": feedback.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/insights", methods=["GET"])
def get_learning_insights():
    """Obter insights do sistema de aprendizado."""
    try:
        insights = ai_orchestrator.get_learning_insights()
        return jsonify({"success": True, "insights": insights})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@chat_bp.route("/optimize", methods=["POST"])
def optimize_system():
    """Otimizar sistema baseado no aprendizado."""
    try:
        result = ai_orchestrator.optimize_system()
        return jsonify({"success": True, "optimization_result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
