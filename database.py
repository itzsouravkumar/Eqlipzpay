import os
import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger("eqlipz.database")

# Use Render persistent disk if available, otherwise use local directory
if os.path.exists("/var/data"):
    DB_PATH = Path("/var/data/eqlipz.db")
else:
    DB_PATH = Path(__file__).parent / "eqlipz.db"

def get_db_connection():
    """Returns a connection to the SQLite database."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema if it doesn't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Trust Passports (Contextual Trust Graph)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS trust_passports_v2 (
            entity_id TEXT PRIMARY KEY,
            risk_band TEXT NOT NULL,
            contexts TEXT NOT NULL, -- JSON encoded list of ContextualTrust
            success_count INTEGER DEFAULT 0,
            dispute_count INTEGER DEFAULT 0,
            fraud_count INTEGER DEFAULT 0,
            credential_hash TEXT NOT NULL,
            version TEXT DEFAULT '1',
            created_at TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')

    # 2. Credential Log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS credential_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entity_hash TEXT NOT NULL,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            credential_id TEXT NOT NULL
        )
    ''')

    # 3. Pending Holds (Sweeper)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_holds_v2 (
            transfer_id TEXT PRIMARY KEY,
            payment_id TEXT NOT NULL,
            expiry TEXT NOT NULL,
            status TEXT NOT NULL,
            added_at TEXT NOT NULL
        )
    ''')

    # 4. Calibration Labels (Dispute Feedback Loop)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calibration_labels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            payment_id TEXT NOT NULL,
            prediction TEXT NOT NULL,
            ground_truth TEXT NOT NULL,
            amount REAL NOT NULL,
            source TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')

    # 5. Calibration Log
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS calibration_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            labels_used INTEGER NOT NULL,
            empirical_coverage REAL NOT NULL,
            target_coverage REAL NOT NULL,
            old_alpha REAL NOT NULL,
            new_alpha REAL NOT NULL,
            alpha_changed INTEGER NOT NULL,
            false_negatives INTEGER NOT NULL,
            false_positives INTEGER NOT NULL,
            true_positives INTEGER NOT NULL,
            fn_cost REAL NOT NULL,
            fp_cost REAL NOT NULL
        )
    ''')

    # 6. Evidence Capsules
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS evidence_capsules (
            transaction_id TEXT PRIMARY KEY,
            intent_hash TEXT NOT NULL,
            mandate_hash TEXT NOT NULL,
            risk_policy_version TEXT NOT NULL,
            prediction_set TEXT NOT NULL, -- JSON list
            decision TEXT NOT NULL,
            settlement_action TEXT NOT NULL,
            review_verdict TEXT,
            outcome_hash TEXT,
            previous_hash TEXT,
            created_at TEXT NOT NULL
        )
    ''')

    # 7. Agent Budgets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_budgets (
            agent_id TEXT PRIMARY KEY,
            daily_limit INTEGER NOT NULL,
            transaction_limit INTEGER NOT NULL,
            allowed_categories TEXT NOT NULL, -- JSON list
            allowed_regions TEXT NOT NULL, -- JSON list
            max_merchant_risk TEXT NOT NULL,
            created_at TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')

    # 8. Merchant Liquidity
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS merchant_liquidity (
            merchant_id TEXT PRIMARY KEY,
            available_balance REAL NOT NULL,
            locked_escrow REAL NOT NULL,
            risk_tier TEXT NOT NULL,
            last_updated TEXT NOT NULL
        )
    ''')

    # 9. Network Velocity
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS network_velocity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            transaction_count INTEGER NOT NULL,
            volume_amount REAL NOT NULL,
            anomaly_score REAL NOT NULL
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("[Database] Initialized SQLite tables.")

# Auto-initialize on import
init_db()
