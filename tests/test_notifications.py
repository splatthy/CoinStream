"""
Core unit tests for notification utilities (without Streamlit dependencies).
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

from app.utils.notifications import NotificationType, Notification


class TestNotification:
    """Test cases for Notification class."""
    
    def test_notification_creation(self):
        """Test creating a notification."""
        notification = Notification(
            message="Test message",
            notification_type=NotificationType.SUCCESS,
            title="Test Title",
            duration=timedelta(seconds=5)
        )
        
        assert notification.message == "Test message"
        assert notification.type == NotificationType.SUCCESS
        assert notification.title == "Test Title"
        assert notification.duration == timedelta(seconds=5)
        assert notification.dismissible is True
        assert notification.dismissed is False
        assert notification.id is not None
        assert notification.created_at is not None
    
    def test_notification_defaults(self):
        """Test notification with default values."""
        notification = Notification(
            message="Test message",
            notification_type=NotificationType.INFO
        )
        
        assert notification.message == "Test message"
        assert notification.type == NotificationType.INFO
        assert notification.title is None
        assert notification.duration is None
        assert notification.dismissible is True
        assert notification.dismissed is False
    
    def test_notification_expiration(self):
        """Test notification expiration logic."""
        # Non-expiring notification (no duration)
        notification = Notification(
            message="Permanent message",
            notification_type=NotificationType.INFO
        )
        assert not notification.is_expired()
        
        # Non-expired notification
        notification = Notification(
            message="Recent message",
            notification_type=NotificationType.INFO,
            duration=timedelta(seconds=60)  # 1 minute duration
        )
        assert not notification.is_expired()
        
        # Simulate expired notification by setting old creation time
        notification.created_at = datetime.now() - timedelta(seconds=120)  # 2 minutes ago
        assert notification.is_expired()
    
    def test_notification_to_dict(self):
        """Test converting notification to dictionary."""
        notification = Notification(
            message="Test message",
            notification_type=NotificationType.SUCCESS,
            title="Test Title",
            duration=timedelta(seconds=5),
            dismissible=False
        )
        
        data = notification.to_dict()
        
        assert data['message'] == "Test message"
        assert data['type'] == "success"
        assert data['title'] == "Test Title"
        assert data['duration'] == 5.0
        assert data['dismissible'] is False
        assert data['dismissed'] is False
        assert 'id' in data
        assert 'created_at' in data
    
    def test_notification_from_dict(self):
        """Test creating notification from dictionary."""
        data = {
            'id': 'test_id_123',
            'message': "Test message",
            'type': "error",
            'title': "Error Title",
            'created_at': "2024-01-01T12:00:00",
            'duration': 10.0,
            'dismissible': True,
            'dismissed': True
        }
        
        notification = Notification.from_dict(data)
        
        assert notification.id == 'test_id_123'
        assert notification.message == "Test message"
        assert notification.type == NotificationType.ERROR
        assert notification.title == "Error Title"
        assert notification.created_at == datetime(2024, 1, 1, 12, 0, 0)
        assert notification.duration == timedelta(seconds=10.0)
        assert notification.dismissible is True
        assert notification.dismissed is True
    
    def test_notification_from_dict_minimal(self):
        """Test creating notification from minimal dictionary."""
        data = {
            'id': 'minimal_id',
            'message': "Minimal message",
            'type': "info",
            'created_at': "2024-01-01T12:00:00"
        }
        
        notification = Notification.from_dict(data)
        
        assert notification.id == 'minimal_id'
        assert notification.message == "Minimal message"
        assert notification.type == NotificationType.INFO
        assert notification.title is None
        assert notification.duration is None
        assert notification.dismissible is True  # Default
        assert notification.dismissed is False  # Default


class TestNotificationTypes:
    """Test notification type enum."""
    
    def test_notification_type_values(self):
        """Test NotificationType enum values."""
        assert NotificationType.SUCCESS.value == "success"
        assert NotificationType.ERROR.value == "error"
        assert NotificationType.WARNING.value == "warning"
        assert NotificationType.INFO.value == "info"
    
    def test_notification_type_from_string(self):
        """Test creating NotificationType from string."""
        assert NotificationType("success") == NotificationType.SUCCESS
        assert NotificationType("error") == NotificationType.ERROR
        assert NotificationType("warning") == NotificationType.WARNING
        assert NotificationType("info") == NotificationType.INFO
    
    def test_notification_type_invalid_string(self):
        """Test creating NotificationType from invalid string."""
        with pytest.raises(ValueError):
            NotificationType("invalid_type")


class TestNotificationLogic:
    """Test notification business logic."""
    
    def test_notification_id_uniqueness(self):
        """Test that notification IDs are unique."""
        notification1 = Notification("Message 1", NotificationType.INFO)
        notification2 = Notification("Message 2", NotificationType.INFO)
        
        assert notification1.id != notification2.id
    
    def test_notification_creation_time(self):
        """Test that notification creation time is set correctly."""
        before_creation = datetime.now()
        notification = Notification("Test message", NotificationType.INFO)
        after_creation = datetime.now()
        
        assert before_creation <= notification.created_at <= after_creation
    
    def test_notification_duration_types(self):
        """Test different duration types."""
        # No duration (permanent)
        notification1 = Notification("Permanent", NotificationType.INFO)
        assert notification1.duration is None
        assert not notification1.is_expired()
        
        # Short duration
        notification2 = Notification(
            "Short", 
            NotificationType.INFO, 
            duration=timedelta(milliseconds=1)
        )
        # Wait a bit to ensure expiration
        import time
        time.sleep(0.002)
        assert notification2.is_expired()
        
        # Long duration
        notification3 = Notification(
            "Long", 
            NotificationType.INFO, 
            duration=timedelta(hours=1)
        )
        assert not notification3.is_expired()
    
    def test_notification_serialization_roundtrip(self):
        """Test that serialization and deserialization preserve data."""
        original = Notification(
            message="Roundtrip test",
            notification_type=NotificationType.WARNING,
            title="Warning Title",
            duration=timedelta(seconds=30),
            dismissible=False
        )
        original.dismissed = True  # Modify state
        
        # Serialize to dict
        data = original.to_dict()
        
        # Deserialize from dict
        restored = Notification.from_dict(data)
        
        # Compare all fields
        assert restored.id == original.id
        assert restored.message == original.message
        assert restored.type == original.type
        assert restored.title == original.title
        assert restored.created_at == original.created_at
        assert restored.duration == original.duration
        assert restored.dismissible == original.dismissible
        assert restored.dismissed == original.dismissed


if __name__ == '__main__':
    pytest.main([__file__])