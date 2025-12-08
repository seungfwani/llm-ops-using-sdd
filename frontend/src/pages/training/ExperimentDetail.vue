<template>
  <div class="experiment-detail">
    <header>
      <h1>Experiment: {{ jobId.substring(0, 8) }}...</h1>
    </header>

    <div v-if="loading" class="loading">Loading experiment data...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else-if="experiment" class="experiment-content">
      <div class="experiment-info-card">
        <h2>Experiment Information</h2>
        <div class="info-grid">
          <div class="info-item">
            <label>Job ID:</label>
            <span class="id-value">{{ experiment.jobId }}</span>
          </div>
          <div class="info-item">
            <label>Total Metrics:</label>
            <span>{{ experiment.metrics.length }}</span>
          </div>
        </div>
      </div>

      <div v-if="experiment.metrics.length === 0" class="no-metrics">
        <p>No metrics recorded yet for this experiment.</p>
        <p class="help-text">Metrics will appear here as the training job progresses.</p>
      </div>

      <div v-else class="metrics-section">
        <h2>Metrics</h2>
        
        <!-- Metric Groups -->
        <div v-for="metricGroup in metricGroups" :key="metricGroup.name" class="metric-group">
          <h3>{{ metricGroup.name }}</h3>
          <div class="metric-chart">
            <div class="chart-container">
              <div class="chart-bars">
                <div
                  v-for="(metric, index) in metricGroup.metrics"
                  :key="metric.id"
                  class="chart-bar-wrapper"
                >
                  <div class="chart-bar" :style="getBarStyle(metricGroup.metrics, metric.value)">
                    <span class="bar-value">{{ formatValue(metric.value, metric.unit) }}</span>
                  </div>
                  <div class="bar-label">{{ formatDate(metric.recordedAt) }}</div>
                </div>
              </div>
            </div>
          </div>
          
          <!-- Metric Table -->
          <table class="metrics-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Value</th>
                <th>Unit</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="metric in metricGroup.metrics" :key="metric.id">
                <td>{{ formatDate(metric.recordedAt) }}</td>
                <td class="metric-value">{{ formatValue(metric.value, metric.unit) }}</td>
                <td>{{ metric.unit || '-' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute } from "vue-router";
import { trainingClient, type Experiment, type ExperimentMetric } from "@/services/trainingClient";

const route = useRoute();
const jobId = route.params.id as string;

const experiment = ref<Experiment | null>(null);
const loading = ref(true);
const error = ref("");

const metricGroups = computed(() => {
  if (!experiment.value) return [];
  
  const groups: Record<string, ExperimentMetric[]> = {};
  experiment.value.metrics.forEach((metric) => {
    if (!groups[metric.name]) {
      groups[metric.name] = [];
    }
    groups[metric.name].push(metric);
  });
  
  return Object.entries(groups).map(([name, metrics]) => ({
    name,
    metrics: metrics.sort((a, b) => 
      new Date(a.recordedAt).getTime() - new Date(b.recordedAt).getTime()
    ),
  }));
});

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}

function formatValue(value: number, unit?: string): string {
  if (unit === "percentage") {
    return `${(value * 100).toFixed(2)}%`;
  }
  return value.toFixed(4);
}

function getBarStyle(metrics: ExperimentMetric[], value: number): { height: string } {
  const values = metrics.map((m) => m.value);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const range = max - min || 1;
  const percentage = ((value - min) / range) * 100;
  return { height: `${Math.max(percentage, 5)}%` };
}

onMounted(async () => {
  await loadExperiment();
});

async function loadExperiment() {
  loading.value = true;
  error.value = "";
  try {
    const response = await trainingClient.getExperiment(jobId);
    if (response.status === "success" && response.data) {
      experiment.value = response.data;
    } else {
      error.value = response.message || "Failed to load experiment";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.experiment-detail {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

header {
  margin-bottom: 30px;
  padding-bottom: 20px;
  border-bottom: 2px solid #e9ecef;
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

.loading,
.error {
  padding: 40px;
  text-align: center;
  font-size: 16px;
}

.error {
  color: #dc3545;
}

.experiment-content {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.experiment-info-card {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
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

.no-metrics {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
}

.no-metrics p {
  margin: 10px 0;
  color: #6c757d;
}

.help-text {
  font-size: 14px;
  color: #868e96;
}

.metrics-section {
  display: flex;
  flex-direction: column;
  gap: 30px;
}

.metric-group {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.metric-group h3 {
  margin: 0 0 20px 0;
  font-size: 16px;
  font-weight: 600;
  color: #495057;
  text-transform: capitalize;
}

.metric-chart {
  margin-bottom: 30px;
}

.chart-container {
  padding: 20px;
  background: #f8f9fa;
  border-radius: 4px;
}

.chart-bars {
  display: flex;
  align-items: flex-end;
  justify-content: space-around;
  gap: 10px;
  min-height: 200px;
  padding: 10px 0;
}

.chart-bar-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 5px;
}

.chart-bar {
  width: 100%;
  background: linear-gradient(to top, #007bff, #0056b3);
  border-radius: 4px 4px 0 0;
  min-height: 20px;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 5px;
  position: relative;
  transition: all 0.3s ease;
}

.chart-bar:hover {
  background: linear-gradient(to top, #0056b3, #004085);
  transform: scaleY(1.05);
}

.bar-value {
  color: white;
  font-size: 11px;
  font-weight: 500;
  white-space: nowrap;
}

.bar-label {
  font-size: 11px;
  color: #6c757d;
  text-align: center;
  word-break: break-word;
  max-width: 100px;
}

.metrics-table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 20px;
}

.metrics-table thead {
  background: #f8f9fa;
}

.metrics-table th {
  padding: 12px;
  text-align: left;
  font-size: 12px;
  font-weight: 600;
  color: #495057;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 2px solid #dee2e6;
}

.metrics-table td {
  padding: 12px;
  border-bottom: 1px solid #e9ecef;
  font-size: 14px;
  color: #495057;
}

.metrics-table tbody tr:hover {
  background: #f8f9fa;
}

.metric-value {
  font-family: monospace;
  font-weight: 500;
  color: #007bff;
}

@media (max-width: 768px) {
  .info-grid {
    grid-template-columns: 1fr;
  }

  .chart-bars {
    flex-direction: column;
    align-items: stretch;
    min-height: auto;
  }

  .chart-bar-wrapper {
    flex-direction: row;
    align-items: center;
  }

  .chart-bar {
    width: 60%;
    min-height: 40px;
  }

  .bar-label {
    flex: 1;
    text-align: left;
    padding-left: 10px;
  }
}
</style>

