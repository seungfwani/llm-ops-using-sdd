<template>
  <div class="experiment-search">
    <div class="search-header">
      <h2>Search Experiments</h2>
      <button @click="performSearch" :disabled="searching" class="btn-search">
        {{ searching ? "Searching..." : "Search" }}
      </button>
    </div>

    <div class="search-filters">
      <div class="form-group">
        <label for="experiment-name">Experiment Name:</label>
        <input
          id="experiment-name"
          v-model="filters.experimentName"
          type="text"
          placeholder="e.g., fine-tuning-experiment"
        />
      </div>

      <div class="form-group">
        <label for="filter-string">Filter String:</label>
        <input
          id="filter-string"
          v-model="filters.filterString"
          type="text"
          placeholder="e.g., metrics.accuracy > 0.9"
        />
        <small class="help-text">MLflow filter syntax (optional)</small>
      </div>

      <div class="form-group">
        <label for="max-results">Max Results:</label>
        <input
          id="max-results"
          v-model.number="filters.maxResults"
          type="number"
          min="1"
          max="1000"
        />
      </div>
    </div>

    <div v-if="searching" class="loading">Searching experiments...</div>
    <div v-else-if="searchError" class="error">{{ searchError }}</div>
    <div v-else-if="results && results.length > 0" class="results">
      <div class="results-header">
        <span>Found {{ total }} experiment{{ total !== 1 ? "s" : "" }}</span>
      </div>
      <div class="experiment-list">
        <div
          v-for="experiment in results"
          :key="experiment.id"
          class="experiment-card"
          @click="selectExperiment(experiment)"
        >
          <div class="experiment-header">
            <h3>{{ experiment.experimentName }}</h3>
            <span :class="`status-badge status-${experiment.status}`">
              {{ experiment.status }}
            </span>
          </div>
          <div v-if="experiment.runName" class="experiment-meta">
            <span class="run-name">{{ experiment.runName }}</span>
          </div>
          <div class="experiment-info">
            <div class="info-item">
              <label>Tracking System:</label>
              <span class="tracking-system-badge">{{ experiment.trackingSystem }}</span>
            </div>
            <div class="info-item">
              <label>Started:</label>
              <span>{{ formatDate(experiment.startTime) }}</span>
            </div>
            <div v-if="experiment.endTime" class="info-item">
              <label>Ended:</label>
              <span>{{ formatDate(experiment.endTime) }}</span>
            </div>
          </div>
          <div v-if="experiment.metrics && Object.keys(experiment.metrics).length > 0" class="experiment-metrics">
            <label>Metrics:</label>
            <div class="metrics-list">
              <span
                v-for="(value, name) in experiment.metrics"
                :key="name"
                class="metric-item"
              >
                <strong>{{ name }}:</strong> {{ value }}
              </span>
            </div>
          </div>
          <div class="experiment-actions">
            <router-link
              :to="`/training/jobs/${experiment.trainingJobId}`"
              class="btn-view-job"
              @click.stop
            >
              View Job →
            </router-link>
            <a
              v-if="getMLflowUrl(experiment)"
              :href="getMLflowUrl(experiment)"
              target="_blank"
              rel="noopener noreferrer"
              class="btn-mlflow"
              @click.stop
            >
              Open in MLflow →
            </a>
          </div>
        </div>
      </div>
    </div>
    <div v-else-if="results && results.length === 0" class="no-results">
      No experiments found. Try adjusting your search filters.
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { integrationClient, type ExperimentRun } from "@/services/integrationClient";

const filters = ref({
  experimentName: "",
  filterString: "",
  maxResults: 100,
});

const results = ref<ExperimentRun[]>([]);
const total = ref(0);
const searching = ref(false);
const searchError = ref("");

const performSearch = async () => {
  searching.value = true;
  searchError.value = "";
  
  try {
    const response = await integrationClient.searchExperiments({
      experimentName: filters.value.experimentName || undefined,
      filterString: filters.value.filterString || undefined,
      maxResults: filters.value.maxResults,
    });
    
    if (response.status === "success" && response.data) {
      results.value = response.data.experiments;
      total.value = response.data.total;
    } else {
      searchError.value = response.message || "Failed to search experiments";
      results.value = [];
      total.value = 0;
    }
  } catch (e) {
    searchError.value = `Error: ${e}`;
    results.value = [];
    total.value = 0;
  } finally {
    searching.value = false;
  }
};

const selectExperiment = (experiment: ExperimentRun) => {
  // Navigate to job detail page
  window.location.href = `/training/jobs/${experiment.trainingJobId}`;
};

const getMLflowUrl = (experiment: ExperimentRun): string | null => {
  return integrationClient.getMLflowUIUrl(experiment);
};

const formatDate = (dateStr: string): string => {
  return new Date(dateStr).toLocaleString();
};
</script>

<style scoped>
.experiment-search {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.search-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.search-header h2 {
  margin: 0;
  font-size: 24px;
}

.btn-search {
  padding: 10px 20px;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
}

.btn-search:hover:not(:disabled) {
  background: #0056b3;
}

.btn-search:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.search-filters {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 20px;
  margin-bottom: 30px;
  padding: 20px;
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.form-group label {
  font-size: 14px;
  font-weight: 500;
  color: #495057;
}

.form-group input {
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 14px;
}

.help-text {
  font-size: 12px;
  color: #6c757d;
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

.results-header {
  margin-bottom: 20px;
  font-size: 16px;
  font-weight: 500;
  color: #495057;
}

.experiment-list {
  display: grid;
  gap: 20px;
}

.experiment-card {
  background: white;
  border: 1px solid #e9ecef;
  border-radius: 8px;
  padding: 20px;
  cursor: pointer;
  transition: box-shadow 0.2s;
}

.experiment-card:hover {
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

.experiment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.experiment-header h3 {
  margin: 0;
  font-size: 18px;
  color: #495057;
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

.experiment-meta {
  margin-bottom: 15px;
}

.run-name {
  font-size: 14px;
  color: #6c757d;
  font-style: italic;
}

.experiment-info {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 15px;
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

.experiment-metrics {
  margin-bottom: 15px;
}

.experiment-metrics label {
  display: block;
  font-size: 12px;
  font-weight: 500;
  color: #6c757d;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.metrics-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.metric-item {
  padding: 6px 12px;
  background: #f8f9fa;
  border: 1px solid #e9ecef;
  border-radius: 4px;
  font-size: 13px;
}

.metric-item strong {
  color: #495057;
}

.experiment-actions {
  display: flex;
  gap: 10px;
  padding-top: 15px;
  border-top: 1px solid #e9ecef;
}

.btn-view-job,
.btn-mlflow {
  padding: 8px 16px;
  text-decoration: none;
  border-radius: 4px;
  font-size: 14px;
  font-weight: 500;
  transition: background 0.2s;
}

.btn-view-job {
  background: #007bff;
  color: white;
}

.btn-view-job:hover {
  background: #0056b3;
}

.btn-mlflow {
  background: #0194e2;
  color: white;
}

.btn-mlflow:hover {
  background: #0178b8;
}

@media (max-width: 768px) {
  .search-filters {
    grid-template-columns: 1fr;
  }

  .experiment-info {
    grid-template-columns: 1fr;
  }
}
</style>

