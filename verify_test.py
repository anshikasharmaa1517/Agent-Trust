import sys
import database as db
import evidence_service

def verify_test():
    db.init_db()
    evidences = db.list_audit_evidence()
    if not evidences:
        print("No evidence found")
        return
        
    txn_id = evidences[0]["transaction_id"]
    is_valid, details = evidence_service.verify_evidence(txn_id)
    
    print(f"Is valid: {is_valid}")
    print(f"Details: {details}")

if __name__ == "__main__":
    verify_test()
