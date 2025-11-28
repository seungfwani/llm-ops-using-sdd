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
}

export interface ServingEndpoint {
  id: string;
  modelId: string;
  environment: string;
  route: string;
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

