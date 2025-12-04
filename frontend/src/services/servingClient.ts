import apiClient from "./apiClient";

export interface ServingEndpointRequest {
  modelId: string;
  environment: "dev" | "stg" | "prod";
  route: string;
  minReplicas?: number;
  maxReplicas?: number;
  autoscalePolicy?: {
    cpuUtilization?: number;
    targetLatencyMs?: number;
  };
  promptPolicyId?: string;
  useGpu?: boolean; // Whether to request GPU resources. If not provided, uses default from settings
  servingRuntimeImage?: string; // Container image for model serving runtime (e.g., vLLM, TGI). If not provided, uses default from settings
  cpuRequest?: string; // CPU request (e.g., '2', '1000m'). If not provided, uses default from settings
  cpuLimit?: string; // CPU limit (e.g., '4', '2000m'). If not provided, uses default from settings
  memoryRequest?: string; // Memory request (e.g., '4Gi', '2G'). If not provided, uses default from settings
  memoryLimit?: string; // Memory limit (e.g., '8Gi', '4G'). If not provided, uses default from settings
}

export interface ServingEndpoint {
  id: string;
  modelId: string;
  environment: string;
  route: string;
  runtimeImage?: string;
  status: string;
  minReplicas: number;
  maxReplicas: number;
  createdAt: string;
}

export interface EnvelopeServingEndpoint {
  status: "success" | "fail";
  message: string;
  data?: ServingEndpoint;
}

export interface EnvelopeServingEndpointList {
  status: "success" | "fail";
  message: string;
  data?: ServingEndpoint[];
}

export interface ListEndpointsFilters {
  environment?: "dev" | "stg" | "prod";
  modelId?: string;
  status?: "deploying" | "healthy" | "degraded" | "failed";
}

export const servingClient = {
  async listEndpoints(filters?: ListEndpointsFilters): Promise<EnvelopeServingEndpointList> {
    const params = new URLSearchParams();
    if (filters?.environment) params.append("environment", filters.environment);
    if (filters?.modelId) params.append("modelId", filters.modelId);
    if (filters?.status) params.append("status", filters.status);
    
    const queryString = params.toString();
    const url = `/serving/endpoints${queryString ? `?${queryString}` : ""}`;
    const response = await apiClient.get<EnvelopeServingEndpointList>(url);
    return response.data;
  },

  async deployEndpoint(request: ServingEndpointRequest): Promise<EnvelopeServingEndpoint> {
    const response = await apiClient.post<EnvelopeServingEndpoint>(
      "/serving/endpoints",
      request
    );
    return response.data;
  },

  async getEndpoint(endpointId: string): Promise<EnvelopeServingEndpoint> {
    const response = await apiClient.get<EnvelopeServingEndpoint>(
      `/serving/endpoints/${endpointId}`
    );
    return response.data;
  },

  async rollbackEndpoint(endpointId: string): Promise<EnvelopeServingEndpoint> {
    const response = await apiClient.post<EnvelopeServingEndpoint>(
      `/serving/endpoints/${endpointId}/rollback`
    );
    return response.data;
  },

  async redeployEndpoint(
    endpointId: string,
    useGpu?: boolean,
    servingRuntimeImage?: string,
    cpuRequest?: string,
    cpuLimit?: string,
    memoryRequest?: string,
    memoryLimit?: string
  ): Promise<EnvelopeServingEndpoint> {
    const params = new URLSearchParams();
    if (useGpu !== undefined) {
      params.append("useGpu", useGpu.toString());
    }
    if (servingRuntimeImage !== undefined) {
      params.append("servingRuntimeImage", servingRuntimeImage);
    }
    if (cpuRequest !== undefined && cpuRequest.trim()) {
      params.append("cpuRequest", cpuRequest.trim());
    }
    if (cpuLimit !== undefined && cpuLimit.trim()) {
      params.append("cpuLimit", cpuLimit.trim());
    }
    if (memoryRequest !== undefined && memoryRequest.trim()) {
      params.append("memoryRequest", memoryRequest.trim());
    }
    if (memoryLimit !== undefined && memoryLimit.trim()) {
      params.append("memoryLimit", memoryLimit.trim());
    }
    const queryString = params.toString();
    const url = `/serving/endpoints/${endpointId}/redeploy${queryString ? `?${queryString}` : ""}`;
    const response = await apiClient.post<EnvelopeServingEndpoint>(url);
    return response.data;
  },

  async deleteEndpoint(endpointId: string): Promise<EnvelopeServingEndpoint> {
    const response = await apiClient.delete<EnvelopeServingEndpoint>(
      `/serving/endpoints/${endpointId}`
    );
    return response.data;
  },

  async chatCompletion(
    modelRoute: string,
    messages: ChatMessage[],
    options?: ChatOptions
  ): Promise<ChatCompletionResponse> {
    // Extract route from full path if needed (e.g., "/llm-ops/v1/serve/chat-model" -> "chat-model")
    const routeName = modelRoute.replace(/^\/llm-ops\/v1\/serve\//, '').replace(/^\//, '');
    
    const response = await apiClient.post<ChatCompletionResponse>(
      `/serve/${routeName}/chat`,
      {
        messages,
        temperature: options?.temperature ?? 0.7,
        max_tokens: options?.max_tokens ?? 500,
      }
    );
    return response.data;
  },
};

export interface ChatMessage {
  role: "system" | "user" | "assistant";
  content: string;
}

export interface ChatOptions {
  temperature?: number;
  max_tokens?: number;
}

export interface ChatCompletionResponse {
  status: "success" | "fail";
  message?: string;
  data?: {
    choices: Array<{
      message: {
        role: string;
        content: string;
      };
      finish_reason?: string;
    }>;
    usage?: {
      prompt_tokens: number;
      completion_tokens: number;
      total_tokens: number;
    };
  };
}

