import apiClient from "./apiClient";

export interface TrainingJobRequest {
  modelId: string;
  datasetId: string;
  jobType: "finetune" | "distributed";
  hyperparameters?: Record<string, unknown>;
  resourceProfile: {
    gpuCount: number;
    gpuType: string;
    maxDuration: number;
  };
  retryPolicy?: {
    maxRetries: number;
    backoffSeconds: number;
  };
  notifications?: {
    onStart?: string[];
    onCompletion?: string[];
  };
}

export interface TrainingJob {
  id: string;
  modelId: string;
  datasetId: string;
  jobType: string;
  status: string;
  submittedAt: string;
  startedAt?: string;
  completedAt?: string;
  experimentUrl?: string;
}

export interface EnvelopeTrainingJob {
  status: "success" | "fail";
  message: string;
  data?: TrainingJob;
}

export const trainingClient = {
  async submitJob(request: TrainingJobRequest): Promise<EnvelopeTrainingJob> {
    const response = await apiClient.post<EnvelopeTrainingJob>(
      "/training/jobs",
      request
    );
    return response.data;
  },

  async getJob(jobId: string): Promise<EnvelopeTrainingJob> {
    const response = await apiClient.get<EnvelopeTrainingJob>(
      `/training/jobs/${jobId}`
    );
    return response.data;
  },

  async cancelJob(jobId: string): Promise<EnvelopeTrainingJob> {
    const response = await apiClient.delete<EnvelopeTrainingJob>(
      `/training/jobs/${jobId}`
    );
    return response.data;
  },
};

