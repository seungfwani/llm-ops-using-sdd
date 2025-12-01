<template>
  <section class="model-create">
    <header>
      <h1>Create New Model</h1>
      <router-link to="/catalog/models" class="btn-back">← Back to List</router-link>
    </header>

    <form @submit.prevent="handleSubmit" class="create-form">
      <div class="form-section">
        <h2>Basic Information</h2>
        <label>
          Name *
          <input v-model="form.name" required placeholder="e.g., gpt-4, llama-2" />
        </label>
        <label>
          Version *
          <input v-model="form.version" required placeholder="e.g., 1.0.0, v2" />
        </label>
        <label>
          Type *
          <select v-model="form.type" required>
            <option value="base">Base</option>
            <option value="fine-tuned">Fine-tuned</option>
            <option value="external">External</option>
          </select>
        </label>
        <label>
          Owner Team *
          <input v-model="form.owner_team" required placeholder="e.g., ml-team, nlp-team" />
        </label>
      </div>

      <div class="form-section">
        <h2>Metadata</h2>
        <div v-if="form.type === 'external'" class="external-provider-section">
          <label>
            Provider *
            <select v-model="externalProvider" required>
              <option value="">Select provider...</option>
              <option value="openai">OpenAI (GPT-3.5, GPT-4)</option>
              <option value="ollama">Ollama (Local/Remote)</option>
            </select>
          </label>
          
          <div v-if="externalProvider === 'openai'" class="provider-config">
            <label>
              Model Name *
              <input 
                v-model="externalConfig.model_name" 
                required 
                placeholder="e.g., gpt-4, gpt-3.5-turbo"
              />
            </label>
            <label>
              API Key *
              <input 
                v-model="externalConfig.api_key" 
                type="password"
                required 
                placeholder="sk-..."
              />
            </label>
            <label>
              Base URL (Optional)
              <input 
                v-model="externalConfig.base_url" 
                placeholder="https://api.openai.com/v1 (default)"
              />
            </label>
          </div>
          
          <div v-if="externalProvider === 'ollama'" class="provider-config">
            <label>
              Model Name *
              <input 
                v-model="externalConfig.model_name" 
                required 
                placeholder="e.g., llama2, mistral"
              />
            </label>
            <label>
              Endpoint *
              <input 
                v-model="externalConfig.endpoint" 
                required 
                placeholder="http://localhost:11434"
              />
            </label>
          </div>
        </div>
        
        <label>
          Metadata (JSON) <span v-if="form.type !== 'external'">*</span>
          <textarea 
            v-model="metadataText" 
            :required="form.type !== 'external'"
            :placeholder="metadataPlaceholder"
            rows="8"
          />
        </label>
        <small class="help-text">
          <span v-if="form.type === 'external'">
            Provider configuration will be automatically added to metadata. You can add additional fields here.
          </span>
          <span v-else>
            Enter valid JSON format. Common fields: description, framework, parameters, license, etc.
          </span>
        </small>
      </div>

      <div class="form-section">
        <h2>Lineage (Optional)</h2>
        <label>
          Dataset IDs (comma-separated)
          <input 
            v-model="lineageText" 
            placeholder="dataset-id-1, dataset-id-2"
          />
        </label>
        <small class="help-text">Enter dataset IDs used to train/fine-tune this model, separated by commas</small>
      </div>

      <div v-if="form.type !== 'external'" class="form-section">
        <h2>Model Files (Optional)</h2>
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
          <small class="help-text">Upload model files (weights, config, tokenizer, etc.). Files will be uploaded after model creation.</small>
        </div>
      </div>
      
      <div v-else class="form-section">
        <div class="info-box">
          <strong>External Model</strong>
          <p>External models (OpenAI, Ollama, etc.) don't require file uploads. The model will be accessed via API.</p>
        </div>
      </div>

      <div class="form-actions">
        <button type="button" @click="$router.push('/catalog/models')" class="btn-secondary">
          Cancel
        </button>
        <button :disabled="loading" type="submit" class="btn-primary">
          {{ loading ? 'Creating...' : 'Create Model' }}
        </button>
      </div>

      <div v-if="message" :class="['message', messageType]">
        {{ message }}
      </div>
    </form>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref, watch, computed } from 'vue';
import { useRouter } from 'vue-router';
import { catalogClient } from '@/services/catalogClient';

const router = useRouter();
const loading = ref(false);
const message = ref('');
const messageType = ref<'success' | 'error'>('error');
const dragover = ref(false);
const selectedFiles = ref<File[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const uploading = ref(false);
const uploadProgress = ref(0);
const createdModelId = ref<string | null>(null);

const form = reactive({
  name: '',
  version: '',
  type: 'base',
  owner_team: '',
});

const metadataText = ref('{}');
const lineageText = ref('');
const externalProvider = ref('');
const externalConfig = reactive({
  model_name: '',
  api_key: '',
  base_url: '',
  endpoint: '',
});

// Computed placeholder for metadata textarea
const metadataPlaceholder = computed(() => {
  if (form.type === 'external') {
    return 'Additional metadata (optional)';
  }
  return '{"description": "...", "framework": "...", "parameters": "..."}';
});

// Reset external config when type changes
watch(() => form.type, (newType) => {
  if (newType !== 'external') {
    externalProvider.value = '';
    externalConfig.model_name = '';
    externalConfig.api_key = '';
    externalConfig.base_url = '';
    externalConfig.endpoint = '';
  } else {
    // Ensure metadata is valid JSON for external models
    if (!metadataText.value || metadataText.value.trim() === '') {
      metadataText.value = '{}';
    }
  }
});

async function handleSubmit() {
  loading.value = true;
  message.value = '';
  
  try {
    // Validate external provider config if external type
    if (form.type === 'external') {
      if (!externalProvider.value) {
        message.value = 'Please select a provider for external model';
        messageType.value = 'error';
        loading.value = false;
        return;
      }
      
      if (externalProvider.value === 'openai') {
        if (!externalConfig.model_name || !externalConfig.api_key) {
          message.value = 'Model name and API key are required for OpenAI';
          messageType.value = 'error';
          loading.value = false;
          return;
        }
      } else if (externalProvider.value === 'ollama') {
        if (!externalConfig.model_name || !externalConfig.endpoint) {
          message.value = 'Model name and endpoint are required for Ollama';
          messageType.value = 'error';
          loading.value = false;
          return;
        }
      }
    }
    
    // Parse metadata JSON
    let metadata: Record<string, unknown>;
    try {
      metadata = JSON.parse(metadataText.value || '{}');
    } catch (e) {
      message.value = 'Invalid JSON format in metadata field';
      messageType.value = 'error';
      loading.value = false;
      return;
    }
    
    // Add external provider config to metadata
    if (form.type === 'external') {
      metadata.provider = externalProvider.value;
      if (externalProvider.value === 'openai') {
        metadata.model_name = externalConfig.model_name;
        metadata.api_key = externalConfig.api_key;
        if (externalConfig.base_url) {
          metadata.base_url = externalConfig.base_url;
        }
      } else if (externalProvider.value === 'ollama') {
        metadata.model_name = externalConfig.model_name;
        metadata.endpoint = externalConfig.endpoint;
      }
    }

    // Parse lineage dataset IDs
    const lineage_dataset_ids = lineageText.value
      .split(',')
      .map(id => id.trim())
      .filter(id => id.length > 0);

    const response = await catalogClient.createModel({
      ...form,
      metadata,
      lineage_dataset_ids: lineage_dataset_ids.length > 0 ? lineage_dataset_ids : undefined,
    });

    if (response.status === "success") {
      const modelId = response.data ? (Array.isArray(response.data) ? response.data[0].id : response.data.id) : null;
      createdModelId.value = modelId;
      
      message.value = 'Model created successfully!';
      messageType.value = 'success';
      
      // Upload files if any selected (skip for external models)
      if (modelId && selectedFiles.value.length > 0 && form.type !== 'external') {
        await handleFileUpload(modelId);
          } else {
        // Redirect to model detail page after a short delay if no files to upload
      setTimeout(() => {
          if (modelId) {
          router.push(`/catalog/models/${modelId}`);
        } else {
          router.push('/catalog/models');
        }
      }, 1500);
      }
    } else {
      message.value = response.message || 'Failed to create model';
      messageType.value = 'error';
    }
  } catch (error) {
    message.value = `Error: ${error}`;
    messageType.value = 'error';
  } finally {
    loading.value = false;
  }
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

function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 Bytes';
  const k = 1024;
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

async function handleFileUpload(modelId: string) {
  if (selectedFiles.value.length === 0) return;
  
  uploading.value = true;
  uploadProgress.value = 0;
  
  try {
    // Simulate progress (in real implementation, use axios onUploadProgress)
    const progressInterval = setInterval(() => {
      if (uploadProgress.value < 90) {
        uploadProgress.value += 10;
      }
    }, 200);
    
    const uploadResponse = await catalogClient.uploadModelFiles(modelId, selectedFiles.value);
    
    clearInterval(progressInterval);
    uploadProgress.value = 100;
    
    if (uploadResponse.status === "success") {
      message.value = 'Model created and files uploaded successfully!';
      messageType.value = 'success';
      selectedFiles.value = []; // Clear files after successful upload
      
      // Redirect to model detail page after a short delay
      setTimeout(() => {
        router.push(`/catalog/models/${modelId}`);
      }, 1500);
    } else {
      message.value = `Model created but file upload failed: ${uploadResponse.message}`;
      messageType.value = 'error';
      // Still redirect to detail page so user can retry upload
      setTimeout(() => {
        router.push(`/catalog/models/${modelId}`);
      }, 2000);
    }
  } catch (uploadError) {
    message.value = `Model created but file upload failed: ${uploadError}`;
    messageType.value = 'error';
    uploadProgress.value = 0;
    // Still redirect to detail page so user can retry upload
    setTimeout(() => {
      if (modelId) {
        router.push(`/catalog/models/${modelId}`);
      } else {
        router.push('/catalog/models');
      }
    }, 2000);
  } finally {
    uploading.value = false;
    setTimeout(() => {
      uploadProgress.value = 0;
    }, 1000);
  }
}
</script>

<style scoped>
.model-create {
  padding: 2rem;
  max-width: 800px;
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

.create-form {
  background: white;
  padding: 2rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.form-section {
  margin-bottom: 2rem;
}

.form-section h2 {
  margin-top: 0;
  margin-bottom: 1rem;
  color: #333;
  font-size: 1.1rem;
  border-bottom: 2px solid #e9ecef;
  padding-bottom: 0.5rem;
}

.create-form label {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  margin-bottom: 1rem;
  font-weight: 500;
  color: #333;
}

.create-form input,
.create-form select,
.create-form textarea {
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  font-family: inherit;
}

.create-form input:focus,
.create-form select:focus,
.create-form textarea:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}

.create-form textarea {
  font-family: monospace;
  resize: vertical;
}

.help-text {
  display: block;
  margin-top: -0.75rem;
  margin-bottom: 1rem;
  font-size: 0.85rem;
  color: #6c757d;
}

.form-actions {
  display: flex;
  gap: 1rem;
  justify-content: flex-end;
  margin-top: 2rem;
  padding-top: 2rem;
  border-top: 1px solid #e9ecef;
}

.btn-primary {
  padding: 0.75rem 1.5rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 500;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 0.75rem 1.5rem;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}

.btn-secondary:hover {
  background: #5a6268;
}

.message {
  margin-top: 1rem;
  padding: 1rem;
  border-radius: 4px;
  font-weight: 500;
}

.message.success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.message.error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
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

.external-provider-section {
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 4px;
}

.provider-config {
  margin-top: 1rem;
  padding: 1rem;
  background: white;
  border-radius: 4px;
  border: 1px solid #dee2e6;
}

.provider-config label {
  margin-bottom: 1rem;
}

.info-box {
  padding: 1rem;
  background: #e7f3ff;
  border: 1px solid #b3d9ff;
  border-radius: 4px;
  color: #004085;
}

.info-box strong {
  display: block;
  margin-bottom: 0.5rem;
}

.info-box p {
  margin: 0;
  font-size: 0.9rem;
}
</style>

