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

export type CatalogDataset = {
  id: string;
  name: string;
  version: string;
  storage_uri: string;
  owner_team: string;
  pii_scan_status: string;
  quality_score: number | null;
  change_log?: string | null;
  approved_at?: string | null;
  created_at: string;
  updated_at: string;
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

  async deleteModel(modelId: string): Promise<Envelope<{ model_id: string; storage_cleaned: boolean }>> {
    const response = await apiClient.delete<Envelope<{ model_id: string; storage_cleaned: boolean }>>(
      `/catalog/models/${modelId}`
    );
    return response.data;
  },

  async importFromHuggingFace(payload: {
    hf_model_id: string;
    name?: string;
    version?: string;
    model_type?: string;
    owner_team?: string;
    hf_token?: string;
  }): Promise<Envelope<CatalogModel>> {
    const response = await apiClient.post<Envelope<CatalogModel>>(
      "/catalog/models/import-from-huggingface",
      payload,
      {
        timeout: 1800000, // 30 minutes timeout for Hugging Face import (large models can take time)
      }
    );
    return response.data;
  },

  // Dataset methods
  async listDatasets(): Promise<Envelope<CatalogDataset>> {
    const response = await apiClient.get<Envelope<CatalogDataset>>("/catalog/datasets");
    return response.data;
  },

  async getDataset(datasetId: string): Promise<Envelope<CatalogDataset>> {
    const response = await apiClient.get<Envelope<CatalogDataset>>(`/catalog/datasets/${datasetId}`);
    return response.data;
  },

  async createDataset(payload: {
    name: string;
    version: string;
    owner_team: string;
    change_log?: string;
    storage_uri?: string;
  }): Promise<Envelope<CatalogDataset>> {
    const response = await apiClient.post<Envelope<CatalogDataset>>("/catalog/datasets", payload);
    return response.data;
  },

  async uploadDatasetFiles(datasetId: string, files: File[]): Promise<Envelope<CatalogDataset>> {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append("files", file);
    });

    const response = await apiClient.post<Envelope<CatalogDataset>>(
      `/catalog/datasets/${datasetId}/upload`,
      formData,
      {
        headers: {
          "Content-Type": "multipart/form-data",
        },
      }
    );
    return response.data;
  },

  async previewDataset(datasetId: string, limit: number = 10): Promise<Envelope<any>> {
    const response = await apiClient.get<Envelope<any>>(
      `/catalog/datasets/${datasetId}/preview?limit=${limit}`
    );
    return response.data;
  },

  async getDatasetValidation(datasetId: string): Promise<Envelope<any>> {
    const response = await apiClient.get<Envelope<any>>(
      `/catalog/datasets/${datasetId}/validation`
    );
    return response.data;
  },

  async updateDatasetStatus(datasetId: string, status: string): Promise<Envelope<CatalogDataset>> {
    const response = await apiClient.patch<Envelope<CatalogDataset>>(
      `/catalog/datasets/${datasetId}/status?status=${status}`
    );
    return response.data;
  },
};

