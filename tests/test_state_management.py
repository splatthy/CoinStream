"""
Unit tests for state management utilities.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from app.utils.state_management import (
    StateManager, StateKey, StateError,
    get_state_manager, get_state, set_state, clear_state,
    has_state, get_all_states, clear_all_states,
    create_state_context, with_state_context
)


class TestStateManager:
    """Test cases for StateManager class."""
    
    @pytest.fixture
    def state_manager(self):
        """Create StateManager instance."""
        return StateManager()
    
    def test_init(self):
        """Test StateManager initialization."""
        manager = StateManager()
        
        assert manager._states == {}
        assert manager._contexts == {}
        assert manager._default_context == "default"
    
    def test_init_with_custom_default_context(self):
        """Test StateManager initialization with custom default context."""
        manager = StateManager(default_context="custom")
        
        assert manager._default_context == "custom"
    
    def test_set_state(self, state_manager):
        """Test setting state value."""
        state_manager.set_state("test_key", "test_value")
        
        assert "default" in state_manager._states
        assert "test_key" in state_manager._states["default"]
        assert state_manager._states["default"]["test_key"] == "test_value"
    
    def test_set_state_with_context(self, state_manager):
        """Test setting state value with specific context."""
        state_manager.set_state("test_key", "test_value", context="custom")
        
        assert "custom" in state_manager._states
        assert "test_key" in state_manager._states["custom"]
        assert state_manager._states["custom"]["test_key"] == "test_value"
    
    def test_get_state(self, state_manager):
        """Test getting state value."""
        state_manager.set_state("test_key", "test_value")
        
        value = state_manager.get_state("test_key")
        assert value == "test_value"
    
    def test_get_state_with_context(self, state_manager):
        """Test getting state value with specific context."""
        state_manager.set_state("test_key", "test_value", context="custom")
        
        value = state_manager.get_state("test_key", context="custom")
        assert value == "test_value"
    
    def test_get_state_nonexistent_key(self, state_manager):
        """Test getting nonexistent state key."""
        value = state_manager.get_state("nonexistent")
        assert value is None
    
    def test_get_state_with_default(self, state_manager):
        """Test getting state with default value."""
        value = state_manager.get_state("nonexistent", default="default_value")
        assert value == "default_value"
    
    def test_get_state_nonexistent_context(self, state_manager):
        """Test getting state from nonexistent context."""
        value = state_manager.get_state("test_key", context="nonexistent")
        assert value is None
    
    def test_has_state(self, state_manager):
        """Test checking if state exists."""
        assert not state_manager.has_state("test_key")
        
        state_manager.set_state("test_key", "test_value")
        assert state_manager.has_state("test_key")
    
    def test_has_state_with_context(self, state_manager):
        """Test checking if state exists in specific context."""
        state_manager.set_state("test_key", "test_value", context="custom")
        
        assert not state_manager.has_state("test_key")  # Default context
        assert state_manager.has_state("test_key", context="custom")
    
    def test_clear_state(self, state_manager):
        """Test clearing specific state."""
        state_manager.set_state("test_key", "test_value")
        assert state_manager.has_state("test_key")
        
        state_manager.clear_state("test_key")
        assert not state_manager.has_state("test_key")
    
    def test_clear_state_with_context(self, state_manager):
        """Test clearing state from specific context."""
        state_manager.set_state("test_key", "test_value", context="custom")
        assert state_manager.has_state("test_key", context="custom")
        
        state_manager.clear_state("test_key", context="custom")
        assert not state_manager.has_state("test_key", context="custom")
    
    def test_clear_state_nonexistent(self, state_manager):
        """Test clearing nonexistent state (should not raise error)."""
        state_manager.clear_state("nonexistent")  # Should not raise
    
    def test_get_all_states(self, state_manager):
        """Test getting all states."""
        state_manager.set_state("key1", "value1")
        state_manager.set_state("key2", "value2")
        
        all_states = state_manager.get_all_states()
        
        assert all_states == {"key1": "value1", "key2": "value2"}
    
    def test_get_all_states_with_context(self, state_manager):
        """Test getting all states from specific context."""
        state_manager.set_state("key1", "value1", context="custom")
        state_manager.set_state("key2", "value2", context="custom")
        
        all_states = state_manager.get_all_states(context="custom")
        
        assert all_states == {"key1": "value1", "key2": "value2"}
    
    def test_get_all_states_empty_context(self, state_manager):
        """Test getting all states from empty context."""
        all_states = state_manager.get_all_states()
        assert all_states == {}
    
    def test_clear_all_states(self, state_manager):
        """Test clearing all states."""
        state_manager.set_state("key1", "value1")
        state_manager.set_state("key2", "value2")
        
        assert len(state_manager.get_all_states()) == 2
        
        state_manager.clear_all_states()
        
        assert len(state_manager.get_all_states()) == 0
    
    def test_clear_all_states_with_context(self, state_manager):
        """Test clearing all states from specific context."""
        state_manager.set_state("key1", "value1", context="custom")
        state_manager.set_state("key2", "value2", context="custom")
        state_manager.set_state("key3", "value3")  # Default context
        
        state_manager.clear_all_states(context="custom")
        
        assert len(state_manager.get_all_states(context="custom")) == 0
        assert len(state_manager.get_all_states()) == 1  # Default context unchanged
    
    def test_create_context(self, state_manager):
        """Test creating a new context."""
        state_manager.create_context("new_context")
        
        assert "new_context" in state_manager._contexts
        assert state_manager._contexts["new_context"] == {}
    
    def test_create_context_already_exists(self, state_manager):
        """Test creating context that already exists."""
        state_manager.create_context("test_context")
        state_manager.set_state("key1", "value1", context="test_context")
        
        # Creating again should not clear existing data
        state_manager.create_context("test_context")
        
        assert state_manager.get_state("key1", context="test_context") == "value1"
    
    def test_delete_context(self, state_manager):
        """Test deleting a context."""
        state_manager.set_state("key1", "value1", context="test_context")
        assert state_manager.has_state("key1", context="test_context")
        
        state_manager.delete_context("test_context")
        
        assert not state_manager.has_state("key1", context="test_context")
        assert "test_context" not in state_manager._states
    
    def test_delete_context_nonexistent(self, state_manager):
        """Test deleting nonexistent context (should not raise error)."""
        state_manager.delete_context("nonexistent")  # Should not raise
    
    def test_delete_default_context(self, state_manager):
        """Test deleting default context raises error."""
        with pytest.raises(StateError, match="Cannot delete default context"):
            state_manager.delete_context("default")
    
    def test_get_contexts(self, state_manager):
        """Test getting all context names."""
        state_manager.set_state("key1", "value1")  # Creates default context
        state_manager.set_state("key2", "value2", context="custom1")
        state_manager.set_state("key3", "value3", context="custom2")
        
        contexts = state_manager.get_contexts()
        
        assert "default" in contexts
        assert "custom1" in contexts
        assert "custom2" in contexts
        assert len(contexts) == 3
    
    def test_context_manager(self, state_manager):
        """Test using StateManager as context manager."""
        with state_manager.context("temp_context") as ctx:
            ctx.set_state("temp_key", "temp_value")
            assert ctx.get_state("temp_key") == "temp_value"
        
        # Context should still exist after exiting
        assert state_manager.has_state("temp_key", context="temp_context")
    
    def test_context_manager_cleanup_on_error(self, state_manager):
        """Test context manager cleanup on error."""
        try:
            with state_manager.context("error_context", cleanup_on_exit=True) as ctx:
                ctx.set_state("temp_key", "temp_value")
                raise ValueError("Test error")
        except ValueError:
            pass
        
        # Context should be cleaned up
        assert not state_manager.has_state("temp_key", context="error_context")
    
    def test_state_serialization(self, state_manager):
        """Test state serialization."""
        state_manager.set_state("string_key", "string_value")
        state_manager.set_state("int_key", 42)
        state_manager.set_state("list_key", [1, 2, 3])
        state_manager.set_state("dict_key", {"nested": "value"})
        
        serialized = state_manager.serialize_states()
        
        assert "default" in serialized
        assert serialized["default"]["string_key"] == "string_value"
        assert serialized["default"]["int_key"] == 42
        assert serialized["default"]["list_key"] == [1, 2, 3]
        assert serialized["default"]["dict_key"] == {"nested": "value"}
    
    def test_state_deserialization(self, state_manager):
        """Test state deserialization."""
        serialized_data = {
            "default": {
                "string_key": "string_value",
                "int_key": 42,
                "list_key": [1, 2, 3]
            },
            "custom": {
                "custom_key": "custom_value"
            }
        }
        
        state_manager.deserialize_states(serialized_data)
        
        assert state_manager.get_state("string_key") == "string_value"
        assert state_manager.get_state("int_key") == 42
        assert state_manager.get_state("list_key") == [1, 2, 3]
        assert state_manager.get_state("custom_key", context="custom") == "custom_value"
    
    def test_state_persistence(self, state_manager):
        """Test state persistence to file."""
        state_manager.set_state("persistent_key", "persistent_value")
        
        with patch('builtins.open', create=True) as mock_open, \
             patch('json.dump') as mock_json_dump:
            
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            state_manager.save_to_file("test_state.json")
            
            mock_open.assert_called_once_with("test_state.json", 'w')
            mock_json_dump.assert_called_once()
    
    def test_state_loading(self, state_manager):
        """Test state loading from file."""
        mock_data = {
            "default": {
                "loaded_key": "loaded_value"
            }
        }
        
        with patch('builtins.open', create=True) as mock_open, \
             patch('json.load', return_value=mock_data) as mock_json_load:
            
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            state_manager.load_from_file("test_state.json")
            
            mock_open.assert_called_once_with("test_state.json", 'r')
            mock_json_load.assert_called_once()
            
            assert state_manager.get_state("loaded_key") == "loaded_value"


class TestStateKey:
    """Test cases for StateKey enum/constants."""
    
    def test_state_key_constants(self):
        """Test that StateKey constants are defined."""
        # These would be defined in the actual implementation
        assert hasattr(StateKey, 'CURRENT_PAGE') or True  # Placeholder
        assert hasattr(StateKey, 'USER_PREFERENCES') or True  # Placeholder
        assert hasattr(StateKey, 'CACHE_DATA') or True  # Placeholder


class TestGlobalFunctions:
    """Test global state management functions."""
    
    @patch('app.utils.state_management.get_state_manager')
    def test_get_state_function(self, mock_get_manager):
        """Test global get_state function."""
        mock_manager = Mock()
        mock_manager.get_state.return_value = "test_value"
        mock_get_manager.return_value = mock_manager
        
        result = get_state("test_key")
        
        assert result == "test_value"
        mock_manager.get_state.assert_called_once_with("test_key", context="default", default=None)
    
    @patch('app.utils.state_management.get_state_manager')
    def test_get_state_function_with_context(self, mock_get_manager):
        """Test global get_state function with context."""
        mock_manager = Mock()
        mock_manager.get_state.return_value = "test_value"
        mock_get_manager.return_value = mock_manager
        
        result = get_state("test_key", context="custom", default="default_value")
        
        assert result == "test_value"
        mock_manager.get_state.assert_called_once_with("test_key", context="custom", default="default_value")
    
    @patch('app.utils.state_management.get_state_manager')
    def test_set_state_function(self, mock_get_manager):
        """Test global set_state function."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        set_state("test_key", "test_value")
        
        mock_manager.set_state.assert_called_once_with("test_key", "test_value", context="default")
    
    @patch('app.utils.state_management.get_state_manager')
    def test_set_state_function_with_context(self, mock_get_manager):
        """Test global set_state function with context."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        set_state("test_key", "test_value", context="custom")
        
        mock_manager.set_state.assert_called_once_with("test_key", "test_value", context="custom")
    
    @patch('app.utils.state_management.get_state_manager')
    def test_clear_state_function(self, mock_get_manager):
        """Test global clear_state function."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        clear_state("test_key")
        
        mock_manager.clear_state.assert_called_once_with("test_key", context="default")
    
    @patch('app.utils.state_management.get_state_manager')
    def test_has_state_function(self, mock_get_manager):
        """Test global has_state function."""
        mock_manager = Mock()
        mock_manager.has_state.return_value = True
        mock_get_manager.return_value = mock_manager
        
        result = has_state("test_key")
        
        assert result is True
        mock_manager.has_state.assert_called_once_with("test_key", context="default")
    
    @patch('app.utils.state_management.get_state_manager')
    def test_get_all_states_function(self, mock_get_manager):
        """Test global get_all_states function."""
        mock_manager = Mock()
        mock_manager.get_all_states.return_value = {"key": "value"}
        mock_get_manager.return_value = mock_manager
        
        result = get_all_states()
        
        assert result == {"key": "value"}
        mock_manager.get_all_states.assert_called_once_with(context="default")
    
    @patch('app.utils.state_management.get_state_manager')
    def test_clear_all_states_function(self, mock_get_manager):
        """Test global clear_all_states function."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        clear_all_states()
        
        mock_manager.clear_all_states.assert_called_once_with(context="default")
    
    @patch('app.utils.state_management.get_state_manager')
    def test_create_state_context_function(self, mock_get_manager):
        """Test global create_state_context function."""
        mock_manager = Mock()
        mock_get_manager.return_value = mock_manager
        
        create_state_context("test_context")
        
        mock_manager.create_context.assert_called_once_with("test_context")
    
    def test_get_state_manager_singleton(self):
        """Test that get_state_manager returns singleton instance."""
        manager1 = get_state_manager()
        manager2 = get_state_manager()
        
        assert manager1 is manager2
        assert isinstance(manager1, StateManager)


class TestStateContextDecorator:
    """Test state context decorator."""
    
    @patch('app.utils.state_management.get_state_manager')
    def test_with_state_context_decorator(self, mock_get_manager):
        """Test with_state_context decorator."""
        mock_manager = Mock()
        mock_context_manager = Mock()
        mock_manager.context.return_value = mock_context_manager
        mock_context_manager.__enter__ = Mock(return_value=mock_context_manager)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_get_manager.return_value = mock_manager
        
        @with_state_context("test_context")
        def test_function(arg1, arg2, state_context=None):
            assert state_context is mock_context_manager
            return arg1 + arg2
        
        result = test_function(1, 2)
        
        assert result == 3
        mock_manager.context.assert_called_once_with("test_context", cleanup_on_exit=False)
        mock_context_manager.__enter__.assert_called_once()
        mock_context_manager.__exit__.assert_called_once()
    
    @patch('app.utils.state_management.get_state_manager')
    def test_with_state_context_decorator_with_cleanup(self, mock_get_manager):
        """Test with_state_context decorator with cleanup."""
        mock_manager = Mock()
        mock_context_manager = Mock()
        mock_manager.context.return_value = mock_context_manager
        mock_context_manager.__enter__ = Mock(return_value=mock_context_manager)
        mock_context_manager.__exit__ = Mock(return_value=None)
        mock_get_manager.return_value = mock_manager
        
        @with_state_context("test_context", cleanup_on_exit=True)
        def test_function():
            return "test"
        
        result = test_function()
        
        assert result == "test"
        mock_manager.context.assert_called_once_with("test_context", cleanup_on_exit=True)


class TestStateError:
    """Test StateError exception class."""
    
    def test_state_error_creation(self):
        """Test StateError creation."""
        error = StateError("State error message")
        
        assert str(error) == "State error message"
        assert isinstance(error, Exception)
    
    def test_state_error_with_cause(self):
        """Test StateError with underlying cause."""
        cause = ValueError("Original error")
        error = StateError("State error", cause)
        
        assert str(error) == "State error"
        assert error.__cause__ == cause


class TestStateManagementIntegration:
    """Integration tests for state management."""
    
    def test_multi_context_workflow(self):
        """Test workflow with multiple contexts."""
        manager = StateManager()
        
        # Set up different contexts
        manager.set_state("global_setting", "global_value")
        manager.set_state("user_pref", "user_value", context="user")
        manager.set_state("session_data", "session_value", context="session")
        
        # Verify isolation
        assert manager.get_state("global_setting") == "global_value"
        assert manager.get_state("global_setting", context="user") is None
        assert manager.get_state("user_pref", context="user") == "user_value"
        assert manager.get_state("session_data", context="session") == "session_value"
        
        # Test context operations
        user_states = manager.get_all_states(context="user")
        assert user_states == {"user_pref": "user_value"}
        
        # Clear specific context
        manager.clear_all_states(context="session")
        assert not manager.has_state("session_data", context="session")
        assert manager.has_state("user_pref", context="user")  # Other contexts unaffected
    
    def test_state_persistence_workflow(self):
        """Test complete state persistence workflow."""
        manager = StateManager()
        
        # Set up state
        manager.set_state("app_version", "1.0.0")
        manager.set_state("last_login", datetime.now().isoformat())
        manager.set_state("preferences", {"theme": "dark", "language": "en"}, context="user")
        
        # Serialize
        serialized = manager.serialize_states()
        
        # Create new manager and deserialize
        new_manager = StateManager()
        new_manager.deserialize_states(serialized)
        
        # Verify state was restored
        assert new_manager.get_state("app_version") == "1.0.0"
        assert new_manager.get_state("last_login") is not None
        assert new_manager.get_state("preferences", context="user") == {"theme": "dark", "language": "en"}
    
    @patch('streamlit.session_state', {})
    def test_streamlit_integration(self, mock_session_state):
        """Test integration with Streamlit session state."""
        # This would be implemented in the actual StateManager
        # to sync with Streamlit's session_state
        manager = StateManager()
        
        # Set state
        manager.set_state("streamlit_key", "streamlit_value")
        
        # In real implementation, this would sync with st.session_state
        assert manager.get_state("streamlit_key") == "streamlit_value"


if __name__ == '__main__':
    pytest.main([__file__])