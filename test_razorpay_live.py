"""Direct test of Razorpay Test Mode API call."""
import os
import json
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

import razorpay_adapter

# Step 1: Check connection status
status = razorpay_adapter.get_connection_status()
print(f"Connection Status: {json.dumps(status, indent=2)}")
print()

# Step 2: Attempt a real Test Mode order
if status["mode"] == "TEST":
    print("Making REAL Razorpay Test Mode API call...")
    try:
        order = razorpay_adapter.create_order(
            amount=6999.0,
            currency="INR",
            receipt="test_verify_001",
            description="Test Mode verification",
            notes={"test": "true", "source": "agent_trust_gateway"},
        )
        print(f"\n✓ SUCCESS!")
        print(f"  Order ID:     {order['razorpay_order_id']}")
        print(f"  Status:       {order['status']}")
        print(f"  Amount:       ₹{order['amount']:,.0f}")
        print(f"  Currency:     {order['currency']}")
        print(f"  Simulated:    {order['is_simulated']}")
        print(f"  Receipt:      {order['receipt']}")

        # Verify it's a REAL Razorpay order ID (starts with order_)
        if order["razorpay_order_id"].startswith("order_") and not order["razorpay_order_id"].startswith("sim_order_"):
            print(f"\n✓ CONFIRMED: Real Razorpay Test Mode order created.")
        else:
            print(f"\n✗ WARNING: Order ID format unexpected: {order['razorpay_order_id']}")

    except Exception as e:
        print(f"\n✗ FAILED: {e}")
else:
    print(f"Mode is {status['mode']}. Cannot test real API.")
    print("Set RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env")
