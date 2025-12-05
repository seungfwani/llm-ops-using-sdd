<template>
  <div class="endpoint-deploy">
    <header>
      <h1>Deploy Serving Endpoint</h1>
    </header>
    <form @submit.prevent="deployEndpoint">
      <!-- 기본 정보 (필수) -->
      <section class="form-section">
        <h2 class="section-title">기본 정보</h2>
        <div class="form-row">
          <div class="form-field">
            <label>Model <span class="required">*</span></label>
            <select v-model="form.modelId" required>
              <option value="">Select a model</option>
              <option v-for="model in models" :key="model.id" :value="model.id">
                {{ model.name }} ({{ model.version }})
              </option>
            </select>
          </div>
          <div class="form-field">
            <label>Environment <span class="required">*</span></label>
            <select v-model="form.environment" required>
              <option value="dev">Development</option>
              <option value="stg">Staging</option>
              <option value="prod">Production</option>
            </select>
          </div>
        </div>
        <div class="form-field">
          <label>Route <span class="required">*</span></label>
          <input v-model="form.route" type="text" placeholder="/llm-ops/v1/serve/model-name" required />
          <small>Ingress route path for accessing the endpoint</small>
        </div>
        <div class="form-row">
          <div class="form-field">
            <label>Min Replicas <span class="required">*</span></label>
            <input v-model.number="form.minReplicas" type="number" min="1" required />
          </div>
          <div class="form-field">
            <label>Max Replicas <span class="required">*</span></label>
            <input v-model.number="form.maxReplicas" type="number" min="1" required />
          </div>
        </div>
      </section>

      <!-- Deployment Configuration (스펙 기반) -->
      <section class="form-section">
        <h2 class="section-title">Deployment Configuration</h2>
        <p class="section-description">
          Training job의 메타데이터가 자동으로 로드됩니다. DeploymentSpec에 따라 서빙 프레임워크로 배포됩니다.
        </p>

        <div class="form-row">
          <div class="form-field">
            <label>Model Family <span class="required">*</span></label>
            <input v-model="deploymentSpec.model_family" type="text" placeholder="e.g., llama, mistral, gemma" required />
            <small>Training job의 model_family와 일치해야 합니다</small>
          </div>
          <div class="form-field">
            <label>Job Type <span class="required">*</span></label>
            <select v-model="deploymentSpec.job_type" required>
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
          <select v-model="deploymentSpec.serve_target" @change="onServeTargetChange" required>
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
                :checked="useGpuEnabled"
                @change="onUseGpuChange"
                class="checkbox-input"
              />
              <span>Use GPU Resources</span>
            </label>
            <small>체크 해제 시 CPU-only 리소스로 배포됩니다 (GPU 노드가 없거나 비용 절감이 필요한 경우 유용합니다)</small>
          </div>
          <div class="form-row" v-if="useGpuEnabled">
            <div class="form-field">
              <label>GPU Count <span class="required">*</span></label>
              <input v-model.number="deploymentSpec.resources.gpus" type="number" min="1" required />
              <small>Number of GPUs to allocate</small>
            </div>
            <div class="form-field">
              <label>GPU Memory (GB)</label>
              <input v-model.number="deploymentSpec.resources.gpu_memory_gb" type="number" min="0" />
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
              <input v-model.number="deploymentSpec.runtime.max_concurrent_requests" type="number" min="1" required />
            </div>
            <div class="form-field">
              <label>Max Input Tokens <span class="required">*</span></label>
              <input v-model.number="deploymentSpec.runtime.max_input_tokens" type="number" min="1" required />
            </div>
            <div class="form-field">
              <label>Max Output Tokens <span class="required">*</span></label>
              <input v-model.number="deploymentSpec.runtime.max_output_tokens" type="number" min="1" required />
            </div>
          </div>
          <small class="form-note">max_input_tokens must be ≤ model's max_position_embeddings (자동 검증)</small>
        </div>

        <div class="subsection" v-if="hasDeploymentSpec">
          <h3 class="subsection-title">Container Image</h3>
          <div class="image-info" style="padding: 12px; background: #f5f5f5; border-radius: 4px;">
            <small style="color: #666;">
              이미지는 <strong>serve_target</strong> ({{ deploymentSpec.serve_target }})과 
              <strong>use_gpu</strong> ({{ deploymentSpec.use_gpu ? 'GPU' : 'CPU' }}) 설정에 따라 자동으로 선택됩니다.
            </small>
          </div>
        </div>

        <div class="subsection">
          <h3 class="subsection-title">Rollout Strategy (Optional)</h3>
          <div class="form-field">
            <label>Strategy</label>
            <select v-model="rolloutStrategy" @change="onRolloutStrategyChange">
              <option value="">None (default)</option>
              <option value="blue-green">Blue-Green</option>
              <option value="canary">Canary</option>
            </select>
          </div>
          <div v-if="deploymentSpec.rollout?.strategy === 'canary' && deploymentSpec.rollout.traffic_split" class="form-row" style="margin-top: 10px;">
            <div class="form-field">
              <label>Old Version (%)</label>
              <input v-model.number="deploymentSpec.rollout.traffic_split.old" type="number" min="0" max="100" />
            </div>
            <div class="form-field">
              <label>New Version (%)</label>
              <input v-model.number="deploymentSpec.rollout.traffic_split.new" type="number" min="0" max="100" />
            </div>
          </div>
          <small class="form-note" v-if="deploymentSpec.rollout?.strategy === 'canary'">Old + New must equal 100 (자동 검증)</small>
        </div>
      </section>

      <!-- 고급 옵션 (접을 수 있음) -->
      <section class="form-section">
        <div class="section-header">
          <h2 class="section-title">고급 옵션</h2>
          <button type="button" class="toggle-button" @click="showAdvanced = !showAdvanced">
            {{ showAdvanced ? '숨기기' : '보기' }}
          </button>
        </div>
        <div v-show="showAdvanced">
          <div class="subsection">
            <h3 class="subsection-title">Autoscaling Configuration</h3>
            <div class="form-row">
              <div class="form-field">
                <label>Target Latency (ms)</label>
                <input v-model.number="form.autoscalePolicy.targetLatencyMs" type="number" min="0" placeholder="Optional" />
                <small>Target latency in milliseconds</small>
              </div>
              <div class="form-field">
                <label>GPU Utilization (%)</label>
                <input v-model.number="form.autoscalePolicy.gpuUtilization" type="number" min="0" max="100" placeholder="Optional" />
                <small>Target GPU utilization (0-100)</small>
              </div>
              <div class="form-field">
                <label>CPU Utilization (%)</label>
                <input v-model.number="form.autoscalePolicy.cpuUtilization" type="number" min="0" max="100" placeholder="Optional" />
                <small>Target CPU utilization (0-100)</small>
              </div>
            </div>
            <small class="form-note">비워두면 기본 autoscaling 정책이 사용됩니다</small>
          </div>

          <div class="subsection">
            <h3 class="subsection-title">Serving Framework</h3>
            <div class="form-field">
              <label>Serving Framework</label>
              <select v-model="form.servingFramework">
                <option value="">Use default (from server settings)</option>
                <option v-for="framework in frameworks" :key="framework.name" :value="framework.name" :disabled="!framework.enabled">
                  {{ framework.display_name }} {{ framework.enabled ? '' : '(disabled)' }}
                </option>
              </select>
              <small>KServe, Ray Serve 등 서빙 프레임워크 선택</small>
            </div>
            <div v-if="selectedFramework" class="framework-info">
              <strong>Capabilities:</strong>
              <ul>
                <li v-for="capability in selectedFramework.capabilities" :key="capability">
                  {{ capability }}
                </li>
              </ul>
            </div>
          </div>

          <!-- 이미지는 DeploymentSpec 또는 서버 설정에 따라 자동 선택됩니다 -->

          <div class="subsection">
            <h3 class="subsection-title">Kubernetes Resources</h3>
            <p class="form-note">DeploymentSpec 외부의 Kubernetes 리소스 제한 설정</p>
            <div class="form-row">
              <div class="form-field">
                <label>CPU Request</label>
                <input v-model="form.cpuRequest" type="text" placeholder="e.g., 2 or 1000m" />
                <small>CPU request (e.g., '2' or '1000m')</small>
              </div>
              <div class="form-field">
                <label>CPU Limit</label>
                <input v-model="form.cpuLimit" type="text" placeholder="e.g., 4 or 2000m" />
                <small>CPU limit (e.g., '4' or '2000m')</small>
              </div>
            </div>
            <div class="form-row">
              <div class="form-field">
                <label>Memory Request</label>
                <input v-model="form.memoryRequest" type="text" placeholder="e.g., 4Gi or 2G" />
                <small>Memory request (e.g., '4Gi' or '2G')</small>
              </div>
              <div class="form-field">
                <label>Memory Limit</label>
                <input v-model="form.memoryLimit" type="text" placeholder="e.g., 8Gi or 4G" />
                <small>Memory limit (e.g., '8Gi' or '4G')</small>
              </div>
            </div>
            <small class="form-note">비워두면 서버 기본값이 사용됩니다</small>
          </div>
        </div>
      </section>

      <div class="form-actions">
        <button type="button" class="btn-secondary" @click="$router.push('/serving/endpoints')" :disabled="deploying">
          Cancel
        </button>
        <button type="submit" class="btn-primary" :disabled="deploying">
          {{ deploying ? 'Deploying...' : 'Deploy Endpoint' }}
        </button>
      </div>
    </form>
    <div v-if="message" :class="['message', messageType]">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from "vue";
import { servingClient, type ServingEndpointRequest, type ServingFramework, type DeploymentSpec } from "@/services/servingClient";
import { catalogClient } from "@/services/catalogClient";

const form = reactive<ServingEndpointRequest>({
  modelId: "",
  environment: "dev",
  route: "",
  minReplicas: 1,
  maxReplicas: 3,
  useGpu: undefined, // Remove default, will be determined by DeploymentSpec
  servingRuntimeImage: "",
  cpuRequest: "",
  cpuLimit: "",
  memoryRequest: "",
  memoryLimit: "",
  servingFramework: "",
  autoscalePolicy: {
    targetLatencyMs: undefined,
    gpuUtilization: undefined,
    cpuUtilization: undefined,
  },
});

const deploymentSpec = reactive<Partial<DeploymentSpec>>({
  model_ref: "",
  model_family: "",
  job_type: undefined,
  serve_target: "GENERATION",
  resources: {
    gpus: 1,
    gpu_memory_gb: 80,
  },
  runtime: {
    max_concurrent_requests: 256,
    max_input_tokens: 4096,
    max_output_tokens: 1024,
  },
  rollout: undefined,
  use_gpu: true,
});

const models = ref<Array<{ id: string; name: string; version: string; model_metadata?: Record<string, any> }>>([]);
const frameworks = ref<ServingFramework[]>([]);
const deploying = ref(false);
const message = ref("");
const messageType = ref<"success" | "error">("success");
const customImage = ref("");
const showAdvanced = ref(false);

const selectedFramework = computed(() => {
  if (!form.servingFramework) return null;
  return frameworks.value.find(f => f.name === form.servingFramework) || null;
});

const useGpuEnabled = computed({
  get: () => (deploymentSpec.resources?.gpus || 0) > 0,
  set: (value: boolean) => {
    if (value) {
      if (!deploymentSpec.resources) {
        deploymentSpec.resources = { gpus: 1, gpu_memory_gb: 80 };
      } else {
        deploymentSpec.resources.gpus = deploymentSpec.resources.gpus || 1;
      }
      deploymentSpec.use_gpu = true;
    } else {
      if (deploymentSpec.resources) {
        deploymentSpec.resources.gpus = 0;
      }
      deploymentSpec.use_gpu = false;
    }
  },
});

const onUseGpuChange = (event: Event) => {
  const target = event.target as HTMLInputElement;
  useGpuEnabled.value = target.checked;
};

const hasDeploymentSpec = computed(() => {
  return !!(
    deploymentSpec.model_ref &&
    deploymentSpec.model_family &&
    deploymentSpec.job_type &&
    deploymentSpec.serve_target &&
    deploymentSpec.resources &&
    deploymentSpec.runtime
  );
});

// Computed property for rollout strategy to handle optional chaining
const rolloutStrategy = computed({
  get: () => deploymentSpec.rollout?.strategy || "",
  set: (value: string) => {
    if (!value) {
      deploymentSpec.rollout = undefined;
    } else {
      if (!deploymentSpec.rollout) {
        deploymentSpec.rollout = {
          strategy: value as "blue-green" | "canary",
        };
      } else {
        deploymentSpec.rollout.strategy = value as "blue-green" | "canary";
      }
    }
  },
});

// Watch model selection to populate model_family and job_type from metadata
watch(() => form.modelId, async (modelId) => {
  if (modelId) {
    const model = models.value.find(m => m.id === modelId);
    if (model && model.model_metadata) {
      deploymentSpec.model_family = model.model_metadata.model_family || "";
      deploymentSpec.job_type = model.model_metadata.job_type || undefined;
      deploymentSpec.model_ref = `${model.name}-${model.version}`;
      
      // Auto-set serve_target based on job_type
      if (deploymentSpec.job_type === "RAG_TUNING") {
        deploymentSpec.serve_target = "RAG";
      } else if (["SFT", "RLHF", "PRETRAIN"].includes(deploymentSpec.job_type || "")) {
        deploymentSpec.serve_target = "GENERATION";
      }
    }
  }
});

const onServeTargetChange = () => {
  // RAG_TUNING must use RAG serve_target
  if (deploymentSpec.job_type === "RAG_TUNING" && deploymentSpec.serve_target !== "RAG") {
    deploymentSpec.serve_target = "RAG";
    message.value = "RAG_TUNING job type requires RAG serve_target";
    messageType.value = "error";
    setTimeout(() => { message.value = ""; }, 3000);
  }
  // SFT/RLHF must use GENERATION serve_target
  if ((deploymentSpec.job_type === "SFT" || deploymentSpec.job_type === "RLHF") && deploymentSpec.serve_target !== "GENERATION") {
    deploymentSpec.serve_target = "GENERATION";
    message.value = `${deploymentSpec.job_type} job type requires GENERATION serve_target`;
    messageType.value = "error";
    setTimeout(() => { message.value = ""; }, 3000);
  }
};

const onRolloutStrategyChange = () => {
  if (deploymentSpec.rollout?.strategy === "canary" && !deploymentSpec.rollout.traffic_split) {
    deploymentSpec.rollout.traffic_split = {
      old: 90,
      new: 10,
    };
  }
};

onMounted(async () => {
  try {
    const modelsRes = await catalogClient.listModels();
    if (modelsRes.status === "success" && modelsRes.data) {
      const modelsArray = Array.isArray(modelsRes.data) ? modelsRes.data : [modelsRes.data];
      models.value = modelsArray.filter((m) => m.status === "approved");
    }
  } catch (e) {
    console.error("Failed to load models:", e);
  }

  try {
    const frameworksRes = await servingClient.listFrameworks();
    if (frameworksRes.status === "success" && frameworksRes.data?.frameworks) {
      frameworks.value = frameworksRes.data.frameworks;
      
      // Auto-select KServe if it's enabled (default framework)
      const kserveFramework = frameworks.value.find(f => f.name === "kserve" && f.enabled);
      if (kserveFramework && !form.servingFramework) {
        form.servingFramework = "kserve";
      }
    }
  } catch (e) {
    console.error("Failed to load frameworks:", e);
  }
});

async function deployEndpoint() {
  deploying.value = true;
  message.value = "";
  try {
    // Validate that model_family and job_type are provided (required fields)
    if (!deploymentSpec.model_family || !deploymentSpec.model_family.trim()) {
      message.value = "Model Family is required. Please enter a model family (e.g., llama, mistral, gemma).";
      messageType.value = "error";
      deploying.value = false;
      return;
    }
    
    if (!deploymentSpec.job_type) {
      message.value = "Job Type is required. Please select a job type.";
      messageType.value = "error";
      deploying.value = false;
      return;
    }
    
    // Ensure model_ref is set
    if (!deploymentSpec.model_ref || !deploymentSpec.model_ref.trim()) {
      // Try to get from selected model
      const selectedModel = models.value.find(m => m.id === form.modelId);
      if (selectedModel) {
        deploymentSpec.model_ref = `${selectedModel.name}-${selectedModel.version}`;
      } else {
        message.value = "Model Reference is required. Please select a model.";
        messageType.value = "error";
        deploying.value = false;
        return;
      }
    }
    
    // Ensure serve_target is set based on job_type if not already set
    if (!deploymentSpec.serve_target) {
      if (deploymentSpec.job_type === "RAG_TUNING") {
        deploymentSpec.serve_target = "RAG";
      } else {
        deploymentSpec.serve_target = "GENERATION";
      }
    }
    
    // Ensure resources are set
    if (!deploymentSpec.resources) {
      const useGpu = deploymentSpec.use_gpu ?? true;
      deploymentSpec.resources = {
        gpus: useGpu ? 1 : 0,
        gpu_memory_gb: useGpu ? 80 : undefined,
      };
    }
    
    // Ensure runtime is set
    if (!deploymentSpec.runtime) {
      deploymentSpec.runtime = {
        max_concurrent_requests: 256,
        max_input_tokens: 4096,
        max_output_tokens: 1024,
      };
    }
    
    // Set use_gpu based on GPU count
    deploymentSpec.use_gpu = (deploymentSpec.resources?.gpus || 0) > 0;
    
    // Build DeploymentSpec - now it should be complete
    const spec: DeploymentSpec = deploymentSpec as DeploymentSpec;

    // Prepare request payload
    const request: ServingEndpointRequest = {
      modelId: form.modelId,
      environment: form.environment,
      route: form.route,
      minReplicas: form.minReplicas,
      maxReplicas: form.maxReplicas,
      autoscalePolicy: undefined,
      promptPolicyId: form.promptPolicyId,
      deploymentSpec: spec, // Always include deploymentSpec with model_family and job_type
    };
    
    // Only include autoscalePolicy if at least one metric is set
    if (form.autoscalePolicy && (
      form.autoscalePolicy.targetLatencyMs !== undefined ||
      form.autoscalePolicy.gpuUtilization !== undefined ||
      form.autoscalePolicy.cpuUtilization !== undefined
    )) {
      request.autoscalePolicy = {};
      if (form.autoscalePolicy.targetLatencyMs !== undefined) {
        request.autoscalePolicy.targetLatencyMs = form.autoscalePolicy.targetLatencyMs;
      }
      if (form.autoscalePolicy.gpuUtilization !== undefined) {
        request.autoscalePolicy.gpuUtilization = form.autoscalePolicy.gpuUtilization;
      }
      if (form.autoscalePolicy.cpuUtilization !== undefined) {
        request.autoscalePolicy.cpuUtilization = form.autoscalePolicy.cpuUtilization;
      }
    }
    
    // Include serving framework if selected
    if (form.servingFramework && form.servingFramework.trim()) {
      request.servingFramework = form.servingFramework.trim();
    }
    
    // Include useGpu from DeploymentSpec
    if (spec.use_gpu !== undefined) {
      request.useGpu = spec.use_gpu;
    }
    
    // Include CPU/memory resources if set
    if (form.cpuRequest && form.cpuRequest.trim()) {
      request.cpuRequest = form.cpuRequest.trim();
    }
    if (form.cpuLimit && form.cpuLimit.trim()) {
      request.cpuLimit = form.cpuLimit.trim();
    }
    if (form.memoryRequest && form.memoryRequest.trim()) {
      request.memoryRequest = form.memoryRequest.trim();
    }
    if (form.memoryLimit && form.memoryLimit.trim()) {
      request.memoryLimit = form.memoryLimit.trim();
    }
    
    const response = await servingClient.deployEndpoint(request);
    if (response.status === "success") {
      message.value = `Endpoint deployed successfully: ${response.data?.id}`;
      messageType.value = "success";
      setTimeout(() => {
        // Navigate to endpoint detail page
        if (response.data?.id) {
          window.location.href = `/serving/endpoints/${response.data.id}`;
        }
      }, 1500);
    } else {
      message.value = response.message || "Failed to deploy endpoint";
      messageType.value = "error";
    }
  } catch (e) {
    message.value = `Error: ${e}`;
    messageType.value = "error";
  } finally {
    deploying.value = false;
  }
}
</script>

<style scoped>
.endpoint-deploy {
  max-width: 900px;
  margin: 0 auto;
  padding: 20px;
}

header {
  margin-bottom: 30px;
}

header h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 600;
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

.subsection {
  margin-top: 24px;
  padding-top: 24px;
  border-top: 1px solid #f0f0f0;
}

.subsection-title {
  margin: 0 0 16px 0;
  font-size: 16px;
  font-weight: 600;
  color: #444;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.form-field {
  margin-bottom: 16px;
}

.form-field label {
  display: block;
  margin-bottom: 6px;
  font-weight: 500;
  color: #333;
}

.required {
  color: #dc3545;
}

.form-field input[type="text"],
.form-field input[type="number"],
.form-field select {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
  transition: border-color 0.2s;
}

.form-field input[type="text"]:focus,
.form-field input[type="number"]:focus,
.form-field select:focus {
  outline: none;
  border-color: #007bff;
  box-shadow: 0 0 0 3px rgba(0, 123, 255, 0.1);
}

small {
  display: block;
  color: #666;
  margin-top: 6px;
  font-size: 0.875rem;
}

.form-note {
  display: block;
  color: #666;
  margin-top: 8px;
  font-size: 0.875rem;
  font-style: italic;
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

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 32px;
  padding-top: 24px;
  border-top: 2px solid #e9ecef;
}

.btn-primary,
.btn-secondary {
  padding: 12px 24px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 15px;
  font-weight: 500;
  transition: all 0.2s;
}

.btn-primary {
  background: #007bff;
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-secondary {
  background: #6c757d;
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  background: #5a6268;
}

.btn-primary:disabled,
.btn-secondary:disabled {
  background: #ccc;
  cursor: not-allowed;
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
  width: auto;
  margin: 0;
  cursor: pointer;
  width: 18px;
  height: 18px;
  accent-color: #007bff;
}

.cpu-only-notice {
  margin-top: 12px;
}

@media (max-width: 768px) {
  .endpoint-deploy {
    padding: 16px;
  }
  
  .form-row {
    grid-template-columns: 1fr;
  }
  
  .form-section {
    padding: 16px;
  }
}
</style>
