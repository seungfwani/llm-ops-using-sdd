<template>
  <div class="prompt-create">
    <h1>프롬프트 템플릿 등록</h1>
    <form @submit.prevent="handleSubmit">
      <div class="form-row">
        <label>이름</label>
        <input v-model="form.name" required />
      </div>
      <div class="form-row">
        <label>버전</label>
        <input v-model="form.version" required />
      </div>
      <div class="form-row">
        <label>언어</label>
        <input v-model="form.language" />
      </div>
      <div class="form-row">
        <label>카테고리 태그(쉼표로 구분)</label>
        <input v-model="tagStr" placeholder="예시: chat,summarization" />
      </div>
      <div class="form-row">
        <label>상태</label>
        <select v-model="form.status">
          <option value="draft">임시</option>
          <option value="live">Live</option>
        </select>
      </div>
      <div class="form-row">
        <label>프롬프트 내용</label>
        <textarea v-model="form.content" rows="7" required />
      </div>
      <button type="submit">등록</button>
      <button type="button" @click="router.back()">취소</button>
    </form>
    <div v-if="errorMsg" class="error-msg">{{ errorMsg }}</div>
  </div>
</template>

<script lang="ts" setup>
import { reactive, ref } from 'vue';
import { PromptTemplateCreate, createPromptTemplate } from '@/services/prompts';
import { useRouter } from 'vue-router';

const form = reactive<PromptTemplateCreate>({
  name: '',
  version: '',
  language: '',
  content: '',
  context_tags: [],
  status: 'draft',
});
const tagStr = ref('');
const errorMsg = ref('');
const router = useRouter();

async function handleSubmit() {
  form.context_tags = tagStr.value.split(',').map(s => s.trim()).filter(Boolean);
  try {
    await createPromptTemplate(form);
    router.push({ name: 'PromptList' });
  } catch (e) {
    errorMsg.value = '생성 실패';
  }
}
</script>

<style scoped>
.prompt-create { max-width: 500px; margin: 0 auto; }
.form-row { margin-bottom: 15px; display: flex; gap: 8px; align-items: center; }
label { width: 120px; font-weight: bold; }
input, textarea, select {
  flex: 1;
  padding: 8px;
  border: 1px solid #bbb;
  border-radius: 4px;
}
button[type="submit"] { background: #1976d2; color: #fff; margin-right: 8px; padding: 8px 20px; border: none; border-radius: 4px; }
button[type="button"] { background: #ccc; color: #222; padding: 8px 20px; border: none; border-radius: 4px; }
.error-msg { color: #e53935; margin-top: 10px; }
</style>

