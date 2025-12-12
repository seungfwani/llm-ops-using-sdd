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
          <dt>Use GPU</dt>
          <dd>
            <span v-if="endpoint.useGpu !== undefined">
              {{ endpoint.useGpu ? 'Yes' : 'No (CPU-only)' }}
            </span>
            <span v-else class="text-muted">Not specified</span>
          </dd>
        </dl>
      </div>

      <div class="detail-section">
        <h2>DeploymentSpec Configuration</h2>
        <dl class="detail-list" v-if="endpoint.deploymentSpec">
          <dt>Model Reference</dt>
          <dd class="monospace">{{ endpoint.deploymentSpec.model_ref || 'N/A' }}</dd>
          
          <dt>Model Family</dt>
          <dd>{{ endpoint.deploymentSpec.model_family || 'N/A' }}</dd>
          
          <dt>Job Type</dt>
          <dd>{{ endpoint.deploymentSpec.job_type || 'N/A' }}</dd>
          
          <dt>Serve Target</dt>
          <dd>
            <span class="badge">{{ endpoint.deploymentSpec.serve_target || 'N/A' }}</span>
          </dd>
          
          <dt>GPU Configuration</dt>
          <dd>
            <span v-if="endpoint.deploymentSpec.use_gpu">
              <strong>GPU Enabled</strong>
              <ul style="margin: 8px 0 0 20px; padding: 0;">
                <li v-if="endpoint.deploymentSpec.resources?.gpus">
                  GPU Count: {{ endpoint.deploymentSpec.resources.gpus }}
                </li>
                <li v-if="endpoint.deploymentSpec.resources?.gpu_memory_gb">
                  GPU Memory: {{ endpoint.deploymentSpec.resources.gpu_memory_gb }} GB
                </li>
              </ul>
            </span>
            <span v-else class="text-muted">CPU-only mode</span>
          </dd>
          
          <dt>Runtime Constraints</dt>
          <dd v-if="endpoint.deploymentSpec.runtime">
            <ul style="margin: 0; padding-left: 20px;">
              <li v-if="endpoint.deploymentSpec.runtime.max_concurrent_requests">
                Max Concurrent Requests: {{ endpoint.deploymentSpec.runtime.max_concurrent_requests }}
              </li>
              <li v-if="endpoint.deploymentSpec.runtime.max_input_tokens">
                Max Input Tokens: {{ endpoint.deploymentSpec.runtime.max_input_tokens }}
              </li>
              <li v-if="endpoint.deploymentSpec.runtime.max_output_tokens">
                Max Output Tokens: {{ endpoint.deploymentSpec.runtime.max_output_tokens }}
              </li>
            </ul>
          </dd>
          <dd v-else class="text-muted">Not configured</dd>
          
          <dt>Rollout Strategy</dt>
          <dd v-if="endpoint.deploymentSpec.rollout?.strategy">
            {{ endpoint.deploymentSpec.rollout.strategy }}
            <span v-if="endpoint.deploymentSpec.rollout.traffic_split">
              (Old: {{ endpoint.deploymentSpec.rollout.traffic_split.old }}%, 
              New: {{ endpoint.deploymentSpec.rollout.traffic_split.new }}%)
            </span>
          </dd>
          <dd v-else class="text-muted">Not configured</dd>
        </dl>
        <div v-else class="text-muted" style="padding: 1rem;">
          <p>No DeploymentSpec configured. This endpoint was deployed using legacy configuration.</p>
          <p style="margin-top: 0.5rem; font-size: 0.9rem;">
            To use DeploymentSpec, redeploy this endpoint with DeploymentSpec enabled.
          </p>
        </div>
      </div>

      <div class="detail-section">
        <h2>Resource Configuration</h2>
        <dl class="detail-list">
          <dt>CPU Request</dt>
          <dd>{{ endpoint.cpuRequest || 'Default (server setting)' }}</dd>
          
          <dt>CPU Limit</dt>
          <dd>{{ endpoint.cpuLimit || 'Default (server setting)' }}</dd>
          
          <dt>Memory Request</dt>
          <dd>{{ endpoint.memoryRequest || 'Default (server setting)' }}</dd>
          
          <dt>Memory Limit</dt>
          <dd>{{ endpoint.memoryLimit || 'Default (server setting)' }}</dd>
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

      <!-- Redeploy Configuration (EndpointDeploy.vue와 동일한 구조) -->
      <section class="form-section">
        <h2 class="section-title">Redeploy Configuration</h2>
        <p class="section-description">
          Training job의 메타데이터가 자동으로 로드됩니다. DeploymentSpec에 따라 서빙 프레임워크로 재배포됩니다.
        </p>

        <div class="form-row">
          <div class="form-field">
            <label>Model Family <span class="required">*</span></label>
            <input v-model="redeployDeploymentSpec.model_family" type="text" placeholder="e.g., llama, mistral, gemma" required />
            <small>Training job의 model_family와 일치해야 합니다</small>
          </div>
          <div class="form-field">
            <label>Job Type <span class="required">*</span></label>
            <select v-model="redeployDeploymentSpec.job_type" @change="onRedeployJobTypeChange" required>
              <option value="">Select job type</option>
              <option value="SFT">SFT</option>
              <option value="RAG_TUNING">RAG_TUNING</option>
              <option value="RLHF">RLHF</option>
              <option value="PRETRAIN">PRETRAIN</option>
              <option value="EMBEDDING">EMBEDDING</option>
            </select>
            <small>Training job에서 상속됩니다</small>
          </div>
        </div>

        <div class="form-field">
          <label>Serve Target <span class="required">*</span></label>
          <select v-model="redeployDeploymentSpec.serve_target" @change="onRedeployServeTargetChange" required>
            <option value="">Select serve target</option>
            <option value="GENERATION">GENERATION (for SFT/RLHF/PRETRAIN)</option>
            <option value="RAG">RAG (for RAG_TUNING only)</option>
          </select>
          <small>RAG_TUNING → RAG, SFT/RLHF → GENERATION (자동 검증)</small>
        </div>

        <div class="subsection">
          <h3 class="subsection-title">Resource Configuration</h3>
          <div class="form-field" style="margin-bottom: 16px;">
            <label class="checkbox-label">
              <input 
                type="checkbox" 
                :checked="redeployUseGpuEnabled"
                @change="onRedeployUseGpuChange"
                class="checkbox-input"
              />
              <span>Use GPU Resources</span>
            </label>
            <small>체크 해제 시 CPU-only 리소스로 배포됩니다 (GPU 노드가 없거나 비용 절감이 필요한 경우 유용합니다)</small>
          </div>
          <div class="form-row" v-if="redeployUseGpuEnabled">
            <div class="form-field">
              <label>GPU Count <span class="required">*</span></label>
              <input v-model.number="redeployDeploymentSpec.resources.gpus" type="number" min="1" required />
              <small>Number of GPUs to allocate</small>
            </div>
            <div class="form-field">
              <label>GPU Memory (GB)</label>
              <input v-model.number="redeployDeploymentSpec.resources.gpu_memory_gb" type="number" min="0" />
              <small>GPU memory requirement (optional)</small>
            </div>
          </div>
          <div v-else class="cpu-only-notice">
            <div style="padding: 12px; background: #e7f3ff; border-left: 4px solid #2196F3; border-radius: 4px;">
              <small style="color: #1976D2; font-weight: 500;">CPU-only 모드</small>
              <p style="margin: 4px 0 0 0; color: #666; font-size: 0.875rem;">GPU 없이 CPU 리소스만 사용하여 배포됩니다. GPU 노드가 없거나 비용 절감이 필요한 경우에 유용합니다.</p>
            </div>
          </div>
        </div>

        <div class="subsection">
          <h3 class="subsection-title">Runtime Constraints</h3>
          <div class="form-row">
            <div class="form-field">
              <label>Max Concurrent Requests <span class="required">*</span></label>
              <input v-model.number="redeployDeploymentSpec.runtime.max_concurrent_requests" type="number" min="1" required />
            </div>
            <div class="form-field">
              <label>Max Input Tokens <span class="required">*</span></label>
              <input v-model.number="redeployDeploymentSpec.runtime.max_input_tokens" type="number" min="1" required />
            </div>
            <div class="form-field">
              <label>Max Output Tokens <span class="required">*</span></label>
              <input v-model.number="redeployDeploymentSpec.runtime.max_output_tokens" type="number" min="1" required />
            </div>
          </div>
          <small class="form-note">max_input_tokens must be ≤ model's max_position_embeddings (자동 검증)</small>
        </div>

        <div class="subsection" v-if="hasRedeployDeploymentSpec">
          <h3 class="subsection-title">Container Image</h3>
          <div class="image-info" style="padding: 12px; background: #f5f5f5; border-radius: 4px;">
            <small style="color: #666;">
              이미지는 <strong>serve_target</strong> ({{ redeployDeploymentSpec.serve_target }})과 
              <strong>use_gpu</strong> ({{ redeployDeploymentSpec.use_gpu ? 'GPU' : 'CPU' }}) 설정에 따라 자동으로 선택됩니다.
            </small>
          </div>
        </div>

        <div class="subsection">
          <h3 class="subsection-title">Rollout Strategy (Optional)</h3>
          <div class="form-field">
            <label>Strategy</label>
            <select v-model="redeployRolloutStrategy" @change="onRedeployRolloutStrategyChange">
              <option value="">None (default)</option>
              <option value="blue-green">Blue-Green</option>
              <option value="canary">Canary</option>
            </select>
          </div>
          <div v-if="redeployDeploymentSpec.rollout?.strategy === 'canary' && redeployDeploymentSpec.rollout.traffic_split" class="form-row" style="margin-top: 10px;">
            <div class="form-field">
              <label>Old Version (%)</label>
              <input v-model.number="redeployDeploymentSpec.rollout.traffic_split.old" type="number" min="0" max="100" />
            </div>
            <div class="form-field">
              <label>New Version (%)</label>
              <input v-model.number="redeployDeploymentSpec.rollout.traffic_split.new" type="number" min="0" max="100" />
            </div>
          </div>
          <small class="form-note" v-if="redeployDeploymentSpec.rollout?.strategy === 'canary'">Old + New must equal 100 (자동 검증)</small>
        </div>
      </section>

      <!-- 고급 옵션 (접을 수 있음) -->
      <section class="form-section">
        <div class="section-header">
          <h2 class="section-title">고급 옵션</h2>
          <button type="button" class="toggle-button" @click="showRedeployAdvanced = !showRedeployAdvanced">
            {{ showRedeployAdvanced ? '숨기기' : '보기' }}
          </button>
        </div>
        <div v-show="showRedeployAdvanced">
          <div class="subsection">
            <h3 class="subsection-title">Autoscaling Configuration</h3>
            <div class="form-row">
              <div class="form-field">
                <label>Target Latency (ms)</label>
                <input v-model.number="redeployAutoscalePolicy.targetLatencyMs" type="number" min="0" placeholder="Optional" />
                <small>Target latency in milliseconds</small>
              </div>
              <div class="form-field">
                <label>GPU Utilization (%)</label>
                <input v-model.number="redeployAutoscalePolicy.gpuUtilization" type="number" min="0" max="100" placeholder="Optional" />
                <small>Target GPU utilization (0-100)</small>
              </div>
              <div class="form-field">
                <label>CPU Utilization (%)</label>
                <input v-model.number="redeployAutoscalePolicy.cpuUtilization" type="number" min="0" max="100" placeholder="Optional" />
                <small>Target CPU utilization (0-100)</small>
              </div>
            </div>
            <small class="form-note">비워두면 기본 autoscaling 정책이 사용됩니다</small>
          </div>

          <div class="subsection">
            <h3 class="subsection-title">Serving Framework</h3>
            <div class="form-field">
              <label>Serving Framework</label>
              <select v-model="redeployServingFramework">
                <option value="">Use default (from server settings)</option>
                <option v-for="framework in redeployFrameworks" :key="framework.name" :value="framework.name" :disabled="!framework.enabled">
                  {{ framework.display_name }} {{ framework.enabled ? '' : '(disabled)' }}
                </option>
              </select>
              <small>KServe, Ray Serve 등 서빙 프레임워크 선택</small>
            </div>
            <div v-if="selectedRedeployFramework" class="framework-info">
              <strong>Capabilities:</strong>
              <ul>
                <li v-for="capability in selectedRedeployFramework.capabilities" :key="capability">
                  {{ capability }}
                </li>
              </ul>
            </div>
          </div>

          <div class="subsection">
            <h3 class="subsection-title">Kubernetes Resources</h3>
            <p class="form-note">DeploymentSpec 외부의 Kubernetes 리소스 제한 설정</p>
            <div class="form-row">
              <div class="form-field">
                <label>CPU Request</label>
                <input v-model="redeployCpuRequest" type="text" placeholder="e.g., 2 or 1000m" />
                <small>CPU request (e.g., '2' or '1000m')</small>
              </div>
              <div class="form-field">
                <label>CPU Limit</label>
                <input v-model="redeployCpuLimit" type="text" placeholder="e.g., 4 or 2000m" />
                <small>CPU limit (e.g., '4' or '2000m')</small>
              </div>
            </div>
            <div class="form-row">
              <div class="form-field">
                <label>Memory Request</label>
                <input v-model="redeployMemoryRequest" type="text" placeholder="e.g., 4Gi or 2G" />
                <small>Memory request (e.g., '4Gi' or '2G')</small>
              </div>
              <div class="form-field">
                <label>Memory Limit</label>
                <input v-model="redeployMemoryLimit" type="text" placeholder="e.g., 8Gi or 4G" />
                <small>Memory limit (e.g., '8Gi' or '4G')</small>
              </div>
            </div>
            <small class="form-note">비워두면 서버 기본값이 사용됩니다</small>
          </div>
        </div>
      </section>

      <div v-if="redeployMessage" :class="['message', redeployMessageType]" style="margin-top: 20px; padding: 12px 16px; border-radius: 4px; font-size: 14px;">
        {{ redeployMessage }}
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
            :disabled="redeploying || deleting || stopping" 
            class="btn-redeploy"
          >
            {{ redeploying ? 'Redeploying...' : 'Redeploy Endpoint' }}
          </button>
          <button @click="handleStop" :disabled="stopping || deleting || redeploying" class="btn-warning">
            {{ stopping ? 'Stopping...' : 'Stop Endpoint' }}
          </button>
          <button @click="handleDelete" :disabled="deleting || stopping || redeploying" class="btn-delete">
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
import { ref, onMounted, reactive, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { servingClient, type ServingEndpoint, type ServingDeployment, type DeploymentSpec, type ServingFramework } from '@/services/servingClient';
import { catalogClient } from '@/services/catalogClient';

const route = useRoute();
const router = useRouter();
const endpoint = ref<ServingEndpoint | null>(null);
const deployment = ref<ServingDeployment | null>(null);
const loading = ref(false);
const error = ref('');
const stopping = ref(false);
const deleting = ref(false);
const redeploying = ref(false);
const redeployCpuRequest = ref<string>('');
const redeployCpuLimit = ref<string>('');
const redeployMemoryRequest = ref<string>('');
const redeployMemoryLimit = ref<string>('');
const redeployDeploymentSpec = reactive<Partial<DeploymentSpec>>({});
const redeployAutoscalePolicy = reactive<{
  targetLatencyMs?: number;
  gpuUtilization?: number;
  cpuUtilization?: number;
}>({});
const redeployServingFramework = ref<string>('');
const redeployFrameworks = ref<ServingFramework[]>([]);
const showRedeployAdvanced = ref(false);

// Computed properties for redeploy DeploymentSpec
const hasRedeployDeploymentSpec = computed(() => {
  return !!(
    redeployDeploymentSpec.model_ref &&
    redeployDeploymentSpec.model_family &&
    redeployDeploymentSpec.job_type &&
    redeployDeploymentSpec.serve_target &&
    redeployDeploymentSpec.resources &&
    redeployDeploymentSpec.runtime
  );
});

const redeployUseGpuEnabled = computed({
  get: () => (redeployDeploymentSpec.resources?.gpus || 0) > 0,
  set: (value: boolean) => {
    if (value) {
      if (!redeployDeploymentSpec.resources) {
        redeployDeploymentSpec.resources = { gpus: 1, gpu_memory_gb: 80 };
      } else {
        redeployDeploymentSpec.resources.gpus = redeployDeploymentSpec.resources.gpus || 1;
      }
      redeployDeploymentSpec.use_gpu = true;
    } else {
      if (redeployDeploymentSpec.resources) {
        redeployDeploymentSpec.resources.gpus = 0;
      }
      redeployDeploymentSpec.use_gpu = false;
    }
  },
});

const selectedRedeployFramework = computed(() => {
  if (!redeployServingFramework.value) return null;
  return redeployFrameworks.value.find(f => f.name === redeployServingFramework.value) || null;
});

const redeployRolloutStrategy = computed({
  get: () => redeployDeploymentSpec.rollout?.strategy || "",
  set: (value: string) => {
    if (!value) {
      redeployDeploymentSpec.rollout = undefined;
    } else {
      if (!redeployDeploymentSpec.rollout) {
        redeployDeploymentSpec.rollout = {
          strategy: value as "blue-green" | "canary",
        };
      } else {
        redeployDeploymentSpec.rollout.strategy = value as "blue-green" | "canary";
      }
    }
  },
});

// Handler functions for redeploy DeploymentSpec
function onRedeployJobTypeChange() {
  // Auto-set serve_target based on job_type
  if (redeployDeploymentSpec.job_type === "RAG_TUNING") {
    redeployDeploymentSpec.serve_target = "RAG";
  } else if (["SFT", "RLHF", "PRETRAIN"].includes(redeployDeploymentSpec.job_type || "")) {
    redeployDeploymentSpec.serve_target = "GENERATION";
  }
}

const redeployMessage = ref("");
const redeployMessageType = ref<"success" | "error">("success");

function onRedeployServeTargetChange() {
  // RAG_TUNING must use RAG serve_target
  if (redeployDeploymentSpec.job_type === "RAG_TUNING" && redeployDeploymentSpec.serve_target !== "RAG") {
    redeployDeploymentSpec.serve_target = "RAG";
    redeployMessage.value = "RAG_TUNING job type requires RAG serve_target";
    redeployMessageType.value = "error";
    setTimeout(() => { redeployMessage.value = ""; }, 3000);
  }
  // SFT/RLHF must use GENERATION serve_target
  if ((redeployDeploymentSpec.job_type === "SFT" || redeployDeploymentSpec.job_type === "RLHF") && redeployDeploymentSpec.serve_target !== "GENERATION") {
    redeployDeploymentSpec.serve_target = "GENERATION";
    redeployMessage.value = `${redeployDeploymentSpec.job_type} job type requires GENERATION serve_target`;
    redeployMessageType.value = "error";
    setTimeout(() => { redeployMessage.value = ""; }, 3000);
  }
}

function onRedeployUseGpuChange(event: Event) {
  const target = event.target as HTMLInputElement;
  redeployUseGpuEnabled.value = target.checked;
}

function onRedeployRolloutStrategyChange() {
  if (redeployDeploymentSpec.rollout?.strategy === "canary" && !redeployDeploymentSpec.rollout.traffic_split) {
    redeployDeploymentSpec.rollout.traffic_split = {
      old: 90,
      new: 10,
    };
  }
}

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
      // Force Vue reactivity by creating a new object
      endpoint.value = { ...response.data };
      
      // Load model information to get metadata
      let modelData: { name: string; version: string; metadata?: Record<string, any> } | null = null;
      try {
        const modelResponse = await catalogClient.getModel(endpoint.value.modelId);
        if (modelResponse.status === "success" && modelResponse.data) {
          modelData = {
            name: modelResponse.data.name,
            version: modelResponse.data.version,
            metadata: modelResponse.data.metadata || null,
          };
        }
      } catch (e) {
        console.warn("Failed to load model metadata:", e);
      }
      
      const modelMetadata = modelData?.metadata;
      
      // Load existing deploymentSpec if available
      if (endpoint.value.deploymentSpec) {
        // Deep copy deploymentSpec to avoid reactivity issues
        redeployDeploymentSpec.model_ref = endpoint.value.deploymentSpec.model_ref || '';
        redeployDeploymentSpec.model_family = endpoint.value.deploymentSpec.model_family || '';
        redeployDeploymentSpec.job_type = endpoint.value.deploymentSpec.job_type;
        redeployDeploymentSpec.serve_target = endpoint.value.deploymentSpec.serve_target || 'GENERATION';
        redeployDeploymentSpec.resources = {
          gpus: endpoint.value.deploymentSpec.resources?.gpus || (endpoint.value.useGpu ? 1 : 0),
          gpu_memory_gb: endpoint.value.deploymentSpec.resources?.gpu_memory_gb || 80,
        };
        redeployDeploymentSpec.runtime = {
          max_concurrent_requests: endpoint.value.deploymentSpec.runtime?.max_concurrent_requests || 256,
          max_input_tokens: endpoint.value.deploymentSpec.runtime?.max_input_tokens || 4096,
          max_output_tokens: endpoint.value.deploymentSpec.runtime?.max_output_tokens || 1024,
        };
        redeployDeploymentSpec.use_gpu = endpoint.value.deploymentSpec.use_gpu ?? (endpoint.value.useGpu ?? true);
        redeployDeploymentSpec.rollout = endpoint.value.deploymentSpec.rollout;
      } else {
        // No deploymentSpec - reconstruct from model metadata or endpoint settings
        const modelFamily = modelMetadata?.model_family || '';
        const jobType = modelMetadata?.job_type;
        const useGpu = endpoint.value.useGpu ?? true;
        
        // Determine serve_target based on job_type
        let serveTarget = 'GENERATION';
        if (jobType === "RAG_TUNING") {
          serveTarget = "RAG";
        } else if (["SFT", "RLHF", "PRETRAIN"].includes(jobType || "")) {
          serveTarget = "GENERATION";
        }
        
        // Get model name and version for model_ref
        const modelRef = modelData ? `${modelData.name}-${modelData.version}` : '';
        
        // Initialize deploymentSpec from model metadata or defaults
        redeployDeploymentSpec.model_ref = modelRef;
        redeployDeploymentSpec.model_family = modelFamily;
        redeployDeploymentSpec.job_type = jobType;
        redeployDeploymentSpec.serve_target = serveTarget;
        redeployDeploymentSpec.resources = {
          gpus: useGpu ? 1 : 0,
          gpu_memory_gb: useGpu ? 80 : undefined,
        };
        redeployDeploymentSpec.runtime = {
          max_concurrent_requests: 256,
          max_input_tokens: modelMetadata?.max_position_embeddings || 4096,
          max_output_tokens: 1024,
        };
        redeployDeploymentSpec.use_gpu = useGpu;
      }
      
      // Load existing resource settings
      redeployCpuRequest.value = endpoint.value.cpuRequest || '';
      redeployCpuLimit.value = endpoint.value.cpuLimit || '';
      redeployMemoryRequest.value = endpoint.value.memoryRequest || '';
      redeployMemoryLimit.value = endpoint.value.memoryLimit || '';
      
      // Load existing autoscale policy
      if (endpoint.value.autoscalePolicy) {
        redeployAutoscalePolicy.targetLatencyMs = endpoint.value.autoscalePolicy.targetLatencyMs;
        redeployAutoscalePolicy.gpuUtilization = endpoint.value.autoscalePolicy.gpuUtilization;
        redeployAutoscalePolicy.cpuUtilization = endpoint.value.autoscalePolicy.cpuUtilization;
      }
      
      // Load frameworks for redeploy
      try {
        const frameworksRes = await servingClient.listFrameworks();
        if (frameworksRes.status === "success" && frameworksRes.data?.frameworks) {
          redeployFrameworks.value = frameworksRes.data.frameworks;
        }
      } catch (e) {
        console.error("Failed to load frameworks:", e);
      }
    } else {
      error.value = response.message || "Failed to load endpoint";
      endpoint.value = null;
    }
    
    // Fetch deployment information (needed for serving framework)
    try {
      const deploymentResponse = await servingClient.getDeployment(endpointId);
      if (deploymentResponse.status === "success" && deploymentResponse.data) {
        // Force Vue reactivity by creating a new object
        deployment.value = { ...deploymentResponse.data };
        
        // Load serving framework from deployment if available
        if (deployment.value.serving_framework) {
          redeployServingFramework.value = deployment.value.serving_framework;
        } else {
          // Auto-select KServe if it's enabled (default framework)
          const kserveFramework = redeployFrameworks.value.find(f => f.name === "kserve" && f.enabled);
          if (kserveFramework && !redeployServingFramework.value) {
            redeployServingFramework.value = "kserve";
          }
        }
      } else {
        deployment.value = null;
        // Auto-select KServe if it's enabled (default framework) when no deployment
        const kserveFramework = redeployFrameworks.value.find(f => f.name === "kserve" && f.enabled);
        if (kserveFramework && !redeployServingFramework.value) {
          redeployServingFramework.value = "kserve";
        }
      }
    } catch (e) {
      // Deployment info is optional, don't fail if it's not available
      console.warn("Failed to load deployment info:", e);
      deployment.value = null;
      // Auto-select KServe if it's enabled (default framework) when deployment load fails
      const kserveFramework = redeployFrameworks.value.find(f => f.name === "kserve" && f.enabled);
      if (kserveFramework && !redeployServingFramework.value) {
        redeployServingFramework.value = "kserve";
      }
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

  console.log('[Redeploy] Starting redeployment for endpoint:', endpoint.value.id);
  console.log('[Redeploy] Endpoint route:', endpoint.value.route);
  
  redeploying.value = true;
  try {
    // Build DeploymentSpec if all required fields are present
    let deploymentSpec: DeploymentSpec | undefined = undefined;
    
    // If deploymentSpec is incomplete, try to complete it from model metadata
    if (!hasRedeployDeploymentSpec.value) {
      try {
        const modelResponse = await catalogClient.getModel(endpoint.value.modelId);
        if (modelResponse.status === "success" && modelResponse.data) {
          const model = modelResponse.data;
          const metadata = model.metadata || {};
          
          // Fill in missing fields from model metadata
          if (!redeployDeploymentSpec.model_family && metadata.model_family) {
            redeployDeploymentSpec.model_family = metadata.model_family;
          }
          if (!redeployDeploymentSpec.job_type && metadata.job_type) {
            redeployDeploymentSpec.job_type = metadata.job_type;
          }
          if (!redeployDeploymentSpec.model_ref) {
            redeployDeploymentSpec.model_ref = `${model.name}-${model.version}`;
          }
          
          // Auto-set serve_target based on job_type
          if (redeployDeploymentSpec.job_type === "RAG_TUNING") {
            redeployDeploymentSpec.serve_target = "RAG";
          } else if (["SFT", "RLHF", "PRETRAIN"].includes(redeployDeploymentSpec.job_type || "")) {
            redeployDeploymentSpec.serve_target = "GENERATION";
          }
          
          // Set GPU based on endpoint.useGpu if not set
          const useGpu = endpoint.value.useGpu ?? true;
          if (!redeployDeploymentSpec.resources) {
            redeployDeploymentSpec.resources = { gpus: useGpu ? 1 : 0 };
          } else if (redeployDeploymentSpec.resources.gpus === undefined || redeployDeploymentSpec.resources.gpus === 0) {
            redeployDeploymentSpec.resources.gpus = useGpu ? 1 : 0;
          }
          redeployDeploymentSpec.use_gpu = (redeployDeploymentSpec.resources?.gpus || 0) > 0;
          
          // Set runtime defaults if not set
          if (!redeployDeploymentSpec.runtime) {
            redeployDeploymentSpec.runtime = {
              max_concurrent_requests: 256,
              max_input_tokens: metadata.max_position_embeddings || 4096,
              max_output_tokens: 1024,
            };
          }
        }
      } catch (e) {
        console.warn("Failed to load model metadata for completing deploymentSpec:", e);
      }
    }
    
    if (hasRedeployDeploymentSpec.value) {
      // Set use_gpu based on GPU count
      redeployDeploymentSpec.use_gpu = (redeployDeploymentSpec.resources?.gpus || 0) > 0;
      
      deploymentSpec = redeployDeploymentSpec as DeploymentSpec;
      console.log('[Redeploy] Using DeploymentSpec:', JSON.stringify(deploymentSpec, null, 2));
    } else {
      console.log('[Redeploy] No DeploymentSpec available, will use endpoint defaults');
    }

    // Prepare request payload (same structure as EndpointDeploy.vue)
    const request: {
      useGpu?: boolean;
      servingRuntimeImage?: string;
      cpuRequest?: string;
      cpuLimit?: string;
      memoryRequest?: string;
      memoryLimit?: string;
      deploymentSpec?: DeploymentSpec;
      autoscalePolicy?: {
        targetLatencyMs?: number;
        gpuUtilization?: number;
        cpuUtilization?: number;
      };
      servingFramework?: string;
    } = {
      deploymentSpec: deploymentSpec,
    };
    
    // Include useGpu from DeploymentSpec
    if (deploymentSpec && deploymentSpec.use_gpu !== undefined) {
      request.useGpu = deploymentSpec.use_gpu;
    }
    
    // Only include autoscalePolicy if at least one metric is set
    if (redeployAutoscalePolicy && (
      redeployAutoscalePolicy.targetLatencyMs !== undefined ||
      redeployAutoscalePolicy.gpuUtilization !== undefined ||
      redeployAutoscalePolicy.cpuUtilization !== undefined
    )) {
      request.autoscalePolicy = {};
      if (redeployAutoscalePolicy.targetLatencyMs !== undefined) {
        request.autoscalePolicy.targetLatencyMs = redeployAutoscalePolicy.targetLatencyMs;
      }
      if (redeployAutoscalePolicy.gpuUtilization !== undefined) {
        request.autoscalePolicy.gpuUtilization = redeployAutoscalePolicy.gpuUtilization;
      }
      if (redeployAutoscalePolicy.cpuUtilization !== undefined) {
        request.autoscalePolicy.cpuUtilization = redeployAutoscalePolicy.cpuUtilization;
      }
    }
    
    // Include serving framework if selected
    if (redeployServingFramework.value && redeployServingFramework.value.trim()) {
      request.servingFramework = redeployServingFramework.value.trim();
    }
    
    // Include CPU/memory resources if set
    if (redeployCpuRequest.value && redeployCpuRequest.value.trim()) {
      request.cpuRequest = redeployCpuRequest.value.trim();
    }
    if (redeployCpuLimit.value && redeployCpuLimit.value.trim()) {
      request.cpuLimit = redeployCpuLimit.value.trim();
    }
    if (redeployMemoryRequest.value && redeployMemoryRequest.value.trim()) {
      request.memoryRequest = redeployMemoryRequest.value.trim();
    }
    if (redeployMemoryLimit.value && redeployMemoryLimit.value.trim()) {
      request.memoryLimit = redeployMemoryLimit.value.trim();
    }

    console.log('[Redeploy] Request payload:', JSON.stringify(request, null, 2));
    console.log('[Redeploy] Sending redeploy request to API...');
    
    const response = await servingClient.redeployEndpoint(
      endpoint.value.id,
      request
    );
    
    console.log('[Redeploy] Response received:', response);
    
    if (response.status === "success") {
      console.log('[Redeploy] Redeployment started successfully');
      alert('Endpoint redeployment started successfully. Status will update shortly.');
      await fetchEndpoint();
    } else {
      console.error('[Redeploy] Redeployment failed:', response.message);
      alert(`Redeploy failed: ${response.message}`);
    }
  } catch (e) {
    console.error('[Redeploy] Error during redeployment:', e);
    const errorMessage = e instanceof Error ? e.message : String(e);
    alert(`Error: ${errorMessage}`);
  } finally {
    redeploying.value = false;
    console.log('[Redeploy] Redeployment process completed');
  }
}

async function handleStop() {
  if (!endpoint.value) return;
  
  if (!confirm(`Are you sure you want to stop endpoint "${endpoint.value.route}"? This will scale replicas to 0 (endpoint will not be deleted).`)) {
    return;
  }

  stopping.value = true;
  try {
    // Use updateDeployment to set replicas to 0
    const response = await servingClient.updateDeployment(endpoint.value.id, {
      min_replicas: 0,
      max_replicas: 0,
    });
    if (response.status === "success") {
      alert('Endpoint stopped successfully (replicas scaled to 0)');
      // Refresh endpoint status (deployment info may not be available, which is OK)
      try {
        await fetchEndpoint();
      } catch (e) {
        // If fetchEndpoint fails (e.g., deployment not found), that's OK - the stop was successful
        console.warn("Failed to refresh endpoint after stop:", e);
        // Still refresh the endpoint status to update the UI
        try {
          await servingClient.refreshEndpointStatus(endpoint.value.id);
        } catch (refreshError) {
          console.warn("Failed to refresh endpoint status:", refreshError);
        }
      }
    } else {
      alert(`Stop failed: ${response.message}`);
    }
  } catch (e) {
    const errorMessage = e instanceof Error ? e.message : String(e);
    alert(`Error stopping endpoint: ${errorMessage}`);
  } finally {
    stopping.value = false;
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
      // Force refresh by adding timestamp query parameter
      router.push(`/serving/endpoints?refresh=${Date.now()}`);
    } else {
      alert(`Delete failed: ${response.message}`);
    }
  } catch (e) {
    alert(`Error: ${e}`);
  } finally {
    deleting.value = false;
  }
}

async function refreshEndpoint() {
  if (!endpoint.value) return;
  
  loading.value = true;
  try {
    // Use refresh-status API to force status update from Kubernetes
    const response = await servingClient.refreshEndpointStatus(endpoint.value.id);
    if (response.status === "success" && response.data) {
      // Force Vue reactivity by creating a new object
      endpoint.value = { ...response.data };
      // Also reload deployment info
      try {
        const deploymentResponse = await servingClient.getDeployment(endpoint.value.id);
        if (deploymentResponse.status === "success" && deploymentResponse.data) {
          deployment.value = { ...deploymentResponse.data };
        }
      } catch (e) {
        console.warn("Failed to reload deployment info:", e);
      }
    } else {
      // Fallback to regular fetch if refresh-status fails
      await fetchEndpoint();
    }
  } catch (e) {
    console.error("Failed to refresh endpoint status:", e);
    // Fallback to regular fetch
    await fetchEndpoint();
  } finally {
    loading.value = false;
  }
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

.btn-warning {
  padding: 0.5rem 1rem;
  background: #ffc107;
  color: #212529;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-warning:hover:not(:disabled) {
  background: #e0a800;
}

.btn-warning:disabled {
  background: #ccc;
  cursor: not-allowed;
  color: #6c757d;
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

.subsection {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f0f0f0;
}

.subsection-title {
  margin: 0 0 12px 0;
  font-size: 14px;
  font-weight: 600;
  color: #444;
}

.form-note {
  display: block;
  color: #666;
  margin-top: 8px;
  font-size: 0.875rem;
  font-style: italic;
}

.cpu-only-notice {
  margin-top: 12px;
}

.form-field small {
  display: block;
  color: #666;
  margin-top: 6px;
  font-size: 0.875rem;
}

.framework-badge,
.badge {
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

.form-section {
  background: #fff;
  border: 1px solid #e0e0e0;
  border-radius: 8px;
  padding: 24px;
  margin-bottom: 24px;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.section-title {
  margin: 0 0 8px 0;
  font-size: 20px;
  font-weight: 600;
  color: #333;
}

.section-description {
  margin: 0 0 20px 0;
  color: #666;
  font-size: 0.9rem;
  line-height: 1.5;
}

.toggle-button {
  padding: 6px 12px;
  background: #f8f9fa;
  border: 1px solid #ddd;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  color: #007bff;
  transition: all 0.2s;
}

.toggle-button:hover {
  background: #e9ecef;
  border-color: #adb5bd;
}

.framework-info {
  margin-top: 12px;
  padding: 12px;
  background: #f8f9fa;
  border-radius: 4px;
}

.framework-info strong {
  display: block;
  margin-bottom: 8px;
  color: #333;
}

.framework-info ul {
  margin: 0;
  padding-left: 20px;
}

.framework-info li {
  margin: 4px 0;
  color: #666;
}

.message {
  margin-top: 20px;
  padding: 12px 16px;
  border-radius: 4px;
  font-size: 14px;
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
</style>

