import asyncio
import signal
from typing import Dict, Any

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.config import settings
from processor import MessageProcessor


# Глобальные переменные для graceful shutdown
shutdown_event = asyncio.Event()


WORKER_NAMES = ["triage_worker_1", "triage_worker_2"]


async def ack_successful_messages(
    redis_client,
    stream_name: str,
    group_name: str,
    msg_ids: list[str],
    results: list[bool]
):
    """Подтверждает в Redis только успешно обработанные сообщения"""
    for i, message_id in enumerate(msg_ids):
        if results[i]:
            await redis_client.xack(
                stream_name,
                group_name,
                message_id
            )


async def process_single_message(
    processor: MessageProcessor,
    message_data: Dict[str, Any]
) -> bool:
    """
    Обрабатывает одно сообщение из очереди.
    """
    try:
        return await processor.process_message(message_data)
        
    except Exception as e:
        import traceback
        print(f"[triage_worker] Error while processing message: {e} message={message_data}")
        traceback.print_exc()
        return False
    
    
async def _process_with_semaphore(
    processor: MessageProcessor,
    message_data: Dict[str, Any],
    semaphore: asyncio.Semaphore
):
    async with semaphore:
        return await process_single_message(processor, message_data)



async def main_loop(consumer_name: str):
    """Основной цикл обработки сообщений"""
    print(f"[triage_worker] Starting consumer={consumer_name} with config: "
          f"REDIS_URL={settings.REDIS_URL} REDIS_STREAM={settings.REDIS_STREAM} "
          f"GROUP={settings.REDIS_CONSUMER_GROUP} BATCH_SIZE={settings.BATCH_SIZE} "
          f"BLOCK={settings.STREAM_BLOCK_TIME}")
    # Подключаемся к Redis через URL
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True
    )
    
    # Подключаемся к БД
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Создаем группу потребителей если её нет
    try:
        await redis_client.xgroup_create(
            name=settings.REDIS_STREAM,
            groupname=settings.REDIS_CONSUMER_GROUP,
            id="0-0",
            mkstream=True
        )
        print(f"[triage_worker] Consumer group created: stream={settings.REDIS_STREAM} group={settings.REDIS_CONSUMER_GROUP}")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"[triage_worker] Consumer group already exists: stream={settings.REDIS_STREAM} group={settings.REDIS_CONSUMER_GROUP}")
    
    semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)
    
    await asyncio.sleep(0.1)

    while not shutdown_event.is_set():
        try:
            async with async_session() as session:
                processor = MessageProcessor(redis_client, session)
                
                # Подхватываем зависшие сообщения
                print(f"[triage_worker] Attempting XAUTOCLAIM for pending messages...")
                try:
                    pending_messages = await redis_client.xautoclaim(
                        name=settings.REDIS_STREAM,
                        groupname=settings.REDIS_CONSUMER_GROUP,
                        consumername=consumer_name,
                        min_idle_time=1000,  # 1 секунда, чтобы быстрее подхватывать зависшие
                        start_id="0-0",
                        count=settings.BATCH_SIZE
                    )
                    pending_msgs_list = pending_messages[1] if pending_messages else []
                except redis.ResponseError as e:
                    # Группа ещё не готова или stream не существует
                    print(f"[triage_worker] XAUTOCLAIM failed (expected on first run): {e}")
                    pending_msgs_list = []  
                if pending_msgs_list:
                    print(f"[triage_worker] Claimed {len(pending_msgs_list)} pending messages")
                    tasks = [
                        _process_with_semaphore(processor, msg_data, semaphore)
                        for msg_id, msg_data in pending_msgs_list
                    ]
                    results = await asyncio.gather(*tasks)
                    pending_ids = [msg_id for msg_id, _ in pending_msgs_list]
                    await ack_successful_messages(
                        redis_client,
                        settings.REDIS_STREAM,
                        settings.REDIS_CONSUMER_GROUP,
                        pending_ids,
                        results
                    )
                # Читаем только новые сообщения
                read_id = ">"
                print(f"[triage_worker] Waiting for messages on stream={settings.REDIS_STREAM} group={settings.REDIS_CONSUMER_GROUP} consumer={consumer_name}")
                messages = await redis_client.xreadgroup(
                    groupname=settings.REDIS_CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams={settings.REDIS_STREAM: read_id},
                    count=settings.BATCH_SIZE,
                    block=settings.STREAM_BLOCK_TIME
                )
                
                if messages:
                    total = sum(len(message_list) for _, message_list in messages)
                    print(f"[triage_worker] Received {total} messages")
                    if total > 0:
                        tasks = []
                        msg_ids = []
                        for _, message_list in messages:
                            for message_id, message_data in message_list:
                                print(f"[triage_worker] Handling msg_id={message_id} data={message_data}")
                                tasks.append(_process_with_semaphore(processor, message_data, semaphore))
                                msg_ids.append(message_id)

                        results = await asyncio.gather(*tasks)
                        await ack_successful_messages(
                            redis_client,
                            settings.REDIS_STREAM,
                            settings.REDIS_CONSUMER_GROUP,
                            msg_ids,
                            results
                        )
                    else:
                        print(f"[triage_worker] Empty batch (no inner messages)")
                else:
                    print(f"[triage_worker] No new messages, continuing...")

            # После первой успешной попытки чтения переключаемся на новые сообщения
            # from_start = False
            # Небольшая пауза между итераций
            await asyncio.sleep(0.1)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            import traceback
            print(f"[triage_worker] Loop exception: {e}")
            traceback.print_exc()
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
    
    tasks = [asyncio.create_task(main_loop(name)) for name in WORKER_NAMES]
    await asyncio.gather(*tasks)

    # try:
    #     await main_loop()
    # except KeyboardInterrupt:
    #     pass


if __name__ == "__main__":
    asyncio.run(main())