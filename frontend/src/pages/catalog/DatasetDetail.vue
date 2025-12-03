<template>
  <section class="dataset-detail">
    <div class="catalog-tabs">
      <router-link to="/catalog/models" class="tab-link" active-class="active">Models</router-link>
      <router-link to="/catalog/datasets" class="tab-link" active-class="active">Datasets</router-link>
    </div>
    <header>
      <h1>Dataset Details</h1>
      <router-link to="/catalog/datasets" class="btn-back">← Back to List</router-link>
    </header>

    <div v-if="loading" class="loading">Loading dataset details...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="dataset" class="detail-content">
      <div class="detail-section">
        <h2>Basic Information</h2>
        <dl class="detail-list">
          <dt>Dataset ID</dt>
          <dd class="monospace">{{ dataset.id }}</dd>
          
          <dt>Name</dt>
          <dd><strong>{{ dataset.name }}</strong></dd>
          
          <dt>Version</dt>
          <dd>{{ dataset.version }}</dd>
          
          <dt>Owner Team</dt>
          <dd>{{ dataset.owner_team }}</dd>
          
          <dt>Storage URI</dt>
          <dd v-if="dataset.storage_uri" class="monospace">{{ dataset.storage_uri }}</dd>
          <dd v-else class="text-muted">No files uploaded</dd>
          
          <dt>PII Scan Status</dt>
          <dd>
            <span :class="`pii-badge pii-${dataset.pii_scan_status}`">
              {{ dataset.pii_scan_status }}
            </span>
          </dd>
          
          <dt>Quality Score</dt>
          <dd>
            <span :class="getQualityScoreClass(dataset.quality_score)">
              {{ dataset.quality_score ?? 'N/A' }}
            </span>
          </dd>
          
          <dt>Approval Status</dt>
          <dd>
            <div style="display: flex; align-items: center; gap: 1rem;">
              <span :class="`approval-badge ${getApprovalStatus()}`">
                {{ getApprovalStatusLabel() }}
            </span>
              <select 
                v-model="selectedStatus" 
                @change="handleStatusChange"
                :disabled="statusUpdating"
                class="status-select"
              >
                <option value="draft">Draft</option>
                <option value="under_review">Under Review</option>
                <option value="approved">Approved</option>
                <option value="rejected">Rejected</option>
              </select>
            </div>
          </dd>
          
          <dt v-if="dataset.change_log">Change Log</dt>
          <dd v-if="dataset.change_log">{{ dataset.change_log }}</dd>
        </dl>
      </div>

      <div class="detail-section" v-if="dataset.storage_uri">
        <h2>Dataset Preview</h2>
        <div v-if="previewLoading" class="loading">Loading preview...</div>
        <div v-else-if="previewError" class="error">{{ previewError }}</div>
        <div v-else-if="preview">
          <div class="preview-stats">
            <p><strong>Total Rows:</strong> {{ preview.statistics?.total_rows ?? 'N/A' }}</p>
            <p><strong>Column Count:</strong> {{ preview.statistics?.column_count ?? 'N/A' }}</p>
            <p><strong>File Size:</strong> {{ formatFileSize(preview.statistics?.file_size ?? 0) }}</p>
            <p><strong>Format:</strong> {{ preview.statistics?.format ?? 'unknown' }}</p>
          </div>
          <div v-if="preview.schema && Object.keys(preview.schema).length > 0" class="schema-section">
            <h3>Schema</h3>
            <pre class="schema-display">{{ JSON.stringify(preview.schema, null, 2) }}</pre>
          </div>
          <div v-if="preview.sample_rows && preview.sample_rows.length > 0" class="sample-rows">
            <h3>Sample Rows</h3>
            <table class="preview-table">
              <thead>
                <tr>
                  <th v-for="(_, index) in preview.sample_rows[0]" :key="index">Column {{ index + 1 }}</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, rowIndex) in preview.sample_rows.slice(0, 10)" :key="rowIndex">
                  <td v-for="(cell, cellIndex) in row" :key="cellIndex">{{ cell }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
        <button @click="loadPreview" class="btn-secondary">Refresh Preview</button>
      </div>

      <div class="detail-section">
        <h2>Validation Results</h2>
        <div v-if="validationLoading" class="loading">Loading validation results...</div>
        <div v-else-if="validationError" class="error">{{ validationError }}</div>
        <div v-else-if="validation">
          <div class="validation-section">
            <h3>PII Scan</h3>
            <p><strong>Status:</strong> 
              <span :class="`pii-badge pii-${validation.pii_scan?.status}`">
                {{ validation.pii_scan?.status }}
              </span>
            </p>
            <div v-if="validation.pii_scan?.detected_types?.length" class="pii-detected">
              <p><strong>Detected PII Types:</strong></p>
              <ul>
                <li v-for="type in validation.pii_scan.detected_types" :key="type">{{ type }}</li>
              </ul>
            </div>
          </div>
          <div class="validation-section">
            <h3>Quality Score</h3>
            <p><strong>Overall Score:</strong> 
              <span :class="getQualityScoreClass(validation.quality_score?.overall)">
                {{ validation.quality_score?.overall ?? 'N/A' }}
              </span>
            </p>
            <div v-if="validation.quality_score?.breakdown" class="quality-breakdown">
              <p><strong>Breakdown:</strong></p>
              <ul>
                <li>Missing Values: {{ validation.quality_score.breakdown.missing_values ?? 'N/A' }}%</li>
                <li>Duplicates: {{ validation.quality_score.breakdown.duplicates ?? 'N/A' }}%</li>
                <li>Distribution: {{ validation.quality_score.breakdown.distribution ?? 'N/A' }}</li>
                <li>Schema Compliance: {{ validation.quality_score.breakdown.schema_compliance ?? 'N/A' }}</li>
              </ul>
            </div>
          </div>
        </div>
        <button @click="loadValidation" class="btn-secondary">Refresh Validation</button>
      </div>

      <div class="detail-section">
        <h2>File Upload</h2>
        <div class="file-upload-section">
          <label>
            Upload Dataset Files (CSV, JSONL, Parquet)
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
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from 'vue';
import { useRoute } from 'vue-router';
import { catalogClient, type CatalogDataset } from '@/services/catalogClient';

const route = useRoute();
const datasetId = computed(() => route.params.id as string);

const dataset = ref<CatalogDataset | null>(null);
const preview = ref<any>(null);
const validation = ref<any>(null);
const loading = ref(false);
const previewLoading = ref(false);
const validationLoading = ref(false);
const error = ref('');
const previewError = ref('');
const validationError = ref('');

const selectedFiles = ref<File[]>([]);
const dragover = ref(false);
const uploading = ref(false);
const uploadProgress = ref(0);
const fileInput = ref<HTMLInputElement | null>(null);
const selectedStatus = ref<string>('draft');
const statusUpdating = ref(false);

function getQualityScoreClass(score: number | null): string {
  if (score === null) return 'quality-score na';
  if (score >= 80) return 'quality-score high';
  if (score >= 60) return 'quality-score medium';
  return 'quality-score low';
}

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function getApprovalStatus(): string {
  if (!dataset.value) return 'pending';
  if (dataset.value.approved_at) return 'approved';
  return 'pending';
}

function getApprovalStatusLabel(): string {
  if (!dataset.value) return 'Pending';
  if (dataset.value.approved_at) return 'Approved';
  return 'Pending';
}

async function fetchDataset() {
  loading.value = true;
  error.value = '';
  try {
    const response = await catalogClient.getDataset(datasetId.value);
    if (response.status === 'success' && response.data) {
      dataset.value = response.data;
      // Set initial status based on approved_at
      selectedStatus.value = dataset.value.approved_at ? 'approved' : 'draft';
    } else {
      error.value = response.message || 'Failed to fetch dataset';
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch dataset';
  } finally {
    loading.value = false;
  }
}

async function handleStatusChange() {
  if (!dataset.value || selectedStatus.value === (dataset.value.approved_at ? 'approved' : 'draft')) {
    return;
  }

  if (!confirm(`Are you sure you want to change the dataset status to "${selectedStatus.value}"?`)) {
    // Reset to original status
    selectedStatus.value = dataset.value.approved_at ? 'approved' : 'draft';
    return;
  }

  statusUpdating.value = true;
  try {
    const response = await catalogClient.updateDatasetStatus(datasetId.value, selectedStatus.value);
    if (response.status === 'success') {
      alert('Dataset status updated successfully');
      await fetchDataset();
    } else {
      alert(`Failed to update status: ${response.message}`);
      // Reset to original status
      selectedStatus.value = dataset.value.approved_at ? 'approved' : 'draft';
    }
  } catch (err) {
    alert(`Error updating status: ${err}`);
    // Reset to original status
    if (dataset.value) {
      selectedStatus.value = dataset.value.approved_at ? 'approved' : 'draft';
    }
  } finally {
    statusUpdating.value = false;
  }
}

async function loadPreview() {
  previewLoading.value = true;
  previewError.value = '';
  try {
    const response = await catalogClient.previewDataset(datasetId.value, 10);
    if (response.status === 'success' && response.data) {
      preview.value = response.data;
    } else {
      previewError.value = response.message || 'Failed to load preview';
    }
  } catch (err) {
    previewError.value = err instanceof Error ? err.message : 'Failed to load preview';
  } finally {
    previewLoading.value = false;
  }
}

async function loadValidation() {
  validationLoading.value = true;
  validationError.value = '';
  try {
    const response = await catalogClient.getDatasetValidation(datasetId.value);
    if (response.status === 'success' && response.data) {
      validation.value = response.data;
    } else {
      validationError.value = response.message || 'Failed to load validation';
    }
  } catch (err) {
    validationError.value = err instanceof Error ? err.message : 'Failed to load validation';
  } finally {
    validationLoading.value = false;
  }
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

async function handleUpload() {
  if (selectedFiles.value.length === 0) return;
  
  uploading.value = true;
  uploadProgress.value = 0;
  
  try {
    const response = await catalogClient.uploadDatasetFiles(datasetId.value, selectedFiles.value);
    if (response.status === 'success') {
      alert('Files uploaded successfully');
      selectedFiles.value = [];
      uploadProgress.value = 0;
      await fetchDataset();
      await loadValidation();
    } else {
      alert(`Upload failed: ${response.message}`);
    }
  } catch (err) {
    alert(`Upload error: ${err}`);
  } finally {
    uploading.value = false;
    uploadProgress.value = 0;
  }
}

onMounted(async () => {
  await fetchDataset();
  if (dataset.value?.storage_uri) {
    await loadPreview();
    await loadValidation();
  }
});
</script>

<style scoped>
.dataset-detail {
  padding: 2rem;
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

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 2rem;
}

.detail-section {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.detail-list {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 1rem;
}

.detail-list dt {
  font-weight: 600;
  color: #666;
}

.detail-list dd {
  margin: 0;
}

.monospace {
  font-family: monospace;
  font-size: 0.9rem;
}

.text-muted {
  color: #6c757d;
}

.pii-badge,
.approval-badge,
.quality-score {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.pii-badge.pii-pending {
  background: #fff3cd;
  color: #856404;
}

.pii-badge.pii-clean {
  background: #d4edda;
  color: #155724;
}

.pii-badge.pii-failed {
  background: #f8d7da;
  color: #721c24;
}

.approval-badge.approved {
  background: #d4edda;
  color: #155724;
}

.approval-badge.pending {
  background: #fff3cd;
  color: #856404;
}

.quality-score.high {
  color: #28a745;
}

.quality-score.medium {
  color: #ffc107;
}

.quality-score.low {
  color: #dc3545;
}

.quality-score.na {
  color: #6c757d;
}

.preview-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1rem;
}

.schema-display {
  background: #f5f5f5;
  padding: 1rem;
  border-radius: 4px;
  overflow-x: auto;
  font-size: 0.9rem;
}

.preview-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}

.preview-table th,
.preview-table td {
  padding: 0.5rem;
  border: 1px solid #ddd;
  text-align: left;
}

.preview-table th {
  background: #f5f5f5;
  font-weight: 600;
}

.validation-section {
  margin-bottom: 1.5rem;
}

.pii-detected ul,
.quality-breakdown ul {
  margin: 0.5rem 0;
  padding-left: 1.5rem;
}

.file-upload-area {
  border: 2px dashed #ddd;
  border-radius: 8px;
  padding: 2rem;
  text-align: center;
  margin: 1rem 0;
  transition: all 0.3s;
}

.file-upload-area.dragover {
  border-color: #007bff;
  background: #f0f8ff;
}

.file-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.file-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem;
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

.btn-primary,
.btn-secondary {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover {
  background: #5a6268;
}

.loading,
.error {
  padding: 2rem;
  text-align: center;
}

.error {
  color: #dc3545;
}

.status-select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 0.9rem;
}

.status-select:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}
</style>

