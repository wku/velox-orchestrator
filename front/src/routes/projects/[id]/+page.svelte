<script lang="ts">
    import { onMount } from "svelte";
    import { page } from "$app/stores";
    import { apiCall } from "$lib/api";

    // Type definitions
    interface Project {
        id: string;
        name: string;
        description: string;
        env: Record<string, string>;
        created_at: number;
    }

    interface App {
        id: string;
        name: string;
        image: string;
        status: string;
        domain?: string;
        replicas: number;
    }

    interface LogsResponse {
        logs: Record<string, string>;
    }

    let project: Project | null = null;
    let applications: App[] = [];
    let loading = true;
    let error = "";
    let logs: Record<string, string> = {};
    let showLogsFor: string | null = null;
    let repoId: string | null = null;
    let deploying = false;
    let restarting = false;

    const projectId = $page.params.id;

    onMount(async () => {
        await loadData();
    });

    async function loadData() {
        try {
            loading = true;
            // Parallel fetch: Project, Apps, Repos (to find if it's a git project)
            const [projData, appList, repoList] = await Promise.all([
                apiCall(`/api/v1/projects/${projectId}`),
                apiCall(`/api/v1/projects/${projectId}/applications`),
                apiCall("/api/v1/repos"),
            ]);

            project = projData;
            applications = appList;

            // Find linked repo
            const linkedRepo = repoList.find(
                (r: any) => r.project_id === projectId,
            );
            if (linkedRepo) {
                repoId = linkedRepo.id;
            }
        } catch (e: any) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function deleteProject() {
        if (
            !confirm(
                "Are you sure? This will delete the project and all its applications.",
            )
        )
            return;
        try {
            await apiCall(`/api/v1/projects/${projectId}`, {
                method: "DELETE",
            });
            window.location.href = "/projects";
        } catch (e: any) {
            alert(e.message);
        }
    }

    async function redeployProject() {
        if (
            !confirm(
                "Re-deploy project? This will re-read configuration from source (Git or Local) and rebuild.",
            )
        )
            return;

        try {
            deploying = true;
            // Calls generic project deploy endpoint which handles Git or Local check on backend
            await apiCall(`/api/v1/projects/${projectId}/deploy`, {
                method: "POST",
            });
            // Polling or waiting? For now just reload
            setTimeout(loadData, 2000); // Give it a sec to start
            alert("Deployment triggered.");
        } catch (e: any) {
            alert(e.message);
        } finally {
            deploying = false;
        }
    }

    async function restartProject() {
        if (!confirm("Restart all services in this project?")) return;
        try {
            restarting = true;
            await apiCall(`/api/v1/projects/${projectId}/restart`, {
                method: "POST",
            });
            await loadData();
            alert("Restart triggered.");
        } catch (e: any) {
            alert(e.message);
        } finally {
            restarting = false;
        }
    }

    async function stopApp(appId: string) {
        if (!confirm("Stop this application?")) return;
        try {
            await apiCall(`/api/v1/applications/${appId}/stop`, {
                method: "POST",
            });
            await loadData();
        } catch (e: any) {
            alert(e.message);
        }
    }

    async function restartApp(appId: string) {
        if (!confirm("Restart (Re-deploy) application?")) return;
        try {
            await apiCall(`/api/v1/applications/${appId}/deploy`, {
                method: "POST",
            });
            await loadData();
        } catch (e: any) {
            alert(e.message);
        }
    }

    let logsTab = "runtime"; // 'runtime' | 'build'
    let deployLogs: Record<string, any> = {};

    async function viewLogs(appId: string) {
        try {
            showLogsFor = appId;
            logsTab = "runtime"; // Default to runtime

            // Fetch Runtime Logs (in parallel to be fast, but we handle errors safely)
            apiCall(`/api/v1/applications/${appId}/logs`)
                .then((res) => {
                    let combined = "";
                    for (const [cid, log] of Object.entries(res.logs)) {
                        combined += `--- Container ${cid} ---\n${log}\n`;
                    }
                    logs[appId] = combined;
                })
                .catch((e) => {
                    logs[appId] = `Failed to fetch runtime logs: ${e.message}`;
                });

            // Fetch Build Logs
            apiCall(`/api/v1/applications/${appId}/deploy-logs`)
                .then((res) => {
                    deployLogs[appId] = res;
                })
                .catch((e) => {
                    deployLogs[appId] = {
                        logs: `Failed to fetch deploy logs: ${e.message}`,
                        status: "Unknown",
                        version: 0,
                    };
                });
        } catch (e: any) {
            alert(e.message);
        }
    }

    function getAppUrl(app: App) {
        if (app.domain) {
            return `http://${app.domain}`;
        }
        return null;
    }
</script>

<div class="mb-6">
    <a
        href="/projects"
        class="text-blue-400 hover:text-blue-300 transition-colors mb-4 inline-block"
        >&larr; Back to Projects</a
    >

    {#if loading && !project}
        <div class="text-gray-400">Loading details...</div>
    {:else if error}
        <div
            class="bg-red-900/30 text-red-200 p-4 rounded-lg border border-red-500/30"
        >
            Error: {error}
        </div>
    {:else if project}
        <div class="flex justify-between items-start">
            <div>
                <h2 class="text-3xl font-bold text-white">{project.name}</h2>
                <p class="text-gray-400 mt-1">
                    {project.description || "No description"}
                </p>
                <div class="mt-2 flex gap-4 text-sm text-gray-500">
                    <span
                        >ID: <code class="bg-gray-800 px-1 rounded"
                            >{project.id}</code
                        ></span
                    >
                    <span
                        >Created: {new Date(
                            project.created_at * 1000,
                        ).toLocaleDateString()}</span
                    >
                </div>
            </div>
            <div class="flex gap-3">
                <button
                    on:click={redeployProject}
                    disabled={deploying}
                    class="bg-blue-600 hover:bg-blue-500 text-white px-4 py-2 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                    {#if deploying}
                        <span
                            class="animate-spin h-4 w-4 border-2 border-white/50 border-t-white rounded-full"
                        ></span>
                    {/if}
                    Re-deploy
                </button>
                <button
                    on:click={restartProject}
                    disabled={restarting}
                    class="bg-yellow-600 hover:bg-yellow-500 text-white px-4 py-2 rounded-lg transition-colors flex items-center gap-2 disabled:opacity-50"
                >
                    {#if restarting}
                        <span
                            class="animate-spin h-4 w-4 border-2 border-white/50 border-t-white rounded-full"
                        ></span>
                    {/if}
                    Restart
                </button>
                <button
                    on:click={deleteProject}
                    class="bg-red-900/50 hover:bg-red-900 text-red-200 px-4 py-2 rounded-lg border border-red-500/30 transition-colors"
                >
                    Delete Project
                </button>
            </div>
        </div>

        <!-- Environment Variables -->
        <div class="mt-8 bg-gray-800 rounded-lg border border-gray-700 p-6">
            <h3 class="text-lg font-bold text-white mb-4">
                Project Environment
            </h3>
            {#if Object.keys(project.env || {}).length > 0}
                <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {#each Object.entries(project.env) as [key, value]}
                        <div
                            class="bg-gray-900 p-3 rounded border border-gray-700 font-mono text-sm flex justify-between"
                        >
                            <span class="text-blue-400">{key}</span>
                            <span class="text-gray-300">{value}</span>
                        </div>
                    {/each}
                </div>
            {:else}
                <p class="text-gray-500 italic">
                    No environment variables set.
                </p>
            {/if}
        </div>

        <!-- Applications List -->
        <div class="mt-8">
            <div class="flex justify-between items-center mb-4">
                <h3 class="text-2xl font-bold text-white">
                    Applications (Services)
                </h3>
                <!-- Removed Add Application button as per user request (Compose driven) -->
            </div>

            {#if applications.length === 0}
                <p class="text-gray-500 italic">
                    No applications deployed in this project.
                </p>
            {:else}
                <div class="grid grid-cols-1 gap-4">
                    {#each applications as app}
                        <div
                            class="bg-gray-800 rounded-lg border border-gray-700 p-6 flex flex-col gap-4"
                        >
                            <div class="flex justify-between items-start">
                                <div>
                                    <div class="flex items-center gap-3">
                                        <h4
                                            class="text-xl font-bold text-white"
                                        >
                                            {app.name}
                                        </h4>
                                        {#if app.status === "running"}
                                            <span
                                                class="bg-green-900/30 text-green-400 text-xs px-2 py-0.5 rounded border border-green-500/20"
                                                >Running</span
                                            >
                                        {:else if app.status === "deploying"}
                                            <span
                                                class="bg-blue-900/30 text-blue-400 text-xs px-2 py-0.5 rounded border border-blue-500/20 animate-pulse"
                                                >Deploying</span
                                            >
                                        {:else if app.status === "failed"}
                                            <span
                                                class="bg-red-900/30 text-red-400 text-xs px-2 py-0.5 rounded border border-red-500/20"
                                                >Failed</span
                                            >
                                        {:else}
                                            <span
                                                class="bg-gray-700 text-gray-400 text-xs px-2 py-0.5 rounded border border-gray-600 uppercase"
                                                >{app.status}</span
                                            >
                                        {/if}
                                    </div>
                                    <div class="mt-2 space-y-1">
                                        <p class="text-gray-400 text-sm">
                                            Image: <span
                                                class="text-white font-mono"
                                                >{app.image}</span
                                            >
                                        </p>
                                        {#if getAppUrl(app)}
                                            <p class="text-gray-400 text-sm">
                                                URL: <a
                                                    href={getAppUrl(app)}
                                                    target="_blank"
                                                    class="text-blue-400 hover:underline"
                                                    >{getAppUrl(app)}</a
                                                >
                                            </p>
                                        {:else}
                                            <p
                                                class="text-gray-500 text-sm italic"
                                            >
                                                No public URL configured
                                            </p>
                                        {/if}
                                        <p class="text-gray-400 text-sm">
                                            Replicas: <span class="text-white"
                                                >{app.replicas}</span
                                            >
                                        </p>
                                    </div>
                                </div>

                                <div class="flex items-center gap-2">
                                    <button
                                        on:click={() => viewLogs(app.id)}
                                        class="text-gray-300 hover:text-white bg-gray-700 hover:bg-gray-600 px-3 py-1.5 rounded text-sm transition-colors"
                                    >
                                        Logs
                                    </button>
                                    <button
                                        on:click={() => restartApp(app.id)}
                                        class="text-yellow-400 hover:text-yellow-300 bg-yellow-900/20 hover:bg-yellow-900/40 px-3 py-1.5 rounded text-sm transition-colors"
                                    >
                                        Restart
                                    </button>
                                    <button
                                        on:click={() => stopApp(app.id)}
                                        class="text-red-400 hover:text-red-300 bg-red-900/20 hover:bg-red-900/40 px-3 py-1.5 rounded text-sm transition-colors"
                                    >
                                        Stop
                                    </button>
                                </div>
                            </div>

                            <!-- Logs Viewer Overlay -->
                            {#if showLogsFor === app.id}
                                <div
                                    class="mt-4 bg-gray-900 rounded-lg overflow-hidden border border-gray-700"
                                >
                                    <div class="flex border-b border-gray-700">
                                        <button
                                            class="px-4 py-2 text-xs font-bold uppercase tracking-wider {logsTab ===
                                            'runtime'
                                                ? 'bg-gray-800 text-white border-b-2 border-blue-500'
                                                : 'text-gray-400 hover:text-gray-300'}"
                                            on:click={() =>
                                                (logsTab = "runtime")}
                                        >
                                            Runtime Logs
                                        </button>
                                        <button
                                            class="px-4 py-2 text-xs font-bold uppercase tracking-wider {logsTab ===
                                            'build'
                                                ? 'bg-gray-800 text-white border-b-2 border-blue-500'
                                                : 'text-gray-400 hover:text-gray-300'}"
                                            on:click={() => (logsTab = "build")}
                                        >
                                            Build/Deploy Logs
                                        </button>
                                        <div class="flex-grow"></div>
                                        <button
                                            on:click={() => {
                                                showLogsFor = null;
                                                logs = {};
                                                deployLogs = {};
                                            }}
                                            class="px-4 py-2 text-gray-500 hover:text-white"
                                            >✕</button
                                        >
                                    </div>

                                    <div
                                        class="p-4 bg-black font-mono text-xs text-gray-300 overflow-x-auto max-h-96 whitespace-pre-wrap"
                                    >
                                        {#if logsTab === "runtime"}
                                            {#if logs[app.id]}
                                                {logs[app.id]}
                                            {:else}
                                                <span
                                                    class="text-gray-600 italic"
                                                    >No runtime logs (container
                                                    may be stopped).</span
                                                >
                                            {/if}
                                        {/if}

                                        {#if logsTab === "build"}
                                            {#if deployLogs[app.id]}
                                                <div class="mb-2 text-gray-500">
                                                    Status: {deployLogs[app.id]
                                                        .status} (v{deployLogs[
                                                        app.id
                                                    ].version})
                                                </div>
                                                {deployLogs[app.id].logs ||
                                                    "No logs content."}
                                            {:else}
                                                <span
                                                    class="text-gray-600 italic"
                                                    >No deployment logs found.</span
                                                >
                                            {/if}
                                        {/if}
                                    </div>
                                </div>
                            {/if}
                        </div>
                    {/each}
                </div>
            {/if}
        </div>
    {/if}
</div>
