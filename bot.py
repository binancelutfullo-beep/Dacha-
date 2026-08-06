"""
Dacha bron qilish Telegram bot
+ Admin panel, Qo'llab-quvvatlash paneli, Dacha egalari tizimi (shartnoma + 1% komissiya)
Til: O'zbek / Rus (foydalanuvchi uchun) | Admin panel: O'zbek
Kutubxona: aiogram 3.x, reportlab (PDF shartnoma uchun)
Ma'lumotlar: dachas.json, bookings.json, support.json, support_messages.json, owners.json
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

# ============ SOZLAMALAR ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ_BU_YERGA")
ADMIN_IDS = [x.strip() for x in os.getenv("ADMIN_IDS", os.getenv("ADMIN_CHAT_ID", "")).split(",") if x.strip()]
COMMISSION_RATE = 0.01  # 1%

DACHAS_FILE = "dachas.json"
BOOKINGS_FILE = "bookings.json"
SUPPORT_FILE = "support.json"
SUPPORT_MSG_FILE = "support_messages.json"
OWNERS_FILE = "owners.json"
CONTRACTS_DIR = "contracts"

logging.basicConfig(level=logging.INFO)

# ============ BOSHLANG'ICH MA'LUMOTLAR ============
DEFAULT_DACHAS = {
    "dacha_1": {
        "name_uz": "🏡 Chimyon dachasi",
        "name_ru": "🏡 Дача Чимган",
        "desc_uz": "3 xonali, basseyn, mangal, 8 kishi uchun.",
        "desc_ru": "3 комнаты, бассейн, мангал, до 8 человек.",
        "price": 800000,
        "owner_id": None,
        "owner_name": None,
    },
    "dacha_2": {
        "name_uz": "🌲 Bo'stonliq dachasi",
        "name_ru": "🌲 Дача Бустанлык",
        "desc_uz": "2 xonali, tog' manzarasi, 5 kishi uchun.",
        "desc_ru": "2 комнаты, вид на горы, до 5 человек.",
        "price": 500000,
        "owner_id": None,
        "owner_name": None,
    },
}

DEFAULT_SUPPORT = {
    "s_1": {
        "title": "📞 Aloqa uchun",
        "text": "Operator bilan bog'lanish uchun quyidagi tugmadan foydalaning yoki +998 90 000 00 00 raqamiga qo'ng'iroq qiling.",
    },
}

TEXTS = {
    "uz": {
        "choose_lang": "Tilni tanlang / Выберите язык:",
        "welcome": "Assalomu alaykum! Dacha bron qilish botiga xush kelibsiz. 🏡\n\nPastdagi menyudan foydalaning:",
        "menu_list": "📋 Dachalar ro'yxati",
        "menu_my": "🗂 Mening bronlarim",
        "menu_support": "🆘 Yordam",
        "menu_admin": "🔐 Admin panel",
        "menu_owner": "🏘 Mening dachalarim",
        "menu_owner_apply": "🏘 Dacha egasi bo'lish",
        "choose_dacha": "Dachani tanlang:",
        "back": "⬅️ Orqaga",
        "book_btn": "✅ Shu dachani bron qilish",
        "ask_checkin": "Kirish sanasini kiriting (masalan: 15.08.2026):",
        "ask_checkout": "Chiqish sanasini kiriting (masalan: 18.08.2026):",
        "ask_name": "Ismingizni kiriting:",
        "ask_phone": "Telefon raqamingizni kiriting (masalan: +998901234567):",
        "invalid_date": "❌ Sana noto'g'ri formatda. Masalan: 15.08.2026 shaklida kiriting.",
        "invalid_date_order": "❌ Chiqish sanasi kirish sanasidan keyin bo'lishi kerak.",
        "invalid_phone": "❌ Telefon raqami noto'g'ri. Masalan: +998901234567",
        "confirm": "Bronni tasdiqlaysizmi?\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}",
        "commission_info": "\n\n💰 Taxminiy summa: {total:,} so'm ({nights} kecha)\n📊 Platforma komissiyasi (1%): {commission:,} so'm",
        "confirm_yes": "✅ Tasdiqlash",
        "confirm_no": "❌ Bekor qilish",
        "booked": "🎉 Bronlash muvaffaqiyatli qabul qilindi! Tez orada operator siz bilan bog'lanadi.",
        "cancelled": "Bekor qilindi.",
        "no_bookings": "Sizda hozircha bronlar yo'q.",
        "your_bookings": "🗂 Sizning bronlaringiz:\n\n",
        "no_dachas_user": "Hozircha dachalar mavjud emas.",
        "new_admin_booking": "🆕 Yangi bron!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}\n💰 Summa: {total:,} so'm | Komissiya: {commission:,} so'm\n🆔 User: {user_id}",
        "new_owner_booking": "🆕 Sizning dachangiz bron qilindi!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}  📞 {phone}\n\n💰 Umumiy summa: {total:,} so'm\n📊 Platforma komissiyasi (1%): {commission:,} so'm\n💵 Sizga tegishli: {net:,} so'm",
        "support_title": "Quyidagi ma'lumotlardan foydalaning yoki operatorga yozing:",
        "write_support": "✍️ Operatorga xabar yozish",
        "no_support_info": "Hozircha ma'lumot yo'q.",
        "ask_support_msg": "Xabaringizni yozing, operatorga yuboramiz:",
        "support_sent": "✅ Xabaringiz yuborildi! Tez orada operator javob beradi.",
        "support_reply_prefix": "💬 Operatordan javob:\n\n",
        "new_support_msg_admin": "🆘 Yangi murojaat!\n\n👤 {name} (@{username})\n💬 {text}",
        # --- Dacha egalari ---
        "not_owner": "⛔️ Siz hali tasdiqlangan dacha egasi emassiz. Avval \"🏘 Dacha egasi bo'lish\" orqali ariza yuboring.",
        "owner_already_pending": "⏳ So'rovingiz hozircha ko'rib chiqilmoqda. Iltimos, kuting.",
        "owner_apply_sent": "✅ So'rovingiz yuborildi! Admin tasdiqlagach sizga xabar beramiz.",
        "owner_approved_msg": "🎉 Tabriklaymiz! Sizga dacha egasi huquqi berildi.\n\nEndi pastdagi \"🏘 Mening dachalarim\" tugmasi orqali dacha qo'sha olasiz.",
        "owner_rejected_msg": "❌ Afsuski, dacha egasi bo'lish so'rovingiz rad etildi.",
        "owner_panel_title": "🏘 Mening dachalarim paneli. Nima qilmoqchisiz?",
        "owner_btn_add": "➕ Yangi dacha qo'shish",
        "owner_btn_manage": "✏️ Dachalarimni boshqarish",
        "owner_manage_title": "Tahrirlash yoki o'chirish uchun dachani tanlang:",
        "owner_no_dachas": "Sizda hozircha dachalar yo'q. \"➕ Yangi dacha qo'shish\" orqali qo'shing.",
        "contract_text": (
            "📜 SHARTNOMA (Dacha egasi bilan)\n\n"
            "1. Siz o'z dachangizni ushbu bot orqali mehmonlarga bron qilish uchun joylashtirasiz.\n"
            "2. Bot orqali amalga oshirilgan har bir bron uchun umumiy summadan 1% (bir foiz) miqdorida "
            "xizmat haqi (komissiya) Platformaga to'lanadi.\n"
            "3. Siz kiritgan ma'lumotlar (narx, tavsif, dacha holati) to'g'ri bo'lishi uchun javobgarsiz.\n"
            "4. Platforma faqat bron qilish jarayonini osonlashtiradi, mehmon bilan bo'ladigan "
            "kelishuvlar uchun javobgar emas.\n"
            "5. \"✅ Roziman\" tugmasini bosish orqali siz yuqoridagi shartlarni to'liq qabul qilasiz "
            "(elektron rozilik).\n\n"
            "Davom etishni xohlaysizmi?"
        ),
        "contract_agree": "✅ Roziman",
        "contract_decline": "❌ Rad etaman",
        "contract_declined_msg": "Bekor qilindi. Xohlagan vaqtingizda qaytadan urinib ko'rishingiz mumkin.",
        "ask_owner_name_uz": "1/5. Dacha nomini o'zbek tilida kiriting (masalan: 🏡 Mening dacham):",
        "ask_owner_name_ru": "2/5. Endi nomini rus tilida kiriting:",
        "ask_owner_desc_uz": "3/5. Tavsifni o'zbek tilida kiriting (xonalar soni, qulayliklar va h.k.):",
        "ask_owner_desc_ru": "4/5. Tavsifni rus tilida kiriting:",
        "ask_price": "5/5. Bir kechalik narxni faqat raqamlarda kiriting (masalan: 800000):",
        "invalid_price": "❌ Narx faqat raqamlardan iborat bo'lishi kerak. Masalan: 800000",
        "dacha_added_owner": "✅ Dachangiz qo'shildi va ro'yxatda ko'rinadi! Shartnoma PDF fayli sifatida yuborildi — uni saqlab qo'ying.",
    },
    "ru": {
        "choose_lang": "Tilni tanlang / Выберите язык:",
        "welcome": "Здравствуйте! Добро пожаловать в бот бронирования дач. 🏡\n\nИспользуйте меню внизу:",
        "menu_list": "📋 Список дач",
        "menu_my": "🗂 Мои брони",
        "menu_support": "🆘 Поддержка",
        "menu_admin": "🔐 Админ панель",
        "menu_owner": "🏘 Мои дачи",
        "menu_owner_apply": "🏘 Стать владельцем дачи",
        "choose_dacha": "Выберите дачу:",
        "back": "⬅️ Назад",
        "book_btn": "✅ Забронировать эту дачу",
        "ask_checkin": "Введите дату заезда (например: 15.08.2026):",
        "ask_checkout": "Введите дату выезда (например: 18.08.2026):",
        "ask_name": "Введите ваше имя:",
        "ask_phone": "Введите номер телефона (например: +998901234567):",
        "invalid_date": "❌ Неверный формат даты. Пример: 15.08.2026",
        "invalid_date_order": "❌ Дата выезда должна быть позже даты заезда.",
        "invalid_phone": "❌ Неверный номер телефона. Пример: +998901234567",
        "confirm": "Подтвердить бронь?\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}",
        "commission_info": "\n\n💰 Примерная сумма: {total:,} сум ({nights} ночей)\n📊 Комиссия платформы (1%): {commission:,} сум",
        "confirm_yes": "✅ Подтвердить",
        "confirm_no": "❌ Отменить",
        "booked": "🎉 Бронь успешно оформлена! Скоро с вами свяжется оператор.",
        "cancelled": "Отменено.",
        "no_bookings": "У вас пока нет броней.",
        "your_bookings": "🗂 Ваши брони:\n\n",
        "no_dachas_user": "Пока нет доступных дач.",
        "new_admin_booking": "🆕 Новая бронь!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}\n💰 Сумма: {total:,} сум | Комиссия: {commission:,} сум\n🆔 User: {user_id}",
        "new_owner_booking": "🆕 Ваша дача забронирована!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}  📞 {phone}\n\n💰 Общая сумма: {total:,} сум\n📊 Комиссия платформы (1%): {commission:,} сум\n💵 Вам причитается: {net:,} сум",
        "support_title": "Используйте информацию ниже или напишите оператору:",
        "write_support": "✍️ Написать оператору",
        "no_support_info": "Пока нет информации.",
        "ask_support_msg": "Напишите ваше сообщение, мы передадим оператору:",
        "support_sent": "✅ Сообщение отправлено! Скоро оператор ответит.",
        "support_reply_prefix": "💬 Ответ оператора:\n\n",
        "new_support_msg_admin": "🆘 Новое обращение!\n\n👤 {name} (@{username})\n💬 {text}",
        # --- Владельцы дач ---
        "not_owner": "⛔️ Вы ещё не подтверждённый владелец дачи. Сначала отправьте заявку через \"🏘 Стать владельцем дачи\".",
        "owner_already_pending": "⏳ Ваша заявка ещё рассматривается. Пожалуйста, подождите.",
        "owner_apply_sent": "✅ Заявка отправлена! Сообщим вам, как только админ её рассмотрит.",
        "owner_approved_msg": "🎉 Поздравляем! Вам предоставлены права владельца дачи.\n\nТеперь вы можете добавить дачу через кнопку \"🏘 Мои дачи\" внизу.",
        "owner_rejected_msg": "❌ К сожалению, ваша заявка на статус владельца дачи отклонена.",
        "owner_panel_title": "🏘 Панель моих дач. Что хотите сделать?",
        "owner_btn_add": "➕ Добавить новую дачу",
        "owner_btn_manage": "✏️ Управлять моими дачами",
        "owner_manage_title": "Выберите дачу для редактирования или удаления:",
        "owner_no_dachas": "У вас пока нет дач. Добавьте через \"➕ Добавить новую дачу\".",
        "contract_text": (
            "📜 ДОГОВОР (с владельцем дачи)\n\n"
            "1. Вы размещаете свою дачу через этот бот для бронирования гостями.\n"
            "2. За каждую бронь, оформленную через бот, взимается комиссия платформы в размере "
            "1% (один процент) от общей суммы.\n"
            "3. Вы несёте ответственность за достоверность указанных данных (цена, описание, состояние дачи).\n"
            "4. Платформа только упрощает процесс бронирования и не несёт ответственности за "
            "договорённости между гостем и владельцем дачи.\n"
            "5. Нажимая \"✅ Согласен\", вы полностью принимаете вышеуказанные условия (электронное согласие).\n\n"
            "Хотите продолжить?"
        ),
        "contract_agree": "✅ Согласен",
        "contract_decline": "❌ Не согласен",
        "contract_declined_msg": "Отменено. Вы можете попробовать снова в любое время.",
        "ask_owner_name_uz": "1/5. Введите название дачи на узбекском (например: 🏡 Моя дача):",
        "ask_owner_name_ru": "2/5. Теперь введите название на русском:",
        "ask_owner_desc_uz": "3/5. Введите описание на узбекском (кол-во комнат, удобства и т.д.):",
        "ask_owner_desc_ru": "4/5. Введите описание на русском:",
        "ask_price": "5/5. Введите цену за ночь только цифрами (например: 800000):",
        "invalid_price": "❌ Цена должна состоять только из цифр. Например: 800000",
        "dacha_added_owner": "✅ Ваша дача добавлена и появится в списке! Договор отправлен файлом PDF — сохраните его.",
    },
}

# Admin panel matnlari (o'zbek tilida)
A = {
    "panel_title": "🔐 Admin panel. Nima qilmoqchisiz?",
    "btn_add": "➕ Yangi dacha qo'shish",
    "btn_manage": "✏️ Dachalarni boshqarish",
    "btn_bookings": "📋 Bronlarni ko'rish",
    "btn_support": "🆘 Qo'llab-quvvatlash",
    "back": "⬅️ Orqaga",
    "ask_name_uz": "1/5. Dacha nomini o'zbek tilida kiriting (masalan: 🏡 Chimyon dachasi):",
    "ask_name_ru": "2/5. Endi nomini rus tilida kiriting:",
    "ask_desc_uz": "3/5. Tavsifni o'zbek tilida kiriting:",
    "ask_desc_ru": "4/5. Tavsifni rus tilida kiriting:",
    "ask_price": "5/5. Bir kechalik narxni faqat raqamlarda kiriting (masalan: 800000):",
    "invalid_price": "❌ Narx faqat raqamlardan iborat bo'lishi kerak. Masalan: 800000",
    "added": "✅ Yangi dacha qo'shildi!",
    "manage_title": "Tahrirlash yoki o'chirish uchun dachani tanlang:",
    "edit_btn": "✏️ Tahrirlash",
    "delete_btn": "🗑 O'chirish",
    "edit_choose_field": "«{name}» — qaysi maydonni tahrirlaysiz?",
    "field_name_uz": "📝 Nomi (UZ)",
    "field_name_ru": "📝 Nomi (RU)",
    "field_desc_uz": "📝 Tavsif (UZ)",
    "field_desc_ru": "📝 Tavsif (RU)",
    "field_price": "💰 Narxi",
    "ask_new_value": "Yangi qiymatni kiriting:\n\nHozirgi: {old}",
    "updated": "✅ Yangilandi!",
    "delete_confirm": "❗️ «{name}» dachasini rostdan ham o'chirmoqchimisiz? Bu amalni orqaga qaytarib bo'lmaydi.",
    "delete_yes": "✅ Ha, o'chirish",
    "delete_no": "❌ Yo'q, bekor qilish",
    "deleted": "🗑 Dacha o'chirildi.",
    "no_dachas": "Hozircha dachalar yo'q. Avval yangi dacha qo'shing.",
    "not_admin": "⛔️ Sizda admin huquqi yo'q.",
    "bookings_title": "📋 Barcha bronlar ({count} ta):",
    "booking_item": "🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}  📞 {phone}\n🆔 @{username}",
    "no_bookings_admin": "Hozircha bronlar yo'q.",
    "booking_deleted": "🗑 Bron o'chirildi.",
    # --- Support ---
    "support_panel_title": "🆘 Qo'llab-quvvatlash paneli. Nima qilmoqchisiz?",
    "btn_support_add": "➕ Yangi ma'lumot qo'shish",
    "btn_support_manage": "✏️ Ma'lumotlarni boshqarish",
    "btn_support_inbox": "📨 Kelgan xabarlar",
    "ask_support_title": "1/2. Sarlavha kiriting (masalan: Ish vaqti):",
    "ask_support_text": "2/2. Matnni kiriting:",
    "support_added": "✅ Ma'lumot qo'shildi!",
    "support_manage_title": "Tahrirlash yoki o'chirish uchun tanlang:",
    "support_edit_choose_field": "«{title}» — nimani tahrirlaysiz?",
    "field_title": "📝 Sarlavha",
    "field_text": "📝 Matn",
    "support_ask_new_value": "Yangi qiymatni kiriting:\n\nHozirgi: {old}",
    "support_updated": "✅ Yangilandi!",
    "support_delete_confirm": "❗️ «{title}»ni rostdan ham o'chirmoqchimisiz?",
    "support_deleted": "🗑 O'chirildi.",
    "no_support_items": "Hozircha ma'lumotlar yo'q. Avval yangisini qo'shing.",
    "inbox_title": "📨 Murojaatlar ({count} ta):",
    "inbox_item": "👤 {name} (@{username})\n💬 {text}\n🕐 {time}{status}",
    "inbox_answered_tag": "\n✅ Javob berilgan",
    "reply_btn": "↩️ Javob berish",
    "ask_reply": "Javobingizni yozing, foydalanuvchiga yuboramiz:",
    "reply_sent": "✅ Javob yuborildi!",
    "reply_send_failed": "⚠️ Javob saqlandi, lekin foydalanuvchiga yuborib bo'lmadi (u botni bloklagan bo'lishi mumkin).",
    "no_tickets": "Hozircha murojaatlar yo'q.",
    "ticket_not_found": "Bu murojaat topilmadi (o'chirilgan bo'lishi mumkin).",
    # --- Dacha egalari (admin tomoni) ---
    "owner_app_notify": "🏘 Yangi dacha egasi so'rovi!\n\n👤 {name}\n📞 {phone}\n🆔 {user_id}",
    "owner_approve_btn": "✅ Tasdiqlash",
    "owner_reject_btn": "❌ Rad etish",
    "owner_approved_admin": "\n\n✅ Tasdiqlandi.",
    "owner_rejected_admin": "\n\n❌ Rad etildi.",
}

router = Router()


# ============ HOLATLAR (FSM) ============
class BookingStates(StatesGroup):
    entering_checkin = State()
    entering_checkout = State()
    entering_name = State()
    entering_phone = State()
    confirming = State()


class AdminStates(StatesGroup):
    adding_name_uz = State()
    adding_name_ru = State()
    adding_desc_uz = State()
    adding_desc_ru = State()
    adding_price = State()
    editing_value = State()


class SupportStates(StatesGroup):
    entering_message = State()


class SupportAdminStates(StatesGroup):
    adding_title = State()
    adding_text = State()
    editing_value = State()
    replying = State()


class OwnerApplyStates(StatesGroup):
    entering_name = State()
    entering_phone = State()


class OwnerAddStates(StatesGroup):
    name_uz = State()
    name_ru = State()
    desc_uz = State()
    desc_ru = State()
    price = State()


# ============ MA'LUMOTLAR BILAN ISHLASH ============
def _load(path: str, default):
    if not os.path.exists(path):
        _save(path, default)
        return json.loads(json.dumps(default))
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_dachas() -> dict:
    return _load(DACHAS_FILE, DEFAULT_DACHAS)


def save_dachas(dachas: dict):
    _save(DACHAS_FILE, dachas)


def load_bookings() -> list:
    return _load(BOOKINGS_FILE, [])


def save_bookings(bookings: list):
    _save(BOOKINGS_FILE, bookings)


def add_booking(booking: dict):
    bookings = load_bookings()
    bookings.append(booking)
    save_bookings(bookings)


def load_support() -> dict:
    return _load(SUPPORT_FILE, DEFAULT_SUPPORT)


def save_support(items: dict):
    _save(SUPPORT_FILE, items)


def load_tickets() -> list:
    return _load(SUPPORT_MSG_FILE, [])


def save_tickets(tickets: list):
    _save(SUPPORT_MSG_FILE, tickets)


def add_ticket(ticket: dict):
    tickets = load_tickets()
    tickets.append(ticket)
    save_tickets(tickets)


def load_owners() -> dict:
    return _load(OWNERS_FILE, {})


def save_owners(owners: dict):
    _save(OWNERS_FILE, owners)


def is_admin(user_id: int) -> bool:
    return str(user_id) in ADMIN_IDS


def is_approved_owner(user_id: int) -> bool:
    owners = load_owners()
    rec = owners.get(str(user_id))
    return bool(rec and rec.get("status") == "approved")


def can_manage_dacha(user_id: int, dacha: dict) -> bool:
    return is_admin(user_id) or dacha.get("owner_id") == user_id


def manage_list_cb(user_id: int) -> str:
    return "admin_manage" if is_admin(user_id) else "owner_manage"


def get_lang(data: dict) -> str:
    return data.get("lang", "uz")


def generate_contract_pdf(owner_name: str, dacha_name: str, price: int) -> str:
    os.makedirs(CONTRACTS_DIR, exist_ok=True)
    path = os.path.join(CONTRACTS_DIR, f"shartnoma_{uuid.uuid4().hex[:8]}.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4)
    styles = getSampleStyleSheet()
    story = [
        Paragraph("SHARTNOMA", styles["Title"]),
        Spacer(1, 10),
        Paragraph(f"Sana: {datetime.now().strftime('%d.%m.%Y')}", styles["Normal"]),
        Paragraph(f"Dacha egasi: {owner_name}", styles["Normal"]),
        Paragraph(f"Dacha nomi: {dacha_name}", styles["Normal"]),
        Paragraph(f"Bir kechalik narx: {price:,} so'm".replace(",", " "), styles["Normal"]),
        Spacer(1, 14),
        Paragraph("Shartlar:", styles["Heading2"]),
    ]
    terms = [
        "1. Dacha egasi o'z mulkini ushbu bot orqali mehmonlarga bron qilish uchun joylashtiradi.",
        "2. Bot orqali amalga oshirilgan har bir bron uchun umumiy summadan 1% (bir foiz) miqdorida "
        "xizmat haqi (komissiya) Platformaga to'lanadi.",
        "3. Dacha egasi kiritilgan ma'lumotlarning (narx, tavsif, holat) to'g'riligi uchun mas'uldir.",
        "4. Platforma bron qilish jarayonini osonlashtiradi, lekin mehmon va dacha egasi o'rtasidagi "
        "kelishuvlar uchun javobgar emas.",
        "5. Ushbu shartnomaga elektron rozilik bildirish orqali dacha egasi yuqoridagi shartlarni "
        "to'liq qabul qildi.",
    ]
    for term in terms:
        story.append(Paragraph(term, styles["Normal"]))
        story.append(Spacer(1, 6))
    doc.build(story)
    return path


# ============ KLAVIATURALAR ============
def lang_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            ]
        ]
    )


def main_reply_kb(lang: str, user_id: int) -> ReplyKeyboardMarkup:
    t = TEXTS[lang]
    owners = load_owners()
    rec = owners.get(str(user_id))

    rows = [
        [KeyboardButton(text=t["menu_list"]), KeyboardButton(text=t["menu_my"])],
        [KeyboardButton(text=t["menu_support"])],
    ]

    if rec and rec.get("status") == "approved":
        rows.append([KeyboardButton(text=t["menu_owner"])])
    elif not rec or rec.get("status") == "rejected":
        rows.append([KeyboardButton(text=t["menu_owner_apply"])])
    # status == "pending" -> hech qanday qo'shimcha tugma ko'rsatilmaydi

    if is_admin(user_id):
        rows.append([KeyboardButton(text=t["menu_admin"])])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def dacha_list_kb(lang: str, dachas: dict) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(text=d[f"name_{lang}"], callback_data=f"view_{key}")]
        for key, d in dachas.items()
    ]
    buttons.append([InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def dacha_detail_kb(lang: str, dacha_key: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["book_btn"], callback_data=f"book_{dacha_key}")],
            [InlineKeyboardButton(text=t["back"], callback_data="menu_list")],
        ]
    )


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=t["confirm_yes"], callback_data="confirm_yes"),
                InlineKeyboardButton(text=t["confirm_no"], callback_data="confirm_no"),
            ]
        ]
    )


def support_list_kb(lang: str, items: dict) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    rows = [[InlineKeyboardButton(text=v["title"], callback_data=f"sview_{k}")] for k, v in items.items()]
    rows.append([InlineKeyboardButton(text=t["write_support"], callback_data="support_write")])
    rows.append([InlineKeyboardButton(text=t["back"], callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_detail_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="menu_support")]]
    )


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["btn_add"], callback_data="admin_add")],
            [InlineKeyboardButton(text=A["btn_manage"], callback_data="admin_manage")],
            [InlineKeyboardButton(text=A["btn_bookings"], callback_data="admin_bookings_0")],
            [InlineKeyboardButton(text=A["btn_support"], callback_data="admin_support")],
        ]
    )


def owner_panel_kb(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["owner_btn_add"], callback_data="owner_add")],
            [InlineKeyboardButton(text=t["owner_btn_manage"], callback_data="owner_manage")],
        ]
    )


def dachas_manage_kb(dachas: dict, back_cb: str) -> InlineKeyboardMarkup:
    rows = []
    for key, d in dachas.items():
        rows.append([InlineKeyboardButton(text=d["name_uz"], callback_data="noop")])
        rows.append(
            [
                InlineKeyboardButton(text=A["edit_btn"], callback_data=f"edit_{key}"),
                InlineKeyboardButton(text=A["delete_btn"], callback_data=f"delask_{key}"),
            ]
        )
    rows.append([InlineKeyboardButton(text=A["back"], callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_field_kb(dacha_key: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["field_name_uz"], callback_data=f"ef_nu_{dacha_key}")],
            [InlineKeyboardButton(text=A["field_name_ru"], callback_data=f"ef_nr_{dacha_key}")],
            [InlineKeyboardButton(text=A["field_desc_uz"], callback_data=f"ef_du_{dacha_key}")],
            [InlineKeyboardButton(text=A["field_desc_ru"], callback_data=f"ef_dr_{dacha_key}")],
            [InlineKeyboardButton(text=A["field_price"], callback_data=f"ef_pr_{dacha_key}")],
            [InlineKeyboardButton(text=A["back"], callback_data=back_cb)],
        ]
    )


def delete_confirm_kb(dacha_key: str, back_cb: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=A["delete_yes"], callback_data=f"delyes_{dacha_key}"),
                InlineKeyboardButton(text=A["delete_no"], callback_data=back_cb),
            ]
        ]
    )


def admin_support_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["btn_support_add"], callback_data="admin_support_add")],
            [InlineKeyboardButton(text=A["btn_support_manage"], callback_data="admin_support_manage")],
            [InlineKeyboardButton(text=A["btn_support_inbox"], callback_data="admin_inbox_0")],
            [InlineKeyboardButton(text=A["back"], callback_data="admin_panel")],
        ]
    )


def support_manage_kb(items: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, v in items.items():
        rows.append([InlineKeyboardButton(text=v["title"], callback_data="noop")])
        rows.append(
            [
                InlineKeyboardButton(text=A["edit_btn"], callback_data=f"sedit_{key}"),
                InlineKeyboardButton(text=A["delete_btn"], callback_data=f"sdelask_{key}"),
            ]
        )
    rows.append([InlineKeyboardButton(text=A["back"], callback_data="admin_support")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def support_edit_field_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["field_title"], callback_data=f"sef_t_{key}")],
            [InlineKeyboardButton(text=A["field_text"], callback_data=f"sef_x_{key}")],
            [InlineKeyboardButton(text=A["back"], callback_data="admin_support_manage")],
        ]
    )


def support_delete_confirm_kb(key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=A["delete_yes"], callback_data=f"sdelyes_{key}"),
                InlineKeyboardButton(text=A["delete_no"], callback_data="admin_support_manage"),
            ]
        ]
    )


FIELD_MAP = {"nu": "name_uz", "nr": "name_ru", "du": "desc_uz", "dr": "desc_ru", "pr": "price"}
SUPPORT_FIELD_MAP = {"t": "title", "x": "text"}


def parse_date(text: str):
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y")
    except ValueError:
        return None


def parse_price(text: str):
    raw = text.strip().replace(" ", "").replace(",", "")
    if raw.isdigit():
        return int(raw)
    return None


# ============ START / TIL ============
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(TEXTS["uz"]["choose_lang"], reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang_"))
async def choose_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)
    t = TEXTS[lang]
    await callback.message.edit_text(t["choose_lang"])
    await callback.message.answer(t["welcome"], reply_markup=main_reply_kb(lang, callback.from_user.id))
    await callback.answer()


# ============ PASTKI MENYU (REPLY KEYBOARD) HANDLERLARI ============
# Diqqat: bu handlerlar barcha FSM-holat handlerlaridan OLDIN ro'yxatdan
# o'tkazilishi kerak — shunda tugma bosilganda joriy jarayon to'xtab, menyu ishlaydi.

@router.message(F.text.in_({TEXTS["uz"]["menu_list"], TEXTS["ru"]["menu_list"]}))
async def rk_menu_list(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(None)
    await state.update_data(lang=lang)
    dachas = load_dachas()
    if not dachas:
        await message.answer(TEXTS[lang]["no_dachas_user"])
        return
    await message.answer(TEXTS[lang]["choose_dacha"], reply_markup=dacha_list_kb(lang, dachas))


@router.message(F.text.in_({TEXTS["uz"]["menu_my"], TEXTS["ru"]["menu_my"]}))
async def rk_menu_my(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(None)
    await state.update_data(lang=lang)
    t = TEXTS[lang]
    bookings = load_bookings()
    user_bookings = [b for b in bookings if b["user_id"] == message.from_user.id]
    if not user_bookings:
        text = t["no_bookings"]
    else:
        text = t["your_bookings"]
        for b in user_bookings:
            text += f"🏡 {b['dacha']}\n📅 {b['checkin']} - {b['checkout']}\n\n"
    await message.answer(text)


@router.message(F.text.in_({TEXTS["uz"]["menu_support"], TEXTS["ru"]["menu_support"]}))
async def rk_menu_support(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(None)
    await state.update_data(lang=lang)
    items = load_support()
    text = TEXTS[lang]["support_title"] if items else TEXTS[lang]["no_support_info"]
    await message.answer(text, reply_markup=support_list_kb(lang, items))


@router.message(F.text.in_({TEXTS["uz"]["menu_admin"], TEXTS["ru"]["menu_admin"]}))
async def rk_menu_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(None)
    await message.answer(A["panel_title"], reply_markup=admin_panel_kb())


@router.message(F.text.in_({TEXTS["uz"]["menu_owner"], TEXTS["ru"]["menu_owner"]}))
async def rk_menu_owner(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if not is_approved_owner(message.from_user.id):
        await message.answer(TEXTS[lang]["not_owner"])
        return
    await state.set_state(None)
    await state.update_data(lang=lang)
    await message.answer(TEXTS[lang]["owner_panel_title"], reply_markup=owner_panel_kb(lang))


@router.message(F.text.in_({TEXTS["uz"]["menu_owner_apply"], TEXTS["ru"]["menu_owner_apply"]}))
async def rk_owner_apply_start(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    owners = load_owners()
    rec = owners.get(str(message.from_user.id))
    if rec and rec.get("status") == "pending":
        await message.answer(TEXTS[lang]["owner_already_pending"])
        return
    if rec and rec.get("status") == "approved":
        await message.answer(TEXTS[lang]["owner_panel_title"], reply_markup=owner_panel_kb(lang))
        return
    await state.set_state(OwnerApplyStates.entering_name)
    await state.update_data(lang=lang)
    await message.answer(TEXTS[lang]["ask_name"])


# ============ DACHA KO'RISH / BRON QILISH (FOYDALANUVCHI) ============
@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(None)
    await callback.message.edit_text(TEXTS[lang]["welcome"])
    await callback.answer()


@router.callback_query(F.data == "menu_list")
async def menu_list(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dachas = load_dachas()
    if not dachas:
        await callback.answer(TEXTS[lang]["no_dachas_user"], show_alert=True)
        return
    await callback.message.edit_text(TEXTS[lang]["choose_dacha"], reply_markup=dacha_list_kb(lang, dachas))
    await callback.answer()


@router.callback_query(F.data.startswith("view_"))
async def view_dacha(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dacha_key = callback.data.replace("view_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Bu dacha endi mavjud emas.", show_alert=True)
        return
    price_line = f"\n\n💰 {d.get('price', 0):,} so'm/kecha".replace(",", " ")
    text = f"{d[f'name_{lang}']}\n\n{d[f'desc_{lang}']}{price_line}"
    await callback.message.edit_text(text, reply_markup=dacha_detail_kb(lang, dacha_key))
    await callback.answer()


@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dacha_key = callback.data.replace("book_", "")
    await state.update_data(dacha_key=dacha_key)
    await state.set_state(BookingStates.entering_checkin)
    await callback.message.answer(TEXTS[lang]["ask_checkin"])
    await callback.answer()


@router.message(BookingStates.entering_checkin)
async def enter_checkin(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dt = parse_date(message.text)
    if not dt:
        await message.answer(TEXTS[lang]["invalid_date"])
        return
    await state.update_data(checkin=message.text.strip(), checkin_dt=dt.isoformat())
    await state.set_state(BookingStates.entering_checkout)
    await message.answer(TEXTS[lang]["ask_checkout"])


@router.message(BookingStates.entering_checkout)
async def enter_checkout(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dt = parse_date(message.text)
    if not dt:
        await message.answer(TEXTS[lang]["invalid_date"])
        return
    checkin_dt = datetime.fromisoformat(data["checkin_dt"])
    if dt <= checkin_dt:
        await message.answer(TEXTS[lang]["invalid_date_order"])
        return
    await state.update_data(checkout=message.text.strip(), checkout_dt=dt.isoformat())
    await state.set_state(BookingStates.entering_name)
    await message.answer(TEXTS[lang]["ask_name"])


@router.message(BookingStates.entering_name)
async def enter_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.update_data(name=message.text.strip())
    await state.set_state(BookingStates.entering_phone)
    await message.answer(TEXTS[lang]["ask_phone"])


@router.message(BookingStates.entering_phone)
async def enter_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    phone = message.text.strip()
    if not (phone.startswith("+") and phone[1:].isdigit() and len(phone) >= 10):
        await message.answer(TEXTS[lang]["invalid_phone"])
        return
    await state.update_data(phone=phone)

    dachas = load_dachas()
    d = dachas[data["dacha_key"]]
    checkin_dt = datetime.fromisoformat(data["checkin_dt"])
    checkout_dt = datetime.fromisoformat(data["checkout_dt"])
    nights = max((checkout_dt - checkin_dt).days, 1)
    price = d.get("price", 0)
    total = price * nights
    commission = round(total * COMMISSION_RATE)
    await state.update_data(total=total, commission=commission, nights=nights)

    text = TEXTS[lang]["confirm"].format(
        dacha=d[f"name_{lang}"],
        checkin=data["checkin"],
        checkout=data["checkout"],
        name=data["name"],
        phone=phone,
    )
    text += TEXTS[lang]["commission_info"].format(total=total, nights=nights, commission=commission)

    await state.set_state(BookingStates.confirming)
    await message.answer(text, reply_markup=confirm_kb(lang))


@router.callback_query(F.data == "confirm_yes", BookingStates.confirming)
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = get_lang(data)
    dachas = load_dachas()
    d = dachas[data["dacha_key"]]
    total = data.get("total", 0)
    commission = data.get("commission", 0)

    booking = {
        "id": uuid.uuid4().hex[:8],
        "user_id": callback.from_user.id,
        "username": callback.from_user.username or "—",
        "dacha": d["name_uz"],
        "checkin": data["checkin"],
        "checkout": data["checkout"],
        "name": data["name"],
        "phone": data["phone"],
        "total": total,
        "commission": commission,
        "created_at": datetime.now().isoformat(),
    }
    add_booking(booking)

    await callback.message.edit_text(TEXTS[lang]["booked"])

    for admin_id in ADMIN_IDS:
        admin_text = TEXTS["uz"]["new_admin_booking"].format(
            dacha=d["name_uz"],
            checkin=data["checkin"],
            checkout=data["checkout"],
            name=data["name"],
            phone=data["phone"],
            total=total,
            commission=commission,
            user_id=callback.from_user.id,
        )
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception as e:
            logging.warning(f"Adminga ({admin_id}) xabar yuborilmadi: {e}")

    owner_id = d.get("owner_id")
    if owner_id:
        net = total - commission
        owner_text = TEXTS["uz"]["new_owner_booking"].format(
            dacha=d["name_uz"],
            checkin=data["checkin"],
            checkout=data["checkout"],
            name=data["name"],
            phone=data["phone"],
            total=total,
            commission=commission,
            net=net,
        )
        try:
            await bot.send_message(owner_id, owner_text)
        except Exception as e:
            logging.warning(f"Dacha egasiga ({owner_id}) xabar yuborilmadi: {e}")

    await state.clear()
    await state.update_data(lang=lang)
    await callback.message.answer(TEXTS[lang]["welcome"])
    await callback.answer()


@router.callback_query(F.data == "confirm_no", BookingStates.confirming)
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.clear()
    await state.update_data(lang=lang)
    await callback.message.edit_text(TEXTS[lang]["cancelled"])
    await callback.message.answer(TEXTS[lang]["welcome"])
    await callback.answer()


# ============ QO'LLAB-QUVVATLASH (FOYDALANUVCHI) ============
@router.callback_query(F.data == "menu_support")
async def menu_support(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    items = load_support()
    text = TEXTS[lang]["support_title"] if items else TEXTS[lang]["no_support_info"]
    await callback.message.edit_text(text, reply_markup=support_list_kb(lang, items))
    await callback.answer()


@router.callback_query(F.data.startswith("sview_"))
async def view_support_item(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    key = callback.data.replace("sview_", "")
    items = load_support()
    item = items.get(key)
    if not item:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    text = f"{item['title']}\n\n{item['text']}"
    await callback.message.edit_text(text, reply_markup=support_detail_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "support_write")
async def support_write_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(SupportStates.entering_message)
    await callback.message.answer(TEXTS[lang]["ask_support_msg"])
    await callback.answer()


@router.message(SupportStates.entering_message)
async def support_write_save(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = get_lang(data)

    ticket = {
        "id": uuid.uuid4().hex[:8],
        "user_id": message.from_user.id,
        "username": message.from_user.username or "—",
        "name": message.from_user.full_name,
        "text": message.text.strip(),
        "created_at": datetime.now().isoformat(),
        "status": "open",
        "reply": None,
    }
    add_ticket(ticket)

    for admin_id in ADMIN_IDS:
        admin_text = TEXTS["uz"]["new_support_msg_admin"].format(
            name=ticket["name"], username=ticket["username"], text=ticket["text"]
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=A["reply_btn"], callback_data=f"reply_{ticket['id']}_0")]]
        )
        try:
            await bot.send_message(admin_id, admin_text, reply_markup=kb)
        except Exception as e:
            logging.warning(f"Adminga ({admin_id}) murojaat yuborilmadi: {e}")

    await state.set_state(None)
    await message.answer(TEXTS[lang]["support_sent"])


# ============ DACHA EGALARI: ARIZA ============
@router.message(OwnerApplyStates.entering_name)
async def owner_apply_name(message: Message, state: FSMContext):
    await state.update_data(o_name=message.text.strip())
    await state.set_state(OwnerApplyStates.entering_phone)
    data = await state.get_data()
    lang = get_lang(data)
    await message.answer(TEXTS[lang]["ask_phone"])


@router.message(OwnerApplyStates.entering_phone)
async def owner_apply_phone(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = get_lang(data)
    phone = message.text.strip()
    if not (phone.startswith("+") and phone[1:].isdigit() and len(phone) >= 10):
        await message.answer(TEXTS[lang]["invalid_phone"])
        return

    owners = load_owners()
    owners[str(message.from_user.id)] = {
        "name": data["o_name"],
        "phone": phone,
        "status": "pending",
        "lang": lang,
        "requested_at": datetime.now().isoformat(),
    }
    save_owners(owners)

    for admin_id in ADMIN_IDS:
        text = A["owner_app_notify"].format(name=data["o_name"], phone=phone, user_id=message.from_user.id)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text=A["owner_approve_btn"], callback_data=f"owna_yes_{message.from_user.id}"),
                    InlineKeyboardButton(text=A["owner_reject_btn"], callback_data=f"owna_no_{message.from_user.id}"),
                ]
            ]
        )
        try:
            await bot.send_message(admin_id, text, reply_markup=kb)
        except Exception as e:
            logging.warning(f"Adminga ({admin_id}) ega so'rovi yuborilmadi: {e}")

    await state.set_state(None)
    await message.answer(TEXTS[lang]["owner_apply_sent"])


@router.callback_query(F.data.startswith("owna_yes_"))
async def owner_approve(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    uid = callback.data.replace("owna_yes_", "")
    owners = load_owners()
    if uid in owners:
        owners[uid]["status"] = "approved"
        save_owners(owners)
        u_lang = owners[uid].get("lang", "uz")
        try:
            await bot.send_message(
                int(uid), TEXTS[u_lang]["owner_approved_msg"], reply_markup=main_reply_kb(u_lang, int(uid))
            )
        except Exception as e:
            logging.warning(f"Foydalanuvchiga ({uid}) xabar yuborilmadi: {e}")
    await callback.message.edit_text(callback.message.text + A["owner_approved_admin"])
    await callback.answer()


@router.callback_query(F.data.startswith("owna_no_"))
async def owner_reject(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    uid = callback.data.replace("owna_no_", "")
    owners = load_owners()
    if uid in owners:
        owners[uid]["status"] = "rejected"
        save_owners(owners)
        u_lang = owners[uid].get("lang", "uz")
        try:
            await bot.send_message(
                int(uid), TEXTS[u_lang]["owner_rejected_msg"], reply_markup=main_reply_kb(u_lang, int(uid))
            )
        except Exception as e:
            logging.warning(f"Foydalanuvchiga ({uid}) xabar yuborilmadi: {e}")
    await callback.message.edit_text(callback.message.text + A["owner_rejected_admin"])
    await callback.answer()


# ============ DACHA EGALARI PANELI ============
@router.callback_query(F.data == "owner_panel_reopen")
async def owner_panel_reopen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await callback.message.edit_text(TEXTS[lang]["owner_panel_title"], reply_markup=owner_panel_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "owner_manage")
async def owner_manage(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if not is_approved_owner(callback.from_user.id):
        await callback.answer(TEXTS[lang]["not_owner"], show_alert=True)
        return
    dachas = load_dachas()
    mine = {k: v for k, v in dachas.items() if v.get("owner_id") == callback.from_user.id}
    if not mine:
        await callback.message.edit_text(TEXTS[lang]["owner_no_dachas"], reply_markup=owner_panel_kb(lang))
        await callback.answer()
        return
    await callback.message.edit_text(
        TEXTS[lang]["owner_manage_title"], reply_markup=dachas_manage_kb(mine, "owner_panel_reopen")
    )
    await callback.answer()


@router.callback_query(F.data == "owner_add")
async def owner_add_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if not is_approved_owner(callback.from_user.id):
        await callback.answer(TEXTS[lang]["not_owner"], show_alert=True)
        return
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=TEXTS[lang]["contract_agree"], callback_data="contract_agree"),
                InlineKeyboardButton(text=TEXTS[lang]["contract_decline"], callback_data="contract_decline"),
            ]
        ]
    )
    await callback.message.edit_text(TEXTS[lang]["contract_text"], reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "contract_decline")
async def contract_decline(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await callback.message.edit_text(TEXTS[lang]["contract_declined_msg"], reply_markup=owner_panel_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "contract_agree")
async def contract_agree(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.name_uz)
    await callback.message.edit_text(TEXTS[lang]["ask_owner_name_uz"])
    await callback.answer()


@router.message(OwnerAddStates.name_uz)
async def oa_name_uz(message: Message, state: FSMContext):
    await state.update_data(o_name_uz=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.name_ru)
    await message.answer(TEXTS[lang]["ask_owner_name_ru"])


@router.message(OwnerAddStates.name_ru)
async def oa_name_ru(message: Message, state: FSMContext):
    await state.update_data(o_name_ru=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.desc_uz)
    await message.answer(TEXTS[lang]["ask_owner_desc_uz"])


@router.message(OwnerAddStates.desc_uz)
async def oa_desc_uz(message: Message, state: FSMContext):
    await state.update_data(o_desc_uz=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.desc_ru)
    await message.answer(TEXTS[lang]["ask_owner_desc_ru"])


@router.message(OwnerAddStates.desc_ru)
async def oa_desc_ru(message: Message, state: FSMContext):
    await state.update_data(o_desc_ru=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.price)
    await message.answer(TEXTS[lang]["ask_price"])


@router.message(OwnerAddStates.price)
async def oa_price(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = get_lang(data)
    price = parse_price(message.text)
    if price is None:
        await message.answer(TEXTS[lang]["invalid_price"])
        return

    dachas = load_dachas()
    new_key = f"dacha_{uuid.uuid4().hex[:8]}"
    dachas[new_key] = {
        "name_uz": data["o_name_uz"],
        "name_ru": data["o_name_ru"],
        "desc_uz": data["o_desc_uz"],
        "desc_ru": data["o_desc_ru"],
        "price": price,
        "owner_id": message.from_user.id,
        "owner_name": message.from_user.full_name,
    }
    save_dachas(dachas)

    try:
        pdf_path = generate_contract_pdf(message.from_user.full_name, data["o_name_uz"], price)
        await bot.send_document(message.chat.id, FSInputFile(pdf_path))
    except Exception as e:
        logging.warning(f"Shartnoma PDF yuborilmadi: {e}")

    await state.set_state(None)
    await message.answer(TEXTS[lang]["dacha_added_owner"], reply_markup=owner_panel_kb(lang))


# ============ ADMIN PANELI ============
@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer(A["not_admin"])
        return
    await state.set_state(None)
    await message.answer(A["panel_title"], reply_markup=admin_panel_kb())


@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(None)
    await callback.message.edit_text(A["panel_title"], reply_markup=admin_panel_kb())
    await callback.answer()


# --- Yangi dacha qo'shish (admin) ---
@router.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(AdminStates.adding_name_uz)
    await callback.message.edit_text(A["ask_name_uz"])
    await callback.answer()


@router.message(AdminStates.adding_name_uz)
async def admin_add_name_uz(message: Message, state: FSMContext):
    await state.update_data(new_name_uz=message.text.strip())
    await state.set_state(AdminStates.adding_name_ru)
    await message.answer(A["ask_name_ru"])


@router.message(AdminStates.adding_name_ru)
async def admin_add_name_ru(message: Message, state: FSMContext):
    await state.update_data(new_name_ru=message.text.strip())
    await state.set_state(AdminStates.adding_desc_uz)
    await message.answer(A["ask_desc_uz"])


@router.message(AdminStates.adding_desc_uz)
async def admin_add_desc_uz(message: Message, state: FSMContext):
    await state.update_data(new_desc_uz=message.text.strip())
    await state.set_state(AdminStates.adding_desc_ru)
    await message.answer(A["ask_desc_ru"])


@router.message(AdminStates.adding_desc_ru)
async def admin_add_desc_ru(message: Message, state: FSMContext):
    await state.update_data(new_desc_ru=message.text.strip())
    await state.set_state(AdminStates.adding_price)
    await message.answer(A["ask_price"])


@router.message(AdminStates.adding_price)
async def admin_add_price(message: Message, state: FSMContext):
    data = await state.get_data()
    price = parse_price(message.text)
    if price is None:
        await message.answer(A["invalid_price"])
        return
    dachas = load_dachas()
    new_key = f"dacha_{uuid.uuid4().hex[:8]}"
    dachas[new_key] = {
        "name_uz": data["new_name_uz"],
        "name_ru": data["new_name_ru"],
        "desc_uz": data["new_desc_uz"],
        "desc_ru": data["new_desc_ru"],
        "price": price,
        "owner_id": None,
        "owner_name": None,
    }
    save_dachas(dachas)
    await state.set_state(None)
    await message.answer(A["added"], reply_markup=admin_panel_kb())


# --- Dachalarni boshqarish (admin + egalar umumiy handlerlari) ---
@router.callback_query(F.data == "admin_manage")
async def admin_manage(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    dachas = load_dachas()
    if not dachas:
        await callback.message.edit_text(A["no_dachas"], reply_markup=admin_panel_kb())
        await callback.answer()
        return
    await callback.message.edit_text(A["manage_title"], reply_markup=dachas_manage_kb(dachas, "admin_panel"))
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


@router.callback_query(F.data.startswith("edit_"))
async def admin_edit_choose_field(callback: CallbackQuery, state: FSMContext):
    dacha_key = callback.data.replace("edit_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    if not can_manage_dacha(callback.from_user.id, d):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    back_cb = manage_list_cb(callback.from_user.id)
    await callback.message.edit_text(
        A["edit_choose_field"].format(name=d["name_uz"]), reply_markup=edit_field_kb(dacha_key, back_cb)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ef_"))
async def admin_edit_ask_value(callback: CallbackQuery, state: FSMContext):
    _, field_code, dacha_key = callback.data.split("_", 2)
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    if not can_manage_dacha(callback.from_user.id, d):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    field = FIELD_MAP[field_code]
    await state.update_data(edit_dacha_key=dacha_key, edit_field=field)
    await state.set_state(AdminStates.editing_value)
    await callback.message.edit_text(A["ask_new_value"].format(old=d[field]))
    await callback.answer()


@router.message(AdminStates.editing_value)
async def admin_edit_save_value(message: Message, state: FSMContext):
    data = await state.get_data()
    dacha_key = data["edit_dacha_key"]
    field = data["edit_field"]
    dachas = load_dachas()
    if dacha_key not in dachas or not can_manage_dacha(message.from_user.id, dachas[dacha_key]):
        await state.set_state(None)
        await message.answer(A["no_dachas"])
        return

    if field == "price":
        price = parse_price(message.text)
        if price is None:
            await message.answer(A["invalid_price"])
            return
        dachas[dacha_key][field] = price
    else:
        dachas[dacha_key][field] = message.text.strip()
    save_dachas(dachas)
    await state.set_state(None)

    if is_admin(message.from_user.id):
        await message.answer(A["updated"], reply_markup=dachas_manage_kb(dachas, "admin_panel"))
    else:
        mine = {k: v for k, v in dachas.items() if v.get("owner_id") == message.from_user.id}
        await message.answer(A["updated"], reply_markup=dachas_manage_kb(mine, "owner_panel_reopen"))


@router.callback_query(F.data.startswith("delask_"))
async def admin_delete_ask(callback: CallbackQuery, state: FSMContext):
    dacha_key = callback.data.replace("delask_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    if not can_manage_dacha(callback.from_user.id, d):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    back_cb = manage_list_cb(callback.from_user.id)
    await callback.message.edit_text(
        A["delete_confirm"].format(name=d["name_uz"]), reply_markup=delete_confirm_kb(dacha_key, back_cb)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delyes_"))
async def admin_delete_confirm(callback: CallbackQuery, state: FSMContext):
    dacha_key = callback.data.replace("delyes_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    if not can_manage_dacha(callback.from_user.id, d):
        await callback.answer(A["not_admin"], show_alert=True)
        return

    dachas.pop(dacha_key, None)
    save_dachas(dachas)
    await callback.answer(A["deleted"], show_alert=True)

    if is_admin(callback.from_user.id):
        if dachas:
            await callback.message.edit_text(A["manage_title"], reply_markup=dachas_manage_kb(dachas, "admin_panel"))
        else:
            await callback.message.edit_text(A["no_dachas"], reply_markup=admin_panel_kb())
    else:
        data = await state.get_data()
        lang = get_lang(data)
        mine = {k: v for k, v in dachas.items() if v.get("owner_id") == callback.from_user.id}
        if mine:
            await callback.message.edit_text(
                TEXTS[lang]["owner_manage_title"], reply_markup=dachas_manage_kb(mine, "owner_panel_reopen")
            )
        else:
            await callback.message.edit_text(TEXTS[lang]["owner_no_dachas"], reply_markup=owner_panel_kb(lang))


# --- Bronlarni ko'rish ---
PAGE_SIZE = 5


def bookings_page_kb(bookings: list, page: int) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    page_items = bookings[start : start + PAGE_SIZE]
    rows = []
    for b in page_items:
        label = f"🗑 {b['name']} ({b['checkin']})"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"bdel_{b['id']}_{page}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_bookings_{page - 1}"))
    if start + PAGE_SIZE < len(bookings):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_bookings_{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=A["back"], callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("admin_bookings_"))
async def admin_bookings(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    page = int(callback.data.replace("admin_bookings_", ""))
    bookings = load_bookings()
    bookings.sort(key=lambda b: b["created_at"], reverse=True)

    if not bookings:
        await callback.message.edit_text(A["no_bookings_admin"], reply_markup=admin_panel_kb())
        await callback.answer()
        return

    start = page * PAGE_SIZE
    page_items = bookings[start : start + PAGE_SIZE]
    text = A["bookings_title"].format(count=len(bookings)) + "\n\n"
    for b in page_items:
        text += A["booking_item"].format(
            dacha=b["dacha"], checkin=b["checkin"], checkout=b["checkout"],
            name=b["name"], phone=b["phone"], username=b["username"],
        )
        if b.get("total"):
            text += f"\n💰 {b['total']:,} so'm | 📊 Komissiya: {b['commission']:,} so'm".replace(",", " ")
        text += "\n\n"

    await callback.message.edit_text(text, reply_markup=bookings_page_kb(bookings, page))
    await callback.answer()


@router.callback_query(F.data.startswith("bdel_"))
async def admin_booking_delete(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    _, booking_id, page = callback.data.split("_")
    bookings = load_bookings()
    bookings = [b for b in bookings if b["id"] != booking_id]
    save_bookings(bookings)
    await callback.answer(A["booking_deleted"], show_alert=True)
    callback.data = f"admin_bookings_{page}"
    await admin_bookings(callback, state)


# ============ QO'LLAB-QUVVATLASH (ADMIN) ============
@router.callback_query(F.data == "admin_support")
async def admin_support(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(None)
    await callback.message.edit_text(A["support_panel_title"], reply_markup=admin_support_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_support_add")
async def admin_support_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(SupportAdminStates.adding_title)
    await callback.message.edit_text(A["ask_support_title"])
    await callback.answer()


@router.message(SupportAdminStates.adding_title)
async def admin_support_add_title(message: Message, state: FSMContext):
    await state.update_data(new_title=message.text.strip())
    await state.set_state(SupportAdminStates.adding_text)
    await message.answer(A["ask_support_text"])


@router.message(SupportAdminStates.adding_text)
async def admin_support_add_text(message: Message, state: FSMContext):
    data = await state.get_data()
    items = load_support()
    new_key = f"s_{uuid.uuid4().hex[:8]}"
    items[new_key] = {"title": data["new_title"], "text": message.text.strip()}
    save_support(items)
    await state.set_state(None)
    await message.answer(A["support_added"], reply_markup=admin_support_kb())


@router.callback_query(F.data == "admin_support_manage")
async def admin_support_manage(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    items = load_support()
    if not items:
        await callback.message.edit_text(A["no_support_items"], reply_markup=admin_support_kb())
        await callback.answer()
        return
    await callback.message.edit_text(A["support_manage_title"], reply_markup=support_manage_kb(items))
    await callback.answer()


@router.callback_query(F.data.startswith("sedit_"))
async def admin_support_edit_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    key = callback.data.replace("sedit_", "")
    items = load_support()
    item = items.get(key)
    if not item:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        A["support_edit_choose_field"].format(title=item["title"]), reply_markup=support_edit_field_kb(key)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sef_"))
async def admin_support_edit_ask(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    _, field_code, key = callback.data.split("_", 2)
    items = load_support()
    item = items.get(key)
    if not item:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    field = SUPPORT_FIELD_MAP[field_code]
    await state.update_data(s_edit_key=key, s_edit_field=field)
    await state.set_state(SupportAdminStates.editing_value)
    await callback.message.edit_text(A["support_ask_new_value"].format(old=item[field]))
    await callback.answer()


@router.message(SupportAdminStates.editing_value)
async def admin_support_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    key = data["s_edit_key"]
    field = data["s_edit_field"]
    items = load_support()
    if key not in items:
        await state.set_state(None)
        await message.answer(A["no_support_items"], reply_markup=admin_support_kb())
        return
    items[key][field] = message.text.strip()
    save_support(items)
    await state.set_state(None)
    await message.answer(A["support_updated"], reply_markup=support_manage_kb(items))


@router.callback_query(F.data.startswith("sdelask_"))
async def admin_support_delete_ask(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    key = callback.data.replace("sdelask_", "")
    items = load_support()
    item = items.get(key)
    if not item:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        A["support_delete_confirm"].format(title=item["title"]), reply_markup=support_delete_confirm_kb(key)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sdelyes_"))
async def admin_support_delete_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    key = callback.data.replace("sdelyes_", "")
    items = load_support()
    items.pop(key, None)
    save_support(items)
    await callback.answer(A["support_deleted"], show_alert=True)
    if items:
        await callback.message.edit_text(A["support_manage_title"], reply_markup=support_manage_kb(items))
    else:
        await callback.message.edit_text(A["no_support_items"], reply_markup=admin_support_kb())


def inbox_page_kb(tickets: list, page: int) -> InlineKeyboardMarkup:
    start = page * PAGE_SIZE
    page_items = tickets[start : start + PAGE_SIZE]
    rows = []
    for tk in page_items:
        if tk["status"] != "answered":
            label = f"↩️ {tk['name']}ga javob berish"
            rows.append([InlineKeyboardButton(text=label, callback_data=f"reply_{tk['id']}_{page}")])
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_inbox_{page - 1}"))
    if start + PAGE_SIZE < len(tickets):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_inbox_{page + 1}"))
    if nav:
        rows.append(nav)
    rows.append([InlineKeyboardButton(text=A["back"], callback_data="admin_support")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("admin_inbox_"))
async def admin_inbox(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    page = int(callback.data.replace("admin_inbox_", ""))
    tickets = load_tickets()
    tickets.sort(key=lambda t: t["created_at"], reverse=True)

    if not tickets:
        await callback.message.edit_text(A["no_tickets"], reply_markup=admin_support_kb())
        await callback.answer()
        return

    start = page * PAGE_SIZE
    page_items = tickets[start : start + PAGE_SIZE]
    text = A["inbox_title"].format(count=len(tickets)) + "\n\n"
    for tk in page_items:
        status_tag = A["inbox_answered_tag"] if tk["status"] == "answered" else ""
        time_str = tk["created_at"][:16].replace("T", " ")
        text += A["inbox_item"].format(
            name=tk["name"], username=tk["username"], text=tk["text"], time=time_str, status=status_tag
        ) + "\n\n"

    await callback.message.edit_text(text, reply_markup=inbox_page_kb(tickets, page))
    await callback.answer()


@router.callback_query(F.data.startswith("reply_"))
async def admin_reply_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    parts = callback.data.split("_")
    ticket_id = parts[1]
    tickets = load_tickets()
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)
    if not ticket:
        await callback.answer(A["ticket_not_found"], show_alert=True)
        return
    await state.update_data(reply_ticket_id=ticket_id)
    await state.set_state(SupportAdminStates.replying)
    await callback.message.answer(A["ask_reply"])
    await callback.answer()


@router.message(SupportAdminStates.replying)
async def admin_reply_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ticket_id = data["reply_ticket_id"]
    tickets = load_tickets()
    ticket = next((t for t in tickets if t["id"] == ticket_id), None)

    if not ticket:
        await state.set_state(None)
        await message.answer(A["ticket_not_found"], reply_markup=admin_support_kb())
        return

    reply_text = message.text.strip()
    ticket["status"] = "answered"
    ticket["reply"] = reply_text
    save_tickets(tickets)

    try:
        await bot.send_message(ticket["user_id"], TEXTS["uz"]["support_reply_prefix"] + reply_text)
        await message.answer(A["reply_sent"], reply_markup=admin_support_kb())
    except Exception as e:
        logging.warning(f"Foydalanuvchiga ({ticket['user_id']}) javob yuborilmadi: {e}")
        await message.answer(A["reply_send_failed"], reply_markup=admin_support_kb())

    await state.set_state(None)


# ============ ISHGA TUSHIRISH ============
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
