"""
Exchange synchronization service for managing position data synchronization
between local storage and exchange APIs.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from ..models.position import Position, PositionStatus
from ..models.exchange_config import ExchangeConfig, ConnectionStatus
from ..integrations.exchange_factory import get_exchange_factory
from ..integrations.base_exchange import BaseExchange, AuthenticationError, APIError, NetworkError
from .config_service import ConfigService


class SyncStatus(Enum):
    """Status of synchronization operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class SyncResult:
    """Result of a synchronization operation."""
    exchange_name: str
    status: SyncStatus
    positions_fetched: int
    positions_updated: int
    positions_added: int
    errors: List[str]
    start_time: datetime
    end_time: Optional[datetime] = None
    last_sync_time: Optional[datetime] = None

    def get_duration(self) -> Optional[timedelta]:
        """Get duration of sync operation."""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def is_successful(self) -> bool:
        """Check if sync was successful."""
        return self.status in [SyncStatus.COMPLETED, SyncStatus.PARTIAL]


@dataclass
class PositionReconciliation:
    """Result of position data reconciliation."""
    local_position: Optional[Position]
    remote_position: Optional[Position]
    action: str  # 'add', 'update', 'skip', 'conflict'
    reason: str
    needs_tracking: bool = False  # For partially closed positions


class ExchangeSyncService:
    """
    Service for synchronizing position data between local storage and exchanges.
    
    Handles fetching position history, reconciling data differences, and tracking
    partially closed positions that need future updates.
    """

    def __init__(self, config_service: ConfigService, data_path: str = "/app/data"):
        """
        Initialize exchange synchronization service.
        
        Args:
            config_service: Configuration service instance
            data_path: Path to persistent data directory
        """
        self.config_service = config_service
        self.data_path = data_path
        self.logger = logging.getLogger("exchange.sync")
        self.exchange_factory = get_exchange_factory()
        
        # Cache for position data (in production, this would be a proper database)
        self._position_cache: Dict[str, Dict[str, Position]] = {}  # exchange -> position_id -> position
        self._partial_positions: Dict[str, Set[str]] = {}  # exchange -> set of position_ids
        self._last_sync_times: Dict[str, datetime] = {}
        
        # Load cached data
        self._load_position_cache()
        self._load_partial_positions()

    def sync_all_exchanges(self, force_full_sync: bool = False) -> Dict[str, SyncResult]:
        """
        Synchronize position data for all active exchanges.
        
        Args:
            force_full_sync: If True, perform full sync regardless of last sync time
            
        Returns:
            Dictionary mapping exchange names to sync results
        """
        results = {}
        active_exchanges = self.config_service.get_active_exchanges()
        
        self.logger.info(f"Starting sync for {len(active_exchanges)} active exchanges")
        
        for exchange_config in active_exchanges:
            try:
                result = self.sync_exchange(exchange_config.name, force_full_sync)
                results[exchange_config.name] = result
            except Exception as e:
                self.logger.error(f"Failed to sync {exchange_config.name}: {str(e)}")
                results[exchange_config.name] = SyncResult(
                    exchange_name=exchange_config.name,
                    status=SyncStatus.FAILED,
                    positions_fetched=0,
                    positions_updated=0,
                    positions_added=0,
                    errors=[str(e)],
                    start_time=datetime.now()
                )
        
        return results

    def sync_exchange(self, exchange_name: str, force_full_sync: bool = False) -> SyncResult:
        """
        Synchronize position data for a specific exchange.
        
        Args:
            exchange_name: Name of the exchange to sync
            force_full_sync: If True, perform full sync regardless of last sync time
            
        Returns:
            SyncResult object with sync details
        """
        start_time = datetime.now()
        result = SyncResult(
            exchange_name=exchange_name,
            status=SyncStatus.IN_PROGRESS,
            positions_fetched=0,
            positions_updated=0,
            positions_added=0,
            errors=[],
            start_time=start_time
        )
        
        try:
            self.logger.info(f"Starting sync for exchange: {exchange_name}")
            
            # Get exchange configuration
            exchange_config = self.config_service.get_exchange_config(exchange_name)
            if not exchange_config:
                raise ValueError(f"No configuration found for exchange: {exchange_name}")
            
            if not exchange_config.is_active:
                raise ValueError(f"Exchange {exchange_name} is not active")
            
            # Create exchange client
            api_key = self.config_service.decrypt_api_key(exchange_name, exchange_config.api_key_encrypted)
            client = self.exchange_factory.create_exchange_client(exchange_name, api_key)
            
            # Determine sync time range
            since_time = self._get_sync_start_time(exchange_name, force_full_sync)
            
            # Fetch position history
            self.logger.info(f"Fetching positions since {since_time}")
            remote_positions = client.get_position_history(since=since_time)
            result.positions_fetched = len(remote_positions)
            
            # Get local positions for reconciliation
            local_positions = self._get_local_positions(exchange_name)
            
            # Reconcile data
            reconciliation_results = self._reconcile_positions(
                exchange_name, local_positions, remote_positions
            )
            
            # Apply reconciliation results
            for reconciliation in reconciliation_results:
                if reconciliation.action == 'add':
                    self._add_position(exchange_name, reconciliation.remote_position)
                    result.positions_added += 1
                elif reconciliation.action == 'update':
                    self._update_position(exchange_name, reconciliation.remote_position)
                    result.positions_updated += 1
                
                # Track partially closed positions
                if reconciliation.needs_tracking:
                    self._track_partial_position(exchange_name, reconciliation.remote_position.position_id)
            
            # Update sync metadata
            self._last_sync_times[exchange_name] = start_time
            exchange_config.last_sync = start_time
            exchange_config.connection_status = ConnectionStatus.CONNECTED
            self.config_service.save_exchange_config(exchange_config)
            
            # Save updated data
            self._save_position_cache()
            self._save_partial_positions()
            
            result.status = SyncStatus.COMPLETED
            result.end_time = datetime.now()
            result.last_sync_time = start_time
            
            self.logger.info(
                f"Sync completed for {exchange_name}: "
                f"{result.positions_added} added, {result.positions_updated} updated"
            )
            
        except (AuthenticationError, APIError, NetworkError) as e:
            result.status = SyncStatus.FAILED
            result.errors.append(f"Exchange API error: {str(e)}")
            result.end_time = datetime.now()
            
            # Update connection status
            exchange_config = self.config_service.get_exchange_config(exchange_name)
            if exchange_config:
                exchange_config.connection_status = ConnectionStatus.ERROR
                self.config_service.save_exchange_config(exchange_config)
            
            self.logger.error(f"Sync failed for {exchange_name}: {str(e)}")
            
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            result.end_time = datetime.now()
            self.logger.error(f"Unexpected error during sync for {exchange_name}: {str(e)}")
        
        return result

    def sync_partial_positions(self, exchange_name: str) -> SyncResult:
        """
        Sync only positions that are marked as partially closed.
        
        Args:
            exchange_name: Name of the exchange
            
        Returns:
            SyncResult object with sync details
        """
        start_time = datetime.now()
        result = SyncResult(
            exchange_name=exchange_name,
            status=SyncStatus.IN_PROGRESS,
            positions_fetched=0,
            positions_updated=0,
            positions_added=0,
            errors=[],
            start_time=start_time
        )
        
        try:
            partial_position_ids = self._partial_positions.get(exchange_name, set())
            if not partial_position_ids:
                result.status = SyncStatus.COMPLETED
                result.end_time = datetime.now()
                return result
            
            self.logger.info(f"Syncing {len(partial_position_ids)} partial positions for {exchange_name}")
            
            # Get exchange client
            exchange_config = self.config_service.get_exchange_config(exchange_name)
            if not exchange_config:
                raise ValueError(f"No configuration found for exchange: {exchange_name}")
            
            api_key = self.config_service.decrypt_api_key(exchange_name, exchange_config.api_key_encrypted)
            client = self.exchange_factory.create_exchange_client(exchange_name, api_key)
            
            # Fetch current status of partial positions
            updated_positions = []
            for position_id in partial_position_ids:
                try:
                    position = client.get_position_by_id(position_id)
                    if position:
                        updated_positions.append(position)
                        result.positions_fetched += 1
                except Exception as e:
                    result.errors.append(f"Failed to fetch position {position_id}: {str(e)}")
            
            # Update positions and check if they're still partial
            positions_to_untrack = set()
            for position in updated_positions:
                self._update_position(exchange_name, position)
                result.positions_updated += 1
                
                # If position is now fully closed, stop tracking it
                if position.status == PositionStatus.CLOSED:
                    positions_to_untrack.add(position.position_id)
            
            # Remove fully closed positions from tracking
            for position_id in positions_to_untrack:
                self._untrack_partial_position(exchange_name, position_id)
            
            # Save updated data
            self._save_position_cache()
            self._save_partial_positions()
            
            result.status = SyncStatus.COMPLETED
            result.end_time = datetime.now()
            
            self.logger.info(
                f"Partial sync completed for {exchange_name}: "
                f"{result.positions_updated} updated, {len(positions_to_untrack)} fully closed"
            )
            
        except Exception as e:
            result.status = SyncStatus.FAILED
            result.errors.append(str(e))
            result.end_time = datetime.now()
            self.logger.error(f"Partial sync failed for {exchange_name}: {str(e)}")
        
        return result

    def get_positions(self, exchange_name: str = None) -> Dict[str, List[Position]]:
        """
        Get cached position data.
        
        Args:
            exchange_name: Specific exchange name, or None for all exchanges
            
        Returns:
            Dictionary mapping exchange names to lists of positions
        """
        if exchange_name:
            return {exchange_name: list(self._position_cache.get(exchange_name, {}).values())}
        
        return {
            exchange: list(positions.values())
            for exchange, positions in self._position_cache.items()
        }

    def get_position_by_id(self, exchange_name: str, position_id: str) -> Optional[Position]:
        """
        Get a specific position by ID.
        
        Args:
            exchange_name: Name of the exchange
            position_id: Position ID
            
        Returns:
            Position object or None if not found
        """
        exchange_positions = self._position_cache.get(exchange_name, {})
        return exchange_positions.get(position_id)

    def get_partial_positions(self, exchange_name: str = None) -> Dict[str, List[Position]]:
        """
        Get positions that are marked as partially closed.
        
        Args:
            exchange_name: Specific exchange name, or None for all exchanges
            
        Returns:
            Dictionary mapping exchange names to lists of partial positions
        """
        result = {}
        
        exchanges_to_check = [exchange_name] if exchange_name else self._partial_positions.keys()
        
        for exchange in exchanges_to_check:
            partial_ids = self._partial_positions.get(exchange, set())
            exchange_positions = self._position_cache.get(exchange, {})
            
            partial_positions = [
                exchange_positions[pos_id]
                for pos_id in partial_ids
                if pos_id in exchange_positions
            ]
            
            if partial_positions:
                result[exchange] = partial_positions
        
        return result

    def _get_sync_start_time(self, exchange_name: str, force_full_sync: bool) -> Optional[datetime]:
        """
        Determine the start time for position synchronization.
        
        Args:
            exchange_name: Name of the exchange
            force_full_sync: Whether to force a full sync
            
        Returns:
            Start time for sync, or None for full history
        """
        if force_full_sync:
            return None
        
        # Use last sync time if available
        last_sync = self._last_sync_times.get(exchange_name)
        if last_sync:
            # Go back a bit to ensure we don't miss any updates
            return last_sync - timedelta(hours=1)
        
        # For first sync, get positions from last 30 days
        return datetime.now() - timedelta(days=30)

    def _get_local_positions(self, exchange_name: str) -> Dict[str, Position]:
        """Get local positions for an exchange."""
        return self._position_cache.get(exchange_name, {}).copy()

    def _reconcile_positions(self, exchange_name: str, local_positions: Dict[str, Position],
                           remote_positions: List[Position]) -> List[PositionReconciliation]:
        """
        Reconcile local and remote position data.
        
        Args:
            exchange_name: Name of the exchange
            local_positions: Dictionary of local positions by ID
            remote_positions: List of remote positions
            
        Returns:
            List of reconciliation results
        """
        reconciliations = []
        
        for remote_position in remote_positions:
            position_id = remote_position.position_id
            local_position = local_positions.get(position_id)
            
            if local_position is None:
                # New position - add it
                reconciliations.append(PositionReconciliation(
                    local_position=None,
                    remote_position=remote_position,
                    action='add',
                    reason='New position from exchange',
                    needs_tracking=remote_position.status == PositionStatus.PARTIALLY_CLOSED
                ))
            else:
                # Existing position - check if update is needed
                if self._position_needs_update(local_position, remote_position):
                    reconciliations.append(PositionReconciliation(
                        local_position=local_position,
                        remote_position=remote_position,
                        action='update',
                        reason='Position data changed',
                        needs_tracking=remote_position.status == PositionStatus.PARTIALLY_CLOSED
                    ))
                else:
                    reconciliations.append(PositionReconciliation(
                        local_position=local_position,
                        remote_position=remote_position,
                        action='skip',
                        reason='No changes detected'
                    ))
        
        return reconciliations

    def _position_needs_update(self, local_position: Position, remote_position: Position) -> bool:
        """
        Check if a local position needs to be updated with remote data.
        
        Args:
            local_position: Local position data
            remote_position: Remote position data
            
        Returns:
            True if update is needed, False otherwise
        """
        # Check key fields that might change
        if local_position.status != remote_position.status:
            return True
        
        if local_position.mark_price != remote_position.mark_price:
            return True
        
        if local_position.unrealized_pnl != remote_position.unrealized_pnl:
            return True
        
        if local_position.realized_pnl != remote_position.realized_pnl:
            return True
        
        if local_position.close_time != remote_position.close_time:
            return True
        
        return False

    def _add_position(self, exchange_name: str, position: Position) -> None:
        """Add a new position to the cache."""
        if exchange_name not in self._position_cache:
            self._position_cache[exchange_name] = {}
        
        self._position_cache[exchange_name][position.position_id] = position

    def _update_position(self, exchange_name: str, position: Position) -> None:
        """Update an existing position in the cache."""
        if exchange_name not in self._position_cache:
            self._position_cache[exchange_name] = {}
        
        self._position_cache[exchange_name][position.position_id] = position

    def _track_partial_position(self, exchange_name: str, position_id: str) -> None:
        """Mark a position for tracking as partially closed."""
        if exchange_name not in self._partial_positions:
            self._partial_positions[exchange_name] = set()
        
        self._partial_positions[exchange_name].add(position_id)

    def _untrack_partial_position(self, exchange_name: str, position_id: str) -> None:
        """Stop tracking a position as partially closed."""
        if exchange_name in self._partial_positions:
            self._partial_positions[exchange_name].discard(position_id)

    def _load_position_cache(self) -> None:
        """Load position cache from persistent storage."""
        # In a real implementation, this would load from a database or file
        # For now, we'll start with an empty cache
        self._position_cache = {}

    def _save_position_cache(self) -> None:
        """Save position cache to persistent storage."""
        # In a real implementation, this would save to a database or file
        # For now, we'll just log the operation
        total_positions = sum(len(positions) for positions in self._position_cache.values())
        self.logger.debug(f"Saved {total_positions} positions to cache")

    def _load_partial_positions(self) -> None:
        """Load partial position tracking from persistent storage."""
        # In a real implementation, this would load from a database or file
        # For now, we'll start with an empty set
        self._partial_positions = {}

    def _save_partial_positions(self) -> None:
        """Save partial position tracking to persistent storage."""
        # In a real implementation, this would save to a database or file
        # For now, we'll just log the operation
        total_partial = sum(len(positions) for positions in self._partial_positions.values())
        self.logger.debug(f"Saved {total_partial} partial position IDs to tracking")