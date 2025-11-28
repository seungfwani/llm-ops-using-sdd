import apiClient from "./apiClient";

export interface GovernancePolicy {
  id: string;
  name: string;
  scope: string;
  rules: Record<string, unknown>;
  status: string;
  lastReviewedAt?: string;
  createdAt: string;
}

export interface AuditLog {
  id: string;
  actorId: string;
  action: string;
  resourceType: string;
  resourceId?: string;
  result: string;
  metadata?: Record<string, unknown>;
  occurredAt: string;
}

export interface CostProfile {
  id: string;
  resourceType: string;
  resourceId: string;
  timeWindow: string;
  gpuHours?: number;
  tokenCount?: number;
  costAmount?: number;
  costCurrency: string;
  budgetVariance?: number;
  createdAt: string;
}

export interface CostAggregate {
  totalGpuHours: number;
  totalTokens: number;
  totalCost: number;
  currency: string;
  resourceCount: number;
}

export interface Envelope<T> {
  status: "success" | "fail";
  message: string;
  data?: T | T[];
}

export const governanceClient = {
  async listPolicies(scope?: string, status?: string): Promise<Envelope<GovernancePolicy>> {
    const params = new URLSearchParams();
    if (scope) params.append("scope", scope);
    if (status) params.append("status", status);
    const response = await apiClient.get<Envelope<GovernancePolicy>>(
      `/governance/policies?${params.toString()}`
    );
    return response.data;
  },

  async getPolicy(policyId: string): Promise<Envelope<GovernancePolicy>> {
    const response = await apiClient.get<Envelope<GovernancePolicy>>(
      `/governance/policies/${policyId}`
    );
    return response.data;
  },

  async createPolicy(policy: {
    name: string;
    scope: string;
    rules: Record<string, unknown>;
    status?: string;
  }): Promise<Envelope<GovernancePolicy>> {
    const response = await apiClient.post<Envelope<GovernancePolicy>>(
      "/governance/policies",
      policy
    );
    return response.data;
  },

  async listAuditLogs(params?: {
    actorId?: string;
    resourceType?: string;
    action?: string;
    limit?: number;
  }): Promise<Envelope<AuditLog>> {
    const queryParams = new URLSearchParams();
    if (params?.actorId) queryParams.append("actor_id", params.actorId);
    if (params?.resourceType) queryParams.append("resource_type", params.resourceType);
    if (params?.action) queryParams.append("action", params.action);
    if (params?.limit) queryParams.append("limit", params.limit.toString());
    const response = await apiClient.get<Envelope<AuditLog>>(
      `/governance/audit/logs?${queryParams.toString()}`
    );
    return response.data;
  },

  async listCostProfiles(params?: {
    resourceType?: string;
    resourceId?: string;
    timeWindow?: string;
  }): Promise<Envelope<CostProfile>> {
    const queryParams = new URLSearchParams();
    if (params?.resourceType) queryParams.append("resource_type", params.resourceType);
    if (params?.resourceId) queryParams.append("resource_id", params.resourceId);
    if (params?.timeWindow) queryParams.append("time_window", params.timeWindow);
    const response = await apiClient.get<Envelope<CostProfile>>(
      `/governance/observability/cost-profiles?${queryParams.toString()}`
    );
    return response.data;
  },

  async getCostAggregate(params?: {
    resourceType?: string;
    startDate?: string;
    endDate?: string;
  }): Promise<Envelope<CostAggregate>> {
    const queryParams = new URLSearchParams();
    if (params?.resourceType) queryParams.append("resource_type", params.resourceType);
    if (params?.startDate) queryParams.append("start_date", params.startDate);
    if (params?.endDate) queryParams.append("end_date", params.endDate);
    const response = await apiClient.get<Envelope<CostAggregate>>(
      `/governance/observability/cost-aggregate?${queryParams.toString()}`
    );
    return response.data;
  },
};

