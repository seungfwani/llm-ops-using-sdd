<template>
  <div class="job-detail">
    <header>
      <div class="header-left">
        <router-link to="/training/jobs" class="back-link">← Back to Jobs</router-link>
        <h1>Training Job: {{ jobId.substring(0, 8) }}...</h1>
      </div>
      <div class="header-actions">
        <button @click="refreshJob" :disabled="loading">Refresh</button>
        <button v-if="canResubmit" @click="showResubmitModal = true" class="btn-resubmit" :disabled="loading">
          Resubmit with New Resources
        </button>
        <button v-if="canCancel" @click="cancelJob" class="btn-cancel" :disabled="cancelling">
          {{ cancelling ? "Cancelling..." : "Cancel Job" }}
        </button>
      </div>
    </header>

    <div v-if="loading" class="loading">Loading job details...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="job" class="job-content">
      <div class="job-info-card">
        <h2>Job Information</h2>
        <div class="info-grid">
          <div class="info-item">
            <label>Status:</label>
            <span :class="`status-badge status-${job.status}`">
              {{ job.status }}
            </span>
          </div>
          <div class="info-item">
            <label>Job Type:</label>
            <span class="job-type-badge">{{ job.jobType }}</span>
          </div>
          <div class="info-item">
            <label>Model ID:</label>
            <span class="id-value">{{ job.modelId }}</span>
          </div>
          <div class="info-item">
            <label>Dataset ID:</label>
            <span class="id-value">{{ job.datasetId }}</span>
          </div>
          <div class="info-item">
            <label>Job ID:</label>
            <span class="id-value">{{ job.id }}</span>
          </div>
        </div>
      </div>

      <div v-if="job.resourceProfile" class="job-resources-card">
        <h2>Resource Configuration</h2>
        <div class="info-grid">
          <div v-if="job.resourceProfile.gpuCount" class="info-item">
            <label>GPU Count:</label>
            <span>{{ job.resourceProfile.gpuCount }}</span>
          </div>
          <div v-if="job.resourceProfile.gpuType" class="info-item">
            <label>GPU Type:</label>
            <span>{{ job.resourceProfile.gpuType }}</span>
          </div>
          <div v-if="job.resourceProfile.numNodes" class="info-item">
            <label>Number of Nodes:</label>
            <span>{{ job.resourceProfile.numNodes }}</span>
          </div>
          <div v-if="job.resourceProfile.cpuCores" class="info-item">
            <label>CPU Cores:</label>
            <span>{{ job.resourceProfile.cpuCores }}</span>
          </div>
          <div v-if="job.resourceProfile.memory" class="info-item">
            <label>Memory:</label>
            <span>{{ job.resourceProfile.memory }}</span>
          </div>
          <div v-if="job.resourceProfile.maxDuration" class="info-item">
            <label>Max Duration:</label>
            <span>{{ job.resourceProfile.maxDuration }} minutes</span>
          </div>
        </div>
      </div>

      <div class="job-timeline-card">
        <h2>Timeline</h2>
        <div class="timeline">
          <div class="timeline-item">
            <div class="timeline-marker completed"></div>
            <div class="timeline-content">
              <strong>Submitted</strong>
              <span>{{ formatDate(job.submittedAt) }}</span>
            </div>
          </div>
          <div v-if="job.startedAt" class="timeline-item">
            <div class="timeline-marker completed"></div>
            <div class="timeline-content">
              <strong>Started</strong>
              <span>{{ formatDate(job.startedAt) }}</span>
            </div>
          </div>
          <div v-else class="timeline-item">
            <div class="timeline-marker pending"></div>
            <div class="timeline-content">
              <strong>Started</strong>
              <span>Pending...</span>
            </div>
          </div>
          <div v-if="job.completedAt" class="timeline-item">
            <div class="timeline-marker completed"></div>
            <div class="timeline-content">
              <strong>Completed</strong>
              <span>{{ formatDate(job.completedAt) }}</span>
            </div>
          </div>
          <div v-else class="timeline-item">
            <div class="timeline-marker pending"></div>
            <div class="timeline-content">
              <strong>Completed</strong>
              <span>In progress...</span>
            </div>
          </div>
        </div>
      </div>

      <div v-if="job.outputModelEntryId" class="job-output-model-card">
        <h2>Output Model</h2>
        <div class="info-grid">
          <div class="info-item">
            <label>Model Entry ID:</label>
            <router-link :to="`/catalog/models/${job.outputModelEntryId}`" class="id-value link">
              {{ job.outputModelEntryId }}
            </router-link>
          </div>
          <div v-if="job.outputModelStorageUri" class="info-item">
            <label>Storage URI:</label>
            <span class="id-value">{{ job.outputModelStorageUri }}</span>
          </div>
        </div>
      </div>

      <div class="job-actions-card">
        <h2>Actions</h2>
        <div class="actions">
          <router-link v-if="job.experimentUrl" :to="job.experimentUrl" class="btn-experiment">
            View Experiment →
          </router-link>
          <button v-if="canRegisterModel" @click="showRegisterModelModal = true" class="btn-register" :disabled="loading">
            Register Model
          </button>
          <button @click="refreshJob" :disabled="loading" class="btn-secondary">
            Refresh Job
          </button>
          <button v-if="canResubmit" @click="showResubmitModal = true" class="btn-resubmit" :disabled="loading">
            Resubmit Job
          </button>
          <button v-if="canCancel" @click="cancelJob" class="btn-cancel" :disabled="cancelling">
            {{ cancelling ? "Cancelling..." : "Cancel Job" }}
          </button>
        </div>
      </div>
    </div>

    <!-- Resubmit Modal -->
    <div v-if="showResubmitModal" class="modal-overlay" @click.self="showResubmitModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h2>Resubmit Job with Updated Resources</h2>
          <button @click="showResubmitModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label>
              <input
                type="checkbox"
                v-model="resubmitForm.useGpu"
                @change="onUseGpuChange"
              />
              Use GPU Resources
            </label>
          </div>

          <template v-if="resubmitForm.useGpu">
            <div class="form-group">
              <label for="resubmit-gpuCount">GPU Count: <span class="required">*</span></label>
              <input
                id="resubmit-gpuCount"
                v-model.number="resubmitForm.resourceProfile.gpuCount"
                type="number"
                min="1"
                required
              />
            </div>

            <div v-if="job.jobType === 'distributed'" class="form-group">
              <label for="resubmit-numNodes">Number of Nodes: <span class="required">*</span></label>
              <input
                id="resubmit-numNodes"
                v-model.number="resubmitForm.resourceProfile.numNodes"
                type="number"
                min="2"
                required
              />
            </div>

            <div class="form-group">
              <label for="resubmit-gpuType">GPU Type: <span class="required">*</span></label>
              <select id="resubmit-gpuType" v-model="resubmitForm.resourceProfile.gpuType" required>
                <option value="nvidia-tesla-v100">NVIDIA Tesla V100</option>
                <option value="nvidia-tesla-a100">NVIDIA Tesla A100</option>
                <option value="nvidia-rtx-3090">NVIDIA RTX 3090</option>
                <option value="nvidia-rtx-4090">NVIDIA RTX 4090</option>
              </select>
            </div>
          </template>

          <template v-else>
            <div class="form-group">
              <label for="resubmit-cpuCores">CPU Cores: <span class="required">*</span></label>
              <input
                id="resubmit-cpuCores"
                v-model.number="resubmitForm.resourceProfile.cpuCores"
                type="number"
                min="1"
                required
              />
            </div>

            <div class="form-group">
              <label for="resubmit-memory">Memory: <span class="required">*</span></label>
              <select id="resubmit-memory" v-model="resubmitForm.resourceProfile.memory" required>
                <option value="2Gi">2 GiB</option>
                <option value="4Gi">4 GiB</option>
                <option value="8Gi">8 GiB</option>
                <option value="16Gi">16 GiB</option>
                <option value="32Gi">32 GiB</option>
              </select>
            </div>
          </template>

          <div class="form-group">
            <label for="resubmit-maxDuration">Max Duration (minutes): <span class="required">*</span></label>
            <input
              id="resubmit-maxDuration"
              v-model.number="resubmitForm.resourceProfile.maxDuration"
              type="number"
              min="1"
              required
            />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showResubmitModal = false" class="btn-secondary">Cancel</button>
          <button @click="handleResubmit" class="btn-primary" :disabled="resubmitting">
            {{ resubmitting ? "Resubmitting..." : "Resubmit Job" }}
          </button>
        </div>
      </div>
    </div>

    <!-- Register Model Modal -->
    <div v-if="showRegisterModelModal" class="modal-overlay" @click.self="showRegisterModelModal = false">
      <div class="modal-content">
        <div class="modal-header">
          <h2>Register Output Model</h2>
          <button @click="showRegisterModelModal = false" class="modal-close">×</button>
        </div>
        <div class="modal-body">
          <div class="form-group">
            <label for="register-modelName">Model Name: <span class="required">*</span></label>
            <input
              id="register-modelName"
              v-model="registerModelForm.modelName"
              type="text"
              required
              placeholder="e.g., my-finetuned-model"
            />
          </div>

          <div class="form-group">
            <label for="register-modelVersion">Model Version: <span class="required">*</span></label>
            <input
              id="register-modelVersion"
              v-model="registerModelForm.modelVersion"
              type="text"
              required
              placeholder="e.g., 1.0"
            />
          </div>

          <div class="form-group">
            <label for="register-storageUri">Storage URI: <span class="optional">(Optional)</span></label>
            <input
              id="register-storageUri"
              v-model="registerModelForm.storageUri"
              type="text"
              placeholder="Auto-generated if not provided (e.g., s3://models/my-model/1.0/)"
            />
            <small class="help-text">Storage URI where the trained model artifacts are stored. If not provided, will be auto-generated based on model name and version.</small>
          </div>

          <div class="form-group">
            <label for="register-ownerTeam">Owner Team:</label>
            <input
              id="register-ownerTeam"
              v-model="registerModelForm.ownerTeam"
              type="text"
              placeholder="ml-platform"
            />
          </div>
        </div>
        <div class="modal-footer">
          <button @click="showRegisterModelModal = false" class="btn-secondary">Cancel</button>
          <button @click="handleRegisterModel" class="btn-primary" :disabled="registering">
            {{ registering ? "Registering..." : "Register Model" }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from "vue";
import { useRoute } from "vue-router";
import { trainingClient, type TrainingJob } from "@/services/trainingClient";

const route = useRoute();
const jobId = route.params.id as string;

const job = ref<TrainingJob | null>(null);
const loading = ref(true);
const error = ref("");
const cancelling = ref(false);
const resubmitting = ref(false);
const registering = ref(false);
const showResubmitModal = ref(false);
const showRegisterModelModal = ref(false);
let pollInterval: ReturnType<typeof setInterval> | null = null;

const registerModelForm = ref({
  modelName: "",
  modelVersion: "1.0",
  storageUri: "",
  ownerTeam: "ml-platform",
});

const resubmitForm = ref({
  useGpu: true,
  resourceProfile: {
    gpuCount: 1,
    gpuType: "nvidia-tesla-v100",
    numNodes: 2,
    cpuCores: 4,
    memory: "8Gi",
    maxDuration: 60,
  },
});

const canCancel = computed(() => {
  return job.value && ["queued", "running"].includes(job.value.status);
});

const canResubmit = computed(() => {
  // Can resubmit if job is failed, cancelled, or pending (queued/running but stuck)
  return job.value && ["failed", "cancelled", "queued", "running"].includes(job.value.status);
});

const canRegisterModel = computed(() => {
  // Can register model if job succeeded and model not already registered
  return job.value && job.value.status === "succeeded" && !job.value.outputModelEntryId;
});

const refreshJob = async () => {
  await loadJob();
};

onMounted(async () => {
  await loadJob();
  // Auto-polling disabled - user can manually refresh using the Refresh button
  // startPolling();
});

onUnmounted(() => {
  stopPolling();
});

function startPolling() {
  if (job.value && ["queued", "running"].includes(job.value.status)) {
    pollInterval = setInterval(async () => {
      await loadJob();
      if (job.value && ["succeeded", "failed", "cancelled"].includes(job.value.status)) {
        stopPolling();
      }
    }, 5000);
  }
}

function stopPolling() {
  if (pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

async function loadJob() {
  loading.value = true;
  error.value = "";
  try {
    const response = await trainingClient.getJob(jobId);
    if (response.status === "success" && response.data) {
      job.value = response.data;
      // Initialize resubmit form with current resource profile if available
      if (job.value.resourceProfile) {
        const rp = job.value.resourceProfile;
        resubmitForm.value.useGpu = !!(rp.gpuCount || rp.gpuType);
        if (resubmitForm.value.useGpu) {
          resubmitForm.value.resourceProfile.gpuCount = rp.gpuCount || 1;
          resubmitForm.value.resourceProfile.gpuType = rp.gpuType || "nvidia-tesla-v100";
          // Only set numNodes for distributed jobs
          if (job.value.jobType === "distributed") {
            resubmitForm.value.resourceProfile.numNodes = rp.numNodes || 2;
          } else {
            resubmitForm.value.resourceProfile.numNodes = undefined;
          }
        } else {
          resubmitForm.value.resourceProfile.cpuCores = rp.cpuCores || 4;
          resubmitForm.value.resourceProfile.memory = rp.memory || "8Gi";
          resubmitForm.value.resourceProfile.numNodes = undefined;
        }
        resubmitForm.value.resourceProfile.maxDuration = rp.maxDuration || 60;
      }
      // Auto-polling disabled - user can manually refresh
      // if (["queued", "running"].includes(job.value.status) && !pollInterval) {
      //   startPolling();
      // }
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
  if (!job.value || cancelling.value) return;
  cancelling.value = true;
  try {
    const response = await trainingClient.cancelJob(jobId);
    if (response.status === "success") {
      await loadJob();
    } else {
      error.value = response.message || "Failed to cancel job";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    cancelling.value = false;
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}

function onUseGpuChange() {
  // Reset resource profile fields when switching between GPU/CPU
  if (resubmitForm.value.useGpu) {
    // Switching to GPU - ensure GPU fields are set
    if (!resubmitForm.value.resourceProfile.gpuCount) resubmitForm.value.resourceProfile.gpuCount = 1;
    if (!resubmitForm.value.resourceProfile.gpuType) resubmitForm.value.resourceProfile.gpuType = "nvidia-tesla-v100";
    // Only set numNodes for distributed jobs
    if (job.value?.jobType === "distributed") {
      if (!resubmitForm.value.resourceProfile.numNodes) resubmitForm.value.resourceProfile.numNodes = 2;
    } else {
      resubmitForm.value.resourceProfile.numNodes = undefined;
    }
  } else {
    // Switching to CPU-only - ensure CPU fields are set
    if (!resubmitForm.value.resourceProfile.cpuCores) resubmitForm.value.resourceProfile.cpuCores = 4;
    if (!resubmitForm.value.resourceProfile.memory) resubmitForm.value.resourceProfile.memory = "8Gi";
    resubmitForm.value.resourceProfile.numNodes = undefined;
  }
}

async function handleResubmit() {
  if (!job.value || resubmitting.value) return;
  
  resubmitting.value = true;
  try {
    const response = await trainingClient.resubmitJob(
      jobId,
      resubmitForm.value.resourceProfile,
      resubmitForm.value.useGpu
    );
    
    if (response.status === "success" && response.data) {
      alert("Job resubmitted successfully! Redirecting to new job...");
      showResubmitModal.value = false;
      // Redirect to new job
      if (response.data.id) {
        window.location.href = `/training/jobs/${response.data.id}`;
      } else {
        await loadJob();
      }
    } else {
      error.value = response.message || "Failed to resubmit job";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    resubmitting.value = false;
  }
}

async function handleRegisterModel() {
  if (!job.value || registering.value) return;
  
  if (!registerModelForm.value.modelName) {
    error.value = "Model name is required";
    return;
  }
  
  registering.value = true;
  error.value = ""; // Clear previous errors
  try {
    console.log("Registering model for job:", jobId);
    console.log("Form data:", registerModelForm.value);
    
    const response = await trainingClient.registerModel(jobId, {
      modelName: registerModelForm.value.modelName,
      modelVersion: registerModelForm.value.modelVersion,
      storageUri: registerModelForm.value.storageUri || undefined, // Send undefined if empty
      ownerTeam: registerModelForm.value.ownerTeam,
    });
    
    console.log("Register model response:", response);
    
    if (response.status === "success" && response.data) {
      alert("Model registered successfully! Redirecting to model catalog...");
      showRegisterModelModal.value = false;
      await loadJob();
      // Redirect to model catalog if model entry ID is available
      if (response.data.outputModelEntryId) {
        setTimeout(() => {
          window.location.href = `/catalog/models/${response.data!.outputModelEntryId}`;
        }, 1000);
      }
    } else {
      const errorMsg = response.message || "Failed to register model";
      console.error("Failed to register model:", errorMsg);
      error.value = errorMsg;
    }
  } catch (e) {
    console.error("Error registering model:", e);
    error.value = `Error: ${e}`;
  } finally {
    registering.value = false;
  }
}
</script>

<style scoped>
.job-detail {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #e9ecef;
}

.header-left {
  flex: 1;
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

.header-actions {
  display: flex;
  gap: 10px;
}

button {
  padding: 10px 20px;
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

.btn-cancel {
  background: #dc3545;
}

.btn-cancel:hover:not(:disabled) {
  background: #c82333;
}

.btn-resubmit {
  background: #28a745;
}

.btn-resubmit:hover:not(:disabled) {
  background: #218838;
}

.btn-register {
  background: #007bff;
  color: white;
}

.btn-register:hover:not(:disabled) {
  background: #0056b3;
}

.link {
  color: #007bff;
  text-decoration: none;
}

.link:hover {
  text-decoration: underline;
}

.help-text {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #6c757d;
}

.loading,
.error {
  padding: 40px;
  text-align: center;
  font-size: 16px;
}

.error {
  color: #dc3545;
}

.job-content {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

.job-info-card,
.job-timeline-card,
.job-actions-card,
.job-resources-card,
.job-output-model-card {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.job-actions-card {
  grid-column: 1 / -1;
}

.actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

h2 {
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  color: #495057;
}

.info-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 15px;
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.info-item label {
  font-size: 12px;
  font-weight: 500;
  color: #6c757d;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.id-value {
  font-family: monospace;
  font-size: 13px;
  color: #495057;
  word-break: break-all;
}

.status-badge {
  display: inline-block;
  padding: 6px 12px;
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
  display: inline-block;
  padding: 6px 12px;
  background: #e9ecef;
  border-radius: 4px;
  font-size: 13px;
  text-transform: capitalize;
  color: #495057;
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
  top: 2px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 2px solid #e9ecef;
  background: white;
}

.timeline-marker.completed {
  background: #28a745;
  border-color: #28a745;
}

.timeline-marker.pending {
  background: #ffc107;
  border-color: #ffc107;
}

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.timeline-content strong {
  font-size: 14px;
  color: #495057;
}

.timeline-content span {
  font-size: 13px;
  color: #6c757d;
}

.btn-experiment {
  display: inline-block;
  padding: 12px 24px;
  background: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-experiment:hover {
  background: #0056b3;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-content {
  background: white;
  border-radius: 8px;
  width: 90%;
  max-width: 600px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e9ecef;
}

.modal-header h2 {
  margin: 0;
  font-size: 20px;
}

.modal-close {
  background: none;
  border: none;
  font-size: 28px;
  cursor: pointer;
  color: #6c757d;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-close:hover {
  color: #495057;
}

.modal-body {
  padding: 20px;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 20px;
  border-top: 1px solid #e9ecef;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 5px;
  font-weight: 500;
  color: #495057;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.form-group input[type="checkbox"] {
  width: auto;
  margin-right: 8px;
}

.required {
  color: #dc3545;
}

.optional {
  color: #6c757d;
  font-weight: normal;
  font-size: 12px;
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

.btn-secondary:hover {
  background: #5a6268;
}

@media (max-width: 768px) {
  .job-content {
    grid-template-columns: 1fr;
  }

  header {
    flex-direction: column;
    gap: 15px;
  }

  .info-grid {
    grid-template-columns: 1fr;
  }

  .modal-content {
    width: 95%;
    margin: 20px;
  }
}
</style>

