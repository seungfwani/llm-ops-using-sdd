<template>
  <nav class="navigation-menu" :class="{ 'mobile-open': isMobileMenuOpen }">
    <div class="nav-container">
      <!-- Mobile hamburger button -->
      <button
        class="mobile-toggle"
        @click="toggleMobileMenu"
        :aria-expanded="isMobileMenuOpen"
        aria-label="Toggle navigation menu"
        aria-controls="nav-menu"
      >
        <span class="hamburger-icon">
          <span></span>
          <span></span>
          <span></span>
        </span>
      </button>

      <!-- Navigation menu -->
      <ul id="nav-menu" class="nav-list" :class="{ 'mobile-open': isMobileMenuOpen }">
        <!-- Standalone items -->
        <li
          v-for="item in standaloneItems"
          :key="item.path"
          class="nav-item standalone"
        >
          <router-link
            :to="item.path"
            class="nav-link"
            :class="{ active: isRouteActive($route, item.path) }"
            @click="closeMobileMenu"
          >
            {{ item.label }}
          </router-link>
        </li>

        <!-- Dropdown groups -->
        <li
          v-for="group in navigationGroups"
          :key="group.label"
          class="nav-item dropdown"
          :class="{ 'dropdown-open': openDropdown === group.label }"
        >
          <button
            class="nav-link dropdown-trigger"
            :class="{
              active: findActiveGroup($route) === group.label,
            }"
            @click="toggleDropdown(group.label)"
            @keydown.enter="toggleDropdown(group.label)"
            @keydown.space.prevent="toggleDropdown(group.label)"
            :aria-expanded="openDropdown === group.label"
            :aria-haspopup="true"
            :aria-controls="`dropdown-${group.label}`"
          >
            {{ group.label }}
            <span class="dropdown-arrow" :class="{ open: openDropdown === group.label }">
              ▼
            </span>
          </button>
          <ul
            :id="`dropdown-${group.label}`"
            class="dropdown-menu"
            :class="{ open: openDropdown === group.label }"
            role="menu"
          >
            <li
              v-for="item in group.items"
              :key="item.path"
              role="menuitem"
            >
              <router-link
                :to="item.path"
                class="dropdown-item"
                :class="{ active: isRouteActive($route, item.path) }"
                @click="handleDropdownItemClick(group.label, item.path)"
                @keydown.enter="handleDropdownItemClick(group.label, item.path)"
              >
                {{ item.label }}
              </router-link>
            </li>
          </ul>
        </li>
      </ul>
    </div>

    <!-- Mobile overlay -->
    <div
      v-if="isMobileMenuOpen"
      class="mobile-overlay"
      @click="closeMobileMenu"
      aria-hidden="true"
    ></div>
  </nav>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import {
  navigationGroups,
  standaloneItems,
  isRouteActive,
  findActiveGroup,
} from '@/router/navigation';

const route = useRoute();
const router = useRouter();

// Dropdown state management
const openDropdown = ref<string | null>(null);
const isMobileMenuOpen = ref(false);
const isMobile = ref(false);

// Check if current route is active
const currentActiveGroup = computed(() => findActiveGroup(route));

// Watch route changes to maintain dropdown state
watch(
  () => route.path,
  (newPath) => {
    const activeGroup = findActiveGroup(route);
    
    // Keep dropdown open if navigating within the same group
    if (activeGroup && openDropdown.value === activeGroup) {
      // Dropdown stays open
    } else if (activeGroup) {
      // Open the dropdown for the active group
      openDropdown.value = activeGroup;
    }
    
    // Close mobile menu after navigation
    if (isMobileMenuOpen.value) {
      // Small delay to allow smooth transition
      setTimeout(() => {
        isMobileMenuOpen.value = false;
      }, 200);
    }
  }
);

// Toggle dropdown
function toggleDropdown(groupLabel: string) {
  if (openDropdown.value === groupLabel) {
    openDropdown.value = null;
  } else {
    openDropdown.value = groupLabel;
  }
}

// Handle dropdown item click
function handleDropdownItemClick(groupLabel: string, itemPath: string) {
  // Navigate to the item
  router.push(itemPath);
  
  // Keep dropdown open on desktop, close on mobile
  if (!isMobile.value) {
    // Keep dropdown open for state persistence
    openDropdown.value = groupLabel;
  } else {
    // Close mobile menu after navigation
    setTimeout(() => {
      isMobileMenuOpen.value = false;
      openDropdown.value = null;
    }, 200);
  }
}

// Mobile menu functions
function toggleMobileMenu() {
  isMobileMenuOpen.value = !isMobileMenuOpen.value;
}

function closeMobileMenu() {
  isMobileMenuOpen.value = false;
  openDropdown.value = null;
}

// Check screen size
function checkScreenSize() {
  isMobile.value = window.innerWidth < 768;
  if (!isMobile.value) {
    // On desktop, close mobile menu if open
    isMobileMenuOpen.value = false;
  } else {
    // On mobile, close dropdowns when switching to mobile view
    if (openDropdown.value) {
      openDropdown.value = null;
    }
  }
}

// Handle click outside dropdown
function handleClickOutside(event: MouseEvent) {
  if (!isMobile.value && openDropdown.value) {
    const target = event.target as HTMLElement;
    const dropdown = target.closest('.dropdown');
    if (!dropdown) {
      openDropdown.value = null;
    }
  }
}

// Handle escape key
function handleEscapeKey(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    if (openDropdown.value) {
      openDropdown.value = null;
    }
    if (isMobileMenuOpen.value) {
      closeMobileMenu();
    }
  }
}

// Initialize active dropdown on mount
onMounted(() => {
  checkScreenSize();
  window.addEventListener('resize', checkScreenSize);
  document.addEventListener('click', handleClickOutside);
  document.addEventListener('keydown', handleEscapeKey);
  
  // Open dropdown for active group on mount
  const activeGroup = findActiveGroup(route);
  if (activeGroup && !isMobile.value) {
    openDropdown.value = activeGroup;
  }
});

onUnmounted(() => {
  window.removeEventListener('resize', checkScreenSize);
  document.removeEventListener('click', handleClickOutside);
  document.removeEventListener('keydown', handleEscapeKey);
});
</script>

<style scoped>
.navigation-menu {
  position: relative;
  background-color: #f5f5f5;
  border-bottom: 1px solid #ddd;
  width: 100%;
}

.nav-container {
  max-width: 100%;
  margin: 0 auto;
  padding: 0;
}

/* Mobile toggle button */
.mobile-toggle {
  display: none;
  background: none;
  border: none;
  padding: 12px 16px;
  cursor: pointer;
  z-index: 1001;
  position: relative;
}

.hamburger-icon {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 24px;
  height: 20px;
}

.hamburger-icon span {
  display: block;
  width: 100%;
  height: 3px;
  background-color: #2c3e50;
  border-radius: 2px;
  transition: all 0.3s ease;
}

.mobile-open .hamburger-icon span:nth-child(1) {
  transform: rotate(45deg) translate(8px, 8px);
}

.mobile-open .hamburger-icon span:nth-child(2) {
  opacity: 0;
}

.mobile-open .hamburger-icon span:nth-child(3) {
  transform: rotate(-45deg) translate(8px, -8px);
}

/* Navigation list */
.nav-list {
  display: flex;
  list-style: none;
  margin: 0;
  padding: 0;
  align-items: center;
}

.nav-item {
  position: relative;
  margin: 0;
}

.nav-link {
  display: flex;
  align-items: center;
  padding: 20px 16px;
  color: #2c3e50;
  text-decoration: none;
  font-weight: bold;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 16px;
  transition: color 0.2s ease;
}

.nav-link:hover {
  color: #42b983;
}

.nav-link.active {
  color: #42b983;
}

/* Dropdown trigger */
.dropdown-trigger {
  position: relative;
  padding-right: 32px;
}

.dropdown-arrow {
  position: absolute;
  right: 12px;
  font-size: 10px;
  transition: transform 0.2s ease;
}

.dropdown-arrow.open {
  transform: rotate(180deg);
}

/* Dropdown menu */
.dropdown-menu {
  position: absolute;
  top: 100%;
  left: 0;
  background-color: white;
  border: 1px solid #ddd;
  border-radius: 4px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
  list-style: none;
  margin: 0;
  padding: 8px 0;
  min-width: 180px;
  opacity: 0;
  visibility: hidden;
  transform: translateY(-10px);
  transition: all 0.2s ease;
  z-index: 1000;
}

.dropdown-menu.open {
  opacity: 1;
  visibility: visible;
  transform: translateY(0);
}

.dropdown-item {
  display: block;
  padding: 12px 20px;
  color: #2c3e50;
  text-decoration: none;
  transition: background-color 0.2s ease;
  font-weight: normal;
}

.dropdown-item:hover {
  background-color: #f5f5f5;
  color: #42b983;
}

.dropdown-item.active {
  background-color: #e8f5e9;
  color: #42b983;
  font-weight: bold;
}

/* Mobile styles */
@media (max-width: 767px) {
  .mobile-toggle {
    display: block;
  }

  .nav-list {
    position: fixed;
    top: 0;
    left: 0;
    width: 280px;
    height: 100vh;
    background-color: white;
    flex-direction: column;
    align-items: stretch;
    padding: 60px 0 20px;
    box-shadow: 2px 0 8px rgba(0, 0, 0, 0.1);
    transform: translateX(-100%);
    transition: transform 0.3s ease;
    z-index: 1000;
    overflow-y: auto;
  }

  .nav-list.mobile-open {
    transform: translateX(0);
  }

  .nav-item {
    width: 100%;
    border-bottom: 1px solid #eee;
  }

  .nav-link {
    width: 100%;
    padding: 16px 20px;
    text-align: left;
    justify-content: space-between;
  }

  .dropdown-trigger {
    padding-right: 40px;
  }

  .dropdown-menu {
    position: static;
    width: 100%;
    border: none;
    border-radius: 0;
    box-shadow: none;
    background-color: #f9f9f9;
    max-height: 0;
    overflow: hidden;
    transform: none;
    transition: max-height 0.3s ease;
  }

  .dropdown-menu.open {
    max-height: 500px;
    opacity: 1;
    visibility: visible;
  }

  .dropdown-item {
    padding-left: 40px;
  }

  .mobile-overlay {
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100vh;
    background-color: rgba(0, 0, 0, 0.5);
    z-index: 999;
  }
}

/* Tablet styles */
@media (min-width: 768px) and (max-width: 1024px) {
  .nav-link {
    padding: 16px 12px;
    font-size: 14px;
  }
}

/* Accessibility: Focus styles */
.nav-link:focus,
.dropdown-item:focus,
.mobile-toggle:focus {
  outline: 2px solid #42b983;
  outline-offset: 2px;
}

/* High contrast mode support */
@media (prefers-contrast: high) {
  .nav-link {
    border: 1px solid transparent;
  }

  .nav-link:focus {
    border-color: currentColor;
  }
}
</style>

