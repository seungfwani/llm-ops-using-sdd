<template>
  <section class="dataset-version-compare">
    <div class="catalog-tabs">
      <router-link to="/catalog/models" class="tab-link" active-class="active">Models</router-link>
      <router-link to="/catalog/datasets" class="tab-link" active-class="active">Datasets</router-link>
    </div>
    <header>
      <h1>Dataset Version Compare</h1>
      <router-link :to="`/catalog/datasets/${datasetId}`" class="btn-back">← Back to Dataset</router-link>
    </header>

    <div v-if="loading" class="loading">Loading versions...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <div v-else>
      <div class="version-selectors" v-if="versions.length >= 2">
        <label>
          Base Version
          <select v-model="baseVersionId">
            <option v-for="version in versions" :key="version.id" :value="version.id">
              {{ version.version_tag || version.version_id.slice(0, 8) }} — {{ formatDate(version.created_at) }}
            </option>
          </select>
        </label>
        <label>
          Target Version
          <select v-model="targetVersionId">
            <option v-for="version in versions" :key="version.id" :value="version.id">
              {{ version.version_tag || version.version_id.slice(0, 8) }} — {{ formatDate(version.created_at) }}
            </option>
          </select>
        </label>
        <button class="btn-primary" @click="loadDiff" :disabled="!baseVersionId || !targetVersionId || diffLoading">
          {{ diffLoading ? "Comparing..." : "Compare Versions" }}
        </button>
      </div>
      <p v-else class="empty">At least two versions are required to compare.</p>

      <div v-if="diffError" class="error">{{ diffError }}</div>

      <div v-if="diff" class="diff-results">
        <h2>Diff Summary</h2>
        <div class="diff-grid">
          <div class="diff-card">
            <h3>Files</h3>
            <p><strong>Added:</strong> {{ diff.added_files.length }}</p>
            <p><strong>Removed:</strong> {{ diff.removed_files.length }}</p>
            <p><strong>Modified:</strong> {{ diff.modified_files.length }}</p>
          </div>
          <div class="diff-card">
            <h3>Rows</h3>
            <p><strong>Added Rows:</strong> {{ diff.added_rows }}</p>
            <p><strong>Removed Rows:</strong> {{ diff.removed_rows }}</p>
          </div>
        </div>

        <div class="diff-section" v-if="diff.added_files.length">
          <h3>Added Files</h3>
          <ul>
            <li v-for="file in diff.added_files" :key="`added-${file}`">{{ file }}</li>
          </ul>
        </div>

        <div class="diff-section" v-if="diff.removed_files.length">
          <h3>Removed Files</h3>
          <ul>
            <li v-for="file in diff.removed_files" :key="`removed-${file}`">{{ file }}</li>
          </ul>
        </div>

        <div class="diff-section" v-if="diff.modified_files.length">
          <h3>Modified Files</h3>
          <ul>
            <li v-for="file in diff.modified_files" :key="`modified-${file}`">{{ file }}</li>
          </ul>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref, computed } from "vue";
import { useRoute } from "vue-router";
import {
  catalogClient,
  type DatasetVersion,
  type DatasetVersionDiff,
} from "@/services/catalogClient";

const route = useRoute();
const datasetId = computed(() => route.params.id as string);

const versions = ref<DatasetVersion[]>([]);
const loading = ref(false);
const error = ref("");

const baseVersionId = ref<string>("");
const targetVersionId = ref<string>("");

const diff = ref<DatasetVersionDiff | null>(null);
const diffLoading = ref(false);
const diffError = ref("");

function formatDate(value: string): string {
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

async function loadVersions() {
  loading.value = true;
  error.value = "";
  try {
    const response = await catalogClient.listDatasetVersions(datasetId.value);
    if (response.status === "success" && response.data) {
      const list = Array.isArray(response.data) ? response.data : [response.data];
      versions.value = list;
      if (list.length >= 2) {
        baseVersionId.value = list[list.length - 1].id; // oldest
        targetVersionId.value = list[0].id; // newest
      }
    } else {
      error.value = response.message || "Failed to load dataset versions";
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : "Failed to load dataset versions";
  } finally {
    loading.value = false;
  }
}

async function loadDiff() {
  if (!baseVersionId.value || !targetVersionId.value) return;
  diffLoading.value = true;
  diffError.value = "";
  diff.value = null;
  try {
    const response = await catalogClient.getDatasetVersionDiff(
      datasetId.value,
      targetVersionId.value,
      baseVersionId.value
    );
    if (response.status === "success" && response.data) {
      diff.value = response.data;
    } else {
      diffError.value = response.message || "Failed to calculate diff";
    }
  } catch (err) {
    diffError.value = err instanceof Error ? err.message : "Failed to calculate diff";
  } finally {
    diffLoading.value = false;
  }
}

onMounted(async () => {
  await loadVersions();
});
</script>

<style scoped>
.dataset-version-compare {
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

.btn-back {
  color: #007bff;
  text-decoration: none;
  font-weight: 500;
}

.version-selectors {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem;
  align-items: flex-end;
  margin-bottom: 2rem;
}

.version-selectors label {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.version-selectors select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.btn-primary {
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
}

.btn-primary:disabled {
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

.diff-results {
  margin-top: 2rem;
}

.diff-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.diff-card {
  background: white;
  padding: 1rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.diff-section {
  margin-top: 1rem;
}

.diff-section ul {
  padding-left: 1.5rem;
}
</style>


