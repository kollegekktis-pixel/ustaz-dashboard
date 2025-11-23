import os
import secrets
from datetime import datetime
from typing import Optional

import bcrypt
from fastapi import FastAPI, Request, Form, Depends, HTTPException, Cookie, UploadFile
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import URLSafeTimedSerializer
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship

# ===========================
# DATABASE SETUP
# ===========================
DATABASE_URL = os.getenv("DATABASE_URL")
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not DATABASE_URL:
    DATABASE_URL = "sqlite:///./db.sqlite3"

print(f"🔌 Connecting to database: {DATABASE_URL[:30]}...")

engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True,
    echo=True  # Включаем логирование SQL запросов
)
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ===========================
# MODELS - ИСПРАВЛЕНО для PostgreSQL
# ===========================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(255), unique=True, nullable=False, index=True)  # ИСПРАВЛЕНО
    password_hash = Column(String(255), nullable=False)  # ИСПРАВЛЕНО
    full_name = Column(String(255))  # ИСПРАВЛЕНО
    is_admin = Column(Boolean, default=False)
    school = Column(String(255))  # ИСПРАВЛЕНО
    achievements = relationship("Achievement", back_populates="user")

    def check_password(self, password: str) -> bool:
        password_bytes = password.encode('utf-8')[:72]
        return bcrypt.checkpw(password_bytes, self.password_hash.encode('utf-8'))


class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(500), nullable=False)  # ИСПРАВЛЕНО
    description = Column(Text)  # ИСПРАВЛЕНО - используем Text для длинных текстов
    category = Column(String(100))  # ИСПРАВЛЕНО
    level = Column(String(100))  # ИСПРАВЛЕНО
    file_path = Column(String(500))  # ИСПРАВЛЕНО
    points = Column(Float, default=0.0)
    status = Column(String(50), default="pending")  # ИСПРАВЛЕНО
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="achievements")


# СОЗДАНИЕ ТАБЛИЦ с обработкой ошибок
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
except Exception as e:
    print(f"❌ Error creating tables: {e}")
    raise

# ===========================
# PASSWORD HASHING
# ===========================
def hash_password(password: str) -> str:
    password_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')


# ===========================
# APP SETUP
# ===========================
app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# Создаём папку для загрузки файлов
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

templates = Jinja2Templates(directory="templates")

SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
serializer = URLSafeTimedSerializer(SECRET_KEY)

ALLOW_REGISTRATION = os.getenv("ALLOW_REGISTRATION", "true").lower() == "true"

# ===========================
# TRANSLATIONS
# ===========================
TRANSLATIONS = {
    "ru": {
        # Общее
        "app_title": "UstasSapa Lab",
        "app_subtitle": "Рейтинговая система оценки достижений учителя",
        "language": "Язык",
        "login": "Войти",
        "logout": "Выйти",
        "register": "Зарегистрироваться",
        "dashboard": "Панель",
        "profile": "Профиль",
        "add_achievement": "Добавить достижение",
        "my_achievements": "Мои достижения",
        "admin_panel": "Админ-панель",
        "reports": "Отчёты",
        
        # Логин
        "welcome": "UstasSapa Lab",
        "login_subtitle": "Войдите в систему",
        "username": "Логин",
        "password": "Пароль",
        "no_account": "Нет аккаунта?",
        "register_here": "Зарегистрируйтесь здесь",
        
        # Регистрация
        "registration": "Регистрация",
        "registration_subtitle": "Создайте новый аккаунт",
        "full_name": "ФИО",
        "school": "Школа",
        "confirm_password": "Подтвердите пароль",
        "have_account": "Уже есть аккаунт?",
        "login_here": "Войдите здесь",
        
        # Профиль
        "welcome_user": "Добро пожаловать",
        "total_points": "Всего баллов",
        "pending_achievements": "Ожидают проверки",
        "approved_achievements": "Подтверждено",
        
        # Достижения
        "title": "Название",
        "description": "Описание",
        "category": "Категория",
        "level": "Уровень",
        "file": "Файл (макс. 5 МБ)",
        "points": "Баллы",
        "status": "Статус",
        "date": "Дата",
        "actions": "Действия",
        "approve": "Подтвердить",
        "reject": "Отклонить",
        "delete": "Удалить",
        "save": "Сохранить",
        "cancel": "Отмена",
        "download": "Скачать",
        
        # Категории
        "category_publications": "Публикации",
        "category_conferences": "Конференции",
        "category_olympiads": "Олимпиады",
        "category_projects": "Проекты",
        "category_courses": "Курсы",
        "category_other": "Другое",
        
        # Уровни
        "level_school": "Школьный",
        "level_city": "Городской",
        "level_regional": "Областной",
        "level_national": "Республиканский",
        "level_international": "Международный",
        
        # Статусы
        "status_pending": "Ожидает",
        "status_approved": "Подтверждено",
        "status_rejected": "Отклонено",
        
        # Рейтинг
        "top_teachers": "Топ-10 учителей",
        "rank": "Место",
        "teacher": "Учитель",
        "school_ratings": "Рейтинг школ",
        "total_teachers": "Всего учителей",
        
        # Админ
        "all_users": "Все пользователи",
        "create_user": "Создать пользователя",
        "pending_review": "На проверке",
        "admin_role": "Админ",
        "teacher_role": "Учитель",
        
        # Сообщения
        "error_invalid_credentials": "Неверный логин или пароль",
        "error_username_exists": "Логин уже занят",
        "error_passwords_dont_match": "Пароли не совпадают",
        "error_short_username": "Логин должен быть минимум 3 символа",
        "error_short_password": "Пароль должен быть минимум 6 символов",
        "error_file_too_large": "Файл слишком большой (макс. 5 МБ)",
        "success_registered": "Регистрация успешна!",
        "success_achievement_added": "Достижение добавлено!",
        "success_user_created": "Пользователь создан!",
    },
    "kk": {
        # Жалпы
        "app_title": "UstasSapa Lab",
        "app_subtitle": "Мұғалімнің жетістіктерін бағалау рейтингтік жүйесі",
        "language": "Тіл",
        "login": "Кіру",
        "logout": "Шығу",
        "register": "Тіркелу",
        "dashboard": "Басты бет",
        "profile": "Профиль",
        "add_achievement": "Жетістік қосу",
        "my_achievements": "Менің жетістіктерім",
        "admin_panel": "Әкімші панелі",
        "reports": "Есептер",
        
        # Кіру
        "welcome": "UstasSapa Lab",
        "login_subtitle": "Жүйеге кіріңіз",
        "username": "Логин",
        "password": "Құпия сөз",
        "no_account": "Аккаунт жоқ па?",
        "register_here": "Мұнда тіркеліңіз",
        
        # Тіркелу
        "registration": "Тіркелу",
        "registration_subtitle": "Жаңа аккаунт жасаңыз",
        "full_name": "Аты-жөні",
        "school": "Мектеп",
        "confirm_password": "Құпия сөзді растаңыз",
        "have_account": "Аккаунт бар ма?",
        "login_here": "Мұнда кіріңіз",
        
        # Профиль
        "welcome_user": "Қош келдіңіз",
        "total_points": "Барлық ұпайлар",
        "pending_achievements": "Тексеруді күтуде",
        "approved_achievements": "Расталған",
        
        # Жетістіктер
        "title": "Атауы",
        "description": "Сипаттама",
        "category": "Санат",
        "level": "Деңгей",
        "file": "Файл (макс. 5 МБ)",
        "points": "Ұпайлар",
        "status": "Мәртебе",
        "date": "Күні",
        "actions": "Әрекеттер",
        "approve": "Растау",
        "reject": "Қабылдамау",
        "delete": "Жою",
        "save": "Сақтау",
        "cancel": "Болдырмау",
        "download": "Жүктеп алу",
        
        # Санаттар
        "category_publications": "Жарияланымдар",
        "category_conferences": "Конференциялар",
        "category_olympiads": "Олимпиадалар",
        "category_projects": "Жобалар",
        "category_courses": "Курстар",
        "category_other": "Басқа",
        
        # Деңгейлер
        "level_school": "Мектептік",
        "level_city": "Қалалық",
        "level_regional": "Облыстық",
        "level_national": "Республикалық",
        "level_international": "Халықаралық",
        
        # Мәртебелер
        "status_pending": "Күтуде",
        "status_approved": "Расталған",
        "status_rejected": "Қабылданбаған",
        
        # Рейтинг
        "top_teachers": "Топ-10 мұғалімдер",
        "rank": "Орын",
        "teacher": "Мұғалім",
        "school_ratings": "Мектептер рейтингі",
        "total_teachers": "Барлық мұғалімдер",
        
        # Әкімші
        "all_users": "Барлық пайдаланушылар",
        "create_user": "Пайдаланушы жасау",
        "pending_review": "Тексеруде",
        "admin_role": "Әкімші",
        "teacher_role": "Мұғалім",
        
        # Хабарламалар
        "error_invalid_credentials": "Логин немесе құпия сөз қате",
        "error_username_exists": "Логин бос емес",
        "error_passwords_dont_match": "Құпия сөздер сәйкес келмейді",
        "error_short_username": "Логин кемінде 3 таңба болуы керек",
        "error_short_password": "Құпия сөз кемінде 6 таңба болуы керек",
        "error_file_too_large": "Файл тым үлкен (макс. 5 МБ)",
        "success_registered": "Тіркелу сәтті өтті!",
        "success_achievement_added": "Жетістік қосылды!",
        "success_user_created": "Пайдаланушы жасалды!",
    }
}

def get_translation(lang: str, key: str) -> str:
    """Получить перевод по ключу"""
    return TRANSLATIONS.get(lang, TRANSLATIONS["ru"]).get(key, key)

# ===========================
# DEPENDENCIES
# ===========================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)) -> Optional[User]:
    if not session_token:
        return None
    try:
        user_id = serializer.loads(session_token, max_age=3600 * 24 * 7)
        return db.query(User).filter(User.id == user_id).first()
    except:
        return None


def get_language(language: Optional[str] = Cookie(None)) -> str:
    """Получить текущий язык из cookie"""
    return language if language in ["ru", "kk"] else "ru"


# ===========================
# STARTUP EVENT
# ===========================
@app.on_event("startup")
def create_admin():
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin_pass = os.getenv("ADMIN_PASS", "adminpass123")
            hashed_pw = hash_password(admin_pass)
            new_admin = User(
                username="admin",
                password_hash=hashed_pw,
                full_name="Administrator",
                is_admin=True,
                school="System"
            )
            db.add(new_admin)
            db.commit()
            print("✅ Created admin user: admin")
        else:
            print("ℹ️ Admin user already exists")
    except Exception as e:
        print(f"⚠️ Error creating admin: {e}")
        db.rollback()
    finally:
        db.close()


# ===========================
# ROUTES - Language Switcher
# ===========================
@app.get("/set-language/{lang}")
def set_language(lang: str, request: Request):
    """Переключить язык"""
    if lang not in ["ru", "kk"]:
        lang = "ru"
    
    response = RedirectResponse(url=request.headers.get("referer", "/"), status_code=303)
    response.set_cookie(key="language", value=lang, max_age=3600 * 24 * 365)
    return response


# ===========================
# ROUTES - AUTH
# ===========================
@app.get("/", response_class=HTMLResponse)
def index(request: Request, user: User = Depends(get_current_user), lang: str = Depends(get_language)):
    if user:
        return RedirectResponse(url="/dashboard")
    return RedirectResponse(url="/login")


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, lang: str = Depends(get_language)):
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "lang": lang,
        "t": t
    })


@app.post("/login")
def login_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    t = lambda key: get_translation(lang, key)
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.check_password(password):
        return templates.TemplateResponse("login.html", {
            "request": request,
            "error": t("error_invalid_credentials"),
            "lang": lang,
            "t": t
        })
    
    token = serializer.dumps(user.id)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=3600 * 24 * 7)
    return response


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, lang: str = Depends(get_language)):
    if not ALLOW_REGISTRATION:
        return RedirectResponse(url="/login")
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("register.html", {
        "request": request,
        "lang": lang,
        "t": t
    })


@app.post("/register")
def register_post(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(...),
    school: str = Form(""),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    t = lambda key: get_translation(lang, key)
    
    if not ALLOW_REGISTRATION:
        return RedirectResponse(url="/login")
    
    error = None
    if len(username) < 3:
        error = t("error_short_username")
    elif len(password) < 6:
        error = t("error_short_password")
    elif password != confirm_password:
        error = t("error_passwords_dont_match")
    elif db.query(User).filter(User.username == username).first():
        error = t("error_username_exists")
    
    if error:
        return templates.TemplateResponse("register.html", {
            "request": request,
            "error": error,
            "lang": lang,
            "t": t
        })
    
    hashed_pw = hash_password(password)
    new_user = User(
        username=username,
        password_hash=hashed_pw,
        full_name=full_name,
        school=school,
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    
    token = serializer.dumps(new_user.id)
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=3600 * 24 * 7)
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response


# ===========================
# ROUTES - DASHBOARD
# ===========================
@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    
    achievements = db.query(Achievement).filter(Achievement.user_id == user.id).all()
    all_users = db.query(User).all() if user.is_admin else []
    pending = db.query(Achievement).filter(Achievement.status == "pending").all() if user.is_admin else []
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user,
        "achievements": achievements,
        "all_users": all_users,
        "pending_achievements": pending,
        "allow_registration": ALLOW_REGISTRATION,
        "lang": lang,
        "t": t
    })


@app.post("/add-achievement")
async def add_achievement(
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form("other"),
    level: str = Form("school"),
    points: float = Form(0.0),
    file: Optional[UploadFile] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    file_path = None
    
    # Обработка загрузки файла
    if file and file.filename:
        # Проверка размера файла (5 МБ = 5 * 1024 * 1024 байт)
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            t = lambda key: get_translation(lang, key)
            return templates.TemplateResponse("dashboard.html", {
                "request": {},
                "user": user,
                "achievements": db.query(Achievement).filter(Achievement.user_id == user.id).all(),
                "error": t("error_file_too_large"),
                "lang": lang,
                "t": t
            })
        
        # Сохранение файла
        import uuid
        file_ext = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
    
    new_achievement = Achievement(
        user_id=user.id,
        title=title,
        description=description,
        category=category,
        level=level,
        file_path=file_path,
        points=points,
        status="pending"
    )
    db.add(new_achievement)
    db.commit()
    return RedirectResponse(url="/dashboard?success=achievement_added", status_code=303)


@app.post("/achievement/{achievement_id}/approve")
def approve_achievement(achievement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if achievement:
        achievement.status = "approved"
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/achievement/{achievement_id}/reject")
def reject_achievement(achievement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if achievement:
        achievement.status = "rejected"
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/achievement/{achievement_id}/delete")
def delete_achievement(achievement_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if achievement and (achievement.user_id == user.id or user.is_admin):
        db.delete(achievement)
        db.commit()
    return RedirectResponse(url="/dashboard", status_code=303)


@app.post("/create-user")
def create_user(
    username: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    school: str = Form(""),
    is_admin: bool = Form(False),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
    
    if db.query(User).filter(User.username == username).first():
        return RedirectResponse(url="/dashboard?error=username_exists", status_code=303)
    
    hashed_pw = hash_password(password)
    new_user = User(
        username=username,
        password_hash=hashed_pw,
        full_name=full_name,
        school=school,
        is_admin=is_admin
    )
    db.add(new_user)
    db.commit()
    return RedirectResponse(url="/dashboard?success=user_created", status_code=303)
