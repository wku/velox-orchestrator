<script>
    import { onMount } from "svelte";
    import { apiCall } from "$lib/api";

    let networks = [];
    let containers = [];
    let loading = true;

    onMount(async () => {
        try {
            [networks, containers] = await Promise.all([
                apiCall("/api/v1/networks"),
                apiCall("/api/v1/containers"),
            ]);
        } catch (e) {
            console.error(e);
        } finally {
            loading = false;
        }
    });
</script>

<div class="mb-8">
    <h2
        class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400"
    >
        Infrastructure
    </h2>
    <p class="text-gray-400 mt-2">Monitor nodes, networks, and resources.</p>
</div>

<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
    <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
        <h3
            class="text-gray-400 text-sm font-bold uppercase tracking-wider mb-4"
        >
            CPU Usage
        </h3>
        <div class="relative h-2 bg-gray-700 rounded-full overflow-hidden">
            <div class="absolute top-0 left-0 h-full bg-blue-500 w-[45%]"></div>
        </div>
        <div class="mt-2 text-right text-white font-mono">45%</div>
    </div>

    <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
        <h3
            class="text-gray-400 text-sm font-bold uppercase tracking-wider mb-4"
        >
            Memory Usage
        </h3>
        <div class="relative h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
                class="absolute top-0 left-0 h-full bg-purple-500 w-[60%]"
            ></div>
        </div>
        <div class="mt-2 text-right text-white font-mono">60%</div>
    </div>

    <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
        <h3
            class="text-gray-400 text-sm font-bold uppercase tracking-wider mb-4"
        >
            Disk Usage
        </h3>
        <div class="relative h-2 bg-gray-700 rounded-full overflow-hidden">
            <div
                class="absolute top-0 left-0 h-full bg-green-500 w-[30%]"
            ></div>
        </div>
        <div class="mt-2 text-right text-white font-mono">30%</div>
    </div>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700">
    <div class="p-6 border-b border-gray-700">
        <h3 class="text-lg font-bold text-white">Networks</h3>
    </div>
    <table class="w-full text-left">
        <thead
            class="bg-gray-900/50 text-gray-400 text-xs uppercase font-semibold"
        >
            <tr>
                <th class="px-6 py-4">Name</th>
                <th class="px-6 py-4">Driver</th>
                <th class="px-6 py-4">Scope</th>
            </tr>
        </thead>
        <tbody class="divide-y divide-gray-700">
            {#each networks as net}
                <tr>
                    <td class="px-6 py-4 text-white font-mono"
                        >{net.Name || net.name}</td
                    >
                    <td class="px-6 py-4 text-gray-400"
                        >{net.Driver || net.driver}</td
                    >
                    <td class="px-6 py-4 text-gray-400"
                        >{net.Scope || net.scope}</td
                    >
                </tr>
            {/each}
        </tbody>
    </table>
</div>
