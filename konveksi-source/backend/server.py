from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, APIRouter, HTTPException, Request, Response, Depends
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os, uuid, bcrypt, jwt, logging

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')
client = AsyncIOMotorClient(os.environ['MONGO_URL'])
db = client[os.environ['DB_NAME']]
app = FastAPI(title='Produksi & Jahitan API')
api = APIRouter(prefix='/api')
JWT_ALGORITHM = 'HS256'
logger = logging.getLogger(__name__)

class LoginInput(BaseModel):
    email: str
    password: str

class RecordInput(BaseModel):
    tanggal: str
    model: str
    variasi: Optional[str] = ''
    ukuran: Optional[str] = ''
    yard: float = 0
    kirim1: float = 0
    kirim2: float = 0
    kirim3: float = 0
    kirim4: float = 0
    qty: float = 0
    tarif: float = 0
    status: Optional[Literal['IN PROGRESS', 'DONE']] = 'IN PROGRESS'

def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password, hashed):
    return bcrypt.checkpw(password.encode(), hashed.encode())

def make_token(user_id, email):
    return jwt.encode({'sub': user_id, 'email': email, 'exp': datetime.now(timezone.utc) + timedelta(hours=12), 'type': 'access'}, os.environ['JWT_SECRET'], algorithm=JWT_ALGORITHM)

async def current_user(request: Request):
    token = request.cookies.get('access_token')
    if not token:
        header = request.headers.get('Authorization', '')
        token = header[7:] if header.startswith('Bearer ') else None
    if not token:
        raise HTTPException(401, 'Sesi admin belum aktif')
    try:
        payload = jwt.decode(token, os.environ['JWT_SECRET'], algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({'id': payload['sub']}, {'_id': 0, 'password_hash': 0})
        if not user:
            raise HTTPException(401, 'Admin tidak ditemukan')
        return user
    except jwt.PyJWTError:
        raise HTTPException(401, 'Sesi sudah kedaluwarsa')

async def seed_data():
    await db.users.create_index('email', unique=True)
    await db.records.create_index([('module', 1), ('tanggal', -1)])
    await db.login_attempts.create_index('identifier', unique=True)
    email = os.environ['ADMIN_EMAIL'].lower()
    existing = await db.users.find_one({'email': email})
    if not existing:
        await db.users.insert_one({'id': str(uuid.uuid4()), 'email': email, 'name': 'Administrator', 'role': 'admin', 'password_hash': hash_password(os.environ['ADMIN_PASSWORD'])})
    elif not verify_password(os.environ['ADMIN_PASSWORD'], existing['password_hash']):
        await db.users.update_one({'email': email}, {'$set': {'password_hash': hash_password(os.environ['ADMIN_PASSWORD'])}})
    if await db.records.count_documents({}) == 0:
        today = datetime.now(timezone.utc).date()
        demos = [
            ('faris', 1, {'tanggal': str(today), 'model': 'GMS TALI', 'yard': 320, 'kirim1': 120, 'kirim2': 80, 'kirim3': 0, 'kirim4': 0, 'status': 'IN PROGRESS'}),
            ('faris', 1, {'tanggal': str(today - timedelta(days=1)), 'model': 'Tunik Aisha', 'yard': 250, 'kirim1': 250, 'kirim2': 0, 'kirim3': 0, 'kirim4': 0, 'status': 'DONE'}),
            ('eko', 1, {'tanggal': str(today), 'model': 'GMS TALI', 'variasi': 'Valery', 'ukuran': 'All Size', 'qty': 180}),
            ('eko', 1, {'tanggal': str(today - timedelta(days=1)), 'model': 'Alisya', 'variasi': 'Rachel', 'ukuran': 'L', 'qty': 120}),
            ('irawan', 1, {'tanggal': str(today), 'model': 'Karet', 'qty': 150, 'tarif': 4500}),
            ('irawan', 1, {'tanggal': str(today - timedelta(days=1)), 'model': 'Tunik', 'qty': 220, 'tarif': 5500}),
        ]
        for module, _, data in demos:
            await db.records.insert_one({'id': str(uuid.uuid4()), 'module': module, **data})

@app.on_event('startup')
async def startup():
    await seed_data()

@api.post('/auth/login')
async def login(body: LoginInput, response: Response):
    email = body.email.lower()
    identifier = f"{email}:{'unknown'}"
    attempt = await db.login_attempts.find_one({'identifier': identifier}, {'_id': 0})
    if attempt and attempt.get('locked_until', '') > datetime.now(timezone.utc).isoformat():
        raise HTTPException(429, 'Terlalu banyak percobaan. Coba lagi dalam 15 menit')
    user = await db.users.find_one({'email': email})
    if not user or not verify_password(body.password, user['password_hash']):
        now = datetime.now(timezone.utc)
        count = (attempt.get('count', 0) if attempt else 0) + 1
        values = {'identifier': identifier, 'count': count, 'last_failed': now.isoformat()}
        if count >= 5: values['locked_until'] = (now + timedelta(minutes=15)).isoformat()
        await db.login_attempts.update_one({'identifier': identifier}, {'$set': values}, upsert=True)
        raise HTTPException(401, 'Email atau kata sandi salah')
    await db.login_attempts.delete_one({'identifier': identifier})
    response.set_cookie('access_token', make_token(user['id'], user['email']), httponly=True, secure=True, samesite='none', max_age=43200, path='/')
    return {'id': user['id'], 'email': user['email'], 'name': user['name'], 'role': user['role']}

@api.post('/auth/logout')
async def logout(response: Response):
    response.delete_cookie('access_token', path='/')
    return {'message': 'Berhasil keluar'}

@api.get('/auth/me')
async def me(user=Depends(current_user)):
    return user

@api.get('/records/{module}')
async def list_records(module: str, search: str = '', status: str = '', user=Depends(current_user)):
    query = {'module': module}
    if search: query['model'] = {'$regex': search, '$options': 'i'}
    if status and module == 'faris': query['status'] = status
    return await db.records.find(query, {'_id': 0, 'module': 0}).sort('tanggal', -1).to_list(1000)

@api.post('/records/{module}')
async def create_record(module: str, body: RecordInput, user=Depends(current_user)):
    doc = {'id': str(uuid.uuid4()), 'module': module, **body.model_dump()}
    await db.records.insert_one(doc)
    doc.pop('_id', None)
    doc.pop('module', None)
    return doc

@api.put('/records/{module}/{record_id}')
async def update_record(module: str, record_id: str, body: RecordInput, user=Depends(current_user)):
    result = await db.records.update_one({'id': record_id, 'module': module}, {'$set': body.model_dump()})
    if not result.matched_count: raise HTTPException(404, 'Data tidak ditemukan')
    return {'id': record_id, **body.model_dump()}

@api.delete('/records/{module}/{record_id}')
async def delete_record(module: str, record_id: str, user=Depends(current_user)):
    result = await db.records.delete_one({'id': record_id, 'module': module})
    if not result.deleted_count: raise HTTPException(404, 'Data tidak ditemukan')
    return {'message': 'Data dihapus'}

@api.get('/dashboard')
async def dashboard(user=Depends(current_user)):
    rows = await db.records.find({}, {'_id': 0}).to_list(5000)
    faris = [r for r in rows if r['module'] == 'faris']; eko = [r for r in rows if r['module'] == 'eko']; irawan = [r for r in rows if r['module'] == 'irawan']
    models = {}
    for r in rows: models[r['model']] = models.get(r['model'], 0) + float(r.get('qty', 0) or 0)
    days = {}
    for r in irawan: days[r['tanggal']] = days.get(r['tanggal'], 0) + float(r.get('qty', 0) or 0) * float(r.get('tarif', 0) or 0)
    return {'total_yard': sum(float(r.get('yard', 0) or 0) for r in faris), 'total_qty': sum(float(r.get('qty', 0) or 0) for r in eko), 'total_ongkos': sum(float(r.get('qty', 0) or 0) * float(r.get('tarif', 0) or 0) for r in irawan), 'active': sum(r.get('status') == 'IN PROGRESS' for r in faris), 'done': sum(r.get('status') == 'DONE' for r in faris), 'motif_count': len(eko), 'trend': [{'tanggal': k, 'total': v} for k, v in sorted(days.items())], 'models': [{'name': k, 'qty': v} for k, v in sorted(models.items(), key=lambda x: -x[1])[:6]]}

app.include_router(api)
app.add_middleware(CORSMiddleware, allow_credentials=True, allow_origins=[os.environ['FRONTEND_URL']], allow_methods=['*'], allow_headers=['*'])
@app.on_event('shutdown')
async def shutdown(): client.close()