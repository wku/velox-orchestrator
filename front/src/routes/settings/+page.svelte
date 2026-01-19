<script>
    let settings = {
        theme: "dark",
        autoDeploy: true,
        notifyEmail: "admin@example.com",
    };
</script>

<div class="mb-8">
    <h2
        class="text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-white to-gray-400"
    >
        Settings
    </h2>
    <p class="text-gray-400 mt-2">Configure system preferences and users.</p>
</div>

<div class="space-y-6">
    <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
        <h3 class="text-lg font-bold text-white mb-6">General Settings</h3>

        <div class="space-y-4">
            <div class="flex items-center justify-between">
                <div>
                    <h4 class="text-white font-medium">Auto-Deploy</h4>
                    <p class="text-sm text-gray-400">
                        Automatically deploy changes when pushed to Git.
                    </p>
                </div>
                <button
                    class="relative inline-flex h-6 w-11 items-center rounded-full bg-blue-600"
                >
                    <span
                        class="translate-x-6 inline-block h-4 w-4 transform rounded-full bg-white transition"
                    />
                </button>
            </div>
        </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
        <!-- Existing Cards -->

        <a href="/settings/system" class="block group">
            <div
                class="bg-gray-800 rounded-lg p-6 border border-gray-700 group-hover:border-blue-500 transition-colors"
            >
                <div class="flex items-center gap-3 mb-2">
                    <div class="p-2 bg-gray-900 rounded-lg text-blue-400">
                        <svg
                            xmlns="http://www.w3.org/2000/svg"
                            class="h-6 w-6"
                            fill="none"
                            viewBox="0 0 24 24"
                            stroke="currentColor"
                        >
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                stroke-width="2"
                                d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"
                            />
                            <path
                                stroke-linecap="round"
                                stroke-linejoin="round"
                                stroke-width="2"
                                d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                            />
                        </svg>
                    </div>
                    <h2
                        class="text-xl font-bold text-white group-hover:text-blue-400 transition-colors"
                    >
                        System
                    </h2>
                </div>
                <p class="text-gray-400">
                    Manage orchestrator service, restart, system info.
                </p>
            </div>
        </a>
    </div>

    <div class="bg-gray-800 p-6 rounded-lg border border-gray-700">
        <h3 class="text-lg font-bold text-white mb-6">Users & Permissions</h3>
        <p class="text-gray-400 text-sm">
            User management is handled via configuration file in this version.
        </p>
    </div>
</div>
