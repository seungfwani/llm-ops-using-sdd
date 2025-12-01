<template>
  <div class="cost-dashboard">
    <h1>Cost Dashboard</h1>
    <div class="filters">
      <select v-model="filterResourceType" @change="loadData">
        <option value="">All Resources</option>
        <option value="training_job">Training Jobs</option>
        <option value="serving_endpoint">Serving Endpoints</option>
      </select>
      <input v-model="startDate" type="date" @change="loadData" />
      <input v-model="endDate" type="date" @change="loadData" />
      <button @click="loadData">Refresh</button>
    </div>
    <div v-if="loading">Loading...</div>
    <div v-else-if="error">{{ error }}</div>
    <div v-else class="dashboard-content">
      <div class="summary">
        <h2>Cost Summary</h2>
        <div class="metrics">
          <div class="metric">
            <label>Total Cost</label>
            <div class="value">${{ aggregate?.totalCost?.toFixed(2) || "0.00" }}</div>
          </div>
          <div class="metric">
            <label>GPU Hours</label>
            <div class="value">{{ aggregate?.totalGpuHours?.toFixed(2) || "0.00" }}</div>
          </div>
          <div class="metric">
            <label>Total Tokens</label>
            <div class="value">{{ aggregate?.totalTokens?.toLocaleString() || "0" }}</div>
          </div>
          <div class="metric">
            <label>Resources</label>
            <div class="value">{{ aggregate?.resourceCount || 0 }}</div>
          </div>
        </div>
      </div>
      <div class="profiles">
        <h2>Cost Profiles</h2>
        <table>
          <thead>
            <tr>
              <th>Resource Type</th>
              <th>Resource ID</th>
              <th>Time Window</th>
              <th>GPU Hours</th>
              <th>Tokens</th>
              <th>Cost</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="profile in profiles" :key="profile.id">
              <td>{{ profile.resourceType }}</td>
              <td>{{ profile.resourceId }}</td>
              <td>{{ profile.timeWindow }}</td>
              <td>{{ profile.gpuHours?.toFixed(2) || "N/A" }}</td>
              <td>{{ profile.tokenCount?.toLocaleString() || "N/A" }}</td>
              <td>${{ profile.costAmount?.toFixed(2) || "0.00" }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { governanceClient, type CostProfile, type CostAggregate } from "@/services/governanceClient";

const aggregate = ref<CostAggregate | null>(null);
const profiles = ref<CostProfile[]>([]);
const loading = ref(true);
const error = ref("");
const filterResourceType = ref("");
const startDate = ref("");
const endDate = ref("");

onMounted(() => {
  loadData();
});

async function loadData() {
  loading.value = true;
  error.value = "";
  try {
    // Load aggregate
    const aggregateRes = await governanceClient.getCostAggregate({
      resourceType: filterResourceType.value || undefined,
      startDate: startDate.value || undefined,
      endDate: endDate.value || undefined,
    });
    if (aggregateRes.status === "success" && aggregateRes.data) {
      aggregate.value = aggregateRes.data;
    }

    // Load profiles
    const profilesRes = await governanceClient.listCostProfiles({
      resourceType: filterResourceType.value || undefined,
    });
    if (profilesRes.status === "success" && Array.isArray(profilesRes.data)) {
      profiles.value = profilesRes.data;
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.cost-dashboard {
  padding: 20px;
}
.filters {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}
select,
input {
  padding: 8px;
}
button {
  padding: 8px 16px;
  background: #007bff;
  color: white;
  border: none;
  cursor: pointer;
}
.dashboard-content {
  display: flex;
  flex-direction: column;
  gap: 30px;
}
.summary {
  background: #f5f5f5;
  padding: 20px;
  border-radius: 5px;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 20px;
  margin-top: 15px;
}
.metric {
  text-align: center;
}
.metric label {
  display: block;
  font-size: 14px;
  color: #666;
  margin-bottom: 5px;
}
.metric .value {
  font-size: 24px;
  font-weight: bold;
  color: #007bff;
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

