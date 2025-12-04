"""Pipeline definition parser and validator.

Parses and validates pipeline definitions from user input.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Set
from datetime import datetime

logger = logging.getLogger(__name__)


class PipelineParseError(Exception):
    """Error raised when pipeline definition is invalid."""
    pass


class PipelineParser:
    """Parser for pipeline definitions."""
    
    VALID_STAGE_TYPES = {
        "data_validation",
        "training",
        "evaluation",
        "deployment",
    }
    
    VALID_STATUSES = {
        "pending",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    }
    
    def __init__(self):
        """Initialize the parser."""
        pass
    
    def parse_pipeline_definition(
        self,
        pipeline_name: str,
        stages: List[Dict[str, Any]],
        orchestration_system: Optional[str] = None,
        max_retries: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Parse and validate pipeline definition.
        
        Args:
            pipeline_name: User-defined pipeline name
            stages: List of stage definitions
            orchestration_system: Orchestration system identifier (default: "argo_workflows")
            max_retries: Maximum retry attempts (default: 3)
        
        Returns:
            Parsed and validated pipeline definition dictionary
        
        Raises:
            PipelineParseError: If pipeline definition is invalid
        """
        # Validate pipeline name
        self._validate_pipeline_name(pipeline_name)
        
        # Validate stages
        self._validate_stages(stages)
        
        # Check for cycles
        self._check_cycles(stages)
        
        # Normalize stages
        normalized_stages = self._normalize_stages(stages)
        
        # Build pipeline definition
        pipeline_definition = {
            "entrypoint": "main",
            "templates": [],  # Will be filled by builder
            "arguments": {},
        }
        
        # Build stages metadata
        stages_metadata = []
        for stage in normalized_stages:
            stages_metadata.append({
                "name": stage["name"],
                "type": stage["type"],
                "dependencies": stage.get("dependencies", []),
                "condition": stage.get("condition"),
                "config": stage.get("config", {}),
            })
        
        return {
            "pipeline_name": pipeline_name,
            "orchestration_system": orchestration_system or "argo_workflows",
            "pipeline_definition": pipeline_definition,
            "stages": stages_metadata,
            "max_retries": max_retries or 3,
        }
    
    def _validate_pipeline_name(self, name: str) -> None:
        """Validate pipeline name.
        
        Args:
            name: Pipeline name
        
        Raises:
            PipelineParseError: If name is invalid
        """
        if not name or not isinstance(name, str):
            raise PipelineParseError("Pipeline name is required and must be a string")
        
        if len(name.strip()) == 0:
            raise PipelineParseError("Pipeline name cannot be empty")
        
        if len(name) > 100:
            raise PipelineParseError("Pipeline name must be 100 characters or less")
        
        # Check for invalid characters (Kubernetes resource name constraints)
        invalid_chars = set(name) - set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_ ")
        if invalid_chars:
            raise PipelineParseError(
                f"Pipeline name contains invalid characters: {invalid_chars}. "
                "Only alphanumeric characters, hyphens, underscores, and spaces are allowed."
            )
    
    def _validate_stages(self, stages: List[Dict[str, Any]]) -> None:
        """Validate stages list.
        
        Args:
            stages: List of stage definitions
        
        Raises:
            PipelineParseError: If stages are invalid
        """
        if not stages or not isinstance(stages, list):
            raise PipelineParseError("Pipeline must have at least one stage")
        
        if len(stages) == 0:
            raise PipelineParseError("Pipeline must have at least one stage")
        
        if len(stages) > 100:
            raise PipelineParseError("Pipeline cannot have more than 100 stages")
        
        stage_names: Set[str] = set()
        
        for i, stage in enumerate(stages):
            if not isinstance(stage, dict):
                raise PipelineParseError(f"Stage {i} must be a dictionary")
            
            # Validate stage name
            if "name" not in stage:
                raise PipelineParseError(f"Stage {i} must have a 'name' field")
            
            stage_name = stage["name"]
            if not isinstance(stage_name, str) or len(stage_name.strip()) == 0:
                raise PipelineParseError(f"Stage {i} name must be a non-empty string")
            
            if stage_name in stage_names:
                raise PipelineParseError(f"Duplicate stage name: {stage_name}")
            
            stage_names.add(stage_name)
            
            # Validate stage type
            stage_type = stage.get("type", "training")
            if stage_type not in self.VALID_STAGE_TYPES:
                raise PipelineParseError(
                    f"Stage '{stage_name}' has invalid type '{stage_type}'. "
                    f"Valid types: {', '.join(self.VALID_STAGE_TYPES)}"
                )
            
            # Validate dependencies
            dependencies = stage.get("dependencies", [])
            if not isinstance(dependencies, list):
                raise PipelineParseError(
                    f"Stage '{stage_name}' dependencies must be a list"
                )
            
            for dep in dependencies:
                if not isinstance(dep, str):
                    raise PipelineParseError(
                        f"Stage '{stage_name}' dependency must be a string"
                    )
                if dep not in stage_names and dep not in [s.get("name") for s in stages[:i]]:
                    raise PipelineParseError(
                        f"Stage '{stage_name}' depends on non-existent stage '{dep}'"
                    )
            
            # Validate condition if present
            condition = stage.get("condition")
            if condition is not None:
                if not isinstance(condition, dict):
                    raise PipelineParseError(
                        f"Stage '{stage_name}' condition must be a dictionary"
                    )
                self._validate_condition(condition, stage_name)
            
            # Validate config if present
            config = stage.get("config")
            if config is not None:
                if not isinstance(config, dict):
                    raise PipelineParseError(
                        f"Stage '{stage_name}' config must be a dictionary"
                    )
    
    def _validate_condition(self, condition: Dict[str, Any], stage_name: str) -> None:
        """Validate condition object.
        
        Args:
            condition: Condition dictionary
            stage_name: Stage name for error messages
        
        Raises:
            PipelineParseError: If condition is invalid
        """
        # Condition format: {"field": "status", "operator": "==", "value": "success", "task": "previous-stage"}
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        task = condition.get("task")
        
        if not field and not task:
            raise PipelineParseError(
                f"Stage '{stage_name}' condition must have either 'field' or 'task'"
            )
        
        valid_operators = {"==", "!=", ">", "<", ">=", "<=", "in", "not in"}
        if operator and operator not in valid_operators:
            raise PipelineParseError(
                f"Stage '{stage_name}' condition has invalid operator '{operator}'. "
                f"Valid operators: {', '.join(valid_operators)}"
            )
    
    def _check_cycles(self, stages: List[Dict[str, Any]]) -> None:
        """Check for cycles in pipeline dependencies.
        
        Args:
            stages: List of stage definitions
        
        Raises:
            PipelineParseError: If cycle is detected
        """
        stage_names = {stage["name"] for stage in stages}
        
        # Build dependency graph
        graph: Dict[str, List[str]] = {}
        for stage in stages:
            stage_name = stage["name"]
            graph[stage_name] = stage.get("dependencies", [])
        
        # DFS to detect cycles
        visited: Set[str] = set()
        rec_stack: Set[str] = set()
        
        def has_cycle(node: str) -> bool:
            """Check for cycles starting from a node."""
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor):
                        return True
                elif neighbor in rec_stack:
                    return True
            
            rec_stack.remove(node)
            return False
        
        for stage_name in stage_names:
            if stage_name not in visited:
                if has_cycle(stage_name):
                    raise PipelineParseError(
                        f"Cycle detected in pipeline dependencies involving stage '{stage_name}'"
                    )
    
    def _normalize_stages(self, stages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalize stage definitions.
        
        Args:
            stages: List of stage definitions
        
        Returns:
            Normalized list of stage definitions
        """
        normalized = []
        
        for stage in stages:
            normalized_stage = {
                "name": stage["name"].strip(),
                "type": stage.get("type", "training"),
                "dependencies": [dep.strip() for dep in stage.get("dependencies", [])],
            }
            
            if "condition" in stage:
                normalized_stage["condition"] = stage["condition"]
            
            if "config" in stage:
                normalized_stage["config"] = stage["config"]
            
            normalized.append(normalized_stage)
        
        return normalized
    
    def parse_pipeline_from_request(
        self,
        request_data: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Parse pipeline definition from API request.
        
        Args:
            request_data: Request data dictionary with:
                - pipeline_name: Pipeline name
                - stages: List of stages
                - orchestration_system: Optional orchestration system
                - max_retries: Optional max retries
        
        Returns:
            Parsed pipeline definition
        
        Raises:
            PipelineParseError: If request data is invalid
        """
        pipeline_name = request_data.get("pipeline_name")
        if not pipeline_name:
            raise PipelineParseError("pipeline_name is required")
        
        stages = request_data.get("stages")
        if not stages:
            raise PipelineParseError("stages are required")
        
        orchestration_system = request_data.get("orchestration_system")
        max_retries = request_data.get("max_retries")
        
        return self.parse_pipeline_definition(
            pipeline_name=pipeline_name,
            stages=stages,
            orchestration_system=orchestration_system,
            max_retries=max_retries,
        )
    
    def validate_pipeline_status(self, status: str) -> None:
        """Validate pipeline status.
        
        Args:
            status: Pipeline status string
        
        Raises:
            PipelineParseError: If status is invalid
        """
        if status not in self.VALID_STATUSES:
            raise PipelineParseError(
                f"Invalid pipeline status '{status}'. "
                f"Valid statuses: {', '.join(self.VALID_STATUSES)}"
            )
    
    def extract_stage_dependencies(
        self,
        stages: List[Dict[str, Any]],
    ) -> Dict[str, List[str]]:
        """Extract dependency graph from stages.
        
        Args:
            stages: List of stage definitions
        
        Returns:
            Dictionary mapping stage names to their dependencies
        """
        dependencies = {}
        for stage in stages:
            stage_name = stage["name"]
            dependencies[stage_name] = stage.get("dependencies", [])
        return dependencies
    
    def get_entry_stages(
        self,
        stages: List[Dict[str, Any]],
    ) -> List[str]:
        """Get entry stages (stages with no dependencies).
        
        Args:
            stages: List of stage definitions
        
        Returns:
            List of entry stage names
        """
        all_stage_names = {stage["name"] for stage in stages}
        entry_stages = []
        
        for stage in stages:
            dependencies = stage.get("dependencies", [])
            if not dependencies:
                entry_stages.append(stage["name"])
        
        return entry_stages
    
    def get_exit_stages(
        self,
        stages: List[Dict[str, Any]],
    ) -> List[str]:
        """Get exit stages (stages that no other stage depends on).
        
        Args:
            stages: List of stage definitions
        
        Returns:
            List of exit stage names
        """
        all_stage_names = {stage["name"] for stage in stages}
        depended_on = set()
        
        for stage in stages:
            dependencies = stage.get("dependencies", [])
            depended_on.update(dependencies)
        
        exit_stages = [
            stage["name"]
            for stage in stages
            if stage["name"] not in depended_on
        ]
        
        return exit_stages

