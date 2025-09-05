"""
Unit tests for encryption utilities.
"""

import os
import tempfile
import pytest
from unittest.mock import patch, mock_open
from app.utils.encryption import (
    CredentialEncryption, 
    SecureStorage, 
    EncryptionError
)


class TestCredentialEncryption:
    """Test cases for CredentialEncryption class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.encryption = CredentialEncryption("test_master_key_123")
    
    def test_encrypt_decrypt_credential(self):
        """Test basic encryption and decryption."""
        original = "my_secret_api_key_12345"
        
        # Encrypt
        encrypted = self.encryption.encrypt_credential(original)
        assert encrypted != original
        assert len(encrypted) > 0
        
        # Decrypt
        decrypted = self.encryption.decrypt_credential(encrypted)
        assert decrypted == original
    
    def test_encrypt_empty_credential_raises_error(self):
        """Test that encrypting empty credential raises error."""
        with pytest.raises(EncryptionError, match="Credential cannot be empty"):
            self.encryption.encrypt_credential("")
        
        with pytest.raises(EncryptionError, match="Credential cannot be empty"):
            self.encryption.encrypt_credential("   ")
    
    def test_encrypt_non_string_raises_error(self):
        """Test that encrypting non-string raises error."""
        with pytest.raises(EncryptionError, match="Credential must be a string"):
            self.encryption.encrypt_credential(123)
        
        with pytest.raises(EncryptionError, match="Credential must be a string"):
            self.encryption.encrypt_credential(None)
    
    def test_decrypt_invalid_credential_raises_error(self):
        """Test that decrypting invalid credential raises error."""
        with pytest.raises(EncryptionError, match="Invalid base64 encoding"):
            self.encryption.decrypt_credential("invalid_base64!")
        
        with pytest.raises(EncryptionError, match="Invalid encrypted credential format"):
            self.encryption.decrypt_credential("dGVzdA==")  # Too short
    
    def test_decrypt_empty_credential_raises_error(self):
        """Test that decrypting empty credential raises error."""
        with pytest.raises(EncryptionError, match="Encrypted credential cannot be empty"):
            self.encryption.decrypt_credential("")
    
    def test_decrypt_non_string_raises_error(self):
        """Test that decrypting non-string raises error."""
        with pytest.raises(EncryptionError, match="Encrypted credential must be a string"):
            self.encryption.decrypt_credential(123)
    
    def test_different_encryptions_produce_different_results(self):
        """Test that same credential produces different encrypted results."""
        credential = "same_credential"
        
        encrypted1 = self.encryption.encrypt_credential(credential)
        encrypted2 = self.encryption.encrypt_credential(credential)
        
        # Should be different due to random salt and IV
        assert encrypted1 != encrypted2
        
        # But both should decrypt to same value
        assert self.encryption.decrypt_credential(encrypted1) == credential
        assert self.encryption.decrypt_credential(encrypted2) == credential
    
    def test_verify_master_key(self):
        """Test master key verification."""
        # Correct key should verify
        assert self.encryption.verify_master_key("test_master_key_123") is True
        
        # Wrong key should not verify
        assert self.encryption.verify_master_key("wrong_key") is False
        assert self.encryption.verify_master_key("") is False
    
    def test_change_master_key(self):
        """Test changing master key and re-encrypting credentials."""
        # Create some encrypted credentials
        credentials = {
            "api_key_1": "secret_key_1",
            "api_key_2": "secret_key_2"
        }
        
        encrypted_creds = {}
        for key, value in credentials.items():
            encrypted_creds[key] = self.encryption.encrypt_credential(value)
        
        # Change master key
        new_key = "new_master_key_456"
        re_encrypted = self.encryption.change_master_key(
            "test_master_key_123", 
            new_key, 
            encrypted_creds
        )
        
        # Verify re-encrypted credentials can be decrypted with new key
        new_encryption = CredentialEncryption(new_key)
        for key, original_value in credentials.items():
            decrypted = new_encryption.decrypt_credential(re_encrypted[key])
            assert decrypted == original_value
    
    def test_change_master_key_invalid_old_key(self):
        """Test changing master key with invalid old key."""
        # Create a credential with the correct key first
        encrypted_cred = self.encryption.encrypt_credential("test_value")
        credentials = {"test_key": encrypted_cred}
        
        with pytest.raises(EncryptionError, match="Invalid old master key"):
            self.encryption.change_master_key("wrong_key", "new_key", credentials)
    
    def test_generate_secure_token(self):
        """Test secure token generation."""
        # Default length
        token1 = self.encryption.generate_secure_token()
        token2 = self.encryption.generate_secure_token()
        
        assert len(token1) > 0
        assert len(token2) > 0
        assert token1 != token2  # Should be different
        
        # Custom length
        token_16 = self.encryption.generate_secure_token(16)
        token_64 = self.encryption.generate_secure_token(64)
        
        # Base64 encoding makes output longer than input
        assert len(token_16) > 16
        assert len(token_64) > len(token_16)
    
    def test_generate_secure_token_invalid_length(self):
        """Test secure token generation with invalid lengths."""
        with pytest.raises(EncryptionError, match="Token length must be at least 16 bytes"):
            self.encryption.generate_secure_token(8)
        
        with pytest.raises(EncryptionError, match="Token length must be at most 256 bytes"):
            self.encryption.generate_secure_token(300)
    
    def test_hash_data(self):
        """Test data hashing."""
        data = "test_data_to_hash"
        
        # Hash with generated salt
        hash1, salt1 = self.encryption.hash_data(data)
        hash2, salt2 = self.encryption.hash_data(data)
        
        assert hash1 != hash2  # Different due to different salts
        assert salt1 != salt2
        
        # Hash with same salt should produce same hash
        salt_bytes = os.urandom(16)
        hash3, salt3 = self.encryption.hash_data(data, salt_bytes)
        hash4, salt4 = self.encryption.hash_data(data, salt_bytes)
        
        assert hash3 == hash4
        assert salt3 == salt4
    
    def test_hash_data_non_string_raises_error(self):
        """Test that hashing non-string raises error."""
        with pytest.raises(EncryptionError, match="Data must be a string"):
            self.encryption.hash_data(123)
    
    def test_verify_hash(self):
        """Test hash verification."""
        data = "test_data_to_verify"
        hash_value, salt = self.encryption.hash_data(data)
        
        # Correct data should verify
        assert self.encryption.verify_hash(data, hash_value, salt) is True
        
        # Wrong data should not verify
        assert self.encryption.verify_hash("wrong_data", hash_value, salt) is False
        
        # Wrong hash should not verify
        wrong_hash, _ = self.encryption.hash_data("other_data")
        assert self.encryption.verify_hash(data, wrong_hash, salt) is False
    
    def test_verify_hash_invalid_input(self):
        """Test hash verification with invalid input."""
        # Invalid base64 should return False
        assert self.encryption.verify_hash("data", "invalid_hash!", "invalid_salt!") is False


class TestSecureStorage:
    """Test cases for SecureStorage class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.encryption = CredentialEncryption("test_master_key")
        self.storage = SecureStorage(self.temp_dir, self.encryption)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_store_and_retrieve_credential(self):
        """Test storing and retrieving credentials."""
        key = "test_api_key"
        credential = "secret_api_key_value"
        
        # Store credential
        self.storage.store_credential(key, credential)
        
        # Verify file exists
        file_path = os.path.join(self.temp_dir, f"{key}.enc")
        assert os.path.exists(file_path)
        
        # Retrieve credential
        retrieved = self.storage.retrieve_credential(key)
        assert retrieved == credential
    
    def test_retrieve_nonexistent_credential(self):
        """Test retrieving non-existent credential returns None."""
        result = self.storage.retrieve_credential("nonexistent_key")
        assert result is None
    
    def test_delete_credential(self):
        """Test deleting credentials."""
        key = "test_key_to_delete"
        credential = "test_credential"
        
        # Store credential
        self.storage.store_credential(key, credential)
        assert self.storage.credential_exists(key) is True
        
        # Delete credential
        result = self.storage.delete_credential(key)
        assert result is True
        assert self.storage.credential_exists(key) is False
        
        # Delete non-existent credential
        result = self.storage.delete_credential("nonexistent")
        assert result is False
    
    def test_list_credentials(self):
        """Test listing stored credentials."""
        # Initially empty
        assert self.storage.list_credentials() == []
        
        # Store some credentials
        credentials = ["key1", "key2", "key3"]
        for key in credentials:
            self.storage.store_credential(key, f"value_{key}")
        
        # List should contain all keys
        stored_keys = self.storage.list_credentials()
        assert set(stored_keys) == set(credentials)
    
    def test_credential_exists(self):
        """Test checking if credential exists."""
        key = "existence_test_key"
        
        # Should not exist initially
        assert self.storage.credential_exists(key) is False
        
        # Store credential
        self.storage.store_credential(key, "test_value")
        
        # Should exist now
        assert self.storage.credential_exists(key) is True
    
    def test_file_permissions(self):
        """Test that stored files have correct permissions."""
        key = "permission_test_key"
        self.storage.store_credential(key, "test_value")
        
        file_path = os.path.join(self.temp_dir, f"{key}.enc")
        file_stat = os.stat(file_path)
        
        # Should be readable/writable by owner only (0o600)
        assert oct(file_stat.st_mode)[-3:] == '600'
    
    @patch('builtins.open', side_effect=IOError("Permission denied"))
    def test_store_credential_io_error(self, mock_file):
        """Test handling of IO errors during storage."""
        with pytest.raises(EncryptionError, match="Failed to store credential"):
            self.storage.store_credential("test_key", "test_value")
    
    def test_retrieve_credential_io_error(self):
        """Test handling of IO errors during retrieval."""
        # First create a credential file
        key = "test_key"
        self.storage.store_credential(key, "test_value")
        
        # Now mock open to raise an error when reading
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            with pytest.raises(EncryptionError, match="Failed to retrieve credential"):
                self.storage.retrieve_credential(key)
    
    def test_storage_directory_creation(self):
        """Test that storage directory is created if it doesn't exist."""
        new_dir = os.path.join(self.temp_dir, "new_storage_dir")
        assert not os.path.exists(new_dir)
        
        # Creating SecureStorage should create the directory
        new_storage = SecureStorage(new_dir)
        assert os.path.exists(new_dir)
        assert os.path.isdir(new_dir)


class TestEncryptionIntegration:
    """Integration tests for encryption components."""
    
    def test_end_to_end_credential_management(self):
        """Test complete credential management workflow."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Initialize storage
            storage = SecureStorage(temp_dir)
            
            # Store multiple credentials
            credentials = {
                "bitunix_api_key": "bitunix_secret_key_12345",
                "binance_api_key": "binance_secret_key_67890",
                "coinbase_api_key": "coinbase_secret_key_abcde"
            }
            
            for key, value in credentials.items():
                storage.store_credential(key, value)
            
            # Verify all credentials can be retrieved
            for key, expected_value in credentials.items():
                retrieved_value = storage.retrieve_credential(key)
                assert retrieved_value == expected_value
            
            # Verify listing works
            stored_keys = storage.list_credentials()
            assert set(stored_keys) == set(credentials.keys())
            
            # Delete one credential
            storage.delete_credential("binance_api_key")
            assert not storage.credential_exists("binance_api_key")
            
            # Verify others still exist
            assert storage.credential_exists("bitunix_api_key")
            assert storage.credential_exists("coinbase_api_key")
    
    def test_encryption_with_different_master_keys(self):
        """Test that different master keys produce different results."""
        credential = "same_secret_value"
        
        encryption1 = CredentialEncryption("master_key_1")
        encryption2 = CredentialEncryption("master_key_2")
        
        encrypted1 = encryption1.encrypt_credential(credential)
        encrypted2 = encryption2.encrypt_credential(credential)
        
        # Different master keys should produce different encrypted results
        assert encrypted1 != encrypted2
        
        # Each should decrypt correctly with its own key
        assert encryption1.decrypt_credential(encrypted1) == credential
        assert encryption2.decrypt_credential(encrypted2) == credential
        
        # But not with the other key
        with pytest.raises(EncryptionError):
            encryption1.decrypt_credential(encrypted2)
        
        with pytest.raises(EncryptionError):
            encryption2.decrypt_credential(encrypted1)