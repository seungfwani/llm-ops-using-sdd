<template>
  <section class="dataset-create">
    <div class="catalog-tabs">
      <router-link to="/catalog/models" class="tab-link" active-class="active">Models</router-link>
      <router-link to="/catalog/datasets" class="tab-link" active-class="active">Datasets</router-link>
    </div>
    <header>
      <h1>Create New Dataset</h1>
      <router-link to="/catalog/datasets" class="btn-back">← Back to List</router-link>
    </header>

    <form @submit.prevent="handleSubmit" class="create-form">
      <div class="form-section">
        <h2>Basic Information</h2>
        <label>
          Name *
          <input v-model="form.name" required placeholder="e.g., training-data-v1, benchmark-dataset" />
        </label>
        <label>
          Version *
          <input v-model="form.version" required placeholder="e.g., 1.0.0, v2" />
        </label>
        <label>
          Owner Team *
          <input v-model="form.owner_team" required placeholder="e.g., ml-team, data-team" />
        </label>
        <label>
          Change Log
          <textarea v-model="form.change_log" placeholder="Describe changes in this version" rows="3" />
        </label>
      </div>

      <div class="form-section">
        <h2>Dataset Files</h2>
        <label>
          Upload Dataset Files (CSV, JSONL, Parquet) *
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
              accept=".csv,.jsonl,.parquet"
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
      </div>

      <div v-if="error" class="error-message">{{ error }}</div>
      <div v-if="successMessage" class="success-message">{{ successMessage }}</div>

      <div class="form-actions">
        <button type="submit" :disabled="submitting || selectedFiles.length === 0" class="btn-primary">
          {{ submitting ? 'Creating...' : 'Create Dataset' }}
        </button>
        <router-link to="/catalog/datasets" class="btn-cancel">Cancel</router-link>
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { useRouter } from 'vue-router';
import { catalogClient } from '@/services/catalogClient';

const router = useRouter();

const form = ref({
  name: '',
  version: '',
  owner_team: '',
  change_log: '',
});

const selectedFiles = ref<File[]>([]);
const dragover = ref(false);
const submitting = ref(false);
const uploadProgress = ref(0);
const error = ref('');
const successMessage = ref('');
const fileInput = ref<HTMLInputElement | null>(null);

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function handleDrop(event: DragEvent) {
  dragover.value = false;
  const files = event.dataTransfer?.files;
  if (files) {
    selectedFiles.value = Array.from(files);
  }
}

function handleFileSelect(event: Event) {
  const target = event.target as HTMLInputElement;
  if (target.files) {
    selectedFiles.value = Array.from(target.files);
  }
}

function removeFile(index: number) {
  selectedFiles.value.splice(index, 1);
}

async function handleSubmit() {
  if (selectedFiles.value.length === 0) {
    error.value = 'Please select at least one dataset file';
    return;
  }

  submitting.value = true;
  error.value = '';
  successMessage.value = '';

  try {
    // First create the dataset entry
    const createResponse = await catalogClient.createDataset({
      name: form.value.name,
      version: form.value.version,
      owner_team: form.value.owner_team,
      change_log: form.value.change_log || undefined,
      storage_uri: '', // Will be set after upload
    });

    if (createResponse.status !== 'success' || !createResponse.data) {
      throw new Error(createResponse.message || 'Failed to create dataset');
    }

    const datasetId = createResponse.data.id;

    // Then upload files
    uploadProgress.value = 10;
    const uploadResponse = await catalogClient.uploadDatasetFiles(datasetId, selectedFiles.value);
    uploadProgress.value = 100;

    if (uploadResponse.status !== 'success') {
      throw new Error(uploadResponse.message || 'Failed to upload files');
    }

    successMessage.value = 'Dataset created successfully!';
    
    // Redirect to dataset detail page after a short delay
    setTimeout(() => {
      router.push(`/catalog/datasets/${datasetId}`);
    }, 1500);
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to create dataset';
  } finally {
    submitting.value = false;
    uploadProgress.value = 0;
  }
}
</script>

<style scoped>
.dataset-create {
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
}

.catalog-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 2px solid #e0e0e0;
}

.tab-link {
  padding: 0.75rem 1.5rem;
  text-decoration: none;
  color: #666;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.tab-link:hover {
  color: #007bff;
}

.tab-link.active {
  color: #007bff;
  border-bottom-color: #007bff;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.btn-back {
  color: #007bff;
  text-decoration: none;
  font-weight: 500;
}

.btn-back:hover {
  text-decoration: underline;
}

.create-form {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.form-section {
  margin-bottom: 2rem;
}

.form-section h2 {
  margin-bottom: 1rem;
  color: #333;
  border-bottom: 2px solid #eee;
  padding-bottom: 0.5rem;
}

.form-section label {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
  font-weight: 500;
}

.form-section input,
.form-section textarea {
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.form-section textarea {
  resize: vertical;
}

.file-upload-area {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  margin: 1rem 0;
  transition: all 0.3s;
  cursor: pointer;
}

.file-upload-area.dragover {
  border-color: #007bff;
  background: #f0f8ff;
}

.upload-placeholder {
  margin: 0;
  color: #666;
}

.link-button {
  background: none;
  border: none;
  color: #007bff;
  text-decoration: underline;
  cursor: pointer;
  padding: 0;
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
  padding: 0.75rem;
  background: #f5f5f5;
  margin: 0.5rem 0;
  border-radius: 4px;
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
}

.upload-progress {
  margin: 1rem 0;
}

.progress-bar {
  width: 100%;
  height: 20px;
  background: #f0f0f0;
  border-radius: 10px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: #007bff;
  transition: width 0.3s;
}

.progress-text {
  margin-top: 0.5rem;
  text-align: center;
  font-size: 0.9rem;
  color: #666;
}

.error-message {
  padding: 1rem;
  background: #f8d7da;
  color: #721c24;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.success-message {
  padding: 1rem;
  background: #d4edda;
  color: #155724;
  border-radius: 4px;
  margin-bottom: 1rem;
}

.form-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 2rem;
}

.btn-primary {
  padding: 0.75rem 1.5rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-cancel {
  padding: 0.75rem 1.5rem;
  background: #6c757d;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  display: inline-block;
}

.btn-cancel:hover {
  background: #5a6268;
}
</style>

