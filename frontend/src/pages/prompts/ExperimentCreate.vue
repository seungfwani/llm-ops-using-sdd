<template>
  <div class="experiment-create">
    <h1>Create Prompt A/B Experiment</h1>
    <form @submit.prevent="createExperiment">
      <div>
        <label>Template A:</label>
        <select v-model="form.templateAId" required>
          <option value="">Select template A</option>
          <option v-for="template in templates" :key="template.id" :value="template.id">
            {{ template.name }} ({{ template.version }})
          </option>
        </select>
      </div>
      <div>
        <label>Template B:</label>
        <select v-model="form.templateBId" required>
          <option value="">Select template B</option>
          <option v-for="template in templates" :key="template.id" :value="template.id">
            {{ template.name }} ({{ template.version }})
          </option>
        </select>
      </div>
      <div>
        <label>Allocation (Template A %):</label>
        <input
          v-model.number="form.allocation"
          type="number"
          min="0"
          max="100"
          required
        />
        <small>Percentage of traffic to route to Template A (remainder goes to B)</small>
      </div>
      <div>
        <label>Metric to Optimize:</label>
        <select v-model="form.metric" required>
          <option value="latency_ms">Latency (ms)</option>
          <option value="user_satisfaction">User Satisfaction</option>
          <option value="token_count">Token Count</option>
        </select>
      </div>
      <button type="submit" :disabled="creating">Create Experiment</button>
    </form>
    <div v-if="message" :class="messageType">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";

interface PromptExperimentRequest {
  templateAId: string;
  templateBId: string;
  allocation: number;
  metric: string;
}

const form = reactive<PromptExperimentRequest>({
  templateAId: "",
  templateBId: "",
  allocation: 50,
  metric: "latency_ms",
});

const templates = ref([]);
const creating = ref(false);
const message = ref("");
const messageType = ref<"success" | "error">("success");

onMounted(async () => {
  // TODO: Load prompt templates from API
  templates.value = [];
});

async function createExperiment() {
  creating.value = true;
  message.value = "";
  try {
    // TODO: Call API to create experiment
    message.value = "Experiment created successfully";
    messageType.value = "success";
  } catch (e) {
    message.value = `Error: ${e}`;
    messageType.value = "error";
  } finally {
    creating.value = false;
  }
}
</script>

<style scoped>
.experiment-create {
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
small {
  display: block;
  color: #666;
  margin-top: 5px;
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

