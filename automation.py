# automation.py - Модуль автоматизации

import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import AUTO_SELL_DAYS, CHECK_INTERVAL, ADMIN_IDS
from database import db
from models import Product, Order, AutoSellCampaign

logger = logging.getLogger(__name__)

class AutoSellEngine:
    def __init__(self, bot):
        self.bot = bot
        self.is_running = False
        self.active_campaigns = {}
        
    async def start(self):
        self.is_running = True
        logger.info("🚀 Движок автоматизации запущен")
        
        while self.is_running:
            try:
                await self.process_campaigns()
                await asyncio.sleep(CHECK_INTERVAL)
            except Exception as e:
                logger.error(f"❌ Ошибка в движке автоматизации: {e}")
                await asyncio.sleep(60)
    
    async def stop(self):
        self.is_running = False
        logger.info("⏹️ Движок автоматизации остановлен")
    
    async def process_campaigns(self):
        campaigns = db.get_active_campaigns()
        
        for campaign in campaigns:
            campaign_id = campaign['id']
            
            started_at = datetime.fromisoformat(campaign['started_at'])
            days_passed = (datetime.now() - started_at).days
            
            if days_passed >= campaign['days']:
                await self.end_campaign(campaign_id)
                continue
            
            await self.process_campaign_products(campaign)
    
    async def process_campaign_products(self, campaign: Dict):
        campaign_id = campaign['id']
        products = db.get_products_by_campaign(campaign_id)
        
        for product in products:
            product_age = random.randint(1, 5)
            
            if product_age >= 3 and product.in_stock:
                await self.simulate_activity(product.id)
            
            if product.in_stock and random.random() < 0.1:
                await self.simulate_purchase(product, campaign_id)
    
    async def simulate_activity(self, product_id: int):
        action = random.choice(['hide', 'show', 'change_price'])
        
        if action == 'hide':
            db.update_product_stock(product_id, False)
            logger.info(f"🔒 Товар {product_id} скрыт (имитация)")
            asyncio.create_task(self.restore_product_after_delay(product_id))
        elif action == 'show':
            db.update_product_stock(product_id, True)
            logger.info(f"🔓 Товар {product_id} показан (имитация)")
        elif action == 'change_price':
            products = db.get_all_products()
            product = next((p for p in products if p['id'] == product_id), None)
            if product:
                old_price = product['price']
                new_price = int(old_price * random.uniform(0.9, 1.1))
                logger.info(f"💰 Цена товара {product_id}: {old_price} → {new_price} (имитация)")
    
    async def restore_product_after_delay(self, product_id: int):
        delay = random.randint(1800, 7200)
        await asyncio.sleep(delay)
        db.update_product_stock(product_id, True)
        logger.info(f"🔓 Товар {product_id} восстановлен после имитации")
    
    async def simulate_purchase(self, product: Product, campaign_id: int):
        fake_user_id = random.randint(100000000, 999999999)
        
        product_code = product.product_code if product.product_code else 'AUTO'
        
        order = Order(
            user_id=fake_user_id,
            product_name=product.name,
            city=product.city,
            quantity=product.quantity,
            price=product.price,
            created_at=datetime.now(),
            product_code=product_code,
            is_auto=True
        )
        
        db.add_order(order)
        db.update_product_stock(product.id, False)
        
        campaign = db.get_campaign_by_id(campaign_id)
        if campaign:
            db.update_campaign_stats(
                campaign_id,
                campaign['sold_count'] + 1,
                campaign['total_revenue'] + product.price
            )
        
        for admin_id in ADMIN_IDS:
            if db.is_user_blocked(admin_id):
                continue
            try:
                await self.bot.send_message(
                    admin_id,
                    f"🤖 АВТО-ПРОДАЖА\n"
                    f"Товар: {product.name}\n"
                    f"Город: {product.city}\n"
                    f"Количество: {product.quantity}\n"
                    f"Цена: {product.price}₽\n"
                    f"🔑 Код: <code>/{product_code}</code>\n"
                    f"Кампания: {campaign_id}",
                    parse_mode='HTML'
                )
            except:
                pass
        
        logger.info(f"🤖 Имитация покупки: {product.name} - {product.price}₽, код: {product_code}")
    
    async def end_campaign(self, campaign_id: int):
        db.end_campaign(campaign_id)
        logger.info(f"🏁 Кампания {campaign_id} завершена")
        
        products = db.get_products_by_campaign(campaign_id)
        for product in products:
            db.update_product_stock(product.id, False)
        
        for admin_id in ADMIN_IDS:
            if db.is_user_blocked(admin_id):
                continue
            try:
                await self.bot.send_message(
                    admin_id,
                    f"🏁 Кампания завершена!\n"
                    f"ID: {campaign_id}\n"
                    f"Все товары скрыты."
                )
            except:
                pass
    
    async def create_campaign_from_data(self, data: Dict):
        campaign = AutoSellCampaign(
            id=0,
            name=data['name'],
            cities=data['cities'],
            products=data['products'],
            quantities=data['quantities'],
            prices=data['prices'],
            days=data['days'],
            started_at=datetime.now(),
            is_active=True
        )
        
        campaign_id = db.create_auto_campaign(campaign)
        added_products = []
        
        for city in data['cities']:
            for idx, product_name in enumerate(data['products']):
                for quantity in data['quantities']:
                    product = Product(
                        city=city,
                        name=product_name,
                        quantity=quantity,
                        price=data['prices'][idx] if idx < len(data['prices']) else 0,
                        in_stock=True
                    )
                    db.add_product_with_campaign(product, campaign_id)
                    added_products.append(product)
        
        for product in added_products:
            await self.notify_about_new_product(product)
            await asyncio.sleep(0.1)
        
        logger.info(f"✅ Создана кампания {campaign_id} с {len(added_products)} товарами")
        return campaign_id

    async def notify_about_new_product(self, product: Product):
        users = db.get_all_users()
        
        text = f"""✅ <b>Новый товар!</b>

📍 {product.city} - {product.name} - {product.quantity} - {product.price}₽ - ✅ В наличии

🔑 Код товара: <code>/{product.product_code}</code>

💡 Нажмите на код, чтобы быстро перейти к товару"""
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔑 Перейти к товару /{product.product_code}",
                callback_data=f"goto_product_{product.product_code}"
            )]
        ])
        
        for user_id in users:
            if db.is_user_blocked(user_id):
                continue
            try:
                await self.bot.send_message(
                    user_id,
                    text,
                    parse_mode='HTML',
                    reply_markup=keyboard
                )
                await asyncio.sleep(0.05)
            except:
                pass

auto_engine = None

def init_auto_engine(bot):
    global auto_engine
    auto_engine = AutoSellEngine(bot)
    return auto_engine