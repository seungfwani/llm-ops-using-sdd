import { RouteLocationNormalized } from 'vue-router';

export interface NavigationItem {
  label: string;
  path: string;
  children?: NavigationItem[];
}

export interface NavigationGroup {
  label: string;
  items: NavigationItem[];
}

/**
 * Navigation menu structure for the LLM Ops Platform
 * Groups related features into dropdown menus for better discoverability
 */
export const navigationGroups: NavigationGroup[] = [
  {
    label: 'Catalog',
    items: [
      { label: 'Models', path: '/catalog/models' },
      { label: 'Datasets', path: '/catalog/datasets' },
    ],
  },
  {
    label: 'Prompts',
    items: [
      { label: '프롬프트 관리', path: '/prompts' },
    ],
  },
  {
    label: 'ML Operations',
    items: [
      { label: 'Training', path: '/training/jobs' },
      { label: 'Experiments', path: '/experiments/search' },
      { label: 'Serving', path: '/serving/endpoints' },
    ],
  },
  {
    label: 'Governance',
    items: [
      { label: 'Policies', path: '/governance/policies' },
      { label: 'Audit', path: '/governance/audit' },
      { label: 'Costs', path: '/governance/costs' },
    ],
  },
  {
    label: 'Admin',
    items: [
      { label: 'Integrations', path: '/admin/integrations' },
    ],
  },
];

/**
 * Standalone navigation items (not in dropdown groups)
 */
export const standaloneItems: NavigationItem[] = [
  { label: 'Getting Started', path: '/getting-started' },
];

/**
 * Check if a route matches a navigation item path
 * Handles dynamic routes (e.g., /catalog/models/:id matches /catalog/models)
 */
export function isRouteActive(
  currentRoute: RouteLocationNormalized,
  itemPath: string
): boolean {
  if (currentRoute.path === itemPath) {
    return true;
  }

  // Handle dynamic routes - check if current path starts with item path
  // e.g., /catalog/models/123 matches /catalog/models
  if (currentRoute.path.startsWith(itemPath + '/')) {
    return true;
  }

  // Handle exact matches for parent paths
  const currentPathParts = currentRoute.path.split('/').filter(Boolean);
  const itemPathParts = itemPath.split('/').filter(Boolean);

  // Check if current path is a child of item path
  if (
    currentPathParts.length > itemPathParts.length &&
    itemPathParts.every((part, index) => part === currentPathParts[index])
  ) {
    return true;
  }

  return false;
}

/**
 * Find which navigation group contains the active route
 */
export function findActiveGroup(
  currentRoute: RouteLocationNormalized
): string | null {
  for (const group of navigationGroups) {
    if (group.items.some((item) => isRouteActive(currentRoute, item.path))) {
      return group.label;
    }
  }
  return null;
}

/**
 * Get all routes for verification
 */
export function getAllRoutes(): string[] {
  const routes: string[] = [];

  // Add standalone routes
  standaloneItems.forEach((item) => {
    routes.push(item.path);
  });

  // Add grouped routes
  navigationGroups.forEach((group) => {
    group.items.forEach((item) => {
      routes.push(item.path);
    });
  });

  return routes;
}

