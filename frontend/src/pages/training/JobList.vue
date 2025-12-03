<template>
  <section class="job-list">
    <header>
      <h1>Training Jobs</h1>
      <div class="header-actions">
        <button @click="fetchJobs" :disabled="loading">Refresh</button>
        <router-link to="/training/jobs/submit" class="btn-primary">Submit New Job</router-link>
      </div>
    </header>

    <div class="filters">
      <label>
        Status:
        <select v-model="filters.status" @change="fetchJobs">
          <option value="">All</option>
          <option value="queued">Queued</option>
          <option value="running">Running</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </label>
      <label>
        Model ID:
        <input
          v-model="filters.modelId"
          @input="debouncedFetch"
          placeholder="Filter by model ID"
        />
      </label>
    </div>

    <div v-if="loading" class="loading">Loading jobs...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="jobs.length" class="jobs-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Model ID</th>
          <th>Dataset ID</th>
          <th>Job Type</th>
          <th>Status</th>
          <th>Submitted</th>
          <th>Started</th>
          <th>Completed</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="job in jobs" :key="job.id">
          <td class="id-cell">{{ job.id.substring(0, 8) }}...</td>
          <td>{{ job.modelId.substring(0, 8) }}...</td>
          <td>{{ job.datasetId.substring(0, 8) }}...</td>
          <td>
            <span class="job-type-badge">{{ job.jobType }}</span>
          </td>
          <td>
            <span :class="`status-badge status-${job.status}`">
              {{ job.status }}
            </span>
          </td>
          <td>{{ formatDate(job.submittedAt) }}</td>
          <td>{{ job.startedAt ? formatDate(job.startedAt) : "-" }}</td>
          <td>{{ job.completedAt ? formatDate(job.completedAt) : "-" }}</td>
          <td>
            <router-link :to="`/training/jobs/${job.id}`" class="btn-link">View</router-link>
            <button
              v-if="canCancel(job.status)"
              @click="handleCancel(job.id)"
              class="btn-cancel-small"
              :disabled="cancellingIds.has(job.id)"
            >
              {{ cancellingIds.has(job.id) ? "Cancelling..." : "Cancel" }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No training jobs found.</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive } from "vue";
import {
  trainingClient,
  type TrainingJob,
  type ListJobsFilters,
} from "@/services/trainingClient";

const jobs = ref<TrainingJob[]>([]);
const loading = ref(false);
const error = ref("");
const cancellingIds = ref<Set<string>>(new Set());

const filters = reactive<ListJobsFilters>({
  status: "",
  modelId: "",
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

const debouncedFetch = () => {
  if (debounceTimer) {
    clearTimeout(debounceTimer);
  }
  debounceTimer = setTimeout(() => {
    fetchJobs();
  }, 500);
};

const canCancel = (status: string): boolean => {
  return ["queued", "running"].includes(status);
};

const fetchJobs = async () => {
  loading.value = true;
  error.value = "";
  try {
    const response = await trainingClient.listJobs(filters);
    if (response.status === "success" && response.data) {
      jobs.value = response.data.jobs;
    } else {
      error.value = response.message || "Failed to load jobs";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    loading.value = false;
  }
};

const handleCancel = async (jobId: string) => {
  if (cancellingIds.value.has(jobId)) return;

  cancellingIds.value.add(jobId);
  try {
    const response = await trainingClient.cancelJob(jobId);
    if (response.status === "success") {
      await fetchJobs();
    } else {
      error.value = response.message || "Failed to cancel job";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    cancellingIds.value.delete(jobId);
  }
};

const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleString();
};

onMounted(() => {
  fetchJobs();
  // Auto-refresh disabled - user can manually refresh using the Refresh button
  // const interval = setInterval(() => {
  //   const hasActiveJobs = jobs.value.some((job) =>
  //     ["queued", "running"].includes(job.status)
  //   );
  //   if (hasActiveJobs) {
  //     fetchJobs();
  //   }
  // }, 10000);
  // return () => clearInterval(interval);
});
</script>

<style scoped>
.job-list {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

header h1 {
  margin: 0;
  font-size: 24px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.btn-primary {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  border: none;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover {
  background: #0056b3;
}

button {
  padding: 8px 16px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

button:hover:not(:disabled) {
  background: #5a6268;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.filters {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  padding: 15px;
  background: #f8f9fa;
  border-radius: 4px;
}

.filters label {
  display: flex;
  flex-direction: column;
  gap: 5px;
  font-size: 14px;
  font-weight: 500;
}

.filters select,
.filters input {
  padding: 8px 12px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 14px;
}

.filters input {
  min-width: 200px;
}

.loading,
.error {
  padding: 20px;
  text-align: center;
  font-size: 16px;
}

.error {
  color: #dc3545;
}

.jobs-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  border-radius: 4px;
  overflow: hidden;
}

.jobs-table thead {
  background: #f8f9fa;
}

.jobs-table th {
  padding: 12px;
  text-align: left;
  font-weight: 600;
  font-size: 14px;
  color: #495057;
  border-bottom: 2px solid #dee2e6;
}

.jobs-table td {
  padding: 12px;
  border-bottom: 1px solid #dee2e6;
  font-size: 14px;
}

.jobs-table tbody tr:hover {
  background: #f8f9fa;
}

.id-cell {
  font-family: monospace;
  font-size: 12px;
  color: #6c757d;
}

.status-badge {
  padding: 4px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  text-transform: capitalize;
}

.status-queued {
  background: #ffc107;
  color: #000;
}

.status-running {
  background: #17a2b8;
  color: white;
}

.status-succeeded {
  background: #28a745;
  color: white;
}

.status-failed {
  background: #dc3545;
  color: white;
}

.status-cancelled {
  background: #6c757d;
  color: white;
}

.job-type-badge {
  padding: 4px 8px;
  background: #e9ecef;
  border-radius: 4px;
  font-size: 12px;
  text-transform: capitalize;
}

.btn-link {
  color: #007bff;
  text-decoration: none;
  margin-right: 10px;
  font-size: 14px;
}

.btn-link:hover {
  text-decoration: underline;
}

.btn-cancel-small {
  padding: 4px 8px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.btn-cancel-small:hover:not(:disabled) {
  background: #c82333;
}

.empty {
  padding: 40px;
  text-align: center;
  color: #6c757d;
  font-size: 16px;
}
</style>

