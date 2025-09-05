"""
Data service for managing trade data operations including loading, saving, and querying.
"""

import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Optional, Any, Callable
import logging

from app.models.trade import Trade, TradeStatus, TradeSide, WinLoss
from app.utils.serialization import DataSerializer
from app.utils.validators import DataValidator, ValidationError
from app.utils.backup_recovery import BackupManager


logger = logging.getLogger(__name__)


class DataService:
    """Service for managing trade data operations."""
    
    def __init__(self, data_path: str = "data"):
        """
        Initialize DataService with data directory path.
        
        Args:
            data_path: Path to data directory
        """
        self.data_path = Path(data_path)
        self.trades_file = self.data_path / "trades.json"
        self.backup_manager = BackupManager(str(self.data_path))
        
        # Ensure data directory exists
        self.data_path.mkdir(exist_ok=True)
        
        # In-memory cache for trades
        self._trades_cache: Optional[List[Trade]] = None
        self._cache_last_modified: Optional[datetime] = None
    
    def load_trades(self) -> List[Trade]:
        """
        Load all trades from persistent storage.
        
        Returns:
            List of Trade objects
            
        Raises:
            Exception: If loading fails
        """
        try:
            # Check if we can use cached data
            if self._should_use_cache():
                logger.debug("Using cached trade data")
                return self._trades_cache.copy()
            
            if not self.trades_file.exists():
                logger.info("Trades file does not exist, returning empty list")
                self._trades_cache = []
                self._cache_last_modified = datetime.now()
                return []
            
            logger.info(f"Loading trades from {self.trades_file}")
            
            with open(self.trades_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate data structure
            if not isinstance(data, list):
                raise ValidationError("Trades file must contain a list of trades")
            
            trades = []
            for i, trade_data in enumerate(data):
                try:
                    # Validate trade data before deserializing
                    validated_data = DataValidator.validate_trade_data(trade_data)
                    trade = DataSerializer.deserialize_trade(validated_data)
                    trades.append(trade)
                except Exception as e:
                    logger.error(f"Error loading trade at index {i}: {e}")
                    # Continue loading other trades instead of failing completely
                    continue
            
            # Update cache
            self._trades_cache = trades
            self._cache_last_modified = datetime.now()
            
            logger.info(f"Successfully loaded {len(trades)} trades")
            return trades.copy()
            
        except Exception as e:
            logger.error(f"Failed to load trades: {e}")
            raise Exception(f"Failed to load trades: {e}")
    
    def save_trades(self, trades: List[Trade]) -> None:
        """
        Save trades to persistent storage.
        
        Args:
            trades: List of Trade objects to save
            
        Raises:
            Exception: If saving fails
        """
        try:
            logger.info(f"Saving {len(trades)} trades to {self.trades_file}")
            
            # Create backup before saving
            if self.trades_file.exists():
                self.backup_manager.create_backup("trades.json")
            
            # Serialize trades
            serialized_trades = []
            for trade in trades:
                try:
                    trade.validate()  # Ensure trade is valid before saving
                    serialized_data = DataSerializer.serialize_trade(trade)
                    serialized_trades.append(serialized_data)
                except Exception as e:
                    logger.error(f"Error serializing trade {trade.id}: {e}")
                    raise Exception(f"Error serializing trade {trade.id}: {e}")
            
            # Write to temporary file first, then rename for atomic operation
            temp_file = self.trades_file.with_suffix('.tmp')
            
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(serialized_trades, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_file.replace(self.trades_file)
            
            # Update cache
            self._trades_cache = trades.copy()
            self._cache_last_modified = datetime.now()
            
            logger.info(f"Successfully saved {len(trades)} trades")
            
        except Exception as e:
            logger.error(f"Failed to save trades: {e}")
            # Clean up temporary file if it exists
            temp_file = self.trades_file.with_suffix('.tmp')
            if temp_file.exists():
                temp_file.unlink()
            raise Exception(f"Failed to save trades: {e}")
    
    def update_trade(self, trade_id: str, updates: Dict[str, Any]) -> Trade:
        """
        Update a specific trade with new data.
        
        Args:
            trade_id: ID of the trade to update
            updates: Dictionary of field updates
            
        Returns:
            Updated Trade object
            
        Raises:
            ValueError: If trade not found or updates are invalid
            Exception: If update operation fails
        """
        try:
            trades = self.load_trades()
            
            # Find the trade to update
            trade_index = None
            for i, trade in enumerate(trades):
                if trade.id == trade_id:
                    trade_index = i
                    break
            
            if trade_index is None:
                raise ValueError(f"Trade with ID {trade_id} not found")
            
            trade = trades[trade_index]
            
            # Apply updates
            for field, value in updates.items():
                if not hasattr(trade, field):
                    raise ValueError(f"Invalid field: {field}")
                
                # Validate specific field types
                if field == 'confluences' and value is not None:
                    if not isinstance(value, list):
                        raise ValueError("Confluences must be a list")
                    value = [str(c) for c in value]  # Ensure all are strings
                
                elif field == 'win_loss' and value is not None:
                    if isinstance(value, str):
                        value = WinLoss(value)
                    elif not isinstance(value, WinLoss):
                        raise ValueError("win_loss must be a WinLoss enum or string")
                
                elif field == 'status' and value is not None:
                    if isinstance(value, str):
                        value = TradeStatus(value)
                    elif not isinstance(value, TradeStatus):
                        raise ValueError("status must be a TradeStatus enum or string")
                
                elif field == 'side' and value is not None:
                    if isinstance(value, str):
                        value = TradeSide(value)
                    elif not isinstance(value, TradeSide):
                        raise ValueError("side must be a TradeSide enum or string")
                
                elif field in ['entry_price', 'exit_price', 'quantity', 'pnl'] and value is not None:
                    if not isinstance(value, Decimal):
                        value = Decimal(str(value))
                
                elif field in ['entry_time', 'exit_time'] and value is not None:
                    if isinstance(value, str):
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    elif not isinstance(value, datetime):
                        raise ValueError(f"{field} must be a datetime object or ISO string")
                
                elif field == 'custom_fields' and value is not None:
                    if not isinstance(value, dict):
                        raise ValueError("custom_fields must be a dictionary")
                
                setattr(trade, field, value)
            
            # Update timestamp
            trade.updated_at = datetime.now()
            
            # Validate updated trade
            trade.validate()
            
            # Save updated trades
            self.save_trades(trades)
            
            logger.info(f"Successfully updated trade {trade_id}")
            return trade
            
        except Exception as e:
            logger.error(f"Failed to update trade {trade_id}: {e}")
            raise
    
    def get_trades_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Trade]:
        """
        Get trades within a specific date range.
        
        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            
        Returns:
            List of trades within the date range
        """
        try:
            # Validate date range
            DataValidator.validate_date_range(start_date, end_date)
            
            trades = self.load_trades()
            
            filtered_trades = []
            for trade in trades:
                # Use entry_time for filtering
                if start_date <= trade.entry_time <= end_date:
                    filtered_trades.append(trade)
            
            logger.debug(f"Found {len(filtered_trades)} trades between {start_date} and {end_date}")
            return filtered_trades
            
        except Exception as e:
            logger.error(f"Failed to get trades by date range: {e}")
            raise
    
    def filter_trades(self, filter_func: Callable[[Trade], bool]) -> List[Trade]:
        """
        Filter trades using a custom function.
        
        Args:
            filter_func: Function that takes a Trade and returns bool
            
        Returns:
            List of trades that match the filter
        """
        try:
            trades = self.load_trades()
            filtered_trades = [trade for trade in trades if filter_func(trade)]
            
            logger.debug(f"Filter returned {len(filtered_trades)} trades")
            return filtered_trades
            
        except Exception as e:
            logger.error(f"Failed to filter trades: {e}")
            raise
    
    def get_trades_by_symbol(self, symbol: str) -> List[Trade]:
        """Get all trades for a specific symbol."""
        return self.filter_trades(lambda trade: trade.symbol.upper() == symbol.upper())
    
    def get_trades_by_exchange(self, exchange: str) -> List[Trade]:
        """Get all trades for a specific exchange."""
        return self.filter_trades(lambda trade: trade.exchange.lower() == exchange.lower())
    
    def get_trades_by_status(self, status: TradeStatus) -> List[Trade]:
        """Get all trades with a specific status."""
        return self.filter_trades(lambda trade: trade.status == status)
    
    def get_trades_by_confluence(self, confluence: str) -> List[Trade]:
        """Get all trades that include a specific confluence."""
        return self.filter_trades(lambda trade: confluence in trade.confluences)
    
    def get_winning_trades(self) -> List[Trade]:
        """Get all trades marked as wins."""
        return self.filter_trades(lambda trade: trade.win_loss == WinLoss.WIN)
    
    def get_losing_trades(self) -> List[Trade]:
        """Get all trades marked as losses."""
        return self.filter_trades(lambda trade: trade.win_loss == WinLoss.LOSS)
    
    def get_profitable_trades(self) -> List[Trade]:
        """Get all trades with positive PnL."""
        return self.filter_trades(lambda trade: trade.pnl is not None and trade.pnl > 0)
    
    def get_unprofitable_trades(self) -> List[Trade]:
        """Get all trades with negative PnL."""
        return self.filter_trades(lambda trade: trade.pnl is not None and trade.pnl < 0)
    
    def add_trade(self, trade: Trade) -> None:
        """
        Add a new trade to the data store.
        
        Args:
            trade: Trade object to add
            
        Raises:
            ValueError: If trade with same ID already exists
            Exception: If add operation fails
        """
        try:
            trades = self.load_trades()
            
            # Check for duplicate ID
            if any(t.id == trade.id for t in trades):
                raise ValueError(f"Trade with ID {trade.id} already exists")
            
            # Validate trade
            trade.validate()
            
            # Add to list and save
            trades.append(trade)
            self.save_trades(trades)
            
            logger.info(f"Successfully added trade {trade.id}")
            
        except Exception as e:
            logger.error(f"Failed to add trade {trade.id}: {e}")
            raise
    
    def delete_trade(self, trade_id: str) -> bool:
        """
        Delete a trade from the data store.
        
        Args:
            trade_id: ID of the trade to delete
            
        Returns:
            True if trade was deleted, False if not found
            
        Raises:
            Exception: If delete operation fails
        """
        try:
            trades = self.load_trades()
            
            # Find and remove the trade
            original_count = len(trades)
            trades = [trade for trade in trades if trade.id != trade_id]
            
            if len(trades) == original_count:
                logger.warning(f"Trade {trade_id} not found for deletion")
                return False
            
            # Save updated list
            self.save_trades(trades)
            
            logger.info(f"Successfully deleted trade {trade_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete trade {trade_id}: {e}")
            raise
    
    def get_trade_count(self) -> int:
        """Get total number of trades."""
        try:
            trades = self.load_trades()
            return len(trades)
        except Exception as e:
            logger.error(f"Failed to get trade count: {e}")
            return 0
    
    def get_trade_statistics(self) -> Dict[str, Any]:
        """
        Get basic statistics about trades.
        
        Returns:
            Dictionary with trade statistics
        """
        try:
            trades = self.load_trades()
            
            if not trades:
                return {
                    'total_trades': 0,
                    'open_trades': 0,
                    'closed_trades': 0,
                    'partially_closed_trades': 0,
                    'winning_trades': 0,
                    'losing_trades': 0,
                    'total_pnl': Decimal('0'),
                    'exchanges': [],
                    'symbols': [],
                    'confluences': []
                }
            
            stats = {
                'total_trades': len(trades),
                'open_trades': len([t for t in trades if t.status == TradeStatus.OPEN]),
                'closed_trades': len([t for t in trades if t.status == TradeStatus.CLOSED]),
                'partially_closed_trades': len([t for t in trades if t.status == TradeStatus.PARTIALLY_CLOSED]),
                'winning_trades': len([t for t in trades if t.win_loss == WinLoss.WIN]),
                'losing_trades': len([t for t in trades if t.win_loss == WinLoss.LOSS]),
                'total_pnl': sum((t.pnl for t in trades if t.pnl is not None), Decimal('0')),
                'exchanges': list(set(t.exchange for t in trades)),
                'symbols': list(set(t.symbol for t in trades)),
                'confluences': list(set(c for t in trades for c in t.confluences))
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get trade statistics: {e}")
            raise
    
    def backup_data(self) -> str:
        """
        Create a backup of trade data.
        
        Returns:
            Path to backup file
            
        Raises:
            Exception: If backup fails
        """
        try:
            if not self.trades_file.exists():
                raise Exception("No trades file to backup")
            
            backup_path = self.backup_manager.create_backup("trades.json")
            logger.info(f"Created backup at {backup_path}")
            return backup_path
            
        except Exception as e:
            logger.error(f"Failed to create backup: {e}")
            raise
    
    def restore_from_backup(self, backup_path: str) -> None:
        """
        Restore trade data from backup.
        
        Args:
            backup_path: Path to backup file
            
        Raises:
            Exception: If restore fails
        """
        try:
            self.backup_manager.restore_backup(backup_path, "trades.json")
            
            # Clear cache to force reload
            self._trades_cache = None
            self._cache_last_modified = None
            
            logger.info(f"Restored data from backup {backup_path}")
            
        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            raise
    
    def clear_cache(self) -> None:
        """Clear the in-memory cache."""
        self._trades_cache = None
        self._cache_last_modified = None
        logger.debug("Cleared trade data cache")
    
    def _should_use_cache(self) -> bool:
        """Check if cached data should be used."""
        if self._trades_cache is None or self._cache_last_modified is None:
            return False
        
        # Check if file has been modified since cache was created
        if self.trades_file.exists():
            file_mtime = datetime.fromtimestamp(self.trades_file.stat().st_mtime)
            if file_mtime > self._cache_last_modified:
                return False
        
        # Use cache if it's less than 5 minutes old
        cache_age = datetime.now() - self._cache_last_modified
        return cache_age < timedelta(minutes=5)