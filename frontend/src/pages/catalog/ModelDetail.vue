<template>
  <section class="model-detail">
    <header>
      <h1>Model Detail</h1>
    </header>

    <div v-if="loading" class="loading">Loading model details...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="model" class="detail-content">
      <!-- Import Status Alert -->
      <div v-if="model.metadata?.import_status === 'failed'" class="import-error-alert">
        <h3>⚠️ Import Failed</h3>
        <p class="error-message">{{ model.metadata.import_error || 'Model import failed. Please check the error details.' }}</p>
        <p class="error-hint">You can try importing again or delete this model entry.</p>
      </div>
      
      <div v-else-if="model.metadata?.import_status === 'completed'" class="import-success-alert">
        <p>✅ Model import completed successfully.</p>
      </div>
      
      <div v-else-if="isHuggingFaceModel && !model.storage_uri" class="import-progress-alert">
        <p>⏳ Model import is in progress. Please wait or refresh the page to check the status.</p>
      </div>

      <div class="detail-section">
        <h2>Basic Information</h2>
        <dl class="detail-list">
          <dt>Model ID</dt>
          <dd class="monospace">{{ model.id }}</dd>
          
          <dt>Name</dt>
          <dd><strong>{{ model.name }}</strong></dd>
          
          <dt>Version</dt>
          <dd>{{ model.version }}</dd>
          
          <dt>Type</dt>
          <dd>
            <span :class="`type-badge type-${model.type}`">
              {{ model.type }}
            </span>
          </dd>
          
          <dt>Status</dt>
          <dd>
            <span :class="`status-badge status-${model.status}`">
              {{ model.status }}
            </span>
          </dd>
          
          <dt>Owner Team</dt>
          <dd>{{ model.owner_team }}</dd>
          
          <dt>Storage URI</dt>
          <dd v-if="model.storage_uri" class="monospace storage-uri-value">{{ model.storage_uri }}</dd>
          <dd v-else class="text-muted">
            <span v-if="isHuggingFaceModel && model.metadata?.import_status !== 'failed'">Files are being uploaded from Hugging Face...</span>
            <span v-else-if="model.metadata?.import_status === 'failed'">Import failed - no files available</span>
            <span v-else>No files uploaded</span>
          </dd>
        </dl>
      </div>

      <div class="detail-section">
        <h2>Metadata</h2>
        <pre class="metadata-display">{{ JSON.stringify(model.metadata, null, 2) }}</pre>
      </div>

      <div v-if="registryLinks.length" class="detail-section">
        <h2>Registry Links</h2>
        <ul class="registry-list">
          <li v-for="link in registryLinks" :key="link.id" class="registry-item">
            <div class="registry-main">
              <span class="registry-type">{{ link.registry_type }}</span>
              <a
                v-if="link.registry_repo_url"
                :href="link.registry_repo_url"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ link.registry_model_id }}
              </a>
              <span v-else class="monospace">{{ link.registry_model_id }}</span>
            </div>
            <div class="registry-meta">
              <span v-if="link.registry_version" class="badge">
                version: {{ link.registry_version }}
              </span>
              <span class="badge" :class="link.imported ? 'badge-imported' : 'badge-exported'">
                {{ link.imported ? 'imported' : 'exported' }}
              </span>
              <span class="badge" :class="`badge-sync-${link.sync_status}`">
                {{ link.sync_status }}
              </span>
            </div>
          </li>
        </ul>
        <div class="registry-actions">
          <button class="btn-secondary" :disabled="checkingUpdates" @click="handleCheckUpdates">
            {{ checkingUpdates ? 'Checking updates...' : 'Check for Registry Updates' }}
          </button>
          <p v-if="updatesAvailable" class="update-hint">
            Updates are available for one or more registry models. Please review in the registry UI.
          </p>
        </div>
      </div>

      <div class="detail-section">
        <h2>Model Files</h2>
        <div v-if="model.storage_uri" class="storage-info">
          <p><strong>Storage Location:</strong> <span class="monospace">{{ model.storage_uri }}</span></p>
          <p v-if="model.metadata?.model_size_gb" class="file-size-info">
            <strong>Model Size:</strong> {{ formatModelSize(model.metadata.model_size_gb) }}
          </p>
          <p v-if="isHuggingFaceModel" class="import-source">
            <strong>Source:</strong> Imported from Hugging Face ({{ model.metadata?.huggingface_model_id || 'N/A' }})
          </p>
        </div>
        <div v-else class="no-storage-info">
          <p v-if="isHuggingFaceModel" class="info-message">
            This model was imported from Hugging Face. Files should be available shortly.
          </p>
          <p v-else class="info-message">
            No files have been uploaded for this model yet.
          </p>
        </div>
        <div class="file-upload-section">
          <label>
            Upload Model Files
            <div class="file-upload-area" 
                 @drop.prevent="handleDrop"
                 @dragover.prevent="dragover = true"
                 @dragleave.prevent="dragover = false"
                 :class="{ 'dragover': dragover }">
              <input 
                type="file" 
                ref="fileInput"
                @change="handleFileSelect"
                multiple
                accept=".bin,.safetensors,.json,.txt,.pt,.pth,.onnx"
                style="display: none"
              />
              <p v-if="selectedFiles.length === 0" class="upload-placeholder">
                Drag and drop files here or <button type="button" @click="fileInput?.click()" class="link-button">browse</button>
              </p>
              <ul v-else class="file-list">
                <li v-for="(file, index) in selectedFiles" :key="index" class="file-item">
                  <span>{{ file.name }} ({{ formatFileSize(file.size) }})</span>
                  <button type="button" @click="removeFile(index)" class="remove-file">×</button>
                </li>
              </ul>
            </div>
          </label>
          <div v-if="uploadProgress > 0 && uploadProgress < 100" class="upload-progress">
            <div class="progress-bar">
              <div class="progress-fill" :style="{ width: uploadProgress + '%' }"></div>
            </div>
            <p class="progress-text">Uploading... {{ uploadProgress }}%</p>
          </div>
          <button 
            v-if="selectedFiles.length > 0" 
            @click="handleUpload" 
            :disabled="uploading"
            class="btn-primary"
          >
            {{ uploading ? 'Uploading...' : 'Upload Files' }}
          </button>
        </div>
      </div>

      <div class="detail-section">
        <h2>Actions</h2>
        <div class="actions">
          <label>
            Update Status:
            <select v-model="newStatus" @change="handleStatusUpdate">
              <option value="">Select status...</option>
              <option value="draft">Draft</option>
              <option value="pending_review">Pending Review</option>
              <option value="approved">Approved</option>
              <option value="rejected">Rejected</option>
            </select>
          </label>
          <button
            class="btn-secondary"
            type="button"
            :disabled="exporting"
            @click="handleExport"
          >
            {{ exporting ? 'Exporting...' : 'Export to Registry' }}
          </button>
          <button @click="refreshModel" :disabled="loading" class="btn-secondary">
            Refresh
          </button>
          <button 
            @click="handleDelete" 
            :disabled="loading || deleting" 
            class="btn-delete"
          >
            {{ deleting ? 'Deleting...' : 'Delete Model' }}
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { catalogClient, type CatalogModel, type RegistryModelLink } from '@/services/catalogClient';

const route = useRoute();
const router = useRouter();
const model = ref<CatalogModel | null>(null);
const loading = ref(false);
const error = ref('');
const newStatus = ref('');
const dragover = ref(false);
const selectedFiles = ref<File[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const uploadProgress = ref(0);
const deleting = ref(false);
const exporting = ref(false);
const registryLinks = ref<RegistryModelLink[]>([]);
const checkingUpdates = ref(false);
const updatesAvailable = ref(false);

async function fetchModel() {
  const modelId = route.params.id as string;
  if (!modelId) {
    error.value = 'Model ID is required';
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    const response = await catalogClient.getModel(modelId);
    if (response.status === "success" && response.data) {
      model.value = Array.isArray(response.data) ? response.data[0] : response.data;
      newStatus.value = model.value.status;
    } else {
      error.value = response.message || "Failed to load model";
      model.value = null;
    }
  } catch (e) {
    error.value = `Error: ${e}`;
    model.value = null;
  } finally {
    loading.value = false;
  }
}

async function fetchRegistryLinks() {
  const modelId = route.params.id as string;
  if (!modelId) return;
  try {
    const response = await catalogClient.getRegistryLinks(modelId);
    if (response.status === 'success' && response.data) {
      registryLinks.value = Array.isArray(response.data) ? response.data : [response.data];
    } else {
      registryLinks.value = [];
    }
  } catch {
    registryLinks.value = [];
  }
}

async function handleStatusUpdate() {
  if (!model.value || !newStatus.value || newStatus.value === model.value.status) {
    return;
  }

  if (!confirm(`Are you sure you want to change status to "${newStatus.value}"?`)) {
    newStatus.value = model.value.status;
    return;
  }

  loading.value = true;
  try {
    const response = await catalogClient.updateModelStatus(model.value.id, newStatus.value);
    if (response.status === "success") {
      await fetchModel();
      alert('Status updated successfully');
    } else {
      alert(`Status update failed: ${response.message}`);
      newStatus.value = model.value.status;
    }
  } catch (e) {
    alert(`Error: ${e}`);
    newStatus.value = model.value?.status || '';
  } finally {
    loading.value = false;
  }
}

function refreshModel() {
  fetchModel();
  fetchRegistryLinks();
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    selectedFiles.value = Array.from(target.files);
  }
}

function handleDrop(event: DragEvent) {
  dragover.value = false;
  if (event.dataTransfer?.files) {
    selectedFiles.value = Array.from(event.dataTransfer.files);
  }
}

function removeFile(index: number) {
  selectedFiles.value.splice(index, 1);
}

const isHuggingFaceModel = computed(() => {
  return model.value?.metadata?.source === 'huggingface' || 
         model.value?.metadata?.huggingface_model_id !== undefined;
});

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function formatModelSize(gb: number): string {
  if (gb < 1) {
    const mb = gb * 1024;
    return `${mb.toFixed(2)} MB`;
  }
  return `${gb.toFixed(2)} GB`;
}

async function handleUpload() {
  if (!model.value || selectedFiles.value.length === 0) return;
  
  uploading.value = true;
  uploadProgress.value = 0;
  error.value = '';
  
  try {
    // Simulate progress (in real implementation, use axios onUploadProgress)
    const progressInterval = setInterval(() => {
      if (uploadProgress.value < 90) {
        uploadProgress.value += 10;
      }
    }, 200);
    
    const response = await catalogClient.uploadModelFiles(model.value.id, selectedFiles.value);
    
    clearInterval(progressInterval);
    uploadProgress.value = 100;
    
    if (response.status === "success") {
      selectedFiles.value = [];
      await fetchModel(); // Refresh model to show updated storage_uri
      setTimeout(() => {
        uploadProgress.value = 0;
      }, 1000);
    } else {
      error.value = response.message || 'Upload failed';
      uploadProgress.value = 0;
    }
  } catch (e) {
    error.value = `Upload error: ${e}`;
    uploadProgress.value = 0;
  } finally {
    uploading.value = false;
  }
}

async function handleExport() {
  if (!model.value) return;
  const modelId = model.value.id;

  const registryModelId = prompt(
    'Enter target registry model ID (leave blank to derive from model name):',
    model.value.name.replace(/_/g, '-')
  ) || undefined;

  exporting.value = true;
  try {
    const response = await catalogClient.exportToRegistry(modelId, {
      registry_type: 'huggingface',
      registry_model_id: registryModelId,
    });
    if (response.status === 'success') {
      alert('Model exported to registry successfully');
      await fetchRegistryLinks();
    } else {
      alert(`Export failed: ${response.message}`);
    }
  } catch (e) {
    alert(`Error exporting model: ${e}`);
  } finally {
    exporting.value = false;
  }
}

async function handleCheckUpdates() {
  if (!model.value) return;
  checkingUpdates.value = true;
  updatesAvailable.value = false;
  try {
    const response = await catalogClient.checkRegistryUpdates(model.value.id);
    if (response.status === 'success' && response.data) {
      const data = Array.isArray(response.data) ? response.data[0] : response.data;
      updatesAvailable.value = !!data.updates_available;
      if (Array.isArray(data.registry_links)) {
        // sync_status는 ModelRegistryService 쪽에서 이미 업데이트하지만,
        // 프론트에서도 사용자에게 힌트를 주기 위해 갱신해 둔다.
        await fetchRegistryLinks();
      }
    } else {
      alert(response.message || 'Failed to check updates');
    }
  } catch (e) {
    alert(`Error checking updates: ${e}`);
  } finally {
    checkingUpdates.value = false;
  }
}

async function handleDelete() {
  if (!model.value) return;

  const modelName = model.value.name;
  const modelId = model.value.id;

  if (!confirm(`Are you sure you want to delete model "${modelName}" (${modelId})? This action cannot be undone.`)) {
    return;
  }

  deleting.value = true;
  try {
    const response = await catalogClient.deleteModel(modelId);
    if (response.status === "success") {
      alert('Model deleted successfully');
      router.push('/catalog/models'); // Navigate back to list
    } else {
      alert(`Failed to delete model: ${response.message}`);
    }
  } catch (e) {
    alert(`Error deleting model: ${e}`);
  } finally {
    deleting.value = false;
  }
}

onMounted(fetchModel);
</script>

<style scoped>
.model-detail {
  padding: 2rem;
  max-width: 900px;
  margin: 0 auto;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.btn-back {
  padding: 0.5rem 1rem;
  background: #6c757d;
  color: white;
  text-decoration: none;
  border-radius: 4px;
}

.btn-back:hover {
  background: #5a6268;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.import-error-alert {
  background: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 8px;
  padding: 1.5rem;
  margin-bottom: 2rem;
  color: #721c24;
}

.import-error-alert h3 {
  margin-top: 0;
  margin-bottom: 0.75rem;
  color: #721c24;
}

.import-error-alert .error-message {
  margin: 0.5rem 0;
  font-weight: 500;
  white-space: pre-wrap;
  word-break: break-word;
}

.import-error-alert .error-hint {
  margin: 0.75rem 0 0 0;
  font-size: 0.9rem;
  color: #856404;
}

.import-success-alert {
  background: #d4edda;
  border: 1px solid #c3e6cb;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 2rem;
  color: #155724;
}

.import-progress-alert {
  background: #e7f3ff;
  border: 1px solid #b3d9ff;
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 2rem;
  color: #004085;
}

.detail-section {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.detail-section h2 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.25rem;
}

.detail-list {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 1rem;
  margin: 0;
}

.detail-list dt {
  font-weight: 600;
  color: #666;
}

.detail-list dd {
  margin: 0;
  color: #333;
}

.monospace {
  font-family: monospace;
  font-size: 0.9rem;
  background: #f8f9fa;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  display: inline-block;
}

.metadata-display {
  background: #f8f9fa;
  padding: 1rem;
  border-radius: 4px;
  overflow-x: auto;
  font-family: monospace;
  font-size: 0.9rem;
  max-height: 400px;
  overflow-y: auto;
}

.type-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: capitalize;
  display: inline-block;
}

.type-base {
  background: #d1ecf1;
  color: #0c5460;
}

.type-fine-tuned {
  background: #d4edda;
  color: #155724;
}

.type-external {
  background: #fff3cd;
  color: #856404;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: capitalize;
  display: inline-block;
}

.status-draft {
  background: #e2e3e5;
  color: #383d41;
}

.status-pending_review {
  background: #fff3cd;
  color: #856404;
}

.status-approved {
  background: #d4edda;
  color: #155724;
}

.status-rejected {
  background: #f8d7da;
  color: #721c24;
}

.actions {
  display: flex;
  gap: 1rem;
  align-items: flex-end;
}

.actions label {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.actions select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  min-width: 200px;
}

.btn-secondary {
  padding: 0.5rem 1rem;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  height: fit-content;
}

.btn-secondary:hover:not(:disabled) {
  background: #5a6268;
}

.btn-secondary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-delete {
  padding: 0.5rem 1rem;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  height: fit-content;
}

.btn-delete:hover:not(:disabled) {
  background: #c82333;
}

.btn-delete:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.text-muted {
  color: #6c757d;
  font-style: italic;
}

.storage-info {
  margin-bottom: 1rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 4px;
}

.storage-info p {
  margin: 0.5rem 0;
}

.storage-info .file-size-info {
  color: #495057;
  font-size: 0.9rem;
}

.storage-info .import-source {
  color: #6c757d;
  font-size: 0.85rem;
  font-style: italic;
}

.storage-uri-value {
  word-break: break-all;
  background: #f8f9fa;
  padding: 0.5rem;
  border-radius: 4px;
  display: inline-block;
  max-width: 100%;
}

.no-storage-info {
  margin-bottom: 1rem;
  padding: 1rem;
  background: #fff3cd;
  border: 1px solid #ffc107;
  border-radius: 4px;
}

.no-storage-info .info-message {
  margin: 0;
  color: #856404;
}

.registry-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.registry-item {
  display: flex;
  flex-direction: column;
  padding: 0.75rem;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  background: #f8f9fa;
}

.registry-main {
  display: flex;
  gap: 0.5rem;
  align-items: center;
  margin-bottom: 0.25rem;
}

.registry-type {
  text-transform: uppercase;
  font-size: 0.75rem;
  font-weight: 700;
  color: #6c757d;
}

.registry-meta {
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.badge {
  padding: 0.15rem 0.5rem;
  font-size: 0.75rem;
  border-radius: 999px;
  background: #e2e3e5;
  color: #383d41;
}

.badge-imported {
  background: #d4edda;
  color: #155724;
}

.badge-exported {
  background: #d1ecf1;
  color: #0c5460;
}

.badge-sync-synced {
  background: #d4edda;
  color: #155724;
}

.badge-sync-out_of_sync {
  background: #fff3cd;
  color: #856404;
}

.badge-sync-never_synced {
  background: #e2e3e5;
  color: #383d41;
}

.registry-actions {
  margin-top: 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.update-hint {
  font-size: 0.85rem;
  color: #856404;
}

.file-upload-section {
  margin-top: 1rem;
}

.file-upload-area {
  border: 2px dashed #ddd;
  border-radius: 4px;
  padding: 2rem;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s;
  background: #f8f9fa;
  margin-top: 0.5rem;
}

.file-upload-area:hover,
.file-upload-area.dragover {
  border-color: #007bff;
  background: #e7f3ff;
}

.upload-placeholder {
  margin: 0;
  color: #6c757d;
}

.link-button {
  background: none;
  border: none;
  color: #007bff;
  text-decoration: underline;
  cursor: pointer;
  padding: 0;
  font-size: inherit;
}

.link-button:hover {
  color: #0056b3;
}

.file-list {
  list-style: none;
  padding: 0;
  margin: 0;
  text-align: left;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
  background: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  margin-bottom: 0.5rem;
}

.remove-file {
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  cursor: pointer;
  font-size: 1.2rem;
  line-height: 1;
  padding: 0;
}

.remove-file:hover {
  background: #c82333;
}

.upload-progress {
  margin-top: 1rem;
}

.progress-bar {
  width: 100%;
  height: 20px;
  background: #e9ecef;
  border-radius: 10px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: #28a745;
  transition: width 0.3s;
}

.progress-text {
  margin: 0;
  font-size: 0.9rem;
  color: #6c757d;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
}

.error {
  color: #dc3545;
}
</style>

