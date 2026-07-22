# 🎭 DARK SPAM FILTER - ROYAL ULTRA EDITION

بوت فلترة كومبو كروت ائتمان - يدعم ملفات كبيرة جداً (حتى 5GB+)

## ⚡ الميزات

- 🧹 **CLEAN COMBO** - تنظيف وفلترة الكومبو
- 🌍 **FILTER COUNTRIES** - فلترة حسب الدولة
- ✂️ **SPLIT MANAGER** - تقسيم الملفات الكبيرة
- 🏦 **BANKS MANAGER** - إدارة البنوك
- 🔍 **BINs SEARCH** - البحث بالـ BIN
- 💳 **CARD BRANDS** - فلترة حسب نوع الكارت
- 📊 **STATISTICS** - إحصائيات متقدمة
- 🗑️ **CLEAR** - مسح البيانات

## 🛠️ التثبيت

```bash
# تثبيت المتطلبات
pip install -r requirements.txt

# تعديل config.py
# أضف API_ID, API_HASH, BOT_TOKEN

# تشغيل البوت
python bot.py
```

## 📁 الملفات

- `bot.py` - البوت الرئيسي
- `config.py` - الإعدادات
- `database.py` - قاعدة البيانات
- `filters.py` - منطق الفلترة
- `requirements.txt` - المتطلبات

## 📏 الحدود

- الحد الأقصى لحجم الملف: **5 GB**
- يدعم ملفات حتى **25+ مليون سطر**
- معالجة على دفعات لتحسين الأداء

## 🔧 الإعداد

1. احصل على API_ID و API_HASH من [my.telegram.org](https://my.telegram.org)
2. احصل على BOT_TOKEN من [@BotFather](https://t.me/BotFather)
3. عدّل ملف `config.py`
4. شغّل البوت: `python bot.py`
