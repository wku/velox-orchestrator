<script>
    import { onMount } from "svelte";
    import { apiCall } from "$lib/api";

    let repos = [];
    let loading = true;
    let error = "";

    onMount(async () => {
        try {
            repos = await apiCall("/api/v1/repos");
            // Enrich
            repos = repos.map((r) => ({
                ...r,
                name: r.url.split("/").pop().replace(".git", ""),
                status: "Active", // Mock status
                last_sync: r.last_deploy_at
                    ? new Date(r.last_deploy_at * 1000).toLocaleString()
                    : "Never",
            }));
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    });
</script>

<div class="flex justify-between items-center mb-8">
    <div>
        <h2
            class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400"
        >
            GitOps
        </h2>
        <p class="text-gray-400 mt-2">
            Continuous deployment from Git repositories.
        </p>
    </div>
    <button
        class="bg-purple-600 hover:bg-purple-500 text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-lg shadow-purple-900/20"
    >
        Connect Repository
    </button>
</div>

<div class="space-y-4">
    {#each repos as repo}
        <div
            class="bg-gray-800 p-6 rounded-lg border border-gray-700 flex items-center justify-between"
        >
            <div class="flex items-center gap-4">
                <div class="p-3 bg-gray-700 rounded-lg">
                    <!-- Icon placeholder -->
                    <span class="font-bold text-gray-400">GIT</span>
                </div>
                <div>
                    <h3 class="text-lg font-bold text-white mb-1">
                        {repo.name}
                    </h3>
                    <div class="flex items-center gap-3 text-sm text-gray-400">
                        <span class="flex items-center gap-1">
                            <span class="w-2 h-2 rounded-full bg-purple-400"
                            ></span>
                            {repo.branch}
                        </span>
                        <span>#{repo.commit}</span>
                        <span>{repo.last_sync}</span>
                    </div>
                </div>
            </div>

            <div class="flex items-center gap-4">
                <span
                    class="text-green-400 text-sm font-medium bg-green-900/20 px-3 py-1 rounded-full border border-green-500/20"
                >
                    {repo.status}
                </span>
                <button
                    class="text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors"
                >
                    Sync Now
                </button>
                <button
                    class="text-gray-400 hover:text-white p-2 hover:bg-gray-700 rounded transition-colors"
                >
                    Settings
                </button>
            </div>
        </div>
    {/each}
</div>
