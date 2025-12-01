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
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Boolean
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

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()

# ===========================
# MODELS
# ===========================
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String)
    role = Column(String, default='teacher')  # 'super_admin', 'director', 'methodist', 'teacher'
    school = Column(String)
    subject = Column(String)
    category = Column(String)
    experience = Column(Integer, default=0)
    
    achievements = relationship("Achievement", back_populates="user")

    def check_password(self, password: str) -> bool:
        password_bytes = password.encode('utf-8')[:72]
        return bcrypt.checkpw(password_bytes, self.password_hash.encode('utf-8'))
    
    @property
    def is_admin(self):
        """Обратная совместимость: любой не-teacher считается админом"""
        return self.role in ['super_admin', 'director', 'methodist']
    
    @property
    def is_super_admin(self):
        return self.role == 'super_admin'
    
    @property
    def is_director(self):
        return self.role == 'director'
    
    @property
    def is_methodist(self):
        return self.role == 'methodist'
    
    @property
    def can_delete_users(self):
        return self.role == 'super_admin'
    
    @property
    def can_manage_users(self):
        return self.role in ['super_admin', 'director']
    
    @property
    def can_moderate_achievements(self):
        return self.role in ['super_admin', 'director', 'methodist']
    
    @property
    def can_view_reports(self):
        return self.role in ['super_admin', 'director']


class Achievement(Base):
    __tablename__ = "achievements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    achievement_type = Column(String, default="oqushy_status")
    student_name = Column(String)
    place = Column(String)
    title = Column(String, nullable=False)
    description = Column(String)
    category = Column(String)
    level = Column(String)
    file_path = Column(String)
    points = Column(Float, default=0.0)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    user = relationship("User", back_populates="achievements")


Base.metadata.create_all(bind=engine)

# ===========================
# AUTO MIGRATION
# ===========================
def auto_migrate():
    """Автоматическая миграция при старте приложения"""
    try:
        from sqlalchemy import inspect, text
        db = SessionLocal()
        
        # Проверить есть ли колонка role
        inspector = inspect(engine)
        columns = [col['name'] for col in inspector.get_columns('users')]
        
        if 'role' not in columns:
            print("🔄 Запуск автоматической миграции...")
            
            # Добавить колонку role
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'teacher'"))
                conn.commit()
            print("✅ Колонка 'role' добавлена")
            
            # Конвертировать is_admin → role
            users = db.query(User).all()
            has_super = False
            
            for user in users:
                # Проверяем через getattr на случай если is_admin еще Boolean колонка
                is_admin_val = getattr(user, 'is_admin', False)
                if is_admin_val == True or is_admin_val == 1:
                    if not has_super:
                        user.role = 'super_admin'
                        has_super = True
                        print(f"✅ {user.username} → super_admin")
                    else:
                        user.role = 'director'
                        print(f"✅ {user.username} → director")
                elif not hasattr(user, 'role') or user.role is None:
                    user.role = 'teacher'
            
            db.commit()
            print("✅ Миграция завершена!")
        
        # Проверить статус для достижений
        achievement_columns = [col['name'] for col in inspector.get_columns('achievements')]
        if 'status' in achievement_columns:
            # Установить approved для существующих достижений без статуса
            with engine.connect() as conn:
                result = conn.execute(text(
                    "UPDATE achievements SET status = 'approved' WHERE status IS NULL OR status = ''"
                ))
                conn.commit()
                if result.rowcount > 0:
                    print(f"✅ Установлен статус 'approved' для {result.rowcount} достижений")
        
        db.close()
        
    except Exception as e:
        print(f"⚠️ Ошибка миграции: {e}")
        print("Продолжаем работу...")

# Запустить миграцию при старте
auto_migrate()

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
        "app_title": "Jetistik Hub",
        "app_subtitle": "Мұғалім жетістіктерінің деректі-рейтингтік жүйесі",
        "language": "Язык",
        "login": "Войти",
        "logout": "Выйти",
        "register": "Зарегистрироваться",
        "home": "Главная",
        "profile": "Профиль",
        
        # Главное меню
        "main_page": "Басты Бет",
        "jeke_cabinet": "Jeke Cabinet",
        "jetistik_alany": "Jetistik Alany",
        "rulebox": "RuleBox",
        "ai_tools": "AI Tools",
        
        # Роли
        "role": "Роль",
        "super_admin": "Супер Админ",
        "director": "Директор",
        "methodist": "Методист",
        "teacher": "Учитель",
        "admin_panel": "Управление",
        "moderate": "Проверка достижений",
        "pending_achievements": "На проверке",
        "approve": "Утвердить",
        "reject": "Отклонить",
        "moderation": "Модерация",
        
        # Разделы достижений
        "oqushy_status": "Oqushy Status",
        "sapa_qorzhyn": "Sapa Qorzhyn",
        "qogam_serpin": "Qogam Serpin",
        "tarbie_arnasy": "Tarbie Arnasy",
        "tartip_erejeleri": "Тәртіп ережелері",
        
        # Описания разделов
        "oqushy_status_desc": "Достижения учеников",
        "sapa_qorzhyn_desc": "Качественная среда",
        "qogam_serpin_desc": "Общественная активность",
        "tarbie_arnasy_desc": "Воспитательная деятельность",
        
        # Формы
        "add_achievement": "Добавить достижение",
        "my_achievements": "Мои достижения",
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
        
        # Профиль
        "welcome_user": "Добро пожаловать",
        "total_points": "Всего баллов",
        "pending_achievements": "Ожидают проверки",
        "approved_achievements": "Подтверждено",
        "school": "Школа",
        "subject": "Предмет",
        "teacher_category": "Категория",
        "experience": "Стаж",
        
        # Достижения учеников
        "student_name": "ФИО ученика",
        "place": "Место",
        "place_1": "1 место",
        "place_2": "2 место",
        "place_3": "3 место",
        "place_certificate": "Сертификат участника",
        
        # Категории для Oqushy Status
        "category_competitions": "Конкурсы",
        "category_olympiad": "Олимпиада",
        "category_project": "Проект",
        
        # Категории для Sapa Qorzhyn
        "category_teacher_competitions": "Конкурсы",
        "category_teacher_olympiad": "Олимпиада",
        "category_teacher_projects": "Проекты",
        "category_experience_exchange": "Обмен опыта",
        "category_methodical": "Методические пособия",
        
        # Категории для Qogam Serpin
        "category_social_events": "Социальные мероприятия",
        "category_volunteering": "Волонтёрство",
        "category_community_work": "Общественная работа",
        
        # Категории для Tarbie Arnasy
        "category_educational_events": "Воспитательные мероприятия",
        "category_class_work": "Классная работа",
        "category_parent_work": "Работа с родителями",
        
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
        "reports": "Отчёты",
        "school_ratings": "Рейтинг школ",
        "total_teachers": "Всего учителей",
        
        # Админ
        "admin_panel": "Админ-панель",
        "all_users": "Все пользователи",
        "create_user": "Создать пользователя",
        "pending_review": "На проверке",
        "admin_role": "Админ",
        "teacher_role": "Учитель",
        
        # Логин
        "welcome": "Jetistik Hub",
        "login_subtitle": "Войдите в систему",
        "username": "Логин",
        "password": "Пароль",
        "no_account": "Нет аккаунта?",
        "register_here": "Зарегистрируйтесь здесь",
        
        # Регистрация
        "registration": "Регистрация",
        "registration_subtitle": "Создайте новый аккаунт",
        "full_name": "ФИО",
        "confirm_password": "Подтвердите пароль",
        "have_account": "Уже есть аккаунт?",
        "login_here": "Войдите здесь",
        
        # Сообщения
        "error_invalid_credentials": "Неверный логин или пароль",
        "error_username_exists": "Логин уже занят",
        "error_passwords_dont_match": "Пароли не совпадают",
        "error_short_username": "Логин должен быть не менее 3 символов",
        "error_short_password": "Пароль должен быть не менее 6 символов",
        "error_file_too_large": "Файл слишком большой (макс. 5 МБ)",
        "success_achievement_added": "Достижение успешно добавлено",
        "success_user_created": "Пользователь создан",
    },
    "kk": {
        # Жалпы
        "app_title": "Jetistik Hub",
        "app_subtitle": "Мұғалім жетістіктерінің деректі-рейтингтік жүйесі",
        "language": "Тіл",
        "login": "Кіру",
        "logout": "Шығу",
        "register": "Тіркелу",
        "home": "Басты бет",
        "profile": "Профиль",
        
        # Басты мәзір
        "main_page": "Басты Бет",
        "jeke_cabinet": "Jeke Cabinet",
        "jetistik_alany": "Jetistik Alany",
        "rulebox": "RuleBox",
        "ai_tools": "AI Tools",
        
        # Рөлдер
        "role": "Рөл",
        "super_admin": "Супер Админ",
        "director": "Директор",
        "methodist": "Әдіскер",
        "teacher": "Мұғалім",
        "admin_panel": "Басқару",
        "moderate": "Жетістіктерді тексеру",
        "pending_achievements": "Тексеруде",
        "approve": "Бекіту",
        "reject": "Қабылдамау",
        "moderation": "Модерация",
        
        # Жетістіктер бөлімдері
        "oqushy_status": "Oqushy Status",
        "sapa_qorzhyn": "Sapa Qorzhyn",
        "qogam_serpin": "Qogam Serpin",
        "tarbie_arnasy": "Tarbie Arnasy",
        "tartip_erejeleri": "Тәртіп ережелері",
        
        # Бөлімдер сипаттамалары
        "oqushy_status_desc": "Оқушылардың жетістіктері",
        "sapa_qorzhyn_desc": "Сапалы орта",
        "qogam_serpin_desc": "Қоғамдық белсенділік",
        "tarbie_arnasy_desc": "Тәрбие жұмыстары",
        
        # Формалар
        "add_achievement": "Жетістік қосу",
        "my_achievements": "Менің жетістіктерім",
        "title": "Атауы",
        "description": "Сипаттама",
        "category": "Санат",
        "level": "Деңгей",
        "file": "Файл (макс. 5 МБ)",
        "points": "Ұпай",
        "status": "Мәртебесі",
        "date": "Күні",
        "actions": "Әрекеттер",
        "approve": "Растау",
        "reject": "Қабылдамау",
        "delete": "Жою",
        "save": "Сақтау",
        "cancel": "Болдырмау",
        "download": "Жүктеу",
        
        # Профиль
        "welcome_user": "Қош келдіңіз",
        "total_points": "Барлық ұпай",
        "pending_achievements": "Тексеруді күтуде",
        "approved_achievements": "Расталған",
        "school": "Мектеп",
        "subject": "Пән",
        "teacher_category": "Санат",
        "experience": "Тәжірибе",
        
        # Оқушы жетістіктері
        "student_name": "Оқушының аты-жөні",
        "place": "Орын",
        "place_1": "1 орын",
        "place_2": "2 орын",
        "place_3": "3 орын",
        "place_certificate": "Қатысушы сертификаты",
        
        # Oqushy Status санаттары
        "category_competitions": "Конкурстар",
        "category_olympiad": "Олимпиада",
        "category_project": "Жоба",
        
        # Sapa Qorzhyn санаттары
        "category_teacher_competitions": "Конкурстар",
        "category_teacher_olympiad": "Олимпиада",
        "category_teacher_projects": "Жобалар",
        "category_experience_exchange": "Тәжірибе алмасу",
        "category_methodical": "Әдістемелік құралдар",
        
        # Qogam Serpin санаттары
        "category_social_events": "Әлеуметтік іс-шаралар",
        "category_volunteering": "Волонтерлық",
        "category_community_work": "Қоғамдық жұмыс",
        
        # Tarbie Arnasy санаттары
        "category_educational_events": "Тәрбиелік іс-шаралар",
        "category_class_work": "Сынып жұмысы",
        "category_parent_work": "Ата-аналармен жұмыс",
        
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
        "reports": "Есептер",
        "school_ratings": "Мектептер рейтингі",
        "total_teachers": "Барлық мұғалімдер",
        
        # Админ
        "admin_panel": "Админ панелі",
        "all_users": "Барлық қолданушылар",
        "create_user": "Қолданушы жасау",
        "pending_review": "Тексеруде",
        "admin_role": "Админ",
        "teacher_role": "Мұғалім",
        
        # Кіру
        "welcome": "Jetistik Hub",
        "login_subtitle": "Жүйеге кіріңіз",
        "username": "Логин",
        "password": "Құпия сөз",
        "no_account": "Аккаунт жоқ па?",
        "register_here": "Тіркеліңіз",
        
        # Тіркелу
        "registration": "Тіркелу",
        "registration_subtitle": "Жаңа аккаунт жасаңыз",
        "full_name": "Аты-жөні",
        "confirm_password": "Құпия сөзді растаңыз",
        "have_account": "Аккаунт бар ма?",
        "login_here": "Кіріңіз",
        
        # Хабарламалар
        "error_invalid_credentials": "Логин немесе құпия сөз дұрыс емес",
        "error_username_exists": "Логин бос емес",
        "error_passwords_dont_match": "Құпия сөздер сәйкес емес",
        "error_short_username": "Логин кемінде 3 таңбадан тұруы керек",
        "error_short_password": "Құпия сөз кемінде 6 таңбадан тұруы керек",
        "error_file_too_large": "Файл тым үлкен (макс. 5 МБ)",
        "success_achievement_added": "Жетістік сәтті қосылды",
        "success_user_created": "Қолданушы жасалды",
    }
}


def get_translation(lang: str, key: str) -> str:
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


def get_language(request: Request):
    return request.cookies.get("language", "ru")


def get_current_user(session_token: Optional[str] = Cookie(None), db: Session = Depends(get_db)):
    if not session_token:
        return None
    try:
        user_id = serializer.loads(session_token, max_age=3600 * 24 * 7)
        return db.query(User).filter(User.id == user_id).first()
    except:
        return None


# ===========================
# ROUTES - AUTH
# ===========================
@app.get("/", response_class=HTMLResponse)
def root():
    return RedirectResponse(url="/login")


@app.get("/set-language/{lang}")
def set_language(request: Request, lang: str):
    # Получаем текущую страницу из referer
    referer = request.headers.get("referer", "/home")
    # Извлекаем путь без домена
    if referer:
        from urllib.parse import urlparse
        path = urlparse(referer).path or "/home"
    else:
        path = "/home"
    
    response = RedirectResponse(url=path, status_code=303)
    response.set_cookie(key="language", value=lang, max_age=3600 * 24 * 365)
    return response


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, lang: str = Depends(get_language)):
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("login.html", {"request": request, "lang": lang, "t": t})


@app.post("/login")
def login_post(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    t = lambda key: get_translation(lang, key)
    user = db.query(User).filter(User.username == username).first()
    
    if not user or not user.check_password(password):
        return templates.TemplateResponse("login.html", {
            "request": {},
            "error": t("error_invalid_credentials"),
            "lang": lang,
            "t": t
        })
    
    token = serializer.dumps(user.id)
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=3600 * 24 * 7)
    return response


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request, lang: str = Depends(get_language)):
    if not ALLOW_REGISTRATION:
        return RedirectResponse(url="/login")
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("register.html", {"request": request, "lang": lang, "t": t})


@app.post("/register")
def register_post(
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    full_name: str = Form(...),
    school: str = Form(""),
    subject: str = Form(""),
    teacher_category: str = Form(""),
    experience: int = Form(0),
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
            "request": {},
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
        subject=subject,
        category=teacher_category,
        experience=experience,
        is_admin=False
    )
    db.add(new_user)
    db.commit()
    
    token = serializer.dumps(new_user.id)
    response = RedirectResponse(url="/home", status_code=303)
    response.set_cookie(key="session_token", value=token, httponly=True, max_age=3600 * 24 * 7)
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_token")
    return response


# ===========================
# ROUTES - MAIN PAGES
# ===========================
@app.get("/home", response_class=HTMLResponse)
def home_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("home.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })


@app.get("/jeke-cabinet", response_class=HTMLResponse)
def jeke_cabinet(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    achievements = db.query(Achievement).filter(Achievement.user_id == user.id).all()
    
    total_points = sum(a.points for a in achievements if a.status == "approved")
    pending_count = sum(1 for a in achievements if a.status == "pending")
    approved_count = sum(1 for a in achievements if a.status == "approved")
    
    return templates.TemplateResponse("jeke_cabinet.html", {
        "request": request,
        "user": user,
        "achievements": achievements,
        "total_points": total_points,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "lang": lang,
        "t": t
    })


@app.get("/jetistik-alany", response_class=HTMLResponse)
def jetistik_alany(
    request: Request,
    user: User = Depends(get_current_user),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("jetistik_alany.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })


@app.get("/oqushy-status", response_class=HTMLResponse)
def oqushy_status(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    achievements = db.query(Achievement).filter(
        Achievement.user_id == user.id,
        Achievement.achievement_type == "oqushy_status"
    ).all()
    
    return templates.TemplateResponse("oqushy_status.html", {
        "request": request,
        "user": user,
        "achievements": achievements,
        "lang": lang,
        "t": t
    })


@app.get("/sapa-qorzhyn", response_class=HTMLResponse)
def sapa_qorzhyn(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    achievements = db.query(Achievement).filter(
        Achievement.user_id == user.id,
        Achievement.achievement_type == "sapa_qorzhyn"
    ).all()
    
    return templates.TemplateResponse("sapa_qorzhyn.html", {
        "request": request,
        "user": user,
        "achievements": achievements,
        "lang": lang,
        "t": t
    })


@app.get("/qogam-serpin", response_class=HTMLResponse)
def qogam_serpin(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    achievements = db.query(Achievement).filter(
        Achievement.user_id == user.id,
        Achievement.achievement_type == "qogam_serpin"
    ).all()
    
    return templates.TemplateResponse("qogam_serpin.html", {
        "request": request,
        "user": user,
        "achievements": achievements,
        "lang": lang,
        "t": t
    })


@app.get("/tarbie-arnasy", response_class=HTMLResponse)
def tarbie_arnasy(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    t = lambda key: get_translation(lang, key)
    achievements = db.query(Achievement).filter(
        Achievement.user_id == user.id,
        Achievement.achievement_type == "tarbie_arnasy"
    ).all()
    
    return templates.TemplateResponse("tarbie_arnasy.html", {
        "request": request,
        "user": user,
        "achievements": achievements,
        "lang": lang,
        "t": t
    })


@app.get("/admin", response_class=HTMLResponse)
def admin_panel(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user or not user.is_admin:
        return RedirectResponse(url="/home")
    
    t = lambda key: get_translation(lang, key)
    all_users = db.query(User).all()
    pending_achievements = db.query(Achievement).filter(Achievement.status == "pending").all()
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "all_users": all_users,
        "pending_achievements": pending_achievements,
        "lang": lang,
        "t": t
    })


@app.get("/reports", response_class=HTMLResponse)
def reports_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    # Только супер админ и директор могут видеть отчеты
    if not user.can_view_reports:
        return RedirectResponse(url="/home")
    
    t = lambda key: get_translation(lang, key)
    all_users = db.query(User).all()
    
    return templates.TemplateResponse("reports.html", {
        "request": request,
        "user": user,
        "all_users": all_users,
        "lang": lang,
        "t": t
    })


@app.get("/moderate", response_class=HTMLResponse)
def moderate_page(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    # Только супер админ, директор и методист могут модерировать
    if not user.can_moderate_achievements:
        return RedirectResponse(url="/home")
    
    t = lambda key: get_translation(lang, key)
    
    # Получить все достижения всех пользователей
    all_achievements = db.query(Achievement).join(User).all()
    
    return templates.TemplateResponse("moderate.html", {
        "request": request,
        "user": user,
        "achievements": all_achievements,
        "lang": lang,
        "t": t
    })


@app.post("/api/achievements/{achievement_id}/approve")
def approve_achievement(
    achievement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Утвердить достижение"""
    if not user or not user.can_moderate_achievements:
        raise HTTPException(status_code=403, detail="Access denied")
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement:
        raise HTTPException(status_code=404, detail="Achievement not found")
    
    achievement.status = "approved"
    db.commit()
    
    return {"status": "success", "message": "Достижение утверждено"}


@app.post("/api/achievements/{achievement_id}/reject")
def reject_achievement(
    achievement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Отклонить достижение"""
    if not user or not user.can_moderate_achievements:
        raise HTTPException(status_code=403, detail="Access denied")
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if not achievement:
        raise HTTPException(status_code=404, detail="Achievement not found")
    
    achievement.status = "rejected"
    db.commit()
    
    return {"status": "success", "message": "Достижение отклонено"}


# ===========================
# ROUTES - ACHIEVEMENTS
# ===========================
@app.post("/add-achievement")
async def add_achievement(
    achievement_type: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    category: str = Form(...),
    level: str = Form(None),
    place: str = Form(None),
    student_name: str = Form(None),
    file: Optional[UploadFile] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    # Расчёт баллов
    points_table = {
        'city': {'1': 35, '2': 30, '3': 25, 'certificate': 10},
        'regional': {'1': 40, '2': 35, '3': 30, 'certificate': 15},
        'national': {'1': 45, '2': 40, '3': 35, 'certificate': 20},
        'international': {'1': 50, '2': 45, '3': 40, 'certificate': 25}
    }
    
    calculated_points = 0
    if level and place:
        calculated_points = points_table.get(level, {}).get(place, 0)
    
    file_path = None
    if file and file.filename:
        content = await file.read()
        if len(content) > 5 * 1024 * 1024:
            t = lambda key: get_translation(lang, key)
            return RedirectResponse(url=f"/{achievement_type}?error=file_too_large", status_code=303)
        
        import uuid
        file_ext = file.filename.split(".")[-1]
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)
        
        with open(file_path, "wb") as f:
            f.write(content)
    
    new_achievement = Achievement(
        user_id=user.id,
        achievement_type=achievement_type,
        student_name=student_name,
        title=title,
        description=description,
        category=category,
        level=level,
        place=place,
        file_path=file_path,
        points=calculated_points,
        status="pending"
    )
    db.add(new_achievement)
    db.commit()
    
    return RedirectResponse(url=f"/{achievement_type.replace('_', '-')}?success=added", status_code=303)


@app.post("/achievement/{achievement_id}/approve")
def approve_achievement(
    achievement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if achievement:
        achievement.status = "approved"
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/achievement/{achievement_id}/reject")
def reject_achievement(
    achievement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user or not user.is_admin:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if achievement:
        achievement.status = "rejected"
        db.commit()
    return RedirectResponse(url="/admin", status_code=303)


@app.post("/achievement/{achievement_id}/delete")
def delete_achievement(
    achievement_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user:
        raise HTTPException(status_code=403)
    
    achievement = db.query(Achievement).filter(Achievement.id == achievement_id).first()
    if achievement and (achievement.user_id == user.id or user.is_admin):
        db.delete(achievement)
        db.commit()
    
    return RedirectResponse(url="/jeke-cabinet", status_code=303)


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
        return RedirectResponse(url="/admin?error=username_exists", status_code=303)
    
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
    return RedirectResponse(url="/admin?success=user_created", status_code=303)
