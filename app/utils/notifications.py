"""
User notification system for displaying messages and feedback.
"""

import streamlit as st
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class NotificationType(Enum):
    """Types of notifications."""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class Notification:
    """Represents a user notification."""
    
    def __init__(self, message: str, notification_type: NotificationType,
                 title: Optional[str] = None, duration: Optional[timedelta] = None,
                 dismissible: bool = True):
        """
        Initialize notification.
        
        Args:
            message: Notification message
            notification_type: Type of notification
            title: Optional title
            duration: How long to show notification (None = permanent)
            dismissible: Whether user can dismiss the notification
        """
        self.id = f"notification_{datetime.now().timestamp()}"
        self.message = message
        self.type = notification_type
        self.title = title
        self.created_at = datetime.now()
        self.duration = duration
        self.dismissible = dismissible
        self.dismissed = False
    
    def is_expired(self) -> bool:
        """Check if notification has expired."""
        if self.duration is None:
            return False
        
        return datetime.now() - self.created_at > self.duration
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert notification to dictionary."""
        return {
            'id': self.id,
            'message': self.message,
            'type': self.type.value,
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'duration': self.duration.total_seconds() if self.duration else None,
            'dismissible': self.dismissible,
            'dismissed': self.dismissed
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Notification':
        """Create notification from dictionary."""
        notification = cls(
            message=data['message'],
            notification_type=NotificationType(data['type']),
            title=data.get('title'),
            duration=timedelta(seconds=data['duration']) if data.get('duration') else None,
            dismissible=data.get('dismissible', True)
        )
        
        notification.id = data['id']
        notification.created_at = datetime.fromisoformat(data['created_at'])
        notification.dismissed = data.get('dismissed', False)
        
        return notification


class NotificationManager:
    """Manages user notifications."""
    
    def __init__(self):
        """Initialize notification manager."""
        self.notifications_key = "notifications"
        self.max_notifications = 10
    
    def add_notification(self, message: str, notification_type: NotificationType,
                        title: Optional[str] = None, duration: Optional[timedelta] = None,
                        dismissible: bool = True) -> str:
        """
        Add a new notification.
        
        Args:
            message: Notification message
            notification_type: Type of notification
            title: Optional title
            duration: How long to show notification
            dismissible: Whether user can dismiss
            
        Returns:
            Notification ID
        """
        notification = Notification(
            message=message,
            notification_type=notification_type,
            title=title,
            duration=duration,
            dismissible=dismissible
        )
        
        notifications = self._get_notifications()
        notifications.append(notification)
        
        # Keep only the most recent notifications
        if len(notifications) > self.max_notifications:
            notifications = notifications[-self.max_notifications:]
        
        self._save_notifications(notifications)
        
        logger.debug(f"Added {notification_type.value} notification: {message}")
        return notification.id
    
    def success(self, message: str, title: Optional[str] = None,
               duration: Optional[timedelta] = None) -> str:
        """Add success notification."""
        return self.add_notification(
            message, NotificationType.SUCCESS, title, duration
        )
    
    def error(self, message: str, title: Optional[str] = None,
             duration: Optional[timedelta] = None) -> str:
        """Add error notification."""
        return self.add_notification(
            message, NotificationType.ERROR, title, duration
        )
    
    def warning(self, message: str, title: Optional[str] = None,
               duration: Optional[timedelta] = None) -> str:
        """Add warning notification."""
        return self.add_notification(
            message, NotificationType.WARNING, title, duration
        )
    
    def info(self, message: str, title: Optional[str] = None,
            duration: Optional[timedelta] = None) -> str:
        """Add info notification."""
        return self.add_notification(
            message, NotificationType.INFO, title, duration
        )
    
    def dismiss_notification(self, notification_id: str) -> bool:
        """
        Dismiss a notification.
        
        Args:
            notification_id: ID of notification to dismiss
            
        Returns:
            True if dismissed, False if not found
        """
        notifications = self._get_notifications()
        
        for notification in notifications:
            if notification.id == notification_id:
                notification.dismissed = True
                self._save_notifications(notifications)
                logger.debug(f"Dismissed notification: {notification_id}")
                return True
        
        return False
    
    def clear_all_notifications(self) -> None:
        """Clear all notifications."""
        self._save_notifications([])
        logger.debug("Cleared all notifications")
    
    def get_active_notifications(self) -> List[Notification]:
        """
        Get all active (non-dismissed, non-expired) notifications.
        
        Returns:
            List of active notifications
        """
        notifications = self._get_notifications()
        active = []
        
        for notification in notifications:
            if not notification.dismissed and not notification.is_expired():
                active.append(notification)
        
        return active
    
    def cleanup_expired_notifications(self) -> None:
        """Remove expired notifications."""
        notifications = self._get_notifications()
        active_notifications = [n for n in notifications 
                              if not n.is_expired() or not n.dismissible]
        
        if len(active_notifications) != len(notifications):
            self._save_notifications(active_notifications)
            logger.debug(f"Cleaned up {len(notifications) - len(active_notifications)} expired notifications")
    
    def render_notifications(self) -> None:
        """Render all active notifications in the UI."""
        # Clean up expired notifications first
        self.cleanup_expired_notifications()
        
        active_notifications = self.get_active_notifications()
        
        for notification in active_notifications:
            self._render_notification(notification)
    
    def _render_notification(self, notification: Notification) -> None:
        """Render a single notification."""
        # Create container for notification
        container = st.container()
        
        with container:
            # Determine Streamlit function based on type
            if notification.type == NotificationType.SUCCESS:
                st_func = st.success
            elif notification.type == NotificationType.ERROR:
                st_func = st.error
            elif notification.type == NotificationType.WARNING:
                st_func = st.warning
            else:  # INFO
                st_func = st.info
            
            # Format message
            display_message = notification.message
            if notification.title:
                display_message = f"**{notification.title}**\n\n{display_message}"
            
            # Show notification
            st_func(display_message)
            
            # Add dismiss button if dismissible
            if notification.dismissible:
                col1, col2 = st.columns([4, 1])
                with col2:
                    if st.button("✕", key=f"dismiss_{notification.id}", 
                               help="Dismiss notification"):
                        self.dismiss_notification(notification.id)
                        st.rerun()
    
    def _get_notifications(self) -> List[Notification]:
        """Get notifications from session state."""
        if self.notifications_key not in st.session_state:
            return []
        
        notifications_data = st.session_state[self.notifications_key]
        return [Notification.from_dict(data) for data in notifications_data]
    
    def _save_notifications(self, notifications: List[Notification]) -> None:
        """Save notifications to session state."""
        notifications_data = [n.to_dict() for n in notifications]
        st.session_state[self.notifications_key] = notifications_data


def get_notification_manager() -> NotificationManager:
    """Get or create global notification manager."""
    if 'notification_manager' not in st.session_state:
        st.session_state.notification_manager = NotificationManager()
    
    return st.session_state.notification_manager


def show_success(message: str, title: Optional[str] = None,
                duration: Optional[timedelta] = None) -> str:
    """Show success notification."""
    return get_notification_manager().success(message, title, duration)


def show_error(message: str, title: Optional[str] = None,
              duration: Optional[timedelta] = None) -> str:
    """Show error notification."""
    return get_notification_manager().error(message, title, duration)


def show_warning(message: str, title: Optional[str] = None,
                duration: Optional[timedelta] = None) -> str:
    """Show warning notification."""
    return get_notification_manager().warning(message, title, duration)


def show_info(message: str, title: Optional[str] = None,
             duration: Optional[timedelta] = None) -> str:
    """Show info notification."""
    return get_notification_manager().info(message, title, duration)


def clear_notifications() -> None:
    """Clear all notifications."""
    get_notification_manager().clear_all_notifications()


def render_notifications() -> None:
    """Render all active notifications."""
    get_notification_manager().render_notifications()


# Context manager for handling operations with notifications
class NotificationContext:
    """Context manager for operations that need notification feedback."""
    
    def __init__(self, operation_name: str, success_message: Optional[str] = None,
                 error_message: Optional[str] = None):
        """
        Initialize notification context.
        
        Args:
            operation_name: Name of the operation
            success_message: Message to show on success
            error_message: Message to show on error
        """
        self.operation_name = operation_name
        self.success_message = success_message or f"{operation_name} completed successfully"
        self.error_message = error_message or f"{operation_name} failed"
        self.notification_manager = get_notification_manager()
    
    def __enter__(self):
        """Enter context."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context and show appropriate notification."""
        if exc_type is None:
            # Success
            self.notification_manager.success(self.success_message)
        else:
            # Error
            error_details = str(exc_val) if exc_val else "Unknown error"
            full_message = f"{self.error_message}: {error_details}"
            self.notification_manager.error(full_message)
        
        # Don't suppress exceptions
        return False