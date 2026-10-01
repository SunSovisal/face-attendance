"""Request and response schemas."""

from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str
     
class AttendanceConfirm(BaseModel):
    match_token: str