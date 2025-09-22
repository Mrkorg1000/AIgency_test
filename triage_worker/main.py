import asyncio
import signal
from typing import Dict, Any

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from triage_worker.config.config import settings
from triage_worker.processor import MessageProcessor


# Глобальные переменные для graceful shutdown
shutdown_event = asyncio.Event()


async def process_single_message(
    processor: MessageProcessor,
    message_data: Dict[str, Any]  # Только данные сообщения
) -> bool:
    """
    Обрабатывает одно сообщение из очереди.
    Возвращает True если сообщение успешно обработано.
    """
    try:
        success = await processor.process_message(message_data)
        return success
        
    except Exception:
        return False


async def main_loop():
    """Основной цикл обработки сообщений"""
    # Подключаемся к Redis через URL
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=False
    )
    
    # Подключаемся к БД
    engine = create_async_engine(settings.DATABASE_URL, echo=settings.DB_ECHO)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Создаем группу потребителей если её нет
    try:
        await redis_client.xgroup_create(
            name=settings.REDIS_STREAM,
            groupname=settings.REDIS_CONSUMER_GROUP,
            id="$",
            mkstream=True
        )
    except redis.ResponseError:
        # Группа уже существует - это нормально
        pass
    
    while not shutdown_event.is_set():
        try:
            # Читаем сообщения из стрима
            messages = await redis_client.xreadgroup(
                groupname=settings.REDIS_CONSUMER_GROUP,
                consumername=settings.REDIS_CONSUMER_NAME,
                streams={settings.REDIS_STREAM: ">"},
                count=settings.BATCH_SIZE,
                block=settings.STREAM_BLOCK_TIME
            )
            
            if not messages:
                continue
            
            # Обрабатываем батч сообщений
            async with async_session() as session:
                processor = MessageProcessor(redis_client, session)
                
                for _, message_list in messages:
                    for message_id, message_data in message_list:
                        success = await process_single_message(
                            processor, message_data
                        )
                        
                        if success:
                            # Подтверждаем обработку сообщения
                            await redis_client.xack(
                                settings.REDIS_STREAM,
                                settings.REDIS_CONSUMER_GROUP,
                                message_id
                            )
            
            # Небольшая пауза между итераций
            await asyncio.sleep(0.1)
            
        except asyncio.CancelledError:
            break
        except Exception:
            await asyncio.sleep(5)
    
    # Завершаем работу
    await redis_client.close()
    await engine.dispose()


def handle_shutdown(signum, frame):
    """Обработчик сигналов завершения"""
    shutdown_event.set()


async def main():
    """Главная функция"""
    # Регистрируем обработчики сигналов
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    try:
        await main_loop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    asyncio.run(main())