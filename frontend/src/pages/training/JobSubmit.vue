<template>
  <div class="job-submit">
    <h1>Submit Training Job</h1>
    <form @submit.prevent="submitJob">
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
        <label>Dataset:</label>
        <select v-model="form.datasetId" required>
          <option value="">Select a dataset</option>
          <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">
            {{ dataset.name }} ({{ dataset.version }})
          </option>
        </select>
      </div>
      <div>
        <label>Job Type:</label>
        <select v-model="form.jobType" required>
          <option value="finetune">Fine-tuning</option>
          <option value="distributed">Distributed Training</option>
        </select>
      </div>
      <div>
        <label>GPU Count:</label>
        <input v-model.number="form.resourceProfile.gpuCount" type="number" min="1" required />
      </div>
      <div>
        <label>GPU Type:</label>
        <input v-model="form.resourceProfile.gpuType" required />
      </div>
      <div>
        <label>Max Duration (minutes):</label>
        <input v-model.number="form.resourceProfile.maxDuration" type="number" min="1" required />
      </div>
      <button type="submit" :disabled="submitting">Submit Job</button>
    </form>
    <div v-if="message" :class="messageType">{{ message }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from "vue";
import { trainingClient, type TrainingJobRequest } from "@/services/trainingClient";
import { catalogClient } from "@/services/catalogClient";

const form = reactive<TrainingJobRequest>({
  modelId: "",
  datasetId: "",
  jobType: "finetune",
  resourceProfile: {
    gpuCount: 1,
    gpuType: "nvidia-tesla-v100",
    maxDuration: 60,
  },
});

const models = ref([]);
const datasets = ref([]);
const submitting = ref(false);
const message = ref("");
const messageType = ref<"success" | "error">("success");

onMounted(async () => {
  // Load models and datasets for selection
  try {
    const modelsRes = await catalogClient.listModels();
    if (modelsRes.status === "success" && modelsRes.data) {
      models.value = Array.isArray(modelsRes.data) ? modelsRes.data : [modelsRes.data];
    }
    // TODO: Load datasets similarly
  } catch (e) {
    console.error("Failed to load models/datasets:", e);
  }
});

async function submitJob() {
  submitting.value = true;
  message.value = "";
  try {
    const response = await trainingClient.submitJob(form);
    if (response.status === "success") {
      message.value = `Job submitted successfully: ${response.data?.id}`;
      messageType.value = "success";
      // TODO: Navigate to job detail page
    } else {
      message.value = response.message || "Failed to submit job";
      messageType.value = "error";
    }
  } catch (e) {
    message.value = `Error: ${e}`;
    messageType.value = "error";
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.job-submit {
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

