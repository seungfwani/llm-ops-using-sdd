<template>
  <div class="pipeline-detail">
    <header>
      <div class="header-left">
        <h1>Pipeline: {{ pipeline?.pipeline_name || pipelineId.substring(0, 8) + "..." }}</h1>
      </div>
      <div class="header-actions">
        <button @click="refreshPipeline" :disabled="loading">Refresh</button>
        <a
          v-if="argoUIUrl"
          :href="argoUIUrl"
          target="_blank"
          rel="noopener noreferrer"
          class="btn-argo"
        >
          Open in Argo UI →
        </a>
        <button
          v-if="canCancel"
          @click="cancelPipeline"
          class="btn-cancel"
          :disabled="cancelling"
        >
          {{ cancelling ? "Cancelling..." : "Cancel Pipeline" }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading">Loading pipeline details...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="pipeline" class="pipeline-content">
      <div class="pipeline-info-card">
        <h2>Pipeline Information</h2>
        <div class="info-grid">
          <div class="info-item">
            <label>Status:</label>
            <span :class="`status-badge status-${pipeline.status}`">
              {{ pipeline.status }}
            </span>
          </div>
          <div class="info-item">
            <label>Orchestration System:</label>
            <span class="system-badge">{{ pipeline.orchestration_system }}</span>
          </div>
          <div class="info-item">
            <label>Workflow ID:</label>
            <span class="id-value">{{ pipeline.workflow_id || "N/A" }}</span>
          </div>
          <div class="info-item">
            <label>Namespace:</label>
            <span>{{ pipeline.workflow_namespace }}</span>
          </div>
          <div class="info-item">
            <label>Current Stage:</label>
            <span>{{ pipeline.current_stage || "N/A" }}</span>
          </div>
          <div class="info-item">
            <label>Retry Count:</label>
            <span>{{ pipeline.retry_count }} / {{ pipeline.max_retries }}</span>
          </div>
          <div class="info-item">
            <label>Started:</label>
            <span>{{ pipeline.start_time ? formatDate(pipeline.start_time) : "N/A" }}</span>
          </div>
          <div class="info-item">
            <label>Completed:</label>
            <span>{{ pipeline.end_time ? formatDate(pipeline.end_time) : "N/A" }}</span>
          </div>
        </div>
      </div>

      <div class="pipeline-stages-card">
        <h2>Pipeline Stages</h2>
        <div class="stages-list">
          <div
            v-for="(stage, index) in pipeline.stages"
            :key="index"
            class="stage-item"
            :class="{ active: stage.name === pipeline.current_stage }"
          >
            <div class="stage-number">{{ index + 1 }}</div>
            <div class="stage-info">
              <h3>{{ stage.name }}</h3>
              <div class="stage-meta">
                <span class="stage-type">{{ stage.type }}</span>
                <span v-if="stage.dependencies && stage.dependencies.length > 0" class="stage-deps">
                  Depends on: {{ stage.dependencies.join(", ") }}
                </span>
              </div>
            </div>
            <div v-if="stage.phase" class="stage-status">
              <span :class="`phase-badge phase-${stage.phase.toLowerCase()}`">
                {{ stage.phase }}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div class="pipeline-timeline-card">
        <h2>Timeline</h2>
        <div class="timeline">
          <div class="timeline-item">
            <div class="timeline-marker"></div>
            <div class="timeline-content">
              <strong>Created</strong>
              <span>{{ formatDate(pipeline.created_at) }}</span>
            </div>
          </div>
          <div v-if="pipeline.start_time" class="timeline-item">
            <div class="timeline-marker"></div>
            <div class="timeline-content">
              <strong>Started</strong>
              <span>{{ formatDate(pipeline.start_time) }}</span>
            </div>
          </div>
          <div v-if="pipeline.end_time" class="timeline-item">
            <div class="timeline-marker"></div>
            <div class="timeline-content">
              <strong>{{ pipeline.status === "succeeded" ? "Completed" : "Ended" }}</strong>
              <span>{{ formatDate(pipeline.end_time) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  workflowClient,
  type WorkflowPipeline,
} from "@/services/workflowClient";

const route = useRoute();
const router = useRouter();
const pipelineId = route.params.id as string;

const pipeline = ref<WorkflowPipeline | null>(null);
const loading = ref(false);
const error = ref("");
const cancelling = ref(false);

const argoUIUrl = computed(() => {
  if (!pipeline.value) return null;
  return workflowClient.getArgoUIUrl(pipeline.value);
});

const canCancel = computed(() => {
  return pipeline.value?.status === "pending" || pipeline.value?.status === "running";
});

onMounted(() => {
  fetchPipeline();
  // Auto-refresh every 10 seconds if pipeline is running
  const interval = setInterval(() => {
    if (pipeline.value && (pipeline.value.status === "pending" || pipeline.value.status === "running")) {
      fetchPipeline(true);
    }
  }, 10000);
  
  return () => clearInterval(interval);
});

async function fetchPipeline(updateStatus: boolean = false) {
  loading.value = true;
  error.value = "";
  try {
    const response = await workflowClient.getPipeline(pipelineId, updateStatus);
    if (response.status === "success" && response.data) {
      pipeline.value = response.data;
    } else {
      error.value = response.message || "Failed to fetch pipeline";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    loading.value = false;
  }
}

async function refreshPipeline() {
  await fetchPipeline(true);
}

async function cancelPipeline() {
  if (!confirm("Are you sure you want to cancel this pipeline?")) {
    return;
  }
  cancelling.value = true;
  try {
    const response = await workflowClient.cancelPipeline(pipelineId);
    if (response.status === "success") {
      await fetchPipeline(true);
    } else {
      alert(`Failed to cancel pipeline: ${response.message}`);
    }
  } catch (e) {
    alert(`Error cancelling pipeline: ${e}`);
  } finally {
    cancelling.value = false;
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}
</script>

<style scoped>
.pipeline-detail {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 30px;
}

.header-left {
  flex: 1;
}

.back-link {
  color: #007bff;
  text-decoration: none;
  margin-bottom: 10px;
  display: inline-block;
}

.back-link:hover {
  text-decoration: underline;
}

.header-actions {
  display: flex;
  gap: 10px;
}

.pipeline-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.pipeline-info-card,
.pipeline-stages-card,
.pipeline-timeline-card {
  background: white;
  padding: 20px;
  border-radius: 8px;
  border: 1px solid #e9ecef;
}

.pipeline-info-card h2,
.pipeline-stages-card h2,
.pipeline-timeline-card h2 {
  margin-top: 0;
  margin-bottom: 20px;
  color: #495057;
}

.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 15px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.info-item label {
  font-weight: 500;
  color: #6c757d;
  font-size: 12px;
  text-transform: uppercase;
}

.id-value {
  font-family: monospace;
  font-size: 12px;
  color: #495057;
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

.stages-list {
  display: flex;
  flex-direction: column;
  gap: 15px;
}

.stage-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 15px;
  border: 2px solid #e9ecef;
  border-radius: 8px;
  background: #f8f9fa;
}

.stage-item.active {
  border-color: #17a2b8;
  background: #e7f3ff;
}

.stage-number {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: #007bff;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  flex-shrink: 0;
}

.stage-info {
  flex: 1;
}

.stage-info h3 {
  margin: 0 0 5px 0;
  color: #495057;
}

.stage-meta {
  display: flex;
  gap: 15px;
  font-size: 12px;
  color: #6c757d;
}

.stage-type {
  padding: 2px 8px;
  background: #e9ecef;
  border-radius: 4px;
}

.stage-deps {
  font-style: italic;
}

.phase-badge {
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.phase-running {
  background: #17a2b8;
  color: white;
}

.phase-succeeded {
  background: #28a745;
  color: white;
}

.phase-failed {
  background: #dc3545;
  color: white;
}

.timeline {
  position: relative;
  padding-left: 30px;
}

.timeline::before {
  content: "";
  position: absolute;
  left: 10px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #e9ecef;
}

.timeline-item {
  position: relative;
  margin-bottom: 20px;
}

.timeline-marker {
  position: absolute;
  left: -25px;
  top: 5px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #007bff;
  border: 2px solid white;
}

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.timeline-content strong {
  color: #495057;
}

.timeline-content span {
  color: #6c757d;
  font-size: 14px;
}

.btn-argo {
  padding: 8px 16px;
  background: #0194e2;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 14px;
}

.btn-argo:hover {
  background: #0178b8;
}

.btn-cancel {
  padding: 8px 16px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-cancel:hover:not(:disabled) {
  background: #c82333;
}

.btn-cancel:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.loading,
.error {
  padding: 40px;
  text-align: center;
}

.error {
  color: #dc3545;
}
</style>

