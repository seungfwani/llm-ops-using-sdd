<template>
  <div class="prompt-list">
    <h1>프롬프트 템플릿 목록</h1>
    <div class="actions">
      <router-link :to="{ name: 'PromptCreate' }" class="create-btn">+ 새 템플릿 등록</router-link>
    </div>
    <table v-if="prompts.length" class="prompt-table">
      <thead>
        <tr>
          <th>이름</th>
          <th>버전</th>
          <th>언어</th>
          <th>상태</th>
          <th>최근 수정</th>
          <th>관리</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="prompt in prompts" :key="prompt.id">
          <td>{{ prompt.name }}</td>
          <td>{{ prompt.version }}</td>
          <td>{{ prompt.language || '-' }}</td>
          <td>{{ prompt.status }}</td>
          <td>{{ formatDate(prompt.updated_at) }}</td>
          <td>
            <router-link :to="{ name: 'PromptDetail', params: { id: prompt.id } }">상세</router-link>
            <button class="delete-btn" @click="deletePrompt(prompt.id)">삭제</button>
          </td>
        </tr>
      </tbody>
    </table>
    <div v-else>
      <p>등록된 프롬프트 템플릿이 없습니다.</p>
    </div>
    <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted } from 'vue';
import { fetchPromptTemplates, deletePromptTemplate, PromptTemplate } from '@/services/prompts';
import { useRouter } from 'vue-router';

const prompts = ref<PromptTemplate[]>([]);
const errorMsg = ref('');
const router = useRouter();

function formatDate(date: string) {
  return new Date(date).toLocaleString();
}

async function loadPrompts() {
  try {
    prompts.value = await fetchPromptTemplates();
    errorMsg.value = '';
  } catch (e) {
    errorMsg.value = '프롬프트 목록 조회 실패';
  }
}

async function deletePrompt(id: string) {
  if (!confirm('정말로 삭제하시겠습니까?')) return;
  try {
    await deletePromptTemplate(id);
    prompts.value = prompts.value.filter(p => p.id !== id);
  } catch (e) {
    errorMsg.value = '삭제 실패';
  }
}

onMounted(() => {
  loadPrompts();
});
</script>

<style scoped>
.prompt-list { max-width: 900px; margin: 0 auto; }
.actions { margin-bottom: 20px; }
.create-btn {
  padding: 8px 15px;
  background: #2196f3;
  color: #fff;
  border-radius: 4px;
  text-decoration: none;
}
.prompt-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
.prompt-table th, .prompt-table td { border: 1px solid #ccc; padding: 10px; text-align: left; }
.delete-btn { background: #ff4d4f; color: #fff; border: none; padding: 6px 14px; border-radius: 3px; margin-left: 5px; cursor: pointer; }
.error-msg { color: #e53935; margin-top: 10px; }
</style>

