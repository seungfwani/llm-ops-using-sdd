<template>
  <div class="prompt-detail" v-if="prompt">
    <h1>프롬프트 템플릿 상세/수정</h1>
    <form @submit.prevent="handleUpdate">
      <div class="form-row">
        <label>이름</label>
        <input v-model="editForm.name" required />
      </div>
      <div class="form-row">
        <label>버전</label>
        <input v-model="editForm.version" required />
      </div>
      <div class="form-row">
        <label>언어</label>
        <input v-model="editForm.language" />
      </div>
      <div class="form-row">
        <label>카테고리 태그(쉼표로 구분)</label>
        <input v-model="tagStr" placeholder="예시: chat,summarization" />
      </div>
      <div class="form-row">
        <label>상태</label>
        <select v-model="editForm.status">
          <option value="draft">임시</option>
          <option value="live">Live</option>
        </select>
      </div>
      <div class="form-row">
        <label>프롬프트 내용</label>
        <textarea v-model="editForm.content" rows="7" required />
      </div>
      <div>
        <button type="submit">수정</button>
        <button type="button" @click="handleDelete">삭제</button>
        <button type="button" @click="router.back()">뒤로</button>
      </div>
    </form>
    <div class="meta">생성일: {{ formatDate(prompt.created_at) }}, 최근수정: {{ formatDate(prompt.updated_at) }}</div>
    <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
  </div>
  <div v-else class="not-found">프롬프트 템플릿을 찾을 수 없습니다.</div>
</template>

<script lang="ts" setup>
import { ref, reactive, onMounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { fetchPromptTemplate, updatePromptTemplate, deletePromptTemplate, PromptTemplateUpdate, PromptTemplate } from '@/services/prompts';

const route = useRoute();
const router = useRouter();
const prompt = ref<PromptTemplate | null>(null);
const editForm = reactive<PromptTemplateUpdate>({});
const tagStr = ref('');
const errorMsg = ref('');

function formatDate(date: string) {
  return new Date(date).toLocaleString();
}

async function loadPrompt() {
  try {
    const data = await fetchPromptTemplate(route.params.id as string);
    prompt.value = data;
    if (data) {
      editForm.name = data.name;
      editForm.version = data.version;
      editForm.language = data.language;
      editForm.content = data.content;
      editForm.context_tags = data.context_tags || [];
      editForm.status = data.status;
      tagStr.value = (data.context_tags || []).join(',');
    }
  } catch(e) {
    prompt.value = null;
  }
}

async function handleUpdate() {
  editForm.context_tags = tagStr.value.split(',').map(s => s.trim()).filter(Boolean);
  try {
    if (!prompt.value) return;
    await updatePromptTemplate(prompt.value.id, editForm);
    errorMsg.value = '';
    window.alert('수정 완료!');
    await loadPrompt();
  } catch(e) {
    errorMsg.value = '수정 실패';
  }
}

async function handleDelete() {
  if (!prompt.value) return;
  if (!confirm('정말로 삭제하시겠습니까?')) return;
  try {
    await deletePromptTemplate(prompt.value.id);
    errorMsg.value = '';
    router.push({ name: 'PromptList' });
  } catch(e) {
    errorMsg.value = '삭제 실패';
  }
}

onMounted(() => {
  loadPrompt();
});
</script>

<style scoped>
.prompt-detail { max-width: 500px; margin: 0 auto; }
.form-row { margin-bottom: 15px; display: flex; gap: 8px; align-items: center; }
label { width: 120px; font-weight: bold; }
input, textarea, select {
  flex: 1;
  padding: 8px;
  border: 1px solid #bbb;
  border-radius: 4px;
}
button { margin-right: 8px; }
button[type="submit"] { background: #1976d2; color: #fff; border: none; border-radius: 4px; padding: 7px 18px; }
button[type="button"] { background: #ccc; color: #222; padding: 7px 18px; border: none; border-radius: 4px; }
.meta { margin-top: 10px; color: #666; font-size: 0.9em; }
.error-msg { color: #e53935; margin-top: 10px; }
.not-found { text-align: center; color: #888; margin-top: 40px; }
</style>

