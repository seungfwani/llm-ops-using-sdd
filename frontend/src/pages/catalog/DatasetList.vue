<template>
  <section class="dataset-list">
    <div class="catalog-tabs">
      <router-link to="/catalog/models" class="tab-link" active-class="active">Models</router-link>
      <router-link to="/catalog/datasets" class="tab-link" active-class="active">Datasets</router-link>
    </div>
    <header>
      <h1>Dataset Catalog</h1>
      <div class="header-actions">
        <button @click="fetchDatasets" :disabled="loading" class="btn-secondary">Refresh</button>
        <router-link to="/catalog/datasets/new" class="btn-primary">New Dataset</router-link>
      </div>
    </header>

    <div class="filters">
      <label>
        Name:
        <input v-model="filters.name" @input="debouncedFetch" placeholder="Filter by name" />
      </label>
      <label>
        Version:
        <input v-model="filters.version" @input="debouncedFetch" placeholder="Filter by version" />
      </label>
      <label>
        Owner Team:
        <input v-model="filters.owner_team" @input="debouncedFetch" placeholder="Filter by team" />
      </label>
      <label>
        PII Status:
        <select v-model="filters.pii_status" @change="fetchDatasets">
          <option value="">All</option>
          <option value="pending">Pending</option>
          <option value="clean">Clean</option>
          <option value="failed">Failed</option>
        </select>
      </label>
      <label>
        Quality Score:
        <input
          v-model.number="filters.min_quality_score"
          type="number"
          min="0"
          max="100"
          @input="debouncedFetch"
          placeholder="Min score"
        />
      </label>
    </div>

    <div v-if="loading" class="loading">Loading datasets...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="datasets.length" class="datasets-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Version</th>
          <th>Owner Team</th>
          <th>PII Status</th>
          <th>Quality Score</th>
          <th>Approval Status</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="dataset in filteredDatasets" :key="dataset.id">
          <td><strong>{{ dataset.name }}</strong></td>
          <td>{{ dataset.version }}</td>
          <td>{{ dataset.owner_team }}</td>
          <td>
            <span :class="`pii-badge pii-${dataset.pii_scan_status}`">
              {{ dataset.pii_scan_status }}
            </span>
          </td>
          <td>
            <span :class="getQualityScoreClass(dataset.quality_score)">
              {{ dataset.quality_score ?? 'N/A' }}
            </span>
          </td>
          <td>
            <span :class="`approval-badge ${dataset.approved_at ? 'approved' : 'pending'}`">
              {{ dataset.approved_at ? 'Approved' : 'Pending' }}
            </span>
          </td>
          <td>
            <div class="action-buttons">
              <router-link :to="`/catalog/datasets/${dataset.id}`" class="btn-link">View</router-link>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No datasets found.</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive, computed } from 'vue';
import { catalogClient, type CatalogDataset } from '@/services/catalogClient';

const datasets = ref<CatalogDataset[]>([]);
const loading = ref(false);
const error = ref('');

const filters = reactive({
  name: '',
  version: '',
  owner_team: '',
  pii_status: '',
  min_quality_score: null as number | null,
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function debouncedFetch() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    fetchDatasets();
  }, 300);
}

const filteredDatasets = computed(() => {
  return datasets.value.filter((dataset) => {
    if (filters.name && !dataset.name.toLowerCase().includes(filters.name.toLowerCase())) {
      return false;
    }
    if (filters.version && !dataset.version.toLowerCase().includes(filters.version.toLowerCase())) {
      return false;
    }
    if (filters.owner_team && !dataset.owner_team.toLowerCase().includes(filters.owner_team.toLowerCase())) {
      return false;
    }
    if (filters.pii_status && dataset.pii_scan_status !== filters.pii_status) {
      return false;
    }
    if (filters.min_quality_score !== null && (dataset.quality_score === null || dataset.quality_score < filters.min_quality_score)) {
      return false;
    }
    return true;
  });
});

function getQualityScoreClass(score: number | null): string {
  if (score === null) return 'quality-score na';
  if (score >= 80) return 'quality-score high';
  if (score >= 60) return 'quality-score medium';
  return 'quality-score low';
}

async function fetchDatasets() {
  loading.value = true;
  error.value = '';
  try {
    const response = await catalogClient.listDatasets();
    if (response.status === 'success' && response.data) {
      datasets.value = Array.isArray(response.data) ? response.data : [response.data];
    } else {
      error.value = response.message || 'Failed to fetch datasets';
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : 'Failed to fetch datasets';
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  fetchDatasets();
});
</script>

<style scoped>
.dataset-list {
  padding: 2rem;
}

.catalog-tabs {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 1.5rem;
  border-bottom: 2px solid #e0e0e0;
}

.tab-link {
  padding: 0.75rem 1.5rem;
  text-decoration: none;
  color: #666;
  font-weight: 500;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: all 0.2s;
}

.tab-link:hover {
  color: #007bff;
}

.tab-link.active {
  color: #007bff;
  border-bottom-color: #007bff;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2rem;
}

.header-actions {
  display: flex;
  gap: 1rem;
}

.filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.filters label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.875rem;
}

.filters input,
.filters select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.datasets-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  border-radius: 8px;
  overflow: hidden;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.datasets-table thead {
  background: #f5f5f5;
}

.datasets-table th {
  padding: 1rem;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #ddd;
}

.datasets-table td {
  padding: 1rem;
  border-bottom: 1px solid #eee;
}

.datasets-table tbody tr:hover {
  background: #f9f9f9;
}

.pii-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
}

.pii-badge.pii-pending {
  background: #fff3cd;
  color: #856404;
}

.pii-badge.pii-clean {
  background: #d4edda;
  color: #155724;
}

.pii-badge.pii-failed {
  background: #f8d7da;
  color: #721c24;
}

.quality-score {
  font-weight: 600;
}

.quality-score.high {
  color: #28a745;
}

.quality-score.medium {
  color: #ffc107;
}

.quality-score.low {
  color: #dc3545;
}

.quality-score.na {
  color: #6c757d;
}

.approval-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 600;
}

.approval-badge.approved {
  background: #d4edda;
  color: #155724;
}

.approval-badge.pending {
  background: #fff3cd;
  color: #856404;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
}

.btn-link {
  color: #007bff;
  text-decoration: none;
  font-weight: 500;
}

.btn-link:hover {
  text-decoration: underline;
}

.btn-primary {
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-weight: 500;
}

.btn-primary:hover {
  background: #0056b3;
}

.loading,
.error,
.empty {
  padding: 2rem;
  text-align: center;
}

.error {
  color: #dc3545;
}
</style>

