<template>
  <section class="endpoint-detail">
    <header>
      <h1>Serving Endpoint Details</h1>
      <router-link to="/serving/endpoints" class="btn-back">← Back to List</router-link>
    </header>

    <div v-if="loading" class="loading">Loading endpoint details...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="endpoint" class="detail-content">
      <div class="detail-section">
        <h2>Basic Information</h2>
        <dl class="detail-list">
          <dt>Endpoint ID</dt>
          <dd class="monospace">{{ endpoint.id }}</dd>
          
          <dt>Route</dt>
          <dd class="monospace">{{ endpoint.route }}</dd>
          
          <dt>Environment</dt>
          <dd>
            <span :class="`env-badge env-${endpoint.environment}`">
              {{ endpoint.environment.toUpperCase() }}
            </span>
          </dd>
          
          <dt>Status</dt>
          <dd>
            <span :class="`status-badge status-${endpoint.status}`">
              {{ endpoint.status }}
            </span>
          </dd>
          
          <dt>Created At</dt>
          <dd>{{ formatDate(endpoint.createdAt) }}</dd>
        </dl>
      </div>

      <div class="detail-section">
        <h2>Model Information</h2>
        <dl class="detail-list">
          <dt>Model ID</dt>
          <dd class="monospace">{{ endpoint.modelId }}</dd>
          <dd class="model-link">
            <router-link :to="`/catalog/models/${endpoint.modelId}`">
              View Model Details →
            </router-link>
          </dd>
          <dt>Runtime Image</dt>
          <dd class="monospace">
            <span v-if="endpoint.runtimeImage">
              {{ endpoint.runtimeImage }}
            </span>
            <span v-else class="text-muted">
              Default (server setting)
            </span>
          </dd>
        </dl>
      </div>

      <div class="detail-section">
        <h2>Scaling Configuration</h2>
        <dl class="detail-list">
          <dt>Min Replicas</dt>
          <dd>{{ endpoint.minReplicas }}</dd>
          
          <dt>Max Replicas</dt>
          <dd>{{ endpoint.maxReplicas }}</dd>
          
          <dt>Replica Range</dt>
          <dd>{{ endpoint.minReplicas }} - {{ endpoint.maxReplicas }}</dd>
        </dl>
      </div>

      <div class="detail-section">
        <h2>Runtime Configuration</h2>
        <dl class="detail-list">
          <dt>GPU Override for Redeploy</dt>
          <dd>
            <select v-model="redeployGpuOverride">
              <option value="">Keep current / default</option>
              <option value="gpu">Force GPU (useGpu=true)</option>
              <option value="cpu">Force CPU-only (useGpu=false)</option>
            </select>
            <p class="help-text">
              Choose whether the next redeploy should force GPU or CPU-only resources.
              Leave as “Keep current / default” to use the existing/global setting.
            </p>
          </dd>

          <dt>Override Runtime Image</dt>
          <dd>
            <select v-model="runtimeImageSelection">
              <option value="">Use current / default</option>
              <option value="vllm/vllm-openai:nightly">vLLM OpenAI (nightly)</option>
              <option value="ghcr.io/vllm/vllm:latest">vLLM (latest)</option>
              <option value="ghcr.io/vllm/vllm:0.6.0">vLLM (0.6.0)</option>
              <option value="ghcr.io/huggingface/text-generation-inference:latest">TGI (latest, GHCR)</option>
              <option value="custom">Custom image...</option>
            </select>
            <input
              v-if="runtimeImageSelection === 'custom'"
              v-model="customRuntimeImage"
              type="text"
              placeholder="e.g., my-registry.io/my-image:tag"
              class="runtime-image-input"
            />
            <p class="help-text">
              If set, this image will be used on the next redeploy and recorded on the endpoint. Leave empty to keep current/default image.
            </p>
          </dd>
        </dl>
      </div>

      <div class="detail-section">
        <h2>Actions</h2>
        <div class="actions">
          <router-link
            v-if="endpoint.status === 'healthy'"
            :to="`/serving/chat/${endpoint.id}`"
            class="btn-primary"
          >
            Test Chat
          </router-link>
          <button 
            @click="handleRedeploy" 
            :disabled="redeploying || deleting || rollingBack" 
            class="btn-redeploy"
          >
            {{ redeploying ? 'Redeploying...' : 'Redeploy Endpoint' }}
          </button>
          <button @click="handleRollback" :disabled="rollingBack || deleting || redeploying" class="btn-danger">
            {{ rollingBack ? 'Rolling back...' : 'Rollback Endpoint' }}
          </button>
          <button @click="handleDelete" :disabled="deleting || rollingBack || redeploying" class="btn-delete">
            {{ deleting ? 'Deleting...' : 'Delete Endpoint' }}
          </button>
          <button @click="refreshEndpoint" :disabled="loading" class="btn-secondary">
            Refresh
          </button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { servingClient, type ServingEndpoint } from '@/services/servingClient';

const route = useRoute();
const router = useRouter();
const endpoint = ref<ServingEndpoint | null>(null);
const loading = ref(false);
const error = ref('');
const rollingBack = ref(false);
const deleting = ref(false);
const redeploying = ref(false);
const redeployGpuOverride = ref<string>('');
const runtimeImageSelection = ref<string>('');
const customRuntimeImage = ref<string>('');

async function fetchEndpoint() {
  const endpointId = route.params.id as string;
  if (!endpointId) {
    error.value = 'Endpoint ID is required';
    return;
  }

  loading.value = true;
  error.value = '';
  try {
    const response = await servingClient.getEndpoint(endpointId);
    if (response.status === "success" && response.data) {
      endpoint.value = response.data;
      // Initialize runtime image selector based on current endpoint
      if (endpoint.value.runtimeImage) {
        const knownImages = [
          "vllm/vllm-openai:nightly",
          "ghcr.io/vllm/vllm:latest",
          "ghcr.io/vllm/vllm:0.6.0",
          "ghcr.io/huggingface/text-generation-inference:latest",
        ];
        if (knownImages.includes(endpoint.value.runtimeImage)) {
          runtimeImageSelection.value = endpoint.value.runtimeImage;
          customRuntimeImage.value = "";
        } else {
          runtimeImageSelection.value = "custom";
          customRuntimeImage.value = endpoint.value.runtimeImage;
        }
      } else {
        runtimeImageSelection.value = "";
        customRuntimeImage.value = "";
      }
    } else {
      error.value = response.message || "Failed to load endpoint";
      endpoint.value = null;
    }
  } catch (e) {
    error.value = `Error: ${e}`;
    endpoint.value = null;
  } finally {
    loading.value = false;
  }
}

async function handleRedeploy() {
  if (!endpoint.value) return;
  
  if (!confirm(`Are you sure you want to redeploy endpoint "${endpoint.value.route}"? This will restart the deployment with the same configuration.`)) {
    return;
  }

  redeploying.value = true;
  try {
    // Determine GPU override (tri-state: keep / force GPU / force CPU)
    let useGpuOverride: boolean | undefined = undefined;
    if (redeployGpuOverride.value === 'gpu') {
      useGpuOverride = true;
    } else if (redeployGpuOverride.value === 'cpu') {
      useGpuOverride = false;
    }

    // Determine runtime image override
    let runtimeImageOverride: string | undefined;
    if (runtimeImageSelection.value === 'custom' && customRuntimeImage.value.trim()) {
      runtimeImageOverride = customRuntimeImage.value.trim();
    } else if (runtimeImageSelection.value && runtimeImageSelection.value !== 'custom') {
      runtimeImageOverride = runtimeImageSelection.value;
    }

    const response = await servingClient.redeployEndpoint(
      endpoint.value.id,
      useGpuOverride,
      runtimeImageOverride
    );
    if (response.status === "success") {
      alert('Endpoint redeployment started successfully. Status will update shortly.');
      await fetchEndpoint();
    } else {
      alert(`Redeploy failed: ${response.message}`);
    }
  } catch (e) {
    alert(`Error: ${e}`);
  } finally {
    redeploying.value = false;
  }
}

async function handleRollback() {
  if (!endpoint.value) return;
  
  if (!confirm('Are you sure you want to rollback this endpoint?')) {
    return;
  }

  rollingBack.value = true;
  try {
    const response = await servingClient.rollbackEndpoint(endpoint.value.id);
    if (response.status === "success") {
      alert('Endpoint rolled back successfully');
      await fetchEndpoint();
    } else {
      alert(`Rollback failed: ${response.message}`);
    }
  } catch (e) {
    alert(`Error: ${e}`);
  } finally {
    rollingBack.value = false;
  }
}

async function handleDelete() {
  if (!endpoint.value) return;
  
  if (!confirm(`Are you sure you want to delete endpoint "${endpoint.value.route}"? This will permanently delete the endpoint and all its Kubernetes resources.`)) {
    return;
  }

  deleting.value = true;
  try {
    const response = await servingClient.deleteEndpoint(endpoint.value.id);
    if (response.status === "success") {
      alert('Endpoint deleted successfully');
      router.push('/serving/endpoints');
    } else {
      alert(`Delete failed: ${response.message}`);
    }
  } catch (e) {
    alert(`Error: ${e}`);
  } finally {
    deleting.value = false;
  }
}

function refreshEndpoint() {
  fetchEndpoint();
}

function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleString();
  } catch {
    return dateString;
  }
}

onMounted(fetchEndpoint);
</script>

<style scoped>
.endpoint-detail {
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

.model-link {
  margin-top: 0.5rem;
}

.model-link a {
  color: #007bff;
  text-decoration: none;
}

.model-link a:hover {
  text-decoration: underline;
}

.env-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  display: inline-block;
}

.env-dev {
  background: #d1ecf1;
  color: #0c5460;
}

.env-stg {
  background: #fff3cd;
  color: #856404;
}

.env-prod {
  background: #d4edda;
  color: #155724;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: capitalize;
  display: inline-block;
}

.status-deploying {
  background: #d1ecf1;
  color: #0c5460;
}

.status-healthy {
  background: #d4edda;
  color: #155724;
}

.status-degraded {
  background: #fff3cd;
  color: #856404;
}

.status-failed {
  background: #f8d7da;
  color: #721c24;
}

.actions {
  display: flex;
  gap: 1rem;
  align-items: center;
}

.btn-primary {
  padding: 0.5rem 1rem;
  background: #28a745;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 0.9rem;
  display: inline-block;
}

.btn-primary:hover {
  background: #218838;
}

.btn-danger {
  padding: 0.5rem 1rem;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-danger:hover:not(:disabled) {
  background: #c82333;
}

.btn-danger:disabled {
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
}

.btn-delete:hover:not(:disabled) {
  background: #c82333;
}

.btn-delete:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 0.5rem 1rem;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-secondary:hover:not(:disabled) {
  background: #5a6268;
}

.btn-secondary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-redeploy {
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-redeploy:hover:not(:disabled) {
  background: #0056b3;
}

.btn-redeploy:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.runtime-image-input {
  margin-top: 0.5rem;
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.help-text {
  margin-top: 0.5rem;
  font-size: 0.85rem;
  color: #6c757d;
}

.text-muted {
  color: #6c757d;
  font-style: italic;
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

