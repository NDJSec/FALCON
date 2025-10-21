from typing import Optional, List, Dict, Any
import uuid
from sqlalchemy import (
    create_engine,
    Column,
    String,
    Text,
    ForeignKey,
    TIMESTAMP,
    func,
    BigInteger,
    Boolean,
    SmallInteger,
    LargeBinary,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
from sqlalchemy.dialects.postgresql import UUID
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage

from backend import config
from backend.auth_utils import decode_access_token

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(LargeBinary, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(TIMESTAMP, server_default=func.now())

    conversations = relationship("Conversation", backref="user", cascade="all, delete")


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    started_at = Column(TIMESTAMP, server_default=func.now())

    messages = relationship("Message", backref="conversation", cascade="all, delete")


class Message(Base):
    __tablename__ = "messages"
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    feedback = Column(SmallInteger, nullable=True)
    source_ip = Column(String, nullable=True)
    created_at = Column(TIMESTAMP, server_default=func.now())


engine = create_engine(config.DATABASE_URL)
SessionLocal: sessionmaker[Session] = sessionmaker(bind=engine)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def _get_user_from_jwt(jwt_token: str, db: Session) -> Optional[User]:
    try:
        payload = decode_access_token(jwt_token)
        username = payload.get("sub")
        if not username:
            return None
        return db.query(User).filter_by(username=username).first()
    except Exception:
        return None


def is_valid_token(jwt_token: str) -> bool:
    if not jwt_token:
        return False
    with SessionLocal() as session:
        user: Optional[User] = _get_user_from_jwt(jwt_token, session)
        return user is not None and user.is_active


def log_message(
    jwt_token: str,
    conversation_id: Optional[str],
    role: str,
    content: str,
    source_ip: Optional[str] = None,
) -> Optional[str]:
    with SessionLocal() as session:
        user: Optional[User] = _get_user_from_jwt(jwt_token, session)
        if not user or not user.is_active:
            return None

        conversation: Optional[Conversation] = None
        if conversation_id:
            try:
                conv_uuid = uuid.UUID(conversation_id)
                conversation = session.query(Conversation).filter_by(id=conv_uuid).first()
            except (ValueError, TypeError):
                pass

        if not conversation:
            conversation = Conversation(user_id=user.id)
            session.add(conversation)
            session.commit()
            session.refresh(conversation)

        msg = Message(
            conversation_id=conversation.id,
            role=role,
            content=content,
            source_ip=source_ip,
        )
        session.add(msg)
        session.commit()

        return str(conversation.id)


def log_feedback(message_id: int, feedback: int) -> None:
    with SessionLocal() as session:
        session.query(Message).filter(Message.id == message_id).update({"feedback": feedback})
        session.commit()


def load_conversations_for_token(jwt_token: str) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        user: Optional[User] = _get_user_from_jwt(jwt_token, session)
        if not user:
            return []
        conversations = (
            session.query(Conversation)
            .filter_by(user_id=user.id)
            .order_by(Conversation.started_at.desc())
            .all()
        )
        return [{"id": str(c.id), "started_at": c.started_at.isoformat()} for c in conversations]


def load_messages_for_conversation(conversation_id: str) -> List[Dict[str, Any]]:
    with SessionLocal() as session:
        try:
            conv_uuid = uuid.UUID(conversation_id)
            messages: List[Message] = (
                session.query(Message)
                .filter_by(conversation_id=conv_uuid)
                .order_by(Message.created_at.asc())
                .all()
            )
            return [
                {
                    "id": m.id,
                    "role": m.role,
                    "content": m.content,
                    "feedback": m.feedback,
                }
                for m in messages
            ]
        except (ValueError, TypeError):
            return []


def create_new_conversation(jwt_token: str) -> Optional[str]:
    """
    Expects a JWT token string, validates the user, then creates a new conversation.
    """
    with SessionLocal() as session:
        user: Optional[User] = _get_user_from_jwt(jwt_token, session)
        if not user or not user.is_active:
            return None

        conversation = Conversation(user_id=user.id)
        session.add(conversation)
        session.commit()
        session.refresh(conversation)

        return str(conversation.id)


def get_messages_for_history(conversation_id: Optional[str]) -> ChatMessageHistory:
    history = ChatMessageHistory()
    if not conversation_id:
        return history

    messages = load_messages_for_conversation(conversation_id)
    for msg in messages:
        if msg["role"] == "user":
            history.add_message(HumanMessage(content=msg["content"]))
        elif msg["role"].startswith("assistant"):
            history.add_message(AIMessage(content=msg["content"]))
    return history
