"""DVC repository manager for managing DVC repositories.

Provides low-level operations for DVC repository initialization, configuration,
and command execution. Used by DVCAdapter to manage dataset-specific DVC repositories.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from integrations.error_handler import (
    ToolConfigurationError,
    ToolOperationError,
    ToolUnavailableError,
    wrap_tool_error,
)

logger = logging.getLogger(__name__)


class DVCRepoManager:
    """Manager for DVC repository operations."""
    
    def __init__(
        self,
        base_repo_dir: str,
        remote_name: str = "minio",
        remote_url: Optional[str] = None,
    ):
        """Initialize DVC repository manager.
        
        Args:
            base_repo_dir: Base directory for DVC repositories
            remote_name: Name of DVC remote storage
            remote_url: URL of DVC remote storage (S3/MinIO)
        """
        self.base_repo_dir = Path(base_repo_dir)
        self.remote_name = remote_name
        self.remote_url = remote_url
        
        # Ensure base directory exists
        self.base_repo_dir.mkdir(parents=True, exist_ok=True)
    
    def get_repo_path(self, dataset_record_id: str) -> Path:
        """Get DVC repository path for a dataset.
        
        Args:
            dataset_record_id: Dataset record ID (UUID string)
            
        Returns:
            Path to DVC repository directory
        """
        return self.base_repo_dir / dataset_record_id
    
    def repo_exists(self, dataset_record_id: str) -> bool:
        """Check if DVC repository exists for a dataset.
        
        Args:
            dataset_record_id: Dataset record ID
            
        Returns:
            True if repository exists, False otherwise
        """
        repo_path = self.get_repo_path(dataset_record_id)
        return repo_path.exists() and (repo_path / ".dvc").exists()
    
    def initialize_repo(
        self,
        dataset_record_id: str,
        force: bool = False,
    ) -> Path:
        """Initialize a new DVC repository for a dataset.
        
        Args:
            dataset_record_id: Dataset record ID
            force: If True, reinitialize even if repo exists
            
        Returns:
            Path to initialized repository
            
        Raises:
            ToolConfigurationError: If initialization fails
        """
        repo_path = self.get_repo_path(dataset_record_id)
        
        if self.repo_exists(dataset_record_id) and not force:
            logger.debug(f"DVC repository already exists at {repo_path}")
            return repo_path
        
        # Create directory if it doesn't exist
        repo_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize Git repository (DVC requires Git)
        self._init_git_repo(repo_path)
        
        # Initialize DVC repository
        self._init_dvc_repo(repo_path)
        
        # Configure remote if URL is provided
        if self.remote_url:
            self._configure_remote(repo_path)
        
        logger.info(f"Initialized DVC repository at {repo_path}")
        return repo_path
    
    def _init_git_repo(self, repo_path: Path) -> None:
        """Initialize Git repository.
        
        Args:
            repo_path: Path to repository directory
            
        Raises:
            ToolConfigurationError: If Git initialization fails
        """
        git_dir = repo_path / ".git"
        if git_dir.exists():
            logger.debug(f"Git repository already exists at {repo_path}")
            return
        
        try:
            result = subprocess.run(
                ["git", "init"],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.debug(f"Initialized Git repository at {repo_path}")
        except subprocess.TimeoutExpired as e:
            raise ToolConfigurationError(
                message="Git initialization timed out",
                tool_name="dvc",
                original_error=e,
            )
        except subprocess.SubprocessError as e:
            # Try with --no-scm flag for DVC if Git fails
            logger.warning(f"Git initialization failed: {e}, trying DVC with --no-scm")
            raise ToolConfigurationError(
                message="Failed to initialize Git repository for DVC",
                tool_name="dvc",
                original_error=e,
            )
        except FileNotFoundError:
            raise ToolUnavailableError(
                message="Git command not found - is Git installed?",
                tool_name="git",
            )
    
    def _init_dvc_repo(self, repo_path: Path, use_no_scm: bool = False) -> None:
        """Initialize DVC repository.
        
        Args:
            repo_path: Path to repository directory
            use_no_scm: If True, use --no-scm flag (for Git-less DVC)
            
        Raises:
            ToolConfigurationError: If DVC initialization fails
        """
        dvc_dir = repo_path / ".dvc"
        if dvc_dir.exists():
            logger.debug(f"DVC repository already exists at {repo_path}")
            return
        
        try:
            cmd = ["dvc", "init"]
            if use_no_scm:
                cmd.append("--no-scm")
            
            result = subprocess.run(
                cmd,
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.debug(f"Initialized DVC repository at {repo_path}")
        except subprocess.TimeoutExpired as e:
            raise ToolConfigurationError(
                message="DVC initialization timed out",
                tool_name="dvc",
                original_error=e,
            )
        except subprocess.SubprocessError as e:
            # If Git init failed, try with --no-scm
            if not use_no_scm:
                logger.warning("DVC init failed, retrying with --no-scm")
                return self._init_dvc_repo(repo_path, use_no_scm=True)
            raise ToolConfigurationError(
                message="Failed to initialize DVC repository",
                tool_name="dvc",
                original_error=e,
            )
        except FileNotFoundError:
            raise ToolUnavailableError(
                message="DVC command not found - is DVC installed?",
                tool_name="dvc",
            )
    
    def _configure_remote(self, repo_path: Path) -> None:
        """Configure DVC remote storage.
        
        Args:
            repo_path: Path to repository directory
        """
        if not self.remote_url:
            return
        
        try:
            # Check if remote already exists
            result = subprocess.run(
                ["dvc", "remote", "list"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=10,
            )
            
            if self.remote_name in result.stdout:
                logger.debug(f"DVC remote '{self.remote_name}' already configured")
                return
            
            # Add remote
            result = subprocess.run(
                ["dvc", "remote", "add", self.remote_name, self.remote_url],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.info(f"Configured DVC remote '{self.remote_name}' at {self.remote_url}")
        except subprocess.SubprocessError as e:
            logger.warning(f"Failed to configure DVC remote: {e}")
            # Non-fatal - continue without remote
    
    def run_command(
        self,
        command: List[str],
        dataset_record_id: str,
        timeout: int = 60,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """Run a DVC command in the dataset's repository.
        
        Args:
            command: DVC command as list of strings (e.g., ["add", "data.csv"])
            dataset_record_id: Dataset record ID
            timeout: Command timeout in seconds
            check: If True, raise exception on non-zero return code
            
        Returns:
            CompletedProcess result
            
        Raises:
            ToolOperationError: If command fails and check=True
            ToolUnavailableError: If DVC is not installed
        """
        repo_path = self.get_repo_path(dataset_record_id)
        
        if not repo_path.exists():
            raise ToolOperationError(
                message=f"Repository not found for dataset {dataset_record_id}",
                tool_name="dvc",
                details={"dataset_id": dataset_record_id},
            )
        
        try:
            result = subprocess.run(
                ["dvc"] + command,
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            
            if check and result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown DVC error"
                raise ToolOperationError(
                    message=f"DVC command failed: {error_msg}",
                    tool_name="dvc",
                    details={
                        "command": " ".join(["dvc"] + command),
                        "returncode": result.returncode,
                        "stdout": result.stdout,
                        "stderr": result.stderr,
                    },
                )
            
            return result
        except subprocess.TimeoutExpired as e:
            raise ToolOperationError(
                message=f"DVC command timed out after {timeout}s",
                tool_name="dvc",
                original_error=e,
                details={"command": " ".join(["dvc"] + command)},
            )
        except FileNotFoundError:
            raise ToolUnavailableError(
                message="DVC command not found - is DVC installed?",
                tool_name="dvc",
            )
        except Exception as e:
            raise wrap_tool_error(e, "dvc", " ".join(command))
    
    def get_repo_status(self, dataset_record_id: str) -> Dict[str, Any]:
        """Get repository status information.
        
        Args:
            dataset_record_id: Dataset record ID
            
        Returns:
            Dictionary with repository status:
            {
                "exists": bool,
                "initialized": bool,
                "remote_configured": bool,
                "commit_count": int,
                "current_commit": str | None
            }
        """
        repo_path = self.get_repo_path(dataset_record_id)
        status = {
            "exists": repo_path.exists(),
            "initialized": False,
            "remote_configured": False,
            "commit_count": 0,
            "current_commit": None,
        }
        
        if not status["exists"]:
            return status
        
        # Check if DVC is initialized
        status["initialized"] = (repo_path / ".dvc").exists()
        
        if not status["initialized"]:
            return status
        
        # Check remote configuration
        try:
            result = subprocess.run(
                ["dvc", "remote", "list"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            status["remote_configured"] = self.remote_name in result.stdout
        except Exception:
            pass
        
        # Get Git commit count and current commit
        try:
            result = subprocess.run(
                ["git", "rev-list", "--count", "HEAD"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                status["commit_count"] = int(result.stdout.strip() or 0)
            
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_path),
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                status["current_commit"] = result.stdout.strip()
        except Exception:
            pass
        
        return status
    
    def cleanup_repo(self, dataset_record_id: str, remove_files: bool = False) -> None:
        """Clean up a DVC repository.
        
        Args:
            dataset_record_id: Dataset record ID
            remove_files: If True, remove all repository files (dangerous!)
        """
        repo_path = self.get_repo_path(dataset_record_id)
        
        if not repo_path.exists():
            return
        
        if remove_files:
            import shutil
            shutil.rmtree(repo_path)
            logger.info(f"Removed DVC repository at {repo_path}")
        else:
            # Just remove DVC cache and temp files
            dvc_cache = repo_path / ".dvc" / "cache"
            if dvc_cache.exists():
                import shutil
                shutil.rmtree(dvc_cache)
                logger.debug(f"Cleaned DVC cache at {dvc_cache}")
    
    def list_repos(self) -> List[str]:
        """List all dataset record IDs that have DVC repositories.
        
        Returns:
            List of dataset record IDs
        """
        if not self.base_repo_dir.exists():
            return []
        
        repos = []
        for item in self.base_repo_dir.iterdir():
            if item.is_dir() and (item / ".dvc").exists():
                repos.append(item.name)
        
        return repos

