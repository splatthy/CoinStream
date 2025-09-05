"""
Encryption utilities for secure credential storage and data protection.
"""

import os
import base64
import hashlib
from typing import Optional, Union
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature


class EncryptionError(Exception):
    """Custom exception for encryption-related errors."""
    pass


class CredentialEncryption:
    """
    Handles encryption and decryption of sensitive credentials using AES-256.
    Uses PBKDF2 for key derivation from a master password.
    """
    
    def __init__(self, master_key: Optional[str] = None):
        """
        Initialize the encryption system.
        
        Args:
            master_key: Master key for encryption. If None, will be generated or loaded.
        """
        self._backend = default_backend()
        self._master_key = master_key
        self._derived_key: Optional[bytes] = None
    
    def _get_or_create_master_key(self) -> str:
        """Get existing master key or create a new one."""
        if self._master_key:
            return self._master_key
        
        # In production, this should be provided by user or environment
        # For now, generate a random key and store it securely
        master_key = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8')
        self._master_key = master_key
        return master_key
    
    def _derive_key(self, salt: bytes, password: str) -> bytes:
        """
        Derive encryption key from password using PBKDF2.
        
        Args:
            salt: Salt for key derivation
            password: Master password
            
        Returns:
            Derived encryption key
        """
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits for AES-256
            salt=salt,
            iterations=100000,  # OWASP recommended minimum
            backend=self._backend
        )
        return kdf.derive(password.encode('utf-8'))
    
    def encrypt_credential(self, credential: str) -> str:
        """
        Encrypt a credential string.
        
        Args:
            credential: The credential to encrypt
            
        Returns:
            Base64-encoded encrypted credential with salt and IV
            
        Raises:
            EncryptionError: If encryption fails
        """
        try:
            if not isinstance(credential, str):
                raise EncryptionError("Credential must be a string")
            
            if not credential.strip():
                raise EncryptionError("Credential cannot be empty")
            
            # Generate random salt and IV
            salt = os.urandom(16)  # 128 bits
            iv = os.urandom(16)    # 128 bits for AES
            
            # Derive key from master password
            master_key = self._get_or_create_master_key()
            key = self._derive_key(salt, master_key)
            
            # Encrypt the credential
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=self._backend
            )
            encryptor = cipher.encryptor()
            
            # Pad the credential to block size (16 bytes for AES)
            credential_bytes = credential.encode('utf-8')
            padding_length = 16 - (len(credential_bytes) % 16)
            padded_credential = credential_bytes + bytes([padding_length] * padding_length)
            
            encrypted_data = encryptor.update(padded_credential) + encryptor.finalize()
            
            # Combine salt + IV + encrypted data and encode
            combined = salt + iv + encrypted_data
            return base64.urlsafe_b64encode(combined).decode('utf-8')
            
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt credential: {str(e)}")
    
    def decrypt_credential(self, encrypted_credential: str) -> str:
        """
        Decrypt an encrypted credential.
        
        Args:
            encrypted_credential: Base64-encoded encrypted credential
            
        Returns:
            Decrypted credential string
            
        Raises:
            EncryptionError: If decryption fails
        """
        try:
            if not isinstance(encrypted_credential, str):
                raise EncryptionError("Encrypted credential must be a string")
            
            if not encrypted_credential.strip():
                raise EncryptionError("Encrypted credential cannot be empty")
            
            # Decode from base64
            try:
                combined = base64.urlsafe_b64decode(encrypted_credential.encode('utf-8'))
            except Exception:
                raise EncryptionError("Invalid base64 encoding")
            
            if len(combined) < 48:  # 16 (salt) + 16 (IV) + 16 (min encrypted data)
                raise EncryptionError("Invalid encrypted credential format")
            
            # Extract salt, IV, and encrypted data
            salt = combined[:16]
            iv = combined[16:32]
            encrypted_data = combined[32:]
            
            # Derive key from master password
            master_key = self._get_or_create_master_key()
            key = self._derive_key(salt, master_key)
            
            # Decrypt the data
            cipher = Cipher(
                algorithms.AES(key),
                modes.CBC(iv),
                backend=self._backend
            )
            decryptor = cipher.decryptor()
            
            padded_credential = decryptor.update(encrypted_data) + decryptor.finalize()
            
            # Remove padding
            padding_length = padded_credential[-1]
            if padding_length > 16 or padding_length == 0:
                raise EncryptionError("Invalid padding")
            
            credential_bytes = padded_credential[:-padding_length]
            return credential_bytes.decode('utf-8')
            
        except EncryptionError:
            raise
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt credential: {str(e)}")
    
    def verify_master_key(self, test_key: str) -> bool:
        """
        Verify if the provided key matches the master key.
        
        Args:
            test_key: Key to test
            
        Returns:
            True if key matches, False otherwise
        """
        try:
            # Create a test encryption/decryption cycle
            test_data = "test_verification_string"
            
            # Create a temporary encryption instance with the test key
            temp_encryption = CredentialEncryption(test_key)
            encrypted = temp_encryption.encrypt_credential(test_data)
            
            # Try to decrypt with current instance
            decrypted = self.decrypt_credential(encrypted)
            return decrypted == test_data
            
        except Exception:
            return False
    
    def change_master_key(self, old_key: str, new_key: str, encrypted_credentials: dict) -> dict:
        """
        Change the master key and re-encrypt all credentials.
        
        Args:
            old_key: Current master key
            new_key: New master key
            encrypted_credentials: Dictionary of encrypted credentials
            
        Returns:
            Dictionary with re-encrypted credentials
            
        Raises:
            EncryptionError: If key change fails
        """
        try:
            # Create encryption instances for old and new keys
            old_encryption = CredentialEncryption(old_key)
            new_encryption = CredentialEncryption(new_key)
            
            # Verify old key by trying to decrypt one credential
            if encrypted_credentials:
                test_key = next(iter(encrypted_credentials))
                try:
                    old_encryption.decrypt_credential(encrypted_credentials[test_key])
                except Exception:
                    raise EncryptionError("Invalid old master key")
            
            # Decrypt all credentials with old key and re-encrypt with new key
            re_encrypted_credentials = {}
            decrypted_credentials = {}
            
            for key, encrypted_value in encrypted_credentials.items():
                decrypted_value = old_encryption.decrypt_credential(encrypted_value)
                decrypted_credentials[key] = decrypted_value
                re_encrypted_credentials[key] = new_encryption.encrypt_credential(decrypted_value)
            
            # Clear decrypted data from memory
            for key in decrypted_credentials:
                decrypted_credentials[key] = "0" * len(decrypted_credentials[key])
            
            # Update this instance's master key
            self._master_key = new_key
            
            return re_encrypted_credentials
            
        except EncryptionError:
            raise
        except Exception as e:
            raise EncryptionError(f"Failed to change master key: {str(e)}")
    
    def generate_secure_token(self, length: int = 32) -> str:
        """
        Generate a cryptographically secure random token.
        
        Args:
            length: Length of the token in bytes
            
        Returns:
            Base64-encoded secure token
        """
        if length < 16:
            raise EncryptionError("Token length must be at least 16 bytes")
        
        if length > 256:
            raise EncryptionError("Token length must be at most 256 bytes")
        
        token_bytes = os.urandom(length)
        return base64.urlsafe_b64encode(token_bytes).decode('utf-8')
    
    def hash_data(self, data: str, salt: Optional[bytes] = None) -> tuple:
        """
        Hash data using SHA-256 with salt.
        
        Args:
            data: Data to hash
            salt: Optional salt (generated if not provided)
            
        Returns:
            Tuple of (hash, salt) both as base64 strings
        """
        if not isinstance(data, str):
            raise EncryptionError("Data must be a string")
        
        if salt is None:
            salt = os.urandom(16)
        
        digest = hashes.Hash(hashes.SHA256(), backend=self._backend)
        digest.update(salt)
        digest.update(data.encode('utf-8'))
        hash_bytes = digest.finalize()
        
        return (
            base64.urlsafe_b64encode(hash_bytes).decode('utf-8'),
            base64.urlsafe_b64encode(salt).decode('utf-8')
        )
    
    def verify_hash(self, data: str, hash_b64: str, salt_b64: str) -> bool:
        """
        Verify data against a hash.
        
        Args:
            data: Original data
            hash_b64: Base64-encoded hash
            salt_b64: Base64-encoded salt
            
        Returns:
            True if data matches hash, False otherwise
        """
        try:
            salt = base64.urlsafe_b64decode(salt_b64.encode('utf-8'))
            expected_hash, _ = self.hash_data(data, salt)
            return expected_hash == hash_b64
        except Exception:
            return False


class SecureStorage:
    """
    Secure storage manager for encrypted credentials and sensitive data.
    """
    
    def __init__(self, storage_path: str, encryption: Optional[CredentialEncryption] = None):
        """
        Initialize secure storage.
        
        Args:
            storage_path: Path to storage directory
            encryption: Encryption instance (created if not provided)
        """
        self.storage_path = storage_path
        self.encryption = encryption or CredentialEncryption()
        
        # Ensure storage directory exists
        os.makedirs(storage_path, exist_ok=True)
    
    def store_credential(self, key: str, credential: str) -> None:
        """
        Store an encrypted credential.
        
        Args:
            key: Identifier for the credential
            credential: The credential to store
            
        Raises:
            EncryptionError: If storage fails
        """
        try:
            encrypted = self.encryption.encrypt_credential(credential)
            
            # Store in a secure file
            file_path = os.path.join(self.storage_path, f"{key}.enc")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(encrypted)
            
            # Set restrictive permissions (owner read/write only)
            os.chmod(file_path, 0o600)
            
        except Exception as e:
            raise EncryptionError(f"Failed to store credential '{key}': {str(e)}")
    
    def retrieve_credential(self, key: str) -> Optional[str]:
        """
        Retrieve and decrypt a credential.
        
        Args:
            key: Identifier for the credential
            
        Returns:
            Decrypted credential or None if not found
            
        Raises:
            EncryptionError: If retrieval/decryption fails
        """
        file_path = os.path.join(self.storage_path, f"{key}.enc")
        
        if not os.path.exists(file_path):
            return None
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                encrypted = f.read().strip()
            
            return self.encryption.decrypt_credential(encrypted)
            
        except Exception as e:
            raise EncryptionError(f"Failed to retrieve credential '{key}': {str(e)}")
    
    def delete_credential(self, key: str) -> bool:
        """
        Delete a stored credential.
        
        Args:
            key: Identifier for the credential
            
        Returns:
            True if deleted, False if not found
        """
        try:
            file_path = os.path.join(self.storage_path, f"{key}.enc")
            
            if os.path.exists(file_path):
                os.remove(file_path)
                return True
            
            return False
            
        except Exception:
            return False
    
    def list_credentials(self) -> list:
        """
        List all stored credential keys.
        
        Returns:
            List of credential keys
        """
        try:
            files = os.listdir(self.storage_path)
            return [f[:-4] for f in files if f.endswith('.enc')]
        except Exception:
            return []
    
    def credential_exists(self, key: str) -> bool:
        """
        Check if a credential exists.
        
        Args:
            key: Identifier for the credential
            
        Returns:
            True if credential exists, False otherwise
        """
        file_path = os.path.join(self.storage_path, f"{key}.enc")
        return os.path.exists(file_path)