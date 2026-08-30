"""
EqlipZ Pay — Sweeper / Reconciliation Cron
============================================
Background job that polls for dropped webhooks and auto-releases
holds that have exceeded their 48h limit.

PRD §17: "The Sweeper: a cron or celery task running every 15 minutes
that polls the payment gateway for dropped webhooks."
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Callable
from database import get_db_connection

logger = logging.getLogger("eqlipz.sweeper")


class ReconcileSweeper:
    """
    Background polling service to reconcile pending transactions
    and manage hold timeouts.
    """
    
    def __init__(self, interval_seconds: int = 900):
        self.interval_seconds = interval_seconds
        self._running = False
        self._task = None
        
        # Callbacks for when an action needs to be taken by the main app
        self.on_hold_released: Callable = None
        
        logger.info(f"[Sweeper] Initialized with interval {interval_seconds}s (SQLite backend)")
        
    def track_hold(self, payment_id: str, transfer_id: str, expiry: datetime):
        """Register a new hold for the sweeper to monitor."""
        conn = get_db_connection()
        cursor = conn.cursor()
        added_at = datetime.now().isoformat()
        
        # If expiry is datetime, convert to isoformat. If it's already string, keep it.
        expiry_str = expiry.isoformat() if isinstance(expiry, datetime) else str(expiry)
        
        cursor.execute(
            "INSERT OR REPLACE INTO pending_holds (transfer_id, payment_id, expiry, status, added_at) VALUES (?, ?, ?, ?, ?)",
            (transfer_id, payment_id, expiry_str, "pending", added_at)
        )
        conn.commit()
        conn.close()
        logger.info(f"[Sweeper] Tracking hold for transfer {transfer_id}, expiry {expiry_str}")
        
    def resolve_hold(self, transfer_id: str):
        """Mark a hold as manually resolved so the sweeper stops tracking it."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM pending_holds WHERE transfer_id = ?", (transfer_id,))
        rows_deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        if rows_deleted > 0:
            logger.info(f"[Sweeper] Stopped tracking resolved hold {transfer_id}")
            
    async def start(self):
        """Start the background polling loop."""
        if self._running:
            return
            
        self._running = True
        logger.info("[Sweeper] Starting reconciliation loop...")
        
        while self._running:
            try:
                await self.sweep()
            except Exception as e:
                logger.error(f"[Sweeper] Error in sweep cycle: {e}")
                
            await asyncio.sleep(self.interval_seconds)
            
    def stop(self):
        """Stop the background polling loop."""
        self._running = False
        logger.info("[Sweeper] Stopping reconciliation loop...")
        
    async def sweep(self):
        """
        Execute a single sweep cycle.
        Find holds that have expired and auto-release them.
        """
        now = datetime.now().isoformat()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM pending_holds WHERE expiry <= ?", (now,))
        expired_holds = cursor.fetchall()
        
        if not expired_holds:
            conn.close()
            return
            
        logger.info(f"[Sweeper] Found {len(expired_holds)} expired holds to auto-release")
        
        for row in expired_holds:
            transfer_id = row["transfer_id"]
            payment_id = row["payment_id"]
            
            # Fire callback if registered
            if self.on_hold_released:
                try:
                    # Execute in a non-blocking way or await if it's async
                    if asyncio.iscoroutinefunction(self.on_hold_released):
                        await self.on_hold_released(transfer_id, payment_id)
                    else:
                        self.on_hold_released(transfer_id, payment_id)
                except Exception as e:
                    logger.error(f"[Sweeper] Callback failed for {transfer_id}: {e}")
            else:
                logger.warning("[Sweeper] No callback registered for auto-release")
                
            # Remove from tracking
            cursor.execute("DELETE FROM pending_holds WHERE transfer_id = ?", (transfer_id,))
            
        conn.commit()
        conn.close()
            
    def get_stats(self) -> Dict:
        """Get stats for dashboard."""
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM pending_holds")
        count = cursor.fetchone()[0]
        conn.close()
        
        return {
            "is_running": self._running,
            "interval_seconds": self.interval_seconds,
            "pending_holds_tracked": count
        }
