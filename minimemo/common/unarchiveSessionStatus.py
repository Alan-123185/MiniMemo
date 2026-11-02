import datetime

from pydantic import BaseModel


class unarchiveSessionStatus(BaseModel):
    session:str
    count:int
    the_latest_create_time:datetime.datetime
