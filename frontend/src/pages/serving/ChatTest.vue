<template>
  <section class="chat-test">
    <header>
      <h1>Chat with Serving Model</h1>
    </header>

    <div class="chat-container">
      <!-- Endpoint Selection -->
      <div class="endpoint-selector">
        <label>
          <strong>Select Endpoint:</strong>
          <select v-model="selectedEndpointId" @change="onEndpointChange" :disabled="loadingEndpoints">
            <option value="">-- Select an endpoint --</option>
            <option v-for="endpoint in endpoints" :key="endpoint.id" :value="endpoint.id">
              {{ getRouteName(endpoint.route) }} ({{ endpoint.environment }})
            </option>
          </select>
        </label>
        <button @click="fetchEndpoints" :disabled="loadingEndpoints" class="btn-refresh">
          {{ loadingEndpoints ? 'Loading...' : 'Refresh' }}
        </button>
      </div>

      <!-- Endpoint Info -->
      <div v-if="selectedEndpoint" class="endpoint-info">
        <div class="info-item">
          <span class="label">Route:</span>
          <span class="value monospace">{{ selectedEndpoint.route }}</span>
        </div>
        <div class="info-item">
          <span class="label">Environment:</span>
          <span class="value">{{ selectedEndpoint.environment.toUpperCase() }}</span>
        </div>
        <div class="info-item">
          <span class="label">Status:</span>
          <span :class="`status-badge status-${selectedEndpoint.status}`">
            {{ selectedEndpoint.status }}
          </span>
        </div>
      </div>

      <!-- Chat Messages -->
      <div class="chat-messages" ref="messagesContainer">
        <div v-if="messages.length === 0" class="empty-state">
          <p>Start a conversation with the model by typing a message below.</p>
        </div>
        <div
          v-for="(message, index) in messages"
          :key="index"
          :class="['message', `message-${message.role}`]"
        >
          <div class="message-role">{{ message.role === 'user' ? 'You' : 'Assistant' }}</div>
          <div class="message-content">{{ message.content }}</div>
          <div v-if="message.timestamp" class="message-timestamp">
            {{ formatTime(message.timestamp) }}
          </div>
        </div>
        <div v-if="isLoading" class="message message-assistant">
          <div class="message-role">Assistant</div>
          <div class="message-content loading-indicator">
            <span class="dot"></span>
            <span class="dot"></span>
            <span class="dot"></span>
          </div>
        </div>
      </div>

      <!-- Chat Input -->
      <div class="chat-input-container">
        <div class="input-controls">
          <label>
            Temperature:
            <input
              v-model.number="temperature"
              type="number"
              min="0"
              max="2"
              step="0.1"
              class="input-small"
            />
          </label>
          <label>
            Max Tokens:
            <input
              v-model.number="maxTokens"
              type="number"
              min="1"
              max="4000"
              step="100"
              class="input-small"
            />
          </label>
          <button @click="clearChat" class="btn-clear">Clear Chat</button>
        </div>
        <div class="input-wrapper">
          <textarea
            v-model="inputMessage"
            @keydown.enter.prevent="handleEnter"
            @keydown.shift.enter="handleShiftEnter"
            placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
            rows="3"
            class="chat-input"
            :disabled="!selectedEndpoint || isLoading || selectedEndpoint?.status !== 'healthy'"
          ></textarea>
          <button
            @click="sendMessage"
            :disabled="!canSend"
            class="btn-send"
          >
            {{ isLoading ? 'Sending...' : 'Send' }}
          </button>
        </div>
        <div v-if="selectedEndpoint?.status !== 'healthy'" class="error-message">
          ⚠️ This endpoint is not healthy. Chat is disabled.
        </div>
        <div v-if="error" class="error-message">{{ error }}</div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch, nextTick } from 'vue';
import { useRoute } from 'vue-router';
import { servingClient, type ServingEndpoint, type ChatMessage, type ChatOptions } from '@/services/servingClient';

const route = useRoute();
const endpoints = ref<ServingEndpoint[]>([]);
const selectedEndpointId = ref<string>('');
const selectedEndpoint = ref<ServingEndpoint | null>(null);
const loadingEndpoints = ref(false);
const messages = ref<Array<ChatMessage & { timestamp?: Date }>>([]);
const inputMessage = ref('');
const isLoading = ref(false);
const error = ref('');
const temperature = ref(0.7);
const maxTokens = ref(500);
const messagesContainer = ref<HTMLElement | null>(null);

const canSend = computed(() => {
  return (
    selectedEndpoint.value &&
    selectedEndpoint.value.status === 'healthy' &&
    inputMessage.value.trim().length > 0 &&
    !isLoading.value
  );
});

onMounted(() => {
  fetchEndpoints();
  
  // Check if endpoint ID is provided in route params
  const endpointId = route.params.endpointId as string;
  if (endpointId) {
    selectedEndpointId.value = endpointId;
  }
});

watch(selectedEndpointId, () => {
  if (selectedEndpointId.value) {
    loadEndpoint();
  } else {
    selectedEndpoint.value = null;
    messages.value = [];
  }
});

async function fetchEndpoints() {
  loadingEndpoints.value = true;
  error.value = '';
  try {
    const response = await servingClient.listEndpoints({ status: 'healthy' });
    if (response.status === 'success' && response.data) {
      endpoints.value = response.data;
      
      // If endpoint ID from route exists, select it
      const endpointId = route.params.endpointId as string;
      if (endpointId && !selectedEndpointId.value) {
        const found = endpoints.value.find(e => e.id === endpointId);
        if (found) {
          selectedEndpointId.value = endpointId;
        }
      }
    } else {
      error.value = response.message || 'Failed to load endpoints';
    }
  } catch (e) {
    error.value = `Error loading endpoints: ${e}`;
    console.error('Failed to fetch endpoints:', e);
  } finally {
    loadingEndpoints.value = false;
  }
}

async function loadEndpoint() {
  if (!selectedEndpointId.value) return;
  
  try {
    const response = await servingClient.getEndpoint(selectedEndpointId.value);
    if (response.status === 'success' && response.data) {
      selectedEndpoint.value = response.data;
      // Clear messages when switching endpoints
      messages.value = [];
    } else {
      error.value = response.message || 'Failed to load endpoint details';
    }
  } catch (e) {
    error.value = `Error loading endpoint: ${e}`;
    console.error('Failed to load endpoint:', e);
  }
}

function onEndpointChange() {
  loadEndpoint();
}

function getRouteName(route: string): string {
  // Extract model name from route like "/llm-ops/v1/serve/chat-model" -> "chat-model"
  const match = route.match(/\/([^/]+)$/);
  return match ? match[1] : route;
}

async function sendMessage() {
  if (!canSend.value || !selectedEndpoint.value) return;

  const userMessage = inputMessage.value.trim();
  if (!userMessage) return;

  // Add user message
  messages.value.push({
    role: 'user',
    content: userMessage,
    timestamp: new Date(),
  });

  const currentInput = userMessage;
  inputMessage.value = '';
  isLoading.value = true;
  error.value = '';

  // Scroll to bottom
  await nextTick();
  scrollToBottom();

  try {
    // Prepare messages for API (include system message if not present)
    const apiMessages: ChatMessage[] = [
      { role: 'system', content: 'You are a helpful assistant.' },
      ...messages.value
        .filter(m => m.role !== 'system')
        .map(m => ({ role: m.role, content: m.content })),
    ];

    const routeName = getRouteName(selectedEndpoint.value.route);
    const options: ChatOptions = {
      temperature: temperature.value,
      max_tokens: maxTokens.value,
    };

    const response = await servingClient.chatCompletion(routeName, apiMessages, options);

    if (response.status === 'success' && response.data?.choices?.[0]) {
      const assistantMessage = response.data.choices[0].message.content;
      messages.value.push({
        role: 'assistant',
        content: assistantMessage,
        timestamp: new Date(),
      });
    } else {
      error.value = response.message || 'Failed to get response from model';
      // Show error as a message
      messages.value.push({
        role: 'assistant',
        content: `Error: ${error.value}`,
        timestamp: new Date(),
      });
    }
  } catch (e: any) {
    const errorMsg = e.response?.data?.message || e.message || 'Failed to send message';
    error.value = errorMsg;
    console.error('Chat error:', e);
    
    // Show error as a message
    messages.value.push({
      role: 'assistant',
      content: `Error: ${errorMsg}`,
      timestamp: new Date(),
    });
  } finally {
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
}

function handleEnter() {
  if (!event?.shiftKey) {
    sendMessage();
  }
}

function handleShiftEnter() {
  // Allow new line on Shift+Enter
  // The default behavior is already handled
}

function clearChat() {
  messages.value = [];
  error.value = '';
}

function scrollToBottom() {
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
}

function formatTime(date: Date): string {
  return date.toLocaleTimeString();
}
</script>

<style scoped>
.chat-test {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding: 2rem;
  max-width: 1200px;
  margin: 0 auto;
}

header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

header h1 {
  margin: 0;
}

.btn-back {
  padding: 0.5rem 1rem;
  background: #6c757d;
  color: white;
  text-decoration: none;
  border-radius: 4px;
  font-size: 0.9rem;
}

.btn-back:hover {
  background: #5a6268;
}

.chat-container {
  display: flex;
  flex-direction: column;
  flex: 1;
  border: 1px solid #ddd;
  border-radius: 8px;
  background: white;
  overflow: hidden;
}

.endpoint-selector {
  padding: 1rem;
  border-bottom: 1px solid #ddd;
  display: flex;
  gap: 1rem;
  align-items: center;
  background: #f8f9fa;
}

.endpoint-selector label {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.endpoint-selector select {
  padding: 0.5rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
}

.btn-refresh {
  padding: 0.5rem 1rem;
  background: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  height: fit-content;
}

.btn-refresh:hover:not(:disabled) {
  background: #0056b3;
}

.btn-refresh:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.endpoint-info {
  padding: 1rem;
  border-bottom: 1px solid #ddd;
  background: #f8f9fa;
  display: flex;
  gap: 2rem;
  flex-wrap: wrap;
}

.info-item {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.info-item .label {
  font-weight: 600;
  color: #666;
}

.info-item .value {
  color: #333;
}

.monospace {
  font-family: monospace;
  font-size: 0.9rem;
  background: white;
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
}

.status-badge {
  padding: 0.25rem 0.5rem;
  border-radius: 4px;
  font-size: 0.85rem;
  font-weight: 600;
  text-transform: capitalize;
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

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  background: #fafafa;
}

.empty-state {
  text-align: center;
  color: #666;
  padding: 3rem;
}

.message {
  display: flex;
  flex-direction: column;
  max-width: 80%;
  padding: 0.75rem 1rem;
  border-radius: 8px;
}

.message-user {
  align-self: flex-end;
  background: #007bff;
  color: white;
}

.message-assistant {
  align-self: flex-start;
  background: white;
  border: 1px solid #ddd;
}

.message-role {
  font-size: 0.75rem;
  font-weight: 600;
  margin-bottom: 0.25rem;
  opacity: 0.8;
}

.message-content {
  white-space: pre-wrap;
  word-wrap: break-word;
  line-height: 1.5;
}

.message-timestamp {
  font-size: 0.7rem;
  margin-top: 0.25rem;
  opacity: 0.6;
}

.loading-indicator {
  display: flex;
  gap: 0.25rem;
  align-items: center;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #007bff;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) {
  animation-delay: -0.32s;
}

.dot:nth-child(2) {
  animation-delay: -0.16s;
}

@keyframes bounce {
  0%, 80%, 100% {
    transform: scale(0);
  }
  40% {
    transform: scale(1);
  }
}

.chat-input-container {
  padding: 1rem;
  border-top: 1px solid #ddd;
  background: white;
}

.input-controls {
  display: flex;
  gap: 1rem;
  margin-bottom: 0.5rem;
  align-items: center;
  flex-wrap: wrap;
}

.input-controls label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.9rem;
}

.input-small {
  width: 80px;
  padding: 0.25rem;
  border: 1px solid #ddd;
  border-radius: 4px;
}

.btn-clear {
  padding: 0.5rem 1rem;
  background: #6c757d;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 0.9rem;
}

.btn-clear:hover {
  background: #5a6268;
}

.input-wrapper {
  display: flex;
  gap: 0.5rem;
  align-items: flex-end;
}

.chat-input {
  flex: 1;
  padding: 0.75rem;
  border: 1px solid #ddd;
  border-radius: 4px;
  font-size: 1rem;
  font-family: inherit;
  resize: none;
}

.chat-input:disabled {
  background: #f5f5f5;
  cursor: not-allowed;
}

.btn-send {
  padding: 0.75rem 2rem;
  background: #28a745;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
  font-weight: 600;
  height: fit-content;
}

.btn-send:hover:not(:disabled) {
  background: #218838;
}

.btn-send:disabled {
  background: #ccc;
  cursor: not-allowed;
}

.error-message {
  margin-top: 0.5rem;
  padding: 0.5rem;
  background: #f8d7da;
  color: #721c24;
  border-radius: 4px;
  font-size: 0.9rem;
}
</style>
