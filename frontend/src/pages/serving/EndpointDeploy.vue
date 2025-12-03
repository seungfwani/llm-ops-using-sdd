<template>
  <div class="endpoint-deploy">
    <h1>Deploy Serving Endpoint</h1>
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
        <label>
          <input v-model="form.useGpu" type="checkbox" />
          Use GPU Resources
        </label>
        <small style="display: block; color: #666; margin-top: 5px;">
          Uncheck to deploy with CPU-only resources (useful when GPU nodes are unavailable)
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
      <button type="submit" :disabled="deploying">Deploy</button>
    </form>
    <div v-if="message" :class="messageType">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { servingClient, type ServingEndpointRequest } from "@/services/servingClient";
import { catalogClient } from "@/services/catalogClient";

const form = reactive<ServingEndpointRequest>({
  modelId: "",
  environment: "dev",
  route: "",
  minReplicas: 1,
  maxReplicas: 3,
  useGpu: true, // Default to GPU, user can uncheck for CPU-only
  servingRuntimeImage: "", // Default to empty (use server default)
});

const models = ref([]);
const deploying = ref(false);
const message = ref("");
const messageType = ref<"success" | "error">("success");
const customImage = ref("");

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
      autoscalePolicy: form.autoscalePolicy,
      promptPolicyId: form.promptPolicyId,
    };
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
button {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  cursor: pointer;
}
button:disabled {
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

