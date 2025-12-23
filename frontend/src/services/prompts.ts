import apiClient from './apiClient';

const API_BASE = '/prompts/templates';

export interface PromptTemplate {
  id: string;
  name: string;
  version: string;
  language?: string;
  content: string;
  context_tags?: string[];
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplateCreate {
  name: string;
  version: string;
  language?: string;
  content: string;
  context_tags?: string[];
  status?: string;
}

export interface PromptTemplateUpdate {
  name?: string;
  version?: string;
  language?: string;
  content?: string;
  context_tags?: string[];
  status?: string;
}

export interface EnvelopeSingle {
  status: string;
  message?: string;
  data?: PromptTemplate;
}

export interface EnvelopeList {
  status: string;
  message?: string;
  data?: PromptTemplate[];
}

export async function fetchPromptTemplates(status?: string) {
  const params = status ? { status } : {};
  const { data } = await apiClient.get<EnvelopeList>(API_BASE, { params });
  return data.data || [];
}

export async function fetchPromptTemplate(id: string) {
  const { data } = await apiClient.get<EnvelopeSingle>(`${API_BASE}/${id}`);
  return data.data;
}

export async function createPromptTemplate(payload: PromptTemplateCreate) {
  const { data } = await apiClient.post<EnvelopeSingle>(API_BASE, payload);
  return data.data;
}

export async function updatePromptTemplate(id: string, payload: PromptTemplateUpdate) {
  const { data } = await apiClient.put<EnvelopeSingle>(`${API_BASE}/${id}`, payload);
  return data.data;
}

export async function deletePromptTemplate(id: string) {
  const { data } = await apiClient.delete<EnvelopeSingle>(`${API_BASE}/${id}`);
  return data.status === 'success';
}

