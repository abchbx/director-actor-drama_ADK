---
phase: 14
phase_slug: websocket-layer
created: "2026-04-15"
sampling_rate: per-task
framework: pytest + pytest-asyncio
---

# Phase 14 Validation Strategy: WebSocket Layer

## Phase Requirements → Test Map

| Req ID | Requirement | Test Type | Test Command | Wave 0 Status |
|--------|-------------|-----------|--------------|---------------|
| WS-01 | WS endpoint at /api/v1/ws receives real-time scene events | unit | `uv run pytest tests/unit/test_ws_manager.py::test_ws_endpoint -x` | ❌ Wave 0 |
| WS-02 | 18 event types all pushable with Pydantic model validation | unit | `uv run pytest tests/unit/test_event_mapper.py -x` | ❌ Wave 0 |
| WS-03 | EventBridge observes ADK Runner event stream without modifying tool code | unit | `uv run pytest tests/unit/test_runner_utils.py::test_event_callback -x` | ❌ Wave 0 |
| WS-04 | 100-event replay buffer for reconnected clients | unit | `uv run pytest tests/unit/test_ws_manager.py::test_replay -x` | ❌ Wave 0 |
| WS-05 | Heartbeat (15s/30s) + disconnect + reconnect lifecycle | unit | `uv run pytest tests/unit/test_ws_manager.py::test_heartbeat -x` | ❌ Wave 0 |

## Sampling Rate

- **Per task commit:** `uv run pytest tests/unit/test_event_mapper.py tests/unit/test_ws_manager.py -q`
- **Per wave merge:** `uv run pytest tests/unit/ -q`
- **Phase gate:** Full suite green before `/gsd-verify-work`

## Wave 0 Gaps

- [ ] `tests/unit/test_event_mapper.py` — covers WS-02 (18 event type mapping)
- [ ] `tests/unit/test_ws_manager.py` — covers WS-01/WS-04/WS-05 (connection, replay, heartbeat)
- [ ] `tests/unit/test_runner_utils.py` update — covers WS-03 (event_callback parameter)
- [ ] No new framework install needed — pytest + pytest-asyncio already available

## Validation Architecture

### Test Framework
- **pytest** 8.4.2 + **pytest-asyncio** — existing project setup
- **httpx TestClient** — FastAPI WebSocket testing via `TestClient.websocket_connect()`
- **unittest.mock** — for mocking ADK Runner events, asyncio tasks, heartbeat timers

### Test Organization
- `tests/unit/test_event_mapper.py` — Event mapper unit tests (WS-02)
- `tests/unit/test_ws_manager.py` — ConnectionManager + replay + heartbeat (WS-01/04/05)
- `tests/unit/test_runner_utils.py` — Extended to test event_callback parameter (WS-03)
- `tests/integration/test_ws_integration.py` — End-to-end WS connection + event flow

### Mock Strategy
- ADK Runner events: Mock `Event`, `Content`, `Part`, `FunctionCall`, `FunctionResponse` objects
- WebSocket connections: Use TestClient.websocket_connect() for real WS behavior
- Heartbeat timing: Mock `asyncio.sleep` to accelerate 15s/30s intervals in tests
- flush_state_sync: Mock to verify called before broadcast

### Critical Test Scenarios
1. WS client connects → receives replay buffer events → receives live events
2. REST command triggers → event_callback fires → WS client receives mapped event
3. Heartbeat ping/pong cycle → client responds → connection maintained
4. Heartbeat timeout → no pong → connection closed and removed from pool
5. Client disconnect → removed from pool → other clients unaffected
6. 18 event types all map correctly from function_call names
7. Slow client → broadcast times out → client removed from pool
8. No WS clients → event_callback is None → REST behavior unchanged

---
*Phase: 14-websocket-layer*
*Validation strategy created: 2026-04-15*
