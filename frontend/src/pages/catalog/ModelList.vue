<template>
  <section class="model-list">
    <header>
      <h1>Model Catalog</h1>
      <div class="header-actions">
      <button @click="fetchModels" :disabled="loading">Refresh</button>
        <router-link to="/catalog/models/new" class="btn-primary">Create New Model</router-link>
      </div>
    </header>

    <div class="filters">
      <label>
        Type:
        <select v-model="filters.type" @change="fetchModels">
          <option value="">All</option>
          <option value="base">Base</option>
          <option value="fine-tuned">Fine-tuned</option>
          <option value="external">External</option>
        </select>
      </label>
      <label>
        Status:
        <select v-model="filters.status" @change="fetchModels">
          <option value="">All</option>
          <option value="draft">Draft</option>
          <option value="pending_review">Pending Review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </select>
      </label>
      <label>
        Owner Team:
        <input v-model="filters.owner_team" @input="debouncedFetch" placeholder="Filter by team" />
      </label>
    </div>

    <div v-if="loading" class="loading">Loading models...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="models.length" class="models-table">
      <thead>
        <tr>
          <th>Name</th>
          <th>Version</th>
          <th>Type</th>
          <th>Status</th>
          <th>Owner Team</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="model in filteredModels" :key="model.id">
          <td><strong>{{ model.name }}</strong></td>
          <td>{{ model.version }}</td>
          <td>
            <span :class="`type-badge type-${model.type}`">
              {{ model.type }}
            </span>
          </td>
          <td>
            <span :class="`status-badge status-${model.status}`">
              {{ model.status }}
            </span>
          </td>
          <td>{{ model.owner_team }}</td>
          <td>
            <div class="action-buttons">
            <router-link :to="`/catalog/models/${model.id}`" class="btn-link">View</router-link>
              <button @click="handleDelete(model.id, model.name)" class="btn-delete" :disabled="deleting === model.id">
                {{ deleting === model.id ? 'Deleting...' : 'Delete' }}
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No models found.</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive, computed } from 'vue';
import { catalogClient, type CatalogModel } from '@/services/catalogClient';

const models = ref<CatalogModel[]>([]);
const loading = ref(false);
const error = ref('');
const deleting = ref<string | null>(null);

const filters = reactive({
  type: '',
  status: '',
  owner_team: '',
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function debouncedFetch() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    fetchModels();
  }, 300);
}

const filteredModels = computed(() => {
  let result = models.value;
  
  if (filters.type) {
    result = result.filter(m => m.type === filters.type);
  }
  if (filters.status) {
    result = result.filter(m => m.status === filters.status);
  }
  if (filters.owner_team) {
    const teamLower = filters.owner_team.toLowerCase();
    result = result.filter(m => m.owner_team.toLowerCase().includes(teamLower));
  }
  
  return result;
});

async function fetchModels() {
  loading.value = true;
  error.value = '';
  try {
    const response = await catalogClient.listModels();
    if (response.status === "success" && response.data) {
      models.value = Array.isArray(response.data) ? response.data : [response.data];
    } else {
      error.value = response.message || "Failed to load models";
      models.value = [];
    }
  } catch (e) {
    error.value = `Error: ${e}`;
    models.value = [];
  } finally {
    loading.value = false;
  }
}

async function handleDelete(modelId: string, modelName: string) {
  if (!confirm(`Are you sure you want to delete model "${modelName}" (${modelId})? This action cannot be undone.`)) {
    return;
  }

  deleting.value = modelId;
  try {
    const response = await catalogClient.deleteModel(modelId);
    if (response.status === "success") {
      alert('Model deleted successfully');
      await fetchModels(); // Refresh the list
    } else {
      alert(`Failed to delete model: ${response.message}`);
    }
  } catch (e) {
    alert(`Error deleting model: ${e}`);
  } finally {
    deleting.value = null;
  }
}

onMounted(fetchModels);
</script>

<style scoped>
.model-list {
  padding: 2rem;
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

.btn-primary {
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  border: none;
  cursor: pointer;
}

.btn-primary:hover {
  background: #0056b3;
}

.filters {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  padding: 1rem;
  background: #f5f5f5;
  border-radius: 4px;
}

.filters label {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  font-size: 0.9rem;
}

.filters select,
.filters input {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.models-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.models-table th {
  background: #f8f9fa;
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #dee2e6;
}

.models-table td {
  padding: 0.75rem;
  border-bottom: 1px solid #dee2e6;
}

.models-table tr:hover {
  background: #f8f9fa;
}

.type-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: capitalize;
}

.type-base {
  background: #d1ecf1;
  color: #0c5460;
}

.type-fine-tuned {
  background: #d4edda;
  color: #155724;
}

.type-external {
  background: #fff3cd;
  color: #856404;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: capitalize;
}

.status-draft {
  background: #e2e3e5;
  color: #383d41;
}

.status-pending_review {
  background: #fff3cd;
  color: #856404;
}

.status-approved {
  background: #d4edda;
  color: #155724;
}

.status-rejected {
  background: #f8d7da;
  color: #721c24;
}

.btn-link {
  color: #007bff;
  text-decoration: none;
}

.btn-link:hover {
  text-decoration: underline;
}

.action-buttons {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.btn-delete {
  padding: 0.25rem 0.75rem;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-delete:hover:not(:disabled) {
  background: #c82333;
}

.btn-delete:disabled {
  background: #ccc;
  cursor: not-allowed;
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

