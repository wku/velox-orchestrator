import { get } from 'svelte/store';
import { isAuthenticated } from '$lib/stores/auth';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function apiCall(endpoint, options = {}) {
    const token = localStorage.getItem('token');

    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
    };

    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }

    const config = {
        ...options,
        headers
    };

    try {
        const res = await fetch(`${API_URL}${endpoint}`, config);

        if (res.status === 401) {
            if (typeof window !== 'undefined') {
                // Only redirect if not already there to avoid loops
                if (window.location.pathname !== '/login') {
                    window.location.href = '/login';
                }
            }
            throw new Error('Unauthorized');
        }

        // Check if response has content
        const contentType = res.headers.get("content-type");
        let data = null;
        if (contentType && contentType.includes("application/json")) {
            data = await res.json();
        } else {
            // For non-JSON (or empty) responses, we usually don't need the body unless error
            // But valid text responses exist.
            const text = await res.text();
            data = text ? text : null;
            // Try to parse as JSON just in case Content-Type was missing but body is JSON
            try {
                if (data) data = JSON.parse(data);
            } catch (e) { }
        }

        if (!res.ok) {
            // Error handling
            let msg = res.statusText;
            if (data && typeof data === 'object' && data.detail) {
                msg = data.detail;
            } else if (typeof data === 'string') {
                msg = data;
            }
            throw new Error(msg || `API Error: ${res.status}`);
        }

        return data;
    } catch (error) {
        console.error(`API Call Failed [${endpoint}]:`, error);
        throw error;
    }
}
