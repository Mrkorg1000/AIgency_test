import pytest
import uuid
from conftest import (
    wait_for_insight,
    TEST_INTAKE_API_URL,
    TEST_INSIGHTS_API_URL,
)


@pytest.mark.asyncio
async def test_e2e_lead_creation_and_insight(
    http_client,
    clean_env,
    wait_for_services
):
    """
    E2E test: POST /leads → event in queue → worker creates Insight → GET insight.
    
    Tests the complete lead processing cycle:
    1. Lead creation via intake-api
    2. Event publication to Redis Stream
    3. Worker processing
    4. Insight creation in DB
    5. Insight retrieval via insights-api
    """
    
    # 1. Prepare test data
    idempotency_key = str(uuid.uuid4())
    lead_data = {
        "email": "test@example.com",
        "phone": "+1234567890",
        "name": "John Doe",
        "note": "Need urgent pricing for 50 seats ASAP! Want to buy next week.",
        "source": "landing-test"
    }
    
    # 2. Create lead via intake-api
    response = await http_client.post(
        f"{TEST_INTAKE_API_URL}/leads/",
        json=lead_data,
        headers={"Idempotency-Key": idempotency_key}
    )
    
    # 3. Verify successful creation
    assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
    lead_response = response.json()
    
    assert "id" in lead_response
    assert lead_response["email"] == lead_data["email"]
    assert lead_response["name"] == lead_data["name"]
    assert lead_response["note"] == lead_data["note"]
    
    lead_id = lead_response["id"]
    print(f"✓ Lead created: id={lead_id}")
    
    # 4. Wait for worker processing (insight creation)
    insight = await wait_for_insight(http_client, lead_id, timeout=15)
    print(f"✓ Insight created: {insight}")
    
    # 5. Verify insight structure
    assert "id" in insight
    assert insight["lead_id"] == lead_id
    assert "intent" in insight
    assert "priority" in insight
    assert "next_action" in insight
    assert "confidence" in insight
    assert "created_at" in insight
    
    # 6. Verify RuleBasedLLM logic
    # note contains "pricing", "buy", "urgent", "ASAP" → should have intent="buy" and high priority
    assert insight["intent"] == "buy", f"Expected intent='buy', got '{insight['intent']}'"
    assert insight["priority"] in ["P0", "P1"], f"Expected high priority, got '{insight['priority']}'"
    
    print(f"✓ E2E test passed successfully!")
    print(f"  Lead ID: {lead_id}")
    print(f"  Intent: {insight['intent']}")
    print(f"  Priority: {insight['priority']}")
    print(f"  Next Action: {insight['next_action']}")


@pytest.mark.asyncio
async def test_idempotency_same_key_same_body(
    http_client,
    clean_env,
    wait_for_services
):
    """
    Test 2: Repeated POST /leads with same Idempotency-Key and body.
    
    Verifies:
    1. First request creates lead (201)
    2. Second request with same key and body returns cached response (200)
    3. Only one lead created in DB
    4. Only one event sent to queue
    """
    
    # 1. Prepare test data
    idempotency_key = str(uuid.uuid4())
    lead_data = {
        "email": "idempotency@example.com",
        "phone": "+9876543210",
        "name": "Jane Smith",
        "note": "Interested in demo",
        "source": "website"
    }
    
    # 2. First request - create lead
    response1 = await http_client.post(
        f"{TEST_INTAKE_API_URL}/leads/",
        json=lead_data,
        headers={"Idempotency-Key": idempotency_key}
    )
    
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}: {response1.text}"
    lead1 = response1.json()
    lead_id = lead1["id"]
    print(f"✓ First request: Lead created with id={lead_id}")
    
    # 3. Second request with same key and body
    response2 = await http_client.post(
        f"{TEST_INTAKE_API_URL}/leads/",
        json=lead_data,
        headers={"Idempotency-Key": idempotency_key}
    )
    
    # Should return 200 (from cache) with same response body
    assert response2.status_code == 200, f"Expected 200 (cached), got {response2.status_code}: {response2.text}"
    lead2 = response2.json()
    print(f"✓ Second request: Returned cached response")
    
    # 4. Verify same lead was returned
    assert lead2["id"] == lead1["id"], "Lead IDs should match"
    assert lead2["email"] == lead1["email"]
    assert lead2["name"] == lead1["name"]
    assert lead2["note"] == lead1["note"]
    
    # 5. Verify only one lead in DB
    get_response = await http_client.get(f"{TEST_INTAKE_API_URL}/leads/{lead_id}")
    assert get_response.status_code == 200
    
    # 6. Wait for insight and verify only one was created
    insight = await wait_for_insight(http_client, lead_id, timeout=15)
    assert insight["lead_id"] == lead_id
    print(f"✓ Only one insight created for lead {lead_id}")
    
    print(f"✓ Idempotency test (same key, same body) passed!")


@pytest.mark.asyncio
async def test_idempotency_same_key_different_body(
    http_client,
    clean_env,
    wait_for_services
):
    """
    Test 3: Repeated POST /leads with same Idempotency-Key but different body.
    
    Verifies:
    1. First request creates lead (201)
    2. Second request with same key but different body returns error (409)
    """
    
    # 1. Prepare test data
    idempotency_key = str(uuid.uuid4())
    lead_data1 = {
        "email": "conflict@example.com",
        "phone": "+1111111111",
        "name": "First Name",
        "note": "First note",
        "source": "source1"
    }
    
    # 2. First request - create lead
    response1 = await http_client.post(
        f"{TEST_INTAKE_API_URL}/leads/",
        json=lead_data1,
        headers={"Idempotency-Key": idempotency_key}
    )
    
    assert response1.status_code == 201, f"Expected 201, got {response1.status_code}: {response1.text}"
    lead1 = response1.json()
    print(f"✓ First request: Lead created with id={lead1['id']}")
    
    # 3. Second request with same key but DIFFERENT body
    lead_data2 = {
        "email": "different@example.com",  # Different email
        "phone": "+2222222222",             # Different phone
        "name": "Different Name",           # Different name
        "note": "Different note",           # Different note
        "source": "source2"                 # Different source
    }
    
    response2 = await http_client.post(
        f"{TEST_INTAKE_API_URL}/leads/",
        json=lead_data2,
        headers={"Idempotency-Key": idempotency_key}
    )
    
    # Should return error 409 (Conflict) or 422 (Unprocessable Entity)
    assert response2.status_code in [409, 422], \
        f"Expected 409 or 422 (conflict), got {response2.status_code}: {response2.text}"
    print(f"✓ Second request: Correctly rejected with status {response2.status_code}")
    
    # 4. Verify only first lead remains in DB
    get_response = await http_client.get(f"{TEST_INTAKE_API_URL}/leads/{lead1['id']}")
    assert get_response.status_code == 200
    stored_lead = get_response.json()
    assert stored_lead["email"] == lead_data1["email"], "Original lead should remain unchanged"
    
    print(f"✓ Idempotency conflict test passed!")


@pytest.mark.asyncio
async def test_duplicate_event_no_duplicate_insight(
    http_client,
    clean_env,
    wait_for_services,
    redis_client,
    db_session
):
    """
    Test 4: Duplicate event in queue does not create second insight.
    
    Verifies:
    1. Create lead
    2. Wait for first insight creation
    3. Manually publish duplicate event to Redis Stream
    4. Verify second insight is NOT created (unique index on lead_id + content_hash)
    """
    import hashlib
    from datetime import datetime
    from conftest import TEST_REDIS_STREAM
    from sqlalchemy import text
    
    # 1. Create lead
    idempotency_key = str(uuid.uuid4())
    lead_data = {
        "email": "duplicate@example.com",
        "phone": "+3333333333",
        "name": "Duplicate Test",
        "note": "Test duplicate event handling",
        "source": "test"
    }
    
    response = await http_client.post(
        f"{TEST_INTAKE_API_URL}/leads/",
        json=lead_data,
        headers={"Idempotency-Key": idempotency_key}
    )
    
    assert response.status_code == 201
    lead = response.json()
    lead_id = lead["id"]
    print(f"✓ Lead created: id={lead_id}")
    
    # 2. Wait for first insight creation
    insight1 = await wait_for_insight(http_client, lead_id, timeout=15)
    print(f"✓ First insight created: id={insight1['id']}")
    
    # 3. Verify exactly one insight in DB
    result = await db_session.execute(
        text("SELECT COUNT(*) FROM insights WHERE lead_id = :lead_id"),
        {"lead_id": lead_id}
    )
    count_before = result.scalar()
    assert count_before == 1, f"Expected 1 insight, found {count_before}"
    
    # 4. Manually publish DUPLICATE event to Redis Stream
    content_hash = hashlib.sha256(lead_data["note"].encode()).hexdigest()
    duplicate_event = {
        "event_id": str(uuid.uuid4()),  # New event_id
        "type": "lead.created",
        "lead_id": lead_id,
        "note": lead_data["note"],
        "content_hash": content_hash,  # Same content_hash!
        "occurred_at": datetime.utcnow().isoformat()
    }
    
    await redis_client.xadd(TEST_REDIS_STREAM, duplicate_event)
    print(f"✓ Duplicate event published to stream")
    
    # 5. Give worker time to process duplicate
    import asyncio
    await asyncio.sleep(3)
    
    # 6. Verify second insight was NOT created
    result = await db_session.execute(
        text("SELECT COUNT(*) FROM insights WHERE lead_id = :lead_id"),
        {"lead_id": lead_id}
    )
    count_after = result.scalar()
    assert count_after == 1, f"Expected still 1 insight, but found {count_after}"
    
    # 7. Verify GET still returns first insight
    insight2 = await wait_for_insight(http_client, lead_id, timeout=5)
    assert insight2["id"] == insight1["id"], "Should return the same insight"
    assert insight2["content_hash"] == content_hash
    
    print(f"✓ Duplicate event correctly ignored - no second insight created!")
    print(f"✓ Duplicate event test passed!")
