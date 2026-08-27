# main.py - Запуск бота (ПОЛНАЯ ВЕРСИЯ)

import asyncio
import logging
import sys
import os
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeChat
from config import BOT_TOKEN, AUTO_SELL_ENABLED, BACKUP_ENABLED, BACKUP_INTERVAL, ADMIN_IDS

from handlers import router
from utils import proxy_rotator
from automation import init_auto_engine
from database import db

logging.basicConfig(level=logging.INFO, stream=sys.stdout)
logger = logging.getLogger(__name__)

backup_task = None

async def auto_backup_worker():
    """Фоновый процесс для автоматического создания бекапов"""
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
    """Настраивает команды для разных пользователей"""
    
    # ТОЛЬКО /start для обычных пользователей
    user_commands = [
        BotCommand(command="start", description="Запустить бота"),
    ]
    
    # ВСЕ КОМАНДЫ для админов
    admin_commands = [
        BotCommand(command="start", description="Запустить бота"),
        BotCommand(command="code", description="Найти товар по коду"),
        BotCommand(command="backup", description="Создать резервную копию"),
        BotCommand(command="backup_list", description="Список резервных копий"),
    ]
    
    # Устанавливаем команды для всех пользователей (только /start)
    await bot.set_my_commands(user_commands, scope=BotCommandScopeDefault())
    
    # Устанавливаем ВСЕ команды для каждого админа
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
    """Действия при запуске бота"""
    logger.info("🚀 Бот запускается...")
    
    # Проверяем существование базы данных
    if not os.path.exists('bot.db'):
        logger.info("📁 Создание новой базы данных...")
        db.init_db()
        logger.info("✅ Новая база данных создана")
    else:
        logger.info("✅ База данных уже существует, данные сохранены")
        db.init_db()
    
    logger.info("✅ База данных готова")
    
    # Настройка команд для разных пользователей
    await setup_commands(bot)
    
    # Запускаем автоматический бекап
    global backup_task
    if BACKUP_ENABLED:
        logger.info(f"💾 Автоматический бекап включен (интервал: {BACKUP_INTERVAL} сек.)")
        backup_task = asyncio.create_task(auto_backup_worker())
    else:
        logger.info("💾 Автоматический бекап отключен")

async def main():
    """Главная функция запуска бота"""
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    if proxy_rotator.proxies:
        first_proxy = proxy_rotator.proxies[0]
        logger.info(f"🌐 Using proxy: {first_proxy}")
    
    auto_engine = init_auto_engine(bot)
    
    dp = Dispatcher()
    dp.include_router(router)
    
    await on_startup(bot)
    
    if AUTO_SELL_ENABLED:
        logger.info("🚀 Запуск движка автоматизации...")
        asyncio.create_task(auto_engine.start())
    
    try:
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"❌ Error: {e}")
    finally:
        # Останавливаем задачу бекапа
        global backup_task
        if backup_task:
            backup_task.cancel()
            try:
                await backup_task
            except asyncio.CancelledError:
                pass
        
        if AUTO_SELL_ENABLED:
            await auto_engine.stop()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())