from pydantic import BaseModel


class existFact(BaseModel):
    content:str
    memory_id:str

