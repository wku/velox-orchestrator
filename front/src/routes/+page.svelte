<script>
    import { onMount } from "svelte";
    import { page } from "$app/stores";

    let stats = {
        projects: 0,
        containers: 0,
        routes: 0,
    };

    // Use environment variable for API URL or default to localhost
    const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

    onMount(async () => {
        const token = localStorage.getItem("token");
        if (!token) return;

        try {
            const res = await fetch(`${API_URL}/api/v1/stats`, {
                headers: {
                    Authorization: `Bearer ${token}`,
                },
            });
            if (res.ok) {
                const data = await res.json();
                stats = data;
            }
        } catch (e) {
            console.error("Failed to fetch stats", e);
        }
    });
</script>

<div class="mb-8">
    <h2
        class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400"
    >
        Dashboard
    </h2>
    <p class="text-gray-400 mt-2">Overview of your orchestration platform.</p>
</div>

<div class="grid grid-cols-1 md:grid-cols-3 gap-6">
    <!-- Stat Cards -->
    <div
        class="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-sm hover:border-gray-600 transition-colors"
    >
        <h3 class="text-gray-400 text-sm font-medium uppercase tracking-wider">
            Active Projects
        </h3>
        <p class="text-4xl font-bold mt-4 text-white">{stats.projects}</p>
        <div class="mt-4 text-sm text-gray-500">Total deployed projects</div>
    </div>

    <div
        class="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-sm hover:border-gray-600 transition-colors"
    >
        <h3 class="text-gray-400 text-sm font-medium uppercase tracking-wider">
            Healthy Containers
        </h3>
        <p class="text-4xl font-bold mt-4 text-green-400">{stats.containers}</p>
        <div class="mt-4 text-sm text-gray-500">Running instances</div>
    </div>

    <div
        class="bg-gray-800 p-6 rounded-lg border border-gray-700 shadow-sm hover:border-gray-600 transition-colors"
    >
        <h3 class="text-gray-400 text-sm font-medium uppercase tracking-wider">
            Active Routes
        </h3>
        <p class="text-4xl font-bold mt-4 text-blue-400">{stats.routes}</p>
        <div class="mt-4 text-sm text-gray-500">Configured ingress rules</div>
    </div>
</div>

<div class="mt-8 grid grid-cols-1 lg:grid-cols-2 gap-8">
    <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
        <h3 class="text-lg font-bold mb-4 border-b border-gray-700 pb-2">
            Recent Activity
        </h3>
        <div class="text-gray-400 text-sm italic py-4 text-center">
            No recent activity logs available.
        </div>
    </div>

    <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
        <h3 class="text-lg font-bold mb-4 border-b border-gray-700 pb-2">
            System Status
        </h3>
        <div class="space-y-3">
            <div class="flex justify-between items-center">
                <span class="text-gray-400">API Status</span>
                <span
                    class="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs border border-green-500/20"
                    >Operational</span
                >
            </div>
            <div class="flex justify-between items-center">
                <span class="text-gray-400">Docker Engine</span>
                <span
                    class="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs border border-green-500/20"
                    >Connected</span
                >
            </div>
            <div class="flex justify-between items-center">
                <span class="text-gray-400">Redis</span>
                <span
                    class="px-2 py-1 bg-green-900/30 text-green-400 rounded text-xs border border-green-500/20"
                    >Connected</span
                >
            </div>
        </div>
    </div>
</div>
