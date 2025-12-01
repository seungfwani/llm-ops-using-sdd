<template>
  <div class="job-detail">
    <h1>Training Job: {{ jobId }}</h1>
    <div v-if="loading">Loading...</div>
    <div v-else-if="error">{{ error }}</div>
    <div v-else-if="job">
      <div class="job-info">
        <p><strong>Status:</strong> {{ job.status }}</p>
        <p><strong>Model ID:</strong> {{ job.modelId }}</p>
        <p><strong>Dataset ID:</strong> {{ job.datasetId }}</p>
        <p><strong>Job Type:</strong> {{ job.jobType }}</p>
        <p><strong>Submitted:</strong> {{ formatDate(job.submittedAt) }}</p>
        <p v-if="job.startedAt"><strong>Started:</strong> {{ formatDate(job.startedAt) }}</p>
        <p v-if="job.completedAt"><strong>Completed:</strong> {{ formatDate(job.completedAt) }}</p>
        <a v-if="job.experimentUrl" :href="job.experimentUrl">View Experiment</a>
      </div>
      <button v-if="canCancel" @click="cancelJob">Cancel Job</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { trainingClient, type TrainingJob } from "@/services/trainingClient";

const route = useRoute();
const jobId = route.params.id as string;

const job = ref<TrainingJob | null>(null);
const loading = ref(true);
const error = ref("");

const canCancel = computed(() => {
  return job.value && ["queued", "running"].includes(job.value.status);
});

onMounted(async () => {
  await loadJob();
  // Poll for status updates if job is still running
  if (job.value && ["queued", "running"].includes(job.value.status)) {
    const interval = setInterval(async () => {
      await loadJob();
      if (job.value && ["succeeded", "failed", "cancelled"].includes(job.value.status)) {
        clearInterval(interval);
      }
    }, 5000);
  }
});

async function loadJob() {
  loading.value = true;
  error.value = "";
  try {
    const response = await trainingClient.getJob(jobId);
    if (response.status === "success" && response.data) {
      job.value = response.data;
    } else {
      error.value = response.message || "Failed to load job";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    loading.value = false;
  }
}

async function cancelJob() {
  if (!job.value) return;
  try {
    const response = await trainingClient.cancelJob(jobId);
    if (response.status === "success") {
      await loadJob();
    } else {
      error.value = response.message || "Failed to cancel job";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}
</script>

<style scoped>
.job-detail {
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}
.job-info {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 5px;
  margin-bottom: 15px;
}
.job-info p {
  margin: 8px 0;
}
button {
  padding: 10px 20px;
  background: #dc3545;
  color: white;
  border: none;
  cursor: pointer;
}
</style>

