<script>
    import { onMount } from "svelte";
    import { apiCall } from "$lib/api";

    let routes = [];
    let loading = true;
    let error = "";

    onMount(async () => {
        try {
            routes = await apiCall("/api/v1/routes");
            // Backend returns 'upstreams' array, frontend logic handles it
            routes = routes.map((r) => ({
                id: r.id,
                domain: r.host + r.path,
                target: r.upstreams
                    .map((u) => `${u.address}:${u.port}`)
                    .join(", "),
                type: r.protocol.toUpperCase(),
                ssl: true, // simplified assumption or check if https
            }));
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    });

    async function deleteRoute(id) {
        if (!confirm("Are you sure you want to delete this route?")) return;
        try {
            await apiCall(`/api/v1/routes/${id}`, "DELETE");
            routes = routes.filter((r) => r.id !== id);
        } catch (e) {
            alert(e.message);
        }
    }
</script>

<div class="mb-8">
    <h2
        class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400"
    >
        Routes & Gateways
    </h2>
    <p class="text-gray-400 mt-2">
        Configure ingress rules and SSL certificates.
    </p>
</div>

<div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
    <table class="w-full text-left">
        <thead
            class="bg-gray-900/50 text-gray-400 uppercase text-xs font-semibold tracking-wider"
        >
            <tr>
                <th class="px-6 py-4">Domain</th>
                <th class="px-6 py-4">Target</th>
                <th class="px-6 py-4">Type</th>
                <th class="px-6 py-4">SSL Status</th>
                <th class="px-6 py-4 text-right">Actions</th>
            </tr>
        </thead>
        <tbody class="divide-y divide-gray-700">
            {#each routes as route}
                <tr class="hover:bg-gray-700/30 transition-colors">
                    <td class="px-6 py-4 text-white font-medium"
                        >{route.domain}</td
                    >
                    <td class="px-6 py-4 text-gray-300 font-mono text-sm"
                        >{route.target}</td
                    >
                    <td class="px-6 py-4 text-gray-300">{route.type}</td>
                    <td class="px-6 py-4">
                        {#if route.ssl}
                            <span
                                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-900/30 text-green-400 border border-green-500/20"
                            >
                                Secured
                            </span>
                        {:else}
                            <span
                                class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-900/30 text-red-400 border border-red-500/20"
                            >
                                Insecure
                            </span>
                        {/if}
                    </td>
                    <td class="px-6 py-4 text-right space-x-2">
                        <!-- Edit (Future Implementation) -->
                        <button
                            class="text-xs text-gray-500 hover:text-white cursor-not-allowed opacity-50"
                            title="Not implemented">Edit</button
                        >

                        <button
                            class="text-xs text-red-500 hover:text-red-300"
                            on:click={() => deleteRoute(route.id)}
                        >
                            Delete
                        </button>
                    </td>
                </tr>
            {/each}
        </tbody>
    </table>
</div>
