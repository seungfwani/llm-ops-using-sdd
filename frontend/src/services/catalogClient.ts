import apiClient from "./apiClient";

export type CatalogModel = {
  id: string;
  name: string;
  version: string;
  type: string;
  status: string;
  owner_team: string;
  metadata: Record<string, unknown>;
  storage_uri?: string;
};

export interface Envelope<T> {
  status: "success" | "fail";
  message: string;
  data?: T | T[];
}

export const catalogClient = {
  async listModels(): Promise<Envelope<CatalogModel>> {
    const response = await apiClient.get<Envelope<CatalogModel>>("/catalog/models");
    return response.data;
  },

  async getModel(modelId: string): Promise<Envelope<CatalogModel>> {
    const response = await apiClient.get<Envelope<CatalogModel>>(`/catalog/models/${modelId}`);
    return response.data;
  },

  async createModel(payload: {
    name: string;
    version: string;
    type: string;
    owner_team: string;
    metadata: Record<string, unknown>;
    lineage_dataset_ids?: string[];
  }): Promise<Envelope<CatalogModel>> {
    const response = await apiClient.post<Envelope<CatalogModel>>("/catalog/models", payload);
    return response.data;
  },

  async updateModelStatus(modelId: string, status: string): Promise<Envelope<CatalogModel>> {
    const response = await apiClient.patch<Envelope<CatalogModel>>(
      `/catalog/models/${modelId}/status?status=${status}`
    );
    return response.data;
  },

  async uploadModelFiles(modelId: string, files: File[]): Promise<Envelope<CatalogModel>> {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file);
    });

    const response = await apiClient.post<Envelope<CatalogModel>>(
      `/catalog/models/${modelId}/upload`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  },
};

