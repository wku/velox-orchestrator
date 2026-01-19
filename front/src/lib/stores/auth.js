import { writable } from 'svelte/store';
import { browser } from '$app/environment';

export const authUser = writable(null);
export const isAuthenticated = writable(false);

if (browser) {
    const token = localStorage.getItem('token');
    const user = localStorage.getItem('user');

    if (token) {
        isAuthenticated.set(true);
        authUser.set(user || 'Admin');
    }
}

export function login(token, user) {
    if (browser) {
        localStorage.setItem('token', token);
        localStorage.setItem('user', user);
    }
    isAuthenticated.set(true);
    authUser.set(user);
}

export function logout() {
    if (browser) {
        localStorage.removeItem('token');
        localStorage.removeItem('user');
    }
    isAuthenticated.set(false);
    authUser.set(null);
}
