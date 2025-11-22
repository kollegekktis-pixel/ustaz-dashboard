# main.py
import os
from pathlib import Path
from datetime import date
from typing import Generator

from fastapi import FastAPI, Request, Form, UploadFile, File, Depends, HTTPException, status
from fastapi.responses import RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from sqlalchemy import create_engine, Column, Integer, String, Date, ForeignKey
from sqlalchemy.orm import sessionmaker, declarative_base, relationship, Session as DBSession
from passlib.hash import bcrypt
from dotenv import load_dotenv

load_dotenv()

# Config
SECRET_KEY = os.getenv("SECRET_KEY", "supersecretkey123")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./db.sqlite3")
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "uploads"))
ADMIN_USER = os.getenv("ADMIN_USER", "admin")
ADMIN_PASS = os.getenv("ADMIN_PASS", "12345")

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Учительский Дашборд")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(BASE_DIR, "templates"))

# static
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "static")), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# DB
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    full_name = Column(String, nullable=True)
    password_hash = Column(String)
    role = Column(String, default="teacher")
    school = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    achievements = relationship("Achievement", back_populates="teacher")

    def verify_password(self, plain: str) -> bool:
        return bcrypt.verify(plain, self.password_hash)

class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    teacher_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    level = Column(String)
    date = Column(Date)
    filename = Column(String, nullable=True)
    status = Column(String, default="pending")
    teacher = relationship("User", back_populates="achievements")

Base.metadata.create_all(bind=engine)

# Helpers
def get_db() -> Generator[DBSession, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_by_username(db: DBSession, username: str):
    return db.query(User).filter(User.username == username).first()

# Ensure admin
with SessionLocal() as db:
    if not get_user_by_username(db, ADMIN_USER):
        admin = User(username=ADMIN_USER, full_name="Methodist Admin",
                     password_hash=bcrypt.hash(ADMIN_PASS), role="admin", school="", subject="")
        db.add(admin); db.commit()
        print("Created admin user:", ADMIN_USER)

LEVEL_POINTS = {"school": 2, "city": 3, "region": 4, "republic": 5}
LEVEL_LABELS = {"school": "Школьный", "city": "Городской", "region": "Областной", "republic": "Республиканский"}

# Auth helpers
def current_user(request: Request, db: DBSession):
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(User).filter(User.id == uid).first()


def require_user(request: Request, db: DBSession = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user

def require_admin(request: Request, db: DBSession = Depends(get_db)):
    user = require_user(request, db)
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not admin")
    return user

# Routes
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    user_id = request.session.get("user_id")
    if user_id:
        return RedirectResponse(url="/dashboard", status_code=302)
    return RedirectResponse(url="/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_get(request: Request):
    dummy = type("U",(object,),{"full_name":"", "username":""})()
    return templates.TemplateResponse("login.html", {"request": request, "user": dummy})

@app.post("/login")
def login_post(request: Request, username: str = Form(...), password: str = Form(...), db: DBSession = Depends(get_db)):
    user = get_user_by_username(db, username)
    if not user or not user.verify_password(password):
        dummy = type("U",(object,),{"full_name":"", "username":""})()
        return templates.TemplateResponse("login.html", {"request": request, "error": "Неверный логин или пароль", "user": dummy})
    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=302)

@app.get("/logout")
def logout(request: Request):
    request.session.pop("user_id", None)
    return RedirectResponse(url="/login")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, db: DBSession = Depends(get_db)):
    user = current_user(request, db)
    if not user:
        return RedirectResponse(url="/login")
    return templates.TemplateResponse("dashboard.html", {"request": request, "user": user, "level_labels": LEVEL_LABELS})

@app.get("/file/{fname}")
def serve_file(fname: str):
    path = UPLOAD_DIR / fname
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)

# API
@app.get("/api/me")
def api_me(user: User = Depends(require_user)):
    return {"id": user.id, "username": user.username, "full_name": user.full_name, "role": user.role, "school": user.school, "subject": user.subject}

@app.get("/api/achievements")
def api_achievements(db: DBSession = Depends(get_db), user: User = Depends(require_user)):
    if user.role == "admin":
        items = db.query(Achievement).order_by(Achievement.id.desc()).all()
    else:
        items = db.query(Achievement).filter(Achievement.teacher_id == user.id).order_by(Achievement.id.desc()).all()
    out = []
    for a in items:
        out.append({
            "id": a.id,
            "teacher": a.teacher.full_name or a.teacher.username,
            "teacher_id": a.teacher_id,
            "title": a.title,
            "level": a.level,
            "level_label": LEVEL_LABELS.get(a.level, a.level),
            "date": a.date.isoformat() if a.date else None,
            "filename": a.filename,
            "status": a.status,
            "points": LEVEL_POINTS.get(a.level, 0)
        })
    return out

@app.post("/api/achievements")
async def api_create_achievement(request: Request,
                                 title: str = Form(...),
                                 level: str = Form(...),
                                 date_val: str = Form(...),
                                 file: UploadFile = File(None),
                                 db: DBSession = Depends(get_db),
                                 user: User = Depends(require_user)):
    filename = None
    if file:
        safe_name = f"{user.id}_{int(date.today().strftime('%Y%m%d'))}_{file.filename}"
        dest = UPLOAD_DIR / safe_name
        with open(dest, "wb") as f:
            content = await file.read()
            f.write(content)
        filename = safe_name
    a = Achievement(teacher_id=user.id, title=title, level=level, date=date.fromisoformat(date_val), filename=filename, status="pending")
    db.add(a); db.commit()
    return {"ok": True, "id": a.id}

@app.post("/api/achievements/{aid}/confirm")
def api_confirm(aid: int, db: DBSession = Depends(get_db), admin: User = Depends(require_admin)):
    a = db.query(Achievement).filter(Achievement.id == aid).first()
    if not a:
        raise HTTPException(404, "Not found")
    a.status = "confirmed"
    db.commit()
    return {"ok": True}

@app.post("/api/achievements/{aid}/reject")
def api_reject(aid: int, db: DBSession = Depends(get_db), admin: User = Depends(require_admin)):
    a = db.query(Achievement).filter(Achievement.id == aid).first()
    if not a:
        raise HTTPException(404, "Not found")
    a.status = "rejected"
    db.commit()
    return {"ok": True}

@app.get("/api/rating")
def api_rating(db: DBSession = Depends(get_db), user: User = Depends(require_user)):
    users = db.query(User).all()
    achs = db.query(Achievement).filter(Achievement.status == "confirmed").all()
    teacher_scores = {u.id: 0 for u in users}
    for a in achs:
        pts = LEVEL_POINTS.get(a.level, 0)
        teacher_scores[a.teacher_id] = teacher_scores.get(a.teacher_id, 0) + pts
    teachers_out = []
    for u in users:
        teachers_out.append({"id": u.id, "name": u.full_name or u.username, "school": u.school or "—", "score": teacher_scores.get(u.id, 0)})
    schools = {}
    counts = {}
    for t in teachers_out:
        s = t["school"]
        schools[s] = schools.get(s, 0) + t["score"]
        counts[s] = counts.get(s, 0) + 1
    school_out = []
    for s, total in schools.items():
        cnt = counts[s]
        avg = total / cnt if cnt else 0
        school_out.append({"school": s, "total": total, "avg": round(avg, 2)})
    teachers_out = sorted(teachers_out, key=lambda x: x["score"], reverse=True)
    school_out = sorted(school_out, key=lambda x: x["avg"], reverse=True)
    return {"teachers": teachers_out, "schools": school_out}

# Admin: create user (simple)
@app.post("/create_user")
def create_user(request: Request, 
                username: str = Form(...), 
                password: str = Form(...),
                full_name: str = Form(""), 
                role: str = Form("teacher"), 
                school: str = Form(""), 
                subject: str = Form(""),
                db: DBSession = Depends(get_db), 
                admin: User = Depends(require_admin)
               ):
if get_user_by_username(db, username):
    return templates.TemplateResponse("dashboard.html", 
                                          {"request": request, "user": admin, "error": "Пользователь существует"})
safe_pass = password[:50]  # обрежем чтобы не было больше 72 байта
u = User
         (username=username, 
         full_name=full_name,
         password_hash=bcrypt.hash(safe_pass),
         role=role, 
         school=school, 
         subject=subject)
db.add(u); 
db.commit()
    return RedirectResponse(url="/dashboard", status_code=302)



