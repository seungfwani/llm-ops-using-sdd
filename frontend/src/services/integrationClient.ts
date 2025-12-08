import apiClient from "./apiClient";

export interface ExperimentRun {
  id: string;
  trainingJobId: string;
  trackingSystem: string;
  trackingRunId: string;
  experimentName: string;
  runName?: string;
  parameters?: Record<string, unknown>;
  metrics?: Record<string, number>;
  artifactUris?: string[];
  status: "running" | "completed" | "failed" | "killed";
  startTime: string;
  endTime?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateExperimentRunRequest {
  experimentName?: string;
  runName?: string;
  parameters?: Record<string, unknown>;
}

export interface LogExperimentMetricsRequest {
  metrics: Record<string, number>;
  step?: number;
}

export interface SearchExperimentsRequest {
  experimentName?: string;
  filterString?: string;
  maxResults?: number;
}

export interface EnvelopeExperimentRun {
  status: "success" | "fail";
  message: string;
  data?: ExperimentRun;
}

export interface ExperimentSearchResponse {
  experiments: ExperimentRun[];
  total: number;
}

export interface EnvelopeExperimentSearch {
  status: "success" | "fail";
  message: string;
  data?: ExperimentSearchResponse;
}

export const integrationClient = {
  /**
   * Get experiment run for a training job.
   */
  async getExperimentRun(jobId: string): Promise<EnvelopeExperimentRun> {
    const response = await apiClient.get<EnvelopeExperimentRun>(
      `/training/jobs/${jobId}/experiment-run`
    );
    return response.data;
  },

  /**
   * Create experiment run for a training job.
   */
  async createExperimentRun(
    jobId: string,
    request: CreateExperimentRunRequest
  ): Promise<EnvelopeExperimentRun> {
    const response = await apiClient.post<EnvelopeExperimentRun>(
      `/training/jobs/${jobId}/experiment-run`,
      request
    );
    return response.data;
  },

  /**
   * Log metrics to experiment run.
   */
  async logExperimentMetrics(
    jobId: string,
    request: LogExperimentMetricsRequest
  ): Promise<{ status: "success" | "fail"; message: string }> {
    const response = await apiClient.post<{ status: "success" | "fail"; message: string }>(
      `/training/jobs/${jobId}/experiment-run/metrics`,
      request
    );
    return response.data;
  },

  /**
   * Search experiments.
   */
  async searchExperiments(
    request: SearchExperimentsRequest
  ): Promise<EnvelopeExperimentSearch> {
    const response = await apiClient.post<EnvelopeExperimentSearch>(
      `/experiments/search`,
      request
    );
    return response.data;
  },

  /**
   * Get MLflow UI URL for an experiment run.
   * This constructs the URL based on the tracking system and run ID.
   */
  getMLflowUIUrl(experimentRun: ExperimentRun): string | null {
    if (experimentRun.trackingSystem !== "mlflow") {
      return null;
    }
    // Construct MLflow UI URL
    // In production, this would be configured via environment variable
    const mlflowBaseUrl = import.meta.env.VITE_MLFLOW_UI_URL || "http://localhost:5000";
    return `${mlflowBaseUrl}/#/experiments/${experimentRun.experimentName}/runs/${experimentRun.trackingRunId}`;
  },
};

