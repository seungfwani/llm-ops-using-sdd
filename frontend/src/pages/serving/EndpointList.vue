<template>
  <section class="endpoint-list">
    <header>
      <h1>Serving Endpoints</h1>
      <div class="header-actions">
        <button @click="fetchEndpoints" :disabled="loading">Refresh</button>
        <router-link to="/serving/endpoints/deploy" class="btn-primary">Deploy New</router-link>
      </div>
    </header>

    <div class="filters">
      <label>
        Environment:
        <select v-model="filters.environment" @change="fetchEndpoints">
          <option value="">All</option>
          <option value="dev">Development</option>
          <option value="stg">Staging</option>
          <option value="prod">Production</option>
        </select>
      </label>
      <label>
        Status:
        <select v-model="filters.status" @change="fetchEndpoints">
          <option value="">All</option>
          <option value="deploying">Deploying</option>
          <option value="healthy">Healthy</option>
          <option value="degraded">Degraded</option>
          <option value="failed">Failed</option>
        </select>
      </label>
      <label>
        Model ID:
        <input v-model="filters.modelId" @input="debouncedFetch" placeholder="Filter by model ID" />
      </label>
    </div>

    <div v-if="loading" class="loading">Loading endpoints...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <table v-else-if="endpoints.length" class="endpoints-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Route</th>
          <th>Environment</th>
          <th>Status</th>
          <th>Model ID</th>
          <th>Replicas</th>
          <th>Created</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="endpoint in endpoints" :key="endpoint.id">
          <td class="id-cell">{{ endpoint.id.substring(0, 8) }}...</td>
          <td>{{ endpoint.route }}</td>
          <td>
            <span :class="`env-badge env-${endpoint.environment}`">
              {{ endpoint.environment.toUpperCase() }}
            </span>
          </td>
          <td>
            <span :class="`status-badge status-${endpoint.status}`">
              {{ endpoint.status }}
            </span>
          </td>
          <td>{{ endpoint.modelId.substring(0, 8) }}...</td>
          <td>{{ endpoint.minReplicas }}-{{ endpoint.maxReplicas }}</td>
          <td>{{ formatDate(endpoint.createdAt) }}</td>
          <td>
            <router-link :to="`/serving/endpoints/${endpoint.id}`" class="btn-link">View</router-link>
            <router-link
              v-if="endpoint.status === 'healthy'"
              :to="`/serving/chat/${endpoint.id}`"
              class="btn-link btn-chat"
            >
              Chat
            </router-link>
            <button
              @click="handleDelete(endpoint.id, endpoint.route)"
              class="btn-delete-small"
              :disabled="deletingIds.has(endpoint.id)"
            >
              {{ deletingIds.has(endpoint.id) ? 'Deleting...' : 'Delete' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No serving endpoints found.</p>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, reactive } from 'vue';
import { servingClient, type ServingEndpoint, type ListEndpointsFilters } from '@/services/servingClient';

const endpoints = ref<ServingEndpoint[]>([]);
const loading = ref(false);
const error = ref('');
const deletingIds = ref<Set<string>>(new Set());

const filters = reactive<ListEndpointsFilters>({
  environment: undefined,
  status: undefined,
  modelId: undefined,
});

let debounceTimer: ReturnType<typeof setTimeout> | null = null;

function debouncedFetch() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    fetchEndpoints();
  }, 300);
}

async function fetchEndpoints() {
  loading.value = true;
  error.value = '';
  try {
    const response = await servingClient.listEndpoints(filters);
    if (response.status === "success" && response.data) {
      endpoints.value = response.data;
    } else {
      error.value = response.message || "Failed to load endpoints";
      endpoints.value = [];
    }
  } catch (e) {
    error.value = `Error: ${e}`;
    endpoints.value = [];
  } finally {
    loading.value = false;
  }
}

async function handleDelete(endpointId: string, route: string) {
  if (!confirm(`Are you sure you want to delete endpoint "${route}"? This will permanently delete the endpoint and all its Kubernetes resources.`)) {
    return;
  }

  deletingIds.value.add(endpointId);
  try {
    const response = await servingClient.deleteEndpoint(endpointId);
    if (response.status === "success") {
      // Remove from list
      endpoints.value = endpoints.value.filter(e => e.id !== endpointId);
    } else {
      alert(`Delete failed: ${response.message}`);
    }
  } catch (e) {
    alert(`Error: ${e}`);
  } finally {
    deletingIds.value.delete(endpointId);
  }
}

function formatDate(dateString: string): string {
  try {
    const date = new Date(dateString);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString();
  } catch {
    return dateString;
  }
}

onMounted(fetchEndpoints);
</script>

<style scoped>
.endpoint-list {
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

.endpoints-table {
  width: 100%;
  border-collapse: collapse;
  background: white;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.endpoints-table th {
  background: #f8f9fa;
  padding: 0.75rem;
  text-align: left;
  font-weight: 600;
  border-bottom: 2px solid #dee2e6;
}

.endpoints-table td {
  padding: 0.75rem;
  border-bottom: 1px solid #dee2e6;
}

.endpoints-table tr:hover {
  background: #f8f9fa;
}

.id-cell {
  font-family: monospace;
  font-size: 0.9rem;
}

.env-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
}

.env-dev {
  background: #d1ecf1;
  color: #0c5460;
}

.env-stg {
  background: #fff3cd;
  color: #856404;
}

.env-prod {
  background: #d4edda;
  color: #155724;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: capitalize;
}

.status-deploying {
  background: #d1ecf1;
  color: #0c5460;
}

.status-healthy {
  background: #d4edda;
  color: #155724;
}

.status-degraded {
  background: #fff3cd;
  color: #856404;
}

.status-failed {
  background: #f8d7da;
  color: #721c24;
}

.btn-link {
  color: #007bff;
  text-decoration: none;
  margin-right: 0.5rem;
}

.btn-link:hover {
  text-decoration: underline;
}

.btn-chat {
  color: #28a745;
}

.btn-delete-small {
  padding: 0.25rem 0.5rem;
  background: #dc3545;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.85rem;
  margin-left: 0.5rem;
}

.btn-delete-small:hover:not(:disabled) {
  background: #c82333;
}

.btn-delete-small:disabled {
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

