from dataclasses import dataclass


@dataclass
class TalkContext:
    user_id:str
    agent_id:str
    session_id:str
