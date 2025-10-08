import asyncio
import signal
from typing import Dict, Any

import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from common.config import settings
from processor import MessageProcessor


# Global variables for graceful shutdown
shutdown_event = asyncio.Event()

WORKER_NAMES = ["triage_worker_1", "triage_worker_2"]


async def ack_successful_messages(
    redis_client,
    stream_name: str,
    group_name: str,
    msg_ids: list[str],
    results: list[bool]
):
    """
    Acknowledges only successfully processed messages in Redis.
    
    Args:
        redis_client: Redis client instance
        stream_name: Redis stream name
        group_name: Consumer group name
        msg_ids: List of message IDs
        results: List of processing results (True/False)
    """
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
    Processes a single message from the queue.
    
    Args:
        processor: Message processor instance
        message_data: Message data to process
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        return await processor.process_message(message_data)
    except Exception as e:
        import traceback
        print(f"[triage_worker] Error processing message: {e}")
        traceback.print_exc()
        return False
    
    
async def _process_with_semaphore(
    processor: MessageProcessor,
    message_data: Dict[str, Any],
    semaphore: asyncio.Semaphore
):
    """
    Processes message with concurrency control via semaphore.
    
    Args:
        processor: Message processor instance
        message_data: Message data to process
        semaphore: Semaphore for concurrency control
        
    Returns:
        bool: Processing result
    """
    async with semaphore:
        return await process_single_message(processor, message_data)


async def main_loop(consumer_name: str):
    """
    Main message processing loop.
    
    Args:
        consumer_name: Name of this consumer instance
    """
    print(f"[triage_worker] Starting consumer={consumer_name}")
    print(f"[triage_worker] Config: stream={settings.REDIS_STREAM} "
          f"group={settings.REDIS_CONSUMER_GROUP} batch={settings.BATCH_SIZE}")
    
    # Connect to Redis
    redis_client = redis.from_url(
        settings.REDIS_URL,
        decode_responses=True
    )
    
    # Connect to database
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    # Create consumer group if it doesn't exist
    try:
        await redis_client.xgroup_create(
            name=settings.REDIS_STREAM,
            groupname=settings.REDIS_CONSUMER_GROUP,
            id="0-0",
            mkstream=True
        )
        print(f"[triage_worker] Consumer group created: {settings.REDIS_CONSUMER_GROUP}")
    except redis.ResponseError as e:
        if "BUSYGROUP" in str(e):
            print(f"[triage_worker] Consumer group already exists")
    
    semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT_REQUESTS)
    
    await asyncio.sleep(0.1)

    while not shutdown_event.is_set():
        try:
            async with async_session() as session:
                processor = MessageProcessor(redis_client, session)
                
                # Claim pending messages (for reliability)
                try:
                    pending_messages = await redis_client.xautoclaim(
                        name=settings.REDIS_STREAM,
                        groupname=settings.REDIS_CONSUMER_GROUP,
                        consumername=consumer_name,
                        min_idle_time=1000,  # 1 second to quickly reclaim stuck messages
                        start_id="0-0",
                        count=settings.BATCH_SIZE
                    )
                    pending_msgs_list = pending_messages[1] if pending_messages else []
                except redis.ResponseError:
                    # Group not ready or stream doesn't exist yet
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
                
                # Read new messages
                read_id = ">"
                messages = await redis_client.xreadgroup(
                    groupname=settings.REDIS_CONSUMER_GROUP,
                    consumername=consumer_name,
                    streams={settings.REDIS_STREAM: read_id},
                    count=settings.BATCH_SIZE,
                    block=settings.STREAM_BLOCK_TIME
                )
                
                if messages:
                    total = sum(len(message_list) for _, message_list in messages)
                    if total > 0:
                        print(f"[triage_worker] Processing {total} new messages")
                        tasks = []
                        msg_ids = []
                        for _, message_list in messages:
                            for message_id, message_data in message_list:
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

            await asyncio.sleep(0.1)
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            import traceback
            print(f"[triage_worker] Loop exception: {e}")
            traceback.print_exc()
            await asyncio.sleep(5)
    
    # Cleanup
    await redis_client.close()
    await engine.dispose()
    print(f"[triage_worker] Consumer {consumer_name} stopped")


def handle_shutdown(signum, frame):
    """
    Signal handler for graceful shutdown.
    
    Args:
        signum: Signal number
        frame: Current stack frame
    """
    print("[triage_worker] Shutdown signal received")
    shutdown_event.set()


async def main():
    """Main entry point - starts all worker instances."""
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    tasks = [asyncio.create_task(main_loop(name)) for name in WORKER_NAMES]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())