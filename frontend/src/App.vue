<template>
  <div id="app">
    <nav>
      <router-link to="/catalog/models">Models</router-link> |
      <router-link to="/catalog/datasets">Datasets</router-link> |
      <router-link to="/training/jobs">Training</router-link> |
      <router-link to="/serving/endpoints">Serving</router-link> |
      <router-link to="/governance/policies">Governance</router-link>
    </nav>
    <main>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
// App component
</script>

<style>
#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}

nav {
  padding: 20px;
  background-color: #f5f5f5;
  border-bottom: 1px solid #ddd;
}

nav a {
  font-weight: bold;
  color: #2c3e50;
  text-decoration: none;
  margin: 0 10px;
}

nav a.router-link-exact-active {
  color: #42b983;
}

main {
  padding: 20px;
}
</style>

