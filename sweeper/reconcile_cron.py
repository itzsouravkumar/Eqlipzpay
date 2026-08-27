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
        
        # In-memory tracking of pending items (in a real DB this would be a table)
        self._pending_holds: Dict[str, Dict] = {}
        
        # Callbacks for when an action needs to be taken by the main app
        self.on_hold_released: Callable = None
        
        logger.info(f"[Sweeper] Initialized with interval {interval_seconds}s")
        
    def track_hold(self, payment_id: str, transfer_id: str, expiry: datetime):
        """Register a new hold for the sweeper to monitor."""
        self._pending_holds[transfer_id] = {
            "payment_id": payment_id,
            "transfer_id": transfer_id,
            "expiry": expiry,
            "status": "pending",
            "added_at": datetime.now()
        }
        logger.info(f"[Sweeper] Tracking hold for transfer {transfer_id}, expiry {expiry}")
        
    def resolve_hold(self, transfer_id: str):
        """Mark a hold as manually resolved so the sweeper stops tracking it."""
        if transfer_id in self._pending_holds:
            self._pending_holds.pop(transfer_id)
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
        now = datetime.now()
        expired_transfers = []
        
        for transfer_id, data in self._pending_holds.items():
            if data["expiry"] <= now:
                expired_transfers.append(transfer_id)
                
        if not expired_transfers:
            return
            
        logger.info(f"[Sweeper] Found {len(expired_transfers)} expired holds to auto-release")
        
        for transfer_id in expired_transfers:
            data = self._pending_holds[transfer_id]
            
            # Fire callback if registered
            if self.on_hold_released:
                try:
                    # Execute in a non-blocking way or await if it's async
                    if asyncio.iscoroutinefunction(self.on_hold_released):
                        await self.on_hold_released(transfer_id, data["payment_id"])
                    else:
                        self.on_hold_released(transfer_id, data["payment_id"])
                except Exception as e:
                    logger.error(f"[Sweeper] Callback failed for {transfer_id}: {e}")
            else:
                logger.warning("[Sweeper] No callback registered for auto-release")
                
            # Remove from tracking
            self._pending_holds.pop(transfer_id, None)
            
    def get_stats(self) -> Dict:
        """Get stats for dashboard."""
        return {
            "is_running": self._running,
            "interval_seconds": self.interval_seconds,
            "pending_holds_tracked": len(self._pending_holds)
        }
