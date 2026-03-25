import os
import time
import json
import uuid
import bcrypt
from contextlib import asynccontextmanager

import mysql.connector
import paho.mqtt.client as mqtt
from fastapi import Cookie, Depends, FastAPI, HTTPException, Request, Response, WebSocket
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

def get_db():
    conn = mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
    )
    try:
        yield conn
    finally:
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    for _ in range(30):
        try:
            conn = mysql.connector.connect(
                host=os.environ.get("DB_HOST"),
                user=os.environ.get("DB_USER"),
                password=os.environ.get("DB_PASSWORD"),
                database=os.environ.get("DB_NAME"),
            )
            cursor = conn.cursor()
            with open("init.sql") as f:
                for statement in f.read().split(";"):
                    statement = statement.strip()
                    if statement:
                        cursor.execute(statement)
            conn.commit()
            cursor.close()
            conn.close()
            break
        except mysql.connector.Error:
            time.sleep(1)
    yield

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="static"), name="static")


class UserAuth(BaseModel):
    username: str
    password: str

def get_current_user(session_token: str | None = Cookie(None), conn=Depends(get_db)):
    if not session_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT users.id, users.username FROM sessions "
        "JOIN users ON sessions.user_id = users.id "
        "WHERE sessions.session_token = %s",
        (session_token,),
    )
    user = cursor.fetchone()
    cursor.close()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user

@app.post("/api/register")
def register(user: UserAuth, conn=Depends(get_db)):
    if not user.username or not user.password:
        raise HTTPException(status_code=400, detail="Missing fields")
        
    hashed = bcrypt.hashpw(user.password.encode(), bcrypt.gensalt())
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
            (user.username, hashed.decode()),
        )
        conn.commit()
    except mysql.connector.IntegrityError:
        cursor.close()
        raise HTTPException(status_code=400, detail="Username already exists")
    
    cursor.close()
    return {"status": "success"}

@app.post("/api/login")
def login(user: UserAuth, response: Response, conn=Depends(get_db)):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, password_hash FROM users WHERE username = %s", (user.username,))
    db_user = cursor.fetchone()

    if not db_user or not bcrypt.checkpw(user.password.encode(), db_user["password_hash"].encode()):
        cursor.close()
        raise HTTPException(status_code=401, detail="Invalid username or password")

    session_token = str(uuid.uuid4())
    cursor.execute(
        "INSERT INTO sessions (user_id, session_token) VALUES (%s, %s)",
        (db_user["id"], session_token)
    )
    conn.commit()
    cursor.close()

    response.set_cookie(key="session_token", value=session_token, httponly=True)
    return {"status": "success"}

@app.post("/api/logout")
def logout(response: Response, session_token: str | None = Cookie(None), conn=Depends(get_db)):
    if session_token:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE session_token = %s", (session_token,))
        conn.commit()
        cursor.close()
    response.delete_cookie("session_token")
    return {"status": "success"}


MQTT_BROKER = os.getenv("MQTT_BROKER", "broker.emqx.io")
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "ece140a/ta7/autograder")
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

def on_mqtt_message(client, userdata, msg):
    try:
        payload_str = msg.payload.decode('utf-8')
        if payload_str in ["get_one", "start_continuous", "stop"]:
            return
            
        payload = json.loads(payload_str)
        print(f"Received MQTT Data: {payload['prediction']} ({payload['confidence']})")
        
        # FIXED: Use environ variables here so it dynamically uses 'ta8db' during autograding
        conn = mysql.connector.connect(
            host=os.environ.get("DB_HOST"),
            user=os.environ.get("DB_USER"),
            password=os.environ.get("DB_PASSWORD"),
            database=os.environ.get("DB_NAME"), 
        )
        cursor = conn.cursor()
        
        cursor.execute("INSERT IGNORE INTO devices (mac_address) VALUES (%s)",(payload["mac_address"],))
        cursor.execute(
            """
            INSERT INTO readings (mac_address, thermistor_temp, prediction, confidence, pixels)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (payload["mac_address"], payload["thermistor"], payload["prediction"], payload["confidence"], json.dumps(payload["pixels"]))
        )
        conn.commit()
        cursor.close()
        conn.close()
        
    except json.JSONDecodeError:
        pass
    except Exception as e:
        print(f"Error processing MQTT message: {e}")



mqtt_client.on_message = on_mqtt_message

try:
    mqtt_client.connect(MQTT_BROKER, 1883, 60)
    mqtt_client.subscribe(MQTT_TOPIC)
    print(f"Subscribed to topic: {MQTT_TOPIC}")
    mqtt_client.loop_start()
except Exception as e:
    print(f"MQTT connection failed: {e}")


@app.get("/")
def read_root(session_token: str | None = Cookie(None), conn=Depends(get_db)):
    # Redirect to login if user has no session token
    if not session_token:
        return RedirectResponse(url="/login", status_code=303)
        
    # Verify the token exists in the database
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM sessions WHERE session_token = %s", (session_token,))
    session = cursor.fetchone()
    cursor.close()
    
    if not session:
        return RedirectResponse(url="/login", status_code=303)
        
    with open("static/index.html") as f:
        return HTMLResponse(f.read())

@app.get("/login", response_class=HTMLResponse)
def login_page():
    with open("static/login.html") as f:
        return HTMLResponse(f.read())

@app.get("/register", response_class=HTMLResponse)
def register_page():
    with open("static/register.html") as f:
        return HTMLResponse(f.read())


class Command(BaseModel):
    command: str

@app.post("/api/command")
def send_command(cmd: Command, current_user=Depends(get_current_user)):
    valid_commands = ["get_one", "start_continuous", "stop"]
    if cmd.command not in valid_commands:
        raise HTTPException(status_code=400, detail="Invalid command")
    
    mqtt_client.publish(MQTT_TOPIC, cmd.command)
    return {"status": "success"}

class Reading(BaseModel):
    mac_address: str
    pixels: list[float]
    thermistor: float = 0.0     
    thermistor_temp: float = 0.0 
    prediction: str
    confidence: float

@app.post("/api/readings")
def add_reading(reading: Reading, conn=Depends(get_db), current_user=Depends(get_current_user)):
    cursor = conn.cursor()
    actual_temp = reading.thermistor_temp if reading.thermistor_temp != 0.0 else reading.thermistor
    
    cursor.execute("INSERT IGNORE INTO devices (mac_address) VALUES (%s)", (reading.mac_address,))
    cursor.execute(
        """
        INSERT INTO readings (mac_address, thermistor_temp, prediction, confidence, pixels)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (reading.mac_address, actual_temp, reading.prediction, reading.confidence, json.dumps(reading.pixels))
    )
    
    row_id = cursor.lastrowid
    conn.commit()
    cursor.close()
    return {"id": row_id}

@app.get("/api/readings")
def get_readings(device_mac: str = None, conn=Depends(get_db), current_user=Depends(get_current_user)):
    cursor = conn.cursor(dictionary=True) 
    
    if device_mac:
        cursor.execute("SELECT * FROM readings WHERE mac_address = %s", (device_mac,))
    else:
        cursor.execute("SELECT * FROM readings")
        
    rows = cursor.fetchall()
    cursor.close()
    
    formatted_rows = []
    for r in rows:
        pixels = r["pixels"]
        if isinstance(pixels, str):
            pixels = json.loads(pixels)
            
        formatted_rows.append({
            "id": r["id"],
            "mac_address": r["mac_address"],
            "thermistor_temp": r["thermistor_temp"],
            "prediction": r["prediction"],
            "confidence": r["confidence"],
            "pixels": pixels
        })

    return formatted_rows

@app.delete("/api/readings/{id}")
def delete_reading(id: int, conn=Depends(get_db), current_user=Depends(get_current_user)):
    cursor = conn.cursor()
    cursor.execute("DELETE FROM readings WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    return {"status": "success"}

@app.get("/api/devices")
def get_devices(conn=Depends(get_db), current_user=Depends(get_current_user)):
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT mac_address FROM devices")
    rows = cursor.fetchall()
    cursor.close()
    
    return [{"mac_address": r["mac_address"]} for r in rows]

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            await websocket.receive_text()
    except:
        pass