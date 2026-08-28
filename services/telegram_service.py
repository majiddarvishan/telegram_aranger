from cryptography.fernet import Fernet
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded

from services.telegram_runtime import get_runtime


def proxy_config(state) -> dict | None:
    if not state.get("use_proxy", True): return None
    p={"scheme":"socks5","hostname":state.get("proxy_host","127.0.0.1"),"port":int(state.get("proxy_port",1080))}
    if state.get("proxy_user","").strip(): p["username"]=state["proxy_user"].strip()
    if state.get("proxy_pass","").strip(): p["password"]=state["proxy_pass"].strip()
    return p


def encrypt_session(key: str, session: str) -> bytes: return Fernet(key.encode()).encrypt(session.encode())
def decrypt_session(key: str, encrypted: bytes) -> str: return Fernet(key.encode()).decrypt(encrypted).decode()

def user_dict(user) -> dict:
    return {"id":user.id,"phone_number":user.phone_number or "","username":user.username or "","first_name":user.first_name or "","last_name":user.last_name or ""}

async def _new_client(settings, session_string=None, proxy=None):
    kwargs={"name":"telegram","api_id":settings.api_id,"api_hash":settings.api_hash,"proxy":proxy,"in_memory":True}
    if session_string: kwargs["session_string"]=session_string
    c=Client(**kwargs)
    await c.connect()
    return c

async def _send_code(settings, phone, proxy):
    rt=get_runtime()
    if rt.client:
        try: await rt.client.disconnect()
        except Exception: pass
        rt.client=None
    c=await _new_client(settings, proxy=proxy)
    sent=await c.send_code(phone)
    rt.client=c
    return sent.phone_code_hash

def send_code(settings, phone, proxy): return get_runtime().run(_send_code(settings,phone,proxy))

async def _verify_code(phone, code_hash, code):
    c=get_runtime().client
    try:
        await c.sign_in(phone, code_hash, code)
    except SessionPasswordNeeded:
        return "2fa", None
    return "success", user_dict(await c.get_me())

def verify_code(phone, code_hash, code): return get_runtime().run(_verify_code(phone,code_hash,code))

async def _verify_2fa(password): return user_dict(await get_runtime().client.check_password(password))
def verify_2fa(password): return get_runtime().run(_verify_2fa(password))

async def _export(): return await get_runtime().client.export_session_string()
def export_session(): return get_runtime().run(_export())

async def _restore(settings, encrypted, key, proxy):
    c=await _new_client(settings, decrypt_session(key, encrypted), proxy)
    try:
        me=await c.get_me(); get_runtime().client=c; return user_dict(me)
    except Exception:
        try: await c.disconnect()
        except Exception: pass
        raise

def restore(settings, encrypted, key, proxy): return get_runtime().run(_restore(settings,encrypted,key,proxy))

async def _disconnect(logout=False):
    rt=get_runtime(); c=rt.client
    if not c: return
    try:
        if logout: await c.log_out()
        elif c.is_connected: await c.disconnect()
    finally: rt.client=None

def disconnect(): get_runtime().run(_disconnect(False))
def logout(): get_runtime().run(_disconnect(True))

async def _dialogs():
    c = get_runtime().client
    result = []

    async for d in c.get_dialogs():
        chat = d.chat

        if chat.type.value not in (
            "private",
            "group",
            "supergroup",
            "channel",
        ):
            continue

        title = (
            chat.title
            or f"{chat.first_name or ''} {chat.last_name or ''}".strip()
            or str(chat.id)
        )

        result.append(
            {
                "id": chat.id,
                "title": title,
                "type": chat.type.value,
                "username": chat.username or "",
            }
        )

    return result

def get_dialogs(): return get_runtime().run(_dialogs())

async def _history(chat_id, start_dt, end_dt, limit=100):
    c=get_runtime().client; out=[]
    async for m in c.get_chat_history(chat_id, limit=limit):
        if not m.date: continue
        if m.date < start_dt: break
        if m.date <= end_dt:
            out.append({"id":m.id,"chat_id":chat_id,"text":m.text or m.caption or "[Media / File]","date":m.date,"user_id":chat_id})
    return out

def history(chat_id,start_dt,end_dt,limit=100): return get_runtime().run(_history(chat_id,start_dt,end_dt,limit))

async def _delete(chat_id,message_id): await get_runtime().client.delete_messages(chat_id,message_id)
def delete_message(chat_id,message_id): get_runtime().run(_delete(chat_id,message_id))
