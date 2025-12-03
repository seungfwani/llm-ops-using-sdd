import apiClient from "./apiClient";

export interface TrainingJobRequest {
  modelId?: string; // Required for finetune, optional for from_scratch/pretrain
  datasetId: string;
  jobType: "finetune" | "from_scratch" | "pretrain" | "distributed";
  useGpu?: boolean; // Whether to use GPU resources (default: true). Set to false for CPU-only training
  hyperparameters?: Record<string, unknown>; // Required for from_scratch/pretrain (must include architecture)
  resourceProfile: {
    // GPU configuration (when useGpu=true)
    gpuCount?: number;
    gpuType?: string;
    // CPU-only configuration (when useGpu=false)
    cpuCores?: number;
    memory?: string; // e.g., "8Gi", "16Gi"
    // Common configuration
    maxDuration: number;
    numNodes?: number; // For distributed training
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
  resourceProfile?: {
    gpuCount?: number;
    gpuType?: string;
    numNodes?: number;
    cpuCores?: number;
    memory?: string;
    maxDuration?: number;
  };
  outputModelStorageUri?: string;
  outputModelEntryId?: string;
}

export interface RegisterModelRequest {
  modelName: string;
  modelVersion: string;
  storageUri: string;
  ownerTeam?: string;
  metadata?: Record<string, unknown>;
}

export interface EnvelopeTrainingJob {
  status: "success" | "fail";
  message: string;
  data?: TrainingJob;
}

export interface ListJobsFilters {
  modelId?: string;
  status?: string;
}

export interface EnvelopeTrainingJobList {
  status: "success" | "fail";
  message: string;
  data?: {
    jobs: TrainingJob[];
  };
}

export interface ExperimentMetric {
  id: string;
  trainingJobId: string;
  name: string;
  value: number;
  unit?: string;
  recordedAt: string;
}

export interface Experiment {
  jobId: string;
  metrics: ExperimentMetric[];
}

export interface EnvelopeExperiment {
  status: "success" | "fail";
  message: string;
  data?: Experiment;
}

export const trainingClient = {
  async listJobs(filters?: ListJobsFilters): Promise<EnvelopeTrainingJobList> {
    const params = new URLSearchParams();
    if (filters?.modelId) {
      params.append("modelId", filters.modelId);
    }
    if (filters?.status) {
      params.append("status", filters.status);
    }
    const queryString = params.toString();
    const url = `/training/jobs${queryString ? `?${queryString}` : ""}`;
    const response = await apiClient.get<EnvelopeTrainingJobList>(url);
    return response.data;
  },

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

  async resubmitJob(
    jobId: string,
    resourceProfile: TrainingJobRequest["resourceProfile"],
    useGpu?: boolean
  ): Promise<EnvelopeTrainingJob> {
    const response = await apiClient.post<EnvelopeTrainingJob>(
      `/training/jobs/${jobId}/resubmit`,
      {
        resourceProfile,
        useGpu,
      }
    );
    return response.data;
  },

  async getExperiment(jobId: string): Promise<EnvelopeExperiment> {
    const response = await apiClient.get<EnvelopeExperiment>(
      `/training/experiments/${jobId}`
    );
    return response.data;
  },

  async registerModel(
    jobId: string,
    request: RegisterModelRequest
  ): Promise<EnvelopeTrainingJob> {
    const response = await apiClient.post<EnvelopeTrainingJob>(
      `/training/jobs/${jobId}/register-model`,
      request
    );
    return response.data;
  },
};

