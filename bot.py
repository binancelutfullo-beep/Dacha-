"""
Dacha bron qilish Telegram bot
+ Admin panel, Qo'llab-quvvatlash paneli, Dacha egalari tizimi (shartnoma + 1% komissiya)
+ Dacha rasmlari
Til: O'zbek / Rus (foydalanuvchi uchun) | Admin panel: O'zbek
Barcha navigatsiya — inline tugmalar orqali.
Kutubxona: aiogram 3.x, reportlab (PDF shartnoma uchun)
Ma'lumotlar: dachas.json, bookings.json, support.json, support_messages.json, owners.json
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

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
    InputMediaPhoto,
    InputMediaVideo,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# ============ SOZLAMALAR ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ_BU_YERGA")
ADMIN_IDS = [x.strip() for x in os.getenv("ADMIN_IDS", os.getenv("ADMIN_CHAT_ID", "")).split(",") if x.strip()]
COMMISSION_RATE = 0.01  # 1%

TASHKENT_TZ = timezone(timedelta(hours=5))


def now_tz() -> datetime:
    """O'zbekiston (Toshkent, UTC+5) vaqtini qaytaradi — barcha sana/vaqt yozuvlari
    (created_at, PDF shartnoma vaqti va h.k.) shu funksiya orqali olinadi."""
    return datetime.now(TASHKENT_TZ)

# DATA_DIR — Railway'da Volume ulangan bo'lsa, shu papkaga yozilgan fayllar
# qayta deploy/restartlardan keyin ham SAQLANIB QOLADI. Volume ulanmasa,
# fayllar joriy papkaga yoziladi (Railway'da bu holatda ma'lumot yo'qolishi mumkin).
DATA_DIR = os.getenv("DATA_DIR", ".")
os.makedirs(DATA_DIR, exist_ok=True)

DACHAS_FILE = os.path.join(DATA_DIR, "dachas.json")
BOOKINGS_FILE = os.path.join(DATA_DIR, "bookings.json")
SUPPORT_FILE = os.path.join(DATA_DIR, "support.json")
SUPPORT_MSG_FILE = os.path.join(DATA_DIR, "support_messages.json")
OWNERS_FILE = os.path.join(DATA_DIR, "owners.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")
GUESTS_FILE = os.path.join(DATA_DIR, "guests.json")
OWNER_CODES_FILE = os.path.join(DATA_DIR, "owner_codes.json")
PROMO_FILE = os.path.join(DATA_DIR, "promocodes.json")
ABOUT_FILE = os.path.join(DATA_DIR, "about.txt")
CONTRACTS_DIR = os.path.join(DATA_DIR, "contracts")
CONTRACT_TEXTS_FILE = os.path.join(DATA_DIR, "contract_texts.json")

# --- PDF uchun kirill (rus tili) harflarini qo'llab-quvvatlaydigan shrift ---
# ReportLab'ning standart shriftlari (Helvetica va h.k.) faqat lotin harflarini biladi,
# shuning uchun rus tilidagi ism/matnlar PDF'da noto'g'ri chiqib qolmasligi uchun
# alohida shrift fayllari (fonts/ papkasi) ro'yxatdan o'tkaziladi.
FONTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
PDF_FONT = "Helvetica"
PDF_FONT_BOLD = "Helvetica-Bold"
try:
    pdfmetrics.registerFont(TTFont("DejaVuSans", os.path.join(FONTS_DIR, "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf")))
    PDF_FONT = "DejaVuSans"
    PDF_FONT_BOLD = "DejaVuSans-Bold"
except Exception as e:
    logging.warning(f"Kirill shrifti topilmadi, standart shrift ishlatiladi (rus matni noto'g'ri chiqishi mumkin): {e}")

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
        "photos": [],
        "video_id": None,
        "location": None,
        "address": None,
        "region": "tv",
        "district": "Bo'stonliq",
        "verified": True,
    },
    "dacha_2": {
        "name_uz": "🌲 Bo'stonliq dachasi",
        "name_ru": "🌲 Дача Бустанлык",
        "desc_uz": "2 xonali, tog' manzarasi, 5 kishi uchun.",
        "desc_ru": "2 комнаты, вид на горы, до 5 человек.",
        "price": 500000,
        "owner_id": None,
        "owner_name": None,
        "photos": [],
        "video_id": None,
        "location": None,
        "address": None,
        "region": "tv",
        "district": "Bo'stonliq",
        "verified": True,
    },
}

DEFAULT_SUPPORT = {
    "s_1": {
        "title": "📞 Aloqa uchun",
        "text": "Operator bilan bog'lanish uchun quyidagi tugmadan foydalaning yoki +998 90 000 00 00 raqamiga qo'ng'iroq qiling.",
    },
}

DEFAULT_CONTRACT_TEXTS = {
    "owner": (
        "📜 SHARTNOMA (Dacha egasi bilan)\n\n"
        "1. Siz o'z dachangizni ushbu bot orqali mehmonlarga bron qilish uchun joylashtirasiz.\n"
        "2. Bot orqali amalga oshirilgan har bir bron uchun umumiy summadan belgilangan foizda "
        "xizmat haqi (komissiya) Platformaga to'lanadi.\n"
        "3. Siz kiritgan ma'lumotlar (narx, tavsif, dacha holati) to'g'ri bo'lishi uchun javobgarsiz.\n"
        "4. Platforma faqat bron qilish jarayonini osonlashtiradi, mehmon bilan bo'ladigan "
        "kelishuvlar uchun javobgar emas.\n"
        "5. \"Roziman\" tugmasini bosish orqali siz yuqoridagi shartlarni to'liq qabul qilasiz "
        "(elektron rozilik)."
    ),
    "guest": (
        "📜 SHARTNOMA (Mehmon bilan)\n\n"
        "1. Siz ushbu bot orqali dacha bron qilmoqchisiz. Kiritgan ma'lumotlaringiz (ism, telefon) "
        "to'g'ri bo'lishi shart.\n"
        "2. Bron faqat tanlangan sanalar uchun amal qiladi. Bekor qilish \"Mening bronlarim\" "
        "bo'limidan amalga oshiriladi.\n"
        "3. Dacha holati va unda bo'lgan qoidalarga rioya qilish mehmon zimmasida.\n"
        "4. Platforma bron jarayonini osonlashtiradi, lekin dacha va mehmon o'rtasidagi "
        "kelishuvlar uchun javobgar emas.\n"
        "5. \"Roziman\" tugmasini bosish orqali siz yuqoridagi shartlarni to'liq qabul qilasiz "
        "(elektron rozilik)."
    ),
}

# ============ NARX BO'YICHA FILTR ============
PRICE_RANGES = [
    (0, 500000, "0 - 500 000 so'm"),
    (500000, 1000000, "500 000 - 1 000 000 so'm"),
    (1000000, 2000000, "1 000 000 - 2 000 000 so'm"),
    (2000000, None, "2 000 000 so'm dan yuqori"),
]

# ============ VILOYATLAR VA TUMANLAR ============
REGIONS = {
    "tsh": {"name": "Toshkent shahri", "districts": [
        "Bektemir", "Chilonzor", "Mirzo Ulug'bek", "Mirobod", "Olmazor", "Sergeli",
        "Shayxontohur", "Uchtepa", "Yakkasaroy", "Yashnobod", "Yunusobod", "Yangihayot",
    ]},
    "tv": {"name": "Toshkent viloyati", "districts": [
        "Bekabad", "Bo'ka", "Bo'stonliq", "Chinoz", "Nurafshon", "Ohangaron", "Oqqo'rg'on",
        "Parkent", "Piskent", "Quyichirchiq", "Toshkent tumani", "O'rtachirchiq",
        "Yangiyo'l", "Yuqorichirchiq", "Zangiota",
    ]},
    "and": {"name": "Andijon viloyati", "districts": [
        "Andijon shahri", "Andijon tumani", "Asaka", "Baliqchi", "Bo'z", "Buloqboshi",
        "Izboskan", "Jalaquduq", "Xo'jaobod", "Qo'rg'ontepa", "Marhamat", "Oltinko'l",
        "Paxtaobod", "Shahrixon", "Ulug'nor",
    ]},
    "bux": {"name": "Buxoro viloyati", "districts": [
        "Buxoro shahri", "Buxoro tumani", "G'ijduvon", "Jondor", "Kogon", "Qorako'l",
        "Qorovulbozor", "Peshku", "Romitan", "Shofirkon", "Vobkent", "Olot",
    ]},
    "far": {"name": "Farg'ona viloyati", "districts": [
        "Farg'ona shahri", "Farg'ona tumani", "Beshariq", "Bog'dod", "Buvayda", "Dang'ara",
        "Furqat", "Oltiariq", "Qo'shtepa", "Quva", "Rishton", "So'x", "Toshloq",
        "Uchko'prik", "O'zbekiston tumani", "Yozyovon",
    ]},
    "jiz": {"name": "Jizzax viloyati", "districts": [
        "Jizzax shahri", "Arnasoy", "Baxmal", "Do'stlik", "Forish", "G'allaorol",
        "Mirzacho'l", "Paxtakor", "Yangiobod", "Zafarobod", "Zarbdor", "Zomin",
    ]},
    "xor": {"name": "Xorazm viloyati", "districts": [
        "Urganch shahri", "Urganch tumani", "Bog'ot", "Gurlan", "Xazorasp", "Xonqa",
        "Qo'shko'pir", "Shovot", "Yangiariq", "Yangibozor",
    ]},
    "nam": {"name": "Namangan viloyati", "districts": [
        "Namangan shahri", "Namangan tumani", "Chortoq", "Chust", "Kosonsoy", "Mingbuloq",
        "Norin", "Pop", "To'raqo'rg'on", "Uchqo'rg'on", "Uychi", "Yangiqo'rg'on",
    ]},
    "nav": {"name": "Navoiy viloyati", "districts": [
        "Navoiy shahri", "Karmana", "Konimex", "Navbahor", "Nurota", "Qiziltepa",
        "Tomdi", "Uchquduq", "Xatirchi",
    ]},
    "qas": {"name": "Qashqadaryo viloyati", "districts": [
        "Qarshi shahri", "Qarshi tumani", "Chiroqchi", "Dehqonobod", "G'uzor", "Kasbi",
        "Kitob", "Koson", "Mirishkor", "Muborak", "Nishon", "Shahrisabz", "Yakkabog'",
    ]},
    "qor": {"name": "Qoraqalpog'iston Respublikasi", "districts": [
        "Nukus shahri", "Amudaryo", "Beruniy", "Chimboy", "Ellikqal'a", "Kegeyli",
        "Mo'ynoq", "Nukus tumani", "Qanliko'l", "Qorao'zak", "Shumanay", "Taxtako'pir",
        "To'rtko'l", "Xo'jayli",
    ]},
    "sam": {"name": "Samarqand viloyati", "districts": [
        "Samarqand shahri", "Samarqand tumani", "Bulung'ur", "Ishtixon", "Jomboy",
        "Kattaqo'rg'on", "Narpay", "Nurobod", "Oqdaryo", "Payariq", "Paxtachi",
        "Pastdarg'om", "Toyloq", "Urgut",
    ]},
    "sir": {"name": "Sirdaryo viloyati", "districts": [
        "Guliston shahri", "Boyovut", "Guliston tumani", "Mirzaobod", "Oqoltin",
        "Sardoba", "Sayxunobod", "Sirdaryo", "Xovos",
    ]},
    "sur": {"name": "Surxondaryo viloyati", "districts": [
        "Termiz shahri", "Angor", "Bandixon", "Boysun", "Denov", "Jarqo'rg'on",
        "Muzrabot", "Oltinsoy", "Qiziriq", "Qumqo'rg'on", "Sariosiyo", "Sherobod",
        "Sho'rchi", "Termiz tumani", "Uzun",
    ]},
}

TEXTS = {
    "uz": {
        "choose_lang": "Tilni tanlang / Выберите язык:",
        "welcome": "Assalomu alaykum! Dacha bron qilish botiga xush kelibsiz. 🏡\n\nQuyidagi menyudan foydalaning:",
        "menu_list": "📋 Dachalar ro'yxati",
        "menu_my": "🗂 Mening bronlarim",
        "menu_support": "🆘 Yordam",
        "menu_admin": "🔐 Admin panel",
        "menu_owner": "🏘 Mening dachalarim",
        "menu_owner_apply": "🏘 Dacha egasi bo'lish",
        "choose_dacha": "Dachani tanlang:",
        "choose_region": "Viloyatni tanlang:",
        "choose_district": "Tumanni tanlang:",
        "choose_price_range": "Narx oralig'ini tanlang:",
        "choose_search_type": "Dachani qanday qidirasiz?",
        "search_by_price": "💰 Narx bo'yicha qidirish",
        "search_by_region": "🗺 Viloyat bo'yicha qidirish",
        "search_by_name": "🔍 Nomi bo'yicha qidirish",
        "ask_dacha_name": "Dacha nomini kiriting:",
        "back": "⬅️ Orqaga",
        "book_btn": "✅ Shu dachani bron qilish",
        "ask_checkin": "Kirish sanasini kiriting (masalan: 15.08.2026):",
        "ask_checkout": "Chiqish sanasini kiriting (masalan: 18.08.2026):",
        "ask_name": "Ismingizni kiriting:",
        "guest_register_intro": "Botdan foydalanishdan oldin qisqa ro'yxatdan o'tamiz (bir martalik):",
        "guest_registered": "✅ Ro'yxatdan o'tdingiz! Endi botdan to'liq foydalanishingiz mumkin.",
        "ask_phone": "Telefon raqamingizni kiriting (masalan: +998901234567):",
        "invalid_date": "❌ Sana noto'g'ri formatda. Masalan: 15.08.2026 shaklida kiriting.",
        "invalid_date_order": "❌ Chiqish sanasi kirish sanasidan keyin bo'lishi kerak.",
        "date_in_past": "❌ O'tgan sanani tanlab bo'lmaydi. Bugungi yoki keyingi sanani kiriting.",
        "date_too_far": "❌ Sana juda uzoq kelajakda (1 yildan ortiq). Yaqinroq sana tanlang.",
        "stay_too_long": "❌ Bron muddati juda uzoq (90 kundan ortiq). Qisqaroq muddat tanlang.",
        "cancel_operation_btn": "❌ Bekor qilish",
        "operation_cancelled": "Bekor qilindi. Asosiy menyudan davom eting.",
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
        "about_btn": "ℹ️ Biz haqimizda",
        "no_support_info": "Hozircha ma'lumot yo'q.",
        "ask_support_msg": "Xabaringizni yozing, operatorga yuboramiz:",
        "support_sent": "✅ Xabaringiz yuborildi! Tez orada operator javob beradi.",
        "support_reply_prefix": "💬 Operatordan javob:\n\n",
        "new_support_msg_admin": "🆘 Yangi murojaat!\n\n👤 {name} (@{username})\n💬 {text}",
        # --- Bandlik, bekor qilish, reyting ---
        "dates_unavailable": "❌ Afsuski, tanlangan sanalar band. Iltimos, boshqa sanalarni tanlang yoki kirish sanasini qaytadan kiriting.",
        "cancel_btn": "❌ Bekor qilish",
        "location_btn": "📍 Lokatsiya",
        "no_location": "Bu dacha uchun lokatsiya kiritilmagan.",
        "rate_btn": "⭐ Baholash",
        "cancel_confirm": "«{dacha}» ({checkin} - {checkout}) bronini bekor qilishni tasdiqlaysizmi?",
        "cancel_yes": "✅ Ha, bekor qilish",
        "cancel_no": "❌ Yo'q",
        "booking_cancelled": "✅ Bron bekor qilindi.",
        "already_cancelled": "Bu bron allaqachon bekor qilingan.",
        "cancelled_tag": " (bekor qilingan)",
        "rate_ask_stars": "Necha yulduz berasiz?",
        "rate_ask_comment": "Izoh qoldirmoqchimisiz? Yozing yoki o'tkazib yuboring.",
        "rate_skip_btn": "O'tkazib yuborish",
        "rate_thanks": "✅ Rahmat! Bahoyingiz saqlandi.",
        "already_rated": "Siz bu bronni allaqachon baholagansiz.",
        "rating_line": "\n⭐ {avg} ({count} ta sharh)",
        "no_rating_line": "\n⭐ Hali sharh yo'q",
        "reviews_btn": "📝 Sharhlar ({count})",
        "reviews_title": "📝 «{dacha}» sharhlari:\n\n",
        "review_item": "{rating} — {name}{comment}",
        "no_reviews": "Hali sharh yo'q.",
        "booking_cancelled_admin": "❌ Bron bekor qilindi!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}",
        # --- Dacha egalari ---
        "not_owner": "⛔️ Siz hali tasdiqlangan dacha egasi emassiz. Avval \"🏘 Dacha egasi bo'lish\" orqali ariza yuboring.",
        "owner_already_pending": "⏳ So'rovingiz hozircha ko'rib chiqilmoqda. Iltimos, kuting.",
        "owner_apply_sent": "✅ So'rovingiz yuborildi! Admin tasdiqlagach sizga xabar beramiz.",
        "owner_approved_msg": "🎉 Tabriklaymiz! Sizga dacha egasi huquqi berildi.\n\nEndi asosiy menyudagi \"🏘 Mening dachalarim\" tugmasi orqali dacha qo'sha olasiz.",
        "owner_rejected_msg": "❌ Afsuski, dacha egasi bo'lish so'rovingiz rad etildi.",
        "owner_panel_title": "🏘 Mening dachalarim paneli. Nima qilmoqchisiz?",
        "owner_btn_add": "➕ Yangi dacha qo'shish",
        "owner_btn_manage": "✏️ Dachalarimni boshqarish",
        "owner_manage_title": "Tahrirlash yoki o'chirish uchun dachani tanlang:",
        "owner_no_dachas": "Sizda hozircha dachalar yo'q. \"➕ Yangi dacha qo'shish\" orqali qo'shing.",
        "owner_btn_payments": "💰 To'lovlar tarixi",
        "owner_entry_choice": "Dacha egasi bo'lishning ikki yo'li bor:",
        "owner_have_code_btn": "🎟 Kodim bor",
        "owner_send_application_btn": "📝 Ariza yuborish",
        "ask_owner_code": "🎟 Agar admin sizga bir martalik kod bergan bo'lsa (Telegram, SMS va h.k. orqali), uni shu yerga yozing.\n\nKod tasdiqlansa, siz darhol dacha egasi huquqiga ega bo'lasiz va dacha qo'sha olasiz.",
        "invalid_owner_code": "❌ Bu kod noto'g'ri yoki allaqachon ishlatilgan. Qaytadan urinib ko'ring yoki ariza yuboring:",
        "owner_code_accepted": "🎉 Kod qabul qilindi! Sizga dacha egasi huquqi berildi.\n\nEndi asosiy menyudagi \"🏘 Mening dachalarim\" tugmasi orqali dacha qo'sha olasiz.",
        "ask_promo": "Promo-kodingiz bormi? Kiriting yoki o'tkazib yuboring:",
        "promo_skip_btn": "⏭ O'tkazib yuborish",
        "invalid_promo": "❌ Bu promo-kod noto'g'ri yoki faol emas.",
        "promo_applied": "\n\n🎁 Promo-kod «{code}» qo'llandi: -{discount:,} so'm",
        "payments_summary": "💰 To'lovlar tarixi\n\nJami bronlar: {count} ta\nJami summa: {total:,} so'm\nJami komissiya: {commission:,} so'm\nSizga tegishli sof daromad: {net:,} so'm",
        "payments_list_title": "📋 Oxirgi bronlar:",
        "payments_item": "\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n💰 {total:,} so'm | Komissiya: {commission:,} so'm",
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
        "ask_owner_name_uz": "1/8. Dacha nomini o'zbek tilida kiriting (masalan: 🏡 Mening dacham):",
        "ask_owner_name_ru": "2/8. Endi nomini rus tilida kiriting:",
        "ask_owner_desc_uz": "3/8. Tavsifni o'zbek tilida kiriting (xonalar soni, qulayliklar va h.k.):",
        "ask_owner_desc_ru": "4/8. Tavsifni rus tilida kiriting:",
        "ask_price": "5/8. Bir kechalik narxni faqat raqamlarda kiriting (masalan: 800000):",
        "invalid_price": "❌ Narx faqat raqamlardan iborat bo'lishi kerak. Masalan: 800000",
        "ask_photos": "6/8. Endi dacha rasmlarini yuboring (bittadan, 1 tadan 5 tagacha). Har bir rasmdan keyin \"✅ Tugatish\" tugmasini bosishingiz mumkin:",
        "invalid_photo": "❌ Iltimos, rasmni Telegram 'rasm' sifatida yuboring (fayl/hujjat sifatida emas).",
        "photo_added": "✅ Rasm qabul qilindi ({n}/5). Yana yuborishingiz yoki tugatishingiz mumkin.",
        "photos_max_reached": "✅ Maksimal 5 ta rasm qabul qilindi.",
        "photos_done_btn": "✅ Tugatish",
        "ask_video": "7/8. Xohlasangiz, dacha haqida qisqa video yuboring (ixtiyoriy):",
        "invalid_video": "❌ Iltimos, video sifatida yuboring, yoki o'tkazib yuboring.",
        "video_skip_btn": "⏭ O'tkazib yuborish",
        "ask_location": "8/8. Dacha lokatsiyasini yuboring (📍 tugma orqali) yoki manzilni matn ko'rinishida yozing. Xohlamasangiz o'tkazib yuborishingiz mumkin:",
        "invalid_location": "❌ Lokatsiya, manzil matni yoki \"O'tkazib yuborish\" tugmasidan birini tanlang.",
        "send_location_btn": "📍 Lokatsiyani yuborish",
        "skip_btn": "⏭ O'tkazib yuborish",
        "dacha_added_owner": "✅ Dachangiz qo'shildi va ro'yxatda ko'rinadi! Shartnoma PDF fayli sifatida yuborildi — uni saqlab qo'ying.",
    },
    "ru": {
        "choose_lang": "Tilni tanlang / Выберите язык:",
        "welcome": "Здравствуйте! Добро пожаловать в бот бронирования дач. 🏡\n\nВыберите пункт меню:",
        "menu_list": "📋 Список дач",
        "menu_my": "🗂 Мои брони",
        "menu_support": "🆘 Поддержка",
        "menu_admin": "🔐 Админ панель",
        "menu_owner": "🏘 Мои дачи",
        "menu_owner_apply": "🏘 Стать владельцем дачи",
        "choose_dacha": "Выберите дачу:",
        "choose_region": "Выберите область:",
        "choose_district": "Выберите район:",
        "choose_price_range": "Выберите ценовой диапазон:",
        "choose_search_type": "Как хотите искать дачу?",
        "search_by_price": "💰 По цене",
        "search_by_region": "🗺 По области",
        "search_by_name": "🔍 По названию",
        "ask_dacha_name": "Введите название дачи:",
        "back": "⬅️ Назад",
        "book_btn": "✅ Забронировать эту дачу",
        "ask_checkin": "Введите дату заезда (например: 15.08.2026):",
        "ask_checkout": "Введите дату выезда (например: 18.08.2026):",
        "ask_name": "Введите ваше имя:",
        "guest_register_intro": "Перед использованием бота пройдём короткую регистрацию (одноразово):",
        "guest_registered": "✅ Вы зарегистрированы! Теперь можете полноценно пользоваться ботом.",
        "ask_phone": "Введите номер телефона (например: +998901234567):",
        "invalid_date": "❌ Неверный формат даты. Пример: 15.08.2026",
        "invalid_date_order": "❌ Дата выезда должна быть позже даты заезда.",
        "date_in_past": "❌ Нельзя выбрать прошедшую дату. Введите сегодняшнюю или будущую дату.",
        "date_too_far": "❌ Дата слишком далеко в будущем (более 1 года). Выберите более близкую дату.",
        "stay_too_long": "❌ Слишком длительный срок брони (более 90 дней). Выберите более короткий срок.",
        "cancel_operation_btn": "❌ Отменить",
        "operation_cancelled": "Отменено. Продолжайте из главного меню.",
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
        "about_btn": "ℹ️ О нас",
        "no_support_info": "Пока нет информации.",
        "ask_support_msg": "Напишите ваше сообщение, мы передадим оператору:",
        "support_sent": "✅ Сообщение отправлено! Скоро оператор ответит.",
        "support_reply_prefix": "💬 Ответ оператора:\n\n",
        "new_support_msg_admin": "🆘 Новое обращение!\n\n👤 {name} (@{username})\n💬 {text}",
        # --- Доступность, отмена, рейтинг ---
        "dates_unavailable": "❌ К сожалению, выбранные даты заняты. Пожалуйста, выберите другие даты или введите дату заезда заново.",
        "cancel_btn": "❌ Отменить",
        "location_btn": "📍 Локация",
        "no_location": "Для этой дачи локация не указана.",
        "rate_btn": "⭐ Оценить",
        "cancel_confirm": "Подтвердить отмену брони «{dacha}» ({checkin} - {checkout})?",
        "cancel_yes": "✅ Да, отменить",
        "cancel_no": "❌ Нет",
        "booking_cancelled": "✅ Бронь отменена.",
        "already_cancelled": "Эта бронь уже отменена.",
        "cancelled_tag": " (отменена)",
        "rate_ask_stars": "Сколько звёзд поставите?",
        "rate_ask_comment": "Хотите оставить комментарий? Напишите его или пропустите.",
        "rate_skip_btn": "Пропустить",
        "rate_thanks": "✅ Спасибо! Ваша оценка сохранена.",
        "already_rated": "Вы уже оценили эту бронь.",
        "rating_line": "\n⭐ {avg} ({count} отзывов)",
        "no_rating_line": "\n⭐ Пока нет отзывов",
        "reviews_btn": "📝 Отзывы ({count})",
        "reviews_title": "📝 Отзывы о «{dacha}»:\n\n",
        "review_item": "{rating} — {name}{comment}",
        "no_reviews": "Пока нет отзывов.",
        "booking_cancelled_admin": "❌ Бронь отменена!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}",
        # --- Владельцы дач ---
        "not_owner": "⛔️ Вы ещё не подтверждённый владелец дачи. Сначала отправьте заявку через \"🏘 Стать владельцем дачи\".",
        "owner_already_pending": "⏳ Ваша заявка ещё рассматривается. Пожалуйста, подождите.",
        "owner_apply_sent": "✅ Заявка отправлена! Сообщим вам, как только админ её рассмотрит.",
        "owner_approved_msg": "🎉 Поздравляем! Вам предоставлены права владельца дачи.\n\nТеперь вы можете добавить дачу через кнопку \"🏘 Мои дачи\" в главном меню.",
        "owner_rejected_msg": "❌ К сожалению, ваша заявка на статус владельца дачи отклонена.",
        "owner_panel_title": "🏘 Панель моих дач. Что хотите сделать?",
        "owner_btn_add": "➕ Добавить новую дачу",
        "owner_btn_manage": "✏️ Управлять моими дачами",
        "owner_manage_title": "Выберите дачу для редактирования или удаления:",
        "owner_no_dachas": "У вас пока нет дач. Добавьте через \"➕ Добавить новую дачу\".",
        "owner_btn_payments": "💰 История платежей",
        "owner_entry_choice": "Есть два способа стать владельцем дачи:",
        "owner_have_code_btn": "🎟 У меня есть код",
        "owner_send_application_btn": "📝 Отправить заявку",
        "ask_owner_code": "🎟 Если админ дал вам одноразовый код (через Telegram, SMS и т.д.), введите его здесь.\n\nЕсли код подтвердится, вы сразу получите права владельца дачи и сможете добавлять дачи.",
        "invalid_owner_code": "❌ Этот код неверен или уже использован. Попробуйте снова или отправьте заявку:",
        "owner_code_accepted": "🎉 Код принят! Вам предоставлены права владельца дачи.\n\nТеперь вы можете добавить дачу через кнопку \"🏘 Мои дачи\" в главном меню.",
        "ask_promo": "У вас есть промокод? Введите или пропустите:",
        "promo_skip_btn": "⏭ Пропустить",
        "invalid_promo": "❌ Этот промокод неверен или неактивен.",
        "promo_applied": "\n\n🎁 Промокод «{code}» применён: -{discount:,} сум",
        "payments_summary": "💰 История платежей\n\nВсего броней: {count}\nОбщая сумма: {total:,} сум\nОбщая комиссия: {commission:,} сум\nВаш чистый доход: {net:,} сум",
        "payments_list_title": "📋 Последние брони:",
        "payments_item": "\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n💰 {total:,} сум | Комиссия: {commission:,} сум",
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
        "ask_owner_name_uz": "1/8. Введите название дачи на узбекском (например: 🏡 Моя дача):",
        "ask_owner_name_ru": "2/8. Теперь введите название на русском:",
        "ask_owner_desc_uz": "3/8. Введите описание на узбекском (кол-во комнат, удобства и т.д.):",
        "ask_owner_desc_ru": "4/8. Введите описание на русском:",
        "ask_price": "5/8. Введите цену за ночь только цифрами (например: 800000):",
        "invalid_price": "❌ Цена должна состоять только из цифр. Например: 800000",
        "ask_photos": "6/8. Теперь отправьте фото дачи (по одному, от 1 до 5 штук). После каждого фото можно нажать \"✅ Готово\":",
        "invalid_photo": "❌ Пожалуйста, отправьте изображение как «фото» в Telegram (не как файл/документ).",
        "photo_added": "✅ Фото принято ({n}/5). Можете отправить ещё или завершить.",
        "photos_max_reached": "✅ Принято максимум 5 фото.",
        "photos_done_btn": "✅ Готово",
        "ask_video": "7/8. При желании отправьте короткое видео о даче (необязательно):",
        "invalid_video": "❌ Пожалуйста, отправьте именно видео, либо пропустите.",
        "video_skip_btn": "⏭ Пропустить",
        "ask_location": "8/8. Отправьте геолокацию дачи (кнопкой 📍) или укажите адрес текстом. Можно пропустить:",
        "invalid_location": "❌ Выберите геолокацию, введите адрес текстом или нажмите \"Пропустить\".",
        "send_location_btn": "📍 Отправить геолокацию",
        "skip_btn": "⏭ Пропустить",
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
    "ask_name_uz": "1/8. Dacha nomini o'zbek tilida kiriting (masalan: 🏡 Chimyon dachasi):",
    "ask_name_ru": "2/8. Endi nomini rus tilida kiriting:",
    "ask_desc_uz": "3/8. Tavsifni o'zbek tilida kiriting:",
    "ask_desc_ru": "4/8. Tavsifni rus tilida kiriting:",
    "ask_price": "5/8. Bir kechalik narxni faqat raqamlarda kiriting (masalan: 800000):",
    "invalid_price": "❌ Narx faqat raqamlardan iborat bo'lishi kerak. Masalan: 800000",
    "ask_photos": "6/8. Endi dacha rasmlarini yuboring (bittadan, 1-5 tagacha). Har birdan keyin \"✅ Tugatish\" tugmasini bosishingiz mumkin:",
    "invalid_photo": "❌ Iltimos, rasmni Telegram 'rasm' sifatida yuboring.",
    "photo_added": "✅ Rasm qabul qilindi ({n}/5). Yana yuborishingiz yoki tugatishingiz mumkin.",
    "photos_max_reached": "✅ Maksimal 5 ta rasm qabul qilindi.",
    "ask_video": "7/8. Xohlasangiz, qisqa video yuboring (ixtiyoriy):",
    "invalid_video": "❌ Iltimos, video sifatida yuboring, yoki o'tkazib yuboring.",
    "ask_location": "8/8. Lokatsiyani yuboring yoki manzilni matn ko'rinishida yozing. O'tkazib yuborishingiz mumkin:",
    "invalid_location": "❌ Lokatsiya, manzil matni yoki \"O'tkazib yuborish\" tugmasidan birini tanlang.",
    "choose_region": "Viloyatni tanlang:",
    "choose_district": "Tumanni tanlang:",
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
    "field_media": "🖼 Rasm/Video",
    "field_location": "📍 Lokatsiya",
    "field_region": "🗺 Viloyat/Tuman",
    "field_verify": "✅ Tasdiqlash/bekor qilish",
    "verify_on": "✅ Dacha tasdiqlangan deb belgilandi.",
    "verify_off": "⬜ Tasdiqlash belgisi olib tashlandi.",
    # --- Owner kodlari ---
    "btn_owner_codes": "🎟 Owner kodlari",
    "owner_codes_panel_title": "🎟 Owner kodlari. Nima qilmoqchisiz?",
    "btn_new_owner_code": "➕ Yangi kod yaratish",
    "btn_list_owner_codes": "📋 Kodlar ro'yxati",
    "owner_code_generated": "✅ Yangi kod yaratildi:\n\n`{code}`\n\n_(kodni bosing — avtomatik nusxalanadi)_\n\nBuni owner'ga o'zingiz yuboring (Telegram, SMS va h.k.). Kod faqat bir marta ishlatiladi.",
    "no_owner_codes": "Hozircha kodlar yo'q.",
    "owner_codes_list_title": "🎟 Kodlar ro'yxati:",
    "code_active_tag": "✅ faol",
    "code_used_tag": "❌ ishlatilgan (user: {uid})",
    # --- Promo-kodlar ---
    "btn_promocodes": "🎁 Promo-kodlar",
    "promo_panel_title": "🎁 Promo-kodlar. Nima qilmoqchisiz?",
    "btn_new_promo": "➕ Yangi promo-kod",
    "btn_list_promo": "📋 Ro'yxat",
    "ask_promo_code": "Promo-kod matnini kiriting (masalan: YOZGI2026):",
    "invalid_promo_code": "❌ Kod bo'sh bo'lishi mumkin emas.",
    "promo_code_exists": "❌ Bu kod allaqachon mavjud. Boshqa kod kiriting:",
    "ask_promo_type": "Chegirma turini tanlang:",
    "promo_type_percent": "% Foizli",
    "promo_type_fixed": "💵 Qat'iy summa",
    "ask_promo_percent": "Chegirma foizini kiriting (masalan: 10):",
    "ask_promo_fixed": "Chegirma summasini so'mda kiriting (masalan: 50000):",
    "invalid_promo_value": "❌ Noto'g'ri qiymat. Qaytadan kiriting:",
    "promo_created": "✅ Promo-kod «{code}» yaratildi!",
    "no_promocodes": "Hozircha promo-kodlar yo'q.",
    "promo_list_title": "🎁 Promo-kodlar (bosib yoqish/o'chirish mumkin):",
    "promo_toggled": "Holat o'zgartirildi.",
    "promo_skip_btn": "⏭ O'tkazib yuborish",
    "code_deleted": "🗑 O'chirildi.",
    "cancel_operation_btn": "❌ Bekor qilish",
    "ask_promo_limit": "Nechta marta ishlatilishi mumkinligini kiriting (raqam), yoki cheksiz bo'lsa o'tkazib yuboring:",
    "ask_promo_expiry": "Amal qilish muddatini kiriting (masalan: 31.12.2026), yoki cheksiz bo'lsa o'tkazib yuboring:",
    "btn_guests": "👥 Ro'yxatdan o'tgan mehmonlar",
    "btn_broadcast": "📢 Hammaga xabar yuborish",
    "ask_broadcast_text": "Barcha foydalanuvchilarga yuboriladigan xabar matnini kiriting:",
    "broadcast_preview": "📢 Xabar {count} ta foydalanuvchiga yuboriladi:\n\n---\n{text}\n---\n\nTasdiqlaysizmi?",
    "broadcast_send_btn": "✅ Yuborish",
    "broadcast_done": "✅ Yuborildi: {sent} ta\n❌ Yuborilmadi: {failed} ta",
    "btn_about": "ℹ️ Biz haqimizda",
    "about_panel_title": "ℹ️ Hozirgi \"Biz haqimizda\" matni:",
    "btn_edit_about": "✏️ Matnni tahrirlash",
    "ask_about_text": "Yangi \"Biz haqimizda\" matnini yuboring:\n\nHozirgi:\n{old}",
    "about_updated": "✅ Matn yangilandi!",
    "no_guests": "Hozircha ro'yxatdan o'tgan mehmonlar yo'q.",
    "guests_title": "👥 Ro'yxatdan o'tgan mehmonlar ({count} ta):",
    "field_photo": "🖼 Rasm",
    "ask_new_value": "Yangi qiymatni kiriting:\n\nHozirgi: {old}",
    "ask_new_photo": "Yangi rasmni yuboring (rasm sifatida):",
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
    # --- Komissiya boshqaruvi ---
    "btn_commissions": "💰 Komissiyalarni boshqarish",
    "commissions_title": "💰 Komissiyalar. Standart: {default}%.\nOwner tanlab, alohida foizini o'zgartiring:",
    "no_owners": "Hozircha tasdiqlangan dacha egalari yo'q.",
    "commission_edit_btn": "✏️ O'zgartirish",
    "commission_reset_btn": "↩️ Standartga qaytarish",
    "commission_pause_btn": "⏸ Komissiyani to'xtatish",
    "commission_resume_btn": "▶️ Komissiyani qayta yoqish",
    "commission_paused": "⏸ Bu owner uchun komissiya to'xtatildi (0% olinadi).",
    "commission_resumed": "▶️ Bu owner uchun komissiya qayta yoqildi.",
    "ask_commission": "«{name}» uchun yangi komissiya foizini kiriting (masalan: 1.5 yoki 0):",
    "invalid_commission": "❌ Foiz 0 dan 100 gacha son bo'lishi kerak. Masalan: 1.5",
    "commission_updated": "✅ Komissiya yangilandi!",
    "commission_reset_done": "↩️ Standart komissiyaga qaytarildi.",
    # --- Shartnoma matnlarini boshqarish ---
    "btn_contracts": "📜 Shartnoma matnlari",
    "contracts_panel_title": "📜 Shartnoma matnlari. Qaysi birini tahrirlaysiz?",
    "btn_edit_guest_contract": "✏️ Mehmon shartnomasi",
    "btn_edit_owner_contract": "✏️ Dacha egasi shartnomasi",
    "contract_kind_guest": "Mehmon shartnomasi",
    "contract_kind_owner": "Dacha egasi shartnomasi",
    "ask_contract_text": "«{label}» uchun yangi to'liq matnni yuboring.\n\nHozirgi matn:\n\n{old}",
    "contract_updated": "✅ Shartnoma matni yangilandi!",
}

router = Router()


# ============ HOLATLAR (FSM) ============
class BookingStates(StatesGroup):
    entering_checkin = State()
    entering_checkout = State()
    entering_name = State()
    entering_phone = State()
    entering_promo = State()
    confirming = State()


class AdminStates(StatesGroup):
    adding_name_uz = State()
    adding_name_ru = State()
    adding_desc_uz = State()
    adding_desc_ru = State()
    adding_price = State()
    adding_photos = State()
    adding_video = State()
    adding_location = State()
    editing_value = State()
    editing_photos = State()
    editing_video = State()
    editing_location = State()
    editing_commission = State()
    editing_contract = State()


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
    entering_code = State()


class GuestRegisterStates(StatesGroup):
    entering_name = State()
    entering_phone = State()


class OwnerAddStates(StatesGroup):
    name_uz = State()
    name_ru = State()
    desc_uz = State()
    desc_ru = State()
    price = State()
    photos = State()
    video = State()
    location = State()


class ReviewStates(StatesGroup):
    entering_comment = State()


class DachaSearchStates(StatesGroup):
    entering_name = State()


class BroadcastStates(StatesGroup):
    entering_message = State()


class AboutStates(StatesGroup):
    editing_text = State()


class PromoStates(StatesGroup):
    entering_code = State()
    choosing_type = State()
    entering_value = State()
    entering_limit = State()
    entering_expiry = State()


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


def load_contract_texts() -> dict:
    return _load(CONTRACT_TEXTS_FILE, DEFAULT_CONTRACT_TEXTS)


def save_contract_texts(texts: dict):
    _save(CONTRACT_TEXTS_FILE, texts)


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


def load_guests() -> dict:
    return _load(GUESTS_FILE, {})


DEFAULT_ABOUT_TEXT = (
    "ℹ️ Biz haqimizda\n\n"
    "🏡 Ushbu bot — dachalarni onlayn bron qilish platformasi.\n"
    "📅 Yaratilgan sana: 2026\n"
    "👤 Bot egasi/administratori: platforma admini\n"
    "🎯 Maqsad: dacha egalari va mehmonlarni qulay, ishonchli va tezkor tarzda bog'lash."
)


def load_about_text() -> str:
    if not os.path.exists(ABOUT_FILE):
        save_about_text(DEFAULT_ABOUT_TEXT)
        return DEFAULT_ABOUT_TEXT
    with open(ABOUT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def save_about_text(text: str):
    with open(ABOUT_FILE, "w", encoding="utf-8") as f:
        f.write(text)


def save_guests(guests: dict):
    _save(GUESTS_FILE, guests)


def load_owner_codes() -> dict:
    return _load(OWNER_CODES_FILE, {})


def save_owner_codes(codes: dict):
    _save(OWNER_CODES_FILE, codes)


def load_promocodes() -> dict:
    return _load(PROMO_FILE, {})


def save_promocodes(promos: dict):
    _save(PROMO_FILE, promos)


def get_commission_rate(owner_id) -> float:
    """Owner uchun belgilangan individual komissiya foizini qaytaradi,
    belgilanmagan bo'lsa standart COMMISSION_RATE qaytaradi.
    Agar admin komissiyani shu owner uchun vaqtincha O'CHIRGAN bo'lsa — 0 qaytaradi
    (asl foiz esa saqlanib qoladi, qayta yoqilganda tiklanadi)."""
    if not owner_id:
        return COMMISSION_RATE
    owners = load_owners()
    rec = owners.get(str(owner_id))
    if not rec:
        return COMMISSION_RATE
    if rec.get("commission_enabled") is False:
        return 0.0
    if rec.get("commission_rate") is not None:
        return rec["commission_rate"]
    return COMMISSION_RATE


def load_reviews() -> list:
    return _load(REVIEWS_FILE, [])


def save_reviews(reviews: list):
    _save(REVIEWS_FILE, reviews)


def add_review(review: dict):
    reviews = load_reviews()
    reviews.append(review)
    save_reviews(reviews)


def get_dacha_rating(dacha_key: str):
    reviews = load_reviews()
    ratings = [r["rating"] for r in reviews if r["dacha_key"] == dacha_key]
    if not ratings:
        return None, 0
    return round(sum(ratings) / len(ratings), 1), len(ratings)


def is_dates_available(dacha_key: str, checkin_dt: datetime, checkout_dt: datetime) -> bool:
    """Berilgan sana oralig'i shu dacha uchun bo'sh ekanligini tekshiradi
    (bekor qilingan bronlar hisobga olinmaydi)."""
    bookings = load_bookings()
    for b in bookings:
        if b.get("dacha_key") != dacha_key:
            continue
        if b.get("status") == "cancelled":
            continue
        if "checkin_dt" not in b or "checkout_dt" not in b:
            continue
        existing_in = datetime.fromisoformat(b["checkin_dt"])
        existing_out = datetime.fromisoformat(b["checkout_dt"])
        if checkin_dt < existing_out and checkout_dt > existing_in:
            return False
    return True


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


def _build_contract_pdf(filename_prefix: str, person_label: str, person_name: str, dacha_name: str,
                         extra_line: str, body_text: str, telegram_id: int) -> str:
    os.makedirs(CONTRACTS_DIR, exist_ok=True)
    path = os.path.join(CONTRACTS_DIR, f"{filename_prefix}_{uuid.uuid4().hex[:8]}.pdf")
    doc = SimpleDocTemplate(path, pagesize=A4)
    base = getSampleStyleSheet()
    style_title = ParagraphStyle("TitleCyr", parent=base["Title"], fontName=PDF_FONT_BOLD)
    style_heading = ParagraphStyle("HeadingCyr", parent=base["Heading2"], fontName=PDF_FONT_BOLD)
    style_normal = ParagraphStyle("NormalCyr", parent=base["Normal"], fontName=PDF_FONT)

    now = now_tz()
    story = [
        Paragraph("SHARTNOMA", style_title),
        Spacer(1, 10),
        Paragraph(f"Sana: {now.strftime('%d.%m.%Y %H:%M')}", style_normal),
        Paragraph(f"{person_label}: {person_name}", style_normal),
        Paragraph(f"Dacha nomi: {dacha_name}", style_normal),
        Paragraph(extra_line, style_normal),
        Spacer(1, 14),
        Paragraph("Shartlar:", style_heading),
    ]
    for line in body_text.split("\n"):
        line = line.strip()
        if not line:
            story.append(Spacer(1, 6))
            continue
        story.append(Paragraph(line, style_normal))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 14))
    story.append(Paragraph("Elektron rozilik dalili:", style_heading))
    consent = (
        f"Ushbu shartnoma {now.strftime('%d.%m.%Y')} kuni soat {now.strftime('%H:%M')}da "
        f"Telegram orqali {person_name} (Telegram ID: {telegram_id}) tomonidan \"Roziman\" "
        f"tugmasini bosish yo'li bilan elektron tasdiqlandi."
    )
    story.append(Paragraph(consent, style_normal))
    doc.build(story)
    return path


def generate_contract_pdf(owner_name: str, dacha_name: str, price: int, telegram_id: int) -> str:
    body = load_contract_texts()["owner"]
    extra = f"Bir kechalik narx: {price:,} so'm".replace(",", " ")
    return _build_contract_pdf("shartnoma_owner", "Dacha egasi", owner_name, dacha_name, extra, body, telegram_id)


def generate_guest_contract_pdf(guest_name: str, dacha_name: str, checkin: str, checkout: str, telegram_id: int) -> str:
    body = load_contract_texts()["guest"]
    extra = f"Bron sanalari: {checkin} - {checkout}"
    return _build_contract_pdf("shartnoma_mehmon", "Mehmon", guest_name, dacha_name, extra, body, telegram_id)


# ============ KLAVIATURALAR (HAMMASI INLINE) ============
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
    # status == "pending" -> qo'shimcha tugma ko'rsatilmaydi

    if is_admin(user_id):
        rows.append([KeyboardButton(text=t["menu_admin"])])

    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def dacha_list_kb(lang: str, dachas: dict, back_cb: str = "back_main") -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            text=("✅ " if d.get("verified") else "") + d[f"name_{lang}"], callback_data=f"view_{key}"
        )]
        for key, d in dachas.items()
    ]
    buttons.append([InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def search_menu_kb(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["search_by_price"], callback_data="pricefilter_menu")],
            [InlineKeyboardButton(text=t["search_by_region"], callback_data="searchregion_menu")],
            [InlineKeyboardButton(text=t["search_by_name"], callback_data="searchname_menu")],
            [InlineKeyboardButton(text=t["back"], callback_data="back_main")],
        ]
    )


def region_select_kb(dachas: dict, callback_prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    """Faqat foydalanuvchi DACHALARNI BROUZING qilayotganda (callback_prefix == 'browseregion')
    mavjud dachalar bo'lgan viloyatlar filtrlanadi. Qo'shish (oregion/aregion) va tahrirlash
    (efregionsel) oqimlarida har doim TO'LIQ ro'yxat ko'rsatiladi — chunki bu yerda tanlov
    cheksiz, mavjud dachalarga bog'liq emas."""
    if callback_prefix == "browseregion":
        present = {d["region"] for d in dachas.values() if d.get("region")}
    else:
        present = set(REGIONS.keys())
    rows = []
    rows += [
        [InlineKeyboardButton(text=REGIONS[key]["name"], callback_data=f"{callback_prefix}_{key}")]
        for key in REGIONS if key in present
    ]
    if callback_prefix == "browseregion" and any(not d.get("region") for d in dachas.values()):
        rows.append([InlineKeyboardButton(text="📦 Boshqalar", callback_data="browseregion_boshqa")])
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def district_select_kb(region_key: str, dachas: dict, callback_prefix: str, back_cb: str) -> InlineKeyboardMarkup:
    """Tuman tanlash klaviaturasi. Qo'shish oqimi uchun (callback_prefix oxiri 'district' bilan
    tugab, 'a'/'o' bilan boshlansa) barcha tumanlar, brauzing uchun faqat dachasi bor tumanlar."""
    all_districts = REGIONS.get(region_key, {}).get("districts", [])
    if callback_prefix.startswith("browse"):
        present = {d.get("district") for d in dachas.values() if d.get("region") == region_key}
        indices = [i for i, name in enumerate(all_districts) if name in present]
    else:
        indices = list(range(len(all_districts)))
    rows = [
        [InlineKeyboardButton(text=all_districts[i], callback_data=f"{callback_prefix}_{region_key}_{i}")]
        for i in indices
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dacha_detail_kb(lang: str, dacha_key: str, review_count: int = 0) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    rows = [[InlineKeyboardButton(text=t["book_btn"], callback_data=f"book_{dacha_key}")]]
    if review_count:
        rows.append(
            [InlineKeyboardButton(text=t["reviews_btn"].format(count=review_count), callback_data=f"reviews_{dacha_key}")]
        )
    rows.append([InlineKeyboardButton(text=t["back"], callback_data="menu_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def my_bookings_text(lang: str, user_bookings: list) -> str:
    t = TEXTS[lang]
    if not user_bookings:
        return t["no_bookings"]
    text = t["your_bookings"]
    for b in user_bookings:
        tag = t["cancelled_tag"] if b.get("status") == "cancelled" else ""
        text += f"🏡 {b['dacha']}\n📅 {b['checkin']} - {b['checkout']}{tag}\n\n"
    return text


def my_bookings_kb(lang: str, user_bookings: list):
    t = TEXTS[lang]
    reviews = load_reviews()
    reviewed_ids = {r["booking_id"] for r in reviews}
    dachas = load_dachas()
    rows = []
    for b in user_bookings:
        status = b.get("status", "active")
        label_tail = f"{b['dacha']} ({b['checkin']})"
        if status == "active":
            rows.append(
                [InlineKeyboardButton(text=f"{t['cancel_btn']}: {label_tail}", callback_data=f"cancelbooking_{b['id']}")]
            )
            d = dachas.get(b.get("dacha_key"))
            if d and d.get("location"):
                rows.append(
                    [InlineKeyboardButton(text=f"{t['location_btn']}: {label_tail}", callback_data=f"showloc_{b['id']}")]
                )
        if status != "cancelled" and b["id"] not in reviewed_ids:
            rows.append(
                [InlineKeyboardButton(text=f"{t['rate_btn']}: {label_tail}", callback_data=f"rate_{b['id']}")]
            )
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)


def star_rating_kb(booking_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⭐" * n, callback_data=f"ratestar_{booking_id}_{n}") for n in (1, 2, 3)],
            [InlineKeyboardButton(text="⭐" * n, callback_data=f"ratestar_{booking_id}_{n}") for n in (4, 5)],
        ]
    )


def rate_comment_kb(lang: str, booking_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]["rate_skip_btn"], callback_data=f"ratecomment_skip_{booking_id}")]
        ]
    )


async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    """`callback.message` ba'zan rasm/video xabari bo'lishi mumkin (masalan bitta rasmli
    dacha ko'rinishi) — bunday holatda oddiy `edit_text` Telegram tomonidan rad etiladi
    (chunki rasm xabarida "text" emas, "caption" bo'ladi), va tugma "ishlamay qoladi".
    Shu funksiya buni avtomatik aniqlab, xato bo'lsa eski xabarni o'chirib, o'rniga
    yangi (oddiy matnli) xabar yuboradi — foydalanuvchi doim javob oladi."""
    try:
        await callback.message.edit_text(text, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception:
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer(text, reply_markup=reply_markup, parse_mode=parse_mode)


def cancel_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """Matn kiritish so'raladigan deyarli har bir bosqichga biriktiriladigan
    universal "Bekor qilish" tugmasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=TEXTS[lang]["cancel_operation_btn"], callback_data="cancel_operation")]]
    )


@router.callback_query(F.data == "cancel_operation")
async def cancel_operation(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(None)
    await state.update_data(lang=lang)
    await safe_edit_text(callback, TEXTS[lang]["operation_cancelled"])
    await callback.answer()


def cancel_booking_confirm_kb(lang: str, booking_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=TEXTS[lang]["cancel_yes"], callback_data=f"cancelyes_{booking_id}"),
                InlineKeyboardButton(text=TEXTS[lang]["cancel_no"], callback_data="menu_my"),
            ]
        ]
    )


def done_inline_kb(lang: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=TEXTS[lang]["photos_done_btn"], callback_data=callback_data)]]
    )


def skip_inline_kb(lang: str, callback_data: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]["video_skip_btn"], callback_data=callback_data)],
            [InlineKeyboardButton(text=TEXTS[lang]["cancel_operation_btn"], callback_data="cancel_operation")],
        ]
    )


def location_request_kb(lang: str) -> ReplyKeyboardMarkup:
    t = TEXTS[lang]
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t["send_location_btn"], request_location=True)],
            [KeyboardButton(text=t["skip_btn"])],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def support_list_kb(lang: str, items: dict) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    rows = [[InlineKeyboardButton(text=v["title"], callback_data=f"sview_{k}")] for k, v in items.items()]
    rows.append([InlineKeyboardButton(text=t["write_support"], callback_data="support_write")])
    rows.append([InlineKeyboardButton(text=t["about_btn"], callback_data="menu_about")])
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
            [InlineKeyboardButton(text=A["btn_commissions"], callback_data="admin_commissions")],
            [InlineKeyboardButton(text=A["btn_contracts"], callback_data="admin_contracts")],
            [InlineKeyboardButton(text=A["btn_owner_codes"], callback_data="admin_owner_codes")],
            [InlineKeyboardButton(text=A["btn_promocodes"], callback_data="admin_promocodes")],
            [InlineKeyboardButton(text=A["btn_guests"], callback_data="admin_guests_0")],
            [InlineKeyboardButton(text=A["btn_broadcast"], callback_data="admin_broadcast")],
            [InlineKeyboardButton(text=A["btn_about"], callback_data="admin_about")],
            [InlineKeyboardButton(text=A["back"], callback_data="back_main")],
        ]
    )


def owner_panel_kb(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["owner_btn_add"], callback_data="owner_add")],
            [InlineKeyboardButton(text=t["owner_btn_manage"], callback_data="owner_manage")],
            [InlineKeyboardButton(text=t["owner_btn_payments"], callback_data="owner_payments")],
            [InlineKeyboardButton(text=t["back"], callback_data="back_main")],
        ]
    )


def owner_entry_choice_kb(lang: str) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t["owner_have_code_btn"], callback_data="owner_code_start")],
            [InlineKeyboardButton(text=t["owner_send_application_btn"], callback_data="owner_apply_form_start")],
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


def edit_field_kb(dacha_key: str, back_cb: str, show_verify: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=A["field_name_uz"], callback_data=f"ef_nu_{dacha_key}")],
        [InlineKeyboardButton(text=A["field_name_ru"], callback_data=f"ef_nr_{dacha_key}")],
        [InlineKeyboardButton(text=A["field_desc_uz"], callback_data=f"ef_du_{dacha_key}")],
        [InlineKeyboardButton(text=A["field_desc_ru"], callback_data=f"ef_dr_{dacha_key}")],
        [InlineKeyboardButton(text=A["field_price"], callback_data=f"ef_pr_{dacha_key}")],
        [InlineKeyboardButton(text=A["field_media"], callback_data=f"efmedia_{dacha_key}")],
        [InlineKeyboardButton(text=A["field_location"], callback_data=f"efloc_{dacha_key}")],
        [InlineKeyboardButton(text=A["field_region"], callback_data=f"efregion_{dacha_key}")],
    ]
    if show_verify:
        rows.append([InlineKeyboardButton(text=A["field_verify"], callback_data=f"toggleverify_{dacha_key}")])
    rows.append([InlineKeyboardButton(text=A["back"], callback_data=back_cb)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def get_dacha_photos(d: dict) -> list:
    """Yangi 'photos' ro'yxatini, mavjud bo'lmasa eski 'photo_id' maydonini qaytaradi (orqaga moslik)."""
    photos = d.get("photos")
    if photos:
        return photos
    legacy = d.get("photo_id")
    return [legacy] if legacy else []


async def send_dacha_media(bot: Bot, chat_id: int, photos: list, video_id, text: str, reply_markup=None) -> str:
    """Dacha uchun rasm/video(lar)ni to'g'ri usulda yuboradi:
    - 0 ta bo'lsa: hech narsa yubormaydi ("none" qaytaradi)
    - 1 ta bo'lsa: bitta xabar, tugma SHU XABARGA biriktiriladi ("single" qaytaradi)
    - 2+ bo'lsa: albom sifatida (Telegram bunda tugma biriktirishga ruxsat bermaydi — bu
      platformaning o'zining cheklovi, alohida xabar bilan tugma yuborish shart bo'ladi;
      "album" qaytaradi)."""
    items = [("photo", p) for p in photos[:9]]
    if video_id:
        items.append(("video", video_id))

    if not items:
        return "none"
    if len(items) == 1:
        kind, file_id = items[0]
        if kind == "photo":
            await bot.send_photo(chat_id, photo=file_id, caption=text, reply_markup=reply_markup)
        else:
            await bot.send_video(chat_id, video=file_id, caption=text, reply_markup=reply_markup)
        return "single"

    media = [
        InputMediaPhoto(media=fid, caption=text if i == 0 else None)
        if kind == "photo"
        else InputMediaVideo(media=fid, caption=text if i == 0 else None)
        for i, (kind, fid) in enumerate(items)
    ]
    await bot.send_media_group(chat_id, media)
    return "album"


async def show_dacha_detail(target, lang: str, dacha_key: str, d: dict):
    """Dacha tafsilotlarini ko'rsatadi — rasm/video albomi va matn bilan.
    Lokatsiya BU YERDA yuborilmaydi — u faqat bron qilingandan keyin,
    "Mening bronlarim"dagi alohida tugma orqali beriladi.
    `target` — CallbackQuery yoki Message bo'lishi mumkin."""
    price_line = f"\n\n💰 {d.get('price', 0):,} so'm/kecha".replace(",", " ")
    avg, count = get_dacha_rating(dacha_key)
    if count:
        rating_line = TEXTS[lang]["rating_line"].format(avg=avg, count=count)
    else:
        rating_line = TEXTS[lang]["no_rating_line"]
    address_line = f"\n\n📍 {d['address']}" if d.get("address") else ""
    region_line = ""
    if d.get("region") and d.get("district"):
        region_name = REGIONS.get(d["region"], {}).get("name", "")
        region_line = f"\n\n🗺 {region_name}, {d['district']}"
    verified_prefix = "✅ " if d.get("verified") else ""
    text = f"{verified_prefix}{d[f'name_{lang}']}\n\n{d[f'desc_{lang}']}{price_line}{rating_line}{region_line}{address_line}"
    kb = dacha_detail_kb(lang, dacha_key, review_count=count)

    photos = get_dacha_photos(d)
    video_id = d.get("video_id")
    has_media = bool(photos or video_id)

    if isinstance(target, CallbackQuery):
        message = target.message
        bot = target.bot
        chat_id = message.chat.id
        if has_media:
            result = await send_dacha_media(bot, chat_id, photos, video_id, text, reply_markup=kb)
            if result == "album":
                # Telegram albomga tugma biriktirishga ruxsat bermaydi — alohida xabar shart
                await bot.send_message(chat_id, "⬇️", reply_markup=kb)
            try:
                await message.delete()
            except Exception:
                pass
        else:
            await message.edit_text(text, reply_markup=kb)
    else:
        bot = target.bot
        chat_id = target.chat.id
        if has_media:
            result = await send_dacha_media(bot, chat_id, photos, video_id, text, reply_markup=kb)
            if result == "album":
                await target.answer("⬇️", reply_markup=kb)
        else:
            await target.answer(text, reply_markup=kb)


# ============ START / TIL ============
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    # Eski versiyada yuborilgan pastki doimiy klaviaturani (agar bo'lsa) olib tashlaymiz
    removed = await message.answer("⏳", reply_markup=ReplyKeyboardRemove())
    try:
        await removed.delete()
    except Exception:
        pass
    await message.answer(TEXTS["uz"]["choose_lang"], reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang_"))
async def choose_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)
    t = TEXTS[lang]
    await safe_edit_text(callback, t["choose_lang"])

    guests = load_guests()
    if str(callback.from_user.id) not in guests:
        await state.set_state(GuestRegisterStates.entering_name)
        await callback.message.answer(t["guest_register_intro"])
        await callback.message.answer(t["ask_name"], reply_markup=cancel_kb("uz"))
        await callback.answer()
        return

    await callback.message.answer(t["welcome"], reply_markup=main_reply_kb(lang, callback.from_user.id))
    await callback.answer()


@router.message(GuestRegisterStates.entering_name)
async def guest_register_name(message: Message, state: FSMContext):
    await state.update_data(g_name=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(GuestRegisterStates.entering_phone)
    await message.answer(TEXTS[lang]["ask_phone"], reply_markup=cancel_kb(lang))


@router.message(GuestRegisterStates.entering_phone)
async def guest_register_phone(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    phone = message.text.strip()
    if not (phone.startswith("+") and phone[1:].isdigit() and len(phone) >= 10):
        await message.answer(TEXTS[lang]["invalid_phone"])
        return

    guests = load_guests()
    guests[str(message.from_user.id)] = {
        "name": data["g_name"],
        "phone": phone,
        "lang": lang,
        "registered_at": now_tz().isoformat(),
    }
    save_guests(guests)

    await state.set_state(None)
    await message.answer(
        TEXTS[lang]["guest_registered"], reply_markup=main_reply_kb(lang, message.from_user.id)
    )


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(None)
    await state.update_data(lang=lang)
    await safe_edit_text(callback, TEXTS[lang]["welcome"])
    await callback.answer()


# ============ DACHA KO'RISH / BRON QILISH (FOYDALANUVCHI) ============
@router.callback_query(F.data == "menu_list")
async def menu_list(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dachas = load_dachas()
    if not dachas:
        await callback.answer(TEXTS[lang]["no_dachas_user"], show_alert=True)
        return
    await safe_edit_text(callback, TEXTS[lang]["choose_search_type"], reply_markup=search_menu_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "searchregion_menu")
async def search_region_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dachas = load_dachas()
    await safe_edit_text(callback, 
        TEXTS[lang]["choose_region"], reply_markup=region_select_kb(dachas, "browseregion", "menu_list")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("browseregion_"))
async def browse_region(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    region_key = callback.data.replace("browseregion_", "")
    dachas = load_dachas()

    if region_key == "boshqa":
        filtered = {k: v for k, v in dachas.items() if not v.get("region")}
        if not filtered:
            await callback.answer(TEXTS[lang]["no_dachas_user"], show_alert=True)
            return
        await safe_edit_text(callback, 
            TEXTS[lang]["choose_dacha"], reply_markup=dacha_list_kb(lang, filtered, "searchregion_menu")
        )
        await callback.answer()
        return

    await safe_edit_text(callback, 
        TEXTS[lang]["choose_district"],
        reply_markup=district_select_kb(region_key, dachas, "browsedistrict", "searchregion_menu"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("browsedistrict_"))
async def browse_district(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    _, region_key, idx = callback.data.split("_", 2)
    district_name = REGIONS[region_key]["districts"][int(idx)]
    dachas = load_dachas()
    filtered = {
        k: v for k, v in dachas.items() if v.get("region") == region_key and v.get("district") == district_name
    }
    if not filtered:
        await callback.answer(TEXTS[lang]["no_dachas_user"], show_alert=True)
        return
    back_cb = f"browseregion_{region_key}"
    await safe_edit_text(callback, 
        TEXTS[lang]["choose_dacha"], reply_markup=dacha_list_kb(lang, filtered, back_cb)
    )
    await callback.answer()


def price_filter_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=f"💰 {label}", callback_data=f"pf_{i}")]
        for i, (lo, hi, label) in enumerate(PRICE_RANGES)
    ]
    rows.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="menu_list")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "pricefilter_menu")
async def price_filter_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await safe_edit_text(callback, TEXTS[lang]["choose_price_range"], reply_markup=price_filter_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("pf_"))
async def price_filter_apply(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    idx = int(callback.data.replace("pf_", ""))
    lo, hi, label = PRICE_RANGES[idx]
    dachas = load_dachas()
    filtered = {
        k: v for k, v in dachas.items()
        if v.get("price", 0) >= lo and (hi is None or v.get("price", 0) < hi)
    }
    if not filtered:
        await callback.answer(TEXTS[lang]["no_dachas_user"], show_alert=True)
        return
    await safe_edit_text(callback, 
        TEXTS[lang]["choose_dacha"], reply_markup=dacha_list_kb(lang, filtered, "pricefilter_menu")
    )
    await callback.answer()


@router.callback_query(F.data == "searchname_menu")
async def search_name_menu(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(DachaSearchStates.entering_name)
    await safe_edit_text(callback, TEXTS[lang]["ask_dacha_name"], reply_markup=cancel_kb(lang))
    await callback.answer()


@router.message(DachaSearchStates.entering_name)
async def search_name_apply(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    query = message.text.strip().lower()
    dachas = load_dachas()
    filtered = {
        k: v for k, v in dachas.items()
        if query in v.get("name_uz", "").lower() or query in v.get("name_ru", "").lower()
    }
    await state.set_state(None)
    if not filtered:
        await message.answer(TEXTS[lang]["no_dachas_user"], reply_markup=search_menu_kb(lang))
        return
    await message.answer(TEXTS[lang]["choose_dacha"], reply_markup=dacha_list_kb(lang, filtered, "menu_list"))


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
    await show_dacha_detail(callback, lang, dacha_key, d)
    await callback.answer()


@router.callback_query(F.data.startswith("book_"))
async def start_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dacha_key = callback.data.replace("book_", "")
    await state.update_data(dacha_key=dacha_key)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=TEXTS[lang]["contract_agree"], callback_data="guest_contract_agree"),
                InlineKeyboardButton(text=TEXTS[lang]["contract_decline"], callback_data="guest_contract_decline"),
            ]
        ]
    )
    await callback.message.answer(load_contract_texts()["guest"], reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "guest_contract_decline")
async def guest_contract_decline(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await safe_edit_text(callback, TEXTS[lang]["contract_declined_msg"])
    await callback.answer()


@router.callback_query(F.data == "guest_contract_agree")
async def guest_contract_agree(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(BookingStates.entering_checkin)
    await safe_edit_text(callback, TEXTS[lang]["ask_checkin"], reply_markup=cancel_kb(lang))
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
    await message.answer(TEXTS[lang]["choose_search_type"], reply_markup=search_menu_kb(lang))


@router.message(F.text.in_({TEXTS["uz"]["menu_my"], TEXTS["ru"]["menu_my"]}))
async def rk_menu_my(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(None)
    await state.update_data(lang=lang)
    bookings = load_bookings()
    user_bookings = [b for b in bookings if b["user_id"] == message.from_user.id]
    await message.answer(my_bookings_text(lang, user_bookings), reply_markup=my_bookings_kb(lang, user_bookings))


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
    await state.update_data(lang=lang)
    await message.answer(TEXTS[lang]["owner_entry_choice"], reply_markup=owner_entry_choice_kb(lang))


@router.message(BookingStates.entering_checkin)
async def enter_checkin(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dt = parse_date(message.text)
    if not dt:
        await message.answer(TEXTS[lang]["invalid_date"])
        return
    today = now_tz().replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    if dt.date() < today.date():
        await message.answer(TEXTS[lang]["date_in_past"])
        return
    if (dt.date() - today.date()).days > 365:
        await message.answer(TEXTS[lang]["date_too_far"])
        return
    await state.update_data(checkin=message.text.strip(), checkin_dt=dt.isoformat())
    await state.set_state(BookingStates.entering_checkout)
    await message.answer(TEXTS[lang]["ask_checkout"], reply_markup=cancel_kb(lang))


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
    if (dt - checkin_dt).days > 90:
        await message.answer(TEXTS[lang]["stay_too_long"])
        return

    if not is_dates_available(data["dacha_key"], checkin_dt, dt):
        await message.answer(TEXTS[lang]["dates_unavailable"])
        await state.set_state(BookingStates.entering_checkin)
        return

    await state.update_data(checkout=message.text.strip(), checkout_dt=dt.isoformat())
    await state.set_state(BookingStates.entering_name)
    await message.answer(TEXTS[lang]["ask_name"], reply_markup=cancel_kb(lang))


@router.message(BookingStates.entering_name)
async def enter_name(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.update_data(name=message.text.strip())
    await state.set_state(BookingStates.entering_phone)
    await message.answer(TEXTS[lang]["ask_phone"], reply_markup=cancel_kb(lang))


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
    await state.update_data(base_total=total, nights=nights)

    await state.set_state(BookingStates.entering_promo)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]["promo_skip_btn"], callback_data="promo_skip")],
            [InlineKeyboardButton(text=TEXTS[lang]["cancel_operation_btn"], callback_data="cancel_operation")],
        ]
    )
    await message.answer(TEXTS[lang]["ask_promo"], reply_markup=kb)


async def _show_booking_confirm(target, state: FSMContext, discount: int = 0, promo_code: str = None):
    data = await state.get_data()
    lang = get_lang(data)
    dachas = load_dachas()
    d = dachas[data["dacha_key"]]
    base_total = data["base_total"]
    nights = data["nights"]
    total = max(base_total - discount, 0)
    commission = round(total * get_commission_rate(d.get("owner_id")))
    await state.update_data(total=total, commission=commission, discount=discount, promo_code=promo_code)

    text = TEXTS[lang]["confirm"].format(
        dacha=d[f"name_{lang}"],
        checkin=data["checkin"],
        checkout=data["checkout"],
        name=data["name"],
        phone=data["phone"],
    )
    if discount:
        text += TEXTS[lang]["promo_applied"].format(discount=discount, code=promo_code).replace(",", " ")
    text += TEXTS[lang]["commission_info"].format(total=total, nights=nights, commission=commission)

    await state.set_state(BookingStates.confirming)
    if isinstance(target, CallbackQuery):
        await target.message.edit_text(text, reply_markup=confirm_kb(lang))
    else:
        await target.answer(text, reply_markup=confirm_kb(lang))


@router.callback_query(F.data == "promo_skip", BookingStates.entering_promo)
async def promo_skip(callback: CallbackQuery, state: FSMContext):
    await _show_booking_confirm(callback, state)
    await callback.answer()


@router.message(BookingStates.entering_promo)
async def promo_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    code = message.text.strip().upper().replace(" ", "")
    promos = load_promocodes()
    rec = promos.get(code)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TEXTS[lang]["promo_skip_btn"], callback_data="promo_skip")],
            [InlineKeyboardButton(text=TEXTS[lang]["cancel_operation_btn"], callback_data="cancel_operation")],
        ]
    )
    if not rec or not rec.get("active"):
        await message.answer(TEXTS[lang]["invalid_promo"], reply_markup=kb)
        return
    if rec.get("expires_at") and now_tz().date().isoformat() > rec["expires_at"]:
        await message.answer(TEXTS[lang]["invalid_promo"], reply_markup=kb)
        return
    max_uses = rec.get("max_uses")
    if max_uses is not None and rec.get("used_count", 0) >= max_uses:
        await message.answer(TEXTS[lang]["invalid_promo"], reply_markup=kb)
        return

    base_total = data["base_total"]
    if rec["type"] == "percent":
        discount = round(base_total * rec["value"] / 100)
    else:
        discount = round(rec["value"])
    discount = min(discount, base_total)

    await _show_booking_confirm(message, state, discount=discount, promo_code=code)


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
        "dacha_key": data["dacha_key"],
        "checkin": data["checkin"],
        "checkout": data["checkout"],
        "checkin_dt": data["checkin_dt"],
        "checkout_dt": data["checkout_dt"],
        "name": data["name"],
        "phone": data["phone"],
        "total": total,
        "commission": commission,
        "discount": data.get("discount", 0),
        "promo_code": data.get("promo_code"),
        "status": "active",
        "created_at": now_tz().isoformat(),
    }
    add_booking(booking)

    if booking.get("promo_code"):
        promos = load_promocodes()
        if booking["promo_code"] in promos:
            promos[booking["promo_code"]]["used_count"] = promos[booking["promo_code"]].get("used_count", 0) + 1
            save_promocodes(promos)

    await safe_edit_text(callback, TEXTS[lang]["booked"])

    try:
        pdf_path = generate_guest_contract_pdf(
            data["name"], d["name_uz"], data["checkin"], data["checkout"], callback.from_user.id
        )
        await bot.send_document(callback.message.chat.id, FSInputFile(pdf_path))
    except Exception as e:
        logging.warning(f"Mehmon shartnomasi PDF yuborilmadi: {e}")

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
    await safe_edit_text(callback, TEXTS[lang]["cancelled"])
    await callback.message.answer(TEXTS[lang]["welcome"])
    await callback.answer()


@router.callback_query(F.data == "menu_my")
async def my_bookings(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    bookings = load_bookings()
    user_bookings = [b for b in bookings if b["user_id"] == callback.from_user.id]
    await safe_edit_text(callback, 
        my_bookings_text(lang, user_bookings), reply_markup=my_bookings_kb(lang, user_bookings)
    )
    await callback.answer()


# ============ BRONNI BEKOR QILISH ============
@router.callback_query(F.data.startswith("cancelbooking_"))
async def cancel_booking_ask(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    booking_id = callback.data.replace("cancelbooking_", "")
    bookings = load_bookings()
    booking = next((b for b in bookings if b["id"] == booking_id and b["user_id"] == callback.from_user.id), None)
    if not booking:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    if booking.get("status") == "cancelled":
        await callback.answer(TEXTS[lang]["already_cancelled"], show_alert=True)
        return
    text = TEXTS[lang]["cancel_confirm"].format(
        dacha=booking["dacha"], checkin=booking["checkin"], checkout=booking["checkout"]
    )
    await callback.message.answer(text, reply_markup=cancel_booking_confirm_kb(lang, booking_id))
    await callback.answer()


@router.callback_query(F.data.startswith("cancelyes_"))
async def cancel_booking_confirm(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = get_lang(data)
    booking_id = callback.data.replace("cancelyes_", "")
    bookings = load_bookings()
    booking = next((b for b in bookings if b["id"] == booking_id and b["user_id"] == callback.from_user.id), None)
    if not booking:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    booking["status"] = "cancelled"
    save_bookings(bookings)
    await safe_edit_text(callback, TEXTS[lang]["booking_cancelled"])
    await callback.answer()

    cancel_notify = TEXTS["uz"]["booking_cancelled_admin"].format(
        dacha=booking["dacha"], checkin=booking["checkin"], checkout=booking["checkout"], name=booking["name"]
    )
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, cancel_notify)
        except Exception as e:
            logging.warning(f"Adminga ({admin_id}) bekor qilish xabari yuborilmadi: {e}")

    dachas = load_dachas()
    d = dachas.get(booking.get("dacha_key"))
    if d and d.get("owner_id"):
        try:
            await bot.send_message(d["owner_id"], cancel_notify)
        except Exception as e:
            logging.warning(f"Owner'ga ({d['owner_id']}) bekor qilish xabari yuborilmadi: {e}")


@router.callback_query(F.data.startswith("showloc_"))
async def show_booking_location(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    booking_id = callback.data.replace("showloc_", "")
    bookings = load_bookings()
    booking = next((b for b in bookings if b["id"] == booking_id and b["user_id"] == callback.from_user.id), None)
    if not booking:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    dachas = load_dachas()
    d = dachas.get(booking.get("dacha_key"))
    location = d.get("location") if d else None
    if not location:
        await callback.answer(TEXTS[lang]["no_location"], show_alert=True)
        return
    await callback.message.answer_location(latitude=location["lat"], longitude=location["lon"])
    await callback.answer()


# ============ REYTING VA SHARHLAR ============
@router.callback_query(F.data.startswith("rate_"))
async def rate_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    booking_id = callback.data.replace("rate_", "")
    bookings = load_bookings()
    booking = next((b for b in bookings if b["id"] == booking_id and b["user_id"] == callback.from_user.id), None)
    if not booking:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    reviews = load_reviews()
    if any(r["booking_id"] == booking_id for r in reviews):
        await callback.answer(TEXTS[lang]["already_rated"], show_alert=True)
        return
    await callback.message.answer(TEXTS[lang]["rate_ask_stars"], reply_markup=star_rating_kb(booking_id))
    await callback.answer()


@router.callback_query(F.data.startswith("ratestar_"))
async def rate_star(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    _, booking_id, n = callback.data.split("_")
    bookings = load_bookings()
    booking = next((b for b in bookings if b["id"] == booking_id and b["user_id"] == callback.from_user.id), None)
    if not booking:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    reviews = load_reviews()
    if any(r["booking_id"] == booking_id for r in reviews):
        await callback.answer(TEXTS[lang]["already_rated"], show_alert=True)
        return
    await state.update_data(
        review_booking_id=booking_id, review_dacha_key=booking.get("dacha_key"), review_rating=int(n)
    )
    await state.set_state(ReviewStates.entering_comment)
    await safe_edit_text(callback, TEXTS[lang]["rate_ask_comment"], reply_markup=rate_comment_kb(lang, booking_id))
    await callback.answer()


async def _save_review(user_id: int, name: str, data: dict, comment):
    review = {
        "id": uuid.uuid4().hex[:8],
        "booking_id": data["review_booking_id"],
        "dacha_key": data["review_dacha_key"],
        "user_id": user_id,
        "name": name,
        "rating": data["review_rating"],
        "comment": comment,
        "created_at": now_tz().isoformat(),
    }
    add_review(review)


@router.message(ReviewStates.entering_comment)
async def rate_comment_text(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if "review_booking_id" not in data:
        await state.set_state(None)
        return
    await _save_review(message.from_user.id, message.from_user.full_name, data, message.text.strip())
    await state.set_state(None)
    await message.answer(TEXTS[lang]["rate_thanks"])


@router.callback_query(F.data.startswith("ratecomment_skip_"))
async def rate_comment_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if "review_booking_id" not in data:
        await callback.answer()
        return
    await _save_review(callback.from_user.id, callback.from_user.full_name, data, None)
    await state.set_state(None)
    await safe_edit_text(callback, TEXTS[lang]["rate_thanks"])
    await callback.answer()


@router.callback_query(F.data.startswith("reviews_"))
async def view_reviews(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    dacha_key = callback.data.replace("reviews_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    reviews = [r for r in load_reviews() if r["dacha_key"] == dacha_key]
    reviews.sort(key=lambda r: r["created_at"], reverse=True)

    text = TEXTS[lang]["reviews_title"].format(dacha=d[f"name_{lang}"])
    if not reviews:
        text += TEXTS[lang]["no_reviews"]
    else:
        for r in reviews[:15]:
            comment = f"\n{r['comment']}" if r.get("comment") else ""
            text += TEXTS[lang]["review_item"].format(rating="⭐" * r["rating"], name=r["name"], comment=comment)
            text += "\n"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data=f"view_{dacha_key}")]]
    )
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()


# ============ QO'LLAB-QUVVATLASH (FOYDALANUVCHI) ============
@router.callback_query(F.data == "menu_support")
async def menu_support(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    items = load_support()
    text = TEXTS[lang]["support_title"] if items else TEXTS[lang]["no_support_info"]
    await safe_edit_text(callback, text, reply_markup=support_list_kb(lang, items))
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
    await safe_edit_text(callback, text, reply_markup=support_detail_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "support_write")
async def support_write_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(SupportStates.entering_message)
    await callback.message.answer(TEXTS[lang]["ask_support_msg"], reply_markup=cancel_kb(lang))
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
        "created_at": now_tz().isoformat(),
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
@router.callback_query(F.data == "owner_apply_start")
async def owner_apply_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    owners = load_owners()
    rec = owners.get(str(callback.from_user.id))
    if rec and rec.get("status") == "pending":
        await callback.answer(TEXTS[lang]["owner_already_pending"], show_alert=True)
        return
    if rec and rec.get("status") == "approved":
        await safe_edit_text(callback, TEXTS[lang]["owner_panel_title"], reply_markup=owner_panel_kb(lang))
        await callback.answer()
        return
    await safe_edit_text(callback, TEXTS[lang]["owner_entry_choice"], reply_markup=owner_entry_choice_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "owner_apply_form_start")
async def owner_apply_form_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerApplyStates.entering_name)
    await safe_edit_text(callback, TEXTS[lang]["ask_name"], reply_markup=cancel_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "owner_code_start")
async def owner_code_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerApplyStates.entering_code)
    await safe_edit_text(callback, TEXTS[lang]["ask_owner_code"], reply_markup=cancel_kb(lang))
    await callback.answer()


@router.message(OwnerApplyStates.entering_code)
async def owner_code_check(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    entered = message.text.strip().upper()

    codes = load_owner_codes()
    code_rec = codes.get(entered)
    if not code_rec or code_rec.get("used"):
        await message.answer(TEXTS[lang]["invalid_owner_code"], reply_markup=owner_entry_choice_kb(lang))
        return

    code_rec["used"] = True
    code_rec["used_by"] = message.from_user.id
    code_rec["used_at"] = now_tz().isoformat()
    save_owner_codes(codes)

    owners = load_owners()
    owners[str(message.from_user.id)] = {
        "name": message.from_user.full_name,
        "phone": None,
        "status": "approved",
        "lang": lang,
        "requested_at": now_tz().isoformat(),
        "via_code": entered,
    }
    save_owners(owners)

    await state.set_state(None)
    await message.answer(
        TEXTS[lang]["owner_code_accepted"], reply_markup=main_reply_kb(lang, message.from_user.id)
    )


@router.message(OwnerApplyStates.entering_name)
async def owner_apply_name(message: Message, state: FSMContext):
    await state.update_data(o_name=message.text.strip())
    await state.set_state(OwnerApplyStates.entering_phone)
    data = await state.get_data()
    lang = get_lang(data)
    await message.answer(TEXTS[lang]["ask_phone"], reply_markup=cancel_kb(lang))


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
        "requested_at": now_tz().isoformat(),
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
    await safe_edit_text(callback, callback.message.text + A["owner_approved_admin"])
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
    await safe_edit_text(callback, callback.message.text + A["owner_rejected_admin"])
    await callback.answer()


# ============ DACHA EGALARI PANELI ============
@router.callback_query(F.data == "owner_panel_reopen")
async def owner_panel_reopen(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if not is_approved_owner(callback.from_user.id):
        await callback.answer(TEXTS[lang]["not_owner"], show_alert=True)
        return
    await safe_edit_text(callback, TEXTS[lang]["owner_panel_title"], reply_markup=owner_panel_kb(lang))
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
        await safe_edit_text(callback, TEXTS[lang]["owner_no_dachas"], reply_markup=owner_panel_kb(lang))
        await callback.answer()
        return
    await safe_edit_text(callback, 
        TEXTS[lang]["owner_manage_title"], reply_markup=dachas_manage_kb(mine, "owner_panel_reopen")
    )
    await callback.answer()


@router.callback_query(F.data == "owner_payments")
async def owner_payments(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if not is_approved_owner(callback.from_user.id):
        await callback.answer(TEXTS[lang]["not_owner"], show_alert=True)
        return

    dachas = load_dachas()
    my_keys = {k for k, v in dachas.items() if v.get("owner_id") == callback.from_user.id}
    bookings = load_bookings()
    my_bookings = [b for b in bookings if b.get("dacha_key") in my_keys and b.get("status") != "cancelled"]
    my_bookings.sort(key=lambda b: b["created_at"], reverse=True)

    total_sum = sum(b.get("total", 0) for b in my_bookings)
    total_commission = sum(b.get("commission", 0) for b in my_bookings)
    net = total_sum - total_commission

    text = TEXTS[lang]["payments_summary"].format(
        count=len(my_bookings), total=total_sum, commission=total_commission, net=net
    )
    if my_bookings:
        text += "\n\n" + TEXTS[lang]["payments_list_title"]
        for b in my_bookings[:20]:
            text += TEXTS[lang]["payments_item"].format(
                dacha=b["dacha"], checkin=b["checkin"], checkout=b["checkout"],
                total=b.get("total", 0), commission=b.get("commission", 0),
            )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="owner_panel_reopen")]]
    )
    await safe_edit_text(callback, text, reply_markup=kb)
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
    await safe_edit_text(callback, load_contract_texts()["owner"], reply_markup=kb)
    await callback.answer()


@router.callback_query(F.data == "contract_decline")
async def contract_decline(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await safe_edit_text(callback, TEXTS[lang]["contract_declined_msg"], reply_markup=owner_panel_kb(lang))
    await callback.answer()


@router.callback_query(F.data == "contract_agree")
async def contract_agree(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.name_uz)
    await safe_edit_text(callback, TEXTS[lang]["ask_owner_name_uz"], reply_markup=cancel_kb(lang))
    await callback.answer()


@router.message(OwnerAddStates.name_uz)
async def oa_name_uz(message: Message, state: FSMContext):
    await state.update_data(o_name_uz=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.name_ru)
    await message.answer(TEXTS[lang]["ask_owner_name_ru"], reply_markup=cancel_kb(lang))


@router.message(OwnerAddStates.name_ru)
async def oa_name_ru(message: Message, state: FSMContext):
    await state.update_data(o_name_ru=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.desc_uz)
    await message.answer(TEXTS[lang]["ask_owner_desc_uz"], reply_markup=cancel_kb(lang))


@router.message(OwnerAddStates.desc_uz)
async def oa_desc_uz(message: Message, state: FSMContext):
    await state.update_data(o_desc_uz=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.desc_ru)
    await message.answer(TEXTS[lang]["ask_owner_desc_ru"], reply_markup=cancel_kb(lang))


@router.message(OwnerAddStates.desc_ru)
async def oa_desc_ru(message: Message, state: FSMContext):
    await state.update_data(o_desc_ru=message.text.strip())
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(OwnerAddStates.price)
    await message.answer(TEXTS[lang]["ask_price"], reply_markup=cancel_kb(lang))


@router.message(OwnerAddStates.price)
async def oa_price(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    price = parse_price(message.text)
    if price is None:
        await message.answer(TEXTS[lang]["invalid_price"])
        return
    await state.update_data(o_price=price, o_photos=[])
    await state.set_state(OwnerAddStates.photos)
    await message.answer(TEXTS[lang]["ask_photos"], reply_markup=cancel_kb(lang))


@router.message(OwnerAddStates.photos)
async def oa_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if not message.photo:
        await message.answer(TEXTS[lang]["invalid_photo"])
        return
    photos = data.get("o_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(o_photos=photos)
    if len(photos) >= 5:
        await state.set_state(OwnerAddStates.video)
        await message.answer(TEXTS[lang]["photos_max_reached"])
        await message.answer(TEXTS[lang]["ask_video"], reply_markup=skip_inline_kb(lang, "owner_video_skip"))
        return
    await message.answer(
        TEXTS[lang]["photo_added"].format(n=len(photos)),
        reply_markup=done_inline_kb(lang, "owner_photos_done"),
    )


@router.callback_query(F.data == "owner_photos_done")
async def oa_photos_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if not data.get("o_photos"):
        await callback.answer(TEXTS[lang]["invalid_photo"], show_alert=True)
        return
    await state.set_state(OwnerAddStates.video)
    await safe_edit_text(callback, TEXTS[lang]["ask_video"], reply_markup=skip_inline_kb(lang, "owner_video_skip"))
    await callback.answer()


@router.message(OwnerAddStates.video)
async def oa_video(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    if not message.video:
        await message.answer(TEXTS[lang]["invalid_video"])
        return
    await state.update_data(o_video=message.video.file_id)
    await state.set_state(OwnerAddStates.location)
    await message.answer(TEXTS[lang]["ask_location"], reply_markup=location_request_kb(lang))


@router.callback_query(F.data == "owner_video_skip")
async def oa_video_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.update_data(o_video=None)
    await state.set_state(OwnerAddStates.location)
    await safe_edit_text(callback, TEXTS[lang]["ask_location"], reply_markup=cancel_kb(lang))
    await callback.message.answer("📍", reply_markup=location_request_kb(lang))
    await callback.answer()


@router.message(OwnerAddStates.location)
async def oa_location(message: Message, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)

    location = None
    address = None
    if message.location:
        location = {"lat": message.location.latitude, "lon": message.location.longitude}
    elif message.text == TEXTS[lang]["skip_btn"]:
        pass
    elif message.text:
        address = message.text.strip()
    else:
        await message.answer(TEXTS[lang]["invalid_location"])
        return

    await state.update_data(o_location=location, o_address=address)
    await message.answer(
        TEXTS[lang]["choose_region"],
        reply_markup=region_select_kb({}, "oregion", "owner_panel_reopen"),
    )


@router.callback_query(F.data.startswith("oregion_"))
async def oa_region_selected(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    region_key = callback.data.replace("oregion_", "")
    await state.update_data(o_region=region_key)
    await safe_edit_text(callback, 
        TEXTS[lang]["choose_district"], reply_markup=district_select_kb(region_key, {}, "odistrict", "oa_back_to_region")
    )
    await callback.answer()


@router.callback_query(F.data == "oa_back_to_region")
async def oa_region_back(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await safe_edit_text(callback, 
        TEXTS[lang]["choose_region"], reply_markup=region_select_kb({}, "oregion", "owner_panel_reopen")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("odistrict_"))
async def oa_district_selected(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = get_lang(data)
    _, region_key, idx = callback.data.split("_", 2)
    district_name = REGIONS[region_key]["districts"][int(idx)]

    dachas = load_dachas()
    new_key = f"dacha_{uuid.uuid4().hex[:8]}"
    dachas[new_key] = {
        "name_uz": data["o_name_uz"],
        "name_ru": data["o_name_ru"],
        "desc_uz": data["o_desc_uz"],
        "desc_ru": data["o_desc_ru"],
        "price": data["o_price"],
        "owner_id": callback.from_user.id,
        "owner_name": callback.from_user.full_name,
        "photos": data.get("o_photos", []),
        "video_id": data.get("o_video"),
        "location": data.get("o_location"),
        "address": data.get("o_address"),
        "region": region_key,
        "district": district_name,
        "verified": False,
    }
    save_dachas(dachas)

    try:
        pdf_path = generate_contract_pdf(
            callback.from_user.full_name, data["o_name_uz"], data["o_price"], callback.from_user.id
        )
        await bot.send_document(callback.message.chat.id, FSInputFile(pdf_path))
    except Exception as e:
        logging.warning(f"Shartnoma PDF yuborilmadi: {e}")

    await state.set_state(None)
    await safe_edit_text(callback, TEXTS[lang]["dacha_added_owner"])
    # "Lokatsiya so'rash" bosqichida yuborilgan vaqtinchalik pastki klaviaturani
    # asosiy menyuga qaytarib qo'yamiz — aks holda "yopishib qolib" qoladi.
    await callback.message.answer("✅", reply_markup=main_reply_kb(lang, callback.from_user.id))
    await callback.message.answer(TEXTS[lang]["owner_panel_title"], reply_markup=owner_panel_kb(lang))
    await callback.answer()


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
    await safe_edit_text(callback, A["panel_title"], reply_markup=admin_panel_kb())
    await callback.answer()


# --- Yangi dacha qo'shish (admin) ---
@router.callback_query(F.data == "admin_add")
async def admin_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(AdminStates.adding_name_uz)
    await safe_edit_text(callback, A["ask_name_uz"], reply_markup=cancel_kb("uz"))
    await callback.answer()


@router.message(AdminStates.adding_name_uz)
async def admin_add_name_uz(message: Message, state: FSMContext):
    await state.update_data(new_name_uz=message.text.strip())
    await state.set_state(AdminStates.adding_name_ru)
    await message.answer(A["ask_name_ru"], reply_markup=cancel_kb("uz"))


@router.message(AdminStates.adding_name_ru)
async def admin_add_name_ru(message: Message, state: FSMContext):
    await state.update_data(new_name_ru=message.text.strip())
    await state.set_state(AdminStates.adding_desc_uz)
    await message.answer(A["ask_desc_uz"], reply_markup=cancel_kb("uz"))


@router.message(AdminStates.adding_desc_uz)
async def admin_add_desc_uz(message: Message, state: FSMContext):
    await state.update_data(new_desc_uz=message.text.strip())
    await state.set_state(AdminStates.adding_desc_ru)
    await message.answer(A["ask_desc_ru"], reply_markup=cancel_kb("uz"))


@router.message(AdminStates.adding_desc_ru)
async def admin_add_desc_ru(message: Message, state: FSMContext):
    await state.update_data(new_desc_ru=message.text.strip())
    await state.set_state(AdminStates.adding_price)
    await message.answer(A["ask_price"], reply_markup=cancel_kb("uz"))


@router.message(AdminStates.adding_price)
async def admin_add_price(message: Message, state: FSMContext):
    price = parse_price(message.text)
    if price is None:
        await message.answer(A["invalid_price"])
        return
    await state.update_data(new_price=price, new_photos=[])
    await state.set_state(AdminStates.adding_photos)
    await message.answer(A["ask_photos"], reply_markup=cancel_kb("uz"))


@router.message(AdminStates.adding_photos)
async def admin_add_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    if not message.photo:
        await message.answer(A["invalid_photo"])
        return
    photos = data.get("new_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(new_photos=photos)
    if len(photos) >= 5:
        await state.set_state(AdminStates.adding_video)
        await message.answer(A["photos_max_reached"])
        await message.answer(A["ask_video"], reply_markup=skip_inline_kb("uz", "admin_video_skip"))
        return
    await message.answer(
        A["photo_added"].format(n=len(photos)), reply_markup=done_inline_kb("uz", "admin_photos_done")
    )


@router.callback_query(F.data == "admin_photos_done")
async def admin_photos_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("new_photos"):
        await callback.answer(A["invalid_photo"], show_alert=True)
        return
    await state.set_state(AdminStates.adding_video)
    await safe_edit_text(callback, A["ask_video"], reply_markup=skip_inline_kb("uz", "admin_video_skip"))
    await callback.answer()


@router.message(AdminStates.adding_video)
async def admin_add_video(message: Message, state: FSMContext):
    if not message.video:
        await message.answer(A["invalid_video"])
        return
    await state.update_data(new_video=message.video.file_id)
    await state.set_state(AdminStates.adding_location)
    await message.answer(A["ask_location"], reply_markup=location_request_kb("uz"))


@router.callback_query(F.data == "admin_video_skip")
async def admin_video_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(new_video=None)
    await state.set_state(AdminStates.adding_location)
    await safe_edit_text(callback, A["ask_location"], reply_markup=cancel_kb("uz"))
    await callback.message.answer("📍", reply_markup=location_request_kb("uz"))
    await callback.answer()


@router.message(AdminStates.adding_location)
async def admin_add_location(message: Message, state: FSMContext):
    data = await state.get_data()

    location = None
    address = None
    if message.location:
        location = {"lat": message.location.latitude, "lon": message.location.longitude}
    elif message.text == TEXTS["uz"]["skip_btn"]:
        pass
    elif message.text:
        address = message.text.strip()
    else:
        await message.answer(A["invalid_location"])
        return

    await state.update_data(new_location=location, new_address=address)
    await message.answer(A["choose_region"], reply_markup=region_select_kb({}, "aregion", "admin_panel"))


@router.callback_query(F.data.startswith("aregion_"))
async def admin_region_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    region_key = callback.data.replace("aregion_", "")
    await state.update_data(new_region=region_key)
    await safe_edit_text(callback, 
        A["choose_district"], reply_markup=district_select_kb(region_key, {}, "adistrict", "aa_back_to_region")
    )
    await callback.answer()


@router.callback_query(F.data == "aa_back_to_region")
async def admin_region_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await safe_edit_text(callback, A["choose_region"], reply_markup=region_select_kb({}, "aregion", "admin_panel"))
    await callback.answer()


@router.callback_query(F.data.startswith("adistrict_"))
async def admin_district_selected(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    data = await state.get_data()
    _, region_key, idx = callback.data.split("_", 2)
    district_name = REGIONS[region_key]["districts"][int(idx)]

    dachas = load_dachas()
    new_key = f"dacha_{uuid.uuid4().hex[:8]}"
    dachas[new_key] = {
        "name_uz": data["new_name_uz"],
        "name_ru": data["new_name_ru"],
        "desc_uz": data["new_desc_uz"],
        "desc_ru": data["new_desc_ru"],
        "price": data["new_price"],
        "owner_id": None,
        "owner_name": None,
        "photos": data.get("new_photos", []),
        "video_id": data.get("new_video"),
        "location": data.get("new_location"),
        "address": data.get("new_address"),
        "region": region_key,
        "district": district_name,
        "verified": False,
    }
    save_dachas(dachas)
    await state.set_state(None)
    await safe_edit_text(callback, A["added"])
    await callback.message.answer("✅", reply_markup=main_reply_kb("uz", callback.from_user.id))
    await callback.message.answer(A["panel_title"], reply_markup=admin_panel_kb())
    await callback.answer()


# --- Dachalarni boshqarish (admin + egalar umumiy handlerlari) ---
@router.callback_query(F.data == "admin_manage")
async def admin_manage(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    dachas = load_dachas()
    if not dachas:
        await safe_edit_text(callback, A["no_dachas"], reply_markup=admin_panel_kb())
        await callback.answer()
        return
    await safe_edit_text(callback, A["manage_title"], reply_markup=dachas_manage_kb(dachas, "admin_panel"))
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
    await safe_edit_text(callback, 
        A["edit_choose_field"].format(name=d["name_uz"]),
        reply_markup=edit_field_kb(dacha_key, back_cb, show_verify=is_admin(callback.from_user.id)),
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
    if field == "photo_id":
        await safe_edit_text(callback, A["ask_new_photo"], reply_markup=cancel_kb("uz"))
    else:
        await safe_edit_text(callback, A["ask_new_value"].format(old=d[field]), reply_markup=cancel_kb("uz"))
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
    elif field == "photo_id":
        if not message.photo:
            await message.answer(A["invalid_photo"])
            return
        dachas[dacha_key][field] = message.photo[-1].file_id
    else:
        dachas[dacha_key][field] = message.text.strip()
    save_dachas(dachas)
    await state.set_state(None)

    if is_admin(message.from_user.id):
        await message.answer(A["updated"], reply_markup=dachas_manage_kb(dachas, "admin_panel"))
    else:
        mine = {k: v for k, v in dachas.items() if v.get("owner_id") == message.from_user.id}
        await message.answer(A["updated"], reply_markup=dachas_manage_kb(mine, "owner_panel_reopen"))


def _updated_manage_reply(user_id: int, dachas: dict):
    """Tahrirlash tugagach mos ro'yxatni qaytaradi (admin — barchasi, owner — faqat o'ziniki)."""
    if is_admin(user_id):
        return dachas_manage_kb(dachas, "admin_panel")
    mine = {k: v for k, v in dachas.items() if v.get("owner_id") == user_id}
    return dachas_manage_kb(mine, "owner_panel_reopen")


# --- Rasm/video tahrirlash ---
@router.callback_query(F.data.startswith("efmedia_"))
async def edit_media_start(callback: CallbackQuery, state: FSMContext):
    dacha_key = callback.data.replace("efmedia_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d or not can_manage_dacha(callback.from_user.id, d):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.update_data(edit_dacha_key=dacha_key, edit_photos=[])
    await state.set_state(AdminStates.editing_photos)
    await safe_edit_text(callback, A["ask_photos"], reply_markup=cancel_kb("uz"))
    await callback.answer()


@router.message(AdminStates.editing_photos)
async def edit_media_photo(message: Message, state: FSMContext):
    data = await state.get_data()
    if not message.photo:
        await message.answer(A["invalid_photo"])
        return
    photos = data.get("edit_photos", [])
    photos.append(message.photo[-1].file_id)
    await state.update_data(edit_photos=photos)
    if len(photos) >= 5:
        await state.set_state(AdminStates.editing_video)
        await message.answer(A["photos_max_reached"])
        await message.answer(A["ask_video"], reply_markup=skip_inline_kb("uz", "editmedia_video_skip"))
        return
    await message.answer(
        A["photo_added"].format(n=len(photos)), reply_markup=done_inline_kb("uz", "editmedia_photos_done")
    )


@router.callback_query(F.data == "editmedia_photos_done")
async def edit_media_photos_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("edit_photos"):
        await callback.answer(A["invalid_photo"], show_alert=True)
        return
    await state.set_state(AdminStates.editing_video)
    await safe_edit_text(callback, A["ask_video"], reply_markup=skip_inline_kb("uz", "editmedia_video_skip"))
    await callback.answer()


def _finish_media_edit(user_id: int, data: dict, new_video):
    """new_video: fayl_id (yangi video) yoki 'KEEP' (eski video saqlanadi).
    Qaytaradi: (ok, dachas, xabar_matni, klaviatura)."""
    dachas = load_dachas()
    key = data.get("edit_dacha_key")
    if key not in dachas or not can_manage_dacha(user_id, dachas[key]):
        return False, dachas, A["no_dachas"], None
    dachas[key]["photos"] = data.get("edit_photos", [])
    if new_video != "KEEP":
        dachas[key]["video_id"] = new_video
    save_dachas(dachas)
    return True, dachas, A["updated"], _updated_manage_reply(user_id, dachas)


@router.message(AdminStates.editing_video)
async def edit_media_video(message: Message, state: FSMContext):
    data = await state.get_data()
    if not message.video:
        await message.answer(A["invalid_video"])
        return
    ok, dachas, text, kb = _finish_media_edit(message.from_user.id, data, message.video.file_id)
    await state.set_state(None)
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data == "editmedia_video_skip")
async def edit_media_video_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ok, dachas, text, kb = _finish_media_edit(callback.from_user.id, data, "KEEP")
    await state.set_state(None)
    await safe_edit_text(callback, text, reply_markup=kb)
    await callback.answer()


# --- Lokatsiya tahrirlash ---
@router.callback_query(F.data.startswith("efloc_"))
async def edit_location_start(callback: CallbackQuery, state: FSMContext):
    dacha_key = callback.data.replace("efloc_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d or not can_manage_dacha(callback.from_user.id, d):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.update_data(edit_dacha_key=dacha_key)
    await state.set_state(AdminStates.editing_location)
    await safe_edit_text(callback, A["ask_location"], reply_markup=cancel_kb("uz"))
    await callback.message.answer("📍", reply_markup=location_request_kb("uz"))
    await callback.answer()


@router.message(AdminStates.editing_location)
async def edit_location_save(message: Message, state: FSMContext):
    data = await state.get_data()
    location = None
    address = None
    if message.location:
        location = {"lat": message.location.latitude, "lon": message.location.longitude}
    elif message.text == TEXTS["uz"]["skip_btn"]:
        pass
    elif message.text:
        address = message.text.strip()
    else:
        await message.answer(A["invalid_location"])
        return

    dachas = load_dachas()
    key = data.get("edit_dacha_key")
    if key not in dachas or not can_manage_dacha(message.from_user.id, dachas[key]):
        await state.set_state(None)
        await message.answer(A["no_dachas"])
        return
    dachas[key]["location"] = location
    dachas[key]["address"] = address
    save_dachas(dachas)
    await state.set_state(None)
    await message.answer(A["updated"], reply_markup=_updated_manage_reply(message.from_user.id, dachas))


# --- Viloyat/tuman tahrirlash ---
@router.callback_query(F.data.startswith("efregion_"))
async def edit_region_start(callback: CallbackQuery, state: FSMContext):
    dacha_key = callback.data.replace("efregion_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d or not can_manage_dacha(callback.from_user.id, d):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.update_data(edit_dacha_key=dacha_key)
    await safe_edit_text(callback, 
        A["choose_region"], reply_markup=region_select_kb({}, "efregionsel", manage_list_cb(callback.from_user.id))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("efregionsel_"))
async def edit_region_selected(callback: CallbackQuery, state: FSMContext):
    region_key = callback.data.replace("efregionsel_", "")
    await safe_edit_text(callback, 
        A["choose_district"], reply_markup=district_select_kb(region_key, {}, "efdistrictsel", "efa_back_to_region")
    )
    await callback.answer()


@router.callback_query(F.data == "efa_back_to_region")
async def edit_region_back(callback: CallbackQuery, state: FSMContext):
    await safe_edit_text(callback, 
        A["choose_region"], reply_markup=region_select_kb({}, "efregionsel", manage_list_cb(callback.from_user.id))
    )
    await callback.answer()


@router.callback_query(F.data.startswith("efdistrictsel_"))
async def edit_district_selected(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    key = data.get("edit_dacha_key")
    _, region_key, idx = callback.data.split("_", 2)
    district_name = REGIONS[region_key]["districts"][int(idx)]

    dachas = load_dachas()
    if key not in dachas or not can_manage_dacha(callback.from_user.id, dachas[key]):
        await callback.answer(A["no_dachas"], show_alert=True)
        return
    dachas[key]["region"] = region_key
    dachas[key]["district"] = district_name
    save_dachas(dachas)
    await state.set_state(None)
    await safe_edit_text(callback, A["updated"], reply_markup=_updated_manage_reply(callback.from_user.id, dachas))
    await callback.answer()


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
    await safe_edit_text(callback, 
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
            await safe_edit_text(callback, A["manage_title"], reply_markup=dachas_manage_kb(dachas, "admin_panel"))
        else:
            await safe_edit_text(callback, A["no_dachas"], reply_markup=admin_panel_kb())
    else:
        data = await state.get_data()
        lang = get_lang(data)
        mine = {k: v for k, v in dachas.items() if v.get("owner_id") == callback.from_user.id}
        if mine:
            await safe_edit_text(callback, 
                TEXTS[lang]["owner_manage_title"], reply_markup=dachas_manage_kb(mine, "owner_panel_reopen")
            )
        else:
            await safe_edit_text(callback, TEXTS[lang]["owner_no_dachas"], reply_markup=owner_panel_kb(lang))


# --- Shartnoma matnlarini boshqarish (faqat admin) ---
def contracts_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["btn_edit_guest_contract"], callback_data="cxedit_guest")],
            [InlineKeyboardButton(text=A["btn_edit_owner_contract"], callback_data="cxedit_owner")],
            [InlineKeyboardButton(text=A["back"], callback_data="admin_panel")],
        ]
    )


@router.callback_query(F.data == "admin_contracts")
async def admin_contracts(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await safe_edit_text(callback, A["contracts_panel_title"], reply_markup=contracts_menu_kb())
    await callback.answer()


@router.callback_query(F.data.startswith("cxedit_"))
async def admin_contract_edit_ask(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    kind = callback.data.replace("cxedit_", "")  # "guest" yoki "owner"
    if kind not in ("guest", "owner"):
        await callback.answer("Xato.", show_alert=True)
        return
    texts = load_contract_texts()
    await state.update_data(contract_kind=kind)
    await state.set_state(AdminStates.editing_contract)
    label = A["contract_kind_guest"] if kind == "guest" else A["contract_kind_owner"]
    await safe_edit_text(callback, A["ask_contract_text"].format(label=label, old=texts[kind]), reply_markup=cancel_kb("uz"))
    await callback.answer()


@router.message(AdminStates.editing_contract)
async def admin_contract_edit_save(message: Message, state: FSMContext):
    data = await state.get_data()
    kind = data.get("contract_kind")
    if kind not in ("guest", "owner"):
        await state.set_state(None)
        return
    texts = load_contract_texts()
    texts[kind] = message.text.strip()
    save_contract_texts(texts)
    await state.set_state(None)
    await message.answer(A["contract_updated"], reply_markup=contracts_menu_kb())


# --- "Tasdiqlangan dacha" belgisi (faqat admin) ---
@router.callback_query(F.data.startswith("toggleverify_"))
async def toggle_verify(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    dacha_key = callback.data.replace("toggleverify_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    d["verified"] = not d.get("verified", False)
    save_dachas(dachas)
    status = A["verify_on"] if d["verified"] else A["verify_off"]
    await callback.answer(status, show_alert=True)
    back_cb = manage_list_cb(callback.from_user.id)
    await safe_edit_text(callback, 
        A["edit_choose_field"].format(name=d["name_uz"]), reply_markup=edit_field_kb(dacha_key, back_cb, show_verify=True)
    )


# --- Owner kodlari (bir martalik) ---
def owner_codes_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["btn_new_owner_code"], callback_data="ownercode_new")],
            [InlineKeyboardButton(text=A["btn_list_owner_codes"], callback_data="ownercode_list")],
            [InlineKeyboardButton(text=A["back"], callback_data="admin_panel")],
        ]
    )


@router.callback_query(F.data == "admin_owner_codes")
async def admin_owner_codes(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await safe_edit_text(callback, A["owner_codes_panel_title"], reply_markup=owner_codes_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "ownercode_new")
async def owner_code_generate(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    code = uuid.uuid4().hex[:8].upper()
    codes = load_owner_codes()
    codes[code] = {"used": False, "used_by": None, "used_at": None, "created_at": now_tz().isoformat()}
    save_owner_codes(codes)
    await safe_edit_text(callback, 
        A["owner_code_generated"].format(code=code),
        reply_markup=owner_codes_menu_kb(),
        parse_mode="Markdown",
    )
    await callback.answer()


@router.callback_query(F.data == "ownercode_list")
async def owner_code_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    codes = load_owner_codes()
    if not codes:
        await safe_edit_text(callback, A["no_owner_codes"], reply_markup=owner_codes_menu_kb())
        await callback.answer()
        return
    rows = []
    for code, rec in sorted(codes.items(), key=lambda x: x[1]["created_at"], reverse=True)[:30]:
        status = A["code_used_tag"].format(uid=rec["used_by"]) if rec["used"] else A["code_active_tag"]
        rows.append([InlineKeyboardButton(text=f"{code} — {status}", callback_data="noop")])
        rows.append([InlineKeyboardButton(text=A["delete_btn"], callback_data=f"ocdel_{code}")])
    rows.append([InlineKeyboardButton(text=A["back"], callback_data="admin_owner_codes")])
    await safe_edit_text(callback, A["owner_codes_list_title"], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("ocdel_"))
async def owner_code_delete(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    code = callback.data.replace("ocdel_", "")
    codes = load_owner_codes()
    codes.pop(code, None)
    save_owner_codes(codes)
    await callback.answer(A["code_deleted"], show_alert=True)
    await owner_code_list(callback, state)


# --- Promo-kodlar ---
def promocodes_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["btn_new_promo"], callback_data="promo_new")],
            [InlineKeyboardButton(text=A["btn_list_promo"], callback_data="promo_list")],
            [InlineKeyboardButton(text=A["back"], callback_data="admin_panel")],
        ]
    )


@router.callback_query(F.data == "admin_promocodes")
async def admin_promocodes(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await safe_edit_text(callback, A["promo_panel_title"], reply_markup=promocodes_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "promo_new")
async def promo_new_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(PromoStates.entering_code)
    await safe_edit_text(callback, A["ask_promo_code"], reply_markup=cancel_kb("uz"))
    await callback.answer()


@router.message(PromoStates.entering_code)
async def promo_new_code(message: Message, state: FSMContext):
    code = message.text.strip().upper().replace(" ", "")
    if not code:
        await message.answer(A["invalid_promo_code"])
        return
    promos = load_promocodes()
    if code in promos:
        await message.answer(A["promo_code_exists"])
        return
    await state.update_data(new_promo_code=code)
    await state.set_state(PromoStates.choosing_type)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=A["promo_type_percent"], callback_data="promotype_percent"),
                InlineKeyboardButton(text=A["promo_type_fixed"], callback_data="promotype_fixed"),
            ]
        ]
    )
    await message.answer(A["ask_promo_type"], reply_markup=kb)


@router.callback_query(F.data.startswith("promotype_"))
async def promo_type_selected(callback: CallbackQuery, state: FSMContext):
    promo_type = callback.data.replace("promotype_", "")  # "percent" yoki "fixed"
    await state.update_data(new_promo_type=promo_type)
    await state.set_state(PromoStates.entering_value)
    prompt = A["ask_promo_percent"] if promo_type == "percent" else A["ask_promo_fixed"]
    await safe_edit_text(callback, prompt, reply_markup=cancel_kb("uz"))
    await callback.answer()


@router.message(PromoStates.entering_value)
async def promo_value_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    raw = message.text.strip().replace(",", ".").replace("%", "").replace(" ", "")
    try:
        value = float(raw)
    except ValueError:
        await message.answer(A["invalid_promo_value"])
        return
    promo_type = data["new_promo_type"]
    if promo_type == "percent" and not (0 < value <= 100):
        await message.answer(A["invalid_promo_value"])
        return
    if promo_type == "fixed" and value <= 0:
        await message.answer(A["invalid_promo_value"])
        return

    await state.update_data(new_promo_value=value)
    await state.set_state(PromoStates.entering_limit)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["promo_skip_btn"], callback_data="promolimit_skip")],
            [InlineKeyboardButton(text=A["cancel_operation_btn"], callback_data="cancel_operation")],
        ]
    )
    await message.answer(A["ask_promo_limit"], reply_markup=kb)


@router.callback_query(F.data == "promolimit_skip")
async def promo_limit_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(new_promo_limit=None)
    await state.set_state(PromoStates.entering_expiry)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["promo_skip_btn"], callback_data="promoexpiry_skip")],
            [InlineKeyboardButton(text=A["cancel_operation_btn"], callback_data="cancel_operation")],
        ]
    )
    await safe_edit_text(callback, A["ask_promo_expiry"], reply_markup=kb)
    await callback.answer()


@router.message(PromoStates.entering_limit)
async def promo_limit_entered(message: Message, state: FSMContext):
    raw = message.text.strip()
    if not raw.isdigit() or int(raw) <= 0:
        await message.answer(A["invalid_promo_value"])
        return
    await state.update_data(new_promo_limit=int(raw))
    await state.set_state(PromoStates.entering_expiry)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["promo_skip_btn"], callback_data="promoexpiry_skip")],
            [InlineKeyboardButton(text=A["cancel_operation_btn"], callback_data="cancel_operation")],
        ]
    )
    await message.answer(A["ask_promo_expiry"], reply_markup=kb)


async def _finalize_promo(user_id: int, data: dict, expires_at):
    code = data["new_promo_code"]
    promos = load_promocodes()
    promos[code] = {
        "type": data["new_promo_type"],
        "value": data["new_promo_value"],
        "active": True,
        "created_at": now_tz().isoformat(),
        "max_uses": data.get("new_promo_limit"),
        "used_count": 0,
        "expires_at": expires_at,
    }
    save_promocodes(promos)
    return code


@router.callback_query(F.data == "promoexpiry_skip")
async def promo_expiry_skip(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    code = await _finalize_promo(callback.from_user.id, data, None)
    await state.set_state(None)
    await safe_edit_text(callback, A["promo_created"].format(code=code), reply_markup=promocodes_menu_kb())
    await callback.answer()


@router.message(PromoStates.entering_expiry)
async def promo_expiry_entered(message: Message, state: FSMContext):
    data = await state.get_data()
    dt = parse_date(message.text)
    if not dt:
        await message.answer(TEXTS["uz"]["invalid_date"])
        return
    code = await _finalize_promo(message.from_user.id, data, dt.date().isoformat())
    await state.set_state(None)
    await message.answer(A["promo_created"].format(code=code), reply_markup=promocodes_menu_kb())


@router.callback_query(F.data == "promo_list")
async def promo_list(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    promos = load_promocodes()
    if not promos:
        await safe_edit_text(callback, A["no_promocodes"], reply_markup=promocodes_menu_kb())
        await callback.answer()
        return
    rows = []
    for code, rec in promos.items():
        val = f"{rec['value']:g}%" if rec["type"] == "percent" else f"{rec['value']:,.0f} so'm".replace(",", " ")
        status = "✅" if rec["active"] else "⛔️"
        used = rec.get("used_count", 0)
        limit_str = f"/{rec['max_uses']}" if rec.get("max_uses") else ""
        rows.append(
            [InlineKeyboardButton(
                text=f"{status} {code} — {val} ({used}{limit_str} marta)", callback_data=f"promotoggle_{code}"
            )]
        )
        rows.append([InlineKeyboardButton(text=A["delete_btn"], callback_data=f"promodel_{code}")])
    rows.append([InlineKeyboardButton(text=A["back"], callback_data="admin_promocodes")])
    await safe_edit_text(callback, A["promo_list_title"], reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


@router.callback_query(F.data.startswith("promodel_"))
async def promo_delete(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    code = callback.data.replace("promodel_", "")
    promos = load_promocodes()
    promos.pop(code, None)
    save_promocodes(promos)
    await callback.answer(A["code_deleted"], show_alert=True)
    await promo_list(callback, state)


@router.callback_query(F.data.startswith("promotoggle_"))
async def promo_toggle(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    code = callback.data.replace("promotoggle_", "")
    promos = load_promocodes()
    if code in promos:
        promos[code]["active"] = not promos[code]["active"]
        save_promocodes(promos)
    await callback.answer(A["promo_toggled"], show_alert=True)
    await promo_list(callback, state)


# --- Komissiyalarni boshqarish (har bir owner uchun alohida foiz) ---
def commissions_list_kb(owners: dict) -> InlineKeyboardMarkup:
    rows = []
    for uid, rec in owners.items():
        if rec.get("status") != "approved":
            continue
        rate = rec.get("commission_rate")
        enabled = rec.get("commission_enabled", True)
        pct_display = f"{rate * 100:g}%" if rate is not None else f"{COMMISSION_RATE * 100:g}% (standart)"
        status_tag = "" if enabled else " ⏸ TO'XTATILGAN"
        rows.append([InlineKeyboardButton(text=f"{rec['name']} — {pct_display}{status_tag}", callback_data="noop")])
        row = [InlineKeyboardButton(text=A["commission_edit_btn"], callback_data=f"cedit_{uid}")]
        if rate is not None:
            row.append(InlineKeyboardButton(text=A["commission_reset_btn"], callback_data=f"creset_{uid}"))
        rows.append(row)
        toggle_text = A["commission_resume_btn"] if not enabled else A["commission_pause_btn"]
        rows.append([InlineKeyboardButton(text=toggle_text, callback_data=f"ctoggle_{uid}")])
    rows.append([InlineKeyboardButton(text=A["back"], callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data.startswith("ctoggle_"))
async def commission_toggle(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    uid = callback.data.replace("ctoggle_", "")
    owners = load_owners()
    if uid not in owners:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    current = owners[uid].get("commission_enabled", True)
    owners[uid]["commission_enabled"] = not current
    save_owners(owners)
    msg = A["commission_paused"] if current else A["commission_resumed"]
    await callback.answer(msg, show_alert=True)
    await safe_edit_text(callback, 
        A["commissions_title"].format(default=f"{COMMISSION_RATE * 100:g}"), reply_markup=commissions_list_kb(owners)
    )


@router.callback_query(F.data == "admin_commissions")
async def admin_commissions(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    owners = load_owners()
    approved = {uid: r for uid, r in owners.items() if r.get("status") == "approved"}
    if not approved:
        await safe_edit_text(callback, A["no_owners"], reply_markup=admin_panel_kb())
        await callback.answer()
        return
    await safe_edit_text(callback, 
        A["commissions_title"].format(default=f"{COMMISSION_RATE * 100:g}"), reply_markup=commissions_list_kb(owners)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("cedit_"))
async def admin_commission_edit_ask(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    uid = callback.data.replace("cedit_", "")
    owners = load_owners()
    if uid not in owners:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    await state.update_data(commission_uid=uid)
    await state.set_state(AdminStates.editing_commission)
    await safe_edit_text(callback, A["ask_commission"].format(name=owners[uid]["name"]), reply_markup=cancel_kb("uz"))
    await callback.answer()


@router.message(AdminStates.editing_commission)
async def admin_commission_save(message: Message, state: FSMContext):
    data = await state.get_data()
    uid = data.get("commission_uid")
    raw = message.text.strip().replace(",", ".").replace("%", "")
    try:
        pct = float(raw)
    except ValueError:
        await message.answer(A["invalid_commission"])
        return
    if pct < 0 or pct > 100:
        await message.answer(A["invalid_commission"])
        return

    owners = load_owners()
    if uid not in owners:
        await state.set_state(None)
        await message.answer(A["no_owners"], reply_markup=admin_panel_kb())
        return
    owners[uid]["commission_rate"] = pct / 100
    save_owners(owners)
    await state.set_state(None)
    await message.answer(A["commission_updated"], reply_markup=commissions_list_kb(owners))


@router.callback_query(F.data.startswith("creset_"))
async def admin_commission_reset(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    uid = callback.data.replace("creset_", "")
    owners = load_owners()
    if uid in owners:
        owners[uid].pop("commission_rate", None)
        save_owners(owners)
    await callback.answer(A["commission_reset_done"], show_alert=True)
    owners = load_owners()
    approved = {u: r for u, r in owners.items() if r.get("status") == "approved"}
    if approved:
        await safe_edit_text(callback, 
            A["commissions_title"].format(default=f"{COMMISSION_RATE * 100:g}"), reply_markup=commissions_list_kb(owners)
        )
    else:
        await safe_edit_text(callback, A["no_owners"], reply_markup=admin_panel_kb())


# --- Hammaga xabar yuborish (broadcast) ---
def get_all_user_ids() -> set:
    ids = set()
    for uid in load_guests().keys():
        ids.add(int(uid))
    for uid in load_owners().keys():
        ids.add(int(uid))
    for b in load_bookings():
        ids.add(b["user_id"])
    return ids


@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(BroadcastStates.entering_message)
    await safe_edit_text(callback, A["ask_broadcast_text"], reply_markup=cancel_kb("uz"))
    await callback.answer()


@router.message(BroadcastStates.entering_message)
async def admin_broadcast_preview(message: Message, state: FSMContext):
    await state.update_data(broadcast_text=message.text)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["broadcast_send_btn"], callback_data="broadcast_confirm")],
            [InlineKeyboardButton(text=A["cancel_operation_btn"], callback_data="cancel_operation")],
        ]
    )
    count = len(get_all_user_ids())
    await message.answer(A["broadcast_preview"].format(count=count, text=message.text), reply_markup=kb)


@router.callback_query(F.data == "broadcast_confirm")
async def admin_broadcast_send(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    data = await state.get_data()
    text = data.get("broadcast_text", "")
    user_ids = get_all_user_ids()
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            sent += 1
        except Exception:
            failed += 1
    await state.set_state(None)
    await safe_edit_text(
        callback, A["broadcast_done"].format(sent=sent, failed=failed), reply_markup=admin_panel_kb()
    )
    await callback.answer()


# --- "Biz haqimizda" (admin tahrirlaydigan) ---
def about_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["btn_edit_about"], callback_data="about_edit")],
            [InlineKeyboardButton(text=A["back"], callback_data="admin_panel")],
        ]
    )


@router.callback_query(F.data == "admin_about")
async def admin_about(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    about_text = load_about_text()
    await safe_edit_text(callback, A["about_panel_title"] + "\n\n" + about_text, reply_markup=about_menu_kb())
    await callback.answer()


@router.callback_query(F.data == "about_edit")
async def about_edit_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(AboutStates.editing_text)
    await safe_edit_text(
        callback, A["ask_about_text"].format(old=load_about_text()), reply_markup=cancel_kb("uz")
    )
    await callback.answer()


@router.message(AboutStates.editing_text)
async def about_edit_save(message: Message, state: FSMContext):
    save_about_text(message.text.strip())
    await state.set_state(None)
    await message.answer(A["about_updated"], reply_markup=admin_panel_kb())


@router.callback_query(F.data == "menu_about")
async def menu_about(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    about_text = load_about_text()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=TEXTS[lang]["back"], callback_data="back_main")]]
    )
    await safe_edit_text(callback, about_text, reply_markup=kb)
    await callback.answer()


# --- Ro'yxatdan o'tgan mehmonlar ---
@router.callback_query(F.data.startswith("admin_guests_"))
async def admin_guests(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    page = int(callback.data.replace("admin_guests_", ""))
    guests = load_guests()
    if not guests:
        await safe_edit_text(callback, A["no_guests"], reply_markup=admin_panel_kb())
        await callback.answer()
        return

    items = sorted(guests.items(), key=lambda x: x[1].get("registered_at", ""), reverse=True)
    start = page * PAGE_SIZE
    page_items = items[start : start + PAGE_SIZE]
    text = A["guests_title"].format(count=len(items)) + "\n\n"
    for uid, rec in page_items:
        phone = rec.get("phone") or "—"
        text += f"👤 {rec.get('name', '—')}\n📞 {phone}\n🆔 {uid}\n\n"

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"admin_guests_{page - 1}"))
    if start + PAGE_SIZE < len(items):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"admin_guests_{page + 1}"))
    rows = [nav] if nav else []
    rows.append([InlineKeyboardButton(text=A["back"], callback_data="admin_panel")])
    await safe_edit_text(callback, text, reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    await callback.answer()


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
        await safe_edit_text(callback, A["no_bookings_admin"], reply_markup=admin_panel_kb())
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
        if b.get("status") == "cancelled":
            text += "\n❌ Bekor qilingan"
        text += "\n\n"

    await safe_edit_text(callback, text, reply_markup=bookings_page_kb(bookings, page))
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
    await safe_edit_text(callback, A["support_panel_title"], reply_markup=admin_support_kb())
    await callback.answer()


@router.callback_query(F.data == "admin_support_add")
async def admin_support_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    await state.set_state(SupportAdminStates.adding_title)
    await safe_edit_text(callback, A["ask_support_title"], reply_markup=cancel_kb("uz"))
    await callback.answer()


@router.message(SupportAdminStates.adding_title)
async def admin_support_add_title(message: Message, state: FSMContext):
    await state.update_data(new_title=message.text.strip())
    await state.set_state(SupportAdminStates.adding_text)
    await message.answer(A["ask_support_text"], reply_markup=cancel_kb("uz"))


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
        await safe_edit_text(callback, A["no_support_items"], reply_markup=admin_support_kb())
        await callback.answer()
        return
    await safe_edit_text(callback, A["support_manage_title"], reply_markup=support_manage_kb(items))
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
    await safe_edit_text(callback, 
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
    await safe_edit_text(callback, A["support_ask_new_value"].format(old=item[field]))
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
    await safe_edit_text(callback, 
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
        await safe_edit_text(callback, A["support_manage_title"], reply_markup=support_manage_kb(items))
    else:
        await safe_edit_text(callback, A["no_support_items"], reply_markup=admin_support_kb())


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
        await safe_edit_text(callback, A["no_tickets"], reply_markup=admin_support_kb())
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

    await safe_edit_text(callback, text, reply_markup=inbox_page_kb(tickets, page))
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
    await callback.message.answer(A["ask_reply"], reply_markup=cancel_kb("uz"))
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
