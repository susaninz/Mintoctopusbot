"""
HTTP сервер для health checks и webhook в production
"""
import asyncio
import json
from aiohttp import web
from health_check import health_checker
import logging
from telegram import Update

logger = logging.getLogger(__name__)

# Глобальная переменная для доступа к Telegram Application
telegram_application = None

async def health_endpoint(request):
    """Health check endpoint для Fly.io"""
    try:
        if health_checker:
            health_status = await health_checker.full_health_check()
            
            if health_status.get("overall_status") == "healthy":
                return web.json_response(health_status, status=200)
            else:
                return web.json_response(health_status, status=503)
        else:
            return web.json_response({
                "status": "unhealthy",
                "error": "Health checker not initialized"
            }, status=503)
            
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return web.json_response({
            "status": "error",
            "error": str(e)
        }, status=500)

async def webhook_endpoint(request):
    """Обработчик webhook от Telegram"""
    try:
        if not telegram_application:
            logger.error("Telegram application not initialized")
            return web.json_response({"error": "Bot not ready"}, status=503)
            
        # Получаем JSON данные от Telegram
        data = await request.json()
        logger.debug(f"Received webhook data: {data}")
        
        # Создаем Update объект из полученных данных
        update = Update.de_json(data, telegram_application.bot)
        
        if update:
            # Обрабатываем update через application
            await telegram_application.process_update(update)
            return web.json_response({"status": "ok"})
        else:
            logger.warning("Failed to parse webhook update")
            return web.json_response({"error": "Invalid update"}, status=400)
            
    except Exception as e:
        logger.error(f"Webhook processing error: {e}")
        return web.json_response({"error": str(e)}, status=500)

async def root_endpoint(request):
    """Root endpoint"""
    return web.json_response({
        "service": "Mintoctopus Bot",
        "status": "running",
        "version": "1.0.0"
    })

def set_telegram_application(application):
    """Устанавливает ссылку на Telegram Application"""
    global telegram_application
    telegram_application = application

async def create_health_app():
    """Создает aiohttp приложение для health checks и webhook"""
    app = web.Application()
    app.router.add_get('/health', health_endpoint)
    app.router.add_get('/', root_endpoint)
    app.router.add_post('/webhook', webhook_endpoint)  # Правильный webhook endpoint
    return app

async def start_health_server(port=8080):
    """Запускает health check сервер"""
    app = await create_health_app()
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    
    logger.info(f"Health check server started on port {port}")
    return runner