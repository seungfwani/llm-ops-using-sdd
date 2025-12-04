<template>
  <div class="endpoint-deploy">
    <header>
      <router-link to="/serving/endpoints" class="back-link">← Back to Endpoints</router-link>
      <h1>Deploy Serving Endpoint</h1>
    </header>
    <form @submit.prevent="deployEndpoint">
      <div>
        <label>Model:</label>
        <select v-model="form.modelId" required>
          <option value="">Select a model</option>
          <option v-for="model in models" :key="model.id" :value="model.id">
            {{ model.name }} ({{ model.version }})
          </option>
        </select>
      </div>
      <div>
        <label>Environment:</label>
        <select v-model="form.environment" required>
          <option value="dev">Development</option>
          <option value="stg">Staging</option>
          <option value="prod">Production</option>
        </select>
      </div>
      <div>
        <label>Route:</label>
        <input v-model="form.route" placeholder="/llm-ops/v1/serve/model-name" required />
      </div>
      <div>
        <label>Min Replicas:</label>
        <input v-model.number="form.minReplicas" type="number" min="1" required />
      </div>
      <div>
        <label>Max Replicas:</label>
        <input v-model.number="form.maxReplicas" type="number" min="1" required />
      </div>
      <div>
        <label>Serving Framework:</label>
        <select v-model="form.servingFramework">
          <option value="">Use default (from server settings)</option>
          <option v-for="framework in frameworks" :key="framework.name" :value="framework.name" :disabled="!framework.enabled">
            {{ framework.display_name }} {{ framework.enabled ? '' : '(disabled)' }}
          </option>
        </select>
        <small style="display: block; color: #666; margin-top: 5px;">
          Select the serving framework to use (KServe, Ray Serve, etc.). Leave empty to use server default.
        </small>
        <div v-if="selectedFramework" style="margin-top: 10px; padding: 10px; background: #f8f9fa; border-radius: 4px;">
          <strong>Capabilities:</strong>
          <ul style="margin: 5px 0 0 20px; padding: 0;">
            <li v-for="capability in selectedFramework.capabilities" :key="capability" style="margin: 3px 0;">
              {{ capability }}
            </li>
          </ul>
        </div>
      </div>
      <div>
        <label>Autoscaling Configuration:</label>
        <div style="margin-left: 20px; margin-top: 10px;">
          <div style="margin-bottom: 10px;">
            <label style="display: flex; align-items: center;">
              <input v-model.number="form.autoscalePolicy.targetLatencyMs" type="number" min="0" placeholder="Target latency (ms)" style="width: 200px; margin-right: 10px;" />
              Target Latency (ms)
            </label>
            <small style="display: block; color: #666; margin-top: 5px; margin-left: 210px;">
              Target latency in milliseconds for autoscaling decisions
            </small>
          </div>
          <div style="margin-bottom: 10px;">
            <label style="display: flex; align-items: center;">
              <input v-model.number="form.autoscalePolicy.gpuUtilization" type="number" min="0" max="100" placeholder="GPU utilization (%)" style="width: 200px; margin-right: 10px;" />
              GPU Utilization (%)
            </label>
            <small style="display: block; color: #666; margin-top: 5px; margin-left: 210px;">
              Target GPU utilization percentage (0-100)
            </small>
          </div>
          <div style="margin-bottom: 10px;">
            <label style="display: flex; align-items: center;">
              <input v-model.number="form.autoscalePolicy.cpuUtilization" type="number" min="0" max="100" placeholder="CPU utilization (%)" style="width: 200px; margin-right: 10px;" />
              CPU Utilization (%)
            </label>
            <small style="display: block; color: #666; margin-top: 5px; margin-left: 210px;">
              Target CPU utilization percentage (0-100)
            </small>
          </div>
        </div>
        <small style="display: block; color: #666; margin-top: 5px;">
          Configure autoscaling metrics. Leave empty to use default autoscaling behavior.
        </small>
      </div>
      <div>
        <label>
          <input v-model="form.useGpu" type="checkbox" />
          Use GPU Resources
        </label>
        <small style="display: block; color: #666; margin-top: 5px;">
          Uncheck to deploy with CPU-only resources (useful when GPU nodes are unavailable)
        </small>
      </div>
      <div>
        <label>CPU Request:</label>
        <input v-model="form.cpuRequest" type="text" placeholder="e.g., 2 or 1000m" />
        <small style="display: block; color: #666; margin-top: 5px;">
          CPU request (e.g., '2' for 2 cores, '1000m' for 1000 millicores). Leave empty to use default.
        </small>
      </div>
      <div>
        <label>CPU Limit:</label>
        <input v-model="form.cpuLimit" type="text" placeholder="e.g., 4 or 2000m" />
        <small style="display: block; color: #666; margin-top: 5px;">
          CPU limit (e.g., '4' for 4 cores, '2000m' for 2000 millicores). Leave empty to use default.
        </small>
      </div>
      <div>
        <label>Memory Request:</label>
        <input v-model="form.memoryRequest" type="text" placeholder="e.g., 4Gi or 2G" />
        <small style="display: block; color: #666; margin-top: 5px;">
          Memory request (e.g., '4Gi' for 4 gibibytes, '2G' for 2 gigabytes). Leave empty to use default.
        </small>
      </div>
      <div>
        <label>Memory Limit:</label>
        <input v-model="form.memoryLimit" type="text" placeholder="e.g., 8Gi or 4G" />
        <small style="display: block; color: #666; margin-top: 5px;">
          Memory limit (e.g., '8Gi' for 8 gibibytes, '4G' for 4 gigabytes). Leave empty to use default.
        </small>
      </div>
      <div>
        <label>Serving Runtime Image:</label>
        <select v-model="form.servingRuntimeImage">
          <option value="">Use default (from server settings)</option>
          <option value="vllm/vllm-openai:nightly">vLLM OpenAI (nightly)</option>
          <option value="ghcr.io/vllm/vllm:latest">vLLM (latest)</option>
          <option value="ghcr.io/vllm/vllm:0.6.0">vLLM (0.6.0)</option>
          <option value="ghcr.io/huggingface/text-generation-inference:latest">TGI (latest, GHCR)</option>
          <option value="custom">Custom image...</option>
        </select>
        <input 
          v-if="form.servingRuntimeImage === 'custom'"
          v-model="customImage"
          type="text"
          placeholder="e.g., my-registry.io/my-image:tag"
          style="margin-top: 5px;"
        />
        <small style="display: block; color: #666; margin-top: 5px;">
          Select the container image for model serving runtime. Different models may require different images.
        </small>
      </div>
      <div class="form-actions">
        <button type="button" class="btn-secondary" @click="$router.push('/serving/endpoints')" :disabled="deploying">
          Cancel
        </button>
        <button type="submit" class="btn-primary" :disabled="deploying">
          {{ deploying ? 'Deploying...' : 'Deploy Endpoint' }}
        </button>
      </div>
    </form>
    <div v-if="message" :class="messageType">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from "vue";
import { servingClient, type ServingEndpointRequest, type ServingFramework } from "@/services/servingClient";
import { catalogClient } from "@/services/catalogClient";

const form = reactive<ServingEndpointRequest>({
  modelId: "",
  environment: "dev",
  route: "",
  minReplicas: 1,
  maxReplicas: 3,
  useGpu: true, // Default to GPU, user can uncheck for CPU-only
  servingRuntimeImage: "", // Default to empty (use server default)
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

const models = ref([]);
const frameworks = ref<ServingFramework[]>([]);
const deploying = ref(false);
const message = ref("");
const messageType = ref<"success" | "error">("success");
const customImage = ref("");

const selectedFramework = computed(() => {
  if (!form.servingFramework) return null;
  return frameworks.value.find(f => f.name === form.servingFramework) || null;
});

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
    }
  } catch (e) {
    console.error("Failed to load frameworks:", e);
  }
});

async function deployEndpoint() {
  deploying.value = true;
  message.value = "";
  try {
    // Prepare request payload
    const request: ServingEndpointRequest = {
      modelId: form.modelId,
      environment: form.environment,
      route: form.route,
      minReplicas: form.minReplicas,
      maxReplicas: form.maxReplicas,
      autoscalePolicy: undefined,
      promptPolicyId: form.promptPolicyId,
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
    // Only include useGpu if it's explicitly set (not undefined)
    if (form.useGpu !== undefined) {
      request.useGpu = form.useGpu;
    }
    // Handle serving runtime image
    if (form.servingRuntimeImage === "custom" && customImage.value.trim()) {
      request.servingRuntimeImage = customImage.value.trim();
    } else if (form.servingRuntimeImage && form.servingRuntimeImage !== "custom") {
      request.servingRuntimeImage = form.servingRuntimeImage;
    }
    // Only include servingRuntimeImage if it's set
    if (!request.servingRuntimeImage) {
      delete request.servingRuntimeImage;
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
      // TODO: Navigate to endpoint detail page
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
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

header {
  margin-bottom: 20px;
}

.back-link {
  display: inline-block;
  margin-bottom: 10px;
  color: #007bff;
  text-decoration: none;
  font-size: 14px;
}

.back-link:hover {
  text-decoration: underline;
}

header h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

form > div {
  margin-bottom: 15px;
}
label {
  display: block;
  margin-bottom: 5px;
}
input[type="text"],
input[type="number"],
select {
  width: 100%;
  padding: 8px;
}

input[type="checkbox"] {
  width: auto;
  margin-right: 8px;
}

small {
  display: block;
  color: #666;
  margin-top: 5px;
  font-size: 0.875rem;
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 20px;
}

.btn-primary,
.btn-secondary {
  padding: 10px 20px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
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
.success {
  color: green;
  margin-top: 10px;
}
.error {
  color: red;
  margin-top: 10px;
}
</style>

