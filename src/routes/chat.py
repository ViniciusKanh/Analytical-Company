from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from src.models.user import db

class Chat(db.Model):
    __tablename__ = 'chats'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False, default='Nova Conversa')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    message_count = db.Column(db.Integer, default=0)
    
    # Relacionamento com mensagens
    messages = db.relationship('Message', backref='chat', lazy=True, cascade='all, delete-orphan')
    
    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active,
            'message_count': self.message_count
        }

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    chat_id = db.Column(db.Integer, db.ForeignKey('chats.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' ou 'assistant'
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    query_type = db.Column(db.String(20))  # 'sql', 'rag', 'general'
    sql_query = db.Column(db.Text)  # Query SQL executada (se aplicável)
    execution_time = db.Column(db.Float)  # Tempo de execução em segundos
    
    def to_dict(self):
        return {
            'id': self.id,
            'chat_id': self.chat_id,
            'content': self.content,
            'role': self.role,
            'timestamp': self.timestamp.isoformat(),
            'query_type': self.query_type,
            'sql_query': self.sql_query,
            'execution_time': self.execution_time
        }

class ChatFeedback(db.Model):
    __tablename__ = 'chat_feedback'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    feedback_type = db.Column(db.String(20), nullable=False)  # 'positive', 'negative'
    feedback_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'message_id': self.message_id,
            'feedback_type': self.feedback_type,
            'feedback_text': self.feedback_text,
            'created_at': self.created_at.isoformat()
        }

