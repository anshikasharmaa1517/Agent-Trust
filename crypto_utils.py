import jwt
import os
import time
from typing import Dict, Any, Optional

# In a real system, this would be a secure, rotated RSA/ECDSA keypair or KMS integration.
# For this prototype, we use a symmetric HMAC key stored in memory/env.
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "super-secret-trust-gateway-key-12345")
ALGORITHM = "HS256"

def generate_intent_token(intent_data: Dict[str, Any]) -> str:
    """
    Cryptographically signs the user's intent.
    This acts as the 'Intent Mandate' in AP2.
    """
    payload = intent_data.copy()
    payload["iat"] = time.time()
    payload["exp"] = time.time() + 3600 # 1 hour expiry
    
    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token

def verify_intent_token(token: str) -> Optional[Dict[str, Any]]:
    """
    Verifies the cryptographic signature of the intent token.
    Returns the decoded payload if valid, None if invalid.
    """
    try:
        decoded_payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded_payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
