from loguru import logger
from sqlalchemy.orm import Session
from minimemo.models.session import Session as SessionModel


class sessionRepository:
    def __init__(self, session: Session):
        self.session = session


    def register_session(self, agent_id: str, session_id: str) -> None:
        """
        把一个会话注册到指定智能体下，会话id由调用方传入
        """
        existing_session = self.session.query(SessionModel).filter_by(
            agent_id=agent_id, session_id=session_id
        ).first()
        if existing_session:
            logger.info(f"Session with session_id {session_id} already exists. Skipping registration.")
            return

        self.session.add(SessionModel(agent_id=agent_id, session_id=session_id))
        self.session.commit()
