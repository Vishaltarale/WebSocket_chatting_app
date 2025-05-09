from fastapi import FastAPI,Request,Form,Query,Depends,WebSocket
from fastapi.responses import HTMLResponse,RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
import re
from models import UserRegister,get_user_form,userlogin,make_userlogin
from bson import ObjectId  
from starlette.middleware.sessions import SessionMiddleware    #for importing middleware step1
import bcrypt
import json
from typing import List, Dict, Any, Optional


client = MongoClient("mongodb+srv://vishal:11223344@cluster0.ostbq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
db = client['fastapidb']
collection = db["fastapi_collection"]

app=FastAPI()

#step2 add_middleware to ur project within that pass 2 parameters 1 sessionmiddleware and 2 our projects secrete key
app.add_middleware(SessionMiddleware, secret_key="your-secret-key")

app.mount('/static',StaticFiles(directory='static'),name='static')
templates = Jinja2Templates(directory='templates')

@app.get('/')
async def home(request:Request):
    return templates.TemplateResponse("index.html",{'request':request})


@app.post("/register")
async def reg(request:Request,user: UserRegister = Depends(get_user_form)):
    if user.password != user.repassword:
        return RedirectResponse("/", status_code=302)

    existing_user = collection.find_one({"email": user.email})
    if existing_user:
        return {"error": f"{user.email} already exists"}

    hashed_pw = bcrypt.hashpw(user.password.encode("utf-8"), bcrypt.gensalt())
    collection.insert_one({
        "email": user.email,
        "password": hashed_pw,
        "repassword": hashed_pw,
        "country": user.country
    })
    request.session['flash'] = "Registered successfull"
    return RedirectResponse("/login", status_code=302)
    
@app.get('/login')
async def login(request:Request):
    if request.session.get("email") is None:
        flashmsg = request.session.pop("flash",None)
        return templates.TemplateResponse("login.html",{'request':request,"flash":flashmsg})
    else:
        return RedirectResponse("/dashboard",status_code=302)
    
@app.post("/login_check")
async def login_check(request: Request, user: userlogin = Depends(make_userlogin)):
    data = collection.find_one({'email': user.email})
    if not data:
        return RedirectResponse(url="/login", status_code=302)

    # Check if password is stored as string and convert it to bytes if needed
    stored_password = data['password']
    if isinstance(stored_password, str):
        stored_password = stored_password.encode('utf-8')
        
    # Now compare the passwords
    if not bcrypt.checkpw(user.password.encode('utf-8'), stored_password):
        return RedirectResponse(url="/login", status_code=302)

    request.session['email'] = user.email
    request.session['flash'] = "login successful"
    return RedirectResponse(url="/dashboard", status_code=302)
    
@app.get('/dashboard')
async def dashboard(request:Request):
    if request.session.get('email') is not None:
        flash_msg = request.session.pop("flash",None)
        return templates.TemplateResponse('dashboard.html',{'request':request,"flash":flash_msg})
    else:
        return RedirectResponse(url="/login",status_code=302)

@app.get('/userdata')
async def dashboard(request:Request):
        flashmsg = request.session.pop("flash",None)
        data = collection.find()
        return templates.TemplateResponse('user.html',{'request':request,'data':data,'flash':flashmsg})

@app.get("/logout")
async def logout(request:Request):
    request.session.clear()
    request.session["flash"] = "Logout Successfully"
    return RedirectResponse(url="/login",status_code=302)

@app.get("/edit", response_class=HTMLResponse)
async def edit(request: Request, id: str = Query(...)):
    data = collection.find_one({"_id": ObjectId(id)})
    return templates.TemplateResponse("useredit.html", {"request": request, "data": data})

@app.post("/useredit")
async def update_user(request:Request,id: str = Form(...), email: str = Form(...), password: str = Form(...), repassword: str = Form(...), country: str = Form(...)):
    collection.update_one(
        {"_id": ObjectId(id)},
        {"$set": {
            "email": email,
            "password": password,
            "repassword": repassword,
            "country": country
        }}
    )
    request.session['flash'] = "User edited successfully"
    return RedirectResponse(url="/userdata", status_code=302)

@app.get('/delete')
async def delete(id:str=Query(...)):
    collection.delete_one({'_id':ObjectId(id)})
    return RedirectResponse(url="/userdata", status_code=302)

@app.get('/profile')
async def profile(request: Request):
    # Get email from session
    user_email = request.session.get("email")
    
    # If no user is logged in, redirect to login
    if not user_email:
        return RedirectResponse(url="/login", status_code=303)
    
    # Find the user document from MongoDB
    user_data = collection.find_one({'email': user_email})
    
    # Convert MongoDB document to regular dict (to avoid ObjectId serialization issues)
    if user_data:
        user_data = dict(user_data)
        # Remove _id field or convert it to string if needed
        if '_id' in user_data:
            user_data['_id'] = str(user_data['_id'])
    
    return templates.TemplateResponse("profile.html", {'request': request, 'user_data': user_data})


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.user_names: Dict[str, str] = {}  # Map WebSocket to username
    
    async def connect(self, websocket: WebSocket, username: str = "Guest"):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_names[websocket] = username

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            username = self.user_names.get(websocket, "Guest")
            self.active_connections.remove(websocket)
            del self.user_names[websocket]
            return username
        return None
    
    def get_username(self, websocket: WebSocket) -> str:
        return self.user_names.get(websocket, "Guest")
    
    def update_username(self, websocket: WebSocket, username: str):
        self.user_names[websocket] = username
    
    def get_all_usernames(self) -> List[str]:
        return list(self.user_names.values())
    
    async def broadcast(self, message: Any, exclude: Optional[WebSocket] = None):
        for connection in self.active_connections:
            if connection != exclude:
                await connection.send_text(json.dumps(message) if isinstance(message, dict) else str(message))

manager = ConnectionManager()

@app.post("/search", response_class=HTMLResponse)
async def search(request: Request, term: str = Form(...)):
    if term:
        data = list(collection.find({
            "$or": [
                {"email": {"$regex": term, "$options": "i"}},
                {"country": {"$regex": term, "$options": "i"}}
            ]
        }))
    else:
        data = list(collection.find())
    
    return templates.TemplateResponse("user.html", {"request": request, "data": data, "term": term})

@app.get("/chat", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("homepage.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
  
    # Accept connection
    await manager.connect(websocket)
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_text()
            
            try:
                message_data = json.loads(data)
                message_type = message_data.get("type", "chat_message")
                
                if message_type == "user_joined":
                    username = message_data.get("username", "Guest")
                    manager.update_username(websocket, username)
                    # Notify others about new user
                    await manager.broadcast({
                        "type": "user_joined",
                        "username": username,
                        "active_users": manager.get_all_usernames()
                    }, exclude=websocket)
                    
                elif message_type == "chat_message":
                    username = message_data.get("username", manager.get_username(websocket))
                    message_content = message_data.get("message", "")
                    # Broadcast message to all clientsu
                    
                    await manager.broadcast({
                        "type": "chat_message",
                        "username": username,
                        "message": message_content
                    })
                    
                elif message_type == "typing":
                    username = message_data.get("username", manager.get_username(websocket))
                    # Broadcast typing indicator
                    await manager.broadcast({
                        "type": "typing",
                        "username": username
                    }, exclude=websocket)
            
            except json.JSONDecodeError:
                # Fallback to plain text for backward compatibility
                await manager.broadcast(data)
    
    except Exception:
        # Handle disconnection
        username = manager.disconnect(websocket)
        if username:
            await manager.broadcast(f"Disconnected {username}")
            
            