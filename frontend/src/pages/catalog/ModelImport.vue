<template>
  <section class="model-import">
    <div class="catalog-tabs">
      <router-link to="/catalog/models" class="tab-link" active-class="active">Models</router-link>
      <router-link to="/catalog/datasets" class="tab-link" active-class="active">Datasets</router-link>
    </div>
    <header>
      <h1>Import Model from Registry</h1>
      <router-link to="/catalog/models" class="btn-back">← Back to Catalog</router-link>
    </header>

    <div class="import-card">
      <form @submit.prevent="handleImport">
        <div class="form-group">
          <label for="registryType">Registry</label>
          <select id="registryType" v-model="form.registry_type" required>
            <option value="huggingface">Hugging Face Hub</option>
          </select>
        </div>

        <div class="form-group">
          <label for="registryModelId">Registry Model ID</label>
          <input
            id="registryModelId"
            v-model="form.registry_model_id"
            type="text"
            required
            placeholder="e.g., microsoft/DialoGPT-medium"
          />
          <small class="help-text">
            Enter the model identifier from the selected registry.
          </small>
        </div>

        <div class="form-group">
          <label for="version">Registry Version (optional)</label>
          <input
            id="version"
            v-model="form.version"
            type="text"
            placeholder="e.g., main or specific commit/tag"
          />
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="name">Catalog Name (optional)</label>
            <input
              id="name"
              v-model="form.name"
              type="text"
              placeholder="Defaults to last segment of registry model ID"
            />
          </div>
          <div class="form-group">
            <label for="modelVersion">Catalog Version</label>
            <input
              id="modelVersion"
              v-model="form.model_version"
              type="text"
              required
            />
          </div>
        </div>

        <div class="form-row">
          <div class="form-group">
            <label for="modelType">Model Type</label>
            <select id="modelType" v-model="form.model_type" required>
              <option value="base">Base</option>
              <option value="fine-tuned">Fine-tuned</option>
              <option value="external">External</option>
            </select>
          </div>
          <div class="form-group">
            <label for="ownerTeam">Owner Team</label>
            <input
              id="ownerTeam"
              v-model="form.owner_team"
              type="text"
              required
            />
          </div>
        </div>

        <div v-if="error" class="error">{{ error }}</div>
        <div v-if="successMessage" class="success">{{ successMessage }}</div>

        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? 'Importing...' : 'Import Model' }}
        </button>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { catalogClient } from '@/services/catalogClient';

const router = useRouter();

const form = reactive({
  registry_type: 'huggingface',
  registry_model_id: '',
  version: '',
  name: '',
  model_version: '1.0.0',
  model_type: 'base',
  owner_team: 'ml-platform',
});

const loading = ref(false);
const error = ref('');
const successMessage = ref('');

async function handleImport() {
  error.value = '';
  successMessage.value = '';

  if (!form.registry_model_id) {
    error.value = 'Registry model ID is required';
    return;
  }

  loading.value = true;
  try {
    const response = await catalogClient.importFromRegistry({
      registry_type: form.registry_type,
      registry_model_id: form.registry_model_id,
      version: form.version || undefined,
      name: form.name || undefined,
      model_version: form.model_version,
      model_type: form.model_type,
      owner_team: form.owner_team,
    });

    if (response.status === 'success' && response.data) {
      const model = Array.isArray(response.data) ? response.data[0] : response.data;
      successMessage.value = 'Model imported successfully from registry';
      // 잠시 성공 메시지를 보여준 뒤 상세 페이지로 이동
      setTimeout(() => {
        router.push(`/catalog/models/${model.id}`);
      }, 800);
    } else {
      error.value = response.message || 'Import failed';
    }
  } catch (e) {
    error.value = `Error: ${e}`;
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.model-import {
  padding: 2rem;
  max-width: 800px;
  margin: 0 auto;
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

.btn-back {
  padding: 0.5rem 1rem;
  background: #6c757d;
  color: white;
  text-decoration: none;
  border-radius: 4px;
}

.btn-back:hover {
  background: #5a6268;
}

.import-card {
  background: white;
  padding: 1.5rem;
  border-radius: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.form-group {
  margin-bottom: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.form-row {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 1rem;
}

label {
  font-weight: 600;
}

input,
select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.help-text {
  font-size: 0.85rem;
  color: #6c757d;
}

.btn-primary {
  padding: 0.5rem 1.25rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.btn-primary:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.btn-primary:hover:not(:disabled) {
  background: #0056b3;
}

.error {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #f8d7da;
  color: #721c24;
  border-radius: 4px;
}

.success {
  margin-bottom: 1rem;
  padding: 0.75rem;
  background: #d4edda;
  color: #155724;
  border-radius: 4px;
}
</style>


