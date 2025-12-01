<template>
  <div class="policy-list">
    <h1>Governance Policies</h1>
    <div class="filters">
      <select v-model="filterScope" @change="loadPolicies">
        <option value="">All Scopes</option>
        <option value="catalog">Catalog</option>
        <option value="training">Training</option>
        <option value="serving">Serving</option>
        <option value="global">Global</option>
      </select>
      <select v-model="filterStatus" @change="loadPolicies">
        <option value="">All Statuses</option>
        <option value="draft">Draft</option>
        <option value="active">Active</option>
        <option value="deprecated">Deprecated</option>
      </select>
      <button @click="goToCreatePolicy">Create Policy</button>
    </div>
    <div v-if="loading">Loading...</div>
    <div v-else-if="error">{{ error }}</div>
    <table v-else>
      <thead>
        <tr>
          <th>Name</th>
          <th>Scope</th>
          <th>Status</th>
          <th>Last Reviewed</th>
          <th>Created</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="policy in policies" :key="policy.id">
          <td>{{ policy.name }}</td>
          <td>{{ policy.scope }}</td>
          <td>{{ policy.status }}</td>
          <td>{{ formatDate(policy.lastReviewedAt) }}</td>
          <td>{{ formatDate(policy.createdAt) }}</td>
          <td>
            <router-link :to="`/governance/policies/${policy.id}`">View</router-link>
          </td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import { governanceClient, type GovernancePolicy } from "@/services/governanceClient";

const router = useRouter();
const policies = ref<GovernancePolicy[]>([]);
const loading = ref(true);
const error = ref("");
const filterScope = ref("");
const filterStatus = ref("");

onMounted(() => {
  loadPolicies();
});

async function loadPolicies() {
  loading.value = true;
  error.value = "";
  try {
    const response = await governanceClient.listPolicies(
      filterScope.value || undefined,
      filterStatus.value || undefined
    );
    if (response.status === "success" && Array.isArray(response.data)) {
      policies.value = response.data;
    } else {
      error.value = response.message || "Failed to load policies";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    loading.value = false;
  }
}

function goToCreatePolicy() {
  router.push("/governance/policies/new");
}

function formatDate(dateStr?: string): string {
  if (!dateStr) return "N/A";
  return new Date(dateStr).toLocaleString();
}
</script>

<style scoped>
.policy-list {
  padding: 20px;
}
.filters {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}
select {
  padding: 8px;
}
button {
  padding: 8px 16px;
  background: #007bff;
  color: white;
  border: none;
  cursor: pointer;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  padding: 10px;
  text-align: left;
  border-bottom: 1px solid #ddd;
}
th {
  background-color: #f5f5f5;
}
</style>

