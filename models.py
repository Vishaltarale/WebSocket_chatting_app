from fastapi import Form, Depends
from pydantic import BaseModel, EmailStr, constr

class UserRegister(BaseModel):
    email: EmailStr
    password: str
    repassword: str
    country: str

# Extract form data and validate using Pydantic
def get_user_form(
    email: str = Form(...),
    password: str = Form(...),
    repassword: str = Form(...),
    country: str = Form(...)
) -> UserRegister:
    return UserRegister(email=email, password=password, repassword=repassword, country=country)

class userlogin(BaseModel):
    email:EmailStr
    password : str

def make_userlogin(email:str=Form(...),
                   password:str=Form(...)
                   ) -> userlogin:
    return userlogin(email=email,password=password)