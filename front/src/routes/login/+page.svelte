<script>
    import { login as authLogin } from "$lib/stores/auth";

    let username = "";
    let password = "";
    let error = "";
    let loading = false;

    // Use environment variable for API URL or default to localhost
    const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

    async function login() {
        loading = true;
        error = "";

        try {
            const res = await fetch(`${API_URL}/api/v1/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password }),
            });

            if (!res.ok) {
                const data = await res.json();
                throw new Error(data.detail || "Login failed");
            }

            const data = await res.json();
            authLogin(data.access_token, username);
            window.location.href = "/";
        } catch (e) {
            error = e.message;
        } finally {
            loading = false;
        }
    }
</script>

<div
    class="min-h-screen flex items-center justify-center bg-gray-900 text-white"
>
    <div class="bg-gray-800 p-8 rounded-lg shadow-lg w-full max-w-md">
        <h2 class="text-3xl font-bold mb-6 text-center text-blue-400">
            Velox Orchestrator Access
        </h2>

        {#if error}
            <div
                class="bg-red-500/20 text-red-300 p-3 rounded mb-4 text-sm border border-red-500/30"
            >
                {error}
            </div>
        {/if}

        <form on:submit|preventDefault={login} class="space-y-4">
            <div>
                <label class="block text-sm font-medium mb-1 text-gray-400"
                    >Username</label
                >
                <input
                    type="text"
                    bind:value={username}
                    class="w-full bg-gray-700 border border-gray-600 rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    placeholder="Enter username"
                />
            </div>

            <div>
                <label class="block text-sm font-medium mb-1 text-gray-400"
                    >Password</label
                >
                <input
                    type="password"
                    bind:value={password}
                    class="w-full bg-gray-700 border border-gray-600 rounded p-2 focus:ring-2 focus:ring-blue-500 focus:outline-none"
                    placeholder="Enter password"
                />
            </div>

            <button
                type="submit"
                class="w-full bg-blue-600 hover:bg-blue-500 text-white font-semibold py-2 rounded transition-colors disabled:opacity-50"
                disabled={loading}
            >
                {loading ? "Authenticating..." : "Login"}
            </button>
        </form>
    </div>
</div>
