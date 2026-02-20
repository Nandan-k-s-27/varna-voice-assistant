"""
VARNA v2.2 - Command Sandboxing Layer
Security validation before executing PowerShell commands.

Features:
  - Whitelist-based argument validation
  - Path injection prevention
  - Script execution blocking
  - Entity extraction validation

This ensures safe command execution for open-source deployment.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from utils.logger import get_logger

log = get_logger(__name__)


class SecurityLevel(Enum):
    """Security level for commands."""
    SAFE = auto()           # Always allowed
    CONFIRMED = auto()      # Needs user confirmation
    BLOCKED = auto()        # Never allowed


@dataclass
class ValidationResult:
    """Result of command validation."""
    allowed: bool
    security_level: SecurityLevel
    reason: str = ""
    sanitized_command: str = ""
    warnings: list[str] = None
    
    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


# Dangerous patterns that should never be allowed
_BLOCKED_PATTERNS = [
    # Script execution
    r'Invoke-Expression',
    r'iex\s+',
    r'Invoke-Command',
    r'icm\s+',
    r'\.ps1',
    r'powershell\s+-[cC]ommand',
    r'powershell\s+-[eE]ncodedCommand',
    r'cmd\s+/c',
    r'cmd\.exe',
    
    # Remote execution
    r'-ComputerName',
    r'Enter-PSSession',
    r'New-PSSession',
    r'Invoke-WebRequest',
    r'Invoke-RestMethod',
    r'curl\s+',
    r'wget\s+',
    r'Start-BitsTransfer',
    
    # System modification
    r'Set-ExecutionPolicy',
    r'Remove-Item\s+.*-Recurse.*-Force',
    r'Format-Volume',
    r'Clear-Disk',
    r'Initialize-Disk',
    
    # Registry modification
    r'Remove-ItemProperty',
    r'Set-ItemProperty.*HKLM:',
    r'New-ItemProperty.*HKLM:',
    r'reg\s+delete',
    r'reg\s+add',
    
    # User/credential access
    r'Get-Credential',
    r'ConvertTo-SecureString',
    r'Net\s+user',
    r'Net\s+localgroup',
    
    # Process injection
    r'[System.Runtime.InteropServices.Marshal]',
    r'VirtualAlloc',
    r'CreateThread',
    
    # Encoded/obfuscated commands
    r'-EncodedCommand',
    r'-ec\s+',
    r'\[Convert\]::FromBase64String',
]

# Patterns that need confirmation
_CONFIRM_PATTERNS = [
    r'Stop-Process',
    r'Stop-Computer',
    r'Restart-Computer',
    r'shutdown',
    r'Remove-Item',
    r'del\s+',
    r'rmdir',
    r'taskkill',
    r'Clear-RecycleBin',
]

# Allowed command prefixes (whitelist approach)
_ALLOWED_PREFIXES = [
    'Start-Process',
    'Get-Process',
    'Get-ChildItem',
    'Get-Content',
    'Set-Location',
    'Get-Location',
    'Get-Date',
    'Get-ComputerInfo',
    'Get-CimInstance',
    'Get-NetIPAddress',
    'Get-Volume',
    'Get-PSDrive',
    'Get-Clipboard',
    'Set-Clipboard',
    'Write-Output',
    'Out-File',
    'rundll32.exe user32.dll,LockWorkStation',
]

# Safe argument patterns
_SAFE_ARGUMENT_PATTERNS = {
    'app_name': r'^[a-zA-Z0-9\s\-_\.]+$',
    'file_path': r'^[a-zA-Z]:\\[a-zA-Z0-9\s\-_\.\\/]+$',
    'url': r'^https?://[a-zA-Z0-9\-\.]+\.[a-zA-Z]{2,}(/[a-zA-Z0-9\-_\.%/?=&]*)?$',
    'number': r'^\d+$',
    'search_query': r'^[a-zA-Z0-9\s\-_\.\,\?\!]+$',
}


class CommandSandbox:
    """
    Security sandbox for command execution.
    
    Validates all commands before execution using:
    1. Blocked pattern detection
    2. Whitelist prefix validation
    3. Argument sanitization
    4. Path injection prevention
    """
    
    def __init__(self, strict_mode: bool = False):
        """
        Initialize sandbox.
        
        Args:
            strict_mode: If True, block anything not explicitly whitelisted.
        """
        self._strict_mode = strict_mode
        self._blocked_patterns = [re.compile(p, re.I) for p in _BLOCKED_PATTERNS]
        self._confirm_patterns = [re.compile(p, re.I) for p in _CONFIRM_PATTERNS]
        self._validation_history: list[dict] = []
        
        log.info("CommandSandbox initialized (strict_mode=%s)", strict_mode)
    
    def validate(self, command: str) -> ValidationResult:
        """
        Validate a command for safe execution.
        
        Args:
            command: PowerShell command to validate.
            
        Returns:
            ValidationResult with allowed status and details.
        """
        original_command = command
        warnings = []
        
        # Check for blocked patterns
        for pattern in self._blocked_patterns:
            if pattern.search(command):
                log.warning("Blocked dangerous command pattern: %s", pattern.pattern)
                return ValidationResult(
                    allowed=False,
                    security_level=SecurityLevel.BLOCKED,
                    reason=f"Blocked pattern detected: {pattern.pattern}",
                    sanitized_command=""
                )
        
        # Check for confirmation-required patterns
        needs_confirm = False
        for pattern in self._confirm_patterns:
            if pattern.search(command):
                needs_confirm = True
                warnings.append(f"Command requires confirmation: {pattern.pattern}")
                break
        
        # Sanitize the command
        sanitized = self._sanitize(command)
        
        if sanitized != command:
            warnings.append("Command was sanitized for safety")
        
        # In strict mode, check whitelist
        if self._strict_mode:
            is_whitelisted = any(
                sanitized.strip().startswith(prefix) 
                for prefix in _ALLOWED_PREFIXES
            )
            if not is_whitelisted:
                log.warning("Command not in whitelist (strict mode): %s", sanitized[:50])
                return ValidationResult(
                    allowed=False,
                    security_level=SecurityLevel.BLOCKED,
                    reason="Command not in whitelist (strict mode)",
                    sanitized_command=""
                )
        
        # Record validation
        self._validation_history.append({
            "original": original_command,
            "sanitized": sanitized,
            "allowed": True,
            "needs_confirm": needs_confirm
        })
        
        security_level = SecurityLevel.CONFIRMED if needs_confirm else SecurityLevel.SAFE
        
        return ValidationResult(
            allowed=True,
            security_level=security_level,
            reason="Passed validation",
            sanitized_command=sanitized,
            warnings=warnings
        )
    
    def validate_entity(
        self, 
        entity: str, 
        entity_type: str
    ) -> tuple[bool, str]:
        """
        Validate an extracted entity.
        
        Args:
            entity: The entity value (app name, path, etc.)
            entity_type: Type of entity (app_name, file_path, url, etc.)
            
        Returns:
            Tuple of (is_valid, sanitized_value).
        """
        if entity_type not in _SAFE_ARGUMENT_PATTERNS:
            # Unknown type - basic sanitization
            sanitized = self._sanitize_string(entity)
            return True, sanitized
        
        pattern = _SAFE_ARGUMENT_PATTERNS[entity_type]
        
        if re.match(pattern, entity):
            return True, entity
        else:
            # Try sanitization
            sanitized = self._sanitize_string(entity)
            if re.match(pattern, sanitized):
                return True, sanitized
            else:
                log.warning("Entity validation failed: %s (type=%s)", 
                           entity[:30], entity_type)
                return False, ""
    
    def _sanitize(self, command: str) -> str:
        """Sanitize a command string."""
        # Remove null bytes
        command = command.replace('\x00', '')
        
        # Remove command injection attempts
        command = re.sub(r'[;&|`$()]', '', command)
        
        # Remove potential encoding tricks
        command = re.sub(r'%[0-9a-fA-F]{2}', '', command)
        
        # Limit length
        if len(command) > 1000:
            command = command[:1000]
        
        return command.strip()
    
    def _sanitize_string(self, s: str) -> str:
        """Sanitize a generic string."""
        # Remove dangerous characters
        s = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', s)
        
        # Remove PowerShell special chars
        s = re.sub(r'[$`]', '', s)
        
        return s.strip()
    
    def validate_path(self, path: str) -> tuple[bool, str]:
        """
        Validate a file path for safety.
        
        Prevents:
        - Path traversal (../)
        - UNC paths
        - Non-existent drives
        """
        # Remove any quotes
        path = path.strip('"\'')
        
        # Check for path traversal
        if '..' in path:
            log.warning("Path traversal attempt blocked: %s", path)
            return False, ""
        
        # Check for UNC paths (network)
        if path.startswith('\\\\'):
            log.warning("UNC path blocked: %s", path)
            return False, ""
        
        # Check for valid Windows path format
        path_pattern = r'^[a-zA-Z]:\\[^<>:"|?*]*$'
        if not re.match(path_pattern, path):
            log.warning("Invalid path format: %s", path)
            return False, ""
        
        # Verify the drive exists
        try:
            drive = path[0].upper()
            if not Path(f"{drive}:\\").exists():
                log.warning("Invalid drive: %s", drive)
                return False, ""
        except Exception:
            return False, ""
        
        return True, path
    
    def get_validation_stats(self) -> dict:
        """Get validation statistics."""
        total = len(self._validation_history)
        allowed = sum(1 for v in self._validation_history if v["allowed"])
        blocked = total - allowed
        
        return {
            "total_validations": total,
            "allowed": allowed,
            "blocked": blocked,
            "block_rate": f"{(blocked/total*100):.1f}%" if total > 0 else "0%"
        }


# Singleton
_sandbox: CommandSandbox | None = None


def get_sandbox(strict_mode: bool = False) -> CommandSandbox:
    """Get or create the singleton sandbox instance."""
    global _sandbox
    if _sandbox is None:
        _sandbox = CommandSandbox(strict_mode=strict_mode)
    return _sandbox
