<script lang="ts">
    import { onMount } from "svelte";
    import { apiCall } from "$lib/api";

    let stats: any = null;
    let loading = true;
    let error = "";
    let restarting = false;

    onMount(async () => {
        await loadStats();
    });

    async function loadStats() {
        try {
            loading = true;
            stats = await apiCall("/api/v1/system/info");
        } catch (e: any) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function restartSystem() {
        if (
            !confirm(
                "Are you sure you want to restart the Velox Orchestrator service? It will be unavailable for a few seconds.",
            )
        )
            return;

        try {
            restarting = true;
            await apiCall("/api/v1/system/restart", { method: "POST" });
            alert("Restart command sent. The page will reload in 10 seconds.");
            setTimeout(() => {
                window.location.reload();
            }, 10000);
        } catch (e: any) {
            alert(e.message);
            restarting = false;
        }
    }
</script>

<div class="max-w-4xl mx-auto">
    <h1 class="text-3xl font-bold text-white mb-2">System Management</h1>
    <p class="text-gray-400 mb-8">
        Manage the Velox Orchestrator service itself.
    </p>

    {#if loading}
        <div class="text-gray-400">Loading system info...</div>
    {:else if error}
        <div
            class="bg-red-900/30 text-red-200 p-4 rounded-lg border border-red-500/30 mb-6"
        >
            Error: {error}
        </div>
    {:else if stats}
        <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
                <h3 class="text-gray-400 text-sm font-medium mb-2">Platform</h3>
                <p class="text-2xl font-bold text-white">{stats.platform}</p>
            </div>
            <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
                <h3 class="text-gray-400 text-sm font-medium mb-2">
                    Python Version
                </h3>
                <p class="text-2xl font-bold text-white">{stats.python}</p>
            </div>
            <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
                <h3 class="text-gray-400 text-sm font-medium mb-2">
                    CPU Usage
                </h3>
                <p class="text-2xl font-bold text-white">
                    {stats.cpu_percent}%
                </p>
                <div
                    class="w-full bg-gray-700 h-2 mt-2 rounded-full overflow-hidden"
                >
                    <div
                        class="bg-blue-500 h-full transition-all duration-500"
                        style="width: {stats.cpu_percent}%"
                    ></div>
                </div>
            </div>
            <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
                <h3 class="text-gray-400 text-sm font-medium mb-2">
                    Memory Usage
                </h3>
                <p class="text-2xl font-bold text-white">
                    {stats.memory_percent}%
                </p>
                <div
                    class="w-full bg-gray-700 h-2 mt-2 rounded-full overflow-hidden"
                >
                    <div
                        class="bg-purple-500 h-full transition-all duration-500"
                        style="width: {stats.memory_percent}%"
                    ></div>
                </div>
            </div>
        </div>
    {/if}

    <div class="bg-gray-800 rounded-lg border border-gray-700 p-6">
        <h2 class="text-xl font-bold text-white mb-4 text-red-400">
            Danger Zone
        </h2>
        <p class="text-gray-400 mb-6">
            Restarting the service will temporarily disrupt access to the
            dashboard and API. Running applications will NOT be affected.
        </p>

        <button
            on:click={restartSystem}
            disabled={restarting}
            class="bg-red-600 hover:bg-red-500 text-white px-6 py-3 rounded-lg font-bold transition-colors flex items-center gap-3 disabled:opacity-50 disabled:cursor-not-allowed"
        >
            {#if restarting}
                <span
                    class="animate-spin h-5 w-5 border-2 border-white/50 border-t-white rounded-full"
                ></span>
            {/if}
            Restart Orchestrator Service
        </button>
    </div>
</div>
