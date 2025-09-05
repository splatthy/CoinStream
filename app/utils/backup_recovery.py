"""
Backup and recovery utilities for data protection and disaster recovery.
"""

import json
import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
import hashlib


class BackupError(Exception):
    """Exception raised during backup operations."""
    pass


class RecoveryError(Exception):
    """Exception raised during recovery operations."""
    pass


class BackupManager:
    """Utility class for managing data backups and recovery."""
    
    def __init__(self, data_dir: str, backup_dir: str = None):
        """Initialize backup manager with data and backup directories."""
        self.data_dir = Path(data_dir)
        self.backup_dir = Path(backup_dir) if backup_dir else self.data_dir / 'backups'
        
        # Create directories if they don't exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self, backup_name: str = None, compress: bool = True) -> str:
        """Create a full backup of all data files."""
        try:
            if backup_name is None:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_name = f"backup_{timestamp}"
            
            if compress:
                backup_path = self.backup_dir / f"{backup_name}.zip"
                self._create_compressed_backup(backup_path)
            else:
                backup_path = self.backup_dir / backup_name
                self._create_directory_backup(backup_path)
            
            # Create backup metadata
            self._create_backup_metadata(backup_path, backup_name)
            
            return str(backup_path)
            
        except Exception as e:
            raise BackupError(f"Failed to create backup: {str(e)}")
    
    def _create_compressed_backup(self, backup_path: Path) -> None:
        """Create compressed ZIP backup."""
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for file_path in self.data_dir.rglob('*.json'):
                if file_path.is_file() and 'backups' not in file_path.parts:
                    arcname = file_path.relative_to(self.data_dir)
                    zipf.write(file_path, arcname)
    
    def _create_directory_backup(self, backup_path: Path) -> None:
        """Create directory-based backup."""
        backup_path.mkdir(parents=True, exist_ok=True)
        
        for file_path in self.data_dir.rglob('*.json'):
            if file_path.is_file() and 'backups' not in file_path.parts:
                relative_path = file_path.relative_to(self.data_dir)
                dest_path = backup_path / relative_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)
    
    def _create_backup_metadata(self, backup_path: Path, backup_name: str) -> None:
        """Create metadata file for backup."""
        metadata = {
            'backup_name': backup_name,
            'created_at': datetime.now().isoformat(),
            'backup_path': str(backup_path),
            'is_compressed': backup_path.suffix == '.zip',
            'files_backed_up': self._get_backup_file_list(),
            'checksum': self._calculate_backup_checksum(backup_path)
        }
        
        metadata_path = backup_path.with_suffix('.metadata.json')
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    
    def _get_backup_file_list(self) -> List[str]:
        """Get list of files included in backup."""
        files = []
        for file_path in self.data_dir.rglob('*.json'):
            if file_path.is_file() and 'backups' not in file_path.parts:
                files.append(str(file_path.relative_to(self.data_dir)))
        return sorted(files)
    
    def _calculate_backup_checksum(self, backup_path: Path) -> str:
        """Calculate MD5 checksum of backup file."""
        if not backup_path.exists():
            return ""
        
        hash_md5 = hashlib.md5()
        with open(backup_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def list_backups(self) -> List[Dict[str, Any]]:
        """List all available backups with metadata."""
        backups = []
        
        for metadata_file in self.backup_dir.glob('*.metadata.json'):
            try:
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                
                # Check if backup file still exists
                backup_path = Path(metadata['backup_path'])
                if backup_path.exists():
                    # Verify checksum
                    current_checksum = self._calculate_backup_checksum(backup_path)
                    metadata['checksum_valid'] = current_checksum == metadata.get('checksum', '')
                    metadata['file_size'] = backup_path.stat().st_size
                    backups.append(metadata)
                
            except Exception as e:
                print(f"Warning: Could not read backup metadata from {metadata_file}: {e}")
        
        # Sort by creation date (newest first)
        backups.sort(key=lambda x: x['created_at'], reverse=True)
        return backups
    
    def restore_backup(self, backup_name: str, confirm: bool = False) -> bool:
        """Restore data from a backup."""
        try:
            if not confirm:
                raise RecoveryError("Restore operation requires explicit confirmation")
            
            # Find backup metadata
            backup_metadata = None
            for backup in self.list_backups():
                if backup['backup_name'] == backup_name:
                    backup_metadata = backup
                    break
            
            if not backup_metadata:
                raise RecoveryError(f"Backup '{backup_name}' not found")
            
            backup_path = Path(backup_metadata['backup_path'])
            if not backup_path.exists():
                raise RecoveryError(f"Backup file not found: {backup_path}")
            
            # Verify checksum
            if not backup_metadata.get('checksum_valid', False):
                raise RecoveryError("Backup file checksum verification failed")
            
            # Create current data backup before restore
            current_backup = self.create_backup(f"pre_restore_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            print(f"Created pre-restore backup: {current_backup}")
            
            # Perform restore
            if backup_metadata['is_compressed']:
                self._restore_from_compressed_backup(backup_path)
            else:
                self._restore_from_directory_backup(backup_path)
            
            print(f"Successfully restored backup: {backup_name}")
            return True
            
        except Exception as e:
            raise RecoveryError(f"Failed to restore backup '{backup_name}': {str(e)}")
    
    def _restore_from_compressed_backup(self, backup_path: Path) -> None:
        """Restore from compressed ZIP backup."""
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            zipf.extractall(self.data_dir)
    
    def _restore_from_directory_backup(self, backup_path: Path) -> None:
        """Restore from directory-based backup."""
        for file_path in backup_path.rglob('*.json'):
            if file_path.is_file():
                relative_path = file_path.relative_to(backup_path)
                dest_path = self.data_dir / relative_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file_path, dest_path)
    
    def delete_backup(self, backup_name: str) -> bool:
        """Delete a backup and its metadata."""
        try:
            # Find backup metadata
            backup_metadata = None
            for backup in self.list_backups():
                if backup['backup_name'] == backup_name:
                    backup_metadata = backup
                    break
            
            if not backup_metadata:
                raise BackupError(f"Backup '{backup_name}' not found")
            
            backup_path = Path(backup_metadata['backup_path'])
            metadata_path = backup_path.with_suffix('.metadata.json')
            
            # Delete backup file
            if backup_path.exists():
                if backup_path.is_dir():
                    shutil.rmtree(backup_path)
                else:
                    backup_path.unlink()
            
            # Delete metadata file
            if metadata_path.exists():
                metadata_path.unlink()
            
            print(f"Deleted backup: {backup_name}")
            return True
            
        except Exception as e:
            raise BackupError(f"Failed to delete backup '{backup_name}': {str(e)}")
    
    def cleanup_old_backups(self, keep_days: int = 30, keep_count: int = 10) -> int:
        """Clean up old backups based on age and count limits."""
        try:
            backups = self.list_backups()
            deleted_count = 0
            
            # Calculate cutoff date
            cutoff_date = datetime.now() - timedelta(days=keep_days)
            
            # Keep the most recent backups regardless of age
            backups_to_keep = backups[:keep_count]
            backups_to_check = backups[keep_count:]
            
            for backup in backups_to_check:
                backup_date = datetime.fromisoformat(backup['created_at'])
                if backup_date < cutoff_date:
                    self.delete_backup(backup['backup_name'])
                    deleted_count += 1
            
            return deleted_count
            
        except Exception as e:
            raise BackupError(f"Failed to cleanup old backups: {str(e)}")
    
    def verify_backup_integrity(self, backup_name: str) -> bool:
        """Verify the integrity of a backup."""
        try:
            # Find backup metadata
            backup_metadata = None
            for backup in self.list_backups():
                if backup['backup_name'] == backup_name:
                    backup_metadata = backup
                    break
            
            if not backup_metadata:
                return False
            
            backup_path = Path(backup_metadata['backup_path'])
            if not backup_path.exists():
                return False
            
            # Verify checksum
            current_checksum = self._calculate_backup_checksum(backup_path)
            expected_checksum = backup_metadata.get('checksum', '')
            
            if current_checksum != expected_checksum:
                return False
            
            # For compressed backups, try to open and validate structure
            if backup_metadata['is_compressed']:
                try:
                    with zipfile.ZipFile(backup_path, 'r') as zipf:
                        # Test the ZIP file
                        zipf.testzip()
                        
                        # Verify expected files are present
                        zip_files = set(zipf.namelist())
                        expected_files = set(backup_metadata.get('files_backed_up', []))
                        
                        if not expected_files.issubset(zip_files):
                            return False
                            
                except zipfile.BadZipFile:
                    return False
            
            return True
            
        except Exception:
            return False
    
    def get_backup_info(self, backup_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific backup."""
        for backup in self.list_backups():
            if backup['backup_name'] == backup_name:
                # Add integrity check
                backup['integrity_verified'] = self.verify_backup_integrity(backup_name)
                return backup
        return None