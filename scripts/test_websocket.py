"""
AI TradeBot - WebSocket Test Script

Directly test WebSocket broadcasting
"""
import asyncio
import websockets
import json
from datetime import datetime

async def test_websocket():
    """Test WebSocket connection and broadcasting"""
    uri = "ws://localhost:8000/ws/events"

    print("Connecting to WebSocket...")
    print(f"URI: {uri}")
    print()

    async with websockets.connect(uri) as ws:
        print("[OK] Connected to WebSocket!")

        # Receive welcome message
        msg = await ws.recv()
        print(f"Server: {msg}")
        print()

        # Wait for existing messages
        print("Listening for messages (2 seconds)...")
        print("-" * 60)

        try:
            for _ in range(5):
                msg = await asyncio.wait_for(ws.recv(), timeout=0.4)
                data = json.loads(msg)
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Received: {data.get('type')}")
        except asyncio.TimeoutError:
            pass

        print("\n" + "-" * 60)
        print("\nNow sending test events...")
        print("-" * 60)

        # Send test events
        test_events = [
            {"type": "perception_start", "data": {"source": "test_simulation"}},
            {"type": "perception_captured", "data": {"event_id": "test_001", "ticker": "600519.SH", "title": "Test: 贵州茅台战略合作", "url": "test://sim", "summary": "测试事件", "raw_data": {}}},
            {"type": "analysis_start", "data": {"event_id": "test_001", "ticker": "600519.SH"}},
            {"type": "ai_thinking", "data": {"event_id": "test_001", "model": "Kimi", "step": "清洗新闻..."}},
            {"type": "ai_thinking", "data": {"event_id": "test_001", "model": "GLM-4", "step": "逻辑推演..."}},
            {"type": "ai_thinking", "data": {"event_id": "test_001", "model": "MiniMax", "step": "生成决策..."}},
            {"type": "decision_complete", "data": {"event_id": "test_001", "ticker": "600519.SH", "action": "HOLD", "exit_plan": {"take_profit": {"price": 1850.0}, "stop_loss": {"price": 1700.0}, "expiration": {"expire_time": "2025-05-12"}}, "reasoning": "测试完成"}}
        ]

        for i, event in enumerate(test_events, 1):
            print(f"[{i}/{len(test_events)}] Sending: {event['type']}")
            await ws.send(json.dumps(event))
            await asyncio.sleep(0.3)

        print("\n" + "=" * 60)
        print("Test complete! Check the Living Logic Wall page.")
        print("Page: file:///D:/AI/AItradebot/docs/showcase/index.html")
        print("=" * 60)

if __name__ == "__main__":
    try:
        asyncio.run(test_websocket())
    except KeyboardInterrupt:
        print("\nTest interrupted")
    except Exception as e:
        print(f"\nError: {e}")
