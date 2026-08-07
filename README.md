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

## ⚠️ Ma'lumotlarni doimiy saqlash (MUHIM — Railway uchun)

Railway'ning odatiy fayl tizimi **doimiy emas** — har safar qayta deploy qilinganda yoki konteyner qayta ishga tushganda, oldingi `dachas.json`, `bookings.json`, `owners.json` va boshqa fayllar **o'chib ketadi**. Aynan shu sabab "kechagi ma'lumotlar bugun yo'qolib ketishi"ga olib keladi.

**Yechim — Railway Volume qo'shish:**

1. Railway loyihangizda service'ni oching → **Settings** → **Volumes** bo'limiga o'ting
2. **"+ New Volume"** tugmasini bosing
3. Mount path sifatida `/data` deb yozing, hajmini tanlang (1 GB yetarli)
4. **Variables** bo'limiga qaytib, yangi o'zgaruvchi qo'shing:
   ```
   DATA_DIR=/data
   ```
5. Saqlang — Railway avtomatik qayta deploy qiladi

Shundan keyin barcha `.json` fayllar va PDF shartnomalar (`contracts/` papkasi) shu Volume ichiga yoziladi va **qayta deploy qilinganda ham yo'qolmaydi**.

`DATA_DIR` o'zgaruvchisi berilmasa, fayllar joriy papkaga yoziladi (lokal test uchun muammo emas, lekin Railway'da xavfli).

## Admin panel

`ADMIN_IDS` ro'yxatiga kiritilgan foydalanuvchilar botda `/admin` buyrug'ini yuborishi yoki asosiy menyudagi **"🔐 Admin panel"** tugmasini bosishi mumkin. Hammasi inline tugmalar orqali:

- **➕ Yangi dacha qo'shish** — bot ketma-ket nomi (UZ/RU) va tavsifini (UZ/RU) so'raydi
- **✏️ Dachalarni boshqarish** — har bir dacha yonida "Tahrirlash" va "O'chirish" tugmalari bor
  - Tahrirlashda qaysi maydonni o'zgartirish kerakligini tanlaysiz (nomi yoki tavsifi, UZ/RU), keyin yangi matnni yuborasiz
  - O'chirishda tasdiqlash so'raladi
- **📋 Bronlarni ko'rish** — barcha bronlar ro'yxati sahifalab ko'rsatiladi, har birini o'chirish mumkin

Dachalar `dachas.json` faylida saqlanadi va kodga tegmasdan to'liq boshqariladi. Birinchi ishga tushirishda avtomatik 2 ta namunaviy dacha yaratiladi — ularni admin panel orqali o'chirib, o'zingiznikini qo'shishingiz mumkin.

## Qo'llab-quvvatlash paneli

Admin panelidagi **"🆘 Qo'llab-quvvatlash"** bo'limi orqali:

- **➕ Yangi ma'lumot qo'shish** — sarlavha va matn (masalan: "Ish vaqti", "To'lov usullari", "Manzil") — foydalanuvchilarga "🆘 Yordam" menyusida ko'rinadi
- **✏️ Ma'lumotlarni boshqarish** — mavjud ma'lumotlarni tahrirlash (sarlavha yoki matn) yoki o'chirish
- **📨 Kelgan xabarlar** — foydalanuvchilar "✍️ Operatorga xabar yozish" orqali yuborgan murojaatlar shu yerda ko'rinadi. Har biriga **"↩️ Javob berish"** tugmasi orqali to'g'ridan-to'g'ri botdan javob yozish mumkin — javob avtomatik foydalanuvchiga yetkaziladi

Foydalanuvchi tomonida: asosiy menyudagi **"🆘 Yordam"** bo'limida admin qo'shgan ma'lumotlar ro'yxati va "operatorga yozish" tugmasi chiqadi. Yangi murojaat kelganda barcha adminlarga darhol xabar boradi (javob tugmasi bilan birga).

## Pastki menyu

Endi barcha asosiy bo'limlar (Dachalar, Bronlarim, Yordam va h.k.) Telegram'ning **pastki doimiy klaviaturasida** ko'rinadi — foydalanuvchi til tanlagandan so'ng bu tugmalar avtomatik chiqadi va suhbat davomida doim ko'rinib turadi. Admin va tasdiqlangan dacha egalari uchun qo'shimcha tugmalar (Admin panel / Mening dachalarim) shu yerda avtomatik paydo bo'ladi.

## Dacha egalari tizimi

- Har qanday foydalanuvchi pastdagi **"🏘 Dacha egasi bo'lish"** tugmasi orqali ariza yuboradi (ism + telefon) — ariza barcha adminlarga "✅ Tasdiqlash / ❌ Rad etish" tugmalari bilan boradi.
- Admin tasdiqlasa, foydalanuvchiga xabar boradi va uning pastki menyusida **"🏘 Mening dachalarim"** tugmasi paydo bo'ladi.
- Owner shu bo'lim orqali **faqat o'ziga tegishli** dachalarni qo'sha, tahrirlay va o'chira oladi (admin esa hamma dachalarni boshqara oladi).
- Yangi dacha qo'shishdan oldin owner'ga **shartnoma matni** ko'rsatiladi ("✅ Roziman" / "❌ Rad etaman"). Rozi bo'lgach, dacha ma'lumotlari (nomi, tavsifi, bir kechalik narxi) so'raladi va **PDF shartnoma** avtomatik yaratilib, ownerga fayl sifatida yuboriladi (`contracts/` papkasida ham saqlanadi).

## 1% komissiya

Har bir dachaga endi **narx (so'm/kecha)** biriktiriladi. Foydalanuvchi bron qilayotganda tasdiqlash oynasida taxminiy umumiy summa va undan **1% platforma komissiyasi** avtomatik hisoblab ko'rsatiladi. Bron tasdiqlangach:
- Admin(lar)ga umumiy summa va komissiya bilan xabar boradi
- Agar dacha owner'ga tegishli bo'lsa, ownerga ham umumiy summa, komissiya va o'ziga tegishli sof summa ko'rsatilgan xabar boradi

**Eslatma:** hozircha bu faqat hisob-kitob va ma'lumot sifatida ko'rsatiladi — real to'lov tizimi (Payme/Click) ulanmagan. Xohlasangiz, keyingi qadam sifatida shuni ham qo'shib beraman.

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
