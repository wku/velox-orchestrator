<script>
  import "../app.css";
  import { page } from "$app/stores";
  import { isAuthenticated, authUser, logout } from "$lib/stores/auth";
  import { onMount } from "svelte";

  // Protect routes
  $: if ($isAuthenticated === false && $page.url.pathname !== "/login") {
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
  }

  const navigation = [
    { name: "Dashboard", href: "/", icon: "LayoutDashboard" },
    { name: "Projects", href: "/projects", icon: "FolderKanban" },
    { name: "Routes", href: "/routes", icon: "Network" },
    { name: "GitOps", href: "/git-repos", icon: "GitBranch" },
    { name: "Infrastructure", href: "/infra", icon: "Server" },
    { name: "Settings", href: "/settings", icon: "Settings" },
  ];

  function isCurrent(path) {
    if (path === "/" && $page.url.pathname === "/") return true;
    if (path !== "/" && $page.url.pathname.startsWith(path)) return true;
    return false;
  }
</script>

{#if $isAuthenticated && $page.url.pathname !== "/login"}
  <div class="flex h-screen bg-gray-900 text-white overflow-hidden">
    <!-- Sidebar -->
    <aside class="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
      <div class="p-6 border-b border-gray-700">
        <h1
          class="text-xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500"
        >
          Velox Orchestrator Orchestrator
        </h1>
      </div>

      <nav class="flex-1 p-4 space-y-1 overflow-y-auto">
        {#each navigation as item}
          <a
            href={item.href}
            class="flex items-center gap-3 px-4 py-3 rounded-lg transition-colors {isCurrent(
              item.href,
            )
              ? 'bg-blue-600/20 text-blue-400 border border-blue-600/30'
              : 'text-gray-400 hover:bg-gray-700 hover:text-white'}"
          >
            <!-- We would use Lucide icons here, using simple text fallback for now if icons pkg not installed -->
            <span class="font-medium">{item.name}</span>
          </a>
        {/each}
      </nav>

      <div class="p-4 border-t border-gray-700 bg-gray-800/50">
        <div class="flex items-center justify-between mb-2">
          <span class="text-sm font-medium text-white">{$authUser}</span>
          <span
            class="text-xs text-green-400 bg-green-400/10 px-2 py-0.5 rounded border border-green-400/20"
            >Online</span
          >
        </div>
        <button
          on:click={logout}
          class="w-full text-sm bg-gray-700 hover:bg-red-900/30 hover:text-red-300 hover:border-red-500/30 border border-transparent py-2 rounded transition-all text-gray-300"
        >
          Logout
        </button>
      </div>
    </aside>

    <!-- Main Content -->
    <main class="flex-1 overflow-auto bg-gray-900 scrollbar-thin">
      <div class="p-8 pb-20 max-w-7xl mx-auto">
        <slot />
      </div>
    </main>
  </div>
{:else}
  <slot />
{/if}

<style>
  /* Custom scrollbar for webkit */
  .scrollbar-thin::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  .scrollbar-thin::-webkit-scrollbar-track {
    background: transparent;
  }
  .scrollbar-thin::-webkit-scrollbar-thumb {
    background: #374151;
    border-radius: 4px;
  }
  .scrollbar-thin::-webkit-scrollbar-thumb:hover {
    background: #4b5563;
  }
</style>
