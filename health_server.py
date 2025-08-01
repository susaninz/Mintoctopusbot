"""
HTTP сервер для health checks в production
"""
import asyncio
import json
from aiohttp import web
from health_check import health_checker
import logging

logger = logging.getLogger(__name__)

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

async def root_endpoint(request):
    """Root endpoint"""
    return web.json_response({
        "service": "Mintoctopus Bot",
        "status": "running",
        "version": "1.0.0"
    })

async def create_health_app():
    """Создает aiohttp приложение для health checks"""
    app = web.Application()
    app.router.add_get('/health', health_endpoint)
    app.router.add_get('/', root_endpoint)
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