import sqlite3
import json
import database as db

def modify_evidence_amount():
    db.init_db()
    evidences = db.list_audit_evidence()
    if not evidences:
        print("No evidence found")
        return
        
    ev = evidences[0]
    txn_id = ev["transaction_id"]
    print(f"Modifying evidence for transaction {txn_id}")
    
    # Get current proposal
    proposal_str = ev["agent_proposal"]
    proposal = json.loads(proposal_str)
    
    # Print current hashes
    print(f"Current Intent Hash: {ev['intent_hash']}")
    print(f"Current Decision Hash: {ev['decision_hash']}")
    print(f"Current Evidence Hash: {ev['evidence_hash']}")
    print(f"Current Amount: {proposal.get('amount')}")
    
    # Modify amount
    original_amount = proposal.get("amount")
    new_amount = float(original_amount) - 1000.0
    proposal["amount"] = new_amount
    
    # Update DB without regenerating hash
    conn = sqlite3.connect(db.DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE audit_evidence SET agent_proposal = ? WHERE transaction_id = ?",
        (json.dumps(proposal, sort_keys=True, default=str), txn_id)
    )
    conn.commit()
    conn.close()
    
    print(f"Modified amount to {new_amount} in DB.")
    
if __name__ == "__main__":
    modify_evidence_amount()
