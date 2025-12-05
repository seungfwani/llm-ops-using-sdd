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
  model_family?: string; // Model family from training-serving-spec.md (llama, mistral, gemma, bert, etc.)
};

export type RegistryModelLink = {
  id: string;
  model_catalog_id: string;
  registry_type: string;
  registry_model_id: string;
  registry_repo_url: string;
  registry_version?: string | null;
  imported: boolean;
  sync_status: string;
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
  type?: string; // Dataset type from training-serving-spec.md (pretrain_corpus, sft_pair, rag_qa, rlhf_pair)
};

export type DatasetVersion = {
  id: string;
  dataset_record_id: string;
  versioning_system: string;
  version_id: string;
  parent_version_id?: string | null;
  version_tag?: string | null;
  checksum: string;
  storage_uri: string;
  diff_summary?: Record<string, unknown> | null;
  file_count: number;
  total_size_bytes: number;
  compression_ratio?: number | null;
  created_at: string;
  created_by: string;
};

export type DatasetVersionDiff = {
  added_files: string[];
  removed_files: string[];
  modified_files: string[];
  added_rows: number;
  removed_rows: number;
  schema_changes: Record<string, unknown>;
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
    model_family: string; // Model family from training-serving-spec.md (llama, mistral, gemma, bert, etc.) - Required
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
    model_family: string; // Required for training-serving-spec.md
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

  async importFromRegistry(payload: {
    registry_type: string;
    registry_model_id: string;
    version?: string | null;
    name?: string | null;
    model_version?: string;
    model_type?: string;
    owner_team?: string;
  }): Promise<Envelope<CatalogModel>> {
    const response = await apiClient.post<Envelope<CatalogModel>>(
      "/catalog/models/import",
      payload,
      {
        timeout: 1800000,
      }
    );
    return response.data;
  },

  async exportToRegistry(
    modelId: string,
    payload: {
      registry_type: string;
      registry_model_id?: string;
      repository_name?: string;
      private?: boolean;
      version_tag?: string;
      metadata?: Record<string, unknown>;
    }
  ): Promise<Envelope<RegistryModelLink>> {
    const response = await apiClient.post<Envelope<RegistryModelLink>>(
      `/catalog/models/${modelId}/export`,
      payload
    );
    return response.data;
  },

  async getRegistryLinks(modelId: string): Promise<Envelope<RegistryModelLink>> {
    const response = await apiClient.get<Envelope<RegistryModelLink>>(
      `/catalog/models/${modelId}/registry-links`
    );
    return response.data;
  },

  async checkRegistryUpdates(
    modelId: string
  ): Promise<Envelope<{ updates_available: boolean; registry_links: any[] }>> {
    const response = await apiClient.post<
      Envelope<{ updates_available: boolean; registry_links: any[] }>
    >(`/catalog/models/${modelId}/check-updates`);
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
    type: string; // Dataset type from training-serving-spec.md (pretrain_corpus, sft_pair, rag_qa, rlhf_pair) - Required
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

  // Dataset versioning methods
  async listDatasetVersions(datasetId: string): Promise<Envelope<DatasetVersion>> {
    const response = await apiClient.get<Envelope<DatasetVersion>>(
      `/catalog/datasets/${datasetId}/versions`
    );
    return response.data;
  },

  async createDatasetVersion(
    datasetId: string,
    payload: { version_tag?: string; parent_version_id?: string | null }
  ): Promise<Envelope<DatasetVersion>> {
    const response = await apiClient.post<Envelope<DatasetVersion>>(
      `/catalog/datasets/${datasetId}/versions`,
      payload
    );
    return response.data;
  },

  async getDatasetVersionDiff(
    datasetId: string,
    versionId: string,
    baseVersionId: string
  ): Promise<Envelope<DatasetVersionDiff>> {
    const response = await apiClient.get<Envelope<DatasetVersionDiff>>(
      `/catalog/datasets/${datasetId}/versions/${versionId}/diff`,
      {
        params: {
          baseVersionId,
        },
      }
    );
    return response.data;
  },

  async restoreDatasetVersion(
    datasetId: string,
    versionId: string
  ): Promise<Envelope<DatasetVersion>> {
    const response = await apiClient.post<Envelope<DatasetVersion>>(
      `/catalog/datasets/${datasetId}/versions/${versionId}/restore`,
      {}
    );
    return response.data;
  },
};

