# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import json
from typing import List, Dict, Any, Optional

# Settings
class Settings:
    PROJECT_NAME = "Interactive Chat Application"
    PROJECT_VERSION = "1.0.0"

settings = Settings()

# Initialize FastAPI
app = FastAPI(title=settings.PROJECT_NAME, version=settings.PROJECT_VERSION)

# Templates
templates = Jinja2Templates(directory="templates")

# Optionally mount static files
# app.mount("/static", StaticFiles(directory="static"), name="static")

# WebSocket connection manager
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

# Routes
@app.get("/", response_class=HTMLResponse)
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
                # Try to parse as JSON
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
                    # Broadcast message to all clients
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
    
    except WebSocketDisconnect:
        # Handle disconnection
        username = manager.disconnect(websocket)
        if username:
            await manager.broadcast({
                "type": "user_left",
                "username": username,
                "active_users": manager.get_all_usernames()
            })