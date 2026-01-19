<script>
    import { onMount } from "svelte";
    import { apiCall } from "$lib/api";

    let projects = [];
    let loading = true;
    let error = "";

    onMount(async () => {
        try {
            const rawProjects = await apiCall("/api/v1/projects");

            // Fetch applications for each project to get accurate counts and detailed info
            projects = await Promise.all(
                rawProjects.map(async (p) => {
                    let appCount = 0;
                    let status = "active"; // Default
                    let lastDeploy = "Unknown";

                    try {
                        const apps = await apiCall(
                            `/api/v1/projects/${p.id}/applications`,
                        );
                        appCount = apps.length;
                        // Logic to determine overall status based on apps.. simplified for now
                        if (apps.length === 0) status = "empty";
                    } catch (err) {
                        console.error(
                            `Failed to fetch apps for project ${p.id}`,
                            err,
                        );
                    }

                    return {
                        ...p,
                        status,
                        apps: appCount,
                        last_deploy: lastDeploy,
                    };
                }),
            );
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
            Projects
        </h2>
        <p class="text-gray-400 mt-2">
            Manage your applications and deployments.
        </p>
    </div>
    <a
        href="/projects/new"
        class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg font-medium transition-colors shadow-lg shadow-blue-900/20"
    >
        New Project
    </a>
</div>

{#if loading}
    <div class="text-center text-gray-400 py-12">Loading projects...</div>
{:else if error}
    <div
        class="bg-red-900/30 text-red-200 p-4 rounded-lg border border-red-500/30"
    >
        Error: {error}
    </div>
{:else}
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {#each projects as project}
            <div
                class="bg-gray-800 rounded-lg border border-gray-700 hover:border-blue-500/50 transition-all group"
            >
                <div class="p-6">
                    <div class="flex justify-between items-start mb-4">
                        <h3
                            class="text-xl font-bold text-white group-hover:text-blue-400 transition-colors"
                        >
                            {project.name}
                        </h3>
                        <span
                            class="px-2 py-1 rounded text-xs font-medium uppercase tracking-wider {project.status ===
                            'active'
                                ? 'bg-green-900/30 text-green-400 border border-green-500/20'
                                : 'bg-yellow-900/30 text-yellow-400 border border-yellow-500/20'}"
                        >
                            {project.status}
                        </span>
                    </div>

                    <div class="space-y-3 text-sm text-gray-400">
                        <div class="flex justify-between">
                            <span>Applications</span>
                            <span class="text-white">{project.apps}</span>
                        </div>
                        <div class="flex justify-between">
                            <span>Last Deploy</span>
                            <span class="text-white">{project.last_deploy}</span
                            >
                        </div>
                    </div>
                </div>

                <div
                    class="bg-gray-800/50 px-6 py-4 border-t border-gray-700 flex justify-between items-center rounded-b-lg"
                >
                    <button
                        class="text-sm text-gray-400 hover:text-white transition-colors"
                        >Settings</button
                    >
                    <a
                        href={`/projects/${project.id}`}
                        class="text-sm text-blue-400 hover:text-blue-300 font-medium transition-colors"
                        >View Details &rarr;</a
                    >
                </div>
            </div>
        {/each}

        <!-- Add New Placeholder -->
        <a
            href="/projects/new"
            class="border-2 border-dashed border-gray-700 rounded-lg p-6 flex flex-col items-center justify-center text-gray-500 hover:border-gray-500 hover:text-gray-300 transition-all h-full block"
        >
            <span class="text-4xl mb-2">+</span>
            <span class="font-medium">Create New Project</span>
        </a>
    </div>
{/if}
