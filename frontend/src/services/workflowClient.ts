import apiClient from "./apiClient";

export interface PipelineStage {
  name: string;
  type: "data_validation" | "training" | "evaluation" | "deployment";
  dependencies?: string[];
  condition?: Record<string, unknown>;
  config?: Record<string, unknown>;
}

export interface CreatePipelineRequest {
  pipeline_name: string;
  orchestration_system?: string;
  stages: PipelineStage[];
  max_retries?: number;
}

export interface WorkflowPipeline {
  id: string;
  pipeline_name: string;
  orchestration_system: string;
  workflow_id: string;
  workflow_namespace: string;
  pipeline_definition: Record<string, unknown>;
  stages: PipelineStage[];
  status: "pending" | "running" | "succeeded" | "failed" | "cancelled";
  current_stage?: string;
  start_time?: string;
  end_time?: string;
  retry_count: number;
  max_retries: number;
  created_at: string;
  updated_at: string;
}

export interface EnvelopeWorkflowPipeline {
  status: "success" | "fail";
  message: string;
  data?: WorkflowPipeline;
}

export interface EnvelopeWorkflowPipelineList {
  status: "success" | "fail";
  message: string;
  data?: WorkflowPipeline[];
}

export interface EnvelopeWorkflowPipelineDelete {
  status: "success" | "fail";
  message: string;
}

export const workflowClient = {
  /**
   * Create a new workflow pipeline.
   */
  async createPipeline(
    request: CreatePipelineRequest
  ): Promise<EnvelopeWorkflowPipeline> {
    const response = await apiClient.post<EnvelopeWorkflowPipeline>(
      "/workflows/pipelines",
      request
    );
    return response.data;
  },

  /**
   * Get workflow pipeline by ID.
   */
  async getPipeline(
    pipelineId: string,
    updateStatus: boolean = false
  ): Promise<EnvelopeWorkflowPipeline> {
    const response = await apiClient.get<EnvelopeWorkflowPipeline>(
      `/workflows/pipelines/${pipelineId}`,
      {
        params: { update_status: updateStatus },
      }
    );
    return response.data;
  },

  /**
   * List workflow pipelines with optional filters.
   */
  async listPipelines(filters?: {
    status?: string;
    orchestration_system?: string;
  }): Promise<EnvelopeWorkflowPipelineList> {
    const response = await apiClient.get<EnvelopeWorkflowPipelineList>(
      "/workflows/pipelines",
      {
        params: filters,
      }
    );
    return response.data;
  },

  /**
   * Cancel a workflow pipeline.
   */
  async cancelPipeline(
    pipelineId: string
  ): Promise<EnvelopeWorkflowPipelineDelete> {
    const response = await apiClient.delete<EnvelopeWorkflowPipelineDelete>(
      `/workflows/pipelines/${pipelineId}`
    );
    return response.data;
  },

  /**
   * Get Argo Workflows UI URL for a pipeline.
   */
  getArgoUIUrl(pipeline: WorkflowPipeline): string | null {
    if (!pipeline.workflow_id || !pipeline.workflow_namespace) {
      return null;
    }
    // Argo Workflows UI URL format
    // This assumes Argo Workflows server is accessible
    // In production, this should be configured via environment variables
    const argoBaseUrl = import.meta.env.VITE_ARGO_UI_URL || "http://localhost:2746";
    return `${argoBaseUrl}/workflows/${pipeline.workflow_namespace}/${pipeline.workflow_id}`;
  },
};

