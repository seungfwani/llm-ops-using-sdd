"""Argo Workflow CRD builder.

Converts platform pipeline definitions to Argo Workflow CRD manifests.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

logger = logging.getLogger(__name__)


class ArgoWorkflowBuilder:
    """Builder for Argo Workflow CRD manifests from pipeline definitions."""
    
    def __init__(self):
        """Initialize the builder."""
        pass
    
    def build_workflow_manifest(
        self,
        pipeline_id: UUID,
        pipeline_name: str,
        stages: List[Dict[str, Any]],
        namespace: str,
        max_retries: int = 3,
        entrypoint: str = "main",
    ) -> Dict[str, Any]:
        """Build Argo Workflow manifest from pipeline definition.
        
        Args:
            pipeline_id: Platform pipeline ID
            pipeline_name: User-defined pipeline name
            stages: List of stage definitions with:
                - name: Stage name
                - type: Stage type (data_validation, training, evaluation, deployment)
                - dependencies: List of stage names this stage depends on
                - condition: Optional condition object
                - config: Stage-specific configuration
            namespace: Kubernetes namespace
            max_retries: Maximum retry attempts
            entrypoint: Entrypoint template name (default: "main")
        
        Returns:
            Argo Workflow manifest dictionary
        
        Raises:
            ValueError: If pipeline definition is invalid (cycles, missing dependencies)
        """
        # Validate pipeline definition
        self._validate_pipeline(stages)
        
        # Generate workflow name
        workflow_name = self._generate_workflow_name(pipeline_name, pipeline_id)
        
        # Build templates
        templates = self._build_templates(stages)
        
        # Build DAG template with dependencies
        dag_template = self._build_dag_template(stages, entrypoint)
        templates.append(dag_template)
        
        # Build workflow manifest
        manifest = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "Workflow",
            "metadata": {
                "name": workflow_name,
                "namespace": namespace,
                "labels": {
                    "pipeline-id": str(pipeline_id),
                    "pipeline-name": pipeline_name,
                    "managed-by": "llm-ops-platform",
                },
                "annotations": {
                    "pipeline-id": str(pipeline_id),
                    "pipeline-name": pipeline_name,
                },
            },
            "spec": {
                "entrypoint": entrypoint,
                "retryStrategy": {
                    "limit": max_retries,
                },
                "templates": templates,
                "arguments": {
                    "parameters": [],
                },
            },
        }
        
        return manifest
    
    def _validate_pipeline(self, stages: List[Dict[str, Any]]) -> None:
        """Validate pipeline definition for cycles and missing dependencies.
        
        Args:
            stages: List of stage definitions
        
        Raises:
            ValueError: If pipeline is invalid
        """
        stage_names = {stage["name"] for stage in stages}
        
        # Check for duplicate stage names
        if len(stage_names) != len(stages):
            raise ValueError("Duplicate stage names found")
        
        # Check dependencies exist
        for stage in stages:
            dependencies = stage.get("dependencies", [])
            for dep in dependencies:
                if dep not in stage_names:
                    raise ValueError(f"Stage '{stage['name']}' depends on non-existent stage '{dep}'")
        
        # Check for cycles using DFS
        visited = set()
        rec_stack = set()
        
        def has_cycle(stage_name: str) -> bool:
            """Check for cycles starting from a stage."""
            visited.add(stage_name)
            rec_stack.add(stage_name)
            
            stage = next((s for s in stages if s["name"] == stage_name), None)
            if stage:
                for dep in stage.get("dependencies", []):
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        return True
            
            rec_stack.remove(stage_name)
            return False
        
        for stage in stages:
            if stage["name"] not in visited:
                if has_cycle(stage["name"]):
                    raise ValueError(f"Cycle detected in pipeline dependencies")
    
    def _generate_workflow_name(self, pipeline_name: str, pipeline_id: UUID) -> str:
        """Generate Kubernetes-compliant workflow name.
        
        Args:
            pipeline_name: User-defined pipeline name
            pipeline_id: Pipeline UUID
        
        Returns:
            Valid Kubernetes resource name
        """
        # Kubernetes names must be lowercase, alphanumeric, and hyphens
        # Max length 63 characters
        name = pipeline_name.lower().replace(" ", "-")
        name = "".join(c if c.isalnum() or c == "-" else "-" for c in name)
        name = name.strip("-")
        
        # Add pipeline ID suffix (first 8 chars)
        suffix = str(pipeline_id)[:8]
        name = f"{name}-{suffix}"[:63]
        
        return name
    
    def _build_templates(self, stages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Build Argo Workflow templates for each stage.
        
        Args:
            stages: List of stage definitions
        
        Returns:
            List of template dictionaries
        """
        templates = []
        
        for stage in stages:
            stage_name = stage["name"]
            stage_type = stage.get("type", "training")
            config = stage.get("config", {})
            
            # Build template based on stage type
            if stage_type == "training":
                template = self._build_training_template(stage_name, config)
            elif stage_type == "evaluation":
                template = self._build_evaluation_template(stage_name, config)
            elif stage_type == "data_validation":
                template = self._build_data_validation_template(stage_name, config)
            elif stage_type == "deployment":
                template = self._build_deployment_template(stage_name, config)
            else:
                # Generic container template
                template = self._build_generic_template(stage_name, config)
            
            templates.append(template)
        
        return templates
    
    def _build_training_template(self, stage_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Build template for training stage.
        
        Args:
            stage_name: Stage name
            config: Stage configuration
        
        Returns:
            Template dictionary
        """
        return {
            "name": stage_name,
            "container": {
                "image": config.get("image", "python:3.11"),
                "command": config.get("command", ["python", "-m", "training"]),
                "args": config.get("args", []),
                "env": self._build_env_vars(config.get("env", {})),
                "resources": self._build_resources(config.get("resources", {})),
            },
        }
    
    def _build_evaluation_template(self, stage_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Build template for evaluation stage.
        
        Args:
            stage_name: Stage name
            config: Stage configuration
        
        Returns:
            Template dictionary
        """
        return {
            "name": stage_name,
            "container": {
                "image": config.get("image", "python:3.11"),
                "command": config.get("command", ["python", "-m", "evaluation"]),
                "args": config.get("args", []),
                "env": self._build_env_vars(config.get("env", {})),
                "resources": self._build_resources(config.get("resources", {})),
            },
        }
    
    def _build_data_validation_template(self, stage_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Build template for data validation stage.
        
        Args:
            stage_name: Stage name
            config: Stage configuration
        
        Returns:
            Template dictionary
        """
        return {
            "name": stage_name,
            "container": {
                "image": config.get("image", "python:3.11"),
                "command": config.get("command", ["python", "-m", "data_validation"]),
                "args": config.get("args", []),
                "env": self._build_env_vars(config.get("env", {})),
                "resources": self._build_resources(config.get("resources", {})),
            },
        }
    
    def _build_deployment_template(self, stage_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Build template for deployment stage.
        
        Args:
            stage_name: Stage name
            config: Stage configuration
        
        Returns:
            Template dictionary
        """
        return {
            "name": stage_name,
            "container": {
                "image": config.get("image", "kubectl:latest"),
                "command": config.get("command", ["kubectl", "apply", "-f", "-"]),
                "args": config.get("args", []),
                "env": self._build_env_vars(config.get("env", {})),
                "resources": self._build_resources(config.get("resources", {})),
            },
        }
    
    def _build_generic_template(self, stage_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """Build generic container template.
        
        Args:
            stage_name: Stage name
            config: Stage configuration
        
        Returns:
            Template dictionary
        """
        return {
            "name": stage_name,
            "container": {
                "image": config.get("image", "alpine:latest"),
                "command": config.get("command", ["echo", "No command specified"]),
                "args": config.get("args", []),
                "env": self._build_env_vars(config.get("env", {})),
                "resources": self._build_resources(config.get("resources", {})),
            },
        }
    
    def _build_env_vars(self, env_dict: Dict[str, str]) -> List[Dict[str, str]]:
        """Build environment variables list from dictionary.
        
        Args:
            env_dict: Dictionary of environment variables
        
        Returns:
            List of environment variable dictionaries
        """
        return [{"name": k, "value": str(v)} for k, v in env_dict.items()]
    
    def _build_resources(self, resources: Dict[str, Any]) -> Dict[str, Any]:
        """Build resource requirements.
        
        Args:
            resources: Resource configuration dictionary
        
        Returns:
            Resource requirements dictionary
        """
        requests = {}
        limits = {}
        
        if "cpu" in resources:
            requests["cpu"] = str(resources["cpu"])
        if "memory" in resources:
            requests["memory"] = str(resources["memory"])
        if "gpu" in resources:
            requests["nvidia.com/gpu"] = str(resources["gpu"])
        
        if "cpu_limit" in resources:
            limits["cpu"] = str(resources["cpu_limit"])
        if "memory_limit" in resources:
            limits["memory"] = str(resources["memory_limit"])
        if "gpu_limit" in resources:
            limits["nvidia.com/gpu"] = str(resources["gpu_limit"])
        
        result = {}
        if requests:
            result["requests"] = requests
        if limits:
            result["limits"] = limits
        
        return result
    
    def _build_dag_template(
        self,
        stages: List[Dict[str, Any]],
        entrypoint: str,
    ) -> Dict[str, Any]:
        """Build DAG template with stage dependencies.
        
        Args:
            stages: List of stage definitions
            entrypoint: Entrypoint template name
        
        Returns:
            DAG template dictionary
        """
        tasks = []
        
        for stage in stages:
            stage_name = stage["name"]
            dependencies = stage.get("dependencies", [])
            condition = stage.get("condition")
            
            task = {
                "name": stage_name,
                "template": stage_name,
            }
            
            if dependencies:
                task["dependencies"] = dependencies
            
            if condition:
                task["when"] = self._build_condition(condition)
            
            tasks.append(task)
        
        return {
            "name": entrypoint,
            "dag": {
                "tasks": tasks,
            },
        }
    
    def _build_condition(self, condition: Dict[str, Any]) -> str:
        """Build Argo Workflow condition expression.
        
        Args:
            condition: Condition dictionary
        
        Returns:
            Condition expression string
        """
        # Simple condition format: {"field": "status", "operator": "==", "value": "success"}
        # Convert to Argo expression: "{{tasks.previous-stage.outputs.result}} == success"
        
        field = condition.get("field", "")
        operator = condition.get("operator", "==")
        value = condition.get("value", "")
        task_ref = condition.get("task", "")
        
        if task_ref:
            # Reference another task's output
            return f"{{{{tasks.{task_ref}.outputs.result}}}} {operator} {value}"
        else:
            # Simple value comparison
            return f"{field} {operator} {value}"

