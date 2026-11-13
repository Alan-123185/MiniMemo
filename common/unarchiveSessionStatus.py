import datetime

from pydantic import BaseModel


class unarchiveSessionStatus(BaseModel):
    session:str
    count:int
    the_latest_create_time:datetime.datetime



class unarchiveAgentStatus(BaseModel):
    agent:str
    count:int
    the_latest_create_time:datetime.datetime