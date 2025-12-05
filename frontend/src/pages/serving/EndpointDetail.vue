<template>
  <section class="endpoint-detail">
    <header>
      <h1>Serving Endpoint Detail</h1>
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
        <h2>Framework Information</h2>
        <dl class="detail-list" v-if="deployment">
          <dt>Serving Framework</dt>
          <dd>
            <span class="framework-badge">{{ deployment.serving_framework }}</span>
          </dd>
          
          <dt>Framework Resource ID</dt>
          <dd class="monospace">{{ deployment.framework_resource_id }}</dd>
          
          <dt>Framework Namespace</dt>
          <dd class="monospace">{{ deployment.framework_namespace }}</dd>
          
          <dt>Current Replicas</dt>
          <dd>{{ deployment.replica_count }}</dd>
          
          <dt>Autoscaling Metrics</dt>
          <dd v-if="deployment.autoscaling_metrics && Object.keys(deployment.autoscaling_metrics).length > 0">
            <ul style="margin: 0; padding-left: 20px;">
              <li v-if="deployment.autoscaling_metrics.targetLatencyMs">
                Target Latency: {{ deployment.autoscaling_metrics.targetLatencyMs }}ms
              </li>
              <li v-if="deployment.autoscaling_metrics.gpuUtilization">
                GPU Utilization: {{ deployment.autoscaling_metrics.gpuUtilization }}%
              </li>
            </ul>
          </dd>
          <dd v-else class="text-muted">Not configured</dd>
          
          <dt>Framework Status</dt>
          <dd>
            <pre v-if="deployment.framework_status" class="status-json">{{ JSON.stringify(deployment.framework_status, null, 2) }}</pre>
            <span v-else class="text-muted">Not available</span>
          </dd>
        </dl>
        <div v-else class="text-muted">
          No framework deployment information available. This endpoint may be using legacy deployment.
        </div>
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
          <template v-if="deployment">
            <dt>Current Replicas</dt>
            <dd>{{ deployment.replica_count }}</dd>
          </template>
        </dl>
      </div>

      <div class="detail-section">
        <h2>Runtime Configuration</h2>
        <dl class="detail-list">
          <dt>DeploymentSpec for Redeploy</dt>
          <dd>
            <div style="margin-bottom: 12px;">
              <label class="checkbox-label">
                <input 
                  type="checkbox" 
                  v-model="showDeploymentSpec"
                  class="checkbox-input"
                />
                <span>Use DeploymentSpec (서빙 생성 페이지와 동일한 방식)</span>
              </label>
              <p class="help-text" style="margin-top: 8px;">
                체크하면 서빙 생성 페이지와 동일한 DeploymentSpec을 사용하여 재배포합니다.
                기존 endpoint의 deploymentSpec이 있으면 자동으로 로드됩니다.
              </p>
            </div>
            
            <div v-if="showDeploymentSpec" style="margin-top: 16px; padding: 16px; background: #f8f9fa; border-radius: 4px;">
              <div class="form-row" style="margin-bottom: 12px;">
                <div class="form-field">
                  <label>Model Family <span class="required">*</span></label>
                  <input v-model="redeployDeploymentSpec.model_family" type="text" placeholder="e.g., llama, mistral" />
                </div>
                <div class="form-field">
                  <label>Job Type <span class="required">*</span></label>
                  <select v-model="redeployDeploymentSpec.job_type">
                    <option value="">Select job type</option>
                    <option value="SFT">SFT</option>
                    <option value="RAG_TUNING">RAG_TUNING</option>
                    <option value="RLHF">RLHF</option>
                    <option value="PRETRAIN">PRETRAIN</option>
                    <option value="EMBEDDING">EMBEDDING</option>
                  </select>
                </div>
              </div>
              
              <div class="form-field" style="margin-bottom: 12px;">
                <label>Serve Target <span class="required">*</span></label>
                <select v-model="redeployDeploymentSpec.serve_target">
                  <option value="">Select serve target</option>
                  <option value="GENERATION">GENERATION (for SFT/RLHF/PRETRAIN)</option>
                  <option value="RAG">RAG (for RAG_TUNING only)</option>
                </select>
              </div>
              
              <div style="margin-bottom: 12px;">
                <label class="checkbox-label">
                  <input 
                    type="checkbox" 
                    :checked="(redeployDeploymentSpec.resources?.gpus || 0) > 0"
                    @change="(e) => {
                      if (!redeployDeploymentSpec.resources) redeployDeploymentSpec.resources = { gpus: 0 };
                      redeployDeploymentSpec.resources.gpus = (e.target as HTMLInputElement).checked ? 1 : 0;
                      redeployDeploymentSpec.use_gpu = (e.target as HTMLInputElement).checked;
                    }"
                    class="checkbox-input"
                  />
                  <span>Use GPU Resources</span>
                </label>
              </div>
              
              <div v-if="(redeployDeploymentSpec.resources?.gpus || 0) > 0" class="form-row" style="margin-bottom: 12px;">
                <div class="form-field">
                  <label>GPU Count <span class="required">*</span></label>
                  <input v-model.number="redeployDeploymentSpec.resources.gpus" type="number" min="1" />
                </div>
                <div class="form-field">
                  <label>GPU Memory (GB)</label>
                  <input v-model.number="redeployDeploymentSpec.resources.gpu_memory_gb" type="number" min="0" />
                </div>
              </div>
              
              <div class="form-row" style="margin-bottom: 12px;">
                <div class="form-field">
                  <label>Max Concurrent Requests <span class="required">*</span></label>
                  <input v-model.number="redeployDeploymentSpec.runtime.max_concurrent_requests" type="number" min="1" />
                </div>
                <div class="form-field">
                  <label>Max Input Tokens <span class="required">*</span></label>
                  <input v-model.number="redeployDeploymentSpec.runtime.max_input_tokens" type="number" min="1" />
                </div>
                <div class="form-field">
                  <label>Max Output Tokens <span class="required">*</span></label>
                  <input v-model.number="redeployDeploymentSpec.runtime.max_output_tokens" type="number" min="1" />
                </div>
              </div>
            </div>
          </dd>
          
          <dt v-if="!showDeploymentSpec">GPU Override for Redeploy</dt>
          <dd v-if="!showDeploymentSpec">
            <select v-model="redeployGpuOverride">
              <option value="">Keep current / default</option>
              <option value="gpu">Force GPU (useGpu=true)</option>
              <option value="cpu">Force CPU-only (useGpu=false)</option>
            </select>
            <p class="help-text">
              Choose whether the next redeploy should force GPU or CPU-only resources.
              Leave as "Keep current / default" to use the existing/global setting.
            </p>
          </dd>

          <dt v-if="!showDeploymentSpec">Override Runtime Image</dt>
          <dd v-if="!showDeploymentSpec">
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
              <strong>Note:</strong> DeploymentSpec을 사용하면 이미지는 자동으로 선택됩니다.
            </p>
          </dd>

          <dt v-if="!showDeploymentSpec">CPU Request Override</dt>
          <dd>
            <input
              v-model="redeployCpuRequest"
              type="text"
              placeholder="e.g., 2 or 1000m"
              class="resource-input"
            />
            <p class="help-text">
              CPU request for the next redeploy (e.g., '2' for 2 cores, '1000m' for 1000 millicores). Leave empty to keep current/default.
            </p>
          </dd>

          <dt>CPU Limit Override</dt>
          <dd>
            <input
              v-model="redeployCpuLimit"
              type="text"
              placeholder="e.g., 4 or 2000m"
              class="resource-input"
            />
            <p class="help-text">
              CPU limit for the next redeploy (e.g., '4' for 4 cores, '2000m' for 2000 millicores). Leave empty to keep current/default.
            </p>
          </dd>

          <dt>Memory Request Override</dt>
          <dd>
            <input
              v-model="redeployMemoryRequest"
              type="text"
              placeholder="e.g., 4Gi or 2G"
              class="resource-input"
            />
            <p class="help-text">
              Memory request for the next redeploy (e.g., '4Gi' for 4 gibibytes, '2G' for 2 gigabytes). Leave empty to keep current/default.
            </p>
          </dd>

          <dt>Memory Limit Override</dt>
          <dd>
            <input
              v-model="redeployMemoryLimit"
              type="text"
              placeholder="e.g., 8Gi or 4G"
              class="resource-input"
            />
            <p class="help-text">
              Memory limit for the next redeploy (e.g., '8Gi' for 8 gibibytes, '4G' for 4 gigabytes). Leave empty to keep current/default.
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
import { ref, onMounted, reactive } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { servingClient, type ServingEndpoint, type ServingDeployment, type DeploymentSpec } from '@/services/servingClient';

const route = useRoute();
const router = useRouter();
const endpoint = ref<ServingEndpoint | null>(null);
const deployment = ref<ServingDeployment | null>(null);
const loading = ref(false);
const error = ref('');
const rollingBack = ref(false);
const deleting = ref(false);
const redeploying = ref(false);
const redeployGpuOverride = ref<string>('');
const runtimeImageSelection = ref<string>('');
const customRuntimeImage = ref<string>('');
const redeployCpuRequest = ref<string>('');
const redeployCpuLimit = ref<string>('');
const redeployMemoryRequest = ref<string>('');
const redeployMemoryLimit = ref<string>('');
const showDeploymentSpec = ref(false);
const redeployDeploymentSpec = reactive<Partial<DeploymentSpec>>({});

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
      
      // Load existing deploymentSpec if available
      if (endpoint.value.deploymentSpec) {
        // Deep copy deploymentSpec to avoid reactivity issues
        redeployDeploymentSpec.model_ref = endpoint.value.deploymentSpec.model_ref || '';
        redeployDeploymentSpec.model_family = endpoint.value.deploymentSpec.model_family || '';
        redeployDeploymentSpec.job_type = endpoint.value.deploymentSpec.job_type;
        redeployDeploymentSpec.serve_target = endpoint.value.deploymentSpec.serve_target || 'GENERATION';
        redeployDeploymentSpec.resources = {
          gpus: endpoint.value.deploymentSpec.resources?.gpus || 0,
          gpu_memory_gb: endpoint.value.deploymentSpec.resources?.gpu_memory_gb,
        };
        redeployDeploymentSpec.runtime = {
          max_concurrent_requests: endpoint.value.deploymentSpec.runtime?.max_concurrent_requests || 256,
          max_input_tokens: endpoint.value.deploymentSpec.runtime?.max_input_tokens || 4096,
          max_output_tokens: endpoint.value.deploymentSpec.runtime?.max_output_tokens || 1024,
        };
        redeployDeploymentSpec.use_gpu = endpoint.value.deploymentSpec.use_gpu ?? true;
        redeployDeploymentSpec.rollout = endpoint.value.deploymentSpec.rollout;
        showDeploymentSpec.value = true;
      } else {
        // Initialize empty deploymentSpec structure
        redeployDeploymentSpec.model_ref = '';
        redeployDeploymentSpec.model_family = '';
        redeployDeploymentSpec.job_type = undefined;
        redeployDeploymentSpec.serve_target = 'GENERATION';
        redeployDeploymentSpec.resources = { gpus: 0 };
        redeployDeploymentSpec.runtime = {
          max_concurrent_requests: 256,
          max_input_tokens: 4096,
          max_output_tokens: 1024,
        };
        redeployDeploymentSpec.use_gpu = false;
      }
      
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
    
    // Fetch deployment information
    try {
      const deploymentResponse = await servingClient.getDeployment(endpointId);
      if (deploymentResponse.status === "success" && deploymentResponse.data) {
        deployment.value = deploymentResponse.data;
      } else {
        deployment.value = null;
      }
    } catch (e) {
      // Deployment info is optional, don't fail if it's not available
      console.warn("Failed to load deployment info:", e);
      deployment.value = null;
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
    // Build DeploymentSpec if available (from existing endpoint or user edits)
    let deploymentSpec: DeploymentSpec | undefined = undefined;
    
    // Use existing deploymentSpec from endpoint if available, or use redeployDeploymentSpec if edited
    if (showDeploymentSpec.value && Object.keys(redeployDeploymentSpec).length > 0) {
      // Check if all required fields are present
      if (
        redeployDeploymentSpec.model_ref &&
        redeployDeploymentSpec.model_family &&
        redeployDeploymentSpec.job_type &&
        redeployDeploymentSpec.serve_target &&
        redeployDeploymentSpec.resources &&
        redeployDeploymentSpec.runtime
      ) {
        // Set use_gpu based on GPU count
        redeployDeploymentSpec.use_gpu = (redeployDeploymentSpec.resources.gpus || 0) > 0;
        deploymentSpec = redeployDeploymentSpec as DeploymentSpec;
      }
    } else if (endpoint.value.deploymentSpec) {
      // Use existing deploymentSpec from endpoint
      deploymentSpec = endpoint.value.deploymentSpec;
    }

    // Determine GPU override (tri-state: keep / force GPU / force CPU)
    // If deploymentSpec is provided, use its use_gpu value
    let useGpuOverride: boolean | undefined = undefined;
    if (deploymentSpec) {
      useGpuOverride = deploymentSpec.use_gpu;
    } else {
      if (redeployGpuOverride.value === 'gpu') {
        useGpuOverride = true;
      } else if (redeployGpuOverride.value === 'cpu') {
        useGpuOverride = false;
      }
    }

    // Determine runtime image override
    // If deploymentSpec is provided, runtime image is determined by serve_target and use_gpu
    let runtimeImageOverride: string | undefined;
    if (!deploymentSpec) {
      if (runtimeImageSelection.value === 'custom' && customRuntimeImage.value.trim()) {
        runtimeImageOverride = customRuntimeImage.value.trim();
      } else if (runtimeImageSelection.value && runtimeImageSelection.value !== 'custom') {
        runtimeImageOverride = runtimeImageSelection.value;
      }
    }

    // Prepare CPU/memory overrides (only include if set)
    const cpuRequestOverride = redeployCpuRequest.value.trim() || undefined;
    const cpuLimitOverride = redeployCpuLimit.value.trim() || undefined;
    const memoryRequestOverride = redeployMemoryRequest.value.trim() || undefined;
    const memoryLimitOverride = redeployMemoryLimit.value.trim() || undefined;

    const response = await servingClient.redeployEndpoint(
      endpoint.value.id,
      {
        useGpu: useGpuOverride,
        servingRuntimeImage: runtimeImageOverride,
        cpuRequest: cpuRequestOverride,
        cpuLimit: cpuLimitOverride,
        memoryRequest: memoryRequestOverride,
        memoryLimit: memoryLimitOverride,
        deploymentSpec: deploymentSpec,
      }
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

.runtime-image-input,
.resource-input {
  margin-top: 0.5rem;
  width: 100%;
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}

.form-field {
  margin-bottom: 12px;
}

.form-field label {
  display: block;
  margin-bottom: 4px;
  font-weight: 500;
  color: #333;
}

.form-field input[type="text"],
.form-field input[type="number"],
.form-field select {
  width: 100%;
  padding: 8px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.checkbox-label {
  display: flex;
  align-items: center;
  cursor: pointer;
  user-select: none;
}

.checkbox-label span {
  margin-left: 8px;
  font-weight: 500;
  color: #333;
}

.checkbox-input {
  width: 18px;
  height: 18px;
  margin: 0;
  cursor: pointer;
  accent-color: #007bff;
}

.required {
  color: #dc3545;
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

.framework-badge {
  padding: 0.25rem 0.5rem;
  background: #007bff;
  color: white;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: uppercase;
  display: inline-block;
}

.status-json {
  background: #f8f9fa;
  padding: 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  max-height: 200px;
  overflow: auto;
  margin: 0;
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

