"""
Trade synchronization service for coordinating data sync operations between
exchange APIs and local trade data storage.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from app.models.trade import Trade, TradeStatus, TradeSide, WinLoss
from app.models.position import Position, PositionStatus
from app.models.exchange_config import ExchangeConfig, ConnectionStatus
from app.integrations.exchange_factory import get_exchange_factory
from app.integrations.base_exchange import BaseExchange, AuthenticationError, APIError, NetworkError
from app.services.config_service import ConfigService
from app.services.data_service import DataService
from app.services.exchange_sync_service import ExchangeSyncService


class TradeSyncStatus(Enum):
    """Status of trade synchronization operations."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"


@dataclass
class TradeSyncResult:
    """Result of a trade synchronization operation."""
    exchange_name: str
    status: TradeSyncStatus
    positions_processed: int
    trades_created: int
    trades_updated: int
    trades_skipped: int
    errors: List[str]
    start_time: datetime
    end_time: Optional[datetime] = None

    def get_duration(self) -> Optional[timedelta]:
        """Get duration of sync operation."""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def is_successful(self) -> bool:
        """Check if sync was successful."""
        return self.status in [TradeSyncStatus.COMPLETED, TradeSyncStatus.PARTIAL]


@dataclass
class TradeReconciliation:
    """Result of trade data reconciliation."""
    position: Position
    existing_trade: Optional[Trade]
    action: str  # 'create', 'update', 'skip'
    reason: str
    trade_data: Optional[Dict[str, Any]] = None


class TradeSyncService:
    """
    Service for synchronizing trade data by converting exchange position data
    into local trade records and managing incremental synchronization.
    """

    def __init__(self, config_service: ConfigService, data_service: DataService, 
                 exchange_sync_service: ExchangeSyncService):
        """
        Initialize trade synchronization service.
        
        Args:
            config_service: Configuration service instance
            data_service: Data service for trade operations
            exchange_sync_service: Exchange sync service for position data
        """
        self.config_service = config_service
        self.data_service = data_service
        self.exchange_sync_service = exchange_sync_service
        self.logger = logging.getLogger("trade.sync")
        
        # Track last sync times for incremental sync
        self._last_sync_times: Dict[str, datetime] = {}

    def sync_all_exchanges(self, force_full_sync: bool = False) -> Dict[str, TradeSyncResult]:
        """
        Synchronize trade data for all active exchanges.
        
        Args:
            force_full_sync: If True, perform full sync regardless of last sync time
            
        Returns:
            Dictionary mapping exchange names to sync results
        """
        results = {}
        active_exchanges = self.config_service.get_active_exchanges()
        
        self.logger.info(f"Starting trade sync for {len(active_exchanges)} active exchanges")
        
        for exchange_config in active_exchanges:
            try:
                result = self.sync_exchange_trades(exchange_config.name, force_full_sync)
                results[exchange_config.name] = result
            except Exception as e:
                self.logger.error(f"Failed to sync trades for {exchange_config.name}: {str(e)}")
                results[exchange_config.name] = TradeSyncResult(
                    exchange_name=exchange_config.name,
                    status=TradeSyncStatus.FAILED,
                    positions_processed=0,
                    trades_created=0,
                    trades_updated=0,
                    trades_skipped=0,
                    errors=[str(e)],
                    start_time=datetime.now()
                )
        
        return results

    def sync_exchange_trades(self, exchange_name: str, force_full_sync: bool = False) -> TradeSyncResult:
        """
        Synchronize trade data for a specific exchange.
        
        Args:
            exchange_name: Name of the exchange to sync
            force_full_sync: If True, perform full sync regardless of last sync time
            
        Returns:
            TradeSyncResult object with sync details
        """
        start_time = datetime.now()
        result = TradeSyncResult(
            exchange_name=exchange_name,
            status=TradeSyncStatus.IN_PROGRESS,
            positions_processed=0,
            trades_created=0,
            trades_updated=0,
            trades_skipped=0,
            errors=[],
            start_time=start_time
        )
        
        try:
            self.logger.info(f"Starting trade sync for exchange: {exchange_name}")
            
            # First, sync position data using the exchange sync service
            position_sync_result = self.exchange_sync_service.sync_exchange(exchange_name, force_full_sync)
            
            if not position_sync_result.is_successful():
                result.status = TradeSyncStatus.FAILED
                result.errors.extend(position_sync_result.errors)
                result.end_time = datetime.now()
                return result
            
            # Get positions from the exchange sync service
            positions_data = self.exchange_sync_service.get_positions(exchange_name)
            positions = positions_data.get(exchange_name, [])
            
            if not positions:
                self.logger.info(f"No positions found for {exchange_name}")
                result.status = TradeSyncStatus.COMPLETED
                result.end_time = datetime.now()
                return result
            
            # Filter positions based on sync time if not full sync
            if not force_full_sync:
                positions = self._filter_positions_by_sync_time(exchange_name, positions)
            
            result.positions_processed = len(positions)
            
            # Get existing trades for reconciliation
            existing_trades = self.data_service.get_trades_by_exchange(exchange_name)
            existing_trades_by_id = {self._generate_trade_id(trade): trade for trade in existing_trades}
            
            # Reconcile positions with existing trades
            reconciliation_results = self._reconcile_trades(
                exchange_name, positions, existing_trades_by_id
            )
            
            # Apply reconciliation results
            for reconciliation in reconciliation_results:
                try:
                    if reconciliation.action == 'create':
                        trade = self._create_trade_from_position(reconciliation.position)
                        self.data_service.add_trade(trade)
                        result.trades_created += 1
                        
                    elif reconciliation.action == 'update':
                        updates = reconciliation.trade_data or {}
                        trade_id = self._generate_trade_id_from_position(reconciliation.position)
                        self.data_service.update_trade(trade_id, updates)
                        result.trades_updated += 1
                        
                    elif reconciliation.action == 'skip':
                        result.trades_skipped += 1
                        
                except Exception as e:
                    error_msg = f"Failed to {reconciliation.action} trade for position {reconciliation.position.position_id}: {str(e)}"
                    result.errors.append(error_msg)
                    self.logger.error(error_msg)
            
            # Update sync metadata
            self._last_sync_times[exchange_name] = start_time
            
            result.status = TradeSyncStatus.COMPLETED if not result.errors else TradeSyncStatus.PARTIAL
            result.end_time = datetime.now()
            
            self.logger.info(
                f"Trade sync completed for {exchange_name}: "
                f"{result.trades_created} created, {result.trades_updated} updated, "
                f"{result.trades_skipped} skipped, {len(result.errors)} errors"
            )
            
        except Exception as e:
            result.status = TradeSyncStatus.FAILED
            result.errors.append(str(e))
            result.end_time = datetime.now()
            self.logger.error(f"Trade sync failed for {exchange_name}: {str(e)}")
        
        return result

    def sync_incremental(self, exchange_name: str) -> TradeSyncResult:
        """
        Perform incremental sync for positions that have been updated recently.
        
        Args:
            exchange_name: Name of the exchange
            
        Returns:
            TradeSyncResult object with sync details
        """
        return self.sync_exchange_trades(exchange_name, force_full_sync=False)

    def get_sync_statistics(self, exchange_name: str = None) -> Dict[str, Any]:
        """
        Get synchronization statistics.
        
        Args:
            exchange_name: Specific exchange name, or None for all exchanges
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {}
        
        if exchange_name:
            exchanges = [exchange_name]
        else:
            exchanges = [config.name for config in self.config_service.get_active_exchanges()]
        
        for exchange in exchanges:
            trade_count = len(self.data_service.get_trades_by_exchange(exchange))
            last_sync = self._last_sync_times.get(exchange)
            
            stats[exchange] = {
                'total_trades': trade_count,
                'last_sync_time': last_sync.isoformat() if last_sync else None,
                'sync_age_hours': (datetime.now() - last_sync).total_seconds() / 3600 if last_sync else None
            }
        
        return stats

    def _filter_positions_by_sync_time(self, exchange_name: str, positions: List[Position]) -> List[Position]:
        """
        Filter positions based on last sync time for incremental sync.
        
        Args:
            exchange_name: Name of the exchange
            positions: List of positions to filter
            
        Returns:
            Filtered list of positions
        """
        last_sync = self._last_sync_times.get(exchange_name)
        if not last_sync:
            return positions
        
        # Include positions that were updated after last sync
        # Add some buffer time to avoid missing updates
        cutoff_time = last_sync - timedelta(minutes=30)
        
        filtered_positions = []
        for position in positions:
            # Check if position was updated recently
            if (position.close_time and position.close_time > cutoff_time) or \
               (not position.close_time and position.open_time > cutoff_time):
                filtered_positions.append(position)
        
        self.logger.debug(f"Filtered {len(positions)} positions to {len(filtered_positions)} for incremental sync")
        return filtered_positions

    def _reconcile_trades(self, exchange_name: str, positions: List[Position], 
                         existing_trades: Dict[str, Trade]) -> List[TradeReconciliation]:
        """
        Reconcile position data with existing trade data.
        
        Args:
            exchange_name: Name of the exchange
            positions: List of positions from exchange
            existing_trades: Dictionary of existing trades by ID
            
        Returns:
            List of reconciliation results
        """
        reconciliations = []
        
        for position in positions:
            trade_id = self._generate_trade_id_from_position(position)
            existing_trade = existing_trades.get(trade_id)
            
            if existing_trade is None:
                # New trade - create it
                reconciliations.append(TradeReconciliation(
                    position=position,
                    existing_trade=None,
                    action='create',
                    reason='New position from exchange'
                ))
            else:
                # Existing trade - check if update is needed
                if self._trade_needs_update(existing_trade, position):
                    updates = self._generate_trade_updates(existing_trade, position)
                    reconciliations.append(TradeReconciliation(
                        position=position,
                        existing_trade=existing_trade,
                        action='update',
                        reason='Position data changed',
                        trade_data=updates
                    ))
                else:
                    reconciliations.append(TradeReconciliation(
                        position=position,
                        existing_trade=existing_trade,
                        action='skip',
                        reason='No changes detected'
                    ))
        
        return reconciliations

    def _trade_needs_update(self, trade: Trade, position: Position) -> bool:
        """
        Check if a trade needs to be updated based on position data.
        
        Args:
            trade: Existing trade
            position: Position data from exchange
            
        Returns:
            True if update is needed, False otherwise
        """
        # Check if position status changed
        expected_status = self._position_status_to_trade_status(position.status)
        if trade.status != expected_status:
            return True
        
        # Check if position is now closed and trade doesn't have exit data
        if position.status == PositionStatus.CLOSED:
            if trade.exit_price is None or trade.exit_time is None:
                return True
            
            # Check if PnL changed significantly
            expected_pnl = position.realized_pnl
            if trade.pnl is None or abs(trade.pnl - expected_pnl) > 0.01:
                return True
        
        # Check if unrealized PnL changed for open positions
        if position.status == PositionStatus.OPEN:
            expected_pnl = position.unrealized_pnl
            if trade.pnl is None or abs(trade.pnl - expected_pnl) > 0.01:
                return True
        
        return False

    def _generate_trade_updates(self, trade: Trade, position: Position) -> Dict[str, Any]:
        """
        Generate update data for a trade based on position data.
        
        Args:
            trade: Existing trade
            position: Position data from exchange
            
        Returns:
            Dictionary of updates to apply
        """
        updates = {}
        
        # Update status
        expected_status = self._position_status_to_trade_status(position.status)
        if trade.status != expected_status:
            updates['status'] = expected_status
        
        # Update exit data for closed positions
        if position.status == PositionStatus.CLOSED:
            if trade.exit_price is None and hasattr(position, 'close_price'):
                updates['exit_price'] = position.close_price
            
            if trade.exit_time is None and position.close_time:
                updates['exit_time'] = position.close_time
            
            # Update realized PnL
            updates['pnl'] = position.realized_pnl
        
        # Update unrealized PnL for open positions
        elif position.status == PositionStatus.OPEN:
            updates['pnl'] = position.unrealized_pnl
        
        return updates

    def _create_trade_from_position(self, position: Position) -> Trade:
        """
        Create a Trade object from a Position object.
        
        Args:
            position: Position data from exchange
            
        Returns:
            Trade object
        """
        trade_id = self._generate_trade_id_from_position(position)
        
        # Determine trade side
        side = TradeSide.LONG if position.side.value == 'long' else TradeSide.SHORT
        
        # Determine trade status
        status = self._position_status_to_trade_status(position.status)
        
        # Calculate PnL based on position status
        if position.status == PositionStatus.CLOSED:
            pnl = position.realized_pnl
        else:
            pnl = position.unrealized_pnl
        
        # Determine exit price for closed positions
        exit_price = None
        if position.status == PositionStatus.CLOSED:
            # Try to get close price from raw data first
            if 'close_price' in position.raw_data:
                exit_price = Decimal(str(position.raw_data['close_price']))
            else:
                # Fallback to mark price if close price not available
                exit_price = position.mark_price

        # Create trade
        trade = Trade(
            id=trade_id,
            exchange=position.raw_data.get('exchange', 'unknown'),
            symbol=position.symbol,
            side=side,
            entry_price=position.entry_price,
            quantity=position.size,
            entry_time=position.open_time,
            status=status,
            exit_price=exit_price,
            exit_time=position.close_time if position.status == PositionStatus.CLOSED else None,
            pnl=pnl,
            win_loss=self._determine_win_loss(pnl) if position.status == PositionStatus.CLOSED else None,
            confluences=[],  # Will be filled by user later
            custom_fields={}
        )
        
        return trade

    def _generate_trade_id(self, trade: Trade) -> str:
        """Generate a consistent ID for a trade."""
        return f"{trade.exchange}_{trade.symbol}_{trade.entry_time.isoformat()}_{trade.side.value}"

    def _generate_trade_id_from_position(self, position: Position) -> str:
        """Generate a trade ID from a position."""
        exchange = position.raw_data.get('exchange', 'unknown')
        side = 'long' if position.side.value == 'long' else 'short'
        return f"{exchange}_{position.symbol}_{position.open_time.isoformat()}_{side}"

    def _position_status_to_trade_status(self, position_status: PositionStatus) -> TradeStatus:
        """Convert position status to trade status."""
        if position_status == PositionStatus.OPEN:
            return TradeStatus.OPEN
        elif position_status == PositionStatus.PARTIALLY_CLOSED:
            return TradeStatus.PARTIALLY_CLOSED
        elif position_status == PositionStatus.CLOSED:
            return TradeStatus.CLOSED
        else:
            return TradeStatus.OPEN  # Default fallback

    def _determine_win_loss(self, pnl) -> Optional[WinLoss]:
        """Determine win/loss based on PnL."""
        if pnl is None:
            return None
        return WinLoss.WIN if pnl > 0 else WinLoss.LOSS

    def get_last_sync_time(self, exchange_name: str) -> Optional[datetime]:
        """Get the last sync time for an exchange."""
        return self._last_sync_times.get(exchange_name)

    def force_resync(self, exchange_name: str) -> TradeSyncResult:
        """Force a complete resync for an exchange."""
        # Clear last sync time to force full sync
        if exchange_name in self._last_sync_times:
            del self._last_sync_times[exchange_name]
        
        return self.sync_exchange_trades(exchange_name, force_full_sync=True)

    def get_sync_health(self) -> Dict[str, Any]:
        """
        Get overall sync health information.
        
        Returns:
            Dictionary with sync health metrics
        """
        active_exchanges = self.config_service.get_active_exchanges()
        health_info = {
            'total_exchanges': len(active_exchanges),
            'synced_exchanges': 0,
            'stale_exchanges': 0,
            'never_synced': 0,
            'exchanges': {}
        }
        
        now = datetime.now()
        stale_threshold = timedelta(hours=24)  # Consider sync stale after 24 hours
        
        for exchange_config in active_exchanges:
            exchange_name = exchange_config.name
            last_sync = self._last_sync_times.get(exchange_name)
            
            if last_sync is None:
                health_info['never_synced'] += 1
                status = 'never_synced'
            elif now - last_sync > stale_threshold:
                health_info['stale_exchanges'] += 1
                status = 'stale'
            else:
                health_info['synced_exchanges'] += 1
                status = 'healthy'
            
            health_info['exchanges'][exchange_name] = {
                'status': status,
                'last_sync': last_sync.isoformat() if last_sync else None,
                'connection_status': exchange_config.connection_status.value,
                'is_active': exchange_config.is_active
            }
        
        return health_info