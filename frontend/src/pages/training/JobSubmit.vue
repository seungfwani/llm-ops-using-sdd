<template>
  <div class="job-submit">
    <header>
      <h1>Submit Training Job</h1>
    </header>

    <form @submit.prevent="submitJob">
      <div class="form-section">
        <h2>Job Configuration</h2>
        
        <div class="form-group">
          <label for="jobType">Job Type: <span class="required">*</span></label>
          <select id="jobType" v-model="form.jobType" @change="onJobTypeChange" required>
            <option value="finetune">Fine-tuning</option>
            <option value="from_scratch">From Scratch</option>
            <option value="pretrain">Pre-training</option>
            <option value="distributed">Distributed Training</option>
          </select>
          <small class="help-text">
            <span v-if="form.jobType === 'finetune'">Fine-tuning requires a base model</span>
            <span v-else-if="form.jobType === 'from_scratch'">From-scratch requires architecture configuration</span>
            <span v-else-if="form.jobType === 'pretrain'">Pre-training requires architecture configuration</span>
            <span v-else-if="form.jobType === 'distributed'">Distributed training requires multiple GPUs/nodes</span>
          </small>
        </div>

        <div v-if="requiresModel" class="form-group">
          <label for="modelId">Base Model: <span class="required">*</span></label>
          <select id="modelId" v-model="form.modelId" :required="requiresModel" :disabled="!requiresModel">
            <option value="">Select a model</option>
            <option v-for="model in models" :key="model.id" :value="model.id">
              {{ model.name }} ({{ model.version }})
            </option>
          </select>
          <small v-if="!requiresModel" class="help-text">Not required for {{ form.jobType }} jobs</small>
        </div>

        <div class="form-group">
          <label for="datasetId">Dataset: <span class="required">*</span></label>
          <select id="datasetId" v-model="form.datasetId" required>
            <option value="">Select a dataset</option>
            <option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">
              {{ dataset.name }} ({{ dataset.version }})
            </option>
          </select>
        </div>

        <div v-if="requiresArchitecture" class="form-group">
          <label for="architecture">Architecture Configuration (JSON): <span class="required">*</span></label>
          <textarea
            id="architecture"
            v-model="architectureJson"
            :required="requiresArchitecture"
            rows="8"
            placeholder='{"architecture": {"type": "transformer", "layers": 12, "hidden_size": 768, ...}, "learning_rate": 0.0001, ...}'
            @blur="validateArchitecture"
          ></textarea>
          <small class="help-text">Must include "architecture" key with model architecture definition</small>
          <div v-if="architectureError" class="error-text">{{ architectureError }}</div>
        </div>
      </div>

      <div class="form-section">
        <h2>Resource Configuration</h2>
        
        <div class="form-group">
          <label>
            <input
              type="checkbox"
              v-model="form.useGpu"
              @change="onUseGpuChange"
            />
            Use GPU Resources
          </label>
          <small class="help-text">
            Uncheck to use CPU-only training (suitable for development/testing on GPU-less servers)
          </small>
        </div>

        <template v-if="form.useGpu">
          <div class="form-group">
            <label for="gpuCount">GPU Count: <span class="required">*</span></label>
            <input
              id="gpuCount"
              v-model.number="form.resourceProfile.gpuCount"
              type="number"
              min="1"
              :required="form.useGpu"
            />
            <small class="help-text">Number of GPUs per node</small>
          </div>

          <div v-if="form.jobType === 'distributed'" class="form-group">
            <label for="numNodes">Number of Nodes: <span class="required">*</span></label>
            <input
              id="numNodes"
              v-model.number="form.resourceProfile.numNodes"
              type="number"
              min="2"
              required
            />
            <small class="help-text">Total number of nodes for distributed training (minimum 2)</small>
          </div>

          <div class="form-group">
            <label for="gpuType">GPU Type: <span class="required">*</span></label>
            <select id="gpuType" v-model="form.resourceProfile.gpuType" :required="form.useGpu">
              <option value="nvidia-tesla-v100">NVIDIA Tesla V100</option>
              <option value="nvidia-tesla-a100">NVIDIA Tesla A100</option>
              <option value="nvidia-rtx-3090">NVIDIA RTX 3090</option>
              <option value="nvidia-rtx-4090">NVIDIA RTX 4090</option>
            </select>
          </div>
        </template>

        <template v-else>
          <div class="form-group">
            <label for="cpuCores">CPU Cores: <span class="required">*</span></label>
            <input
              id="cpuCores"
              v-model.number="form.resourceProfile.cpuCores"
              type="number"
              min="1"
              :required="!form.useGpu"
            />
            <small class="help-text">Number of CPU cores to allocate</small>
          </div>

          <div class="form-group">
            <label for="memory">Memory: <span class="required">*</span></label>
            <select id="memory" v-model="form.resourceProfile.memory" :required="!form.useGpu">
              <option value="2Gi">2 GiB</option>
              <option value="4Gi">4 GiB</option>
              <option value="8Gi">8 GiB</option>
              <option value="16Gi">16 GiB</option>
              <option value="32Gi">32 GiB</option>
            </select>
            <small class="help-text">Memory allocation for CPU-only training</small>
          </div>
        </template>

        <div class="form-group">
          <label for="maxDuration">Max Duration (minutes): <span class="required">*</span></label>
          <input
            id="maxDuration"
            v-model.number="form.resourceProfile.maxDuration"
            type="number"
            min="1"
            required
          />
        </div>
      </div>

      <div class="form-section">
        <h2>Training Job Configuration</h2>
        <p class="step-intro" style="margin-bottom: 1rem; color: #666; font-size: 0.9rem;">
          아래 필드들을 입력하면 자동으로 검증되고 실험 추적 시스템에 기록됩니다.
        </p>
        
        <div class="form-group">
          <label for="modelFamily">Model Family: <span class="required">*</span></label>
          <select id="modelFamily" v-model="trainJobSpec.model_family" required>
            <option value="">Select model family</option>
            <option value="llama">Llama</option>
            <option value="mistral">Mistral</option>
            <option value="gemma">Gemma</option>
            <option value="bert">BERT</option>
          </select>
          <small class="help-text">Select the model architecture family</small>
        </div>

        <div class="form-group">
          <label for="trainJobType">Job Type (Standardized): <span class="required">*</span></label>
          <select id="trainJobType" v-model="trainJobSpec.job_type" @change="onTrainJobTypeChange" required>
            <option value="">Select job type</option>
            <option value="PRETRAIN">PRETRAIN (from scratch)</option>
            <option value="SFT">SFT (Supervised Fine-tuning)</option>
            <option value="RAG_TUNING">RAG_TUNING (RAG retriever/reader)</option>
            <option value="RLHF">RLHF (Reward Modeling + PPO)</option>
            <option value="EMBEDDING">EMBEDDING (Embedding model)</option>
          </select>
          <small class="help-text">Select the type of training job</small>
        </div>

        <div v-if="trainJobSpec.job_type && trainJobSpec.job_type !== 'PRETRAIN'" class="form-group">
          <label for="baseModelRef">Base Model Reference: <span class="required">*</span></label>
          <input
            id="baseModelRef"
            v-model="trainJobSpec.base_model_ref"
            type="text"
            :required="trainJobSpec.job_type !== 'PRETRAIN'"
            placeholder="e.g., llama-3-8b-pretrain-v1"
          />
          <small class="help-text">Required for SFT/RAG_TUNING/RLHF (reference to pretrained model)</small>
        </div>

        <div class="form-group">
          <label for="trainingMethod">Training Method: <span class="required">*</span></label>
          <select id="trainingMethod" v-model="trainJobSpec.method" required>
            <option value="full">Full (full parameter training)</option>
            <option value="lora">LoRA (Low-Rank Adaptation)</option>
            <option value="qlora">QLoRA (Quantized LoRA)</option>
          </select>
          <small class="help-text">PRETRAIN must use 'full', others allow lora/qlora/full</small>
        </div>

        <div class="form-group">
          <h3 style="margin: 1rem 0 0.5rem 0; font-size: 1rem;">Hyperparameters</h3>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
              <label for="learningRate">Learning Rate: <span class="required">*</span></label>
              <input id="learningRate" v-model.number="trainJobSpec.hyperparams.lr" type="number" step="0.0001" min="0" required />
            </div>
            <div>
              <label for="batchSize">Batch Size: <span class="required">*</span></label>
              <input id="batchSize" v-model.number="trainJobSpec.hyperparams.batch_size" type="number" min="1" required />
            </div>
            <div>
              <label for="numEpochs">Number of Epochs: <span class="required">*</span></label>
              <input id="numEpochs" v-model.number="trainJobSpec.hyperparams.num_epochs" type="number" min="1" required />
            </div>
            <div>
              <label for="maxSeqLen">Max Sequence Length: <span class="required">*</span></label>
              <input id="maxSeqLen" v-model.number="trainJobSpec.hyperparams.max_seq_len" type="number" min="1" required />
            </div>
            <div>
              <label for="precision">Precision: <span class="required">*</span></label>
              <select id="precision" v-model="trainJobSpec.hyperparams.precision" required>
                <option value="fp16">FP16</option>
                <option value="bf16">BF16</option>
              </select>
            </div>
          </div>
        </div>

        <div class="form-group">
          <h3 style="margin: 1rem 0 0.5rem 0; font-size: 1rem;">Output Configuration</h3>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem;">
            <div>
              <label for="artifactName">Artifact Name: <span class="required">*</span></label>
              <input id="artifactName" v-model="trainJobSpec.output.artifact_name" type="text" required placeholder="e.g., llama-3-8b-sft-v1" />
            </div>
            <div>
              <label for="saveFormat">Save Format: <span class="required">*</span></label>
              <select id="saveFormat" v-model="trainJobSpec.output.save_format" required>
                <option value="hf">Hugging Face</option>
                <option value="safetensors">SafeTensors</option>
              </select>
            </div>
          </div>
        </div>
      </div>

      <div class="form-section">
        <h2>Advanced Options (Legacy)</h2>
        <p class="step-intro" style="margin-bottom: 1rem; color: #666; font-size: 0.9rem;">
          기존 방식의 하이퍼파라미터 설정 (TrainJobSpec과 함께 사용 가능)
        </p>
        
        <div class="form-group">
          <label for="hyperparameters">Additional Hyperparameters (JSON):</label>
          <textarea
            id="hyperparameters"
            v-model="hyperparametersJson"
            rows="6"
            placeholder='{"batch_size": 32, "epochs": 10, ...}'
          ></textarea>
          <small class="help-text">Optional: Additional training hyperparameters (will be merged with architecture config if provided)</small>
        </div>
      </div>

      <div class="form-actions">
        <button type="button" @click="router.push('/training/jobs')" class="btn-cancel">Cancel</button>
        <button type="submit" :disabled="submitting || !isFormValid" class="btn-submit">
          {{ submitting ? "Submitting..." : "Submit Job" }}
        </button>
      </div>

      <div v-if="message" :class="['message', messageType]">{{ message }}</div>
    </form>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted, watch } from "vue";
import { useRouter } from "vue-router";
import { trainingClient, type TrainingJobRequest, type TrainJobSpec, type DatasetRef } from "@/services/trainingClient";
import { catalogClient } from "@/services/catalogClient";

const router = useRouter();

const form = reactive<TrainingJobRequest>({
  modelId: "",
  datasetId: "",
  jobType: "finetune",
  useGpu: true,
  resourceProfile: {
    gpuCount: 1,
    gpuType: "nvidia-tesla-v100",
    maxDuration: 60,
    numNodes: 2,
    cpuCores: 4,
    memory: "8Gi",
  },
});

const trainJobSpec = reactive<Partial<TrainJobSpec>>({
  job_type: undefined,
  model_family: "",
  base_model_ref: null,
  dataset_ref: {
    name: "",
    version: "",
    type: "sft_pair",
    storage_uri: "",
  } as DatasetRef,
  hyperparams: {
    lr: 0.0001,
    batch_size: 4,
    num_epochs: 3,
    max_seq_len: 4096,
    precision: "bf16",
  },
  method: "lora",
  resources: {
    gpus: 1,
    gpu_type: "A100",
    nodes: 1,
  },
  output: {
    artifact_name: "",
    save_format: "hf",
  },
  use_gpu: true,
});

const models = ref<Array<{ id: string; name: string; version: string }>>([]);
const datasets = ref<Array<{ id: string; name: string; version: string; storage_uri?: string }>>([]);
const submitting = ref(false);
const message = ref("");
const messageType = ref<"success" | "error">("success");
const architectureJson = ref("");
const hyperparametersJson = ref("");
const architectureError = ref("");

// Watch dataset selection to populate dataset_ref
watch(() => form.datasetId, async (datasetId) => {
  if (datasetId) {
    const dataset = datasets.value.find(d => d.id === datasetId);
    if (dataset) {
      trainJobSpec.dataset_ref = {
        name: dataset.name,
        version: dataset.version || "v1",
        type: trainJobSpec.dataset_ref?.type || "sft_pair",
        storage_uri: dataset.storage_uri || "",
      };
    }
  }
});

// Watch job type to set dataset type compatibility
watch(() => trainJobSpec.job_type, (jobType) => {
  if (jobType) {
    // Set compatible dataset type
    const datasetTypeMap: Record<string, "pretrain_corpus" | "sft_pair" | "rag_qa" | "rlhf_pair"> = {
      PRETRAIN: "pretrain_corpus",
      SFT: "sft_pair",
      RAG_TUNING: "rag_qa",
      RLHF: "rlhf_pair",
      EMBEDDING: "pretrain_corpus", // Flexible
    };
    if (trainJobSpec.dataset_ref) {
      trainJobSpec.dataset_ref.type = datasetTypeMap[jobType] || "sft_pair";
    }
    
    // PRETRAIN must use full method
    if (jobType === "PRETRAIN") {
      trainJobSpec.method = "full";
    }
    
    // PRETRAIN doesn't need base_model_ref
    if (jobType === "PRETRAIN") {
      trainJobSpec.base_model_ref = null;
    }
  }
});

const requiresModel = computed(() => {
  return form.jobType === "finetune";
});

const requiresArchitecture = computed(() => {
  return form.jobType === "from_scratch" || form.jobType === "pretrain";
});

const isFormValid = computed(() => {
  // Basic validation
  if (!form.datasetId) return false;
  if (requiresModel.value && !form.modelId) return false;
  if (requiresArchitecture.value) {
    if (!architectureJson.value.trim()) return false;
    if (architectureError.value) return false;
  }
  if (form.useGpu) {
    // GPU validation
    if (!form.resourceProfile.gpuCount || form.resourceProfile.gpuCount < 1) return false;
    if (!form.resourceProfile.gpuType) return false;
    if (form.jobType === "distributed" && (!form.resourceProfile.numNodes || form.resourceProfile.numNodes < 2)) {
      return false;
    }
    if (form.jobType === "distributed" && form.resourceProfile.gpuCount < 2) {
      return false;
    }
  } else {
    // CPU-only validation
    if (!form.resourceProfile.cpuCores || form.resourceProfile.cpuCores < 1) return false;
    if (!form.resourceProfile.memory) return false;
  }
  
  // TrainJobSpec validation (if provided)
  if (trainJobSpec.job_type) {
    if (!trainJobSpec.model_family) return false;
    if (trainJobSpec.job_type !== "PRETRAIN" && !trainJobSpec.base_model_ref) return false;
    if (!trainJobSpec.dataset_ref?.name || !trainJobSpec.dataset_ref?.version || !trainJobSpec.dataset_ref?.type) return false;
    if (!trainJobSpec.hyperparams?.lr || !trainJobSpec.hyperparams?.batch_size || !trainJobSpec.hyperparams?.num_epochs) return false;
    if (!trainJobSpec.method) return false;
    if (!trainJobSpec.output?.artifact_name || !trainJobSpec.output?.save_format) return false;
  }
  
  return true;
});

const onJobTypeChange = () => {
  // Reset conditional fields when job type changes
  if (!requiresModel.value) {
    form.modelId = "";
  }
  if (!requiresArchitecture.value) {
    architectureJson.value = "";
    architectureError.value = "";
  }
  // Reset numNodes for non-distributed jobs
  if (form.jobType !== "distributed") {
    form.resourceProfile.numNodes = undefined;
  } else {
    form.resourceProfile.numNodes = 2;
  }
};

const onTrainJobTypeChange = () => {
  // Reset base_model_ref for PRETRAIN
  if (trainJobSpec.job_type === "PRETRAIN") {
    trainJobSpec.base_model_ref = null;
    trainJobSpec.method = "full";
  }
};

const onUseGpuChange = () => {
  // Reset resource profile fields when switching between GPU/CPU
  if (form.useGpu) {
    // Switching to GPU - ensure GPU fields are set
    if (!form.resourceProfile.gpuCount) form.resourceProfile.gpuCount = 1;
    if (!form.resourceProfile.gpuType) form.resourceProfile.gpuType = "nvidia-tesla-v100";
  } else {
    // Switching to CPU-only - ensure CPU fields are set
    if (!form.resourceProfile.cpuCores) form.resourceProfile.cpuCores = 4;
    if (!form.resourceProfile.memory) form.resourceProfile.memory = "8Gi";
  }
};

const validateArchitecture = () => {
  architectureError.value = "";
  if (!architectureJson.value.trim()) {
    if (requiresArchitecture.value) {
      architectureError.value = "Architecture configuration is required";
    }
    return;
  }
  try {
    const parsed = JSON.parse(architectureJson.value);
    if (!parsed.architecture) {
      architectureError.value = 'Architecture configuration must include "architecture" key';
    }
  } catch (e) {
    architectureError.value = "Invalid JSON format";
  }
};

onMounted(async () => {
  // Load models and datasets for selection
  try {
    const modelsRes = await catalogClient.listModels();
    if (modelsRes.status === "success" && modelsRes.data) {
      models.value = Array.isArray(modelsRes.data) ? modelsRes.data : [modelsRes.data];
    }
    
    const datasetsRes = await catalogClient.listDatasets();
    if (datasetsRes.status === "success" && datasetsRes.data) {
      const datasetsArray = Array.isArray(datasetsRes.data) ? datasetsRes.data : [datasetsRes.data];
      datasets.value = datasetsArray;
    }
  } catch (e) {
    console.error("Failed to load models/datasets:", e);
    message.value = "Failed to load models/datasets. Please refresh the page.";
    messageType.value = "error";
  }
});

async function submitJob() {
  if (!isFormValid.value) {
    message.value = "Please fill in all required fields correctly";
    messageType.value = "error";
    return;
  }

  submitting.value = true;
  message.value = "";

  try {
    // Build hyperparameters object
    let hyperparameters: Record<string, unknown> = {};
    
    if (architectureJson.value.trim()) {
      try {
        const archParsed = JSON.parse(architectureJson.value);
        hyperparameters = { ...hyperparameters, ...archParsed };
      } catch (e) {
        message.value = "Invalid architecture JSON format";
        messageType.value = "error";
        submitting.value = false;
        return;
      }
    }
    
    if (hyperparametersJson.value.trim()) {
      try {
        const hyperParsed = JSON.parse(hyperparametersJson.value);
        hyperparameters = { ...hyperparameters, ...hyperParsed };
      } catch (e) {
        message.value = "Invalid hyperparameters JSON format";
        messageType.value = "error";
        submitting.value = false;
        return;
      }
    }

    // Build TrainJobSpec if all required fields are present
    let spec: TrainJobSpec | undefined = undefined;
    if (
      trainJobSpec.job_type &&
      trainJobSpec.model_family &&
      trainJobSpec.dataset_ref?.name &&
      trainJobSpec.dataset_ref?.version &&
      trainJobSpec.dataset_ref?.type &&
      trainJobSpec.hyperparams &&
      trainJobSpec.method &&
      trainJobSpec.resources &&
      trainJobSpec.output?.artifact_name &&
      trainJobSpec.output?.save_format
    ) {
      // Update resources from form
      if (form.useGpu && form.resourceProfile.gpuCount) {
        trainJobSpec.resources.gpus = form.resourceProfile.gpuCount;
        trainJobSpec.resources.gpu_type = form.resourceProfile.gpuType || "A100";
      }
      if (form.resourceProfile.numNodes) {
        trainJobSpec.resources.nodes = form.resourceProfile.numNodes;
      }
      trainJobSpec.use_gpu = form.useGpu ?? true;
      
      spec = trainJobSpec as TrainJobSpec;
    }

    const request: TrainingJobRequest = {
      ...form,
      hyperparameters: Object.keys(hyperparameters).length > 0 ? hyperparameters : undefined,
      trainJobSpec: spec,
    };

    const response = await trainingClient.submitJob(request);
    if (response.status === "success" && response.data) {
      message.value = `Job submitted successfully: ${response.data.id}`;
      messageType.value = "success";
      // Navigate to job detail page after 1 second
      setTimeout(() => {
        router.push(`/training/jobs/${response.data!.id}`);
      }, 1000);
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
  max-width: 800px;
  margin: 0 auto;
  padding: 20px;
}

header {
  margin-bottom: 30px;
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

h1 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.form-section {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.form-section h2 {
  margin: 0 0 20px 0;
  font-size: 18px;
  font-weight: 600;
  color: #495057;
  border-bottom: 2px solid #e9ecef;
  padding-bottom: 10px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-weight: 500;
  color: #495057;
  font-size: 14px;
}

.required {
  color: #dc3545;
}

.form-group select,
.form-group input,
.form-group textarea {
  width: 100%;
  padding: 10px;
  border: 1px solid #ced4da;
  border-radius: 4px;
  font-size: 14px;
  font-family: inherit;
}

.form-group select:disabled {
  background: #e9ecef;
  cursor: not-allowed;
}

.form-group textarea {
  font-family: monospace;
  resize: vertical;
}

.help-text {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #6c757d;
}

.error-text {
  display: block;
  margin-top: 5px;
  font-size: 12px;
  color: #dc3545;
}

.form-actions {
  display: flex;
  gap: 10px;
  justify-content: flex-end;
  margin-top: 30px;
}

button {
  padding: 12px 24px;
  border: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.btn-submit {
  background: #007bff;
  color: white;
}

.btn-submit:hover:not(:disabled) {
  background: #0056b3;
}

.btn-submit:disabled {
  background: #6c757d;
  cursor: not-allowed;
  opacity: 0.6;
}

.btn-cancel {
  background: #6c757d;
  color: white;
}

.btn-cancel:hover {
  background: #5a6268;
}

.message {
  margin-top: 20px;
  padding: 12px;
  border-radius: 4px;
  font-size: 14px;
}

.message.success {
  background: #d4edda;
  color: #155724;
  border: 1px solid #c3e6cb;
}

.message.error {
  background: #f8d7da;
  color: #721c24;
  border: 1px solid #f5c6cb;
}
</style>
