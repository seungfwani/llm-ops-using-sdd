<template>
  <div class="audit-logs">
    <h1>Audit Logs</h1>
    <div class="filters">
      <input v-model="filterActorId" placeholder="Actor ID" @input="loadLogs" />
      <input v-model="filterResourceType" placeholder="Resource Type" @input="loadLogs" />
      <input v-model="filterAction" placeholder="Action" @input="loadLogs" />
      <input v-model.number="limit" type="number" min="1" max="1000" @input="loadLogs" />
    </div>
    <div v-if="loading">Loading...</div>
    <div v-else-if="error">{{ error }}</div>
    <table v-else>
      <thead>
        <tr>
          <th>Timestamp</th>
          <th>Actor</th>
          <th>Action</th>
          <th>Resource</th>
          <th>Result</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="log in logs" :key="log.id">
          <td>{{ formatDate(log.occurredAt) }}</td>
          <td>{{ log.actorId }}</td>
          <td>{{ log.action }}</td>
          <td>{{ log.resourceType }}{{ log.resourceId ? ` (${log.resourceId})` : "" }}</td>
          <td :class="log.result === 'denied' ? 'denied' : 'allowed'">{{ log.result }}</td>
        </tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from "vue";
import { governanceClient, type AuditLog } from "@/services/governanceClient";

const logs = ref<AuditLog[]>([]);
const loading = ref(true);
const error = ref("");
const filterActorId = ref("");
const filterResourceType = ref("");
const filterAction = ref("");
const limit = ref(100);

onMounted(() => {
  loadLogs();
});

async function loadLogs() {
  loading.value = true;
  error.value = "";
  try {
    const response = await governanceClient.listAuditLogs({
      actorId: filterActorId.value || undefined,
      resourceType: filterResourceType.value || undefined,
      action: filterAction.value || undefined,
      limit: limit.value,
    });
    if (response.status === "success" && Array.isArray(response.data)) {
      logs.value = response.data;
    } else {
      error.value = response.message || "Failed to load audit logs";
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    loading.value = false;
  }
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString();
}
</script>

<style scoped>
.audit-logs {
  padding: 20px;
}
.filters {
  margin-bottom: 20px;
  display: flex;
  gap: 10px;
}
input {
  padding: 8px;
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
.denied {
  color: red;
  font-weight: bold;
}
.allowed {
  color: green;
}
</style>

