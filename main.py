import os
import secrets
from datetime import datetime
from typing import Optional
from urllib.parse import urlparse
import uuid
from io import BytesIO

import bcrypt
import cloudinary
import cloudinary.uploader
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
    is_admin = Column(Boolean, default=False)
    school = Column(String)
    subject = Column(String)
    category = Column(String)
    experience = Column(Integer, default=0)
    
    achievements = relationship("Achievement", back_populates="user")

    def check_password(self, password: str) -> bool:
        password_bytes = password.encode('utf-8')[:72]
        return bcrypt.checkpw(password_bytes, self.password_hash.encode('utf-8'))


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

# ===========================
# CLOUDINARY SETUP
# ===========================
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True
)

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
        "rulebox_subtitle": "Нормативные документы для педагогов",
        "attestation_rules": "Правила аттестации педагогов",
        "attestation_rules_desc": "Приказ Министра образования и науки РК от 27 января 2016 года № 83",
        "curriculum_plans": "Типовые учебные планы",
        "curriculum_plans_desc": "Приказ Министра образования и науки РК от 8 ноября 2012 года № 500",
        "teacher_status": "О статусе педагога",
        "teacher_status_desc": "Закон Республики Казахстан от 27 декабря 2019 года № 293-VІ ЗРК",
        "qualification_characteristics": "Квалификационные характеристики должностей педагогов",
        "qualification_characteristics_desc": "Приказ МОН РК от 13 июля 2009 года № 338",
        "prohibited_items": "Перечень запрещенных предметов и веществ",
        "prohibited_items_desc": "Приказ МОН РК от 25 мая 2021 года № 235",
        "antiterror_protection": "Антитеррористическая защита объектов",
        "antiterror_protection_desc": "Приказ Министра просвещения РК от 31 июля 2023 года № 237",
        "classroom_management": "Положение о классном руководстве",
        "classroom_management_desc": "Приказ и.о. МОН РК от 31 мая 2022 года № 251",
        "education_law": "Закон об образовании",
        "education_law_desc": "Закон РК от 27 июля 2007 года № 319-III",
        "psycho_pedagogical_support": "Служба психолого-педагогического сопровождения",
        "psycho_pedagogical_support_desc": "Приказ Министра просвещения РК от 29 апреля 2025 года № 92",
        "language": "Язык",
        "login": "Войти",
        "logout": "Выйти",
        "register": "Зарегистрироваться",
        "home": "Главная",
        "profile": "Профиль",
        
        # Главное меню
        "main_page": "Главная",
        "jeke_cabinet": "Личный кабинет",
        "jetistik_alany": "Jetistik Alany",
        "rulebox": "RuleBox",
        "ai_tools": "AI Tools",
        
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
        "back": "Назад",
        "edit_profile": "Редактировать профиль",
        "save_changes": "Сохранить изменения",
        "profile_updated": "Профиль успешно обновлён",
        "delete_user": "Удалить пользователя",
        "user_deleted": "Пользователь успешно удалён",
        "cannot_delete_yourself": "Нельзя удалить самого себя",
        "user_not_found": "Пользователь не найден",
        "confirm_delete": "Вы уверены что хотите удалить этого пользователя? Все его достижения будут удалены!",
        "actions": "Действия",
        "select_category": "Выберите категорию",
        
        # Профиль
        "welcome_user": "Добро пожаловать",
        "total_points": "Всего баллов",
        "pending_achievements": "Ожидают проверки",
        "approved_achievements": "Подтверждено",
        "school": "Школа",
        "subject": "Предмет",
        "teacher_category": "Категория",
        "select_category": "Выберите категорию",
        "category_without": "Без категории",
        "category_second": "Педагог-модератор",
        "category_first": "Педагог-эксперт",
        "category_researcher": "Педагог-исследователь",
        "category_master": "Педагог-мастер",
        "experience": "Стаж в данной организации",
        
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
        "category_pedagogical_experience": "Обобщение педагогического опыта",
        "category_publications": "Публикации/Статьи",
        "category_methodical": "Методические пособия",
        
        # Категории для Qogam Serpin
        "category_methodical_leader": "Руководитель методического объединения",
        "category_social_events": "Участие в общественных мероприятиях",
        "category_volunteering": "Волонтёрство",
        
        # Категории для Tarbie Arnasy
        "category_class_management": "Классное руководство",
        "category_parent_voice": "Голос родителей",
        "category_specialist_cooperation": "Сотрудничество со специалистами",
        
        # Уровни
        "level_school": "Школьный",
        "level_city": "Городской",
        "level_regional": "Областной",
        "level_national": "Республиканский",
        "level_international": "Международный",
        "level_classroom": "Классный",
        
        # Стаж
        "years_experience": "Стаж работы",
        "years_0_1": "0-1 год",
        "years_1_2": "1-2 года",
        "years_2_3": "2-3 года",
        "years_3_plus": "3+ года",
        
        # Участие родителей
        "parent_participation": "Участие родителей",
        "participation_up_to_40": "До 40%",
        "participation_up_to_70": "До 70%",
        "participation_up_to_90": "До 90%",
        
        # Статусы
        "status_pending": "Ожидает",
        "status_approved": "Подтверждено",
        "status_rejected": "Отклонено",
        
        # Рейтинг
        "top_teachers_subtitle": "Топ-10 учителей",
        "rank": "Место",
        "teacher": "Учитель",
        "reports": "Рейтинг",
        "school_ratings": "Рейтинг школ",
        "total_teachers": "Всего учителей",
        "rating_title": "Рейтинг педагогов",
        "no_rating_data": "Нет данных для рейтинга",
        "year": "год",
        "years": "лет",
        "no_pending": "в ожидании",
        
        # Админ
        "admin_panel": "Админ-панель",
        "all_users": "Все пользователи",
        "create_user": "Создать пользователя",
        "pending_review": "На проверке",
        "approved": "Утверждено",
        "rejected": "Отказано",
        "moderate": "Рейтинг",
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
        "rulebox_subtitle": "Педагогтарға арналған нормативтік құжаттар",
        "attestation_rules": "Педагогтарды аттестаттау ережелері",
        "attestation_rules_desc": "ҚР Білім және ғылым министрінің 2016 жылғы 27 қаңтардағы № 83 бұйрығы",
        "curriculum_plans": "Үлгілік оқу жоспарлары",
        "curriculum_plans_desc": "ҚР Білім және ғылым министрінің 2012 жылғы 8 қарашадағы № 500 бұйрығы",
        "teacher_status": "Педагог мәртебесі туралы",
        "teacher_status_desc": "Қазақстан Республикасының Заңы 2019 жылғы 27 желтоқсандағы № 293-VІ ҚРЗ",
        "qualification_characteristics": "Педагог лауазымдарының біліктілік сипаттамалары",
        "qualification_characteristics_desc": "ҚР БҒМ 2009 жылғы 13 шілдедегі № 338 бұйрығы",
        "prohibited_items": "Тыйым салынған заттар мен заттардың тізімі",
        "prohibited_items_desc": "ҚР БҒМ 2021 жылғы 25 мамырдағы № 235 бұйрығы",
        "antiterror_protection": "Нысандардың антитеррорлық қорғанысы",
        "antiterror_protection_desc": "ҚР Ағарту министрінің 2023 жылғы 31 шілдедегі № 237 бұйрығы",
        "classroom_management": "Сынып жетекшілігі туралы ереже",
        "classroom_management_desc": "ҚР БҒМ м.а. 2022 жылғы 31 мамырдағы № 251 бұйрығы",
        "education_law": "Білім туралы заң",
        "education_law_desc": "ҚР 2007 жылғы 27 шілдедегі № 319-III Заңы",
        "psycho_pedagogical_support": "Психологиялық-педагогикалық сүйемелдеу қызметі",
        "psycho_pedagogical_support_desc": "ҚР Ағарту министрінің 2025 жылғы 29 сәуірдегі № 92 бұйрығы",
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
        "back": "Артқа",
        "edit_profile": "Профильді өңдеу",
        "save_changes": "Өзгерістерді сақтау",
        "profile_updated": "Профиль сәтті жаңартылды",
        "delete_user": "Пайдаланушыны жою",
        "user_deleted": "Пайдаланушы сәтті жойылды",
        "cannot_delete_yourself": "Өзіңізді жою мүмкін емес",
        "user_not_found": "Пайдаланушы табылмады",
        "confirm_delete": "Бұл пайдаланушыны жойғыңыз келетініне сенімдісіз бе? Оның барлық жетістіктері жойылады!",
        "actions": "Әрекеттер",
        "select_category": "Санатты таңдаңыз",
        
        # Профиль
        "welcome_user": "Қош келдіңіз",
        "total_points": "Барлық ұпай",
        "pending_achievements": "Тексеруді күтуде",
        "approved_achievements": "Расталған",
        "school": "Мектеп",
        "subject": "Пән",
        "teacher_category": "Педагог санатты",
        "select_category": "Санатты таңдаңыз",
        "category_without": "Санатсыз",
        "category_second": "Педагог-модератор",
        "category_first": "Педагог-эксперт",
        "category_researcher": "Педагог-зерттеуші",
        "category_master": "Педагог-шебер",
        "experience": "Осы ұйымдағы еңбек өтілі",
        
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
        "category_pedagogical_experience": "Педагогикалық тәжірибе тарату",
        "category_publications": "Жарияланымдар/Мақалалар",
        "category_methodical": "Әдістемелік құралдар",
        
        # Qogam Serpin санаттары
        "category_methodical_leader": "Әдістемелік бірлестік жетекшісі",
        "category_social_events": "Қоғамдық іс-шараларға қатысу",
        "category_volunteering": "Еріктілік",
        
        # Tarbie Arnasy санаттары
        "category_class_management": "Сынып жетекшілік",
        "category_parent_voice": "Ата-аналар үні",
        "category_specialist_cooperation": "Мамандармен серіктестік",
        
        # Деңгейлер
        "level_school": "Мектептік",
        "level_city": "Қалалық",
        "level_regional": "Облыстық",
        "level_national": "Республикалық",
        "level_international": "Халықаралық",
        "level_classroom": "Сыныптық",
        
        # Еңбек өтілі
        "years_experience": "Еңбек өтілі",
        "years_0_1": "0-1 жыл",
        "years_1_2": "1-2 жыл",
        "years_2_3": "2-3 жыл",
        "years_3_plus": "3+ жыл",
        
        # Ата-аналар қатысуы
        "parent_participation": "Ата-аналар қатысуы",
        "participation_up_to_40": "40% дейін",
        "participation_up_to_70": "70% дейін",
        "participation_up_to_90": "90% дейін",
        
        # Мәртебелер
        "status_pending": "Күтуде",
        "status_approved": "Расталған",
        "status_rejected": "Қабылданбаған",
        
        # Рейтинг
        "top_teachers_subtitle": "Топ-10 мұғалімдер",
        "rank": "Орын",
        "teacher": "Мұғалім",
        "reports": "Нәтиже",
        "school_ratings": "Мектептер рейтингі",
        "total_teachers": "Барлық мұғалімдер",
        "rating_title": "Педагогтар рейтингі",
        "no_rating_data": "Рейтингке арналған деректер жоқ",
        "year": "жыл",
        "years": "жыл",
        "no_pending": "күтілуде",
        
        # Админ
        "admin_panel": "Админ панелі",
        "all_users": "Барлық қолданушылар",
        "create_user": "Қолданушы жасау",
        "pending_review": "Тексеруде",
        "approved": "Бекітілген",
        "rejected": "Қабылданбаған",
        "moderate": "Нәтиже",
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
@app.get("/forgot-password", response_class=HTMLResponse)
def forgot_password_page(request: Request, lang: str = Depends(get_language)):
    """Страница запроса восстановления пароля"""
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("forgot_password.html", {
        "request": request,
        "lang": lang,
        "t": t
    })


@app.post("/forgot-password")
def forgot_password_post(
    username: str = Form(...),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    """Обработка запроса восстановления пароля"""
    t = lambda key: get_translation(lang, key)
    
    # Найти пользователя
    user = db.query(User).filter(User.username == username).first()
    
    # Всегда показываем успех (защита от перебора логинов)
    if not user:
        return templates.TemplateResponse("forgot_password.html", {
            "request": {},
            "success": t("reset_link_sent") if t("reset_link_sent") != "reset_link_sent" else "Если пользователь существует, ссылка для восстановления создана",
            "lang": lang,
            "t": t
        })
    
    # Создать токен восстановления (действителен 1 час)
    reset_token = serializer.dumps(user.id, salt="password-reset")
    
    # ПОКАЗАТЬ ССЫЛКУ НА ЭКРАНЕ (без email!)
    reset_url = f"/reset-password/{reset_token}"
    
    return templates.TemplateResponse("forgot_password.html", {
        "request": {},
        "success": t("reset_link_created") if t("reset_link_created") != "reset_link_created" else "Ссылка для восстановления пароля создана!",
        "reset_link": reset_url,
        "lang": lang,
        "t": t
    })


@app.get("/reset-password/{token}", response_class=HTMLResponse)
def reset_password_page(
    token: str,
    request: Request,
    lang: str = Depends(get_language)
):
    """Страница установки нового пароля"""
    t = lambda key: get_translation(lang, key)
    
    try:
        # Проверить токен (действителен 1 час)
        user_id = serializer.loads(token, salt="password-reset", max_age=3600)
        
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "token": token,
            "lang": lang,
            "t": t
        })
        
    except:
        return templates.TemplateResponse("reset_password.html", {
            "request": request,
            "error": t("reset_token_invalid") if t("reset_token_invalid") != "reset_token_invalid" else "Ссылка недействительна или истекла. Запросите новую ссылку.",
            "lang": lang,
            "t": t
        })


@app.post("/reset-password/{token}")
def reset_password_post(
    token: str,
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    """Обработка установки нового пароля"""
    t = lambda key: get_translation(lang, key)
    
    try:
        # Проверить токен
        user_id = serializer.loads(token, salt="password-reset", max_age=3600)
        
    except:
        return templates.TemplateResponse("reset_password.html", {
            "request": {},
            "token": token,
            "error": t("reset_token_invalid") if t("reset_token_invalid") != "reset_token_invalid" else "Ссылка недействительна или истекла",
            "lang": lang,
            "t": t
        })
    
    # Проверки
    error = None
    if len(new_password) < 6:
        error = t("error_short_password")
    elif new_password != confirm_password:
        error = t("error_passwords_dont_match")
    
    if error:
        return templates.TemplateResponse("reset_password.html", {
            "request": {},
            "token": token,
            "error": error,
            "lang": lang,
            "t": t
        })
    
    # Найти пользователя и обновить пароль
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return templates.TemplateResponse("reset_password.html", {
            "request": {},
            "token": token,
            "error": t("user_not_found") if t("user_not_found") != "user_not_found" else "Пользователь не найден",
            "lang": lang,
            "t": t
        })
    
    # Обновить пароль
    user.password_hash = hash_password(new_password)
    db.commit()
    
    # Перенаправить на страницу входа с сообщением
    return RedirectResponse(url="/login?success=password_reset", status_code=303)

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


@app.get("/edit-profile", response_class=HTMLResponse)
def edit_profile_page(
    request: Request,
    user: User = Depends(get_current_user),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    t = lambda key: get_translation(lang, key)
    return templates.TemplateResponse("edit_profile.html", {
        "request": request,
        "user": user,
        "lang": lang,
        "t": t
    })


@app.post("/update-profile")
def update_profile(
    request: Request,
    full_name: str = Form(...),
    school: str = Form(""),
    subject: str = Form(""),
    teacher_category: str = Form(""),
    experience: int = Form(0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    # Обновить данные пользователя
    user.full_name = full_name
    user.school = school
    user.subject = subject
    user.teacher_category = teacher_category
    user.experience = experience
    
    db.commit()
    
    return RedirectResponse(url="/edit-profile?success=updated", status_code=303)


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
    
    # Рассчитать баллы для каждого пользователя и отсортировать
    user_data = []
    for u in all_users:
        total_points = sum(ach.points for ach in u.achievements if ach.status == 'approved')
        user_data.append({
            'user': u,
            'points': total_points
        })
    
    # Сортировка по баллам (от большего к меньшему)
    user_data.sort(key=lambda x: x['points'], reverse=True)
    
    return templates.TemplateResponse("admin.html", {
        "request": request,
        "user": user,
        "user_data": user_data,  # Передаём отсортированные данные
        "pending_achievements": pending_achievements,
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
    """Страница модерации с рейтингом внизу"""
    if not user or not user.is_admin:
        return RedirectResponse(url="/home")
    
    t = lambda key: get_translation(lang, key)
    
    # Получить все достижения
    pending_achievements = db.query(Achievement).filter(
        Achievement.status == "pending"
    ).order_by(Achievement.created_at.desc()).all()
    
    approved_achievements = db.query(Achievement).filter(
        Achievement.status == "approved"
    ).order_by(Achievement.created_at.desc()).all()
    
    rejected_achievements = db.query(Achievement).filter(
        Achievement.status == "rejected"
    ).order_by(Achievement.created_at.desc()).all()
    
    # ============================================
    # РЕЙТИНГ ТОП-10 (для отображения внизу)
    # ============================================
    
    all_users = db.query(User).all()
    
    user_data = []
    for u in all_users:
        total_points = sum(ach.points for ach in u.achievements if ach.status == 'approved')
        user_data.append({
            'user': u,
            'points': total_points
        })
    
    user_data.sort(key=lambda x: x['points'], reverse=True)
    top_teachers = user_data[:10]
    
    # ============================================
    
    return templates.TemplateResponse("moderate.html", {
        "request": request,
        "user": user,
        "pending_achievements": pending_achievements,
        "approved_achievements": approved_achievements,
        "rejected_achievements": rejected_achievements,
        "pending_count": len(pending_achievements),
        "approved_count": len(approved_achievements),
        "rejected_count": len(rejected_achievements),
        "top_teachers": top_teachers,  # ← ДЛЯ РЕЙТИНГА
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
    
    # Только админ может видеть отчеты
    if not user.is_admin:
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
    years_experience: str = Form(None),
    parent_participation: str = Form(None),
    file: Optional[UploadFile] = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    lang: str = Depends(get_language)
):
    if not user:
        return RedirectResponse(url="/login")
    
    # Расчёт баллов
    calculated_points = 0
    
    # Для Oqushy Status и Sapa Qorzhyn - расчет по уровню и месту
    if achievement_type in ['oqushy_status', 'sapa_qorzhyn'] and level and place:
        points_table = {
            'city': {'1': 35, '2': 30, '3': 25, 'certificate': 10},
            'regional': {'1': 40, '2': 35, '3': 30, 'certificate': 15},
            'national': {'1': 45, '2': 40, '3': 35, 'certificate': 20},
            'international': {'1': 50, '2': 45, '3': 40, 'certificate': 25}
        }
        calculated_points = points_table.get(level, {}).get(place, 0)
    
    # Для Qogam Serpin
    elif achievement_type == 'qogam_serpin':
        if category == 'methodical_leader' and years_experience:
            # Руководитель МО - по стажу
            years_points = {
                '0_1': 10,
                '1_2': 15,
                '2_3': 20,
                '3_plus': 25
            }
            calculated_points = years_points.get(years_experience, 0)
        elif category == 'social_events' and level:
            # Общественные мероприятия - по уровню
            level_points = {
                'city': 10,
                'regional': 15,
                'national': 20
            }
            calculated_points = level_points.get(level, 0)
        elif category == 'volunteering' and level:
            # Волонтерство - по уровню
            level_points = {
                'city': 25,
                'regional': 30,
                'national': 35
            }
            calculated_points = level_points.get(level, 0)
    
    # Для Tarbie Arnasy
    elif achievement_type == 'tarbie_arnasy':
        if category == 'class_management' and years_experience:
            # Классное руководство - по стажу
            years_points = {
                '0_1': 10,
                '1_2': 15,
                '2_3': 20,
                '3_plus': 25
            }
            calculated_points = years_points.get(years_experience, 0)
        elif category == 'parent_voice' and parent_participation:
            # Голос родителей - по % участия
            participation_points = {
                'up_to_40': 10,
                'up_to_70': 20,
                'up_to_90': 30
            }
            calculated_points = participation_points.get(parent_participation, 0)
        elif category == 'specialist_cooperation':
            # Сотрудничество со специалистами - фиксированно
            calculated_points = 10
    
    file_path = None
    if file and file.filename:
        content = await file.read()
        if len(content) > 10 * 1024 * 1024:  # Увеличил лимит до 10 MB
            t = lambda key: get_translation(lang, key)
            return RedirectResponse(url=f"/{achievement_type.replace('_', '-')}?error=file_too_large", status_code=303)
        
        file_ext = file.filename.split(".")[-1].lower()  # ← ИСПРАВЛЕН ОТСТУП!
        
        # Загрузить в Cloudinary
        try:
            # ДОБАВИТЬ РАСШИРЕНИЕ В PUBLIC_ID!
            public_id = f"jetistik_hub/{uuid.uuid4()}.{file_ext}"  # ← С РАСШИРЕНИЕМ!
            
            # Определить тип файла
            if file_ext == 'pdf':
                resource_type = "raw"  # PDF загружается как raw
            else:
                resource_type = "image"  # Картинки как image
            
            file_stream = BytesIO(content)  # ← Создать file-like объект
            file_stream.seek(0)
            
            upload_result = cloudinary.uploader.upload(
                file_stream,
                public_id=public_id,
                resource_type=resource_type
            )
            
            file_path = upload_result['secure_url']
            print(f"✅ File uploaded to Cloudinary: {file_path} (type: {resource_type})")
            
        except Exception as e:
            print(f"❌ Cloudinary upload error: {e}")
            t = lambda key: get_translation(lang, key)
            return RedirectResponse(url=f"/{achievement_type.replace('_', '-')}?error=upload_failed", status_code=303)
            
            with open(local_path, "wb") as f:
                f.write(content)
            
            file_path = f"/uploads/{unique_filename}"
            print(f"📁 File saved locally (fallback): {file_path}")
    
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
    

@app.post("/delete-user/{user_id}")
def delete_user(
    user_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not user or not user.is_admin:
        return RedirectResponse(url="/home", status_code=303)
    
    user_to_delete = db.query(User).filter(User.id == user_id).first()
    
    if not user_to_delete:
        return RedirectResponse(url="/admin?error=user_not_found", status_code=303)
    
    if user_to_delete.id == user.id:
        return RedirectResponse(url="/admin?error=cannot_delete_yourself", status_code=303)
    
    # Удалить достижения
    db.query(Achievement).filter(Achievement.user_id == user_id).delete()
    
    # Удалить пользователя
    db.delete(user_to_delete)
    db.commit()
    
    return RedirectResponse(url="/admin?success=user_deleted", status_code=303)
    
# ===========================
# MAKE ADMIN ROUTE
# ===========================
@app.get("/make-me-admin", response_class=HTMLResponse)
def make_me_admin(
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Простой маршрут: делает текущего пользователя админом"""
    if not user:
        return RedirectResponse(url="/login")
    
    # Сделать пользователя админом
    user.is_admin = True
    db.commit()
    db.refresh(user)
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>✅ Вы теперь админ!</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
                margin: 0;
                padding: 20px;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                max-width: 600px;
                text-align: center;
            }}
            h1 {{
                color: #7030A0;
                font-size: 2.5rem;
                margin-bottom: 20px;
            }}
            .icon {{
                font-size: 5rem;
                margin: 20px 0;
            }}
            .info {{
                background: #f0f7ff;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: left;
            }}
            .btn {{
                display: inline-block;
                padding: 15px 40px;
                margin: 10px;
                border-radius: 50px;
                text-decoration: none;
                font-weight: bold;
                font-size: 1.1rem;
                background: #7030A0;
                color: white;
            }}
            .btn:hover {{
                background: #5a2680;
            }}
            ol {{
                text-align: left;
                margin: 20px auto;
                max-width: 400px;
            }}
            ol li {{
                margin: 10px 0;
                font-size: 1.1rem;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="icon">👑</div>
            <h1>Вы теперь админ!</h1>
            
            <div class="info">
                <strong>Пользователь:</strong> {user.username}<br>
                <strong>ФИО:</strong> {user.full_name or "Не указано"}<br>
                <strong>Статус:</strong> <span style="color: #FFD700; font-weight: bold;">👑 АДМИНИСТРАТОР</span>
            </div>
            
            <p><strong>Что дальше:</strong></p>
            <ol>
                <li>Выйдите из системы</li>
                <li>Войдите заново</li>
                <li>В меню появятся админские функции</li>
            </ol>
            
            <a href="/logout" class="btn">🚪 Выйти</a>
            <a href="/home" class="btn" style="background: #666;">🏠 На главную</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
