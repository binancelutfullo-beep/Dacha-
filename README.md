# Dacha bron qilish Telegram bot

## O'rnatish

1. Python 3.10+ o'rnatilgan bo'lishi kerak.
2. Kutubxonalarni o'rnating:
   ```
   pip install -r requirements.txt
   ```
3. [@BotFather](https://t.me/BotFather) orqali yangi bot yarating va tokenni oling.
4. Tokenni muhit o'zgaruvchisi sifatida bering (yoki `bot.py` ichidagi `BOT_TOKEN` qatoriga to'g'ridan-to'g'ri yozing):
   ```
   export BOT_TOKEN="123456:ABC-your-token-here"
   ```
   Windows'da:
   ```
   set BOT_TOKEN=123456:ABC-your-token-here
   ```
5. Admin huquqi berish uchun Telegram ID'ingizni kiriting (bir nechta admin bo'lsa, vergul bilan ajrating):
   ```
   export ADMIN_IDS="123456789"
   # yoki bir nechta admin:
   export ADMIN_IDS="123456789,987654321"
   ```
   ID'ni bilish uchun [@userinfobot](https://t.me/userinfobot) ga yozing.

## Ishga tushirish

```
python bot.py
```

## Admin panel

`ADMIN_IDS` ro'yxatiga kiritilgan foydalanuvchilar botda `/admin` buyrug'ini yuborishi yoki asosiy menyudagi **"🔐 Admin panel"** tugmasini bosishi mumkin. Hammasi inline tugmalar orqali:

- **➕ Yangi dacha qo'shish** — bot ketma-ket nomi (UZ/RU) va tavsifini (UZ/RU) so'raydi
- **✏️ Dachalarni boshqarish** — har bir dacha yonida "Tahrirlash" va "O'chirish" tugmalari bor
  - Tahrirlashda qaysi maydonni o'zgartirish kerakligini tanlaysiz (nomi yoki tavsifi, UZ/RU), keyin yangi matnni yuborasiz
  - O'chirishda tasdiqlash so'raladi
- **📋 Bronlarni ko'rish** — barcha bronlar ro'yxati sahifalab ko'rsatiladi, har birini o'chirish mumkin

Dachalar `dachas.json` faylida saqlanadi va kodga tegmasdan to'liq boshqariladi. Birinchi ishga tushirishda avtomatik 2 ta namunaviy dacha yaratiladi — ularni admin panel orqali o'chirib, o'zingiznikini qo'shishingiz mumkin.

## Qanday ishlaydi

1. Foydalanuvchi `/start` bosadi → til tanlaydi (UZ/RU).
2. "Dachalar ro'yxati" dan dacha tanlaydi, tavsifini ko'radi.
3. "Bron qilish" tugmasini bosib: kirish sanasi → chiqish sanasi → ism → telefon raqamini kiritadi.
4. Ma'lumotlarni tasdiqlaydi → bron `bookings.json` fayliga saqlanadi va (agar sozlangan bo'lsa) admin'ga xabar boradi.
5. "Mening bronlarim" bo'limida o'z bronlarini ko'rishi mumkin.

## Keyingi qadamlar (ixtiyoriy takomillashtirish)

- Sana band/bo'sh ekanligini avtomatik tekshirish (bir xil sanaga ikki marta bron bo'lmasligi uchun)
- Dachalar rasmlarini yuborish (`message.answer_photo`)
- To'lov integratsiyasi (Payme/Click)
- SQLite bazasiga o'tish (ko'p dacha bo'lsa qulayroq)
