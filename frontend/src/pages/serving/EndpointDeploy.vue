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
});

const models = ref([]);
const deploying = ref(false);
const message = ref("");
const messageType = ref<"success" | "error">("success");

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
    const response = await servingClient.deployEndpoint(form);
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
input,
select {
  width: 100%;
  padding: 8px;
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

