<script>
    import { apiCall } from "$lib/api";
    import { goto } from "$app/navigation";

    let activeTab = "git";
    let loading = false;
    let error = "";

    // Git Deployment
    let gitRepo = {
        url: "",
        branch: "main",
        provider: "github",
        config_file: "docker-compose.yml",
    };

    // Local Deployment
    let localPath = "";

    async function deployGit() {
        loading = true;
        error = "";
        try {
            // 1. Create Git Repo
            const repo = await apiCall("/api/v1/repos", {
                method: "POST",
                body: JSON.stringify(gitRepo),
            });

            // 2. Trigger Deploy
            await apiCall(`/api/v1/repos/${repo.id}/deploy`, {
                method: "POST",
            });

            // Redirect to repos list or find the created project?
            // Deploy returns { status: 'deploying', applications: [...] }
            // We can redirect to projects list.
            goto("/projects");
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    }

    async function deployLocal() {
        loading = true;
        error = "";
        try {
            await apiCall("/api/v1/deploy/local", {
                method: "POST",
                body: JSON.stringify({
                    path: localPath,
                }),
            });
            goto("/projects");
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    }
</script>

<div class="max-w-3xl mx-auto">
    <div class="mb-8">
        <a
            href="/projects"
            class="text-blue-400 hover:text-blue-300 mb-4 inline-block"
            >&larr; Back to Projects</a
        >
        <h2 class="text-3xl font-bold text-white">Deploy Project</h2>
        <p class="text-gray-400 mt-2">
            Create a new project from a Git repository or Local Server Path.
        </p>
    </div>

    {#if error}
        <div
            class="bg-red-900/30 text-red-200 p-4 rounded-lg border border-red-500/30 mb-6 font-mono text-sm whitespace-pre-wrap"
        >
            {error}
        </div>
    {/if}

    <div class="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
        <!-- Tabs -->
        <div class="flex border-b border-gray-700">
            <button
                class="px-6 py-4 text-sm font-medium transition-colors border-b-2 {activeTab ===
                'git'
                    ? 'border-blue-500 text-blue-400 bg-gray-700/50'
                    : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-700/30'}"
                on:click={() => (activeTab = "git")}
            >
                From Git Repository
            </button>
            <button
                class="px-6 py-4 text-sm font-medium transition-colors border-b-2 {activeTab ===
                'local'
                    ? 'border-blue-500 text-blue-400 bg-gray-700/50'
                    : 'border-transparent text-gray-400 hover:text-gray-200 hover:bg-gray-700/30'}"
                on:click={() => (activeTab = "local")}
            >
                Local Path (Server)
            </button>
        </div>

        <div class="p-8">
            {#if activeTab === "git"}
                <form on:submit|preventDefault={deployGit} class="space-y-6">
                    <div
                        class="bg-blue-900/20 border-l-4 border-blue-500 p-4 mb-6"
                    >
                        <p class="text-sm text-blue-200">
                            Velox Orchestrator will clone the repository, read <code
                                >docker-compose.yml</code
                            >, build images, and deploy services with a
                            persistent Webhook.
                        </p>
                    </div>

                    <div>
                        <label
                            for="git-url"
                            class="block text-sm font-medium text-gray-300 mb-2"
                            >Git Repository URL</label
                        >
                        <input
                            id="git-url"
                            bind:value={gitRepo.url}
                            required
                            type="url"
                            class="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                            placeholder="https://github.com/my/repo.git or git@..."
                        />
                    </div>

                    <div class="grid grid-cols-2 gap-4">
                        <div>
                            <label
                                for="git-branch"
                                class="block text-sm font-medium text-gray-300 mb-2"
                                >Branch</label
                            >
                            <input
                                id="git-branch"
                                bind:value={gitRepo.branch}
                                type="text"
                                class="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                placeholder="main"
                            />
                        </div>
                        <div>
                            <label
                                for="config-file"
                                class="block text-sm font-medium text-gray-300 mb-2"
                                >Config File</label
                            >
                            <input
                                id="config-file"
                                bind:value={gitRepo.config_file}
                                type="text"
                                class="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white focus:outline-none focus:border-blue-500"
                                placeholder="docker-compose.yml"
                            />
                        </div>
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        class="w-full bg-blue-600 hover:bg-blue-500 text-white py-2 rounded-lg font-medium transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
                    >
                        {#if loading}
                            <span
                                class="animate-spin h-4 w-4 border-2 border-white/50 border-t-white rounded-full"
                            ></span>
                            Deploying...
                        {:else}
                            Start Deployment
                        {/if}
                    </button>
                </form>
            {:else if activeTab === "local"}
                <form on:submit|preventDefault={deployLocal} class="space-y-6">
                    <div
                        class="bg-gray-700/50 p-4 rounded text-sm text-gray-300 mb-4"
                    >
                        <p>
                            Specify an absolute path on the <strong
                                >{window.location.hostname}</strong
                            >
                            server containing <code>docker-compose.yml</code>.
                        </p>
                    </div>

                    <div>
                        <label
                            for="local-path"
                            class="block text-sm font-medium text-gray-300 mb-2"
                            >Absolute Path</label
                        >
                        <input
                            id="local-path"
                            bind:value={localPath}
                            required
                            type="text"
                            class="w-full bg-gray-900 border border-gray-700 rounded px-4 py-2 text-white font-mono focus:outline-none focus:border-blue-500"
                            placeholder="/home/user/projects/my-app"
                        />
                    </div>

                    <button
                        type="submit"
                        disabled={loading}
                        class="w-full bg-green-600 hover:bg-green-500 text-white py-2 rounded-lg font-medium transition-colors disabled:opacity-50 flex justify-center items-center gap-2"
                    >
                        {#if loading}
                            <span
                                class="animate-spin h-4 w-4 border-2 border-white/50 border-t-white rounded-full"
                            ></span>
                            Deploying...
                        {:else}
                            Deploy from Path
                        {/if}
                    </button>
                </form>
            {/if}
        </div>
    </div>
</div>
