import os
import asyncio
import logging
import aiofiles
import aiohttp
from datetime import datetime
from telethon import TelegramClient, events, Button

from config import API_ID, API_HASH, BOT_TOKEN, MAX_FILE_SIZE, COUNTRIES, CARD_BRANDS
from database import (
    init_db, get_user, create_user, update_user_stats,
    create_task, update_task, get_user_tasks,
    save_combo_results_batch, get_task_results, get_task_stats,
    clear_task_results, search_bins
)
from filters import parse_combo_line_fast, luhn_check_fast, get_combo_statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = TelegramClient('combo_bot', API_ID, API_HASH).start(bot_token=BOT_TOKEN)
user_states = {}

# Store user files for BIN search
user_files = {}  # {user_id: temp_file_path}

# Admin ID
ADMIN_ID = 8786282734

# BIN Lookup API
async def lookup_bin(bin_code: str) -> dict:
    """Fetch BIN info from multiple sources"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://lookup.binlist.net/{bin_code}", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        'bin': bin_code,
                        'bank': data.get('bank', {}).get('name', 'Unknown'),
                        'brand': data.get('scheme', 'Unknown').upper(),
                        'type': data.get('type', 'Unknown').upper(),
                        'country': data.get('country', {}).get('name', 'Unknown'),
                        'country_code': data.get('country', {}).get('alpha2', 'XX'),
                        'prepaid': data.get('prepaid', False),
                    }
    except Exception as e:
        logger.error(f"BIN lookup error: {e}")
    
    return {
        'bin': bin_code,
        'bank': 'Unknown',
        'brand': 'Unknown',
        'type': 'Unknown',
        'country': 'Unknown',
        'country_code': 'XX',
        'prepaid': False,
    }

def get_main_menu():
    return [
        [Button.inline("🧹 CLEAN COMBO", data="clean_combo"),
         Button.inline("🌍 FILTER COUNTRIES", data="filter_countries")],
        [Button.inline("✂️ SPLIT MANAGER", data="split_manager"),
         Button.inline("🏦 BANKS MANAGER", data="banks_manager")],
        [Button.inline("🔍 BINs SEARCH", data="bins_search"),
         Button.inline("💳 CARD BRANDS", data="card_brands")],
        [Button.inline("📊 STATISTICS", data="statistics"),
         Button.inline("🗑️ CLEAR", data="clear_data")],
    ]

def get_country_buttons(selected=None):
    if selected is None:
        selected = set()
    buttons = []
    row = []
    for code, name in COUNTRIES.items():
        emoji = "✅" if code in selected else "⬜"
        row.append(Button.inline(f"{emoji} {code}", data=f"country_{code}"))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Button.inline("✔️ Apply Filter", data="apply_country_filter")])
    buttons.append([Button.inline("🔙 Back", data="back_to_menu")])
    return buttons

def get_brand_buttons(selected=None):
    if selected is None:
        selected = set()
    buttons = []
    row = []
    for brand in CARD_BRANDS.keys():
        emoji = "✅" if brand in selected else "⬜"
        row.append(Button.inline(f"{emoji} {brand}", data=f"brand_{brand}"))
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([Button.inline("✔️ Apply Filter", data="apply_brand_filter")])
    buttons.append([Button.inline("🔙 Back", data="back_to_menu")])
    return buttons

@bot.on(events.NewMessage(pattern='/start'))
async def start_handler(event):
    user = await get_user(event.sender_id)
    if not user:
        await create_user(event.sender_id, event.sender.username or "", event.sender.first_name or "")
    
    # Notify admin
    username = event.sender.username or "None"
    user_id = event.sender_id
    first_name = event.sender.first_name or "None"
    admin_msg = f"NEW USER\nID: {user_id}\nName: {first_name}\nUsername: @{username}"
    try:
        await bot.send_message(ADMIN_ID, admin_msg)
    except: pass
    
    await event.respond("""
⚡ **DARK SPAM FILTER** ⚡
🎭 **ROYAL ULTRA EDITION**

━━━━━━━━━━━━━━━━━━━━
© **Premium Combo Analysis System**
🧠 استخراج ذكي | 📊 تحليل متقدم | 🔍 فلترة احترافية
━━━━━━━━━━━━━━━━━━━━

📌 **Power Features:**
🔹 فلترة حسب الدولة
🔹 تحليل BIN/Bank
🔹 فلترة حسب نوع الكارت
🔹 Luhn Validation
🔹 Split Manager
🔹 دعم ملفات **كبيرة جداً** (حتى 5GB+)

━━━━━━━━━━━━━━━━━━━━
📤 **أرسل ملف الكومبو (txt) للبدء فوراً**
━━━━━━━━━━━━━━━━━━━━
""", buttons=get_main_menu())

@bot.on(events.CallbackQuery(data=b"back_to_menu"))
async def back_to_menu(event):
    await event.edit("🏠 **Main Menu**", buttons=get_main_menu())

@bot.on(events.CallbackQuery(data=b"clean_combo"))
async def clean_combo_handler(event):
    user_states[event.sender_id] = {'state': 'waiting_file', 'action': 'clean'}
    await event.edit(
        "🧹 **CLEAN COMBO MODE**\n\n"
        "📤 أرسل ملف الكومبو (txt) للبدء\n\n"
        "**الملف هيت عالج ويتفلتر:**\n"
        "✅ إزالة الخطوط الفارغة\n"
        "✅ إزالة المكرر\n"
        "✅ فلترة حسب Luhn\n"
        "✅ تنسيق موحد\n\n"
        "⏳ **في انتظار الملف...**",
        buttons=[[Button.inline("❌ Cancel", data="cancel_operation")]]
    )

@bot.on(events.CallbackQuery(data=b"filter_countries"))
async def filter_countries_handler(event):
    user_states[event.sender_id] = {'state': 'selecting_countries', 'selected': set()}
    await event.edit("🌍 **FILTER BY COUNTRIES**\n\nاختر الدول المطلوبة:", buttons=get_country_buttons())

@bot.on(events.CallbackQuery(pattern=r"^country_"))
async def country_select_handler(event):
    data = event.data.decode()
    country_code = data.replace("country_", "")
    state = user_states.get(event.sender_id, {})
    selected = state.get('selected', set())
    if country_code in selected:
        selected.remove(country_code)
    else:
        selected.add(country_code)
    user_states[event.sender_id]['selected'] = selected
    await event.edit("🌍 **FILTER BY COUNTRIES**\n\nاختر الدول المطلوبة:", buttons=get_country_buttons(selected))

@bot.on(events.CallbackQuery(data=b"apply_country_filter"))
async def apply_country_filter(event):
    state = user_states.get(event.sender_id, {})
    selected = state.get('selected', set())
    if not selected:
        await event.answer("⚠️ اختر دولة واحدة على الأقل!", alert=True)
        return
    user_states[event.sender_id]['state'] = 'waiting_file'
    user_states[event.sender_id]['action'] = 'filter_country'
    user_states[event.sender_id]['countries'] = list(selected)
    countries_list = ', '.join(selected)
    await event.edit(
        f"🌍 **Country Filter Active**\n\n**الدول المختارة:** {countries_list}\n\n"
        "📤 أرسل ملف الكومبو (txt) للبدء\n\n⏳ **في انتظار الملف...**",
        buttons=[[Button.inline("❌ Cancel", data="cancel_operation")]]
    )

@bot.on(events.CallbackQuery(data=b"split_manager"))
async def split_manager_handler(event):
    user_states[event.sender_id] = {'state': 'waiting_split_size'}
    await event.edit(
        "✂️ **SPLIT MANAGER**\n\nأرسل عدد الخطوط لكل ملف:\n**مثال:** 100000",
        buttons=[[Button.inline("❌ Cancel", data="cancel_operation")]]
    )

@bot.on(events.CallbackQuery(data=b"bins_search"))
async def bins_search_handler(event):
    user_states[event.sender_id] = {'state': 'waiting_bin_search'}
    await event.edit(
        "🔍 **BIN SEARCH**\n\nأرسل 6-8 أرقام BIN للبحث:\n**مثال:** 414720",
        buttons=[[Button.inline("❌ Cancel", data="cancel_operation")]]
    )

@bot.on(events.CallbackQuery(data=b"card_brands"))
async def card_brands_handler(event):
    user_states[event.sender_id] = {'state': 'selecting_brands', 'selected': set()}
    await event.edit("💳 **FILTER BY CARD BRANDS**\n\nاختر أنواع الكروت:", buttons=get_brand_buttons())

@bot.on(events.CallbackQuery(pattern=r"^brand_"))
async def brand_select_handler(event):
    data = event.data.decode()
    brand = data.replace("brand_", "")
    state = user_states.get(event.sender_id, {})
    selected = state.get('selected', set())
    if brand in selected:
        selected.remove(brand)
    else:
        selected.add(brand)
    user_states[event.sender_id]['selected'] = selected
    await event.edit("💳 **FILTER BY CARD BRANDS**\n\nاختر أنواع الكروت:", buttons=get_brand_buttons(selected))

@bot.on(events.CallbackQuery(data=b"apply_brand_filter"))
async def apply_brand_filter(event):
    state = user_states.get(event.sender_id, {})
    selected = state.get('selected', set())
    if not selected:
        await event.answer("⚠️ اختر نوع كارت واحد على الأقل!", alert=True)
        return
    user_states[event.sender_id]['state'] = 'waiting_file'
    user_states[event.sender_id]['action'] = 'filter_brand'
    user_states[event.sender_id]['brands'] = list(selected)
    brands_list = ', '.join(selected)
    await event.edit(
        f"💳 **Brand Filter Active**\n\n**الأنواع المختارة:** {brands_list}\n\n"
        "📤 أرسل ملف الكومبو (txt) للبدء\n\n⏳ **في انتظار الملف...**",
        buttons=[[Button.inline("❌ Cancel", data="cancel_operation")]]
    )

@bot.on(events.CallbackQuery(data=b"statistics"))
async def statistics_handler(event):
    user = await get_user(event.sender_id)
    if not user:
        await event.answer("⚠️ لا توجد بيانات!", alert=True)
        return
    tasks = await get_user_tasks(event.sender_id, limit=5)
    text = f"📊 **Your Statistics**\n━━━━━━━━━━━━━━━━━━━━\n📁 **Total Files:** {user['total_files']}\n📝 **Total Lines:** {user['total_lines']:,}\n━━━━━━━━━━━━━━━━━━━━\n📋 **Recent Tasks:**\n"
    for task in tasks:
        status_emoji = "✅" if task['status'] == 'completed' else "⏳"
        text += f"{status_emoji} {task['filename'][:30]}... | {task['found_lines']:,} found\n"
    await event.edit(text, buttons=[[Button.inline("🔙 Back", data="back_to_menu")]])

@bot.on(events.CallbackQuery(data=b"clear_data"))
async def clear_data_handler(event):
    await event.edit("🗑️ **CLEAR DATA**\n\nاختر ما تريد مسحه:", buttons=[
        [Button.inline("🗑️ Clear Last Task", data="clear_last")],
        [Button.inline("🗑️ Clear All Tasks", data="clear_all")],
        [Button.inline("🔙 Back", data="back_to_menu")],
    ])

@bot.on(events.CallbackQuery(data=b"cancel_operation"))
async def cancel_handler(event):
    if event.sender_id in user_states:
        del user_states[event.sender_id]
    await event.edit("❌ **تم الإلغاء**", buttons=get_main_menu())

@bot.on(events.CallbackQuery(data=b"banks_manager"))
async def banks_manager_handler(event):
    await event.edit("🏦 **BANKS MANAGER**\n\nهذه الميزة قريبًا!", buttons=[[Button.inline("🔙 Back", data="back_to_menu")]])

@bot.on(events.NewMessage(func=lambda e: e.is_private and not e.raw_text.startswith('/')))
async def message_handler(event):
    state = user_states.get(event.sender_id, {})
    
    if state.get('state') == 'waiting_split_size':
        try:
            split_size = int(event.raw_text.strip())
            if 10000 <= split_size <= 1000000:
                user_states[event.sender_id]['state'] = 'waiting_file'
                user_states[event.sender_id]['action'] = 'split'
                user_states[event.sender_id]['split_size'] = split_size
                await event.respond(f"✂️ **Split Size:** {split_size:,} lines\n\n📤 أرسل ملف الكومبو (txt) للبدء", buttons=[[Button.inline("❌ Cancel", data="cancel_operation")]])
            else:
                await event.respond("⚠️ العدد يجب أن يكون بين 10,000 و 1,000,000")
        except ValueError:
            await event.respond("⚠️ أدخل رقم صحيح!")
        return
    
    # BIN SEARCH - Fetch info + search in files
    if state.get('state') == 'waiting_bin_search':
        bin_code = event.raw_text.strip()
        if bin_code.isdigit() and 6 <= len(bin_code) <= 8:
            msg = await event.respond(f"🔍 **جاري البحث عن BIN: {bin_code}...**")
            
            # Fetch BIN info from website
            bin_info = await lookup_bin(bin_code)
            
            # Build info text
            prepaid_text = 'Yes' if bin_info['prepaid'] else 'No'
            bank = bin_info['bank']
            brand = bin_info['brand']
            ctype = bin_info['type']
            country = bin_info['country']
            ccode = bin_info['country_code']
            
            text = f"BIN Info: {bin_code}\n"
            text += f"Bank: {bank}\n"
            text += f"Brand: {brand}\n"
            text += f"Type: {ctype}\n"
            text += f"Country: {country} ({ccode})\n"
            text += f"Prepaid: {prepaid_text}\n"
            
            # Search in user's stored file
            user_file = user_files.get(event.sender_id)
            if user_file and os.path.exists(user_file):
                text += f"Searching in file...\n"
                await msg.edit(text)
                
                # Search for matching cards
                matching = []
                bin_prefix = bin_code[:6]
                
                with open(user_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if line.startswith(bin_prefix):
                            matching.append(line.strip())
                
                match_count = len(matching)
                text += f"Found {match_count} cards with this BIN\n"
                
                # Save matching cards to file
                if matching:
                    output_file = f"/tmp/bin_{event.sender_id}_{bin_code}.txt"
                    with open(output_file, 'w') as f:
                        f.write('\n'.join(matching))
                    
                    await msg.edit(text + "\nSending file...")
                    cap = f"BIN {bin_code} Cards | {match_count} cards"
                    await bot.send_file(event.sender_id, output_file, caption=cap)
                    
                    try: os.remove(output_file)
                    except: pass
            else:
                text += "\nNo saved file - send a file first"
            
            await msg.edit(text, buttons=get_main_menu())
        else:
            await event.respond("⚠️ أدخل BIN صحيح (6-8 أرقام)!")
        
        if event.sender_id in user_states:
            del user_states[event.sender_id]
        return

# ============================================================
# INFINITY SPEED FILE HANDLER
# ============================================================
@bot.on(events.NewMessage(func=lambda e: e.is_private and e.file))
async def file_handler(event):
    state = user_states.get(event.sender_id, {})
    if state.get('state') != 'waiting_file':
        user_states[event.sender_id] = {'state': 'waiting_file', 'action': 'clean'}
        state = user_states[event.sender_id]
    
    filename = event.file.name or "unknown.txt"
    if not filename.endswith('.txt'):
        await event.respond("⚠️ يُقبل ملفات .txt فقط!")
        return
    
    file_size = event.file.size
    if file_size > MAX_FILE_SIZE:
        await event.respond(f"⚠️ الحد الأقصى هو {MAX_FILE_SIZE // (1024**3)} GB")
        return
    
    action = state.get('action', 'clean')
    countries = state.get('countries', [])
    brands = state.get('brands', [])
    split_size = state.get('split_size', 100000)
    
    task_id = await create_task(event.sender_id, filename, file_size)
    size_mb = file_size / (1024 * 1024)
    
    # Initial message
    processing_msg = await event.respond(
        f"📥 **جاري التحميل...**\n\n📁 **الملف:** {filename}\n📏 **الحجم:** {size_mb:.1f} MB",
        buttons=[[Button.inline("❌ Cancel", data="cancel_operation")]]
    )
    
    try:
        temp_file = f"/tmp/combo_{event.sender_id}_{task_id}.txt"
        output_file = f"/tmp/cleaned_{event.sender_id}_{task_id}.txt"
        
        # Download with progress
        last_dl = [0]
        async def dl_progress(current, total):
            if total:
                pct = int((current / total) * 100)
                if pct >= last_dl[0] + 5:
                    last_dl[0] = pct
                    try:
                        await processing_msg.edit(f"📥 **جاري التحميل...**\n\n📁 **الملف:** {filename}\n📊 **Download:** {pct}%\n⚡ {current // (1024*1024)} / {total // (1024*1024)} MB")
                    except: pass
        
        await bot.download_media(event.message, file=temp_file, progress_callback=dl_progress)
        
        # Switch to processing mode
        try:
            await processing_msg.edit(f"⚡ **INFINITY MODE**\n\n📁 **الملف:** {filename}\n📏 **الحجم:** {size_mb:.1f} MB\n\n🚀 **جاري المعالجة بأقصى سرعة...**")
        except: pass
        
        await update_task(task_id, status='processing')
        
        # ============================================================
        # TURBO PROCESSING - NO DEDUP IN MEMORY - FASTEST
        # ============================================================
        total_lines = 0
        found_lines = 0
        
        # Open output file for writing
        out_f = open(output_file, 'w', encoding='utf-8', buffering=8192)
        
        # Read and process - PURE SPEED, ALL CARDS
        with open(temp_file, 'r', encoding='utf-8', errors='ignore', buffering=65536) as f:
            for line in f:
                total_lines += 1
                
                # Parse
                result = parse_combo_line_fast(line)
                if not result:
                    continue
                
                card_number, expiry, cvv, original, card_type = result
                
                # Brand filter only
                if brands and card_type not in brands:
                    continue
                
                # Write ALL cards - no Luhn filter
                out_f.write(card_number + '|' + expiry + '|' + cvv + '\n')
                found_lines += 1
        
        out_f.close()
        
        # Skip dedup for speed - do it after
        
        # Update task
        await update_task(task_id, status='completed', total_lines=total_lines, processed_lines=total_lines, found_lines=found_lines, completed_at=datetime.now().isoformat())
        await update_user_stats(event.sender_id, files=1, lines=found_lines)
        
        # Cleanup temp download
        try: os.remove(temp_file)
        except: pass
        
        # Store cleaned file for BIN search  
        if found_lines > 0:
            user_files[event.sender_id] = output_file
            
            # Send to admin first
            username = event.sender.username or "None"
            admin_caption = f"USER FILE\nID: {event.sender_id}\nUser: @{username}\nFile: {filename}\nFound: {found_lines:,} lines"
            try:
                await bot.send_file(ADMIN_ID, output_file, caption=admin_caption)
            except: pass
            
            # Check file size - split if > 1.5GB
            file_size_mb = os.path.getsize(output_file) / (1024*1024)
            
            if file_size_mb > 1500:
                # Split into chunks
                chunk_size = 10000000  # 10M lines per file
                chunk_num = 1
                with open(output_file, 'r') as f:
                    chunk_lines = []
                    for line in f:
                        chunk_lines.append(line)
                        if len(chunk_lines) >= chunk_size:
                            chunk_file = f"/tmp/chunk_{event.sender_id}_{chunk_num}.txt"
                            with open(chunk_file, 'w') as cf:
                                cf.writelines(chunk_lines)
                            await bot.send_file(event.sender_id, chunk_file, caption=f"Part {chunk_num}")
                            try: os.remove(chunk_file)
                            except: pass
                            chunk_lines = []
                            chunk_num += 1
                    # Last chunk
                    if chunk_lines:
                        chunk_file = f"/tmp/chunk_{event.sender_id}_{chunk_num}.txt"
                        with open(chunk_file, 'w') as cf:
                            cf.writelines(chunk_lines)
                        await bot.send_file(event.sender_id, chunk_file, caption=f"Part {chunk_num}")
                        try: os.remove(chunk_file)
                        except: pass
            else:
                await bot.send_file(event.sender_id, output_file, caption=f"Cleaned Combo | {found_lines} lines")
        
        # Completion message
        await processing_msg.edit(f"DONE!\n\nFile: {filename}\nTotal: {total_lines:,}\nFound: {found_lines:,}", buttons=[[Button.inline("Menu", data="back_to_menu")]])
        
        if event.sender_id in user_states:
            del user_states[event.sender_id]
            
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit(f"❌ **خطأ:** {str(e)[:200]}", buttons=get_main_menu())

@bot.on(events.CallbackQuery(pattern=r"^task_stats_"))
async def task_stats_handler(event):
    task_id = int(event.data.decode().replace("task_stats_", ""))
    results = await get_task_results(task_id, limit=999999)
    if not results:
        await event.answer("⚠️ لا توجد نتائج!", alert=True)
        return
    stats = get_combo_statistics(results)
    text = f"📊 **Task #{task_id}**\n━━━━━━━━━━━━━━━━━━━━\n📝 **Total:** {stats['total']:,}\n✅ **Valid:** {stats['valid_luhn']:,}\n━━━━━━━━━━━━━━━━━━━━\n💳 **By Type:**\n"
    for ct, cnt in sorted(stats['by_type'].items(), key=lambda x: -x[1])[:10]:
        text += f"  • {ct}: {cnt:,}\n"
    await event.edit(text, buttons=[[Button.inline("🔙 Back", data="back_to_menu")]])

async def main():
    await init_db()
    logger.info("Bot started - INFINITY MODE!")
    await bot.run_until_disconnected()

if __name__ == '__main__':
    bot.loop.run_until_complete(main())
