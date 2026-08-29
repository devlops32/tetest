# main.py - Запуск бота (ОБНОВЛЕННЫЙ)

import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from config import BOT_TOKEN, AUTO_SELL_ENABLED, BACKUP_ENABLED, BACKUP_INTERVAL, ADMIN_IDS

from handlers import router as user_router
from admin_handlers import router as admin_router
from admin_products_handlers import router as admin_products_router
from utils import proxy_rotator
from automation import init_auto_engine
from database import db

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

backup_task = None

async def auto_backup_worker():
    logger.info("💾 Запущен автоматический бекап...")
    while True:
        try:
            await asyncio.sleep(BACKUP_INTERVAL)
            
            backup_path = db.create_backup()
            if backup_path:
                logger.info(f"💾 Автоматический бекап создан: {backup_path}")
            else:
                logger.warning("⚠️ Не удалось создать автоматический бекап")
                
        except asyncio.CancelledError:
            logger.info("⏹️ Автоматический бекап остановлен")
            break
        except Exception as e:
            logger.error(f"❌ Ошибка в автоматическом бекапе: {e}")
            await asyncio.sleep(60)

async def setup_commands(bot: Bot):
    user_commands = [
        BotCommand(command="start", description="Запустить бота"),
    ]
    
    admin_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="code", description="Найти товар по коду"),
        BotCommand(command="backup", description="Создать резервную копию"),
        BotCommand(command="backup_list", description="Список резервных копий"),
    ]
    
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    
    for admin_id in ADMIN_IDS:
        try:
            await bot.set_my_commands(
                admin_commands,
                scope=BotCommandScopeChat(chat_id=admin_id)
            )
            logger.info(f"👤 Команды для админа {admin_id} установлены")
        except Exception as e:
            logger.error(f"❌ Ошибка установки команд для админа {admin_id}: {e}")

async def on_startup(bot: Bot):
    logger.info("🚀 Бот запускается...")
    
    if not os.path.exists('bot.db'):
        logger.info("📁 Создание новой базы данных...")
        db.init_db()
        logger.info("✅ Новая база данных создана")
    else:
        logger.info("✅ База данных уже существует, данные сохранены")
        db.init_db()
    
    logger.info("✅ База данных готова")
    
    await setup_commands(bot)
    
    global backup_task
    if BACKUP_ENABLED:
        logger.info(f"💾 Автоматический бекап включен (интервал: {BACKUP_INTERVAL} сек.)")
        backup_task = asyncio.create_task(auto_backup_worker())
    else:
        logger.info("💾 Автоматический бекап отключен")

async def main():
    if not BOT_TOKEN or BOT_TOKEN == "ВАШ_ТОКЕН_БОТА_СЮДА":
        logger.error("❌ ОШИБКА: Токен бота не настроен!")
        logger.error("📝 Отредактируйте config.py и вставьте правильный токен")
        return
    
    try:
        bot = Bot(
            token=BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
    except Exception as e:
        logger.error(f"❌ Ошибка создания бота: {e}")
        return
    
    if proxy_rotator.proxies:
        first_proxy = proxy_rotator.proxies[0]
        logger.info(f"🌐 Using proxy: {first_proxy}")
    
    auto_engine = init_auto_engine(bot)
    
    dp = Dispatcher()
    dp.include_router(user_router)
    dp.include_router(admin_router)
    dp.include_router(admin_products_router)
    
    await on_startup(bot)
    
    if AUTO_SELL_ENABLED:
        logger.info("🚀 Запуск движка автоматизации...")
        asyncio.create_task(auto_engine.start())
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        global backup_task
        if backup_task:
            backup