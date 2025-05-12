from fastapi import FastAPI, WebSocket, Request
from fastapi.templating import Jinja2Templates
import asyncio

app = FastAPI()
templates = Jinja2Templates(directory="templates")

@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("notification.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    count = 1
    while True:
        if count == 1:
            await asyncio.sleep(2)  # wait 2 seconds 
        else:
            await asyncio.sleep(5)
        await websocket.send_text(f"🔔 Notification {count}")
        count += 1
        
