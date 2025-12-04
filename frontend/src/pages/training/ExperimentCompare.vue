<template>
  <div class="experiment-compare">
    <header>
      <h1>Compare Experiments</h1>
      <router-link to="/training/jobs" class="back-link">← Back to Jobs</router-link>
    </header>

    <div class="compare-controls">
      <div class="control-group">
        <label>Select Experiments to Compare:</label>
        <div class="experiment-selector">
          <div v-for="(selected, index) in selectedExperiments" :key="index" class="selector-item">
            <select v-model="selectedExperiments[index]" @change="loadExperiment(index)">
              <option value="">-- Select Experiment --</option>
              <option
                v-for="exp in availableExperiments"
                :key="exp.id"
                :value="exp.id"
                :disabled="selectedExperiments.includes(exp.id) && selectedExperiments[index] !== exp.id"
              >
                {{ exp.experimentName }} - {{ exp.runName || exp.trackingRunId.substring(0, 8) }}
              </option>
            </select>
            <button
              v-if="selectedExperiments.length > 2"
              @click="removeExperiment(index)"
              class="btn-remove"
            >
              Remove
            </button>
          </div>
          <button @click="addExperiment" class="btn-add">+ Add Experiment</button>
        </div>
      </div>

      <div class="control-actions">
        <button @click="compareExperiments" :disabled="!canCompare" class="btn-compare">
          Compare
        </button>
        <button @click="clearSelection" class="btn-clear">Clear</button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading experiments...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="comparisonData && comparisonData.length > 0" class="comparison-results">
      <h2>Comparison Results</h2>
      <div class="comparison-table">
        <table>
          <thead>
            <tr>
              <th>Metric/Parameter</th>
              <th v-for="(exp, index) in comparisonData" :key="index" class="experiment-column">
                <div class="column-header">
                  <div class="experiment-name">{{ exp.experimentName }}</div>
                  <div class="run-name">{{ exp.runName || exp.trackingRunId.substring(0, 8) }}</div>
                  <div class="experiment-status">
                    <span :class="`status-badge status-${exp.status}`">{{ exp.status }}</span>
                  </div>
                </div>
              </th>
            </tr>
          </thead>
          <tbody>
            <!-- Parameters -->
            <tr v-if="hasParameters" class="section-header">
              <td :colspan="comparisonData.length + 1" class="section-title">Parameters</td>
            </tr>
            <tr
              v-for="paramName in allParameterNames"
              :key="`param-${paramName}`"
              class="data-row"
            >
              <td class="metric-name">{{ paramName }}</td>
              <td v-for="(exp, index) in comparisonData" :key="index">
                {{ getParameterValue(exp, paramName) }}
              </td>
            </tr>

            <!-- Metrics -->
            <tr v-if="hasMetrics" class="section-header">
              <td :colspan="comparisonData.length + 1" class="section-title">Metrics</td>
            </tr>
            <tr
              v-for="metricName in allMetricNames"
              :key="`metric-${metricName}`"
              class="data-row"
            >
              <td class="metric-name">{{ metricName }}</td>
              <td v-for="(exp, index) in comparisonData" :key="index">
                <span :class="getBestMetricClass(metricName, index)">
                  {{ getMetricValue(exp, metricName) }}
                </span>
              </td>
            </tr>

            <!-- Metadata -->
            <tr class="section-header">
              <td :colspan="comparisonData.length + 1" class="section-title">Metadata</td>
            </tr>
            <tr class="data-row">
              <td class="metric-name">Start Time</td>
              <td v-for="(exp, index) in comparisonData" :key="index">
                {{ formatDate(exp.startTime) }}
              </td>
            </tr>
            <tr v-if="hasEndTimes" class="data-row">
              <td class="metric-name">End Time</td>
              <td v-for="(exp, index) in comparisonData" :key="index">
                {{ exp.endTime ? formatDate(exp.endTime) : "N/A" }}
              </td>
            </tr>
            <tr class="data-row">
              <td class="metric-name">Duration</td>
              <td v-for="(exp, index) in comparisonData" :key="index">
                {{ calculateDuration(exp.startTime, exp.endTime) }}
              </td>
            </tr>
            <tr class="data-row">
              <td class="metric-name">Tracking System</td>
              <td v-for="(exp, index) in comparisonData" :key="index">
                <span class="tracking-system-badge">{{ exp.trackingSystem }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="comparison-actions">
        <a
          v-for="(exp, index) in comparisonData"
          :key="index"
          :href="getMLflowUrl(exp)"
          target="_blank"
          rel="noopener noreferrer"
          class="btn-mlflow"
          v-if="getMLflowUrl(exp)"
        >
          Open {{ exp.experimentName }} in MLflow →
        </a>
      </div>
    </div>
    <div v-else-if="comparisonData && comparisonData.length === 0" class="no-results">
      Select at least 2 experiments to compare.
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from "vue";
import { integrationClient, type ExperimentRun } from "@/services/integrationClient";

const selectedExperiments = ref<string[]>(["", ""]);
const availableExperiments = ref<ExperimentRun[]>([]);
const comparisonData = ref<ExperimentRun[]>([]);
const loading = ref(false);
const error = ref("");

const canCompare = computed(() => {
  return selectedExperiments.value.filter((id) => id).length >= 2;
});

const hasParameters = computed(() => {
  return comparisonData.value.some((exp) => exp.parameters && Object.keys(exp.parameters).length > 0);
});

const hasMetrics = computed(() => {
  return comparisonData.value.some((exp) => exp.metrics && Object.keys(exp.metrics).length > 0);
});

const hasEndTimes = computed(() => {
  return comparisonData.value.some((exp) => exp.endTime);
});

const allParameterNames = computed(() => {
  const names = new Set<string>();
  comparisonData.value.forEach((exp) => {
    if (exp.parameters) {
      Object.keys(exp.parameters).forEach((name) => names.add(name));
    }
  });
  return Array.from(names).sort();
});

const allMetricNames = computed(() => {
  const names = new Set<string>();
  comparisonData.value.forEach((exp) => {
    if (exp.metrics) {
      Object.keys(exp.metrics).forEach((name) => names.add(name));
    }
  });
  return Array.from(names).sort();
});

const loadAvailableExperiments = async () => {
  loading.value = true;
  error.value = "";
  try {
    const response = await integrationClient.searchExperiments({
      maxResults: 100,
    });
    if (response.status === "success" && response.data) {
      availableExperiments.value = response.data.experiments;
    }
  } catch (e) {
    error.value = `Failed to load experiments: ${e}`;
  } finally {
    loading.value = false;
  }
};

const loadExperiment = async (index: number) => {
  const experimentId = selectedExperiments.value[index];
  if (!experimentId) {
    // Remove experiment from comparison if deselected
    if (comparisonData.value[index]) {
      comparisonData.value.splice(index, 1);
    }
    return;
  }

  const experiment = availableExperiments.value.find((exp) => exp.id === experimentId);
  if (experiment) {
    // Ensure array is large enough
    while (comparisonData.value.length <= index) {
      comparisonData.value.push({} as ExperimentRun);
    }
    comparisonData.value[index] = experiment;
  }
};

const compareExperiments = async () => {
  const selectedIds = selectedExperiments.value.filter((id) => id);
  if (selectedIds.length < 2) {
    error.value = "Please select at least 2 experiments to compare";
    return;
  }

  comparisonData.value = selectedIds
    .map((id) => availableExperiments.value.find((exp) => exp.id === id))
    .filter((exp) => exp !== undefined) as ExperimentRun[];
};

const addExperiment = () => {
  selectedExperiments.value.push("");
};

const removeExperiment = (index: number) => {
  selectedExperiments.value.splice(index, 1);
  comparisonData.value.splice(index, 1);
};

const clearSelection = () => {
  selectedExperiments.value = ["", ""];
  comparisonData.value = [];
};

const getParameterValue = (exp: ExperimentRun, paramName: string): string => {
  if (!exp.parameters) return "N/A";
  const value = exp.parameters[paramName];
  return value !== undefined ? String(value) : "N/A";
};

const getMetricValue = (exp: ExperimentRun, metricName: string): string => {
  if (!exp.metrics) return "N/A";
  const value = exp.metrics[metricName];
  return value !== undefined ? String(value) : "N/A";
};

const getBestMetricClass = (metricName: string, index: number): string => {
  // Highlight the best (highest) value for each metric
  const values = comparisonData.value
    .map((exp) => {
      if (!exp.metrics) return null;
      const value = exp.metrics[metricName];
      return value !== undefined ? Number(value) : null;
    })
    .filter((v) => v !== null) as number[];

  if (values.length === 0) return "";

  const maxValue = Math.max(...values);
  const currentValue = values[index];

  return currentValue === maxValue ? "best-value" : "";
};

const calculateDuration = (startTime: string, endTime?: string): string => {
  const start = new Date(startTime);
  const end = endTime ? new Date(endTime) : new Date();
  const diffMs = end.getTime() - start.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffDays > 0) {
    return `${diffDays}d ${diffHours % 24}h`;
  } else if (diffHours > 0) {
    return `${diffHours}h ${diffMins % 60}m`;
  } else {
    return `${diffMins}m`;
  }
};

const getMLflowUrl = (experiment: ExperimentRun): string | null => {
  return integrationClient.getMLflowUIUrl(experiment);
};

const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleString();
};

// Load available experiments on mount
loadAvailableExperiments();
</script>

<style scoped>
.experiment-compare {
  max-width: 1400px;
  margin: 0 auto;
  padding: 20px;
}

header {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #e9ecef;
}

header h1 {
  margin: 0 0 10px 0;
  font-size: 28px;
}

.back-link {
  display: inline-block;
  color: #007bff;
  text-decoration: none;
  font-size: 14px;
}

.back-link:hover {
  text-decoration: underline;
}

.compare-controls {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
}

.control-group {
  margin-bottom: 20px;
}

.control-group label {
  display: block;
  margin-bottom: 10px;
  font-weight: 500;
  color: #495057;
}

.experiment-selector {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.selector-item {
  display: flex;
  gap: 10px;
  align-items: center;
}

.selector-item select {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.btn-remove {
  padding: 8px 16px;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-remove:hover {
  background: #c82333;
}

.btn-add {
  padding: 8px 16px;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-add:hover {
  background: #218838;
}

.control-actions {
  display: flex;
  gap: 10px;
}

.btn-compare {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-compare:hover:not(:disabled) {
  background: #0056b3;
}

.btn-compare:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-clear {
  padding: 10px 20px;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-clear:hover {
  background: #5a6268;
}

.loading,
.error,
.no-results {
  padding: 40px;
  text-align: center;
  font-size: 16px;
}

.error {
  color: #dc3545;
}

.comparison-results h2 {
  margin-bottom: 20px;
  font-size: 24px;
}

.comparison-table {
  overflow-x: auto;
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
}

thead {
  background: #f8f9fa;
}

th {
  padding: 15px;
  text-align: left;
  font-weight: 600;
  color: #495057;
  border-bottom: 2px solid #e9ecef;
}

.experiment-column {
  min-width: 200px;
}

.column-header {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.experiment-name {
  font-weight: 600;
  color: #495057;
}

.run-name {
  font-size: 12px;
  color: #6c757d;
  font-style: italic;
}

.experiment-status {
  margin-top: 5px;
}

.status-badge {
  display: inline-block;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
  text-transform: capitalize;
}

.status-running {
  background: #17a2b8;
  color: white;
}

.status-completed {
  background: #28a745;
  color: white;
}

.status-failed {
  background: #dc3545;
  color: white;
}

.status-killed {
  background: #6c757d;
  color: white;
}

tbody tr {
  border-bottom: 1px solid #e9ecef;
}

tbody tr:hover {
  background: #f8f9fa;
}

.section-header {
  background: #f8f9fa;
}

.section-title {
  padding: 12px 15px;
  font-weight: 600;
  color: #495057;
  text-transform: uppercase;
  font-size: 12px;
  letter-spacing: 0.5px;
}

.data-row td {
  padding: 12px 15px;
  font-size: 14px;
}

.metric-name {
  font-weight: 500;
  color: #495057;
}

.best-value {
  background: #d4edda;
  padding: 4px 8px;
  border-radius: 4px;
  font-weight: 600;
  color: #155724;
}

.tracking-system-badge {
  display: inline-block;
  padding: 4px 8px;
  background: #e7f3ff;
  color: #0194e2;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
  text-transform: uppercase;
}

.comparison-actions {
  display: flex;
  gap: 10px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.btn-mlflow {
  padding: 10px 20px;
  background: #0194e2;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
}

.btn-mlflow:hover {
  background: #0178b8;
}

@media (max-width: 768px) {
  .comparison-table {
    font-size: 12px;
  }

  th,
  td {
    padding: 8px;
  }
}
</style>

