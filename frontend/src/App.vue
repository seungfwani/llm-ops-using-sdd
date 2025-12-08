<template>
  <div id="app">
    <NavigationMenu />
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import NavigationMenu from '@/components/NavigationMenu.vue';
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}

main {
  padding: 20px;
}
</style>

