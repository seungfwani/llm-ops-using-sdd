<template>
  <section class="pipeline-list">
    <header>
      <h1>Workflow Pipelines</h1>
      <div class="header-actions">
        <button @click="fetchPipelines" :disabled="loading" class="btn-secondary">Refresh</button>
        <router-link to="/workflows/pipelines/create" class="btn-primary">New Pipeline</router-link>
      </div>
    </header>

    <div class="filters">
      <label>
        Status:
        <select v-model="filters.status" @change="fetchPipelines">
          <option value="">All</option>
          <option value="pending">Pending</option>
          <option value="running">Running</option>
          <option value="succeeded">Succeeded</option>
          <option value="failed">Failed</option>
          <option value="cancelled">Cancelled</option>
        </select>
      </label>
      <label>
        Orchestration System:
        <select v-model="filters.orchestration_system" @change="fetchPipelines">
          <option value="">All</option>
          <option value="argo_workflows">Argo Workflows</option>
        </select>
      </label>
    </div>

    <div v-if="loading" class="loading">Loading pipelines...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="pipelines.length" class="pipelines-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Orchestration System</th>
          <th>Status</th>
          <th>Current Stage</th>
          <th>Stages</th>
          <th>Started</th>
          <th>Completed</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="pipeline in pipelines" :key="pipeline.id">
          <td class="name-cell">{{ pipeline.pipeline_name }}</td>
          <td>
            <span class="system-badge">{{ pipeline.orchestration_system }}</span>
          </td>
          <td>
            <span :class="`status-badge status-${pipeline.status}`">
              {{ pipeline.status }}
            </span>
          </td>
          <td>{{ pipeline.current_stage || "-" }}</td>
          <td>{{ pipeline.stages.length }}</td>
          <td>{{ pipeline.start_time ? formatDate(pipeline.start_time) : "-" }}</td>
          <td>{{ pipeline.end_time ? formatDate(pipeline.end_time) : "-" }}</td>
          <td>
            <router-link :to="`/workflows/pipelines/${pipeline.id}`" class="btn-link">View</router-link>
            <button
              v-if="canCancel(pipeline.status)"
              @click="handleCancel(pipeline.id)"
              class="btn-cancel-small"
              :disabled="cancellingIds.has(pipeline.id)"
            >
              {{ cancellingIds.has(pipeline.id) ? "Cancelling..." : "Cancel" }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No pipelines found.</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive } from "vue";
import {
  workflowClient,
  type WorkflowPipeline,
} from "@/services/workflowClient";

const pipelines = ref<WorkflowPipeline[]>([]);
const loading = ref(false);
const error = ref("");
const cancellingIds = ref<Set<string>>(new Set());

const filters = reactive({
  status: "",
  orchestration_system: "",
});

onMounted(() => {
  fetchPipelines();
});

async function fetchPipelines() {
  loading.value = true;
  error.value = "";
  try {
    const response = await workflowClient.listPipelines({
      status: filters.status || undefined,
      orchestration_system: filters.orchestration_system || undefined,
    });
    if (response.status === "success" && response.data) {
      pipelines.value = response.data;
    } else {
      error.value = response.message || "Failed to fetch pipelines";
      pipelines.value = [];
    }
  } catch (e) {
    error.value = `Error: ${e}`;
    pipelines.value = [];
  } finally {
    loading.value = false;
  }
}

function canCancel(status: string): boolean {
  return status === "pending" || status === "running";
}

async function handleCancel(pipelineId: string) {
  if (!confirm("Are you sure you want to cancel this pipeline?")) {
    return;
  }
  cancellingIds.value.add(pipelineId);
  try {
    const response = await workflowClient.cancelPipeline(pipelineId);
    if (response.status === "success") {
      await fetchPipelines();
    } else {
      alert(`Failed to cancel pipeline: ${response.message}`);
    }
  } catch (e) {
    alert(`Error cancelling pipeline: ${e}`);
  } finally {
    cancellingIds.value.delete(pipelineId);
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}
</script>

<style scoped>
.pipeline-list {
  padding: 20px;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.btn-primary {
  padding: 8px 16px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  text-decoration: none;
}

.btn-primary:hover {
  background: #0056b3;
}

.btn-secondary {
  padding: 8px 16px;
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

.filters {
  display: flex;
  gap: 20px;
  margin-bottom: 20px;
  padding: 15px;
  background: #f5f5f5;
  border-radius: 4px;
}

.filters label {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.pipelines-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
}

.pipelines-table th,
.pipelines-table td {
  padding: 12px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}

.pipelines-table th {
  background: #f8f9fa;
  font-weight: 600;
}

.name-cell {
  font-weight: 500;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  text-transform: capitalize;
}

.status-pending {
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

.system-badge {
  padding: 4px 8px;
  background: #e7f3ff;
  color: #0194e2;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.btn-link {
  color: #007bff;
  text-decoration: none;
  margin-right: 10px;
}

.btn-link:hover {
  text-decoration: underline;
}

.btn-cancel-small {
  padding: 4px 12px;
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

.btn-cancel-small:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading,
.error,
.empty {
  padding: 40px;
  text-align: center;
}

.error {
  color: #dc3545;
}
</style>

