<script lang="ts">
import {
	LayoutDashboard,
	LogOut,
	Menu,
	ScrollText,
	Server,
	Settings as SettingsIcon,
	Ticket,
	Users,
	Wand2,
	X
} from '@lucide/svelte';
import type { Snippet } from 'svelte';
import { goto } from '$app/navigation';
import { page } from '$app/state';
import { logout } from '$lib/api/auth';
import NavItem from '$lib/components/nav-item.svelte';
import PageTitle from '$lib/components/page-title.svelte';
import ThemeToggle from '$lib/components/theme-toggle.svelte';
import { Button } from '$lib/components/ui/button';
import { Separator } from '$lib/components/ui/separator';

interface Props {
	children: Snippet;
	data: {
		user: {
			id: string;
			username: string;
			email: string | null;
			auth_method: string;
		} | null;
	};
}

const { children, data }: Props = $props();

async function handleLogout() {
	await logout();
	await goto('/login');
}

// Mobile menu state
let mobileMenuOpen = $state(false);

function toggleMobileMenu() {
	mobileMenuOpen = !mobileMenuOpen;
}

function closeMobileMenu() {
	mobileMenuOpen = false;
}

function handleOverlayKeydown(event: KeyboardEvent) {
	if (event.key === 'Escape') {
		closeMobileMenu();
	}
}

// Derive current section title from route
const currentTitle = $derived.by(() => {
	const pathname = page.url.pathname;
	if (pathname.startsWith('/dashboard')) return 'Dashboard';
	if (pathname.startsWith('/invitations')) return 'Invitations';
	if (pathname.startsWith('/users')) return 'Users';
	if (pathname.startsWith('/servers')) return 'Servers';
	if (pathname.startsWith('/wizards')) return 'Wizards';
	if (pathname.startsWith('/logs')) return 'Logs';
	if (pathname.startsWith('/settings')) return 'Settings';
	return 'Admin';
});

// Navigation items configuration
const navItems = [
	{ href: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
	{ href: '/invitations', label: 'Invitations', icon: Ticket },
	{ href: '/users', label: 'Users', icon: Users },
	{ href: '/servers', label: 'Servers', icon: Server },
	{ href: '/wizards', label: 'Wizards', icon: Wand2 },
	{ href: '/logs', label: 'Logs', icon: ScrollText },
	{ href: '/settings', label: 'Settings', icon: SettingsIcon }
] as const;

// Close mobile menu when route changes
$effect(() => {
	page.url.pathname;
	mobileMenuOpen = false;
});
</script>

<div class="min-h-screen bg-cr-bg">
	<!-- Mobile Header -->
	<header
		class="sticky top-0 z-50 flex h-14 items-center justify-between border-b border-cr-border bg-cr-bg px-4 md:hidden"
	>
		<Button
			variant="ghost"
			size="icon"
			onclick={toggleMobileMenu}
			aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
			aria-expanded={mobileMenuOpen}
			class="text-cr-text-muted hover:text-cr-accent"
		>
			{#if mobileMenuOpen}
				<X class="size-5" />
			{:else}
				<Menu class="size-5" />
			{/if}
		</Button>
		<PageTitle>{currentTitle}</PageTitle>
		<ThemeToggle />
	</header>

	<!-- Mobile Navigation Overlay -->
	{#if mobileMenuOpen}
		<!-- biome-ignore lint/a11y/useSemanticElements: The dismiss-only overlay is outside tab order; the menu has a separate keyboard close control. -->
		<div
			class="fixed inset-0 z-40 bg-black/50 md:hidden"
			onclick={closeMobileMenu}
			onkeydown={handleOverlayKeydown}
			role="button"
			tabindex="-1"
			aria-label="Close menu"
		></div>
	{/if}

	<!-- Mobile Sidebar -->
	<aside
		class={[
	'fixed inset-y-0 left-0 z-50 w-64 transform bg-cr-bg border-r border-cr-border transition-transform duration-200 ease-in-out md:hidden',
	mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'
].join(' ')}
	>
		<div class="flex h-14 items-center gap-2.5 px-4">
			<img src="/zondarr-logo.svg" alt="" class="size-7" aria-hidden="true">
			<span class="font-display text-lg font-bold text-cr-accent">Zondarr</span>
		</div>
		<Separator class="bg-cr-border" />
		<nav class="flex flex-1 flex-col gap-1 p-4" aria-label="Main navigation">
			{#each navItems as item}
				<NavItem href={item.href}>
					{#snippet icon()}
						<item.icon class="size-5" />
					{/snippet}
					{item.label}
				</NavItem>
			{/each}
		</nav>
		{#if data.user}
			<div class="border-t border-cr-border p-4">
				<div class="flex items-center justify-between">
					<span class="truncate text-sm text-cr-text-muted font-mono">{data.user.username}</span>
					<Button
						variant="ghost"
						size="icon-sm"
						onclick={handleLogout}
						aria-label="Log out"
						class="text-cr-text-muted hover:text-cr-accent"
					>
						<LogOut class="size-4" />
					</Button>
				</div>
			</div>
		{/if}
	</aside>

	<div class="flex">
		<!-- Desktop Sidebar -->
		<aside
			class="hidden md:flex md:w-64 md:flex-col md:fixed md:inset-y-0 border-r border-cr-border bg-cr-bg"
		>
			<div class="flex h-14 items-center gap-2.5 px-4">
				<img src="/zondarr-logo.svg" alt="" class="size-7" aria-hidden="true">
				<span class="font-display text-lg font-bold text-cr-accent">Zondarr</span>
			</div>
			<Separator class="bg-cr-border" />
			<nav class="flex flex-1 flex-col gap-1 p-4" aria-label="Main navigation">
				{#each navItems as item}
					<NavItem href={item.href}>
						{#snippet icon()}
							<item.icon class="size-5" />
						{/snippet}
						{item.label}
					</NavItem>
				{/each}
			</nav>
			{#if data.user}
				<div class="border-t border-cr-border p-4">
					<div class="flex items-center justify-between">
						<span class="truncate text-sm text-cr-text-muted font-mono">{data.user.username}</span>
						<Button
							variant="ghost"
							size="icon-sm"
							onclick={handleLogout}
							aria-label="Log out"
							class="text-cr-text-muted hover:text-cr-accent"
						>
							<LogOut class="size-4" />
						</Button>
					</div>
				</div>
			{/if}
		</aside>

		<!-- Main Content Area -->
		<div class="flex-1 min-w-0 md:ml-64">
			<!-- Desktop Header -->
			<header
				class="sticky top-0 z-30 hidden h-14 items-center justify-between border-b border-cr-border bg-cr-bg px-6 md:flex"
			>
				<PageTitle>{currentTitle}</PageTitle>
				<ThemeToggle />
			</header>

			<!-- Page Content -->
			<main class="p-4 md:p-6">
				{@render children()}
			</main>
		</div>
	</div>
</div>
