<template>
  <div class="pipeline-create">
    <header>
      <h1>Create Workflow Pipeline</h1>
    </header>

    <form @submit.prevent="submitPipeline">
      <div class="form-section">
        <h2>Pipeline Configuration</h2>
        
        <div class="form-group">
          <label for="pipelineName">Pipeline Name: <span class="required">*</span></label>
          <input
            id="pipelineName"
            v-model="form.pipeline_name"
            type="text"
            required
            placeholder="e.g., Model Training Pipeline"
          />
        </div>

        <div class="form-group">
          <label for="orchestrationSystem">Orchestration System:</label>
          <select id="orchestrationSystem" v-model="form.orchestration_system">
            <option value="argo_workflows">Argo Workflows</option>
          </select>
        </div>

        <div class="form-group">
          <label for="maxRetries">Max Retries:</label>
          <input
            id="maxRetries"
            v-model.number="form.max_retries"
            type="number"
            min="0"
            max="10"
            default="3"
          />
          <small class="help-text">Maximum number of retry attempts (0-10)</small>
        </div>
      </div>

      <div class="form-section">
        <h2>Pipeline Stages</h2>
        <div class="stages-container">
          <div
            v-for="(stage, index) in form.stages"
            :key="index"
            class="stage-card"
          >
            <div class="stage-header">
              <h3>Stage {{ index + 1 }}: {{ stage.name || "Unnamed" }}</h3>
              <button
                type="button"
                @click="removeStage(index)"
                class="btn-remove"
                :disabled="form.stages.length <= 1"
              >
                Remove
              </button>
            </div>
            
            <div class="stage-form">
              <div class="form-group">
                <label :for="`stage-name-${index}`">Stage Name: <span class="required">*</span></label>
                <input
                  :id="`stage-name-${index}`"
                  v-model="stage.name"
                  type="text"
                  required
                  placeholder="e.g., Data Validation"
                />
              </div>

              <div class="form-group">
                <label :for="`stage-type-${index}`">Stage Type: <span class="required">*</span></label>
                <select :id="`stage-type-${index}`" v-model="stage.type" required>
                  <option value="data_validation">Data Validation</option>
                  <option value="training">Training</option>
                  <option value="evaluation">Evaluation</option>
                  <option value="deployment">Deployment</option>
                </select>
              </div>

              <div class="form-group">
                <label :for="`stage-dependencies-${index}`">Dependencies:</label>
                <select
                  :id="`stage-dependencies-${index}`"
                  v-model="stage.dependencies"
                  multiple
                  :disabled="index === 0"
                >
                  <option
                    v-for="(prevStage, prevIndex) in form.stages.slice(0, index)"
                    :key="prevIndex"
                    :value="prevStage.name"
                  >
                    {{ prevStage.name }}
                  </option>
                </select>
                <small class="help-text">Select stages that must complete before this stage runs</small>
              </div>
            </div>
          </div>
        </div>

        <button type="button" @click="addStage" class="btn-add-stage">
          + Add Stage
        </button>
      </div>

      <div class="form-actions">
        <button type="submit" :disabled="submitting" class="btn-primary">
          {{ submitting ? "Creating..." : "Create Pipeline" }}
        </button>
        <router-link to="/workflows/pipelines" class="btn-secondary">Cancel</router-link>
      </div>
    </form>

    <div v-if="error" class="error">{{ error }}</div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import {
  workflowClient,
  type CreatePipelineRequest,
  type PipelineStage,
} from "@/services/workflowClient";

const router = useRouter();
const submitting = ref(false);
const error = ref("");

const form = reactive<CreatePipelineRequest>({
  pipeline_name: "",
  orchestration_system: "argo_workflows",
  stages: [
    {
      name: "",
      type: "data_validation",
      dependencies: [],
    },
  ],
  max_retries: 3,
});

function addStage() {
  form.stages.push({
    name: "",
    type: "training",
    dependencies: [],
  });
}

function removeStage(index: number) {
  if (form.stages.length > 1) {
    form.stages.splice(index, 1);
    // Update dependencies to remove references to deleted stage
    const deletedStageName = form.stages[index]?.name;
    form.stages.forEach((stage) => {
      if (stage.dependencies) {
        stage.dependencies = stage.dependencies.filter(
          (dep) => dep !== deletedStageName
        );
      }
    });
  }
}

async function submitPipeline() {
  submitting.value = true;
  error.value = "";

  // Validate stages
  const stageNames = form.stages.map((s) => s.name);
  if (stageNames.some((name) => !name || name.trim() === "")) {
    error.value = "All stages must have a name";
    submitting.value = false;
    return;
  }

  const uniqueNames = new Set(stageNames);
  if (uniqueNames.size !== stageNames.length) {
    error.value = "Stage names must be unique";
    submitting.value = false;
    return;
  }

  try {
    const response = await workflowClient.createPipeline(form);
    if (response.status === "success" && response.data) {
      router.push(`/workflows/pipelines/${response.data.id}`);
    } else {
      error.value = response.message || "Failed to create pipeline";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.pipeline-create {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

header {
  margin-bottom: 30px;
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

.form-section {
  background: white;
  padding: 20px;
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid #e9ecef;
}

.form-section h2 {
  margin-top: 0;
  margin-bottom: 20px;
  color: #495057;
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

.required {
  color: #dc3545;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.form-group select[multiple] {
  min-height: 100px;
}

.help-text {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #6c757d;
}

.stages-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.stage-card {
  border: 2px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  background: #f8f9fa;
}

.stage-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
}

.stage-header h3 {
  margin: 0;
  color: #495057;
}

.btn-remove {
  padding: 6px 12px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
}

.btn-remove:hover:not(:disabled) {
  background: #c82333;
}

.btn-remove:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.stage-form {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 15px;
}

.btn-add-stage {
  padding: 10px 20px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  margin-top: 15px;
}

.btn-add-stage:hover {
  background: #218838;
}

.form-actions {
  display: flex;
  gap: 10px;
  margin-top: 30px;
}

.btn-primary {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-secondary {
  padding: 10px 20px;
  background: #6c757d;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 14px;
  display: inline-block;
}

.btn-secondary:hover {
  background: #5a6268;
}

.error {
  padding: 15px;
  background: #f8d7da;
  color: #721c24;
  border-radius: 4px;
  margin-top: 20px;
}
</style>

