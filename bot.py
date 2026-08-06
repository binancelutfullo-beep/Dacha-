"""
Dacha bron qilish Telegram bot + Admin panel
Til: O'zbek / Rus (foydalanuvchi uchun) | Admin panel: O'zbek
Kutubxona: aiogram 3.x
Ma'lumotlar: dachas.json (dachalar) + bookings.json (bronlar)
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
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# ============ SOZLAMALAR ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ_BU_YERGA")
# Bir nechta adminni vergul bilan ajratib kiriting: "111111,222222"
ADMIN_IDS = [x.strip() for x in os.getenv("ADMIN_IDS", os.getenv("ADMIN_CHAT_ID", "")).split(",") if x.strip()]

DACHAS_FILE = "dachas.json"
BOOKINGS_FILE = "bookings.json"

logging.basicConfig(level=logging.INFO)

# ============ BOSHLANG'ICH DACHALAR (faqat birinchi marta ishga tushganda) ============
DEFAULT_DACHAS = {
    "dacha_1": {
        "name_uz": "🏡 Chimyon dachasi",
        "name_ru": "🏡 Дача Чимган",
        "desc_uz": "3 xonali, basseyn, mangal, 8 kishi uchun. Narxi: 800,000 so'm/kecha",
        "desc_ru": "3 комнаты, бассейн, мангал, до 8 человек. Цена: 800,000 сум/ночь",
    },
    "dacha_2": {
        "name_uz": "🌲 Bo'stonliq dachasi",
        "name_ru": "🌲 Дача Бустанлык",
        "desc_uz": "2 xonali, tog' manzarasi, 5 kishi uchun. Narxi: 500,000 so'm/kecha",
        "desc_ru": "2 комнаты, вид на горы, до 5 человек. Цена: 500,000 сум/ночь",
    },
}

TEXTS = {
    "uz": {
        "choose_lang": "Tilni tanlang / Выберите язык:",
        "welcome": "Assalomu alaykum! Dacha bron qilish botiga xush kelibsiz. 🏡\n\nQuyidagi menyudan foydalaning:",
        "menu_list": "📋 Dachalar ro'yxati",
        "menu_my": "🗂 Mening bronlarim",
        "menu_admin": "🔐 Admin panel",
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
        "confirm_yes": "✅ Tasdiqlash",
        "confirm_no": "❌ Bekor qilish",
        "booked": "🎉 Bronlash muvaffaqiyatli qabul qilindi! Tez orada operator siz bilan bog'lanadi.",
        "cancelled": "Bekor qilindi.",
        "no_bookings": "Sizda hozircha bronlar yo'q.",
        "your_bookings": "🗂 Sizning bronlaringiz:\n\n",
        "no_dachas_user": "Hozircha dachalar mavjud emas.",
        "new_admin_booking": "🆕 Yangi bron!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}\n🆔 User: {user_id}",
    },
    "ru": {
        "choose_lang": "Tilni tanlang / Выберите язык:",
        "welcome": "Здравствуйте! Добро пожаловать в бот бронирования дач. 🏡\n\nВыберите пункт меню:",
        "menu_list": "📋 Список дач",
        "menu_my": "🗂 Мои брони",
        "menu_admin": "🔐 Админ панель",
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
        "confirm_yes": "✅ Подтвердить",
        "confirm_no": "❌ Отменить",
        "booked": "🎉 Бронь успешно оформлена! Скоро с вами свяжется оператор.",
        "cancelled": "Отменено.",
        "no_bookings": "У вас пока нет броней.",
        "your_bookings": "🗂 Ваши брони:\n\n",
        "no_dachas_user": "Пока нет доступных дач.",
        "new_admin_booking": "🆕 Новая бронь!\n\n🏡 {dacha}\n📅 {checkin} - {checkout}\n👤 {name}\n📞 {phone}\n🆔 User: {user_id}",
    },
}

# Admin panel matnlari (o'zbek tilida)
A = {
    "panel_title": "🔐 Admin panel. Nima qilmoqchisiz?",
    "btn_add": "➕ Yangi dacha qo'shish",
    "btn_manage": "✏️ Dachalarni boshqarish",
    "btn_bookings": "📋 Bronlarni ko'rish",
    "back": "⬅️ Orqaga",
    "ask_name_uz": "1/4. Dacha nomini o'zbek tilida kiriting (masalan: 🏡 Chimyon dachasi):",
    "ask_name_ru": "2/4. Endi nomini rus tilida kiriting:",
    "ask_desc_uz": "3/4. Tavsif va narxni o'zbek tilida kiriting:",
    "ask_desc_ru": "4/4. Tavsif va narxni rus tilida kiriting:",
    "added": "✅ Yangi dacha qo'shildi!",
    "manage_title": "Tahrirlash yoki o'chirish uchun dachani tanlang:",
    "edit_btn": "✏️ Tahrirlash",
    "delete_btn": "🗑 O'chirish",
    "edit_choose_field": "«{name}» — qaysi maydonni tahrirlaysiz?",
    "field_name_uz": "📝 Nomi (UZ)",
    "field_name_ru": "📝 Nomi (RU)",
    "field_desc_uz": "📝 Tavsif (UZ)",
    "field_desc_ru": "📝 Tavsif (RU)",
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
    editing_value = State()


# ============ MA'LUMOTLAR BILAN ISHLASH ============
def load_dachas() -> dict:
    if not os.path.exists(DACHAS_FILE):
        save_dachas(DEFAULT_DACHAS)
        return dict(DEFAULT_DACHAS)
    with open(DACHAS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_dachas(dachas: dict):
    with open(DACHAS_FILE, "w", encoding="utf-8") as f:
        json.dump(dachas, f, ensure_ascii=False, indent=2)


def load_bookings() -> list:
    if os.path.exists(BOOKINGS_FILE):
        with open(BOOKINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_bookings(bookings: list):
    with open(BOOKINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(bookings, f, ensure_ascii=False, indent=2)


def add_booking(booking: dict):
    bookings = load_bookings()
    bookings.append(booking)
    save_bookings(bookings)


def is_admin(user_id: int) -> bool:
    return str(user_id) in ADMIN_IDS


def get_lang(data: dict) -> str:
    return data.get("lang", "uz")


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


def main_menu_kb(lang: str, user_id: int) -> InlineKeyboardMarkup:
    t = TEXTS[lang]
    rows = [
        [InlineKeyboardButton(text=t["menu_list"], callback_data="menu_list")],
        [InlineKeyboardButton(text=t["menu_my"], callback_data="menu_my")],
    ]
    if is_admin(user_id):
        rows.append([InlineKeyboardButton(text=t["menu_admin"], callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


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


def admin_panel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["btn_add"], callback_data="admin_add")],
            [InlineKeyboardButton(text=A["btn_manage"], callback_data="admin_manage")],
            [InlineKeyboardButton(text=A["btn_bookings"], callback_data="admin_bookings_0")],
            [InlineKeyboardButton(text=A["back"], callback_data="back_main")],
        ]
    )


def admin_manage_kb(dachas: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, d in dachas.items():
        rows.append([InlineKeyboardButton(text=d["name_uz"], callback_data="noop")])
        rows.append(
            [
                InlineKeyboardButton(text=A["edit_btn"], callback_data=f"edit_{key}"),
                InlineKeyboardButton(text=A["delete_btn"], callback_data=f"delask_{key}"),
            ]
        )
    rows.append([InlineKeyboardButton(text=A["back"], callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def edit_field_kb(dacha_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=A["field_name_uz"], callback_data=f"ef_nu_{dacha_key}")],
            [InlineKeyboardButton(text=A["field_name_ru"], callback_data=f"ef_nr_{dacha_key}")],
            [InlineKeyboardButton(text=A["field_desc_uz"], callback_data=f"ef_du_{dacha_key}")],
            [InlineKeyboardButton(text=A["field_desc_ru"], callback_data=f"ef_dr_{dacha_key}")],
            [InlineKeyboardButton(text=A["back"], callback_data="admin_manage")],
        ]
    )


def delete_confirm_kb(dacha_key: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=A["delete_yes"], callback_data=f"delyes_{dacha_key}"),
                InlineKeyboardButton(text=A["delete_no"], callback_data="admin_manage"),
            ]
        ]
    )


FIELD_MAP = {"nu": "name_uz", "nr": "name_ru", "du": "desc_uz", "dr": "desc_ru"}


def parse_date(text: str):
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y")
    except ValueError:
        return None


# ============ FOYDALANUVCHI HANDLERLARI ============
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(TEXTS["uz"]["choose_lang"], reply_markup=lang_kb())


@router.callback_query(F.data.startswith("lang_"))
async def choose_lang(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split("_")[1]
    await state.update_data(lang=lang)
    t = TEXTS[lang]
    await callback.message.edit_text(t["welcome"], reply_markup=main_menu_kb(lang, callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "back_main")
async def back_main(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.set_state(None)
    await callback.message.edit_text(TEXTS[lang]["welcome"], reply_markup=main_menu_kb(lang, callback.from_user.id))
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
    text = f"{d[f'name_{lang}']}\n\n{d[f'desc_{lang}']}"
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
    await state.update_data(checkout=message.text.strip())
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
    text = TEXTS[lang]["confirm"].format(
        dacha=d[f"name_{lang}"],
        checkin=data["checkin"],
        checkout=data["checkout"],
        name=data["name"],
        phone=phone,
    )
    await state.set_state(BookingStates.confirming)
    await message.answer(text, reply_markup=confirm_kb(lang))


@router.callback_query(F.data == "confirm_yes", BookingStates.confirming)
async def confirm_booking(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    lang = get_lang(data)
    dachas = load_dachas()
    d = dachas[data["dacha_key"]]

    booking = {
        "id": uuid.uuid4().hex[:8],
        "user_id": callback.from_user.id,
        "username": callback.from_user.username or "—",
        "dacha": d["name_uz"],
        "checkin": data["checkin"],
        "checkout": data["checkout"],
        "name": data["name"],
        "phone": data["phone"],
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
            user_id=callback.from_user.id,
        )
        try:
            await bot.send_message(admin_id, admin_text)
        except Exception as e:
            logging.warning(f"Adminga ({admin_id}) xabar yuborilmadi: {e}")

    await state.clear()
    await state.update_data(lang=lang)
    await callback.message.answer(TEXTS[lang]["welcome"], reply_markup=main_menu_kb(lang, callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "confirm_no", BookingStates.confirming)
async def cancel_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    await state.clear()
    await state.update_data(lang=lang)
    await callback.message.edit_text(TEXTS[lang]["cancelled"])
    await callback.message.answer(TEXTS[lang]["welcome"], reply_markup=main_menu_kb(lang, callback.from_user.id))
    await callback.answer()


@router.callback_query(F.data == "menu_my")
async def my_bookings(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    lang = get_lang(data)
    t = TEXTS[lang]
    bookings = load_bookings()
    user_bookings = [b for b in bookings if b["user_id"] == callback.from_user.id]

    if not user_bookings:
        text = t["no_bookings"]
    else:
        text = t["your_bookings"]
        for b in user_bookings:
            text += f"🏡 {b['dacha']}\n📅 {b['checkin']} - {b['checkout']}\n\n"

    await callback.message.edit_text(text, reply_markup=main_menu_kb(lang, callback.from_user.id))
    await callback.answer()


# ============ ADMIN HANDLERLARI ============
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


# --- Yangi dacha qo'shish ---
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
    data = await state.get_data()
    dachas = load_dachas()
    new_key = f"dacha_{uuid.uuid4().hex[:8]}"
    dachas[new_key] = {
        "name_uz": data["new_name_uz"],
        "name_ru": data["new_name_ru"],
        "desc_uz": data["new_desc_uz"],
        "desc_ru": message.text.strip(),
    }
    save_dachas(dachas)
    await state.set_state(None)
    await message.answer(A["added"], reply_markup=admin_panel_kb())


# --- Boshqarish (tahrirlash/o'chirish ro'yxati) ---
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
    await callback.message.edit_text(A["manage_title"], reply_markup=admin_manage_kb(dachas))
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop(callback: CallbackQuery):
    await callback.answer()


# --- Tahrirlash: maydon tanlash ---
@router.callback_query(F.data.startswith("edit_"))
async def admin_edit_choose_field(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    dacha_key = callback.data.replace("edit_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        A["edit_choose_field"].format(name=d["name_uz"]), reply_markup=edit_field_kb(dacha_key)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ef_"))
async def admin_edit_ask_value(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    _, field_code, dacha_key = callback.data.split("_", 2)
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
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
    if dacha_key not in dachas:
        await state.set_state(None)
        await message.answer(A["no_dachas"], reply_markup=admin_panel_kb())
        return
    dachas[dacha_key][field] = message.text.strip()
    save_dachas(dachas)
    await state.set_state(None)
    await message.answer(A["updated"], reply_markup=admin_manage_kb(dachas))


# --- O'chirish ---
@router.callback_query(F.data.startswith("delask_"))
async def admin_delete_ask(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    dacha_key = callback.data.replace("delask_", "")
    dachas = load_dachas()
    d = dachas.get(dacha_key)
    if not d:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        A["delete_confirm"].format(name=d["name_uz"]), reply_markup=delete_confirm_kb(dacha_key)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("delyes_"))
async def admin_delete_confirm(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer(A["not_admin"], show_alert=True)
        return
    dacha_key = callback.data.replace("delyes_", "")
    dachas = load_dachas()
    dachas.pop(dacha_key, None)
    save_dachas(dachas)
    await callback.answer(A["deleted"], show_alert=True)
    if dachas:
        await callback.message.edit_text(A["manage_title"], reply_markup=admin_manage_kb(dachas))
    else:
        await callback.message.edit_text(A["no_dachas"], reply_markup=admin_panel_kb())


# --- Bronlarni ko'rish (sahifalab, har birida o'chirish tugmasi) ---
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
        ) + "\n\n"

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
    # Ro'yxatni yangilab qayta ko'rsatamiz
    callback.data = f"admin_bookings_{page}"
    await admin_bookings(callback, state)


# ============ ISHGA TUSHIRISH ============
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
